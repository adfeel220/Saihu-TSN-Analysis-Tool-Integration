
import xml.etree.ElementTree
import warnings
import copy
import numpy as np
import networkx as nx
import json

keysInWopanetXML = {
    "network": "network",
    "network_tech": "technology",
    "network_name": "name",
    "end_system": "station",
    "switch": "switch",
    "phy_node_name": "name",
    "link": "link",
    "link_from": "from",
    "link_from_port": "fromPort",
    "link_to": "to",
    "link_to_port": "toPort",
    "link_name": "name",
    "flow": "flow",
    "flow_path": "target",
    "flow_path_step": "path",
    "flow_path_step_name": "node"
}


def warning_override(message, category = UserWarning, filename = '', lineno = -1, file=None, line=None):
    '''
    To override warnings.showwarning for simpler warning display
    '''
    print("Warning:", message, category)
warnings.showwarning = warning_override


class PhysicalNet:
    '''
    Defines a physical network 
    '''

    network  : dict
    nodes    : dict     # stations or switches
    flows    : dict
    links    : dict     # key=from_which_physical_node, value=list of {"dest": to_which_physical_node, "output_port": from_which_port_of_source}

    def __init__(self, root:xml.etree.ElementTree=None):
        self.network = dict()
        self.nodes = dict()
        self.flows = dict()
        self.links = dict()

        if root is not None:
            self.read(root)

        
    def read(self, root:xml.etree.ElementTree):
        '''
        Read from WOPANet format XML file
        '''
        self.parse_network(root)
        self.parse_topology(root)
        self.parse_flows(root)


    def parse_network(self, root:xml.etree.ElementTree)->None:
        '''
        Parse information in the "network" element
        '''
        net_elems = root.findall(keysInWopanetXML["network"])
        if(len(net_elems) != 1):
            raise xml.etree.ElementTree.ParseError("Too many network items in XML")
        net_attribs = dict(net_elems[0].attrib)

        # Make sure at least has "name" attribute
        technologies = net_attribs.pop(keysInWopanetXML["network_tech"], "FIFO")
        self.network = copy.deepcopy(net_attribs)
        self.network["technology"] = technologies.split("+")
        self.network["name"] = net_attribs.pop(keysInWopanetXML["network_name"], "Network")


    def parse_topology(self, root:xml.etree.ElementTree)->None:
        '''
        Parse information for "station" and "switches"
        '''
        ## Nodes
        stations = root.findall(keysInWopanetXML["end_system"])
        for st in stations:
            try:
                name = st.attrib.pop(keysInWopanetXML["phy_node_name"])
            except KeyError as e:
                raise xml.etree.ElementTree.ParseError("A station has no name") from e

            if name in self.nodes:
               warnings.warn(f"Station named \"{name}\" is defined multiple times, only the first definition is used.")
               continue

            self.nodes[name] = {
                "type": keysInWopanetXML["end_system"],
                "used_output_ports": list(),
                **st.attrib
            }
        
        switches = root.findall(keysInWopanetXML["switch"])
        for st in switches:
            try:
                name = st.attrib.pop(keysInWopanetXML["phy_node_name"])
            except KeyError as e:
                raise xml.etree.ElementTree.ParseError("A switch has no name") from e

            if name in self.nodes:
               warnings.warn(f"Switch named \"{name}\" is defined multiple times, only the first definition is used.")
               continue

            self.nodes[name] = {
                "type": keysInWopanetXML["switch"],
                "used_output_ports": list(),
                **st.attrib
            }
        
        ## Links
        links = root.findall(keysInWopanetXML["link"])
        for lk in links:
            try:
                from_node = lk.attrib.pop(keysInWopanetXML["link_from"])
                to_node   = lk.attrib.pop(keysInWopanetXML["link_to"])
            except KeyError as e:
                raise xml.etree.ElementTree.ParseError("Link needs to have \"%s\" and \"%s\".".format(keysInWopanetXML["link_from"], keysInWopanetXML["link_to"])) from e

            from_port = lk.attrib.pop(keysInWopanetXML["link_from_port"], "0")

            if from_port not in self.nodes[from_node]["used_output_ports"]:
                self.nodes[from_node]["used_output_ports"].append(from_port)

            link_info = {
                "dest": to_node,
                "output_port": from_port
            }
            if from_node not in self.links:
                self.links[from_node] = [link_info]
            else:
                if link_info in self.links[from_node]:
                    raise xml.etree.ElementTree.ParseError(f"Link {from_node}->{to_node} using port {from_port} has multiple destination")
                self.links[from_node].append(link_info)


    def parse_flows(self, root:xml.etree.ElementTree)->None:
        '''
        Parse information for flows
        '''
        flows = root.findall(keysInWopanetXML["flow"])
        for flow_idx, fl in enumerate(flows):
            fl_name = fl.attrib.pop("name", f"fl{flow_idx}")
            try:
                source = fl.attrib.pop("source")
            except KeyError as e:
                raise xml.etree.ElementTree.ParseError(f"Flow \"{fl_name}\" needs to have a source") from e

            fl_attrib = copy.deepcopy(fl.attrib)

            for path_idx, fl_path in enumerate(fl.findall(keysInWopanetXML["flow_path"])):
                path_name = fl_path.attrib.pop("name", f"p{path_idx}")
                path_attrib = copy.deepcopy(fl_path.attrib)
                
                # fl_name = f"{fl_name}_{path_name}"
                if fl_name in self.flows:
                    continue

                self.flows[fl_name] = dict()
                self.flows[fl_name]["path"] = list()
                self.flows[fl_name]["attrib"] = dict(**fl_attrib, **path_attrib)
                prev_node = source
                for step in fl_path.findall(keysInWopanetXML["flow_path_step"]):
                    try:
                        dest = step.attrib.pop(keysInWopanetXML["flow_path_step_name"])
                    except KeyError as e:
                        raise AttributeError("No attribute \"%s\" in flow %s, path %s".format(keysInWopanetXML["flow_path_step_name"], fl_name, path_name)) from e

                    path_step = {"node": prev_node, "port": self.__get_link_port(prev_node, dest)}
                    self.flows[fl_name]["path"].append(path_step)
                    
                    prev_node = dest


    def get_output_ports(self, ignore_dummy:bool=False)->list:
        '''
        Return a list of output port dict containing name "[physical node name]_[port]" and service curve information

        ignore_dummy: true if we want to ignore nodes where no services defined on them
        '''
        port_list = list()
        for node_name, content in self.nodes.items():
            if "service-rate" not in content and ignore_dummy:
                continue

            output_ports = content.pop("used_output_ports")
            # Special case: when no output port used (no flow passes through node)
            if len(output_ports) == 0:
                port_list.append({"name": node_name, "physical_node":node_name, "port":None, **content})
                continue

            for port in output_ports:
                op_name = f"{node_name}-{port}"
                port_list.append({"name": op_name, "physical_node":node_name, "port":port, **content})

        return port_list
    


    def __get_link_port(self, src:str, dest:str)->str:
        '''
        Get the output port used from "src" to "dest"
        '''
        try:
            for lk in self.links[src]:
                if lk["dest"] == dest:
                    return lk["output_port"]

        except KeyError as ke:
            raise xml.etree.ElementTree.ParseError(f"Unable to resolve port from {src}->{dest}, no links coming out of {src}")

        return None



