
import xml.etree.ElementTree
import warnings
import copy
import numpy as np
import json
from typing import Union
from copy import deepcopy

import networkx as nx
from netscript.unit_util import *

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

# The default unit used when it's written as a pure string number
Wopanet_default_units = {
    "time": "ms",
    "data": "B",
    "rate": "bps"
}

network_param = {
    "packetizer": "PK",
    "multiplexing": {"FIFO", "ARBITRARY"},
    "analysis_option": ["IS", "CEIL", "MOH", "TDMI"]
}

def warning_override(message, category = UserWarning, filename = '', lineno = -1, file=None, line=None):
    '''
    To override warnings.showwarning for simpler warning display
    '''
    print("Warning:", message, category)
warnings.showwarning = warning_override


def try_raise(task_str:str, data, func, *fargs, **fkargs):
    '''
    Try to execution func with arguments "fargs" and "fkargs" when the function possibly raise an error
    and add another layer to show proper information

    task_str : [str] to describe the task we are trying
    data : [Any printable] the data we are to process now

    func   : the function to execute
    fargs  : sequential arguments for func
    fkargs : keyword arguments for func
    '''
    try:
        return func(*fargs, **fkargs)
    except Exception as e:
        raise Exception("Error when trying on {task} with data {d}".format(task=task_str, d=data)) from e


