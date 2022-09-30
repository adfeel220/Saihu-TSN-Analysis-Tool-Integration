import warnings
import numpy as np
import pulp
import json

from typing import List, Union

## Helper functions
def var_set_name(name: str, *indices) -> str:
    '''
    Format the variable name. For example,
    base name: 'x', indices are 1 and 2, then the name is set as 'x_1,2'
    '''
    name += '_'
    for idx in indices:
        name += str(idx) + ','

    return name[:-1]

def var_get_name(name: str) -> tuple:
    '''
    Obtain the base name and indices from the formated variable name. For example,
    "x_1,2" -> ('x', [1,2])
    '''
    base_name, indices = name.split('_')
    indices = indices.split(',')
    indices = [int(idx) for idx in indices]
    
    return base_name, indices


## Class Definition
class tsn_analyzer():


    def __init__(self, filename:str=None) -> None:
        # The adjacency matrix for the network topology
        self.adjacency_mat = None
        self.num_servers = 0

        # The flows which pass through the network
        self.flows = []
        self.num_flows = 0

        self.servers = []

        # For debug
        self.solver = None

        if filename is not None:
            self.load(filename)


    def load(self, filename:str) -> None:
        '''
        Load from a predefined network in json
        '''
        with open(filename) as f:
            network_def = json.load(f)
        
        try:
            self.parse(network_def)
        except Exception as e:
            print(f"Capturing error while loading file {filename}.")
            raise e
            


    def parse(self, network_def:dict) -> None:
        '''
        A network_def object should contain
        
        1. adjacency matrix:
         - a 2D array representing a directed graph
        
        2. flows:
         - a list of objects representing each flow.
           a flow is defined by
           - path: a list of non-repeating indicing of servers
           - packet_length: max packet size arrives at this flow
           - arrival_curve: an object defines a concave curve and contains
             - bursts: a list indicates bursts of curves
             - (times: a list of time where rates changes) (to be computed)
             - rates: a decreasing list of arrival rates w.r.t. "times"
        
        3. servers:
         - a list of objects representing each server.
           a server is defined by
           - capacity: the output capacity of server (shaper constraint)
           - service_curve: an object defines a convex curve and contains
             - latencies: a list indicates latencies of curves
             - (times: a list of time where rates changes) (to be computed)
             - rates: a increasing list of service rates w.r.t. "times"
        '''

        ## Load adjacency matrix
        self.adjacency_mat = np.array(network_def['adjacency_matrix'])
        self.num_servers   = self.adjacency_mat.shape[0]
        # Assert the input is a valid adjacency matrix
        if len(self.adjacency_mat.shape) != 2:
            raise SyntaxError(f"Adjacency matrix dimension incorrect. Expect 2 but get {len(self.adjacency_mat.shape)}")
        if self.adjacency_mat.shape[0] != self.adjacency_mat.shape[1]:
            raise SyntaxError(f"Adjacency matrix should be square, get dimension {self.adjacency_mat.shape} instead")

        ## Load flows
        self.flows = []
        for id, fl in enumerate(network_def['flows']):
            path = fl["path"]

            ## Check if it's a valid path
            # 1. no recurring server along the path
            if len(path) != len(set(path)):
                warnings.warn(f"Skip flow {id} due to recurring server in its path: {path}")
                continue
            # 2. path definition matches the number of servers. i.e. 0 < path_length <= # of servers
            if len(path) <= 0:
                warnings.warn(f"Skip flow {id} because its path is empty")
                continue
            for s in path:
                if s >= self.num_servers or s < 0:
                    raise SyntaxError(f"Path definition in flow {id} is incorrect. Server ID should be 0-{self.num_servers-1}, get {s} instead.")

            ## Check arrival curve syntax
            arrival_curve = fl["arrival_curve"]
            # assertion of arrival curve definition
            self.assert_arrival_curve(arrival_curve=arrival_curve, flow_id=id)
            # Assign times where arrival curve changes rate
            self.__set_arrcur_times(arrival_curve)

            ## Check packet length
            if fl["packet_length"] < 0:
                pkt_len = fl["packet_length"]
                raise ValueError(f"Packet length of flow {id} is negative ({pkt_len}), should at least >= 0.")

            self.flows.append(fl.copy())

        self.num_flows = len(self.flows)

        ## Load servers
        self.servers = []
        for ser_id, ser in enumerate(network_def["servers"]):

            ## Assign packet length according to flow paths
            pkt_len = [fl["packet_length"] for fl in self.__get_flows(ser_id)]    # packet lengths of the involved flows
            # Assign the maximum possible packet length that passes through the server
            ser['packet_length'] = max(pkt_len)

            ## Check service curve
            # assertion of arrival curve definition
            self.assert_service_curve(ser["service_curve"], ser_id)
            # Assign times where service curve changes rate
            self.__set_sercur_times(ser["service_curve"])

            ## Check server capacity
            if ser["capacity"] <= 0:
                raise ValueError(f"Capacity of server {ser_id} is non-positive, should at least >0.")

            self.servers.append(ser.copy())
            
        if len(self.servers) != self.num_servers:
            raise ValueError(f"Network adjacency matrix doesn't match with server definitions. Network is defined with {self.num_servers} nodes but {len(self.servers)} servers defined.")

        


    def set_utility(self, utility:float) -> dict:
        '''
        Set the utility (0,1) to the assigned value and assign an unanimous arrival rate r = u*R/n to all flows.
        where u is utility; R is service rate; n is the maximum amount of flows goes through a server.

        Params:
        utility: (0,1) value of network utility/load

        Returns:
        num_flow: number of flows passses through a server
        max_flow: maximum amount of flows passses through a server
        arr_rate: the assigned arrival rate, None if no change of arrival rate
        '''
        # Calculate the number of flows passes through each server
        num_flows_per_server = [0]*self.num_servers
        for fl in self.flows:
            for server_idx in fl["path"]:
                num_flows_per_server[server_idx] += 1
        
        # Calculate the minimum service rate among servers
        min_ser_rate = np.inf
        for serv in self.servers:
            rate = serv["service_curve"]["rates"][0]
            if rate < min_ser_rate:
                min_ser_rate = rate

        # Calculate the corresponding arrival rate for the utility
        max_flows = max(num_flows_per_server)
        arr_rate = utility*min_ser_rate/max_flows

        # Assign the new arrival rate
        for fl in self.flows:
            fl["arrival_curve"]["times"] = []
            fl["arrival_curve"]["rates"] = [arr_rate]

        return {"num_flow": num_flows_per_server,
                "max_flow": max_flows,
                "arr_rate": arr_rate}


    def get_utility(self) -> float:
        '''
        Return the utility of current network
        '''
        # maximum aggregated arrival rate for each server
        max_agg_arr_rate = np.array([0]*self.num_servers)
        for fl in self.flows:
            for server_idx in fl["path"]:
                max_agg_arr_rate[server_idx] += fl["arrival_curve"]["rates"][0]

        ser_rates = np.array([0]*self.num_servers)
        for idx, serv in enumerate(self.servers):
            ser_rates[idx] = serv["service_curve"]["rates"][0]
        
        return max(max_agg_arr_rate / ser_rates)


    def set_topology(self, adjacency_mat=np.ndarray) -> None:
        '''
        Assign network topology as a directed graph with a adjacency matrix
        '''
        # Assert the input is a valid adjacency matrix
        assert len(adjacency_mat.shape) == 2
        assert adjacency_mat.shape[0] == adjacency_mat.shape[1]

        self.adjacency_mat = np.copy(adjacency_mat)
        self.num_servers = adjacency_mat.shape[0]

    
    def add_links(self, links:Union[list,tuple]) -> None:
        '''
        Add new links, if the index exceed current number of servers, add new servers automatically.

        Params:
        links: a tuple or a list of tuples, each tuple pair indicates (source, destination) on the network
        '''
        
        if type(links) is tuple:
            self.__allocate_link(links)

        elif type(links) is list:
            for lk in links:
                assert type(lk) is tuple
                self.__allocate_link(lk)

    def __allocate_link(self, link:tuple) -> None:
        '''
        Add a link in the network if both source and destination

        Params:
        link: a tuple of (source, destination) of server indices
        '''
        assert len(link) == 2

        # Valid assignment
        if link[0] < self.num_servers and link[1] < self.num_servers:
            self.adjacency_mat[link] = 1
        else:
            # Create a larger network that fits the assignment
            new_size = max(link)+1
            new_adj_mat = np.zeros((new_size, new_size), dtype=np.int32)
            # copy the original network
            new_adj_mat[:self.num_servers, :self.num_servers] = self.adjacency_mat
            # assign new link
            new_adj_mat[link] = 1

            self.adjacency_mat = np.copy(new_adj_mat)



    def solve_tfa(self, problem_name:str="TFA problem") -> list:
        '''
        Solve the TFA problem given that the network is defined properly

        Returns:
        delays: array of delay guarantees at each server
        '''

        # setup the lp problem for the TFA Linear program
        tfa_prog = pulp.LpProblem('TFA_Program', pulp.LpMaximize)
        # variables
        in_time    = [None]*self.num_servers
        out_time   = [None]*self.num_servers
        delays     = [None]*self.num_servers
        arrivals   = [[None]*self.num_servers for _ in range(self.num_flows)]
        departures = [[None]*self.num_servers for _ in range(self.num_flows)]
        bursts     = [[None]*self.num_servers for _ in range(self.num_flows)]

        # for all server j
        for server_idx, server in enumerate(self.servers):
            # Time constraints
            s_var = var_set_name('s', server_idx)
            t_var = var_set_name('t', server_idx)
            in_time[server_idx]  = pulp.LpVariable(s_var, lowBound=0)
            out_time[server_idx] = pulp.LpVariable(t_var, lowBound=0)
            
            tfa_prog += in_time[server_idx] <= out_time[server_idx]    # add constraint that s <= t

            # Arrival constraints
            for fl, fl_idx in self.__get_flows(server_idx, enum_iter=True):
                As_var = var_set_name('As', fl_idx, server_idx)
                x_var  = var_set_name('x' , fl_idx, server_idx)
                Dt_var = var_set_name('Dt', fl_idx, server_idx)
                arrivals[fl_idx][server_idx]   = pulp.LpVariable(As_var, lowBound=0)
                bursts[fl_idx][server_idx]     = pulp.LpVariable(x_var, lowBound=0)
                departures[fl_idx][server_idx] = pulp.LpVariable(Dt_var, lowBound=0)

                arrival_curve = fl["arrival_curve"]

                tfa_prog += arrivals[fl_idx][server_idx] <= bursts[fl_idx][server_idx] + arrival_curve["rates"][0]*in_time[server_idx]

                # Deal with the extra segments of the arrival curve because of piecewise linearity
                num_arrcur_seg = len(arrival_curve["times"])   # number of arrival curve segments
                cumulation = 0
                prev_t = 0  # previous time snap
                for seg in range(num_arrcur_seg):
                    cumulation += (arrival_curve["times"][seg] - prev_t) * arrival_curve["rates"][seg]
                    tfa_prog += arrivals[fl_idx][server_idx] <= bursts[fl_idx][server_idx] + cumulation + arrival_curve["rates"][seg+1] * (in_time[server_idx] - arrival_curve["times"][seg])

                    prev_t = arrival_curve["times"][seg]

            ## Service constraints
            service_curve = server["service_curve"]
            tfa_prog += pulp.lpSum([departures[fl_idx][server_idx] for _, fl_idx in self.__get_flows(server_idx, enum_iter=True)]) \
                        >= service_curve["rates"][0]*out_time[server_idx] - service_curve["rates"][0]*service_curve["latencies"][0]
            tfa_prog += pulp.lpSum([departures[fl_idx][server_idx] for _, fl_idx in self.__get_flows(server_idx, enum_iter=True)]) >= 0

            # Check all segments of the piecewise linear service curve
            num_sercur_seg = len(service_curve["times"])
            cumulation = 0
            prev_t = service_curve["latencies"][0]
            for seg in range(num_sercur_seg):
                cumulation += service_curve["rates"][seg]*(service_curve["times"][seg] - prev_t)
                tfa_prog += pulp.lpSum([departures[fl_idx][server_idx] for _, fl_idx in self.__get_flows(server_idx, enum_iter=True)]) \
                            >= service_curve["rates"][seg+1] * (out_time[server_idx] - service_curve["times"][seg]) + cumulation

                prev_t = service_curve["times"][seg]

            ## FIFO constraints
            for fl, fl_idx in self.__get_flows(server_idx, enum_iter=True):
                tfa_prog += arrivals[fl_idx][server_idx] == departures[fl_idx][server_idx]

            # delays
            d_var = var_set_name('d', server_idx)
            delays[server_idx] = pulp.LpVariable(d_var, lowBound=0)

            tfa_prog += delays[server_idx] <= out_time[server_idx] - in_time[server_idx]

        # Constraints on burst variables (x)
        # Burst propagation
        for server_idx, server in enumerate(self.servers):
            for fl, fl_idx in self.__get_flows(server_idx, enum_iter=True):
                arrival_curve = fl["arrival_curve"]

                for succ in self.__get_successor(server_idx):
                    # propagate only when server -> succ is in current flow
                    if not (server_idx in fl["path"] and succ in fl["path"]):
                        continue

                    tfa_prog += bursts[fl_idx][succ] <= bursts[fl_idx][server_idx] + arrival_curve["rates"][0]*delays[server_idx]
                    # Consider piecewise linear arrival curves
                    num_arrcur_seg = len(arrival_curve["times"])   # number of arrival curve segments
                    cumulation = 0
                    prev_t = 0  # previous time snap
                    for seg in range(num_arrcur_seg):
                        cumulation += (arrival_curve["times"][seg] - prev_t) * arrival_curve["rates"][seg]
                        tfa_prog += bursts[fl_idx][succ] <= bursts[fl_idx][server_idx] + cumulation + arrival_curve["rates"][seg+1] * (delays[server_idx] - arrival_curve["times"][seg])

                        prev_t = arrival_curve["times"][seg]

        # initial bursts 
        for flow_idx, flow in enumerate(self.flows):
            initial_server = flow["path"][0]
            initial_burst  = flow["arrival_curve"]["bursts"][0]
            tfa_prog += bursts[flow_idx][initial_server] <= initial_burst

        # Set objective function
        tfa_prog += pulp.lpSum(delays)

        ## Solve the problem
        status = tfa_prog.solve(pulp.PULP_CBC_CMD(msg=False))

        self.solver = tfa_prog

        # Check solver status
        if status < 1:
            # The problem is not solved, show the issue
            print(f"Problem \"{problem_name}\" is {pulp.LpStatus[status]}.")
            return [np.inf]
        else:
            optimal_delay = []
            for d in delays:
                optimal_delay.append(pulp.value(d))

            return optimal_delay


    def solve_tfa_pp(self, problem_name:str="TFA++ problem") -> list:
        '''
        Solve the TFA++ problem given that the network is defined properly

        Returns:
        delays: array of delay guarantees at each server
        '''
        # ensure the problem is properly defined
        assert self.adjacency_mat is not None

        # setup the lp problem for the TFA Linear program
        tfa_pp_prog = pulp.LpProblem('TFA++_Program', pulp.LpMaximize)
        # variables
        in_time    = [None]*self.num_servers
        out_time   = [None]*self.num_servers
        delays     = [None]*self.num_servers
        arrivals   = [[None]*self.num_servers for _ in range(self.num_flows)]
        departures = [[None]*self.num_servers for _ in range(self.num_flows)]
        bursts     = [[None]*self.num_servers for _ in range(self.num_flows)]

        # for all server j
        for server_idx, server in enumerate(self.servers):
            # Time constraints
            s_var = var_set_name('s', server_idx)
            t_var = var_set_name('t', server_idx)
            in_time[server_idx]  = pulp.LpVariable(s_var, lowBound=0)
            out_time[server_idx] = pulp.LpVariable(t_var, lowBound=0)
            
            tfa_pp_prog += in_time[server_idx] <= out_time[server_idx]    # add constraint that s <= t

            # Arrival constraints
            for fl, fl_idx in self.__get_flows(server_idx, enum_iter=True):
                As_var = var_set_name('As', fl_idx, server_idx)
                x_var  = var_set_name('x' , fl_idx, server_idx)
                Dt_var = var_set_name('Dt', fl_idx, server_idx)
                arrivals[fl_idx][server_idx]   = pulp.LpVariable(As_var, lowBound=0)
                bursts[fl_idx][server_idx]     = pulp.LpVariable(x_var, lowBound=0)
                departures[fl_idx][server_idx] = pulp.LpVariable(Dt_var, lowBound=0)

                arrival_curve = fl["arrival_curve"]

                tfa_pp_prog += arrivals[fl_idx][server_idx] <= bursts[fl_idx][server_idx] + arrival_curve["rates"][0]*in_time[server_idx]

                # Deal with the extra segments of the arrival curve because of piecewise linearity
                num_arrcur_seg = len(arrival_curve["times"])   # number of arrival curve segments
                cumulation = 0
                prev_t = 0  # previous time snap
                for seg in range(num_arrcur_seg):
                    cumulation += (arrival_curve["times"][seg] - prev_t) * arrival_curve["rates"][seg]
                    tfa_pp_prog += arrivals[fl_idx][server_idx] <= bursts[fl_idx][server_idx] + cumulation + arrival_curve["rates"][seg+1] * (in_time[server_idx] - arrival_curve["times"][seg])

                    prev_t = arrival_curve["times"][seg]

            ## Service constraints
            service_curve = server["service_curve"]
            tfa_pp_prog += pulp.lpSum([departures[fl_idx][server_idx] for _, fl_idx in self.__get_flows(server_idx, enum_iter=True)]) \
                        >= service_curve["rates"][0]*out_time[server_idx] - service_curve["rates"][0]*service_curve["latencies"][0]
            tfa_pp_prog += pulp.lpSum([departures[fl_idx][server_idx] for _, fl_idx in self.__get_flows(server_idx, enum_iter=True)]) >= 0

            # Check all segments of the piecewise linear service curve
            num_sercur_seg = len(service_curve["times"])
            cumulation = 0
            prev_t = service_curve["latencies"][0]
            for seg in range(num_sercur_seg):
                cumulation += service_curve["rates"][seg]*(service_curve["times"][seg] - prev_t)
                tfa_pp_prog += pulp.lpSum([departures[fl_idx][server_idx] for _, fl_idx in self.__get_flows(server_idx, enum_iter=True)]) \
                            >= service_curve["rates"][seg+1] * (out_time[server_idx] - service_curve["times"][seg]) + cumulation

                prev_t = service_curve["times"][seg]

            ## FIFO constraints
            for fl, fl_idx in self.__get_flows(server_idx, enum_iter=True):
                tfa_pp_prog += arrivals[fl_idx][server_idx] == departures[fl_idx][server_idx]

            # delays
            d_var = var_set_name('d', server_idx)
            delays[server_idx] = pulp.LpVariable(d_var, lowBound=0)

            tfa_pp_prog += delays[server_idx] <= out_time[server_idx] - in_time[server_idx]

        # Constraints on burst variables (x)
        # Burst propagation
        for server_idx, server in enumerate(self.servers):
            for fl, fl_idx in self.__get_flows(server_idx, enum_iter=True):
                arrival_curve = fl["arrival_curve"]

                for succ in self.__get_successor(server_idx):
                    # propagate only when server -> succ is in current flow
                    if not (server_idx in fl["path"] and succ in fl["path"]):
                        continue

                    tfa_pp_prog += bursts[fl_idx][succ] <= bursts[fl_idx][server_idx] + arrival_curve["rates"][0]*delays[server_idx]
                    # tfa_pp_prog += bursts[fl_idx][succ] >= bursts[fl_idx][server_idx]
                    # Consider piecewise linear arrival curves
                    num_arrcur_seg = len(arrival_curve["times"])   # number of arrival curve segments
                    cumulation = 0
                    prev_t = 0  # previous time snap
                    for seg in range(num_arrcur_seg):
                        cumulation += (arrival_curve["times"][seg] - prev_t) * arrival_curve["rates"][seg]
                        tfa_pp_prog += bursts[fl_idx][succ] <= bursts[fl_idx][server_idx] + cumulation + arrival_curve["rates"][seg+1] * (delays[server_idx] - arrival_curve["times"][seg])

                        prev_t = arrival_curve["times"][seg]

        # initial bursts 
        for flow_idx, flow in enumerate(self.flows):
            initial_server = flow["path"][0]
            initial_burst  = flow["arrival_curve"]["bursts"][0]
            tfa_pp_prog += bursts[flow_idx][initial_server] <= initial_burst

        # Shaper constraints
        # Adding shaping constraint
        for server_id, server in enumerate(self.servers):
            for succ in self.__get_successor(server_id):
                flows_prev = set(self.__get_flows(server_id, indices=True))
                flows_next = set(self.__get_flows(succ, indices=True))
                mutual_flows = list(flows_prev.intersection(flows_next))
                # select flows only when the path "server_id -> succ" is in the flow
                seq_flows = []
                for fl_idx in mutual_flows:
                    if self.flows[fl_idx]["path"].index(server_id)+1 == self.flows[fl_idx]["path"].index(succ):
                        seq_flows.append(fl_idx)

                tfa_pp_prog += pulp.lpSum(arrivals[fl][succ] for fl in seq_flows) <= server["packet_length"] + server["capacity"]*in_time[succ]

        # Set objective function
        tfa_pp_prog += pulp.lpSum(delays)
        # tfa_pp_prog += pulp.lpSum([b for sublist in bursts for b in sublist])

        ## Solve the problem
        status = tfa_pp_prog.solve(pulp.GLPK_CMD(msg=False))

        self.solver = tfa_pp_prog

        # Check solver status
        if status < 1:
            # The problem is not solved, show the issue
            print(f"Problem \"{problem_name}\" is {pulp.LpStatus[status]}.")
            return [np.inf]
        else:
            optimal_delay = []
            for d in delays:
                optimal_delay.append(pulp.value(d))

            return optimal_delay


    def __get_flows(self, server: int, enum_iter:bool=False, indices:bool=False) -> list:
        '''
        Given a server j, find the indices of flow Fl(j) that passes server j
        the answer is returned in a list
        '''
        assert len(self.flows) == self.num_flows

        output = []
        for idx, fl in enumerate(self.flows):
            if server in fl["path"]:
                if enum_iter:
                    output.append((fl, idx))
                elif indices:
                    output.append(idx)
                else:
                    output.append(fl)

        return output

    def __get_successor(self, server: int) -> list:
        '''
        Given a server j, find the indices of servers which are successors of j
        the answer is returned in a list
        '''
        succ = np.argwhere(self.adjacency_mat[server])
        if len(succ) == 0:
            return []
        else:
            return list(np.argwhere(self.adjacency_mat[server])[0])


    def assert_arrival_curve(self, arrival_curve:dict, flow_id:int) -> None:
        '''
        assert the properties of an arrival curve
        '''

        bursts_len = len(arrival_curve["bursts"])
        rates_len  = len(arrival_curve["rates"])

        # Ensure there's at least 1 line defined
        if bursts_len < 1:
            raise SyntaxError(f"No burst defined in the arrival curve of flow {flow_id}")
        if rates_len < 1:
            raise SyntaxError(f"No arrival rate defined in the arrival curve of flow {flow_id}")

        # Check number of segments of the arrival curve coherent in bursts/rates
        min_len = min(bursts_len, rates_len)
        if bursts_len != rates_len:
            warnings.warn(f"\nLength of bursts and arrival rates are different in flow {flow_id}. {bursts_len} numbers in bursts' definition and {rates_len} in rates'. Consider the shorter one ({min_len}) instead", SyntaxWarning)
            arrival_curve["bursts"] = arrival_curve["bursts"][:min_len]
            arrival_curve["rates"]  = arrival_curve["rates"][:min_len]

        # Check the curve is concave
        prev_burst = 0
        prev_rate  = np.inf
        for i in range(min_len):
            curr_burst = arrival_curve["bursts"][i]
            curr_rate  = arrival_curve["rates"][i]
            if curr_burst <= prev_burst or curr_rate >= prev_rate:
                warnings.warn(f"Arrival curve of flow {flow_id} doesn't satisfy concavity, this may cause the problem to be unsolvable", Warning)
            
            prev_burst = curr_burst
            prev_rate  = curr_rate


    def __set_arrcur_times(self, arrival_curve:dict) -> None:
        '''
        Add an extra list "times" in the curve that indicates the time snaps where the rate changes
        '''
        bursts_len = len(arrival_curve["bursts"])
        rates_len  = len(arrival_curve["rates"])
        min_len    = min(bursts_len, rates_len)

        turn_points = [0]*(min_len-1)

        for t in range(len(turn_points)):
            turn_points[t] = (arrival_curve["bursts"][t+1] - arrival_curve["bursts"][t]) / (arrival_curve["rates"][t] - arrival_curve["rates"][t+1])

        arrival_curve["times"] = turn_points


    def assert_service_curve(self, service_curve:dict, server_id:int) -> None:
        '''
        assert the properties of a service curve
        '''
        lat_len  = len(service_curve["latencies"])
        rate_len = len(service_curve["rates"])

        # Ensure there's at least 1 line defined
        if lat_len < 1:
            raise SyntaxError(f"No latency defined in the service curve of server {server_id}")
        if rate_len < 1:
            raise SyntaxError(f"No service rate defined in the service curve of server {server_id}")

        # Check number of segments of the service curve coherent in latencies/rates
        min_len = min(lat_len, rate_len)
        if lat_len != rate_len:
            warnings.warn(f"\nLength of latencies and services rates are different in server {server_id}. {lat_len} numbers in latencies' definition and {rate_len} in rates'. Consider the shorter one ({min_len}) instead", SyntaxWarning)
            service_curve["latencies"] = service_curve["latencies"][:min_len]
            service_curve["rates"]     = service_curve["rates"][:min_len]

        # Check the curve is concave
        prev_latency = 0
        prev_rate  = 0
        for i in range(min_len):
            curr_latency = service_curve["latencies"][i]
            curr_rate    = service_curve["rates"][i]
            if curr_latency <= prev_latency or curr_rate <= prev_rate:
                warnings.warn(f"Service curve of server {server_id} doesn't satisfy convexity, this may cause the problem to be unsolvable", Warning)
            
            prev_latency = curr_latency
            prev_rate  = curr_rate

    
    def __set_sercur_times(self, service_curve:dict) -> None:
        '''
        Add an extra list "times" in the curve that indicates the time snaps where the rate changes
        '''
        assert len(service_curve["latencies"]) == len(service_curve["rates"])
        turn_points = [0]*(len(service_curve["rates"])-1)

        for t in range(len(turn_points)):
            turn_points[t] = (service_curve["rates"][t+1]*service_curve["latencies"][t+1] - service_curve["rates"][t]*service_curve["latencies"][t]) / (service_curve["rates"][t+1] - service_curve["rates"][t])

        service_curve["times"] = turn_points