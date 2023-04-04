#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

# This file is part of the panco project.
# https://github.com/Huawei-Paris-Research-Center/Panco

from __future__ import annotations

__author__ = "Anne Bouillard"
__maintainer__ = "Anne Bouillard"
__email__ = "anne.bouillard@huawei.com"
__copyright__ = "Copyright (C) 2022, Huawei Technologies France"
__license__ = "BSD-3"


import numpy as np
from collections import defaultdict
from copy import deepcopy
from typing import List, Tuple, Dict

from panco.descriptor.flow import Flow
from panco.descriptor.server import Server
from panco.descriptor.curves import tb_sum, residual_blind, RateLatency, TokenBucket


def _sort_lists_of_lists(lol: List[List[int]]):
    """
    Sort lists of a lists of lists

    :param lol: list of lists
    :return: lol, where each list is sorted in the non-decreasing order


    >>> _sort_lists_of_lists([[0, 1, 3], [3, 0, 2], [2, 1]])
    [[0, 1, 3], [0, 2, 3], [1, 2]]
    """
    return [sorted(u_list) for u_list in lol]


def topology(num_servers: int, num_flows: int, path: List[List[int]]):
    """ "
    Topology builds the set of successors and predecessors of the network,
    also builds for each servers the list of flows crossing it.

    :param num_servers: the number of servers in the network
    :type num_servers: int
    :param num_flows: the number of flows in the network
    :type num_flows: int
    :param path: list of paths followed by the flows
    :type path: List[List[int]]
    :return predecessors: the list of the predecessor's list for each server (List[List[int]])
    :return successors: the list of the successor's list for each server (List[List[int]])
    :return flows_in_server: the list of flows that cross each server (List[List[int]])


    >>> paths = [[0, 1, 3], [3, 2, 0], [1, 2]]
    >>> topology(4, 3, paths)
    ([[2], [0], [1, 3], [1]], [[1], [2, 3], [0], [2]], [[0, 1], [0, 2], [1, 2], [0, 1]])
    """
    successors = [[] for _ in range(num_servers)]
    predecessors = [[] for _ in range(num_servers)]
    flows_in_server = [
        [i for i in range(num_flows) if j in path[i]] for j in range(num_servers)
    ]
    for i in range(num_flows):
        for j in range(len(path[i]) - 1):
            if path[i][j + 1] not in successors[path[i][j]]:
                successors[path[i][j]] += [path[i][j + 1]]
            if path[i][j] not in predecessors[path[i][j + 1]]:
                predecessors[path[i][j + 1]] += [path[i][j]]
    return (
        _sort_lists_of_lists(predecessors),
        _sort_lists_of_lists(successors),
        _sort_lists_of_lists(flows_in_server),
    )


def server_depth(num_servers: int, successors: List[List[int]]) -> List[int]:
    """
    Returns the depth of each server in a rooted-forest (the root of each tree is the unique sink
    of the connected component).
    Sinks have depth 0 and a node has the depth of its successor + 1
    The servers must be ordered by their depth (a node has a successor with higher number)

    :param num_servers: the number of servers in the network
    :param successors: The list of successors in of each server
    :return: the list of depths for each server (List[int])


    >>> server_depth(8, [[2], [3], [7], [4], [7], [7], [7], []])
    [2, 3, 1, 2, 1, 1, 1, 0]
    """
    depth = num_servers * [0]
    for i in range(num_servers - 2, -1, -1):
        # print(i)
        if not successors[i] == []:
            depth[i] = depth[successors[i][0]] + 1
            if len(successors[i]) > 2:
                raise Exception("The network is not a rooted-forest ")
    return depth


def backward_search(sink: int, predecessors: List[List[int]]) -> List[int]:
    """
    Performs the backward search of the servers having a path directed to sink.

    :param sink: the server from which the backward search is done
    :param predecessors: list of the list of predecessors of each server
    :return: the list of servers having a path to sink (List[int])


    >>> backward_search(3, [[2], [0], [1, 3], [1]])
    [0, 1, 2, 3]
    >>> backward_search(3, [[1], [0], [1, 3], [1]])
    [0, 1, 3]
    """
    q = {sink}
    servers = set([])
    while len(q) > 0:
        sink = q.pop()
        servers |= {sink}
        q |= set(predecessors[sink])
        q -= servers
    return sorted(list(servers))


