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
from panco.lpSolvePath import LPSOLVEPATH


class SfaLP:
    def __init__(self, network: Network, filename="sfa.lp"):
        """
        Class for computing the performances using the SFA method (linear model only, without shaping)
        in fifo networks, using a linear program to perform the operations. the value of theta is T + b_cross/R.
        :param network: The network to analyze
        :param filename: the name of the file where the lp program is written
        """
        self.network = network
        self.filename = filename
        self.forest, self.list_first, self.removed_edges = self.network.decomposition([])

    def sfa_variables(self, file):
        """
        Writes the constraints (on the bursts propagated at each server for each flow
        :param file: the file where the constraints are written
        :return: None
        """
        file.write('\n /* sigma variables*/\n')
        i = 0
        for f in range(self.forest.num_flows):
            if i < self.network.num_flows and f == self.list_first[i]:
                file.write('x{0} = {1};\n'.format(f, self.network.flows[i].arrival_curve[0].sigma))
                i += 1
            else:
                j = self.forest.flows[f - 1].path[0]
                file.write('x{0} = x{1} + '.format(f, f - 1))
                for k in self.forest.flows_in_server[j]:
                    if not k == f - 1:
                        file.write('+ {0} x{1}'.format(self.forest.flows[f].arrival_curve[0].rho /
                                                       self.network.servers[j].service_curve[0].rate, k))
                file.write('+ {0};\n'.format(self.forest.flows[f].arrival_curve[0].rho *
                                             self.network.servers[j].service_curve[0].latency))

    @property
    def ff_equiv(self) -> Network:
        """
        The equivalent network: all the arrival curves of the flows at each server
        :return: the equivalent network
        """
        file = open(self.filename, 'w')
        file.write('max:')
        for f in range(self.forest.num_flows):
            file.write('+ x{0} '.format(f))
        file.write(';\n')
        self.sfa_variables(file)
        file.close()
        s = sp.run(LPSOLVEPATH + ["-S2", self.filename], stdout=sp.PIPE, encoding='utf-8').stdout
        tab_values = s.split('\n')[4:-1]
        values = [[token for token in line.split(' ') if not token == ""] for line in tab_values]
        if not values:
            for f in range(self.forest.num_flows):
                self.forest.flows[f].arrival_curve[0].sigma = np.inf
        for [s1, s2] in values:
            if s1[0] == 'x':
                self.forest.flows[int(float(s1[1:]))].arrival_curve[0].sigma = float(s2)
        return self.forest

    @property
    def all_delays(self) -> List[float]:
        """
        Returns the delay bounds for all the flows
        :return: the list of delay bounds
        """
        ff_equiv_net = self.ff_equiv
        sum_sigma = [sum([ff_equiv_net.flows[i].arrival_curve[0].sigma for i in ff_equiv_net.flows_in_server[j]])
                     for j in range(self.network.num_servers)]
        sum_ar_rates = [sum([ff_equiv_net.flows[i].arrival_curve[0].rho for i in ff_equiv_net.flows_in_server[j]])
                        for j in range(self.network.num_servers)]
        d_list = []
        i = 0
        lat = 0
        s_rate = np.inf
        for f in range(ff_equiv_net.num_flows):
            if i + 1 < self.network.num_flows and f == self.list_first[i + 1]:
                d_list += [lat + self.network.flows[i].arrival_curve[0].sigma / s_rate]
                i += 1
                lat = 0
                s_rate = np.inf
            j = ff_equiv_net.flows[f].path[0]
            lat += self.network.servers[j].service_curve[0].latency + \
                   (sum_sigma[j] - ff_equiv_net.flows[f].arrival_curve[0].sigma) / \
                   self.network.servers[j].service_curve[0].rate
            s_rate = min(s_rate, self.network.servers[j].service_curve[0].rate - sum_ar_rates[j] +
                         self.network.flows[i].arrival_curve[0].rho)
        d_list += [lat + self.network.flows[i].arrival_curve[0].sigma / s_rate]
        return d_list

    def delay(self, foi):
        """
        Returns the delay bound for flow foi
        :param foi: the flow of interest
        :return: the delay bound of foi
        """
        return self.all_delays[foi]
