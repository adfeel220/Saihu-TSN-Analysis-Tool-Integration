
import xml.etree.ElementTree as ET
import xml.dom.minidom as md
import json
from copy import deepcopy
import numpy as np

# Solve path issue
import os.path
import sys
sys.path.append(os.path.dirname(__file__))

# Import my own modules
from netdef import PhysicalNet, OutputPortNet
from netdef import network_param, Wopanet_default_units
from unit_util import *

def check_file_ext(fpath:str, ext:str) -> str:
    '''
    Check the file name extension (ending) to make sure it's correct
    '''
    # ignore empty input
    if type(fpath) is not str:
        return None

    # make sure "ext" is in the format of ".xxx"
    if not ext.startswith('.'):
        ext = '.' + ext

    # Append file extension to the name if there's no extension in 
    if not fpath.endswith(ext):
        fpath += ext
        
    return fpath


def add_text_in_ext(fpath:str, *text:str, sep:str="_") -> str:
    '''
    Add a text in file path while preserving extension

    Example:
    >>> fname = "test.txt"
    >>> add_text_in_ext(fname, "new", "v")
    test_new_v.txt
    '''
    # Check extension name
    try:
        name, ext = fpath.rsplit(".", 1)
    except ValueError:
        name = fpath
        ext  = ""
    
    # Add text to path
    append_texts = sep.join(text)
    name = sep.join([name, append_texts])

    if len(ext) > 0:
        return ".".join([name, ext])
    else:
        return name
        



def get_portlist_index(portlist:list, physical_name:str, port:str)->int:
    '''
    return the index in a portlist
    '''
    for i, port_info in enumerate(portlist):
        if port_info["physical_node"] == physical_name and port_info["port"] == port:
            return i
    return None

