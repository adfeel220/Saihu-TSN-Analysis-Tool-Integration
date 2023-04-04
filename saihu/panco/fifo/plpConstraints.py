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


from panco.descriptor.network import Network


def times(num_servers, depth):
    t_min = num_servers * [0]
    t_max = num_servers * [0]
    t = 0
    for j in range(num_servers - 1, -1, -1):
        t_min[j] = t + 1
        t_max[j] = t + (depth[j] + 2)
        t = t_max[j]
    return t_min, t_max, t + 1


class PLPConstraints:
    # Linear analysis for fifo tree networks using only a quadratic number of time constraints
    def __init__(
        self,
        network: Network,
        foi,
        next_foi=None,
        list_flows=None,
        delays_flow=None,
        delays_server=None,
    ):
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
        self.delays_flow = delays_flow
        self.delays_server = delays_server

    def time_constraints(self, f):
        f.write("\n/* Time Constraints */\n")
        e = self.next_foi
        f.write("t1e{0} <= t0e{0};\n".format(e))
        f.write("t2e{0} <= t1e{0};\n".format(e))
        for j in range(self.network.num_servers - 1):
            h = self.network.successors[j][0]
            tj = self.t_min[j]
            th = self.t_min[h]
            for u in range(self.network.depth[j] + 1):
                f.write("t{0}e{2} <= t{1}e{2};\n".format(tj + u + 1, tj + u, e))
                f.write("t{0}e{2} <= t{1}e{2};\n".format(tj + u, th + u, e))

    def arrival_constraints(self, f):
        f.write("\n/* arrival constraints */\n")
        e = self.next_foi
        for i in range(self.network.num_flows):
            # path = self.network.flows[i].path
            if i == self.foi:
                arrival_curve = [self.network.flows[i].arrival_curve[0]]
            else:
                arrival_curve = self.network.flows[i].arrival_curve
            for tb in arrival_curve:
                j = self.network.path[i][0]
                for u in range(self.t_min[j], self.t_max[j]):
                    for v in range(u + 1, self.t_max[j] + 1):
                        f.write(
                            "f{0}s{1}t{2}e{6} - f{0}s{1}t{3}e{6} <= x{4} + {5} t{2}e{6} - {5} t{3}e{6};\n".format(
                                i, j, u, v, self.list_flows[i], tb.rho, e
                            )
                        )

    def arrival_shaping_constraints(self, f, b=False):
        f.write("\n/* arrival shaping constraints */\n")
        e = self.next_foi
        for k in range(len(self.network.arrival_shaping)):
            j = self.network.arrival_shaping[k][0]
            max_service = self.network.arrival_shaping[k][2]
            for i in self.network.arrival_shaping[k][1]:
                if not j == self.network.path[i][0]:
                    print("error in shaping constraints", j, self.network.path[i][0])
                    return
            for u in range(self.t_min[j], self.t_max[j]):
                for v in range(u + 1, self.t_max[j] + 1):
                    for tb in max_service:
                        f.write("0")
                        for i in self.network.arrival_shaping[k][1]:
                            if b or (not self.is_cyclic) or (not i == self.foi):
                                f.write(
                                    "+f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4}".format(
                                        i, j, u, v, e
                                    )
                                )
                        f.write(
                            "<= {0} + {1}t{2}e{4} - {1}t{3}e{4};\n".format(
                                tb.sigma, tb.rho, u, v, e
                            )
                        )

    def monotony_constraints(self, f):
        f.write("\n/* Monotony constraints */\n")
        e = self.next_foi
        for i in range(self.network.num_flows):
            for j in self.network.path[i]:
                for u in range(self.t_min[j], self.t_max[j]):
                    f.write(
                        "f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4} >= 0; \n".format(
                            i, j, u, u + 1, e
                        )
                    )

    def fifo_constraints(self, f):
        f.write("\n/* fifo constraints */\n")
        e = self.next_foi
        for i in range(self.network.num_flows):
            for j in self.network.path[i]:
                if j == self.network.num_servers - 1:
                    f.write(
                        "f{0}s{1}t{3}e{5}= f{0}s{2}t{4}e{5}; \n".format(
                            i, j, j + 1, 1, 0, e
                        )
                    )
                else:
                    h = self.network.successors[j][0]
                    for u in range(self.network.depth[j] + 1):
                        f.write(
                            "f{0}s{1}t{3}e{5} = f{0}s{2}t{4}e{5}; \n".format(
                                i, j, h, self.t_min[j] + u, self.t_min[h] + u, e
                            )
                        )

    def sfa_delay_constraints(self, f):
        f.write("\n/* SFA delay constraints */\n")
        e = self.next_foi
        d = self.delays_flow  # Sfa(self.network).delay()
        if d is None:
            return
        for i in range(self.network.num_flows):
            j = self.network.path[i][-1]
            h = self.network.path[i][0]
            if j == self.network.num_servers - 1:
                f.write(
                    "t{0}e{3} - t{1}e{3} <= {2};\n".format(0, self.t_min[h], d[i], e)
                )
            else:
                j = self.network.successors[j][0]
                for k in range(self.network.depth[j] + 2):
                    f.write(
                        "t{0}e{3} - t{1}e{3} <= {2};\n".format(
                            self.t_min[j] + k, self.t_min[h] + k, d[i], e
                        )
                    )

    def tfa_delay_constraints(self, f):
        f.write("\n/* TFA delay constraints */\n")
        e = self.next_foi
        # d, s = Tfa(self.network).analysispp()
        d = self.delays_server
        if d is None:
            return
        for j in range(self.network.num_servers):
            if j == self.network.num_servers - 1:
                f.write(
                    "t{0}e{3} - t{1}e{3} <= {2};\n".format(0, self.t_min[j], d[j], e)
                )
            else:
                h = self.network.successors[j][0]
                for k in range(self.network.depth[h] + 2):
                    f.write(
                        "t{0}e{3} - t{1}e{3} <= {2};\n".format(
                            self.t_min[h] + k, self.t_min[j] + k, d[j], e
                        )
                    )

    def shaping_constraints(self, f):
        f.write("\n/* Shaping constraints (e.g. maximum rate of a link)*/\n")
        e = self.next_foi
        for j in range(self.network.num_servers - 1):
            h = self.network.successors[j][0]
            for u in range(self.t_min[h], self.t_max[h]):
                for v in range(u + 1, self.t_max[h] + 1):
                    for tk in self.network.servers[j].max_service_curve:
                        f.write("0")
                        for i in self.network.edges[(j, h)]:  # flows_in_server[j]:
                            if not self.is_cyclic or not i == self.foi:
                                f.write(
                                    "+ f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4} ".format(
                                        i, h, u, v, e
                                    )
                                )
                        f.write(
                            "<= {4} + {0} t{1}e{3} - {0} t{2}e{3};\n".format(
                                tk.rho, u, v, e, tk.sigma
                            )
                        )

    def service_constraints(self, f):
        f.write("\n/* Service constraints */\n")
        e = self.next_foi
        for j in range(self.network.num_servers):
            u = self.t_max[j]
            if j == self.network.num_servers - 1:
                v = 0
                h = self.network.num_servers
            else:
                h = self.network.successors[j][0]
                v = self.t_max[h]
            for rl in self.network.servers[j].service_curve:
                for i in self.network.flows_in_server[j]:
                    f.write(
                        "f{0}s{1}t{2}e{5} - f{0}s{3}t{4}e{5} + ".format(
                            i, h, v, j, u, e
                        )
                    )
                f.write(
                    "{0} >= {1} t{2}e{5} - {3} t{4}e{5};\n".format(
                        rl.rate * rl.latency, rl.rate, v, rl.rate, u, e
                    )
                )
                for i in self.network.flows_in_server[j]:
                    f.write(
                        "f{0}s{1}t{2}e{5} - f{0}s{3}t{4}e{5} + ".format(
                            i, h, v, j, u, e
                        )
                    )
                f.write("0 >= 0;\n")

    def fix_point_constraints(self, file):
        file.write("\n/* the x burst constraints*/\n")
        # file.write('x{0} = {1};\n'.format(0, self.sigma[0]))
        # file.write('x{0} = {1};\n'.format(e[0], self.sigma[e[0]]))
        file.write(
            "x{4} = f{0}s{1}t0e{3} - f{0}s{2}t0e{3};\n".format(
                self.foi,
                self.network.path[self.foi][0],
                self.network.path[self.foi][-1] + 1,
                self.next_foi,
                self.next_foi,
            )
        )
        j = self.network.path[self.foi][0]
        for k in range(self.t_min[j], self.t_max[j] + 1):
            file.write(
                "f{0}s{1}t0e{5} - f{0}s{1}t{2}e{5} <= x{3} + {4}t0e{5} - {4}t{2}e{5};\n".format(
                    self.foi,
                    j,
                    k,
                    self.list_flows[self.foi],
                    self.network.flows[self.foi].arrival_curve[0].rho,
                    self.next_foi,
                )
            )

    def backlog_objective(self, file):
        if True:  # self.network.path[self.foi][-1] == self.network.num_servers - 1:
            file.write(
                "max: f{0}s{1}t0e0 - f{0}s{2}t0e0;\n".format(
                    self.foi,
                    self.network.flows[self.foi].path[0],
                    self.network.num_servers,
                )
            )
            j = self.network.path[self.foi][0]
            for k in range(self.t_min[j], self.t_max[j] + 1):
                file.write(
                    "f{0}s{1}t0e0 - f{0}s{1}t{2}e0 <= {3} + {4}t0e0 - {4}t{2}e0;\n".format(
                        self.foi,
                        j,
                        k,
                        self.network.flows[self.foi].arrival_curve[0].sigma,
                        self.network.flows[self.foi].arrival_curve[0].rho,
                    )
                )
        else:
            raise Exception("flow do not stop at last server\n")

    def backlog_set_objective(self, set_flows, file):
        for i in set_flows:
            if not self.network.path[self.foi][-1] == self.network.num_servers - 1:
                raise Exception("at least one flow do not stop at last server\n")
        file.write("max: ")
        for i in set_flows:
            file.write(
                "+ f{0}s{1}t0e0 - f{0}s{2}t0e0".format(
                    i, self.network.flows[i].path[0], self.network.num_servers
                )
            )
        file.write(";\n")
        for i in set_flows:
            j = self.network.path[i][0]
            for k in range(self.t_min[j], self.t_max[j] + 1):
                file.write(
                    "f{0}s{1}t0e0 - f{0}s{1}t{2}e0 <= {3} + {4}t0e0 - {4}t{2}e0;\n".format(
                        i,
                        j,
                        k,
                        self.network.flows[i].arrival_curve[0].sigma,
                        self.network.flows[i].arrival_curve[0].rho,
                    )
                )

    def aggregated_backlog_constraints(self, set_flows, file):
        file.write("\n/* Constraints at time t0 for the global backlog */\n")
        for i in set_flows:
            j = self.network.path[i][0]
            for k in range(self.t_min[j], self.t_max[j] + 1):
                file.write(
                    "f{0}s{1}t0e0 - f{0}s{1}t{2}e0 <= {3} + {4}t0e0 - {4}t{2}e0;\n".format(
                        i,
                        j,
                        k,
                        self.network.flows[i].arrival_curve[0].sigma,
                        self.network.flows[i].arrival_curve[0].rho,
                    )
                )

    def aggregated_arrival_constraints(self, set_flows, f):
        j = self.network.flows[set_flows[0]].path[0]
        f.write("\n/* aggregated arrival constraints */\n")
        e = self.next_foi
        rho = sum([self.network.flows[i].arrival_curve[0].rho for i in set_flows])
        for u in range(self.t_min[j], self.t_max[j]):
            for v in range(u + 1, self.t_max[j] + 1):
                for i in set_flows:
                    f.write(
                        "+ f{0}s{1}t{2}e{4} - f{0}s{1}t{3}e{4} ".format(i, j, u, v, e)
                    )
                f.write("<= y + {0} t{1}e{3} - {0} t{2}e{3};\n".format(rho, u, v, e))

    def tfa_delay_constraints_agg(self, f):
        f.write("\n/* TFA delay constraints */\n")
        e = self.next_foi
        # d, s = Tfa(self.network).analysispp()
        # d = self.delays_server
        # if d is None:
        #     return
        for j in range(self.network.num_servers):
            if j == self.network.num_servers - 1:
                f.write("t{0}e{3} - t{1}e{3} <= d{2};\n".format(0, self.t_min[j], j, e))
            else:
                h = self.network.successors[j][0]
                for k in range(self.network.depth[h] + 2):
                    f.write(
                        "t{0}e{3} - t{1}e{3} <= d{2};\n".format(
                            self.t_min[h] + k, self.t_min[j] + k, j, e
                        )
                    )

    # def delay_objective(self, foi, file):
    #     if self.path[foi][-1] == self.num_servers - 1:
    #         file.write('max: t0 - t{};\n'.format(self.t_min[self.path[foi][0]]))
    #     else:
    #         file.write('flow do not stop at last server\n')
    #
    # def backlog_objective(self, foi_set, file):
    #     file.write('max:')
    #     for foi in foi_set:
    #         if self.path[foi][-1] == self.num_servers - 1:
    #             file.write(' + f{0}s{1}t0 - f{0}s{2}t0'.format(foi, self.path[foi][0], self.path[foi][-1]))
    #         else:
    #             file.write('flow do not stop at last server\n')
    #     file.write(';\n')
    #     for foi in foi_set:
    #         j = self.path[foi][0]
    #         for k in range(self.t_min[j], self.t_max[j] + 1):
    #             file.write('f{0}s{1}t0 - f{0}s{1}t{2} <= {3} + {4}t0 - {4}t{2}'.format(foi,
    #                                                                                    j, k,
    #                                                                                    self.sigma[foi],
    #                                                                                    self.rho[foi]))
    #
    # def delay(self, foi, filename="LinearPrograms/fifo.lp"):
    #     file = open(filename, 'w')
    #     self.delay_objective(foi, file)
    #     self.time_constraints(file)
    #     self.arrival_constraints(file)
    #     self.fifo_constraints(file)
    #     self.service_constraints(file)
    #     self.monotony_constraints(file)
    #     self.shaping_constraints(file)
    #     # self.sfa_arrival_constraints(file)
    #     self.sfa_delay_constraints(file)
    #     self.tfa_delay_constraints(file)
    #     self.arrival_shaping_constraints(file)
    #     file.close()
    #     s = sp.run(["wsl", "lp_solve", "-presolve", "-S1", filename], stdout=sp.PIPE, encoding='utf-8').stdout
    #     return float(s.split()[-1])
    #
    # def backlog(self, foi, filename="LinearPrograms/fifo.lp"):
    #     file = open(filename, 'w')
    #     self.backlog_objective(foi, file)
    #     self.time_constraints(file)
    #     self.arrival_constraints(file)
    #     self.fifo_constraints(file)
    #     self.service_constraints(file)
    #     self.monotony_constraints(file)
    #     self.sfa_arrival_constraints(file)
    #     self.sfa_delay_constraints(file)
    #     file.close()
    #     s = sp.run(["wsl", "lp_solve", "-S1", filename], stdout=sp.PIPE, encoding='utf-8').stdout
    #     return float(s.split()[-1])
    #
    def write_constraints(self, file):
        file.write("\n/* flow {} */\n".format(self.list_flows[self.foi]))
        self.time_constraints(file)
        self.arrival_constraints(file)
        self.fifo_constraints(file)
        self.service_constraints(file)
        self.monotony_constraints(file)
        self.shaping_constraints(file)
        self.arrival_shaping_constraints(file)
        self.tfa_delay_constraints(file)
        self.sfa_delay_constraints(file)
        self.fix_point_constraints(file)
