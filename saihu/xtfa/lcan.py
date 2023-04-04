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
This modules contains the implementation of Low-Cost Acyclic Network (LCAN) with Per-Flow Regulators (PFRs) or Interleaved Regulators (IRs)
See my manuscript for more information
"""

import networkx as nx
from typing import List
import logging

from xtfa import inputPipelines, outputPipelines
from xtfa import networks, flows, nodes
from xtfa.baharevMfas import BaharevMfas


lg = logging.getLogger("LCAN")

def computeBurstDependencyGraph(n: networks.CyclicNetwork) -> nx.DiGraph:
    retG  = nx.DiGraph()
    for e in n.gif.edges:
        n1 = "%s/%s-in" % (e[0],e[1])   #burst vertex (we split it in two to transform the MFVS into a MFAS)
        n2 = "%s/%s-out" % (e[0],e[1])  #removing vertex n/m in the MFVS problem is equivalent to removing              
        retG.add_node(n1)               # the edge between (n/m-in) and (n/m-out), where the former has all the 
        retG.add_node(n2)               # incoming edges of (n/m) and the later has all the outgoing edges of (n/m)
        retG.add_edge(n1, n2, cost=1)   
        #We transform the singe vertex n/m  into two vertices, one that will contain all the input edges and one
        #that will contain all the output edges. 
        #Then removing node 'n/m' is equivalent to removing the edge between n1 and n2
    for f in n.flows:
        for e in f.graph.edges:
            b1 = "b-%s-%s" % (f.name, e[0])
            b2 = "b-%s-%s" % (f.name, e[1])
            nout = "%s/%s-out" % (e[0],e[1])    
            if(b1 not in retG.nodes.keys()):
                retG.add_node(b1)
            if(b2 not in retG.nodes.keys()):
                retG.add_node(b2)
            retG.add_edge(b1,b2, cost=1e9)      #propagation edge
            for mp in n.gif.successors(e[0]):
                nin = "%s/%s-in" % (e[0], mp)
                retG.add_edge(b1,nin,cost=1e9)  #contention edge
            retG.add_edge(nout,b2,cost=1e9)     #contention edge
    return retG            
            
            
    
    
    

def lcan_ir(n: networks.CyclicNetwork, **kargs):
    lg.debug("(IR) Computing burst dependency graph")
    g = computeBurstDependencyGraph(n)
    lg.debug("(IR) Launching MFAS search, it may take a while...")
    fas_solver = BaharevMfas()
    fas =  fas_solver.get_fas(g)
    lg.info("(IR) Found feedback-arc-set:")
    print("LCAN IR Positions: %s" % [e[0][:-3].split("/") for e in fas])
    lg.debug("(IR) Configuring IRs in network")
    for e in fas:
        e = e[0][:-3]
        e = e.split("/")
        listProcessedFlows: List[flows.Flow]
        listProcessedFlows = list()
        for f in n.flows:
            if(e in f.graph.edges):
                listProcessedFlows.append(f)
        mod = n.gif.nodes[e[1]]["model"]
        if(not isinstance(mod, nodes.Node)):
            raise AssertionError("Could not find model for node %s" % e[1])
        references = dict()
        for f in listProcessedFlows:
            ref = list(f.graph.predecessors(e[0]))[0]
            if(ref not in references.keys()):
                references[ref] = set()
            references[ref].add(f.name)
        myMapping = dict()
        for k in references.keys():
            myMapping[frozenset(references[k])]=k
            modk = n.gif.nodes[k]["model"]
            if(not isinstance(modk,nodes.Node)):
                raise AssertionError()
            modk.outputPipeline.appendPipelineElement(outputPipelines.FromKeyTaggingOutputPipelineStep(k))
        regPipelineStep = inputPipelines.RegulatorInputPipelineStep(e[1])
        regPipelineStep.groups = myMapping
        mod.inputPipeline.appendPipelineElement(regPipelineStep)
    pass


def lcan_pfr(n: networks.CyclicNetwork, **kargs):
    lg.debug("(PFR) Looking for feedback arc set")
    fas_solver = BaharevMfas()
    fas =  fas_solver.get_fas(n.gif)
    lg.info("(PFR) Found feedback-arc-set:")
    print("LCAN PFR Positions: %s" % fas)
    lg.debug("(PFR) Configuring PFRs in network")
    for e in fas:
        listProcessedFlows: List[flows.Flow]
        listProcessedFlows = list()
        for f in n.flows:
            if(e in f.graph.edges):
                listProcessedFlows.append(f)
        mod = n.gif.nodes[e[1]]["model"]
        if(not isinstance(mod, nodes.Node)):
            raise AssertionError("Could not find model for node %s" % e[1])
        myMapping = dict()
        for f in listProcessedFlows:
            #Regulator configured with source arrival curve
            myMapping[frozenset([f.name])] = "source"
        regPipelineStep = inputPipelines.RegulatorInputPipelineStep(e[1])
        regPipelineStep.groups = myMapping
        regPipelineStep.clockAdaptationMode = kargs.get("adaptation-method","none")
        mod.inputPipeline.appendPipelineElement(regPipelineStep)
    