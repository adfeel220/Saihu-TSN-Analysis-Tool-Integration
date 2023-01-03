import warnings
import numpy as np
import pulp
import json
from .util import *
from netscript.netdef import OutputPortNet

from copy import deepcopy

# set custom warning message
warnings.showwarning = warning_override

## Class Definition
class Linear_TFA():

    network_info   : dict
    adjacency_mat  : np.ndarray
    num_servers    : int
    num_flows      : int
    flows          : list
    servers        : list
    server_no_flow : set
    shaper_defined : bool
    solver         : pulp.LpProblem


    def __init__(self, filename:str=None) -> None:

        # General network information
        self.network_info = dict()
        self.units = {'time': None, 'data': None, 'rate': None}

        # The adjacency matrix for the network topology
        self.adjacency_mat = None

        # The flows which pass through the network
        self.flows = []

        self.servers = []
        self.server_no_flow = set() # server without any flow passes through it, need to exclude from problem otherwise the problem is unbounded

        self.shaper_defined = True

        ## Debug
        # The linear solver used to solve the problem
        self.solver = None

        if filename is not None:
            self.load(filename)

    @property
    def num_servers(self):
        return len(self.servers)
    
    @property
    def num_flows(self):
        return len(self.flows)


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
        Parse the network into the information needed for this tool
        '''
        # Read by output port network
        output_port_net = OutputPortNet(network_def=network_def)

        # Load general network information
        self.network_info  = deepcopy(output_port_net.network_info)
        self.units = deepcopy(output_port_net.units)
        self.adjacency_mat = output_port_net.adjacency_mat.copy()
        self.flows = deepcopy(output_port_net.flows)
        self.servers = deepcopy(output_port_net.servers)

        # Check flows
        for fl in self.flows:
            ## Check arrival curve syntax
            arrival_curve = fl["arrival_curve"]
            # assertion of arrival curve definition
            self.assert_arrival_curve(arrival_curve=arrival_curve, flow_name=fl["name"])
            # Assign times where arrival curve changes rate
            self.__set_arrcur_times(arrival_curve)

        # Check servers
        for ser in self.servers:
            # assertion of arrival curve definition
            self.assert_service_curve(ser["service_curve"], ser["name"])
            # Assign times where service curve changes rate
            self.__set_sercur_times(ser["service_curve"])

            ## Check server capacity
            # Turn off shaper if any of the server doesn't have shaper
            if "capacity" not in ser:
                self.shaper_defined = False
            if ser["capacity"] <= 0:
                warnings.warn("Capacity of server \"{0}\" is non-positive, should at least >0. Ignore using shaper.".format(ser["name"]))        

            # Assign server packet lengths by the maximum of max-packet-length of all flows that passes through this server
            pkt_len = [fl.get("max_packet_length", 0) for fl in self.__get_flows(ser["id"])]    # packet lengths of the involved flows
            if len(pkt_len) > 0:
                ser["max_packet_length"] = max(pkt_len)
            else:
                warnings.warn("No flow passes through server \"{0}\", you may remove it from the analysis".format(ser["name"]))
                self.server_no_flow.add(ser["id"])
                ser['max_packet_length'] = 0


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


    def solve(self) -> list:
        '''
        Solve the problem given that the network is defined properly,
        Use shaper if shaper is defined

        Returns:
        delays: array of delay bounds at each server
        '''
        if self.shaper_defined:
            return self.solve_tfa_pp()
        else:
            return self.solve_tfa()


    def solve_tfa(self, problem_name:str="TFA problem") -> list:
        '''
        Solve the TFA problem given that the network is defined properly

        Returns:
        delays: array of delay guarantees at each server
        '''

        # setup the lp problem for the TFA Linear program
        tfa_prog = pulp.LpProblem('TFA_Program', pulp.LpMaximize)
        # variables
        in_time    = [0]*self.num_servers
        out_time   = [0]*self.num_servers
        delays     = [0]*self.num_servers
        arrivals   = [[0]*self.num_servers for _ in range(self.num_flows)]
        departures = [[0]*self.num_servers for _ in range(self.num_flows)]
        bursts     = [[0]*self.num_servers for _ in range(self.num_flows)]

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

            # Only compute server with flow passes through, otherwise the delay is unbounded
            if server_idx in self.server_no_flow:
                tfa_prog += delays[server_idx] == 0
                continue

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
        if not self.shaper_defined:
            raise RuntimeError("Shaper is not defined while trying to solve a TFA with shaper")

        # setup the lp problem for the TFA Linear program
        tfa_pp_prog = pulp.LpProblem('TFA++_Program', pulp.LpMaximize)
        # variables
        in_time    = [0]*self.num_servers
        out_time   = [0]*self.num_servers
        delays     = [0]*self.num_servers
        arrivals   = [[0]*self.num_servers for _ in range(self.num_flows)]
        departures = [[0]*self.num_servers for _ in range(self.num_flows)]
        bursts     = [[0]*self.num_servers for _ in range(self.num_flows)]

        # for all server j
        for server_idx, server in enumerate(self.servers):
            # Only compute server with flow passes through, otherwise the delay is unbounded
            if server_idx in self.server_no_flow:
                continue

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
            # Only compute server with flow passes through, otherwise the delay is unbounded
            if server_idx in self.server_no_flow:
                continue

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
            # Only compute server with flow passes through, otherwise the delay is unbounded
            if server_idx in self.server_no_flow:
                continue

            for succ in self.__get_successor(server_id):
                flows_prev = set(self.__get_flows(server_id, indices=True))
                flows_next = set(self.__get_flows(succ, indices=True))
                mutual_flows = list(flows_prev.intersection(flows_next))
                # select flows only when the path "server_id -> succ" is in the flow
                seq_flows = []
                for fl_idx in mutual_flows:
                    if self.flows[fl_idx]["path"].index(server_id)+1 == self.flows[fl_idx]["path"].index(succ):
                        seq_flows.append(fl_idx)

                tfa_pp_prog += pulp.lpSum(arrivals[fl][succ] for fl in seq_flows) <= server["max_packet_length"] + server["capacity"]*in_time[succ]

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
            return np.argwhere(self.adjacency_mat[server])[:,0].tolist()


    def assert_arrival_curve(self, arrival_curve:dict, flow_name:str) -> None:
        '''
        assert the properties of an arrival curve
        '''
        # Take min of the curves
        # bursts should be increasing / rates should be decreasing
        bursts = np.array(arrival_curve["bursts"])
        rates  = np.array(arrival_curve["rates"])

        # rearrange based on bursts in increasing order
        bur_order = np.argsort(bursts)
        bursts = bursts[bur_order]
        rates = rates[bur_order]

        # Check the curve is concave
        valid_curve_points = np.ones_like(bursts, dtype=bool)
        prev_burst = 0
        prev_rate  = np.inf
        for i in range(len(bursts)):
            curr_burst = bursts[i]
            curr_rate  = rates[i]

            # we sort the curves by burst in increasing order,
            # so we won't have smaller burst value than the previous one.
            # Thus we consider 2 cases: equal and greater

            # burst is equal, choose the smaller rate
            if curr_burst == prev_burst:
                if curr_rate > prev_rate:
                    valid_curve_points[i-1] = False
                else:
                    valid_curve_points[i] = False
                    continue    # don't need to update previous value

            # burst is larger, but rate is larger -> ignore
            elif curr_rate >= prev_rate:
                valid_curve_points[i] = False
                continue    # don't need to update previous value

            # if curr_burst < prev_burst or curr_rate > prev_rate:
            #     warnings.warn(f"Arrival curve of flow \"{flow_name}\" doesn't satisfy concavity, this may cause the problem to be unsolvable")
            
            prev_burst = curr_burst
            prev_rate  = curr_rate

        # Update arrival curve
        arrival_curve["bursts"] = bursts[valid_curve_points]
        arrival_curve["rates"]  = rates[valid_curve_points]


    def __set_arrcur_times(self, arrival_curve:dict) -> list:
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

        return turn_points


    def assert_service_curve(self, service_curve:dict, server_name:str) -> None:
        '''
        assert the properties of a service curve
        '''
        # Sort the curves
        # latencies should be increasing / rates should be increasing
        latencies = np.array(service_curve["latencies"])
        rates  = np.array(service_curve["rates"])

        # rearrange based on latencies, increasing order
        bur_order = np.argsort(latencies)
        latencies = latencies[bur_order]
        rates = rates[bur_order]

        # Check the curve is convex and take max of rate-latency curves
        valid_curve_points = np.ones_like(latencies, dtype=bool)
        prev_latency = 0
        prev_rate  = 0
        for i in range(len(latencies)):
            curr_latency = latencies[i]
            curr_rate    = rates[i]

            # we sort the curves by latencies in increasing order,
            # so we won't have smaller latencies value than the previous one.
            # Thus we consider 2 cases: equal and greater

            # latency is less, choose the larger rate
            if curr_latency == prev_latency:
                if curr_rate > prev_rate:
                    valid_curve_points[i-1] = False
                else:
                    valid_curve_points[i] = False
                    continue    # don't need to update previous value
            # latency is larger, but rate is less -> ignore
            elif curr_rate <= prev_rate:
                valid_curve_points[i] = False
                continue    # don't need to update previous value

            # if curr_latency <= prev_latency or curr_rate <= prev_rate:
            #     warnings.warn(f"Service curve of server \"{server_name}\" doesn't satisfy convexity, this may cause the problem to be unsolvable")
            prev_latency = curr_latency
            prev_rate    = curr_rate

        # Update arrival curve
        service_curve["latencies"] = latencies[valid_curve_points]
        service_curve["rates"]  = rates[valid_curve_points]

    
    def __set_sercur_times(self, service_curve:dict) -> list:
        '''
        Add an extra list "times" in the curve that indicates the time snaps where the rate changes
        '''
        assert len(service_curve["latencies"]) == len(service_curve["rates"])
        turn_points = [0]*(len(service_curve["rates"])-1)

        for t in range(len(turn_points)):
            turn_points[t] = (service_curve["rates"][t+1]*service_curve["latencies"][t+1] - service_curve["rates"][t]*service_curve["latencies"][t]) / (service_curve["rates"][t+1] - service_curve["rates"][t])

        service_curve["times"] = turn_points

        return turn_points