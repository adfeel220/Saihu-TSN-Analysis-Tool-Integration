# Module to generate networks

import json
import numpy as np
import random
from copy import deepcopy
from unit_util import *

####################################
# Generate certain type of network #
####################################

def generate_interleave_tandem(size:int, burst:float, arrival_rate:float, max_packet_length:float, latency:float, service_rate:float, capacity:float, dir:str=None) -> dict:
    '''
    Generate an interleave tandem with all arrival/service curves being identical.
    An interleave tandem network is a chain topology,
    ------    ------        --------    --------
    | s0 | -> | s1 | -> ... | sn-2 | -> | sn-1 |
    ------    ------        --------    --------
    With flows
    f0: s0->s1->...->sn-1
    fi: fi-1 -> fi, for all i in [1, n-1]

    Params:
    -------------
    size : size of the network = number of servers = number of flows

    burst             : burst of flows
    arrival_rate      : arrival rate of flows
    max_packet_length : maximum packet length of flows

    latency      : service latency
    service_rate : service rate
    capacity     : server output capacity, unit in bps
    
    dir: directory to dump the generated json file. If it's None, no file will be dumped.

    Returns:
    --------------
    network: [dict] The network written as an output port network
    '''
    print(f"Generating a interleave tandem network of {size} servers...", end='')

    ## Define servers
    servers = [None]*size
    for server_idx in range(size):
        servers[server_idx] = {
            "name": f"s{server_idx}",
            "service_curve": {
                "latencies": [latency],
                "rates": [service_rate]
            },
            "capacity": capacity
        }

    ## Define flows
    flows = [None]*size
    # 1. The flow to go through the entire network (chain)
    through_flow = {
        "name": "f0",
        "path": [servers[idx]["name"] for idx in np.arange(size)],
        "arrival_curve": {
            "bursts": [burst],
            "rates": [arrival_rate]
        },
        "max_packet_length": max_packet_length
    }
    flows[0] = through_flow
    # 2. The flows to "interleave" the servers. Flows through every adjacent pair of servers.
    for flow_idx in range(1, size):
        flows[flow_idx] = {
            "name": f"f{flow_idx}",
            "path": [servers[flow_idx-1]["name"], servers[flow_idx]["name"]],
            "arrival_curve": {
                "bursts": [burst],
                "rates": [arrival_rate]
            },
            "max_packet_length": max_packet_length
        }



    ## Dump network definition
    network = {
        "network": {"name": f"interleave-{size}", "multiplexing": "FIFO"},
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    print("Done")

    return network



def generate_ring(size:int, burst:float, arrival_rate:float, max_packet_length:float, latency:float, service_rate:float, capacity:float, dir:str=None) -> dict:
    '''
    Generate a ring with all arrival/service curves being identical.
    An interleave tandem network is a chain topology,
    ------    ------        --------    --------
    | s0 | -> | s1 | -> ... | sn-2 | -> | sn-1 |
    ------    ------        --------    --------
       î                                    |
       --------------------------------------
    With flows
    f0: s0 -> ... -> sn-1
    f1: s1 -> ... -> sn-1 -> s0
    f2: s2 -> ... -> sn-1 -> s0 -> s1
    ...
    fn-1: sn-1 -> s0 -> s1 -> ... -> sn-2

    Params:
    size : size of the network = number of servers = number of flows

    burst        : burst of flows
    arrival_rate : arrival rate of flows
    max_packet_length: packet length of flows

    latency : service latency
    service_rate: service rate
    capacity: server capacity
    
    dir: directory to dump the generated json file. If it's None, no file will be dumped.
    '''
    print(f"Generating a ring network of {size} servers...", end='')

    ## Define servers
    servers = [None]*size
    for server_idx in range(size):
        servers[server_idx] = {
            "name": f"s{server_idx}",
            "service_curve": {
                "latencies": [latency],
                "rates": [service_rate]
            },
            "capacity": capacity
        }

    ## Define flows
    flows = [None]*size
    # 1. The flows to go through all servers by each starting server
    for flow_idx in range(size):
        path = np.roll(np.arange(size), -flow_idx)
        path = [servers[idx]["name"] for idx in path]
        flows[flow_idx] = {
            "name": f"f{flow_idx}",
            "path": path,
            "arrival_curve": {
                "bursts": [burst],
                "rates": [arrival_rate]
            },
            "max_packet_length": max_packet_length
        }


    ## Dump network definition
    network = {
        "network": {"name": f"ring-{size}", "multiplexing": "FIFO"},
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    print("Done")

    return network



def generate_mesh(size:int, burst:float, arrival_rate:float, max_packet_length:float, latency:float, service_rate:float, capacity:float, dir:str=None) -> dict:
    '''
    Generate a mesh network, which has the topology
    ------   ------      --------
    | s0 | - | s2 | ---- | sn-2 |
    ------   ------      --------   ------
           X        X ...         > | sn |
    ------   ------      --------   ------
    | s1 | - | s3 | ---- | sn-1 |
    ------   ------      --------

    The flows are all combination from s0/s1 to sn
    Note that the last server "sn" has service rate = 2*service_rate since there are twice as many flows

    Parameters:
    ---------------
    size: the number of servers in the network, if size is even, will return one network with size+1 servers having an extra server at the end

    burst   : burst of flows
    arrival_rate: arrival rate of flows
    max_packet_length: packet length of flows

    latency : service latency
    service_rate: service rate
    capacity: server capacity
    '''
    print(f"Generating a mesh network of {size} servers...", end='')

    ## Check if available construction
    if size%2 == 0:
        size += 1
        print("Mesh network must have odd number of servers, add 1 new server...", end='')

    mesh_level = size//2 # the number of level of interwinding mesh
    ## Create the adjacency matrix
    # The adjacency matrix should like like this:
    # 0, 0, 1, 1, 0, ...
    # 0, 0, 1, 1, 0, ...
    # 0, 0, 0, 0, 1, 1, 0, ...
    # 0, 0, 0, 0, 1, 1, 0, ...
    # ...
    # 0, ... , 1, 1, 0
    # 0, ... , 1, 1, 0
    # 0, ... , 0, 0, 1
    # 0, ... , 0, 0, 1
    # 0, ... , 0, 0, 0
    # if size > 1:
    #     adjacency_matrix = np.zeros((size, size))
    #     # front mesh part
    #     for l in range(mesh_level-1):
    #         adjacency_matrix[(2*l):(2*l+2), (2*l+2):(2*l+4)] = 1
    #     # end in 1 server
    #     adjacency_matrix[[-3, -2], -1] = 1
    #     adjacency_matrix = adjacency_matrix.tolist()
    # else:
    #     adjacency_matrix = [[0]]

    ## Define servers
    servers = [None]*size
    for server_idx in range(size-1):
        servers[server_idx] = {
            "name": f"s_{server_idx}",
            "service_curve": {
                "latencies": [latency],
                "rates": [service_rate]
            },
            "capacity": capacity
        }
    servers[-1] = {
        "name": f"s_{size-1}",
        "service_curve": {
            "latencies": [latency],
            "rates": [2*service_rate]
        },
        "capacity": capacity
    }


    ## Define flows
    flows = [None]*(2**mesh_level)
    base_index = np.arange(mesh_level, dtype=int)*2
    # use binary representation of length "mesh_level" of a integer, each bit is 0 if select upper server; 1 if lower
    for flow_idx in range(2**mesh_level):
        bin_id = '{0:0{width}b}'.format(flow_idx, width=mesh_level)
        selection = np.array([int(b) for b in bin_id], dtype=int)
        path = (selection + base_index).tolist() + [size-1]
        path = [servers[idx]["name"] for idx in path]
        flows[flow_idx] = {
            "name": f"fl_{flow_idx}",
            "path": path,
            "arrival_curve": {
                "bursts": [burst],
                "rates": [arrival_rate]
            },
            "max_packet_length": max_packet_length
        }


    ## Dump network definition
    network = {
        "network": {"name": f"mesh-{size}", "multiplexing": "FIFO"},
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    print("Done")

    return network


###########################
# Generate random network #
###########################
def node_name(id):
    return f"S{id}"

def port_name(sname, pid):
    return f"{sname}-o{pid}"

def get_uniform(minval, maxval=None, force_type=float) -> str:
    if maxval is None:
        return minval
    
    if not is_comparable(minval, maxval):
        raise ValueError(f"The values \'{minval}\' and \'{maxval}\' are not in the same unit")
    min_num = parse_num_unit(minval)
    max_num = parse_num_unit(maxval)
    val = force_type(random.uniform(min_num, max_num))
    val, mul = decide_multiplier(val)

    unit = ''
    if is_time_unit(minval) or is_time_unit(maxval):
        unit = 's'
    if is_data_unit(minval) or is_data_unit(maxval):
        unit = 'b'
    if is_rate_unit(minval) or is_rate_unit(maxval):
        unit = 'bps'

    return f"{val}{mul}{unit}"


def generate_fix_topology_network(num_flows:int,
                                  connections:dict,
                                  burst  , arrival_rate, max_packet_length,
                                  latency, service_rate, capacity,
                                  max_out_end_stations:int=1,
                                  network_attrib:dict=dict(),
                                  server_attrib:dict=dict(),
                                  flow_attrib:dict=dict(),
                                  dir:str=None,
                                  link_prob:float=0.9,
                                  rand_seed:int=None) -> dict:
    '''
    Generate a network with a given switch topology

    Input
    ---------
    - num_flows   `int` : number of flows to be generated in the network
    - connections `dict[str, list[str]]` : possible connections between switches. key=name of switch; value=list of switch's name that "key" can connect to. e.g.
        connections = {
            "s1": ["s2", "s3"],
            "s2": ["s3"],
            "s3": ["s1", "s2"]
        }
        this means 's1' can go to 's2' & 's3'; 's2' can go to 's3'; and 's3' can go to 's1' & 's2'
    - burst `float|str|Iterable` : burst of arrival curve, can be 
        1. `float`: a direct assignment. e.g. 2.0
        2. `str`: a constant assignment with unit. e.g. "2.5kB"
        3. `Iterable`: length 2 indicating min and max value, the burst value will be selected randomly between min & max. e.g. ("100b", "5kB")
    - arrival_rate `float|str|Iterable` : arrival rate of arrival curve, can be 
        1. `float`: a direct assignment. e.g. 2.0
        2. `str`: a constant assignment with unit. e.g. "2.5Mbps"
        3. `Iterable`: length 2 indicating min and max value, the rate value will be selected randomly between min & max. e.g. ("1kbps", "50Mbps")
    - max_packet_length `float|str` : maximum packet length of a flow, can be 
        1. `float`: a direct assignment. e.g. 2.0
        2. `str`: a constant assignment with unit. e.g. "10kB"
    - latency `float|str|Iterable` : latency of service curve, can be 
        1. `float`: a direct assignment. e.g. 2.0
        2. `str`: a constant assignment with unit. e.g. "2.5ms"
        3. `Iterable`: length 2 indicating min and max value, the latency value will be selected randomly between min & max. e.g. ("10us", "20ms")
    - service_rate `float|str|Iterable` : service rate of service curve, can be 
        1. `float`: a direct assignment. e.g. 2.0
        2. `str`: a constant assignment with unit. e.g. "2.5Mbps"
        3. `Iterable`: length 2 indicating min and max value, the burst value will be selected randomly between min & max. e.g. ("1kbps", "50Mbps")
    - capacity `float|str` : capacity of a link, can be 
        1. `float`: a direct assignment. e.g. 2.0
        2. `str`: a constant assignment with unit. e.g. "1Gbps"
    - max_out_end_stations `int` : maximum number of end stations (sink) that can be attached to a switch. Default is 1
    - network_attrib `dict` : (optional) Additinoal network information. Default is empty
    - server_attrib `dict`  : (optional) Additinoal server information. Default is empty
    - flow_attrib `dict`    : (optional) Additinoal flow information. Default is empty
    - dir `str` : (optional) path to dump the generated file as a json output-port network. Default is None, where no file will be dumped
    - link_prob `float` : (optional) probability p to continue finding next switch, otherwise directly go to a sink. Default is 0.9
    - rand_seed `int` : (optional) random seed to feed to python `random` library. Default is None (random seed by time)

    Output
    ----------
    output_port_network `dict` : the generated network in JSON format written in a dictionary

    Example
    ----------
    >>> connections = {
            "S1": [      "S2", "S3",                         "S8"],
            "S2": ["S1",             "S4",                   "S8"],
            "S3": ["S1",             "S4", "S5",       "S7", "S8"],
            "S4": [      "S2", "S3",             "S6", "S7", "S8"],
            "S5": [            "S3",             "S6", "S7"],
            "S6": [                  "S4", "S5",       "S7"],
            "S7": [            "S3", "S4", "S5", "S6"],
            "S8": ["S1", "S2", "S3", "S4"]
        }
    >>> net = generate_fix_topology_network(num_flows=30, connections=connections,
                burst=("10B", "500B"), arrival_rate=("200bps", "20kbps"), max_packet_length="6kB",
                latency=("2us", "200ms"), service_rate=("1Mbps", "50Mbps"), capacity="100Mbps",
                dir="test.json",
                link_prob=0.9)
    '''
    assert num_flows >= 1
    assert 0 <= link_prob <= 1
    assert max_out_end_stations >= 1

    random.seed(rand_seed)

    NUM_SWITCHES = len(connections)

    print(f"Generating random fixed-topology network of {num_flows} flows and {NUM_SWITCHES} switches...", end='')

    #####################
    # Random Generation #
    #####################
    # init
    next_output_port = dict(zip(connections.keys(), [1]*NUM_SWITCHES))
    next_input_port  = dict(zip(connections.keys(), [1]*NUM_SWITCHES))
    next_input_port.update(zip([f"sk{i}" for i in range(1, max_out_end_stations+1)], [1]*max_out_end_stations))

    network = deepcopy(network_attrib)
    network.setdefault("name", f"NONAME-F{num_flows}-SW{NUM_SWITCHES}")
    network.setdefault("multiplexing", "FIFO")

    # used_connection : labels the used connection
    # key=(from_switch_id, to_switch_id) ; value=(from_output_port_id, to_input_port_id)
    # to_switch_id is negative if it's a sink
    used_connection = dict()

    flows   = list()
    servers = list()

    server_names = list()

    # random paths
    for fid in range(num_flows):
        path = list()
        # randomly decides a starting source
        src_node = random.choice(list(connections.keys()))

        visited_switches = set()

        while True:                    
            # Generate next node
            # Check if still has unvisited switch
            if set(connections[src_node]).issubset(visited_switches):
                break

            if random.random() < link_prob:  # connect to next switch
                # get a switch name from unvisited switches
                next_node = random.choice(list(set(connections[src_node])-visited_switches))

            else:   # going directly to sink
                next_node = "sk{}".format(random.randint(1, max_out_end_stations))

            visited_switches.add(src_node)

            if (src_node, next_node) not in used_connection:
                used_connection[(src_node, next_node)] = (next_output_port[src_node], next_input_port[next_node])
                next_output_port[src_node] += 1
                next_input_port[next_node] += 1

            out_port, in_port = used_connection[(src_node, next_node)]
            out_port_name = port_name(src_node, out_port)

            # Add server if it's not defined yet
            if out_port_name not in server_names:
                # Create a new output port
                servers.append({
                    "name": out_port_name,
                    "service_curve": {
                        "latencies": [get_uniform(*latency) if type(latency) is tuple else latency],
                        "rates": [get_uniform(*service_rate) if type(service_rate) is tuple else service_rate]
                    },
                    "capacity": capacity,
                    **server_attrib
                })
                server_names.append(out_port_name)

            path.append(out_port_name)
            src_node = next_node

            if src_node.startswith("sk"):
                break
        

        flows.append({
            "name": f"f{fid+1}",
            "path": path,
            "arrival_curve": {
                "bursts": [get_uniform(*burst, force_type=int) if type(burst) is tuple else burst],
                "rates": [get_uniform(*arrival_rate) if type(arrival_rate) is tuple else arrival_rate]
            },
            "max_packet_length": max_packet_length,
            **flow_attrib
        })

    dump_file = {
        "network": network,
        "servers": servers,
        "flows": flows
    }

    # output dump file
    if dir is not None:
        with open(dir, 'w') as ofile:
            json.dump(dump_file, ofile, indent=4)

    print("Done")

    return dump_file