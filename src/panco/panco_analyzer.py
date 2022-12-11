
import sys
import os.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import json
import warnings
import numpy as np

# Import panco PLP modules
from panco.descriptor.curves import TokenBucket, RateLatency
from panco.descriptor.flow import Flow
from panco.descriptor.server import Server
from panco.descriptor.network import Network

from panco.fifo.fifoLP import FifoLP
from panco.fifo.tfaLP import TfaLP
from panco.fifo.sfaLP import SfaLP

# set custom warning message
def warning_override(message, category = UserWarning, filename = '', lineno = -1, file=None, line=None):
    print("Warning:", message, category)
warnings.showwarning = warning_override


class panco_analyzer():
    '''
    This class serves 3 purposes:
    1. Parse the network definition file
    2. Run analysis based on user selection
    3. Return result
    '''

    network_info  : dict
    adjacency_mat : np.ndarray
    num_servers   : int
    num_flows     : int
    flows_info    : list
    servers_info  : list
    server_no_flow : list

    network : Network
    servers : list
    flows   : list
    server_names : list
    flows_names  : list

    _methods = {"TFA", "SFA", "PLP"}


    def __init__(self, filename:str=None) -> None:
        # Directly loaded information, may not all used in analysis
        self.network_info = None
        self.adjacency_mat = None
        self.num_flows = 0
        self.num_servers = 0
        self.flows_info = list()
        self.servers_info = list()
        self.server_no_flow = list()

        # Translated info for PLP tool
        self.network = None
        self.flows = list()
        self.flow_names = list()
        self.servers = list()
        self.server_names = list()

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

    
    def parse(self, network_def:dict)->None:
        '''
        Parse a network definition file
        '''
        ## Load general network information
        self.network_info = network_def["network"]

        ## Load adjacency matrix
        self.adjacency_mat = np.array(network_def['adjacency_matrix'], dtype=np.int8)
        self.num_servers   = self.adjacency_mat.shape[0]
        # Assert the input is a valid adjacency matrix
        if len(self.adjacency_mat.shape) != 2:
            raise SyntaxError(f"Adjacency matrix dimension incorrect. Expect 2 but get {len(self.adjacency_mat.shape)}")
        if self.adjacency_mat.shape[0] != self.adjacency_mat.shape[1]:
            raise SyntaxError(f"Adjacency matrix should be square, get dimension {self.adjacency_mat.shape} instead")

        ## Load flows
        self.flows_info = []
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
            # 3. Each adjacent servers along the path is connected by a link
            for si in range(len(path)-1):
                if self.adjacency_mat[path[si], path[si+1]] == 0:
                    raise ValueError(f"Path of flow {id} invalid. No link between server {path[si]} and {path[si+1]}")

            ## Check arrival curve syntax
            arrival_curve = fl["arrival_curve"]
            # assertion of arrival curve definition
            self.assert_arrival_curve(arrival_curve=arrival_curve, flow_id=id)

            ## Check packet length
            if fl["packet_length"] < 0:
                pkt_len = fl["packet_length"]
                raise ValueError(f"Packet length of flow {id} is negative ({pkt_len}), should at least >= 0.")

            self.flows_info.append(fl.copy())

        self.num_flows = len(self.flows_info)

        ## Load servers
        self.servers_info = []
        for ser_id, ser in enumerate(network_def["servers"]):

            ## Assign packet length according to flow paths
            pkt_len = [fl["packet_length"] for fl in self.__get_flows(ser_id)]    # packet lengths of the involved flows
            # Assign the maximum possible packet length that passes through the server
            if len(pkt_len) > 0:
                ser['packet_length'] = max(pkt_len)
            # it's possible that exists isolated server
            else:
                warnings.warn(f"No flow passes through server {ser_id}, you may remove it from the analysis", UserWarning)
                self.server_no_flow.append(ser_id)
                ser['packet_length'] = 0

            ## Check service curve
            # assertion of arrival curve definition
            self.assert_service_curve(ser["service_curve"], ser_id)

            ## Check server capacity
            if ser["capacity"] <= 0:
                raise ValueError(f"Capacity of server {ser_id} is non-positive, should at least >0.")

            self.servers_info.append(ser.copy())
            
        if len(self.servers_info) != self.num_servers:
            raise ValueError(f"Network adjacency matrix doesn't match with server definitions. Network is defined with {self.num_servers} nodes but {len(self.servers_info)} servers defined.")

        
    def is_loaded(self)->bool:
        '''
        Return whether the analyzer has network loaded in
        '''
        if self.network_info is None:
            return False
        if self.adjacency_mat is None:
            return False
        if self.num_flows==0 or self.num_flows==0:
            return False
        return True


    


    def build_network(self, use_shaper:bool=False)->None:
        '''
        Build a PLP network from currently stored network
        '''
        if not self.is_loaded():
            raise RuntimeError("Try to build a network without any network object loaded in the analyzer")

        self.servers = list()
        self.server_names = list()

        ## Servers with service curves
        for ser_id, ser in enumerate(self.servers_info):
            self.server_names.append(ser.get("name", f"sw_{ser_id}"))
            
            service_curves = list()
            shapers = list()
            latencies = ser["service_curve"]["latencies"]
            rates = ser["service_curve"]["rates"]
            for i in range(len(rates)):
                rl_curve = RateLatency(rate=rates[i], latency=latencies[i])
                service_curves.append(rl_curve)
            if use_shaper:
                tb_curve = TokenBucket(ser["packet_length"], ser["capacity"])
                shapers.append(tb_curve)

            # Append servers
            self.servers.append(Server(service_curves, shapers))

        self.flows = list()
        self.flow_names = list()
        ## Flows
        for fl_id, fl in enumerate(self.flows_info):
            self.flow_names.append(fl.get("name", f"fl_{fl_id}"))
            # Resolve path
            path = fl["path"]
            
            arrival_curves = list()
            bursts = fl["arrival_curve"]["bursts"]
            rates  = fl["arrival_curve"]["rates"]
            for i in range(len(rates)):
                tb_curve = TokenBucket(bursts[i], rates[i])
                arrival_curves.append(tb_curve)

            # append flow
            self.flows.append(Flow(arrival_curves, path))

        ## Create a network for analysis
        self.network = Network(self.servers, self.flows)
                

    def analyze(self, method:str="PLP", lp_file:str="fifo.lp", use_tfa:bool=True, use_sfa:bool=True, output_shaping:bool=True)->None:
        '''
        Analyse the stored network

        method: Allow methods are "TFA", "SFA", "PLP"
        lp_file: LP solver file directory
        use_tfa: use TFA result to improve PLP result, relevant only when using PLP or PLP++
        use_sfa: use SFA result to improve PLP result, relevant only when using PLP or PLP++
        '''
        # Build network for analysis
        if self.network is None:
            self.build_network(output_shaping)

        # Analyse result
        if method.upper() == "PLP":
            return self.analyze_fifo(lp_file, True, use_tfa, use_sfa)
        if method.upper() == "ELP":
            return self.analyze_fifo(lp_file, False, use_tfa, use_sfa)
        if method.upper() == "TFA":
            return self.analyze_tfa(lp_file)
        if method.upper() == "SFA":
            return self.analyze_sfa(lp_file)
            

    def analyze_fifo(self, lp_file:str="fifo.lp", polynomial:bool=True, use_tfa:bool=True, use_sfa:bool=True)->tuple:
        '''
        Analyse using PLP with a pre-built network
        '''
        if self.network is None:
            raise RuntimeError("An analysis called before a network is built")

        plp = FifoLP(self.network, polynomial=polynomial, tfa=use_tfa, sfa=use_sfa, filename=lp_file)
        delay_per_flow = plp.all_delays

        return delay_per_flow, None


    def analyze_tfa(self, lp_file:str="fifo.lp")->tuple:
        '''
        Analyse using TFA with a pre-built network
        '''
        if self.network is None:
            raise RuntimeError("An analysis called before a network is built")

        tfa = TfaLP(self.network, filename=lp_file)
        delay_per_flow = tfa.all_delays
        delay_per_server = tfa.delay_servers

        for sid in self.server_no_flow:
            delay_per_server[sid] = 0.0

        return delay_per_flow, delay_per_server

    
    def analyze_sfa(self, lp_file:str="fifo.lp")->tuple:
        '''
        Analyse using SFA with a pre-built network
        '''
        if self.network is None:
            raise RuntimeError("An analysis called before a network is built")

        sfa = SfaLP(self.network, filename=lp_file)
        delay_per_flow = sfa.all_delays

        return delay_per_flow, None

    
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
            warnings.warn(f"Length of latencies and services rates are different in server {server_id}. {lat_len} numbers in latencies' definition and {rate_len} in rates'. Consider the shorter one ({min_len}) instead", SyntaxWarning)
            service_curve["latencies"] = service_curve["latencies"][:min_len]
            service_curve["rates"]     = service_curve["rates"][:min_len]

        # Check the curve is convex
        prev_latency = 0
        prev_rate  = 0
        for i in range(min_len):
            curr_latency = service_curve["latencies"][i]
            curr_rate    = service_curve["rates"][i]
            if curr_latency <= prev_latency or curr_rate <= prev_rate:
                warnings.warn(f"Service curve of server {server_id} doesn't satisfy convexity, this may cause the problem to be unsolvable", Warning)
            
            prev_latency = curr_latency
            prev_rate  = curr_rate


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
            warnings.warn(f"Length of bursts and arrival rates are different in flow {flow_id}. {bursts_len} numbers in bursts' definition and {rates_len} in rates'. Consider the shorter one ({min_len}) instead", SyntaxWarning)
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


    def __get_flows(self, server: int) -> list:
        '''
        Given a server j, find the indices of flow Fl(j) that passes server j
        the answer is returned in a list
        '''
        assert len(self.flows_info) == self.num_flows

        output = []
        for fl in self.flows_info:
            if server in fl["path"]:
                output.append(fl)

        return output

