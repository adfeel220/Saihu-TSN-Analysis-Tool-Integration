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
This modules contains utilitiy class for identifying a feedback arc set in a graph.
The basic interface is FeedbackArcSetMethod.

This module also containts TopologicalSort a linear, sub-optimal heuristic.
It can be useful for identifying the cuts for example for a fixed-point approach.

The other module baharevMfas contains an optimal implementation of FeedbackArcSetMethod (ie provides a *minimum* feedback arc set)
"""

from typing import Iterable, Tuple
import networkx

class FeedbackArcSetMethod:
    def get_fas(self, graph: networkx.DiGraph) -> Iterable[Tuple[str,str]]:
        """ Returns a feedback arc set for the provided graph. 
        In the graph, vertexes are strings, edges are tuples of strings, so we answer an iterable of tuples.

        Args:
            graph (networkx.DiGraph): the graph for which to find a Feedback Arc Set

        Returns:
            Iterable[Tuple[str,str]]: an iterable of edges, representing the feesback arc set for the graph
        """
        return NotImplemented


class TopologicalSort(FeedbackArcSetMethod):
    def get_fas(self, graph: networkx.DiGraph) -> Iterable[Tuple[str, str]]:
        fas = set()
        ordered_node_list = list(graph.nodes)
        #We use an arbitray ordering of the nodes
        for edge in graph.edges:
            start = edge[0]
            end = edge[1]
            start_index = ordered_node_list.index(start)
            end_index = ordered_node_list.index(end)
            if(start_index > end_index):
                #In our arbitrary ordering, start is after end, so the edge is 'backward', we put it in the FAS
                fas.add(edge)
        return fas
