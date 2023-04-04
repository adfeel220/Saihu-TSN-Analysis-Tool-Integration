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
from panco.descriptor.flow import Flow
from panco.descriptor.curves import TokenBucket
from panco.lpSolvePath import LPSOLVEPATH


class TfaLP:
    """
    The class TfaLP computes delay bounds using the TFA++ method, using a linear program. For feed-forward networks,
    does the same as [Mifdaoui, Leydier RTSS17], except that it makes no assumption on the maximum service rate.
    For cyclic networks, it computes the same as [Thomas, Le Boudec, Mifdaoui, RTSS 19], without this same assumption,
    and directly computes the fix-point, without iterating.
    However, this takes into account only the first token-bucket of the arrival curves
    :param network: the network to analyse.
    :param filename: name of the file to write the linear program
    """

    def __init__(self, network: Network, filename="tfa.lp"):
        self.network = network
        self.filename = filename

    def tfa_variables(self, file):
        """
        Writes the constraints of the fix-point variables (the burst transmitted for each flow to the next server)
        :param file: the file in which the constraints are written
        :return: None
        """
        file.write("\n /* sigma variables*/\n")
        for i in range(self.network.num_flows):
            for (l, j) in enumerate(self.network.path[i]):
                if j == self.network.path[i][0]:
                    file.write(
                        "x{0}s{1} = {2};\n".format(
                            i, j, self.network.flows[i].arrival_curve[0].sigma
                        )
                    )
                else:
                    file.write(
                        "x{0}s{1} <= x{0}s{2} + {3} d{2};\n".format(
                            i,
                            j,
                            self.network.path[i][l - 1],
                            self.network.flows[i].arrival_curve[0].rho,
                        )
                    )

    def tfa_constraints_server(self, file):
        """
        Writes the TFA constraints for each server
        :param file: the file where the constraints are written
        :return: None
        """
        for j in range(self.network.num_servers):
            file.write("\n /* server {0}*/\n".format(j))
            for i in self.network.flows_in_server[j]:
                tb = self.network.flows[i].arrival_curve[0]
                file.write(
                    "f{0}s{1}u{1} <= x{0}s{1} + {2} u{1};\n".format(i, j, tb.rho)
                )
            for h in self.network.predecessors[j]:
                for tb in self.network.servers[h].max_service_curve:
                    for i in self.network.edges[(h, j)]:
                        file.write("+ f{0}s{1}u{1}".format(i, j))
                    file.write("<= {0} + {1} u{2};\n".format(tb.sigma, tb.rho, j))
            file.write("0")
            for i in self.network.flows_in_server[j]:
                file.write("+ f{0}s{1}u{1}".format(i, j))
            file.write("= a{0}u{0};\n".format(j))
            for rl in self.network.servers[j].service_curve:
                file.write(
                    "b{0}t{0} >= {1} t{0} - {2};\n".format(
                        j, rl.rate, rl.rate * rl.latency
                    )
                )
            file.write("b{0}t{0} >= 0;\n".format(j))
            file.write("b{0}t{0} = a{0}u{0};\n".format(j))
            file.write("d{0} = t{0} - u{0};\n".format(j))
            file.write("d{0} >= 0;\n".format(j))

        for k in range(len(self.network.arrival_shaping)):
            j = self.network.arrival_shaping[k][0]
            max_service = self.network.arrival_shaping[k][2]
            for i in self.network.arrival_shaping[k][1]:
                if not j == self.network.path[i][0]:
                    print("error in shaping constraints", j, self.network.path[i][0])
                    return
            for tb in max_service:
                file.write("0")
                for i in self.network.arrival_shaping[k][1]:
                    file.write("+ f{0}s{1}u{1}".format(i, j))
                file.write("<= {0} + {1}u{2};\n".format(tb.sigma, tb.rho, j))

    @property
    def delay_servers(self) -> np.ndarray:
        """
        Computes the delay bounds of all the servers.
        :return: the list of the delays of the servers
        """
        file = open(self.filename, "w")
        file.write("max:")
        for i in range(self.network.num_servers):
            file.write("+ d{} ".format(i))
        file.write(";\n")
        self.tfa_constraints_server(file)
        self.tfa_variables(file)
        file.close()
        s = sp.run(
            LPSOLVEPATH + ["-S2", self.filename], stdout=sp.PIPE, encoding="utf-8"
        ).stdout
        tab_values = s.split("\n")[4:-1]
        values = [
            [token for token in line.split(" ") if not token == ""]
            for line in tab_values
        ]
        if not values:
            return self.network.num_servers * [np.inf]
        tab_delays = np.zeros(self.network.num_servers)
        for [s1, s2] in values:
            if s1[0] == "d":
                tab_delays[int(float(s1[1:]))] = float(s2)
        return tab_delays

    def delay(self, foi: int) -> float:
        """
        Returns the delay bound for flow foi
        :param foi: the flow of interest
        :return: the delay bound of foi
        """
        tab_delays = self.delay_servers
        return sum(tab_delays[j] for j in self.network.path[foi])

    @property
    def all_delays(self) -> List[float]:
        """
        Returns the delay bounds for all the flows
        :return: the list of delay bounds
        """
        tab_delays = self.delay_servers
        return [
            sum(tab_delays[i] for i in self.network.path[j])
            for j in range(self.network.num_flows)
        ]

    @property
    def ff_equiv(self) -> Network:
        """
        The equivalenet network decomposed into elementary servers
        :return:
        """
        delays = self.delay_servers
        flows = []
        for i in range(self.network.num_flows):
            d = 0
            arrival_curve = self.network.flows[i].arrival_curve[0]
            for j in self.network.flows[i].path:
                flows += [
                    Flow(
                        [
                            TokenBucket(
                                arrival_curve.sigma + d * arrival_curve.rho,
                                arrival_curve.rho,
                            )
                        ],
                        [j],
                    )
                ]
                d += delays[j]
        return Network(self.network.servers, flows)
