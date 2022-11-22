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
from panco.descriptor.network import Network


def times(num_servers, depth):
    t_min = num_servers * [0]
    t_max = num_servers * [0]
    t = 0
    for j in range(num_servers - 1, -1, -1):
        t_min[j] = t + 1
        t_max[j] = t + 2 ** (depth[j] + 1)
        t = t_max[j]
    return t_min, t_max, t + 1


class ELPConstraints:
    # Linear analysis for fifo tree networks
    def __init__(self, network: Network, foi, next_foi=None, list_flows=None):
        self.network = network
        dates = times(self.network.num_servers, self.network.depth)
        self.t_min = dates[0]
        self.t_max = dates[1]
        self.num_dates = dates[2]
        self.foi = foi
        if next_foi is None:
            self.next_foi = 0
        else:
            self.next_foi = next_foi
        if list_flows is None:
            self.list_flows = range(self.network.num_flows)
            self.is_cyclic = False
        else:
            self.list_flows = list_flows
            self.is_cyclic = True

    @property
    def matrix_order(self):
        mat = np.zeros((self.num_dates, self.num_dates))
        mat[1, 0] = 1
        mat[2, 0] = 1
        mat[2, 1] = 1
        for j in range(self.network.num_servers - 2, -1, -1):
            h = self.network.successors[j][0]
            for i in range(2 ** self.network.depth[j]):
                mat[self.t_min[j] + 2 * i, self.t_min[h] + i] = 1  # fifo
                mat[self.t_min[j] + 2 * i + 1, self.t_min[h] + i] = 1  # service
                mat[self.t_min[j] + 2 * i + 1, self.t_min[j] + 2 * i] = 1  # order
                for k in range(i + 1, 2 ** self.network.depth[j]):
                    if mat[self.t_min[h] + k, self.t_min[h] + i] == 1:
                        mat[self.t_min[j] + 2 * k, self.t_min[j] + 2 * i] = 1
                        mat[self.t_min[j] + 2 * k + 1, self.t_min[j] + 2 * i + 1] = 1
                        mat[self.t_min[j] + 2 * k + 1, self.t_min[j] + 2 * i] = 1
        return mat

    def time_constraints(self, file):
        file.write('\n/* Time Constraints */\n')
        e = self.next_foi
        mat = self.matrix_order
        k, n = mat.shape
        for i in range(k):
            for j in range(k):
                if mat[i, j] == 1:
                    file.write('t{0}e{2} <= t{1}e{2};\n'.format(i, j, e))

    def arrival_constraints(self, file):
        file.write('\n/* arrival constraints */\n')
        mat = self.matrix_order
        e = self.next_foi
        for i in range(self.network.num_flows):
            path = self.network.flows[i].path
            if i == self.foi:
                arrival_curve = [self.network.flows[i].arrival_curve[0]]
            else:
                arrival_curve = self.network.flows[i].arrival_curve
            for tb in arrival_curve:
                for k in range(self.t_min[path[0]], self.t_max[path[0]]):
                    for k1 in range(k + 1, self.t_max[path[0]] + 1):
                        if mat[k1, k] == 1:
                            file.write('f{0}s{1}t{2}e{6} - f{0}s{1}t{3}e{6} <= x{4} + {5} t{2}e{6} - {5} t{3}e{6};\n'.
                                       format(i, path[0], k, k1, self.list_flows[i],
                                              # self.sigma[i],
                                              tb.rho, e))

    def monotony_constraints(self, file):
        file.write('\n/* Monotony constraints */\n')
        mat = self.matrix_order
        e = self.next_foi
        for i in range(self.network.num_flows):
            for j in self.network.path[i]:
                for k in range(self.t_min[j], self.t_max[j]):
                    for h in range(k + 1, self.t_max[j] + 1):
                        if mat[h, k] == 1:
                            file.write('f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4} >= 0; \n'.format(i, j, k, h, e))

    def fifo_constraints(self, file):
        file.write('\n/* fifo constraints */\n')
        e = self.next_foi
        for i in range(self.network.num_flows):
            for j in self.network.path[i]:
                if j == self.network.num_servers - 1:
                    file.write('f{0}s{1}t{2}e{6} = f{3}s{4}t{5}e{6};\n'.format(i, j + 1, 0,
                                                                               i, j, 1, e))
                else:
                    h = self.network.successors[j][0]
                    for k in range(2 ** self.network.depth[j]):
                        file.write('f{0}s{1}t{2}e{6} = f{3}s{4}t{5}e{6};\n'.format(i, h, self.t_min[h] + k,
                                                                                   i, j, self.t_min[j] + 2 * k, e))

    def shaping_constraints(self, file):
        file.write('\n/* Maximum service / shaping constraints (maximum rate of the link)*/\n')
        e = self.next_foi
        for j in range(self.network.num_servers - 1):
            h = self.network.successors[j][0]
            for u in range(self.t_min[h], self.t_max[h]):
                for v in range(u + 1, self.t_max[h] + 1):
                    mat = self.matrix_order
                    if mat[v, u] == 1:
                        for tk in self.network.servers[j].max_service_curve:
                            file.write('0')
                            for i in self.network.flows_in_server[j]:
                                if not self.is_cyclic or not i == self.foi:
                                    file.write('+ f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4}'.format(i, h, u, v, e))
                            file.write('<= {4} + {0} t{1}e{3} - {0} t{2}e{3};\n'.format(tk.rho, u, v, e, tk.sigma))

    def arrival_shaping_constraints(self, f, b=False):
        f.write('\n/* arrival shaping constraints */\n')
        mat = self.matrix_order
        e = self.next_foi
        for k in range(len(self.network.arrival_shaping)):
            j = self.network.arrival_shaping[k][0]
            max_service = self.network.arrival_shaping[k][2]
            for i in self.network.arrival_shaping[k][1]:
                if not j == self.network.path[i][0]:
                    print('error in shaping constraints', j, self.network.path[i][0])
                    return
            for u in range(self.t_min[j], self.t_max[j]):
                for v in range(u + 1, self.t_max[j] + 1):
                    if mat[v, u] == 1:
                        for tb in max_service:
                            f.write('0')
                            for i in self.network.arrival_shaping[k][1]:
                                if not (self.is_cyclic or b) or not i == self.foi:
                                    f.write('+f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4}'.format(i, j, u, v, e))
                            f.write('<= {0} + {1}t{2}e{4} - {1}t{3}e{4};\n'.format(tb.sigma, tb.rho, u, v, e))

    def service_constraints(self, file):
        file.write('\n/* Service constraints */\n')
        e = self.next_foi
        for j in range(self.network.num_servers):
            if j == self.network.num_servers - 1:
                for rl in self.network.servers[j].service_curve:
                    for i in self.network.flows_in_server[j]:
                        file.write('f{0}s{1}t{2}e{6} - f{3}s{4}t{5}e{6} + '.format(i, j + 1, 0,
                                                                                   i, j, 2, e))
                    file.write('{0} >= {1} t{2}e{5} - {3} t{4}e{5};\n'.format(rl.rate * rl.latency,
                                                                              rl.rate, 0,
                                                                              rl.rate, 2, e))
            else:
                for rl in self.network.servers[j].service_curve:
                    h = self.network.successors[j][0]
                    for k in range(2 ** self.network.depth[j]):
                        for i in self.network.flows_in_server[j]:
                            file.write('f{0}s{1}t{2}e{6} - f{3}s{4}t{5}e{6} + '.format(i, h, self.t_min[h] + k,
                                                                                       i, j, self.t_min[j] + 2 * k + 1,
                                                                                       e))
                        file.write('{0} >= {1} t{2}e{5} - {3} t{4}e{5};\n'.format(rl.rate * rl.latency,
                                                                                  rl.rate, self.t_min[h] + k,
                                                                                  rl.rate, self.t_min[j] + 2 * k + 1,
                                                                                  e))

    def fix_point_constraints(self, file):
        file.write('\n/* the x burst constraints*/\n')
        file.write('x{4} = f{0}s{1}t0e{3} - f{0}s{2}t0e{3};\n'.
                   format(self.foi, self.network.path[self.foi][0],
                          self.network.path[self.foi][-1] + 1, self.next_foi, self.next_foi))
        j = self.network.path[self.foi][0]
        for k in range(self.t_min[j], self.t_max[j] + 1):
            file.write('f{0}s{1}t0e{5} - f{0}s{1}t{2}e{5} <= x{3} + {4}t0e{5} - {4}t{2}e{5};\n'.
                       format(self.foi, j, k, self.list_flows[self.foi],
                              self.network.flows[self.foi].arrival_curve[0].rho, self.next_foi))

    def sfa_delay_constraints(self, f):
        pass

    def tfa_delay_constraints(self, f):
        pass

    def service_constraints_lower_bound(self, f):
        pass

    def backlog_objective(self, file):
        if self.network.path[self.foi][-1] == self.network.num_servers - 1:
            file.write(
                'max: f{0}s{1}t0e0 - f{0}s{2}t0e0;\n'.format(self.foi, self.network.flows[self.foi].path[0],
                                                             self.network.num_servers))
            j = self.network.path[self.foi][0]
            for k in range(self.t_min[j], self.t_max[j] + 1):
                file.write('f{0}s{1}t0e0 - f{0}s{1}t{2}e0 <= {3} + {4}t0e0 - {4}t{2}e0;\n'.
                           format(self.foi, j, k, self.network.flows[self.foi].arrival_curve[0].sigma,
                                  self.network.flows[self.foi].arrival_curve[0].rho))
        else:
            raise Exception('flow do not stop at last server\n')

    def write_constraints(self, file):
        file.write('\n/* flow {} */\n'.format(self.list_flows[self.foi]))
        self.time_constraints(file)
        self.arrival_constraints(file)
        self.fifo_constraints(file)
        self.service_constraints(file)
        self.monotony_constraints(file)
        self.shaping_constraints(file)
        self.arrival_shaping_constraints(file)
        self.fix_point_constraints(file)
