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
This module contains a set of utility methods for a graph.
"""

import networkx
import copy
import networkx.algorithms.shortest_paths.generic

def getCost(graph,feedBackArcSet, **kargs):
    '''Return the cost of a feedback arc set for the given graph
    
    Arguments:
        graph {networkx.DiGraph} -- A directed graph. Edges shall contain the attributes that define their cost.
        feedBackArcSet {set} -- A set of edges within the graph
    
    kargs arguments:
        'type' -- The type of cost to look for. Shall match one of the cost tag, see OutPortsDicoHolder. Default: OutPortsDicoHolder.turnDict_tag_absolute_cost
    
    Returns:
        float -- The cost of the set.
    '''
    tagOfCost = kargs.get("type","cost")
    cost = 0
    for edge in feedBackArcSet:
        cost += graph.edges[edge][tagOfCost]
    return cost

def cycleListToSet(cycleList):
    '''Transforms an elementary cycle expressed as a list of vertexes into an elementary cycle expressed as a set of edges.
    
    Arguments:
        cycleList {list} -- A list of vertexes that represent a cycle. The first and last element of the list shall be equal. The cycle shall be elementary
    
    Returns:
        set -- A set of edges that represent the elementary cycle.
    '''
    cycleSet = set()
    for i in range(len(cycleList)-1):
        cycleSet.add(tuple((cycleList[i], cycleList[i+1])))
    return cycleSet

def shortestPath(graph, root, target):
    return networkx.algorithms.shortest_paths.generic.shortest_path(graph,source=root,target=target)

def bfsSearch(graph, root, target):
    '''Search for the shortest path in graph from root to target, using BFS. Shortest path searches are implemented in networkx, but not using BFS. Some BFS functions are implemented in networkx, but none with the expected output.
    
    Arguments:
        graph {networkx.DiGraph} -- A directed graph
        root {node} -- A node in the graph
        target {node} -- A node in the graph
    
    Raises:
        BfsTargetNotFound -- If no path leads from root to target in the graph
    
    Returns:
        list -- ordered list of adjacent nodes in the graph from root (included) to target (included)
    '''
    #NOTE : On pourrait utiliset un dijkstra avec des poids 1 aussi (dans ce cas implémenté dans networkx)
    call_stack = list()
    call_stack.append(tuple((root, [root])))
    while (len(call_stack) > 0):
        (node, previous_stack) = call_stack.pop(0)
        for next_node in graph.neighbors(node):
            previous_stack_loop = copy.deepcopy(previous_stack)
            if(next_node == target):
                previous_stack_loop.append(next_node)
                return previous_stack_loop
            else:
                previous_stack_loop.append(next_node)
                call_stack.append(tuple((next_node, previous_stack_loop)))
    raise networkx.exception.NetworkXNoPath

class BfsTargetNotFound(Exception):
    pass