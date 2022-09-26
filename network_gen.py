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
            "burst": burst,
            "times": [],
            "rates": [arr_rate]
        },
        "packet_length": pkt_leng
    }
    flows[0] = through_flow
    # 2. The flows to "interleave" the servers. Flows through every adjacent pair of servers.
    for flow_idx in range(1, size):
        flows[flow_idx] = {
            "path": [flow_idx-1, flow_idx],
            "arrival_curve": {
                "burst": burst,
                "times": [],
                "rates": [arr_rate]
            },
            "packet_length": pkt_leng
        }

    ## Define servers
    servers = [None]*size
    for server_idx in range(size):
        servers[server_idx] = {
            "name": "",
            "service_curve": {
                "latency": latency,
                "times": [],
                "rates": [ser_rate]
            },
            "capacity": capacity
        }


    ## Dump network definition
    network = {
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
            "path": path,
            "arrival_curve": {
                "burst": burst,
                "times": [],
                "rates": [arr_rate]
            },
            "packet_length": pkt_leng
        }

    ## Define servers
    servers = [None]*size
    for server_idx in range(size):
        servers[server_idx] = {
            "name": "",
            "service_curve": {
                "latency": latency,
                "times": [],
                "rates": [ser_rate]
            },
            "capacity": capacity
        }


    ## Dump network definition
    network = {
        "adjacency_matrix": adjacency_matrix,
        "flows": flows,
        "servers": servers
    }
    if dir is not None:
        with open(dir, "w") as ofile:
            json.dump(network, ofile, indent=4)

    return network