class PhysicalNet:
    '''
    Defines a physical network 
    '''

    network  : dict
    nodes    : dict     # stations or switches
    flows    : dict
    links    : dict     # key=from_which_physical_node, value=list of {"dest": to_which_physical_node, "output_port": from_which_port_of_source, "dest_port": to_which_port_of_destination}

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

            from_port = lk.attrib.pop(keysInWopanetXML["link_from_port"], "o0")
            to_port = lk.attrib.pop(keysInWopanetXML["link_to_port"], "i0")

            if from_port not in self.nodes[from_node]["used_output_ports"]:
                self.nodes[from_node]["used_output_ports"].append(from_port)

            link_info = {
                "dest": to_node,
                "output_port": from_port,
                "dest_port": to_port,
                **lk.attrib
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
        Return a list of output port dict containing name "[physical node name]-[port]" and service curve information

        ignore_dummy: true if we want to ignore nodes where no services defined on them
        '''
        port_list = list()
        for node_name, content in self.nodes.items():
            if "service-rate" not in content and ignore_dummy:
                continue

            node_info = deepcopy(content)
            output_ports = node_info.pop("used_output_ports")
            # Special case: when no output port used (no flow passes through node)
            if len(output_ports) == 0:
                port_list.append({"name": node_name, "physical_node":node_name, "port":None, **node_info})
                continue

            for pid, port in enumerate(output_ports):
                op_name = f"{node_name}-{port}"
                # Check if there's link overwrittten parameters
                if "service-latency" in self.links[node_name][pid]:
                    node_info["service-latency"] = self.links[node_name][pid]["service-latency"]
                if "service-rate" in self.links[node_name][pid]:
                    node_info["service-rate"] = self.links[node_name][pid]["service-rate"]
                if "transmission-capacity" in self.links[node_name][pid]:
                    node_info["transmission-capacity"] = self.links[node_name][pid]["transmission-capacity"]

                port_list.append({"name": op_name, "physical_node":node_name, "port":port, **node_info})

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
    '''
    A wrapper to describe an output-port network. 

    Attributes:
    -----------
    network_info  : [dict] contains general network information
    adjacency_mat : [np.ndarray] the adjacency matrix w.r.t. the "id"s defined in servers
    servers       : [list] list of dictionaries of servers
    flows         : [list] list of dictionaries of flows
    units         : [dict] of attributes "time", "data" and "rate" to indicate the units used in this network
    '''

    network_info : dict
    adjacency_mat: np.ndarray
    servers : list
    flows   : list

    units: dict

    # The mandatory entries at each level and its type
    _mandatory_entries : dict = {
        "network": {
            "name": str
        },
        "flows": {
            "name": str,
            "path": list,
            "arrival_curve": {
                "bursts": list,
                "rates": list
            }
        },
        "servers": {
            "name": str,
            "service_curve": {
                "latencies": list,
                "rates": list
            }
        }
    }

    def __init__(self, ifile:str=None, network_def:dict=None):
        self.network_info  = dict() # general network information
        self.adjacency_mat = None   # adjacency matrix
        self.servers = list()
        self.flows = list()
        self.units = {
            'time': None,
            'data': None,
            'rate': None
        }

        if network_def is not None:
            self.parse(network_def)
            return
        if ifile is not None:
            self.read(ifile)

    def __str__(self) -> str:
        outstr = "Outport-port Network {netname}\n====================\n".format(netname=self.network_info["name"])
        outstr += "Network Information:\n"
        outstr += str(self.network_info)+"\n"
        outstr += "Adjacency Matrix:\n"
        outstr += str(self.adjacency_mat)+"\n"
        outstr += "Servers:\n"
        outstr += '\n'.join([str(s) for s in self.servers]) + "\n"
        outstr += "Flows:\n"
        outstr += '\n'.join([str(f) for f in self.flows]) + "\n"
        outstr += "-------------------\n"
        return outstr

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

        1. network information:
          - a dict stores general network information
          - Or default values of parameters

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
        self._assert_mandatory_fields(network_def)
        ## Load network information
        # A network information must at least have "name"
        self.network_info = network_def["network"]
        self.units = {
            "time": network_def["network"].get("time_unit", self.units["time"]),
            "data": network_def["network"].get("data_unit", self.units["data"]),
            "rate": network_def["network"].get("rate_unit", self.units["rate"])
        }

        # Get server name mapping
        server_name_index_table = dict(zip([s["name"] for s in network_def["servers"]], range(len(network_def["servers"]))))
        # Initialize adjacency matrix
        self.adjacency_mat = np.zeros((len(server_name_index_table), len(server_name_index_table)), dtype=np.int8)

        ## Load flows
        self.flows = []
        for fid, fl in enumerate(network_def['flows']):
            flow_name = fl["name"]

            fl["id"] = fid

            # path defined as a list of server names
            path_in_name = fl["path"]

            # path defined as a list of server indices, server index is the order defined in server list
            path_in_idx = [None]*len(path_in_name)
            for sid, sname in enumerate(path_in_name):
                if sname not in server_name_index_table:
                    raise RuntimeError(f"Server name \"{sname}\" written in flow \"{flow_name}\" is not defined")
                path_in_idx[sid] = server_name_index_table[sname]

            fl["path"] = path_in_idx

            ## Check if it's a valid path
            # 1. no recurring server along the path
            if len(path_in_idx) != len(set(path_in_idx)):
                raise RuntimeError(f"Skip flow {flow_name} due to recurring server in its path: {path_in_name}")
            # 2. non-empty path
            if len(path_in_idx) <= 0:
                warnings.warn(f"Skip flow {flow_name} because its path is empty, you may delete this flow")
                continue

            # Construct adjacency matrix
            for sid in range(len(path_in_idx)-1):
                self.adjacency_mat[path_in_idx[sid], path_in_idx[sid+1]] = 1

            ## Check arrival curve syntax
            arrival_curve = fl["arrival_curve"]
            # Get local unit
            unit = {
                "time": fl.pop("time_unit", self.units["time"]),
                "data": fl.pop("data_unit", self.units["data"]),
                "rate": fl.pop("rate_unit", self.units["rate"])
            }
            # Convert arrival curve to the default unit
            arrival_curve["bursts"] = try_raise(f"Parsing flows.arrival_curve.bursts of \"{flow_name}\"", arrival_curve["bursts"] , self._convert_unit, arrival_curve["bursts"], unit["data"], "data")
            arrival_curve["rates"]  = try_raise(f"Parsing flows.arrival_curve.rates of \"{flow_name}\"" , arrival_curve["rates"]  , self._convert_unit, arrival_curve["rates"], unit["rate"], "rate")

            # Assert the curve properties
            self._assert_curve(arrival_curve, flow_name)

            fl["arrival_curve"] = arrival_curve

            ## Check packet length
            # maximum packet length:
            # it tries to find a local definition, if locally not defined, use the network default,
            # if network default is still not defined, use the maximum burst among all bursts
            default_max_pkt_len = network_def["network"].get("max_packet_length", max(arrival_curve["bursts"]))
            max_pkt_len = fl.get("max_packet_length", default_max_pkt_len)
            max_pkt_len = try_raise(f"Parsing flows.max_packet_length of \"{flow_name}\"", max_pkt_len, self._convert_unit, max_pkt_len, unit["data"], "data")
            if max_pkt_len < 0:
                raise ValueError(f"Maximum packet length of flow {flow_name} is negative ({max_pkt_len}), should at least >= 0.")
            fl["max_packet_length"] = max_pkt_len

            # minimum packet length:
            # it tries to find a local definition, if locally not defined, use the network default,
            # if network default is still not defined, use the minimum burst among all bursts
            default_min_pkt_len = network_def["network"].get("min_packet_length", min(arrival_curve["bursts"]))
            min_pkt_len = fl.get("min_packet_length", default_min_pkt_len)
            min_pkt_len = try_raise(f"Parsing flows.min_packet_length of \"{flow_name}\"", max_pkt_len, self._convert_unit, min_pkt_len, unit["data"], "data")
            if min_pkt_len < 0:
                raise ValueError(f"Minimum packet length of flow {flow_name} is negative ({min_pkt_len}), should at least >= 0.")
            fl["min_packet_length"] = min_pkt_len

            self.flows.append(fl)

        ## Load servers
        self.servers = []
        for ser in network_def["servers"]:

            ser_name = ser["name"]

            ser["id"] = server_name_index_table[ser_name]

            #################
            # Service curve #
            #################
            # Get local unit
            unit = {
                "time": ser.pop("time_unit", self.units["time"]),
                "data": ser.pop("data_unit", self.units["data"]),
                "rate": ser.pop("rate_unit", self.units["rate"])
            }
            
            # assertion of arrival curve definition
            service_curve = ser["service_curve"]

            # Convert service curve to the default unit
            service_curve["latencies"] = try_raise(f"Parsing servers.service_curve.latencies of \"{ser_name}\"", service_curve["latencies"], self._convert_unit, service_curve["latencies"], unit["time"], "time")
            service_curve["rates"] = try_raise(f"Parsing servers.service_curve.rates of \"{ser_name}\"", service_curve["rates"], self._convert_unit, service_curve["rates"], unit["rate"], "rate")
            
            # Assert the curve properties
            self._assert_curve(service_curve, ser_name)

            ser["service_curve"] = service_curve

            ############
            # Capacity #
            ############
            # Default capacity is the maximum service rate
            default_capacity = network_def["network"].get("capacity", max(service_curve["rates"]))
            capacity = ser.get("capacity", default_capacity)
            capacity = try_raise(f"Parsing servers.capacity of \"{ser_name}\"", capacity, self._convert_unit, capacity, unit["rate"], "rate")

            # check server capacity validity
            if capacity <= 0:
                raise ValueError(f"Capacity of server {ser_name} is non-positive, should at least >0.")

            ser["capacity"] = capacity

            self.servers.append(ser)
            
    
    def dump_json(self, ofile:str) -> None:
        '''
        Dump the file into a json
        '''
        out_dict = {
            "network": self.network_info,
            "adjacency_matrix": self.adjacency_mat.tolist(),
            "flows": self.flows,
            "servers": self.servers
        }
        with open(ofile, 'w') as f:
            json.dump(out_dict, f, indent=4)


    def _assert_mandatory_fields(self, data:dict, subfields:list=[]) -> None:
        '''
        Assert the fields of a loaded json data

        Inputs:
        ----------
        data: the data to be check
        subfields: a list of keywords to check, to check field defined in mandatory_entries["network"], the subfields is ["network"]
        '''
        # Access the field for check
        check_field = deepcopy(self._mandatory_entries)
        for f in subfields:
            check_field = check_field[f]

        # still have deeper fields to check
        if type(check_field) is dict:
            # Check all fields stored of the current layer
            for field, ftype in check_field.items():
                if field not in data:
                    raise AttributeError("No \"{missing}\" object is defined in \"{subfd}\" of data {dt}\n A \"{subfd}\" object in network description file must have attributes {must_have}"\
                                        .format(missing=field, subfd='.'.join(subfields), dt=data, must_have=list(check_field.keys())))
                # Explore deeper laters
                if type(ftype) is not type:
                    # if it's a list, we make sure all entries inside the list is good
                    if type(data[field]) is list:
                        for sf in data[field]:
                            try:
                                self._assert_mandatory_fields(sf, [*subfields, field])
                            except Exception as e:
                                raise AttributeError("Missing mandatory field in \"{fields}\" of data {dt} ".format(fields="->".join([*subfields, field]), dt=sf)) from e
                    else:
                        try:
                            self._assert_mandatory_fields(data[field], [*subfields, field])
                        except Exception as e:
                            raise AttributeError("Missing mandatory field in \"{fields}\" of data {dt} ".format(fields="->".join([*subfields, field]), dt=data[field])) from e
                            
                
    def _convert_unit(self, data:Union[float,Iterable], written_unit:str, unit_type:str):
        '''
        Convert the data written in another unit into default unit

        Inputs:
        ----------
        data : [float | Iterable] the data, or the iterable of data to be converted
        writte_unit : [str] the unit that the data is written in
        
        '''
        if unit_type.lower() == "time":
            parse_func = parse_num_unit_time
        elif unit_type.lower() == "data":
            parse_func = parse_num_unit_data
        elif unit_type.lower() == "rate":
            parse_func = parse_num_unit_rate
        else:
            raise SyntaxError(f"Unit type \"{unit_type}\" is not a valid input. Should be either \"time\"/\"data\"/\"rate\"")

        # pure number : use the locally defined unit
        if is_number(data):
            data_with_unit = "{num}{unit}".format(num=data, unit=written_unit)
            try:
                return parse_func(data_with_unit, self.units[unit_type.lower()])
            except ValueError as e:
                raise ValueError(f"Error trying to convert with unit \"{written_unit}\"") from e

        # already with unit : use the unit written in the string
        elif type(data) is str:
            try:
                return parse_func(data, self.units[unit_type.lower()])
            except ValueError as e:
                raise ValueError(f"Error trying to convert \"{data}\"") from e


        # should be an iterable
        else:
            output = []
            for d in data:
                # pure number : use the locally defined unit
                if is_number(d):
                    data_with_unit = "{num}{unit}".format(num=d, unit=written_unit)
                    try:
                        output.append(parse_func(data_with_unit, self.units[unit_type.lower()]))
                    except ValueError as e:
                        raise ValueError(f"Error trying to convert with unit \"{written_unit}\"") from e


                # already with unit : use the unit written in the string
                elif type(d) is str:
                    try:
                        output.append(parse_func(d, self.units[unit_type.lower()]))
                    except ValueError as e:
                        raise ValueError(f"Error trying to convert \"{d}\"") from e

            return output



    def _assert_curve(self, curve:dict, name:int) -> None:
        '''
        assert the properties of a curve
        '''
        if "latencies" in curve:
            # the curve is a service curve, extract latencies
            curve_type = "service"
            attr_name = "latencies"
            attr_type = "server"
            lat_bur_len = len(curve["latencies"])
        elif "bursts" in curve:
            # the curve is an arrival curve, extract bursts
            curve_type = "arrival"
            attr_name = "bursts"
            attr_type = "flow"
            lat_bur_len = len(curve["bursts"])
        else:
            raise KeyError(f"Not a valid curve definition, neither \"latencies\" nor \"bursts\" are in the curve definition")

        rate_len = len(curve["rates"])

        # Ensure there's at least 1 line defined
        if lat_bur_len < 1:
            raise SyntaxError(f"No {attr_name} defined in the {curve_type} curve of {attr_type} \"{name}\"")
        if rate_len < 1:
            raise SyntaxError(f"No {curve_type} rate defined in the {curve_type} curve of {attr_type} \"{name}\"")

        # Check number of segments of the service curve coherent in latencies/rates
        min_len = min(lat_bur_len, rate_len)
        if lat_bur_len != rate_len:
            warnings.warn(f"Length of {attr_name} and rates are different in curve of \"{name}\". {lat_bur_len} numbers in {attr_name}' definition and {rate_len} in rates'. Consider the shorter one ({min_len}) instead")
            curve[attr_name] = curve[attr_name][:min_len]
            curve["rates"] = curve["rates"][:min_len]

        # Ensure the curve is written in-order and remove redundent curves
        # 'in-order' means for arrival curve, all token-buckets are written as 
        # increasing bursts and decreasing rates; for service curves, all rate-latency
        # curves are written as increasing latencies and increasing rates.

        # rearrange based on bursts in increasing order
        order = np.argsort(curve[attr_name])
        bur_lat = np.array(curve[attr_name])[order]
        rates = np.array(curve["rates"])[order]

        # Check the curve is concave
        valid_curve_points = np.ones_like(bur_lat, dtype=bool)
        prev_bur_lat = 0
        prev_rate  = np.inf if attr_type=="flow" else 0
        for i in range(len(bur_lat)):
            curr_bur_lat = bur_lat[i]
            curr_rate  = rates[i]

            # we sort the curves by burst/latency in increasing order,
            # so we won't have smaller burst/latency value than the previous one.
            # Thus we consider 2 cases: equal and greater

            # burst/latency is equal, 
            # choose the smaller rate for token-bucket
            # choose the larger rate for rate-latency
            if curr_bur_lat == prev_bur_lat:
                if attr_type == "flow":
                    if curr_rate < prev_rate:
                        valid_curve_points[i-1] = False
                    else:
                        valid_curve_points[i] = False
                        continue    # don't need to update previous value
                else: # attr_type == "server"
                    if curr_rate > prev_rate:
                        valid_curve_points[i-1] = False
                    else:
                        valid_curve_points[i] = False
                        continue    # don't need to update previous value

            # arrival curve: if burst is larger but rate is also larger -> ignore
            # service curve: if latency is larger but rate is also smaller -> ignore
            elif curr_rate>=prev_rate and attr_type=="flow" or curr_rate<=prev_rate and attr_type=="server":
                valid_curve_points[i] = False
                continue    # don't need to update previous value

            
            prev_bur_lat = curr_bur_lat
            prev_rate  = curr_rate

        # Update arrival curve
        curve[attr_name] = bur_lat[valid_curve_points].tolist()
        curve["rates"]   = rates[valid_curve_points].tolist()

    
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

if __name__ == "__main__":
    opnet = OutputPortNet(ifile="./demo_net.json")
    print(opnet)
    