def trunc_path(path: List[List[int]], list_servers: [List[int]]) -> List[List[int]]:
    """
    Computes the sub-path of servers in list_servers for each path in path

    :param path: list of paths
    :param list_servers: list of servers
    :return: the list of sub_paths (List[List[int]])


    >>> trunc_path([[0, 1, 2, 3], [2, 3, 4], [3, 2, 5, 1]], [0, 1, 3])
    [[0, 1, 3], [3], [3, 1]]
    """
    return [
        [path[i][j] for j in range(len(path[i])) if path[i][j] in list_servers]
        for i in range(len(path))
    ]


def reindexing(lis: List[int]) -> Dict[int]:
    """
    Builds a disciotany from a list. dict[key] is the place of key/

    :param lis: list
    :return: the dicionnart of the indices of the list


    >>> reindexing([3, 1, 4, 6])
    {3: 0, 1: 1, 4: 2, 6: 3}
    """
    return dict(zip(lis, range(len(lis))))


def dfs(
    u: int,
    num_servers: int,
    successors: List[List[int]],
    state: List[int],
    queue: List[int],
    sort: List[int],
) -> Tuple[List[int], List[int], List[int]]:
    """
    Depth-first-search implementation of a graph without cycles

    :param u: source node
    :param num_servers: size of the network
    :param successors: adjacency list of the nodes (list of successors)
    :param state: state of the nodes ('white'/'gray'/'black')
    :param queue: set of nodes queued for analysis
    :param sort: list of nodes in the reversed order of end of discovery (when they become 'black')
    :return: the new state after exploration from u, new queue, update order

    >>> dfs(4, 6, [[], [0], [1, 4], [], [0, 3, 5], [3]], [0, 0, 0, 0, 0, 0], [], [])
    (array([2, 0, 0, 2, 2, 2]), [], [4, 5, 3, 0])
    """
    state[u] = 1
    queue = [u] + queue
    while not queue == []:
        for v in successors[u]:
            if state[v] == 0:
                (state, queue, sort) = dfs(
                    v, num_servers, successors, state, queue, sort
                )
            elif state[v] == 1:
                raise NameError("Network has cycles: feed-forward analysis impossible")
        sort = [u] + sort
        state[u] = 2
        queue = queue[1:]
        return state, queue, sort


def topological_sort(successors: List[List[int]], num_servers: int) -> List[int]:
    """
    Topological sort of a graph given by its lists of successors (adjacency)

    :param successors: the list of successors of each node
    :param num_servers: the number of nodes of the graph
    :return: the topological order of the nodes, and an error if the graph has cycles.


    >>> topological_sort([[], [0], [1, 4], [], [0, 3, 5], [3]], 6)
    [2, 4, 5, 3, 1, 0]
    """
    sort = []
    state = [0 for _ in range(num_servers)]
    u = int(np.argmin(state))
    while state[u] == 0:
        (state, queue, sort) = dfs(u, num_servers, successors, state, [], sort)
        u = np.argmin(state)
    return sort


def inverse_permutation(tab: List[int]) -> List[int]:
    """
    Inverse the computation given by tab

    :param tab: the inverse of the permutation
    :return: the permutation: tab[inverse_tab[i]] = i


    >>> inverse_permutation([1, 3, 0, 2])
    [2, 0, 3, 1]
    """
    n = len(tab)
    inv_tab = n * [0]
    for i in range(n):
        inv_tab[tab[i]] = i
    return inv_tab


def list_to_str(lis: list) -> str:
    return "\n".join(["   %4i: %s" % (i, x) for (i, x) in enumerate(lis)])


def print_list(lis: list):
    print(list_to_str(lis))


