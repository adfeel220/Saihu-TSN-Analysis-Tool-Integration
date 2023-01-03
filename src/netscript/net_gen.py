# Module to generate networks

import json
import numpy as np


def generate_interleaved_tandem(size:int, burst:float, arr_rate:float, pkt_leng:float, latency:float, ser_rate:float, capacity:float, dir:str=None) -> dict:
    '''
    Generate an interleaved tandem with all arrival/service curves being identical.

    Params:
    size    : size of the network = number of servers = number of flows

    burst   : burst of flows
    arr_rate: arrival rate of flows
    pkt_leng: packet length of flows

    latency : service latency
    ser_rate: service rate
    capacity: server capacity
    
    dir: directory to dump the generated json file. If it's None, no file will be dumped.
    '''

    ## Create the adjacency matrix of this feed forward network
    # Method: 
    # 1. Shift an identity matrix right by 1 to form a cyclic network 
    adjacency_matrix = np.eye(size)
    adjacency_matrix = np.roll(adjacency_matrix, 1, axis=1)
    # 2. Remove all links to server 0 to break the network from a cycle into a chain
    adjacency_matrix[:,0] = 0
    # 3. Convert to list to allow JSON serialization
    adjacency_matrix = adjacency_matrix.tolist()

    ## Define flows
    flows = [None]*size
    # 1. The flow to go through the entire network (chain)
    through_flow = {
        "path": list(range(size)),
        "arrival_curve": {
            "bursts": [burst],
            "rates": [arr_rate]
        },
        "packet_length": pkt_leng
    }
    flows[0] = through_flow
    # 2. The flows to "interleave" the servers. Flows through every adjacent pair of servers.
    for flow_idx in range(1, size):
        flows[flow_idx] = {
            "name": f"fl_{flow_idx}",
            "path": [flow_idx-1, flow_idx],
            "arrival_curve": {
                "bursts": [burst],
                "rates": [arr_rate]
            },
            "packet_length": pkt_leng
        }

    ## Define servers
    servers = [None]*size
    for server_idx in range(size):
        servers[server_idx] = {
            "name": f"s_{server_idx}",
            "service_curve": {
                "latencies": [latency],
                "rates": [ser_rate]
            },
            "capacity": capacity
        }


    ## Dump network definition
    network = {
        "network": {"name": f"interleave-{size}", "technology": ["FIFO"]},
        "adjacency_matrix": adjacency_matrix,
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    return network



def generate_ring(size:int, burst:float, arr_rate:float, pkt_leng:float, latency:float, ser_rate:float, capacity:float, dir:str=None) -> dict:
    '''
    Generate a ring with all arrival/service curves being identical.

    Params:
    size    : size of the network = number of servers = number of flows

    burst   : burst of flows
    arr_rate: arrival rate of flows
    pkt_leng: packet length of flows

    latency : service latency
    ser_rate: service rate
    capacity: server capacity
    
    dir: directory to dump the generated json file. If it's None, no file will be dumped.
    '''
    ## Create the adjacency matrix
    # Method:
    if size > 1:
        # 1. Shift an identity matrix right by 1 to form a cyclic network 
        adjacency_matrix = np.eye(size)
        adjacency_matrix = np.roll(adjacency_matrix, 1, axis=1)
        # 2. Convert to list to allow JSON serialization
        adjacency_matrix = adjacency_matrix.tolist()
    else:
        adjacency_matrix = [[0]]

    ## Define flows
    flows = [None]*size
    # 1. The flows to go through all servers by each starting server
    for flow_idx in range(size):
        path = np.roll(np.arange(size), -flow_idx)
        path = path.tolist()
        flows[flow_idx] = {
            "name": f"fl_{flow_idx}",
            "path": path,
            "arrival_curve": {
                "bursts": [burst],
                "rates": [arr_rate]
            },
            "packet_length": pkt_leng
        }

    ## Define servers
    servers = [None]*size
    for server_idx in range(size):
        servers[server_idx] = {
            "name": f"s_{server_idx}",
            "service_curve": {
                "latencies": [latency],
                "rates": [ser_rate]
            },
            "capacity": capacity
        }


    ## Dump network definition
    network = {
        "network": {"name": f"ring-{size}", "technology": ["FIFO"]},
        "adjacency_matrix": adjacency_matrix,
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    return network



def generate_mesh(size:int, burst:float, arr_rate:float, pkt_leng:float, latency:float, ser_rate:float, capacity:float, dir:str=None) -> dict:
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
    Note that the last server "sn" has service rate = 2*ser_rate since there are twice as many flows

    Parameters:
    ---------------
    size: the number of servers in the network, if size is even, will return one network with size+1 servers having an extra server at the end

    burst   : burst of flows
    arr_rate: arrival rate of flows
    pkt_leng: packet length of flows

    latency : service latency
    ser_rate: service rate
    capacity: server capacity
    '''
    ## Check if available construction
    if size%2 == 0:
        size += 1

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
    if size > 1:
        adjacency_matrix = np.zeros((size, size))
        # front mesh part
        for l in range(mesh_level-1):
            adjacency_matrix[(2*l):(2*l+2), (2*l+2):(2*l+4)] = 1
        # end in 1 server
        adjacency_matrix[[-3, -2], -1] = 1
        adjacency_matrix = adjacency_matrix.tolist()
    else:
        adjacency_matrix = [[0]]

    ## Define flows
    flows = [None]*(2**mesh_level)
    base_index = np.arange(mesh_level, dtype=int)*2
    # use binary representation of length "mesh_level" of a integer, each bit is 0 if select upper server; 1 if lower
    for flow_idx in range(2**mesh_level):
        bin_id = '{0:0{width}b}'.format(flow_idx, width=mesh_level)
        selection = np.array([int(b) for b in bin_id], dtype=int)
        path = (selection + base_index).tolist() + [size-1]
        flows[flow_idx] = {
            "name": f"fl_{flow_idx}",
            "path": path,
            "arrival_curve": {
                "bursts": [burst],
                "rates": [arr_rate]
            },
            "packet_length": pkt_leng
        }

    ## Define servers
    servers = [None]*size
    for server_idx in range(size-1):
        servers[server_idx] = {
            "name": f"s_{server_idx}",
            "service_curve": {
                "latencies": [latency],
                "rates": [ser_rate]
            },
            "capacity": capacity
        }
    servers[-1] = {
        "name": f"s_{size-1}",
        "service_curve": {
            "latencies": [latency],
            "rates": [2*ser_rate]
        },
        "capacity": capacity
    }


    ## Dump network definition
    network = {
        "network": {"name": f"mesh-{size}", "technology": ["FIFO"]},
        "adjacency_matrix": adjacency_matrix,
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    return network

