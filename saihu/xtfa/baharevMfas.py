#!/usr/bin/python3
#
# This file is part of xTFA
# Copyright (c) 2021-2022 Ludovic Thomas (ISAE-SUPAERO)
# 
# This program is free software: you can redistribute it and/or modify  
# it under the terms of the GNU General Public License as published by  
# the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License 
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""
This module contains an implementation of the optimal MFAS solver from:
Baharev, Schichl and Neumaier. An exact method for the minimum feedback arc set problem

It relies on the module GurobiInterface, and on graphUtility
The former requires the gurobi solver
"""


import logging
from typing import Iterable, Tuple
import numpy as np
import networkx

from xtfa.fasUtility import FeedbackArcSetMethod
from xtfa.fasUtility import TopologicalSort
from xtfa import graphUtility
from xtfa import GurobiInterface

logger = logging.getLogger("BAHAREV")


# [1] : Baharev, Schichl and Neumaier. An exact method for the minimum feedback arc set problem

class BaharevMfas(FeedbackArcSetMethod):
    '''Class that propose an optimal feedback arc set, using Baharev optimal algorithm based on MILP and lazy constraints.
    '''

    def __init__(self, **kargs):
        '''Initialize the class.
            kargs arguments:
                "heuristique":  the heuristic used for (non-optimal) FAS computation. Default : EnforcedTopologicalSortArcSetProposal, linear
                "debug":        set to True to enable debug prints. Default : False         
        '''
        self.G = None                  
        self.heuristique = kargs.get("heuristique", TopologicalSort())
        self.edge_list = None
        self.cycle_list = None
        self.decision_variable = None
        self.feedback_arc_set = None
        self.A = None
        self.cost_lower_bound = None
        self.cost_upper_bound = None
        self.gurobi_debug = kargs.get("gurobi_debug", False)
        self.milp = kargs.get("milp_interface", GurobiInterface.GurobiInterface(debug=self.gurobi_debug))
        self.costs = None
        self.cost_tag = kargs.get("cost_tag", "cost")
        self.best_cost = None
    
    def set_heuristique(self, heuristique):
        '''Set the heuristic used to compute the non-optimal FAS during the resolution
        
        Arguments:
            heuristique {FeedbackArcSetPropositionInterface.FeedbackArcSetPropositionInterface} -- An implementation of FeedbackArcSetPropositionInterface, non optimal, fast
        '''
        self.heuristique = heuristique
    
    def get_fas(self, graph: networkx.DiGraph) -> Iterable[Tuple[str,str]]:
        '''Returns a feedback arc set. In this class, the result is an optimal FAS.
        
        Arguments:
            graph {networkx.DiGraph} -- A directed graph

        Returns:
            set -- A set of edges in the graph
        '''
        self.G = graph.copy()
        self.__createIndexedLists()
        logger.debug("Initialization")
        self.__initialization()
        iteration = 0
        while True:
            logger.debug("Iteration: %d. Cover Matrix Size: %r" % (iteration, self.A.shape))
            logger.debug("Waiting for MILP interface...")
            iteration += 1
            #Appel du milp pour obtenir la variable de décision à cette boucle
            decision_variable_this_loop = self.milp.solve(self.A,self.costs,self.decision_variable)
            logger.debug("MILP ok")
            #Obtention du cout
            cost_this_loop = sum(self.costs[j]*decision_variable_this_loop[j] for j in range(len(self.edge_list)))
            #Le cout est au moins supérieur à l'actuel car il reste probablement des cycles à casser, et qu'on a obtenu le cout min pour les cycles déjà connus.
            self.cost_lower_bound = cost_this_loop
            #Si les bornes sont égales, on a fini
            if(self.cost_lower_bound >= self.cost_upper_bound):
                break
            #On casse les edges depuis le graph initial (et non pas le précédent), on récupère GLoop
            GLoop = self.__break_edges(decision_variable_this_loop)
            #Si GLoop est acyclique, la decision variable de cette boucle est sol optimale, on a fini
            if(networkx.algorithms.dag.is_directed_acyclic_graph(GLoop)):
                self.decision_variable = decision_variable_this_loop
                break
            #Sinon, on récupère un nouvel Feedback Arc Set sur le graph réduit GLoop
            fasThisLoop = self.heuristique.get_fas(GLoop)
            #On en récupère une variable de décision
            decision_variable_this_loop = self.__get_decision_variable_from_set(fasThisLoop)
            cost_this_loop = sum(self.costs[j]*decision_variable_this_loop[j] for j in range(len(self.edge_list)))
            if(cost_this_loop < self.cost_upper_bound):
                self.cost_upper_bound = cost_this_loop
                self.decision_variable = decision_variable_this_loop
            #On étend la matrice
            self.__extend_matrix(fasThisLoop, GLoop)
        return self.__get_set_from_decision_variable(self.decision_variable)

            

    def __break_edges(self, decisionVariable):
        #Renvoie un graph dont les edges correspondant à decisionVariable ont été retirés
        newG = self.G.copy()
        for j in range(len(self.edge_list)):
            if decisionVariable[j]:
                edge = self.edge_list[j]
                if(edge in newG.edges):
                    newG.remove_edge(*edge)
        return newG

    def __initialization(self):
        # Compute a first feedback arc set using the heuristique
        self.feedback_arc_set = self.heuristique.get_fas(self.G)
        self.decision_variable = self.__get_decision_variable_from_set(self.feedback_arc_set)
        self.cost_lower_bound = 0
        self.cost_upper_bound = sum(self.costs[j]*self.decision_variable[j] for j in range(len(self.edge_list)))
        self.__extend_matrix(self.feedback_arc_set, self.G)

    def __createIndexedLists(self):
        #Create the indexed lists used to store the edges, the cycles and the solution and used to refer to them using indexes
        self.edge_list = list(self.G.edges)
        self.decision_variable = [0] * len(self.edge_list)
        self.cycle_list = list()
        self.A = np.empty([0,len(self.edge_list)], int)
        self.costs = [self.G.edges[edge].get(self.cost_tag,1) for edge in self.edge_list]
    
    def __get_decision_variable_from_set(self, feedback_arc_set):
        #Updates the decision variable based on the provided feedbackArcSet
        decision_variable = [0] * len(self.edge_list)
        for i in range(len(decision_variable)):
            decision_variable[i] = int(self.edge_list[i] in feedback_arc_set)
        return decision_variable

    def __get_set_from_decision_variable(self,decision_variable):
        fas = set()
        for j in range(len(self.edge_list)):
            if decision_variable[j]:
                fas.add(self.edge_list[j])
        return fas


    def __extend_matrix(self, fas, graph):
        #Algorith 2 of [1], extend the matrix (A) with the smallest cycles that are broken by the edges in the provided fas
        iDebug = 0
        nDebug = 0
        logger.debug("Extending the matrix...")
        iDebug = 0
        nDebug = len(fas)
        for edge in fas:
            iDebug += 1
            try:
                head = edge[1]
                tail = edge[0]
                path = graphUtility.shortestPath(graph,head,tail)
                path.append(head)
                simpleCycle = graphUtility.cycleListToSet(path)
                if(simpleCycle not in self.cycle_list):
                    self.cycle_list.append(simpleCycle)
                    row = self.__compute_matrix_row(simpleCycle)
                    self.A = np.append(self.A, np.array([row]), axis=0)

            except networkx.exception.NetworkXNoPath:
                pass
        logger.debug("Done")

    def __compute_matrix_row(self, cycleAsASet):
        matrixRow = [0] * len(self.edge_list)
        for i in range(len(matrixRow)):
            matrixRow[i] = int(self.edge_list[i] in cycleAsASet)
        return matrixRow





