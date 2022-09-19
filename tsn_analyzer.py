import numpy as np
import pulp

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


    def __init__(self) -> None:
        # The adjacency matrix for the network topology
        self.adjacency_mat = None
        self.num_servers = 0

        # The flows which pass through the network
        self.flows = []
        self.num_flows = 0

        # Arrival curves at the source of each flow, as a token-bucket model
        self.arrival_curves = np.empty((0,2))

        # Service curves at each server, as a rate-latency model
        self.service_curves = np.empty((0,2))

        # Shapers as token-bucket models
        self.shapers = np.empty((0,2))

    
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


    def add_flows(self, flows:list, burst:Union[list,float], rate:Union[list,float]) -> None:
        '''
        Add new flows to the existing flows, as token-bucket model

        Params
        The input "flows" can be 1D list to represent 1 new flow, or a 2D list for multiple new flows 
        '''

        assert len(flows) > 0
        
        # Check dimensionality: 1D
        if type(flows[0]) is int:
            self.flows.append(flows.copy())
            self.num_flows += 1

            self.arrival_curves = np.r_[self.arrival_curves, [[burst, rate]]]

        # 2D: list of lists
        elif type(flows[0]) is list:
            assert len(flows) == len(burst)
            assert len(flows) == len(rate)

            for idx, fl in enumerate(flows):
                assert len(fl) > 0
                assert type(fl[0]) is int

                self.flows.append(fl.copy())
                self.num_flows += 1

                self.arrival_curves = np.r_[self.arrival_curves, [[burst[idx], rate[idx]]]]


    def set_arrival(self, flow_idx:int, burst:float, rate:float) -> None:
        '''
        Set the arrival curve for a specific flow as a token-bucket model

        Params:
        flow_idx: the index of the flow
        burst: the burst constraint
        rate: the arrival rate constraint
        '''
        assert flow_idx < self.num_flows

        self.arrival_curves[flow_idx, :] = np.array([burst, rate])


    def set_service(self, server_idx:int, rate:float, latency:float) -> None:
        '''
        Set the service curve for a specific server as a rate-latency model

        Params:
        server_idx: the index of the server
        rate: the service rate constraint
        latency: the latency constraint
        '''
        assert server_idx < self.num_servers

        # If dimension doesn't match, extend to the right dimension
        if self.service_curves.shape[0] != self.num_servers:
            new_service = np.empty((self.num_servers, 2))
            new_service[:self.service_curves.shape[0], :] = self.service_curves
            self.service_curves = new_service

        # Assign the service curve
        self.service_curves[server_idx, :] = np.array([rate, latency])

    
    def set_service_all(self, rates:Union[list,np.ndarray], latencies:Union[list,np.ndarray]) -> None:
        '''
        Set all the service curves together.
        The dimension of rates/latency must has length equals to the number of servers
        '''
        assert self.num_servers == len(rates)
        assert self.num_servers == len(latencies)

        self.service_curves = np.empty((self.num_servers, 2))
        self.service_curves[:, 0] = np.array(rates)
        self.service_curves[:, 1] = np.array(latencies)


    def set_service(self, server_idx:int, pkt_leng:float, capacity:float) -> None:
        '''
        Set the service curve for a specific server as a pkt_leng-capacity model

        Params:
        server_idx: the index of the server
        pkt_leng: the packet length constraint
        capacity: the capacity constraint
        '''
        assert server_idx < self.num_servers

        # If dimension doesn't match, extend to the right dimension
        if self.shapers.shape[0] != self.num_servers:
            new_shapers = np.empty((self.num_servers, 2))
            new_shapers[:self.shapers.shape[0], :] = self.shapers
            self.shapers = new_shapers

        # Assign the service curve
        self.shapers[server_idx, :] = np.array([pkt_leng, capacity])

    def set_shaper_all(self, pkt_leng:Union[list,np.ndarray], capacity:Union[list,np.ndarray]) -> None:
        '''
        Set all the shapers together.
        The dimension of packet_length/capacity must has length equals to the number of servers
        '''
        assert self.num_servers == len(pkt_leng)
        assert self.num_servers == len(capacity)

        self.shapers = np.empty((self.num_servers, 2))
        self.shapers[:, 0] = np.array(pkt_leng)
        self.shapers[:, 1] = np.array(capacity)


    def solve_tfa(self) -> list:
        '''
        Solve the TFA problem given that the network is defined properly

        Returns:
        delays: array of delay guarantees at each server
        '''
        # ensure the problem is properly defined
        assert self.adjacency_mat is not None
        assert len(self.arrival_curves) == self.num_flows
        assert len(self.service_curves) == self.num_servers

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
        for server in range(self.num_servers):
            # Time constraints
            s_var = var_set_name('s', server)
            t_var = var_set_name('t', server)
            in_time[server]  = pulp.LpVariable(s_var, 0)
            out_time[server] = pulp.LpVariable(t_var)
            
            tfa_prog += in_time[server] <= out_time[server]    # add constraint that s <= t

            # Arrival constraints
            for fl in self.__get_flows(server):
                As_var = var_set_name('As', fl, server)
                x_var  = var_set_name('x' , fl, server)
                Dt_var = var_set_name('Dt', fl, server)
                arrivals[fl][server]   = pulp.LpVariable(As_var)
                bursts[fl][server]     = pulp.LpVariable(x_var)
                departures[fl][server] = pulp.LpVariable(Dt_var)

                tfa_prog += arrivals[fl][server] <= bursts[fl][server] + self.arrival_curves[fl][1]*in_time[server]

            # Service constraints
            tfa_prog += pulp.lpSum([departures[fl][server] for fl in self.__get_flows(server)]) \
                        >= self.service_curves[server][0]*out_time[server] - self.service_curves[server][0]*self.service_curves[server][1]
            tfa_prog += pulp.lpSum([departures[fl][server] for fl in self.__get_flows(server)]) >= 0

            # FIFO constraints
            for fl in self.__get_flows(server):
                tfa_prog += arrivals[fl][server] == departures[fl][server]

            # delays
            d_var = var_set_name('d', server)
            delays[server] = pulp.LpVariable(d_var)

            tfa_prog += delays[server] <= out_time[server] - in_time[server]

        # Constraints on burst variables (x)
        # Burst propagation
        for server in range(self.num_servers):
            for fl in self.__get_flows(server):
                for succ in self.__get_successor(server):
                    tfa_prog += bursts[fl][succ] <= bursts[fl][server] + self.arrival_curves[fl][1]*delays[server]

        for flow_idx, flow in enumerate(self.flows):
            tfa_prog += bursts[flow_idx][flow[0]] <= self.arrival_curves[fl][0]

        # Set objective function
        tfa_prog += pulp.lpSum(delays)


        ## Solve the problem
        tfa_prog.solve(pulp.PULP_CBC_CMD(msg=False))
        optimal_delay = []
        for d in delays:
            optimal_delay.append(pulp.value(d))

        return optimal_delay


    def solve_tfa_pp(self) -> list:
        '''
        Solve the TFA++ problem given that the network is defined properly

        Returns:
        delays: array of delay guarantees at each server
        '''
        # ensure the problem is properly defined
        assert self.adjacency_mat is not None
        assert len(self.arrival_curves) == self.num_flows
        assert len(self.service_curves) == self.num_servers
        assert len(self.shapers) == self.num_servers

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
        for server in range(self.num_servers):
            # Time constraints
            s_var = var_set_name('s', server)
            t_var = var_set_name('t', server)
            in_time[server]  = pulp.LpVariable(s_var, 0)
            out_time[server] = pulp.LpVariable(t_var)
            
            tfa_pp_prog += in_time[server] <= out_time[server]    # add constraint that s <= t

            # Arrival constraints
            for fl in self.__get_flows(server):
                As_var = var_set_name('As', fl, server)
                x_var  = var_set_name('x' , fl, server)
                Dt_var = var_set_name('Dt', fl, server)
                arrivals[fl][server]   = pulp.LpVariable(As_var)
                bursts[fl][server]     = pulp.LpVariable(x_var)
                departures[fl][server] = pulp.LpVariable(Dt_var)

                tfa_pp_prog += arrivals[fl][server] <= bursts[fl][server] + self.arrival_curves[fl][1]*in_time[server]

            # Service constraints
            tfa_pp_prog += pulp.lpSum([departures[fl][server] for fl in self.__get_flows(server)]) \
                        >= self.service_curves[server][0]*out_time[server] - self.service_curves[server][0]*self.service_curves[server][1]
            tfa_pp_prog += pulp.lpSum([departures[fl][server] for fl in self.__get_flows(server)]) >= 0

            # FIFO constraints
            for fl in self.__get_flows(server):
                tfa_pp_prog += arrivals[fl][server] == departures[fl][server]

            # delays
            d_var = var_set_name('d', server)
            delays[server] = pulp.LpVariable(d_var)

            tfa_pp_prog += delays[server] <= out_time[server] - in_time[server]

        # Constraints on burst variables (x)
        # Burst propagation
        for server in range(self.num_servers):
            for fl in self.__get_flows(server):
                for succ in self.__get_successor(server):
                    tfa_pp_prog += bursts[fl][succ] <= bursts[fl][server] + self.arrival_curves[fl][1]*delays[server]

        for flow_idx, flow in enumerate(self.flows):
            tfa_pp_prog += bursts[flow_idx][flow[0]] <= self.arrival_curves[fl][0]

        # Shaper constraints
        # Adding shaping constraint
        for server in range(self.num_servers):
            for succ in self.__get_successor(server):
                flows_prev = set(self.__get_flows(server))
                flows_next = set(self.__get_flows(succ))
                mutual_flows = list(flows_prev.intersection(flows_next))
                tfa_pp_prog += pulp.lpSum(arrivals[fl][succ] for fl in mutual_flows) <= self.shapers[server, 0] + self.shapers[server, 1]*in_time[succ]

        # Set objective function
        tfa_pp_prog += pulp.lpSum(delays)


        ## Solve the problem
        tfa_pp_prog.solve(pulp.PULP_CBC_CMD(msg=False))
        optimal_delay = []
        for d in delays:
            optimal_delay.append(pulp.value(d))

        return optimal_delay


    def __get_flows(self, server: int) -> list:
        '''
        Given a server j, find the indices of flow Fl(j) that passes server j
        the answer is returned in a list
        '''
        assert len(self.flows) == self.num_flows

        idx = 0
        involved_flows = []
        for fl in self.flows:
            if server in fl:
                involved_flows.append(idx)
            idx += 1

        return involved_flows

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