class NetworkScriptHandler:
    '''
    Handles read/write and convert different network description files
    '''

    phy_net : PhysicalNet
    op_net  : OutputPortNet

    def __init__(self, phynet_fpath:str=None, opnet_fpath:str=None):
        if phynet_fpath is None:
            self.phy_net = None
        else:
            self.load_phynet(phynet_fpath)

        if opnet_fpath is None:
            self.op_net = None
        else:
            self.load_opnet(opnet_fpath)


    def load_phynet(self, fpath:str)->None:
        '''
        Load a physical network from file
        '''
        xml_root = ET.parse(fpath)
        self.phy_net = PhysicalNet()
        self.phy_net.read(xml_root)


    def load_opnet(self, fpath:str)->None:
        '''
        Load a output-port network from file
        '''
        self.op_net = OutputPortNet()
        self.op_net.read(fpath)

    def enforce_technology(self, in_filename:str, include_tech:list=[], exclude_tech:list=[], out_filename:str=None) -> str:
        '''
        Enforce technology setting to the given WOPANet file

        Parameters:
        --------------
        filename: WOPANet XML file contains the original network definition : str
        include_tech: (Optional) The technologies needed to be added : list of str
        exclude_tech: (Optional) The technologies needed to be taken out : list of str
        out_filename: (Optional) the output file name : str

        Return:
        --------------
        out_filename: the output file name, defulat is in_filename+"_enforced"

        Example:
        >>> in_file.technology = "FIFO+MOH"
        >>> enforce_technology(in_file, include_tech=["IS", "CEIL"], exclude_tech=["MOH"])
        >>> in_file.technology = "FIFO+IS+CEIL"
        '''
        # Special case, nothing needs to be down
        if len(include_tech) == 0 and len(exclude_tech) == 0:
            return in_filename

        # Load file
        xml_root = ET.parse(in_filename)
        net_elems = xml_root.findall("network")
        if(len(net_elems) != 1):
            raise ET.ParseError("Too many network items in XML")
        net_attribs = dict(net_elems[0].attrib)

        # Make sure at least has "name" attribute
        technologies = net_attribs.pop("technology", "")
        technologies = set(technologies.split("+"))
        technologies = technologies.union(include_tech)
        technologies = technologies - set(exclude_tech)
        technologies = "+".join(list(technologies))

        # Resolve output name
        if out_filename is None:
            out_filename = add_text_in_ext(in_filename, "enforced")
        elif out_filename.endswith("/"): # is a directory
            in_filename_no_path = in_filename.rsplit("/")[-1]
            out_filename = os.path.join(out_filename, add_text_in_ext(in_filename_no_path, "enforced"))

        net_elems[0].set("technology", technologies)

        # Dump file
        xml_root.write(out_filename, encoding="UTF-8", xml_declaration=True)

        return out_filename



    # Convert a WOPANet formated xml file into a json format in output port abstraction
    def phynet_to_opnet_json(self, ifpath:str, ofpath:str=None) -> dict:
        '''
        Changing a physical network definition from WOPANet format to the output-port abstraction format as a json

        Inputs:
        ---------
        ifpath: input file path  (str)
        ofpath: (Optional) output file path (str). Default = None means no output, return json as a python dictionary directly

        Returns:
        ---------
        json_out : [dict] the converted output-port network as if loaded from a json file
        '''
        # Ensure extension
        ifpath = check_file_ext(ifpath, 'xml')
        ofpath = check_file_ext(ofpath, 'json')
    
        # Parse file
        self.load_phynet(ifpath)

        ## Create output port network
        json_out = dict()
        # Network information
        technologies = self.phy_net.network.pop("technology", []) # list of technologies split by '+'
        network = {
            **self.phy_net.network,
            "time_unit": Wopanet_default_units["time"],
            "data_unit": Wopanet_default_units["data"],
            "rate_unit": Wopanet_default_units["rate"],
            "converted": ifpath,
        }

        network["packetizer"] = network_param["packetizer"] in technologies
        network["multiplexing"] = "FIFO" if "FIFO" in technologies else "ARBITRARY"
        network["analysis_option"] = list(set(network_param["analysis_option"]).intersection(technologies))                

        max_packet_length = self.phy_net.network.pop("maximum-packet-size", None)
        if max_packet_length is not None:
            network["max_packet_length"] = max_packet_length
        min_packet_length = self.phy_net.network.pop("minimum-packet-size", None)
        if min_packet_length is not None:
            network["min_packet_length"] = min_packet_length
        default_capacity = self.phy_net.network.pop("transmission-capacity", None)
        if default_capacity is not None:
            network["capacity"] = default_capacity

        # Count the number of output ports
        port_list = self.phy_net.get_output_ports(ignore_dummy=True)
        
        # Construct servers            
        servers = list()    # servers in output-port abstractions
        for port in port_list:

            service_curve = {
                "latencies": [port.pop("service-latency")],
                "rates": [port.pop("service-rate")]
            }

            capacity = None
            if "transmission-capacity" in port:
                capacity = port.pop("transmission-capacity")

            server_info = {"service_curve": service_curve, **port}
            if capacity is not None:
                server_info["capacity"] = capacity

            servers.append(server_info)


        # Construct flows
        flows = []
        for fl_name, fl_data in self.phy_net.flows.items():
            attrib = fl_data["attrib"]
            if attrib["arrival-curve"] != "leaky-bucket":
                raise NotImplementedError("The format currently only supports leaky-bucket arrival curves")

            arrival_curve = {
                "bursts": [attrib.pop("lb-burst")],
                "rates": [attrib.pop("lb-rate")]
            }

            # Get flow path
            path = []
            for step in fl_data["path"]:
                port_idx = get_portlist_index(port_list, step["node"], step["port"])
                if port_idx is not None:
                    path.append(servers[port_idx]["name"])

            # Assign the loaded information into the flow info
            flow_info = {"name": fl_name,"path": path, "arrival_curve": arrival_curve, **attrib}

            # Get flow packet length max/min
            # max
            flow_max_packet_length = flow_info.pop("maximum-packet-size", None)
            if flow_max_packet_length is not None:
                flow_info["max_packet_length"] = flow_max_packet_length

            # min
            flow_min_packet_length = flow_info.pop("minimum-packet-size", None)
            if flow_min_packet_length is not None:
                flow_info["min_packet_length"] = flow_min_packet_length

            flows.append(flow_info)
        
        # Dump file
        json_out = {
            "network": network,
            "flows": flows,
            "servers": servers
        }
        if ofpath is not None:
            with open(ofpath, "w") as ofile:
                json.dump(json_out, ofile, indent=4)

        return json_out

    
    # Convert a json file in output port abstraction to WOPANet XML
    def opnet_json_to_phynet(self, ifpath:str, ofpath:str) -> None:
        '''
        Changing a json output port network definition to an XML WOPANet definition

        Inputs:
        ---------
        ifpath: input file path  (str)
        ofpath: output file path (str)
        '''
        # Ensure extension
        ifpath = check_file_ext(ifpath, 'json')
        ofpath = check_file_ext(ofpath, 'xml')
    
        # Parse file
        self.load_opnet(ifpath)

        # Create an XML object
        m_encoding = "UTF-8"
        root = ET.Element("elements")

        ## General network information
        network_info = deepcopy(self.op_net.network_info)
        # Get technology
        technology = list()
        pk = network_info.pop("packetizer", False)
        if pk:
            technology.append("PK")
        if network_info.pop("multiplexing").upper() == "FIFO":
            technology.append("FIFO")
        technology += network_info.pop("analysis_option", [])
        network_info["technology"] = "+".join(technology)

        # Get units
        units = {
            "time": network_info.pop("time_unit", None),
            "data": network_info.pop("data_unit", None),
            "rate": network_info.pop("rate_unit", None)
        }

        network_info["converted"] = ifpath
        network_info = ET.SubElement(root, "network", network_info)

        ######################################
        # Define nodes (stations & switches) #
        ######################################
        sources = list()
        sinks   = list()
        # Prepare sources and sinks
        for fid, flow in enumerate(deepcopy(self.op_net.flows)):
            flow.setdefault("name", f"fl_{fid}")

            srcname = "src-{name}".format(name=flow["name"])
            ET.SubElement(root, "station", name=srcname)
            sources.append(srcname)

            snkname = "sink-{name}".format(name=flow["name"])
            ET.SubElement(root, "station", name=snkname)
            sinks.append(snkname)


        # Service curve and capacity
        server_names = list()
        port_names   = list()
        for sid, server in enumerate(self.op_net.servers):
            server = deepcopy(server)

            # Determine "station" or "switch", where "switch" being default
            server_type = server.pop("type", "switch")

            # Remove id
            server.pop("id", None)

            # Determine name of the server by the priority: physical_name -> name -> default name
            phy_name = f"{server_type[:2]}{sid}"
            phy_name = server.pop("name", phy_name)
            phy_name = server.pop("physical_node", phy_name)

            prt_name = server.pop("port", "o0")
            
            # Read service curve
            s_curve  = server.pop("service_curve")
            latency  = s_curve["latencies"][0]
            rate     = s_curve["rates"][0]
            capacity = server.pop("capacity", None)

            # Write server information
            server_info = {
                "name": phy_name,
                "service-latency": "{latency}".format(latency=latency * get_time_unit(units["time"], Wopanet_default_units["time"])),
                "service-rate": "{rate}".format(rate=rate * get_rate_unit(units["rate"], Wopanet_default_units["rate"]))
            }
            if capacity is not None:
                server_info["transmission-capacity"] = "{capacity}".format(capacity=capacity * get_rate_unit(units["rate"], Wopanet_default_units["rate"]))
            
            # Multiple output port may map to the same physical node. In this case we only need to add one switch/station to the network
            if phy_name not in server_names:
                ET.SubElement(root, server_type, server_info, **server)

            server_names.append(phy_name)
            port_names.append(prt_name)

        ################
        # Define links #
        ################
        # Connect all sources to starting switches, and all last switches to sinks
        for fid, flow in enumerate(self.op_net.flows):
            first_node = flow["path"][0]
            last_node  = flow["path"][-1]

            link_info = {
                "from": sources[fid],
                "to": server_names[first_node],
                "fromPort": "o0",
                "toPort": port_names[first_node],
                "name": f"lk:{sources[fid]}_0-{server_names[first_node]}_{port_names[first_node]}"
            }
            ET.SubElement(root, "link", link_info)

            link_info = {
                "from": server_names[last_node],
                "to": sinks[fid],
                "fromPort": port_names[last_node],
                "toPort": "i0",
                "name": f"lk:{server_names[last_node]}_{port_names[last_node]}-{sinks[fid]}_0"
            }
            ET.SubElement(root, "link", link_info)
    
        # Connect all links defined on adjacency matrix
        for r, row in enumerate(self.op_net.adjacency_mat):
            for c, val in enumerate(row):
                if (val>0):
                    link_info = {
                        "from": server_names[r],
                        "to": server_names[c],
                        "fromPort": port_names[r],
                        "toPort": port_names[c],
                        "name": f"lk:{server_names[r]}_{port_names[r]}-{server_names[c]}_{port_names[c]}"
                    }
                    ET.SubElement(root, "link", link_info)
                
        ################
        # Define flows #
        ################
        for fid, flow in enumerate(self.op_net.flows):
            flow = deepcopy(flow)

            curve_type = flow.pop("arrival-curve", 'leaky-bucket')
            max_packet_len = flow.pop("max_packet_length", None)
            min_packet_len = flow.pop("min_packet_length", None)

            fl_name = f"fl_{fid}"
            fl_name = flow.pop("name", fl_name)

            # Remove id
            flow.pop("id", None)

            a_curve = flow.pop("arrival_curve")
            burst = a_curve["bursts"][0]
            rate  = a_curve["rates"][0]

            path = flow.pop("path")

            if get_data_unit(units["data"], Wopanet_default_units["data"]) < 1:
                burst_str = "{b}{unit}".format(b=burst, unit=units["data"])
            else:
                burst_str = str(burst * get_data_unit(units["data"], Wopanet_default_units["data"]))

            flow_info = {
                "name": fl_name,
                "arrival-curve": curve_type,
                "lb-burst": burst_str,
                "lb-rate": "{rate}".format(rate=rate * get_rate_unit(units["rate"], Wopanet_default_units["rate"])),
                "source": sources[fid]
            }
            if max_packet_len is not None:
                if get_data_unit(units["data"], Wopanet_default_units["data"]) < 1:
                    flow_info["maximum-packet-size"] = "{max_pkl}{unit}".format(max_pkl=max_packet_len, unit=units["data"])
                else:
                    flow_info["maximum-packet-size"] = str(max_packet_len * get_data_unit(units["data"], Wopanet_default_units["data"]))
            if min_packet_len is not None:
                if get_data_unit(units["data"], Wopanet_default_units["data"]) < 1:
                    flow_info["minimum-packet-size"] = "{min_pkl}{unit}".format(min_pkl=min_packet_len, unit=units["data"])
                else:
                    flow_info["minimum-packet-size"] = str(min_packet_len * get_data_unit(units["data"], Wopanet_default_units["data"]))

            flow_elem = ET.SubElement(root, "flow", flow_info, **flow)
            path_elem = ET.SubElement(flow_elem, "target")

            for step in path:
                ET.SubElement(path_elem, "path", node=server_names[step])
            ET.SubElement(path_elem, "path", node=sinks[fid])

        #################
        # Dump XML file #
        #################
        dom = md.parseString(ET.tostring(root))
        xml_string = dom.toprettyxml()
        part1, part2 = xml_string.split('?>')

        with open(ofpath, 'w') as xfile:
            xfile.write(part1 + 'encoding=\"{}\"?>\n'.format(m_encoding) + part2)
            xfile.close()


    def is_cyclic(self, choose_op_net:bool=True)->bool:
        '''
        Determine if the network is cyclic
        '''
        if choose_op_net:
            if self.op_net is not None:
                return self.op_net.is_cyclic()
            raise RuntimeError("Output port network hasn't been initialized.")

        raise NotImplementedError()


    def get_network_info(self, filename:str, target_attr:str, default=None):
        '''
        Get a certain attribute from a file, return None if not found
        '''
        if filename.endswith("xml"):
            # Load the information
            xml_root = ET.parse(filename)
            net = PhysicalNet()
            net.parse_network(xml_root)
            
            return net.network.get(target_attr, default)

        elif filename.endswith("json"):
            # Load the information
            with open(filename, 'r') as ifile:
                network_def = json.load(ifile)
                if "network" not in network_def:
                    return default
                return network_def["network"].get(target_attr, default)

        return default

    
    def get_network_utility(self, filename:str) -> dict:
        '''
        Obtain network load (utility) for each server
        '''
        if filename.endswith(".xml"):
            network_def = self.phynet_to_opnet_json(filename)
            opnet = OutputPortNet(network_def=network_def)
        elif filename.endswith(".json"):
            opnet = OutputPortNet(ifile=filename)
        else:
            raise ValueError("File type of network description file \"{fn}\" not supported".format(fn=filename))

        return opnet.get_utility()
        