class OutputPortNet:

    network_info : dict
    topology: np.ndarray
    servers : list
    flows   : list

    def __init__(self, ifile:str=None, network_def:dict=None):
        self.network_info  = dict() # general network information
        self.adjacency_mat = None   # adjacency matrix
        self.servers = list()
        self.flows = list()

        if network_def is not None:
            self.parse(network_def)
            return
        if ifile is not None:
            self.read(ifile)

    def read(self, ifpath:str)->None:
        '''
        Read from a input file in json format
        '''
        ## Read from file
        with open(ifpath, 'r') as ifile:
            network_def = json.load(ifile)

        self.parse(network_def)

    def parse(self, network_def:dict)->None:
        '''
        Read from a dictionary loaded from json

        0. network information:
         - a dict stores general network information
        
        1. adjacency matrix:
         - a 2D array representing a directed graph
        
        2. flows:
         - a list of objects representing each flow.
           a flow is defined by
           - path: a list of non-repeating indicing of servers
           - packet_length: max packet size arrives at this flow
           - arrival_curve: an object defines a concave curve and contains
             - bursts: a list indicates bursts of curves
             - rates: a decreasing list of arrival rates
        
        3. servers:
         - a list of objects representing each server.
           a server is defined by
           - capacity: the output capacity of server (shaper constraint)
           - service_curve: an object defines a convex curve and contains
             - latencies: a list indicates latencies of curves
             - rates: a increasing list of service rates
        '''
        ## Load network information
        if "network" not in network_def:
            default_net_info = {
                "name": "NONAME",
                "technology": ["FIFO"]
            }
            network_def["network"] = default_net_info
        self.network_info = network_def["network"]

        ## Load adjacency matrix
        self.adjacency_mat = np.array(network_def['adjacency_matrix'], dtype=np.int8)
        num_servers = self.adjacency_mat.shape[0]
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
                if s >= num_servers or s < 0:
                    raise SyntaxError(f"Path definition in flow {id} is incorrect. Server ID should be 0-{num_servers-1}, get {s} instead.")
            # 3. Each adjacent servers along the path is connected by a link
            for si in range(len(path)-1):
                if self.adjacency_mat[path[si], path[si+1]] == 0:
                    raise ValueError(f"Path of flow {id} invalid. No link between server {path[si]} and {path[si+1]}")

            ## Check arrival curve syntax
            arrival_curve = fl["arrival_curve"]
            # assertion of arrival curve definition
            self.assert_curve(arrival_curve, id)

            ## Check packet length
            if fl["packet_length"] < 0:
                pkt_len = fl["packet_length"]
                raise ValueError(f"Packet length of flow {id} is negative ({pkt_len}), should at least >= 0.")

            self.flows.append(fl.copy())

        ## Load servers
        self.servers = []
        for ser_id, ser in enumerate(network_def["servers"]):
            ## Check service curve
            # assertion of arrival curve definition
            self.assert_curve(ser["service_curve"], ser_id)

            ## Check server capacity
            if ser["capacity"] <= 0:
                raise ValueError(f"Capacity of server {ser_id} is non-positive, should at least >0.")

            self.servers.append(ser.copy())
            
        if len(self.servers) != num_servers:
            raise ValueError(f"Network adjacency matrix doesn't match with server definitions. Network is defined with {num_servers} nodes but {len(self.servers)} servers defined.")



    def assert_curve(self, curve:dict, curve_id:int) -> None:
        '''
        assert the properties of acurve
        '''
        if "latencies" in curve:
            # the curve is a service curve, extract latencies
            curve_type = "service"
            lat_bur_len  = len(curve["latencies"])
        elif "bursts" in curve:
            # the curve is an arrival curve, extract bursts
            curve_type = "arrival"
            lat_bur_len  = len(curve["bursts"])
        else:
            raise RuntimeError(f"Not a valid curve definition, neither \"latencies\" nor \"bursts\" are in the curve definition")

        rate_len = len(curve["rates"])

        # Ensure there's at least 1 line defined
        if lat_bur_len < 1:
            raise SyntaxError(f"No latency defined in the service curve of server {curve_id}")
        if rate_len < 1:
            raise SyntaxError(f"No service rate defined in the service curve of server {curve_id}")

        # Check number of segments of the service curve coherent in latencies/rates
        min_len = min(lat_bur_len, rate_len)
        if lat_bur_len != rate_len:
            warnings.warn(f"Length of latencies/bursts and rates are different in curve {curve_id}. {lat_bur_len} numbers in latencies/bursts' definition and {rate_len} in rates'. Consider the shorter one ({min_len}) instead", SyntaxWarning)
            if curve_type == "service":
                curve["latencies"] = curve["latencies"][:min_len]
            elif curve_type == "arrival":
                curve["bursts"] = curve["bursts"][:min_len]
            curve["rates"] = curve["rates"][:min_len]


    
    def get_gif(self)->nx.DiGraph:
        '''
        Return a Graph induced by Flows
        '''
        G = nx.DiGraph()
        for fl in self.flows:
            prev_step = fl["path"][0]
            for step in fl["path"][1:]:
                G.add_edge(prev_step, step)
                prev_step = step

        return G

    def is_cyclic(self)->bool:
        '''
        Tell if the current network is cyclic
        '''
        return len(list(nx.simple_cycles(self.get_gif()))) > 0

    def get_utility(self) -> dict:
        '''
        Compute the utility map of network utility (load).
        Load of each server i is computed as (sum of arrival rates at server i) / (service rate at server i)

        Returns:
        ---------
        utility : dictionary of key=server-names ; value=utility
        '''
        # aggregate arrival rate at each server, key=server_name, value=rate
        agg_arr_rate = np.zeros(len(self.servers))

        for fl in self.flows:
            for ser_id in fl["path"]:
                agg_arr_rate[ser_id] += fl["arrival_curve"]["rates"][0]

        ser_rates = np.zeros(len(self.servers))
        ser_names = [None]*len(self.servers)
        for idx, serv in enumerate(self.servers):
            ser_rates[idx] = serv["service_curve"]["rates"][0]
            ser_names[idx] = serv.get("name", f"s_{idx}")

        utility = dict(zip(ser_names, agg_arr_rate/ser_rates))
        
        return utility
