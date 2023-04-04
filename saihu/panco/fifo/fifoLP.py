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
import subprocess as sp
from typing import List

from panco.descriptor.network import Network
from panco.fifo.elpConstraints import ELPConstraints
from panco.fifo.plpConstraints import PLPConstraints
from panco.fifo.treeLP import TreeLP
from panco.fifo.tfaLP import TfaLP
from panco.fifo.sfaLP import SfaLP
from panco.lpSolvePath import LPSOLVEPATH


def edges_forest(network: Network):
    """
    Returns the list of edges of the network that forms a forest: for each node, keeps only the successor that has
    the smaller number among the successors with a larger number than this node.
    :param network: the network to decompose
    :return: the list of edges to keep
    """
    sf = np.zeros(network.num_servers, int)
    for i in range(network.num_servers):
        j = network.num_servers
        for k in network.successors[i]:
            if k > i:
                j = min(k, j)
        sf[i] = j
    return [(i, sf[i]) for i in range(network.num_servers) if not sf[i] == network.num_servers]


class FifoLP:
    def __init__(self, network: Network, list_edges=None, polynomial=True, sfa=False, tfa=False, filename="fifo.lp"):
        """
        Constructor for the class FifoLP, for the analysis of a network with the linear programming methods.
        The network is decomposed into a forest (self.forest)
        :param network: the network to analyze
        :param polynomial: True if the polynomial method, False for the more precise, but exponential method
        :param sfa: True for inclusion of sfa delay constraints (for polynomial only)
        :param tfa: True for inclusion of the tfa delay constraints (for olynimial method only)
        :param filename: name of the file to write the linear program
        """
        self.network = network
        self.polynomial = polynomial
        self.tfa = tfa
        self.tfa_delays = None
        if self.tfa:
            self.tfa_delays = TfaLP(network, filename="fifoLP_tfa.lp").delay_servers
            if network.num_servers > 0 and self.tfa_delays[0] == np.inf:
                self.tfa = False
        self.sfa = sfa
        self.sfa_delays = None
        if self.sfa:
            self.sfa_delays = SfaLP(network).all_delays
            if network.num_flows > 0 and self.sfa_delays[0] == np.inf:
                self.sfa = False
        self.filename = filename
        if list_edges:
            self.list_edges = list_edges
        else:
            self.list_edges = edges_forest(self.network)
        self.forest, self.list_first, z = self.network.decomposition(self.list_edges)

    def lp_constraint_flow(self, foi: int, file):  # foi flow of the decomposition
        """
        Writes the linear constraints for flow foi of the forest decomposition
        :param foi: flow of interest
        :param file: file where the constraints are written
        :return: None
        """
        net, new_foi, list_flows, list_severs = self.forest.sub_network(foi)
        if self.polynomial:
            if self.tfa_delays is not None:
                sub_tfa_delays = [self.tfa_delays[j] for j in list_severs]
            else:
                sub_tfa_delays = None
            lp = PLPConstraints(net, new_foi, foi + 1, list_flows, None, sub_tfa_delays)
        else:
            lp = ELPConstraints(net, new_foi, foi + 1, list_flows)
        lp.write_constraints(file)

    def lp_constraints(self, file):
        """
        Writes the constraints linear program in file
        :param file: the file where the linear program is written
        :return: None
        """
        file.write('max: ')
        for i in range(self.forest.num_flows):
            file.write('+ x{}'.format(i))
        file.write(';\n\n')
        i = 0
        f = 0
        while i < self.forest.num_flows:
            if i == self.list_first[f]:
                file.write('x{0} = {1};\n'.format(i, self.network.flows[f].arrival_curve[0].sigma))
            else:
                self.lp_constraint_flow(i - 1, file)
            i += 1
            if i in self.list_first:
                f += 1

    @property
    def lp_program(self) -> np.ndarray:
        """
        Writes the linear program and solves it to obtain the unknown burst where the flows have been cut
        :return: the list of bursts of flows in the forest
        """
        file = open(self.filename, 'w')
        self.lp_constraints(file)
        file.close()
        s = sp.run(LPSOLVEPATH + ["-S2", self.filename], stdout=sp.PIPE, encoding='utf-8').stdout
        tab_values = s.split('\n')[4:-1]
        values = [[token for token in line.split(' ') if not token == ""] for line in tab_values]
        tab_bursts = np.zeros(self.forest.num_flows)
        for [s1, s2] in values:
            if s1[0] == 'x':
                tab_bursts[int(float(s1[1:]))] = float(s2)
        return tab_bursts

    def update_sigma(self, f, sigma):
        if not sigma[f] == np.inf:
            return sigma
        sub_net, new_f, list_flows, list_servers = self.forest.sub_network(f - 1)
        for j in list_flows:
            if sigma[j] == np.inf:
                sigma = self.update_sigma(j, sigma)
        sigma[f] = TreeLP(sub_net, new_f, self.polynomial, self.sfa, self.tfa, self.filename).backlog
        self.forest.flows[f].arrival_curve[0].sigma = sigma[f]
        return sigma

    def ff_analysis(self):
        sigma = np.inf * np.ones(self.forest.num_flows)
        for i in range(self.network.num_flows):
            sigma[self.list_first[i]] = self.network.flows[i].arrival_curve[0].sigma
        i = 0
        for f in range(self.forest.num_flows):
            if i < self.network.num_flows and self.list_first[i] == f:
                i += 1
            else:
                self.update_sigma(f, sigma)
        return self.forest

    @property
    def ff_equiv(self) -> Network:
        """
        Construct the equivalent network by solving the fix-point equations. If the network has not been decomposed,
        then returns the original network
        :return: the equivalent network
        """
        if self.forest.num_flows == self.network.num_flows:
            return self.network
        if self.network.is_feed_forward:
            return self.ff_analysis()
        new_sigma = self.lp_program
        for i in range(self.forest.num_flows):
            if i not in self.list_first:
                self.forest.flows[i].arrival_curve[0].sigma = new_sigma[i]
        return self.forest

    @property
    def all_delays(self) -> List[float]:
        """
        Returns the delay bounds for all the flows
        :return: the list of delay bounds
        """
        ff = self.ff_equiv
        tab_delays = []
        i = 0
        d = 0
        while i < ff.num_flows:
            tree, foi, list_flows, list_servers = ff.sub_network(i)
            d += TreeLP(tree, foi, self.polynomial, self.sfa, self.tfa, "fifoLP_delay.lp").delay
            i += 1
            if i in self.list_first:
                tab_delays += [d]
                d = 0
        tab_delays += [d]
        return tab_delays

    def delay(self, foi: int) -> float:
        """
        Returns the delay bounds for flows foi
        :param foi: the flow of interest
        :return: the delay bound of foi
        """
        ff = self.ff_equiv
        i = self.list_first[foi]
        delay = 0
        while (foi < self.network.num_flows - 1 and i < self.list_first[foi + 1]) or \
              (foi == self.network.num_flows - 1 and i < ff.num_flows):
            tree, foi1, list_flows, list_servers = ff.sub_network(i)
            delay += TreeLP(tree, foi1, self.polynomial, self.sfa, self.tfa, filename="fifoLP_delay.lp").delay
            i += 1
        return delay