class Network:
    """
    The class Network encodes a network. A network is described by

    - a list of servers (with minimal and maximal service curves)
    - a list of flows (with a path and an arrival curve)
    - some shaping parameters: if flows are shaped at the entrance of the network.

    :param servers: the list of server description
    :param flows: the list of flows circulating in the network
    :param arrival_shaping: the potential shaping for groups of flows (server, list of flows, maximum service curve)
    :type arrival_shaping: List[(int, List[int], List[TokenBucket])] if not None

    :param self.num_servers: number of servers in the network (int)
    :param self.num_flows: number of flows in the network (int)
    :param self.path: list of paths of the flows (List[List[int]])
    :param self.predecessors: list of predecessors of the servers (List[List[int]])
    :param self.successors: list of successors of the servers (List[List[int]])
    :param self.flows_in_server: list of flows crossing each server (List[List[int]])

    >>> flows = [Flow([TokenBucket(2, 1)], [0, 1]), Flow([TokenBucket(3, 2)], [1, 0])]
    >>> servers = [Server([RateLatency(5, 1)], []), Server([RateLatency(6, 2)], [])]
    >>> arrival_shaping = [(0, [0], [TokenBucket(1, 6)])]
    >>> network = Network(servers, flows, arrival_shaping)
    >>> network.num_servers
    2
    >>> network.num_flows
    2
    >>> network.flows == flows
    True
    >>> network.servers == servers
    True
    >>> network.path
    [[0, 1], [1, 0]]
    >>> network.predecessors
    [[1], [0]]
    >>> network.successors
    [[1], [0]]
    >>> network.flows_in_server
    [[0, 1], [0, 1]]
    """

    def __init__(self, servers: List[Server], flows: List[Flow], arrival_shaping=None):
        """
        Construction of a network
        """
        if arrival_shaping is None:
            arrival_shaping = []
        self.num_servers = len(servers)
        self.num_flows = len(flows)
        self.flows = flows
        self.servers = servers
        self.path = [f.path for f in flows]
        net_topology = topology(self.num_servers, self.num_flows, self.path)
        self.predecessors = net_topology[0]
        self.successors = net_topology[1]
        self.flows_in_server = net_topology[2]
        self._depth = None
        self.arrival_shaping = arrival_shaping

    def __str__(self) -> str:
        return "Flows:\n%s\nServers:\n%s" % (
            list_to_str(self.flows),
            list_to_str(self.servers),
        )

    def __repr__(self) -> str:
        return "<Network:\n%s>" % self.__str__()

    def __eq__(self, other: Network):
        return (
            self.flows == other.flows
            and self.servers == other.servers
            and self.arrival_shaping == other.arrival_shaping
        )

    @property
    def is_feed_forward(self) -> bool:
        """
        Checks is the network in feed-forward, and the servers numbered in increasing order according to the
        topological sort of the network

        :return: True if the network is feed-forward, False otherwise


        >>> flows = [Flow([TokenBucket(2, 1)], [0, 1]), Flow([TokenBucket(3, 2)], [1, 0])]
        >>> servers = [Server([RateLatency(5, 1)], []), Server([RateLatency(6, 2)], [])]
        >>> network = Network(servers, flows)
        >>> network.is_feed_forward
        False
        >>> flows_ff = [Flow([TokenBucket(3, 4)], [0, 1, 3]), Flow([TokenBucket(1, 2)], [0, 2, 3])]
        >>> servers_ff = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...               Server([RateLatency(10, 3)], [TokenBucket(0, 10)]), Server([RateLatency(6, 0)], [])]
        >>> feed_forward = Network(servers_ff, flows_ff)
        >>> feed_forward.is_feed_forward
        True
        """
        for i in range(self.num_flows):
            for j in range(len(self.path[i]) - 1):
                if self.path[i][j] >= self.path[i][j + 1]:
                    return False
        return True

    def make_feed_forward(self) -> Network:
        """
        Transforms a network without cyclic dependencies into a feed-forward network with renumbered the nodes
        in the topological order.

        :return: the same network with good numbering. The order of the flows is unchanged.


        >>> flows_ff = [Flow([TokenBucket(3, 4)], [1, 0, 2]), Flow([TokenBucket(1, 2)], [1, 3, 2])]
        >>> servers_ff = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...               Server([RateLatency(10, 3)], [TokenBucket(0, 10)]), Server([RateLatency(6, 0)], [])]
        >>> feed_forward = Network(servers_ff, flows_ff)
        >>> feed_forward.make_feed_forward()
        <Network:
        Flows:
              0: α(t) = min [3 + 4t]; π = [0, 2, 3]
              1: α(t) = min [1 + 2t]; π = [0, 1, 3]
        Servers:
              0: β(t) = max [10(t - 3)_+]
                 σ(t) = min [0 + 10t]
              1: β(t) = max [6(t - 0)_+]
                 σ(t) = min []
              2: β(t) = max [8(t - 1)_+]
                 σ(t) = min []
              3: β(t) = max [10(t - 3)_+]
                 σ(t) = min [0 + 10t]>
        """
        if self.is_feed_forward:
            return self
        order = topological_sort(self.successors, self.num_servers)
        inverse_order = inverse_permutation(order)
        servers = [self.servers[order[i]] for i in range(self.num_servers)]
        flows = []
        for i in range(self.num_flows):
            path = [inverse_order[p] for p in self.path[i]]
            flows += [Flow(self.flows[i].arrival_curve, path)]
        arrival_shaping = []
        for (x, y, z) in self.arrival_shaping:
            arrival_shaping += [(inverse_order[x], y, z)]
        return Network(servers, flows, arrival_shaping)

    @property
    def is_tree(self) -> bool:
        """
        checks if the network is a rooted-forest, and the servers numbered in increasing number

        :return: True if the network is rooted-forest, False otherwise


        >>> flows_ff = [Flow([TokenBucket(3, 4)], [0, 1, 3]), Flow([TokenBucket(1, 2)], [0, 2, 3])]
        >>> servers_ff = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...               Server([RateLatency(10, 3)], [TokenBucket(0, 10)]), Server([RateLatency(6, 0)], [])]
        >>> feed_forward = Network(servers_ff, flows_ff)
        >>> feed_forward.is_tree
        False
        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.is_tree
        True
        """
        for i in range(self.num_servers):
            if len(self.successors[i]) > 1:
                return False
            if len(self.successors[i]) == 1 and self.successors[i][0] <= i:
                return False
        return True

    @property
    def is_elementary(self) -> bool:
        """
        checks if the network has only paths of length 1

        :return: True if the network has ony paths of length 1, False otherwise

        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.is_elementary
        False
        >>> flows = [Flow([TokenBucket(3, 4)], [0]), Flow([TokenBucket(1, 2)], [1]),
        ...          Flow([TokenBucket(2, 1)], [2]),Flow([TokenBucket(2, 1)], [2]), ]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> elementary = Network(servers, flows)
        >>> elementary.is_elementary
        True
        """
        for i in range(self.num_flows):
            if len(self.path[i]) > 1:
                return False
        return True

    @property
    def is_sink_tree(self) -> bool:
        """
        Checks if self is a sink-tree (a tree and all flows end at the last server)

        :return: True if self is a sink-tree, False otherwise


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.is_sink_tree
        False
        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> sink_tree = Network(servers, flows)
        >>> sink_tree.is_sink_tree
        True
        """
        if not self.is_tree:
            return False
        for f in self.flows:
            if not f.path[-1] == self.num_servers - 1:
                return False
        return True

    def is_sink(self, server) -> bool:
        """
        Checks if the server is a sink (has no successor)

        :param server: the server under consideration
        :return: True if it is a sink, False otherwise


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.is_sink(2)
        True
        >>> tandem.is_sink(0)
        False
        """
        return self.successors[server] == []

    @property
    def edges(self) -> defaultdict[Tuple[int, int]]:
        """
        Builds the dictionary of the edges of the networks. The keys are a pair in integers and the value is the set
        of flows crossing that edge.

        :return: The dictionary of the edges.


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.edges
        defaultdict(<class 'list'>, {(0, 1): [0, 1], (1, 2): [0, 2]})
        """
        # builds the set of edged and the flows crossed by each edge. Returns a defaultdict
        dict_edges = defaultdict(list)
        for i in range(self.num_flows):
            for h in range(len(self.path[i]) - 1):
                dict_edges[(self.path[i][h], self.path[i][h + 1])] += [i]
        return dict_edges

    @property
    def depth(self) -> List[int]:
        """
        Returns the depth of each server in a rooted-forest (the root of each tree is the unique sink
        of the connected component).
        Sinks have depth 0 and a node has the depth of its successor + 1

        :return: the list of depths for each server (List[int])


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.depth
        [2, 1, 0]
        """
        if self._depth is None:
            if self.is_tree:
                self._depth = server_depth(self.num_servers, self.successors)
        return self._depth

    @property
    def load(self) -> float:
        """
        Computes the load of the network: the minimum on all servers of the ratio between the sum of arrival rates
        of flows crossing this server and the service rate of the server.

        :return: the load / usage of the network


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.load == 5/6
        True
        """
        u = 0
        for j in range(self.num_servers):
            r = sum(
                [self.flows[i].arrival_curve[0].rho for i in self.flows_in_server[j]]
            )
            u = max(u, r / self.servers[j].service_curve[0].rate)
        return u

    @property
    def list_loads(self) -> List[float]:
        """
        Computes the load of the servers: the list of the ratio between the sum of arrival rates
        of flows crossing this server and the service rate of the server.

        :return: the list of the usage of all servers


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.list_loads == [0.75, 0.7, 5/6]
        True
        """
        u = []
        for j in range(self.num_servers):
            r = sum(
                [self.flows[i].arrival_curve[0].rho for i in self.flows_in_server[j]]
            )
            u += [r / self.servers[j].service_curve[0].rate]
        return u

    def residual_rate(self, foi: int) -> float:
        """
        Computes the residual rate of flow foi: the minimum on all the servers of its path of the difference
        between the service rate and the other flow's arrival rate

        :param foi: flow of interest
        :return: the residual rate


        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> tandem = Network(servers, flows)
        >>> tandem.residual_rate(0)
        5
        """
        res_rate = np.inf
        for j in self.path[foi]:
            res_server = self.servers[j].service_curve[0].rate
            res_cross = sum(
                [
                    self.flows[i].arrival_curve[0].rho
                    for i in self.flows_in_server[j]
                    if not i == foi
                ]
            )
            res_rate = min(res_rate, res_server - res_cross)
        return res_rate

    @property
    def residual_network(self) -> List[Server]:
        """ "
        Computes the residual service curves of all servers (to be used for lower priority flows for example)
        This method only applies to feed-forward networks

        :return: the list of residual service curves.


        >>> flows = [Flow([TokenBucket(3, 4)], [0]), Flow([TokenBucket(1, 2)], [1]),
        ...          Flow([TokenBucket(2, 1)], [2]),Flow([TokenBucket(2, 1)], [2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> elementary = Network(servers, flows)
        >>> elementary.residual_network
        [<Server: β(t) = max [4(t - 2.75)_+]
                 σ(t) = min []>
        , <Server: β(t) = max [8(t - 3.875)_+]
                 σ(t) = min [0 + 10t]>
        , <Server: β(t) = max [4(t - 1.0)_+]
                 σ(t) = min []>
        ]
        """
        if not self.is_elementary:
            raise Exception(
                "please decompose the network into elementary pieces before computing\
                            the residual network"
            )
        list_servers = []
        for j in range(self.num_servers):
            ac = tb_sum(
                [self.flows[i].arrival_curve[0] for i in self.flows_in_server[j]]
            )
            list_servers += [
                Server(
                    [residual_blind(self.servers[j].service_curve[0], ac)],
                    self.servers[j].max_service_curve,
                )
            ]
        return list_servers

    def sub_network(self, foi: int) -> (Network, int, List[int], List[int]):
        """
        Builds a sub-network with sink the last server crossed by the flow foi
        This methods applies only to well-numbered feed-forward networks

        :param foi: the flow of interest
        :return: the sub-network, the flow number of the foi in this new network, the list of the number
        of flows of the original network and the list of the number of servers of the original network.

        >>> flows = [Flow([TokenBucket(1, 1)], [3, 4]), Flow([TokenBucket(2, 2)], [0, 3]),
        ...          Flow([TokenBucket(3, 3)], [2, 4]), Flow([TokenBucket(4, 4)], [1, 3, 4])]
        >>> servers = [Server([RateLatency(10, 1)], []), Server([RateLatency(20, 2)], []),
        ...            Server([RateLatency(30, 3)], []), Server([RateLatency(40, 3)], []),
        ...            Server([RateLatency(50, 5)], [])]
        >>> arrival_shaping = [(3, [0], [TokenBucket(0, 10)]), (1, [3], [TokenBucket(0, 20)]),
        ...                    (2, [2], [TokenBucket(0, 30)]), (0, [1], [TokenBucket(0, 40)])]
        >>> tree = Network(servers, flows, arrival_shaping)
        >>> tree.sub_network(1)
        (<Network:
        Flows:
              0: α(t) = min [1 + 1t]; π = [2]
              1: α(t) = min [2 + 2t]; π = [0, 2]
              2: α(t) = min [4 + 4t]; π = [1, 2]
        Servers:
              0: β(t) = max [10(t - 1)_+]
                 σ(t) = min []
              1: β(t) = max [20(t - 2)_+]
                 σ(t) = min []
              2: β(t) = max [40(t - 3)_+]
                 σ(t) = min []>, 1, [0, 1, 3], [0, 1, 3])
        >>> tree.sub_network(1)[0].arrival_shaping
        [(2, [0], [0 + 10t]), (1, [2], [0 + 20t]), (0, [1], [0 + 40t])]
        """
        if not self.is_feed_forward:
            raise Exception("Network not feed-forward")
        list_servers = backward_search(self.path[foi][-1], self.predecessors)
        sub_path = trunc_path(self.path, list_servers)
        list_flows = [i for i in range(self.num_flows) if not sub_path[i] == []]
        ind_s = reindexing(list_servers)
        ind_f = reindexing(list_flows)
        servers = [self.servers[i] for i in list_servers]
        flows = [
            Flow(
                self.flows[i].arrival_curve,
                [ind_s[sub_path[i][j]] for j in range(len(sub_path[i]))],
            )
            for i in list_flows
        ]
        arrival_shaping = []
        for i in range(len(self.arrival_shaping)):
            x, y, z = self.arrival_shaping[i]
            if x in list_servers:
                arrival_shaping += [(ind_s[x], [ind_f[j] for j in y], z)]
        sub_net = Network(servers, flows, arrival_shaping)
        return sub_net, ind_f[foi], list_flows, list_servers

    def decomposition(
        self, keep_edges: List[(int, int)]
    ) -> (Network, List[int], List[(int, int)]):
        """
        Decomposition of the network by keeping edges in keep_edges, and cutting the flows.
        returns a new network with arrival curve[0] for all flows obtained from one flow
        returns list_first the list of the first path of the initial flows

        :param keep_edges: the edges to keep in the network
        :return: the new network, the list of the number of flows that are the start of the original flows,
        the list of edges removed in the network.

        >>> flows = [Flow([TokenBucket(1, 1)], [3, 4]), Flow([TokenBucket(2, 2)], [0, 3]),
        ...          Flow([TokenBucket(3, 3)], [2, 4]), Flow([TokenBucket(4, 4)], [1, 3, 4])]
        >>> servers = [Server([RateLatency(10, 1)], []), Server([RateLatency(20, 2)], []),
        ...            Server([RateLatency(30, 3)], []), Server([RateLatency(40, 3)], [TokenBucket(0, 40)]),
        ...            Server([RateLatency(50, 5)], [])]
        >>> arrival_shaping = [(0, [1], [TokenBucket(10, 0)])]
        >>> tree = Network(servers, flows, arrival_shaping)
        >>> tree.decomposition([(0, 3), (1, 3), (2, 4)])
        (<Network:
        Flows:
              0: α(t) = min [1 + 1t]; π = [3]
              1: α(t) = min [1 + 1t]; π = [4]
              2: α(t) = min [2 + 2t]; π = [0, 3]
              3: α(t) = min [3 + 3t]; π = [2, 4]
              4: α(t) = min [4 + 4t]; π = [1, 3]
              5: α(t) = min [4 + 4t]; π = [4]
        Servers:
              0: β(t) = max [10(t - 1)_+]
                 σ(t) = min []
              1: β(t) = max [20(t - 2)_+]
                 σ(t) = min []
              2: β(t) = max [30(t - 3)_+]
                 σ(t) = min []
              3: β(t) = max [40(t - 3)_+]
                 σ(t) = min [0 + 40t]
              4: β(t) = max [50(t - 5)_+]
                 σ(t) = min []>, [0, 2, 3, 4], dict_keys([(3, 4)]))
        >>> tree.decomposition([(0, 3), (1, 3), (2, 4)])[0].arrival_shaping
        [(0, [2], [10 + 0t]), (4, [1, 5], [0 + 40t])]
        """
        dict_removed_edges = defaultdict(list)
        flow_list = []
        path_list = []
        list_first = []
        pre = 0
        for flow in range(self.num_flows):
            i = 0
            path = self.path[flow]
            list_first += [pre]
            p = [path[i]]
            while i < len(path) - 1:
                if (path[i], path[i + 1]) in keep_edges:
                    p += [path[i + 1]]
                else:
                    pre += 1
                    path_list += [p]
                    flow_list += [
                        Flow(deepcopy([self.flows[flow].arrival_curve[0]]), p)
                    ]
                    p = [path[i + 1]]
                    dict_removed_edges[(path[i], path[i + 1])] += [pre]
                i += 1
            pre += 1
            flow_list += [Flow(deepcopy([self.flows[flow].arrival_curve[0]]), p)]
        arrival_shaping_bis = [
            (j, [list_first[i] for i in l], sc) for (j, l, sc) in self.arrival_shaping
        ]
        arrival_shaping_ter = [
            (j, dict_removed_edges[(i, j)], self.servers[i].max_service_curve)
            for (i, j) in dict_removed_edges.keys()
            if self.servers[i].max_service_curve
        ]
        return (
            Network(self.servers, flow_list, arrival_shaping_bis + arrival_shaping_ter),
            list_first,
            dict_removed_edges.keys(),
        )

    def unfold(self, foi: int) -> Tuple[Network, int]:
        """
        Unfolds a feed-forward network into a tree, from the last server visited by the flows of interest.
        This method can be aplied to any acyclic network (not necessarily well-numbered), and will not end if
        there are cycles.

        :param foi: flow of interest
        :return: the unfolded network and the new number of the flows of interest

        >>> flows = [Flow([TokenBucket(1, 1)], [2, 1, 0, 3]), Flow([TokenBucket(2, 2)], [1, 3])]
        >>> servers = [Server([RateLatency(10, 1)], []), Server([RateLatency(20, 2)], [TokenBucket(0, 20)]),
        ...            Server([RateLatency(30, 3)], []), Server([RateLatency(40, 3)], [])]
        >>> arrival_shaping = [(2, [0], [TokenBucket(0, 10)])]
        >>> tree = Network(servers, flows, arrival_shaping)
        >>> tree.unfold(0)
        (<Network:
        Flows:
              0: α(t) = min [1 + 1t]; π = [0, 2, 4, 5]
              1: α(t) = min [1 + 1t]; π = [1, 3]
              2: α(t) = min [2 + 2t]; π = [2]
              3: α(t) = min [2 + 2t]; π = [3, 5]
        Servers:
              0: β(t) = max [30(t - 3)_+]
                 σ(t) = min []
              1: β(t) = max [30(t - 3)_+]
                 σ(t) = min []
              2: β(t) = max [20(t - 2)_+]
                 σ(t) = min [0 + 20t]
              3: β(t) = max [20(t - 2)_+]
                 σ(t) = min [0 + 20t]
              4: β(t) = max [10(t - 1)_+]
                 σ(t) = min []
              5: β(t) = max [40(t - 3)_+]
                 σ(t) = min []>, 0)
        >>> tree.unfold(0)[0].arrival_shaping
        [(0, [0], [0 + 10t]), (1, [1], [0 + 10t])]
        """
        server = self.path[foi][-1]
        list_servers = [(server, -1)]
        dict_servers = defaultdict(list)
        dict_flows = defaultdict(list)
        for (k, (i, j)) in enumerate(list_servers):
            for h in self.predecessors[i]:
                list_servers += [(h, k)]
        list_servers.reverse()
        t = len(list_servers)
        list_servers = [(i, t - j - 1) for (i, j) in list_servers]
        for (k, (i, j)) in enumerate(list_servers):
            dict_servers[i] += [k]
        new_server_list = []
        f_ind = 0
        u_foi = -1
        for (i, (j, h)) in enumerate(list_servers):
            new_server_list += [self.servers[j]]
        new_flow_list = []
        for i in range(self.num_flows):
            for (k, (j, h)) in enumerate(list_servers):
                if j == self.path[i][0]:
                    dict_flows[k] += [(i, f_ind)]
                    pc = [k]
                    ind = 1
                    next_s = list_servers[k][1]
                    while (
                        ind < len(self.path[i])
                        and next_s < len(list_servers)
                        and self.path[i][ind] == list_servers[next_s][0]
                    ):
                        pc += [next_s]
                        ind += 1
                        next_s = list_servers[next_s][1]
                    if i == foi and ind == len(self.path[i]):
                        u_foi = f_ind
                    f_ind += 1
                    new_flow_list += [Flow(self.flows[i].arrival_curve, pc)]
        new_arrival_shaping = []
        for (j, lf, r) in self.arrival_shaping:
            for h in dict_servers[j]:
                lnf = [b for (a, b) in dict_flows[h] if a in lf]
                new_arrival_shaping += [(h, lnf, r)]
        return Network(new_server_list, new_flow_list, new_arrival_shaping), u_foi

    def aggregate_aux(self, flow_list: List[int], foi: int) -> List[Flow]:
        """
        Aggregates flows in flow_list, not being the foi having the same source and destination

        :param flow_list:  list of flows
        :param foi:  the flow of interest
        :return: the list of aggregated flows
        """
        dict_path = defaultdict(list)
        for i in flow_list:
            if not i == foi:
                dict_path[(self.path[i][0], self.path[i][-1])] += [i]
        new_flows = []
        for k in dict_path.keys():
            new_flows += [
                Flow(
                    [tb_sum([self.flows[i].arrival_curve[0] for i in dict_path[k]])],
                    self.path[dict_path[k][0]],
                )
            ]
        return new_flows

    def aggregate_network(self, foi: int) -> (Network, int):
        """
        Builds a new network where flows following the same path and having the same shaping / absence of shaping are
        aggretated together. The flow of interest is never aggregated to others.
        This method only applies to well-numbered trees

        :param foi: the flow of interest
        :return: the new network and the new number of the flow of interest

        >>> flows = [Flow([TokenBucket(3, 4)], [0, 1, 2]), Flow([TokenBucket(3, 4)], [0, 1, 2]),
        ...          Flow([TokenBucket(1, 2)], [0, 1]), Flow([TokenBucket(1, 2)], [0, 1]),
        ...          Flow([TokenBucket(2, 1)], [1, 2]), Flow([TokenBucket(2, 1)], [1, 2])]
        >>> servers = [Server([RateLatency(8, 1)], []), Server([RateLatency(10, 3)], [TokenBucket(0, 10)]),
        ...            Server([RateLatency(6, 0)], [])]
        >>> arrival_shaping = [(0, [0, 1, 2, 3], [TokenBucket(0, 20)]), (1, [4, 5], [TokenBucket(0, 5)])]
        >>> tandem = Network(servers, flows, arrival_shaping)
        >>> tandem.aggregate_network(0)
        (<Network:
        Flows:
              0: α(t) = min [3 + 4t]; π = [0, 1, 2]
              1: α(t) = min [3 + 4t]; π = [0, 1, 2]
              2: α(t) = min [2 + 4t]; π = [0, 1]
              3: α(t) = min [4 + 2t]; π = [1, 2]
        Servers:
              0: β(t) = max [8(t - 1)_+]
                 σ(t) = min []
              1: β(t) = max [10(t - 3)_+]
                 σ(t) = min [0 + 10t]
              2: β(t) = max [6(t - 0)_+]
                 σ(t) = min []>, 0)
        >>> tandem.aggregate_network(0)[0].arrival_shaping
        [(0, [0, 1, 2], [0 + 20t]), (1, [3], [0 + 5t])]
        """
        if not self.is_tree:
            raise Exception("method can only apply to trees")
        shaped_flows = sum([ash[1] for ash in self.arrival_shaping], [])
        unshaped_flows = [
            i for i in range(self.num_flows) if i not in shaped_flows and not i == foi
        ]
        new_flow_list = []
        new_arrival_shaping = []
        new_flow_list += [self.flows[foi]]
        new_foi = 0
        i = 1
        agg_list = self.aggregate_aux(unshaped_flows, foi)
        new_flow_list += agg_list
        i += len(agg_list)
        for (x, y, z) in self.arrival_shaping:
            agg_list = self.aggregate_aux(y, foi)
            new_flow_list += agg_list
            j = len(new_flow_list)
            if foi in y:
                new_arrival_shaping += [(x, [0] + [k for k in range(i, j)], z)]
            else:
                new_arrival_shaping += [(x, [k for k in range(i, j)], z)]
            i = j
        return Network(self.servers, new_flow_list, new_arrival_shaping), new_foi
