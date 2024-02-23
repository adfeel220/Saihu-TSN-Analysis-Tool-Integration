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
This module contains all the class useful for defining a network, managing the TFA iteration one node after another etc.
"""

import threading
from typing import List, Optional, Tuple, Any, Mapping
import networkx
import xml.etree.ElementTree
import logging
import matplotlib.pyplot as plt

import xtfa.fasUtility

from xtfa.clocks import Clock
from xtfa import contentionPipelines
from xtfa import inputPipelines
from xtfa import minPlusToolbox as mpt
from xtfa.flows import AtsCurveNotKnown, CurveNotKnown, Flow, FlowState
from xtfa import nodes
from xtfa import unitUtility



loggercc = logging.getLogger("CYC")
loggerff = logging.getLogger("FFC")

class ProcessANode(threading.Thread):
    """
    This class is used to compute all the pipelines of a node.
    As a sub-class of Thread, we can spawn it, resulting in several nodes computed at the same time

    Inheritance:
        threading.Thread:

    """
    _net: 'FeedForwardNetwork'  #The network associated
    _nodeName: str              #The name of the node associated
    _node: nodes.Node           #The model of the associated node
    postpone: bool              #True if we need to postpone the computation of this node because not all inputs are known

    def __init__(self, net, nodeName: str) -> None:
        self._net = net
        self._nodeName = nodeName
        self._node = self._net.gif.nodes[self._nodeName]["model"]
        self.postpone = False
        super().__init__(name="Processing_%s" % nodeName)

    def prepareNode(self) -> None:
        """This method reports the flow states from the the network's gif (graph induced by flows) to the input of the node model
        """
        for edge in self._net.gif.in_edges(self._nodeName):
            for flow in self._net.gif.edges[edge].get("flow_states",list()):
                self._node.addIncomingFlowState(flow)

    def computeNode(self) -> None:
        self._node.processNode()

    def propagate(self) -> None:
        #clear all the edge lists in outgoing edge (to clear cuts assumptions in case of cyclic computations)
        for out in self._net.gif.out_edges(self._nodeName):
            if("flow_states" in self._net.gif.edges[out].keys()):
                self._net.gif.edges[out]["flow_states"].clear()
        #Retrive the list of flow states at the output of the previous node and write tham 
        outgoingFlowStates = self._node.getOutputFlowStates()
        for outFS in outgoingFlowStates:
            theFlow = outFS.flow
            for outgoingEdge in theFlow.graph.out_edges(self._nodeName):
                newFS = outFS.copy()
                newFS.atEdge = outgoingEdge
                #Change the clock if needed
                if("flow_states" not in self._net.gif.edges[outgoingEdge].keys()):
                    self._net.gif.edges[outgoingEdge]["flow_states"] = list()
                self._net.gif.edges[outgoingEdge]["flow_states"].append(newFS)
                if("flow_states" not in theFlow.graph.edges[outgoingEdge].keys()):
                    theFlow.graph.edges[outgoingEdge]["flow_states"] = list()
                theFlow.graph.edges[outgoingEdge]["flow_states"].append(newFS)
            if("flow_states" not in theFlow.graph.nodes[self._nodeName].keys()):
                theFlow.graph.nodes[self._nodeName]["flow_states"] = list()
            theFlow.graph.nodes[self._nodeName]["flow_states"].append(outFS.copy())
        for outEdge in self._net.gif.out_edges(self._nodeName):
            self._net.gif.edges[outEdge]["edge_ready"] = True

    def run(self) -> None:
        self.prepareNode()
        try:
            self.computeNode()
        except (CurveNotKnown):
            self.postpone = True
            self._node.clearComputations()
        except (AtsCurveNotKnown):
            self.postpone = True
            self._node.clearComputations()

class WopanetReader:
    """This is an utility class that reads the file format of wopanet
    """

    keysInWopanetXML = {
        "network": "network",
        "network_name": "name",
        "end_system": "station",
        "switch": "switch",
        "phy_node_name": "name",
        "link": "link",
        "link_from": "from",
        "link_to": "to",
        "link_name": "name",
        "flow": "flow",
        "flow_path": "target",
        "flow_path_step": "path",
        "flow_path_step_name": "node"
    }

    def __init__(self) -> None:
        self.overridingNetDict = dict()
        self.overridingNodeDict = dict()
        self.overridingLinkDict = dict()
        pass

    def populateNetworkName(self, net: 'FeedForwardNetwork', root: xml.etree.ElementTree.Element):
        netElements = root.findall(self.keysInWopanetXML["network"])
        if(len(netElements) != 1):
            raise xml.etree.ElementTree.ParseError("Too many network items in XML")
        theDict = dict(netElements[0].attrib, **self.overridingNetDict)
        net.name = theDict.pop(self.keysInWopanetXML["network_name"],"Network")
        net.netFlags = theDict

    def getOutportNameAndPropertiesFromPhy(self, phyGraph: networkx.Graph, phyNodeFrom, phyNodeTo) -> Tuple[str, dict]:
        phyLink = phyGraph.edges.get((phyNodeFrom, phyNodeTo))
        if not phyLink:
            raise xml.etree.ElementTree.ParseError("no physical link for %s - %s" %(phyNodeFrom, phyNodeTo))
        mFrom = None
        if phyNodeFrom == phyLink.get("from"):
            mFrom = "from"
        else:
            mFrom = "to"
        attributes = dict()
        attributes["phylink_name"] = phyLink.get("name")
        attributes["phynode_name"] = phyNodeFrom
        return phyNodeFrom + "-" + phyLink.get(mFrom + "Port"), attributes


    def populatePhyTopo(self, net: 'FeedForwardNetwork', root: xml.etree.ElementTree.Element):
        net.physicalTopo = networkx.Graph()
        #nodes
        for phyNodeElement in (root.findall(self.keysInWopanetXML["end_system"])):
            phyNodeUName = phyNodeElement.attrib.get(self.keysInWopanetXML["phy_node_name"])
            net.physicalTopo.add_node(phyNodeUName, **phyNodeElement.attrib, type=self.keysInWopanetXML["end_system"], **self.overridingNodeDict)
        for phyNodeElement in (root.findall(self.keysInWopanetXML["switch"])):
            phyNodeUName = phyNodeElement.attrib.get(self.keysInWopanetXML["phy_node_name"])
            net.physicalTopo.add_node(phyNodeUName, **phyNodeElement.attrib, type=self.keysInWopanetXML["switch"], **self.overridingNodeDict)
        #links
        for linkElement in root.findall(self.keysInWopanetXML["link"]):
            net.physicalTopo.add_edge(linkElement.attrib.get(self.keysInWopanetXML["link_from"]),linkElement.attrib.get(self.keysInWopanetXML["link_to"]), **linkElement.attrib, **self.overridingLinkDict)

    def populateFlows(self, net: 'FeedForwardNetwork', root: xml.etree.ElementTree.Element):
        net.flows = list()
        for flowElement in root.findall(self.keysInWopanetXML["flow"]):
            f = Flow.getFlowFromWopanetParams(**flowElement.attrib)
            net.flows.append(f)
            for flowPathElement in flowElement.findall(self.keysInWopanetXML["flow_path"]):
                phyNode = flowElement.attrib["source"]
                prevOutPortNode = ""
                for flowPathStepElement in flowPathElement.findall(self.keysInWopanetXML["flow_path_step"]):
                    nextPhyNode = flowPathStepElement.attrib.get(self.keysInWopanetXML["flow_path_step_name"])
                    outPortNodeName, outPortAttributes = self.getOutportNameAndPropertiesFromPhy(net.physicalTopo,phyNode,nextPhyNode)
                    f.graph.add_node(outPortNodeName, **outPortAttributes)
                    if(prevOutPortNode):
                        f.graph.add_edge(prevOutPortNode, outPortNodeName)
                    phyNode = nextPhyNode
                    prevOutPortNode = outPortNodeName
            #register all sources
            for n in f.graph.nodes.keys():
                if not list(f.graph.predecessors(n)):
                    #not has no predecessor, this is a source (in most cases, it is unique)
                    f.sources.append(n)
    
    def populateOdg(self, net: 'FeedForwardNetwork', root: xml.etree.ElementTree.Element):
        net.gif = networkx.DiGraph()
        for f in net.flows:
            net.gif = networkx.compose(net.gif, f.graph)
    
    def getPhyEdgeFromName(self, net: 'FeedForwardNetwork', edgeName: str) -> tuple:
        for edge in net.physicalTopo.edges.keys():
            if net.physicalTopo.edges[edge][self.keysInWopanetXML["link_name"]] == edgeName:
                return edge
        return (None,None)

    def setComputationnalFlags(self, net: 'FeedForwardNetwork', root: xml.etree.ElementTree.Element):
        for node in net.gif.nodes.keys():
            dic_link_level = net.physicalTopo.edges[self.getPhyEdgeFromName(net, net.gif.nodes[node]["phylink_name"])]
            dic_node_level = net.physicalTopo.nodes[net.gif.nodes[node]["phynode_name"]]
            dic_network_level = root.findall("network")[0].attrib

            newDic = dict(net.netFlags)
            newDic = dict(newDic, **dic_network_level)
            newDic = dict(newDic, **dic_node_level)
            newDic = dict(newDic, **dic_link_level)
            net.gif.nodes[node]["computational_flags"] = dict( (key,newDic[key]) for key in (newDic.keys()))
            
    def configure_network_from_xml(self, net: 'FeedForwardNetwork', xmlFileName: str):
        root = xml.etree.ElementTree.parse(xmlFileName).getroot()

        #Retrieve network name
        self.populateNetworkName(net, root)

        #Populating physical topology
        self.populatePhyTopo(net, root)

        #Populating all flows
        self.populateFlows(net, root)

        #Compute ODG
        self.populateOdg(net, root)

        #Set the node models
        self.setComputationnalFlags(net, root)
        return net

class NetworkInterface:
    """Minimum interface to be implemented by a network
    """
    def setPlotDelayComputations(self, plot: bool) -> None:
        raise NotImplementedError
    
    def auto_install_pipelines(self) -> None:
        raise NotImplementedError

    def setMultiThread(self, enabled: bool) -> None:
        raise NotImplementedError

    def setArrivalCurveForAllFlowsAtSource(self, curve: mpt.Curve) -> None:
        raise NotImplementedError

    def setServiceCurveForAllFifoContentionSteps(self, serviceCurve: mpt.Curve) -> None:
        """Sets the service curve of all the FIFO queing elements in the network (the FIFO contention step in the contention pipeline). This must be called AFTER the micromodels have been installed on the nodes

        Args:
            serviceCurve (mpt.Curve): the service curve to set

        Raises:
            NotImplementedError: in case the subclass does not override
        """
        raise NotImplementedError

    def setPacketSizeForAllFlows(self, maxPacketSize: int, minPacketSize: Optional[int]=0) -> None:
        raise NotImplementedError


    def setShapingCapacityForAllInputShapingSteps(self, shapingCapacity: float) -> None:
        raise NotImplementedError

    def setTransmissionSpeedForAllMohammadpourImprovementSteps(self, transmissionSpeed: float) -> None:
        raise NotImplementedError

    def setReferenceLinkSpeedForAllPacketizers(self, linkSpeed: float) -> None:
        raise NotImplementedError

    def printMinMaxDelayUpperBound(self) -> None:
        raise NotImplementedError

    def getOrderedDelayUpperBoundList(self) -> List[float]:
        """ Returns the list of the delay upper bound, ordered in increasing values

        Returns:
            List[float]: the list of increasing delay upperbounds
        """
        return NotImplemented
    
    def getOrderedDelayUpperBoundListWithDeadlines(self) -> Tuple[List[float],List[float]]:
        """ Returns the ordered list of delay bounds, together with the deadlines

        Returns:
            Tuple[List[float],List[float]]: first element of the tuple, a list of the delay upperbounds, in increasing order. second element: a list of the corresponding deadlines, for the flows in the same order as in the previous list: not necessarely in increasing order, for example if a flow has a small delay bound and a high deadline.
        """
        return NotImplemented

    def getDelayBoundFlowDestination(self, flowName: str, nodeName: str) -> float:
        return NotImplemented

    def getNodeUsage(self) -> Mapping[str,float]:
        return NotImplemented

    def compute(self, **kargs) -> None:
        raise NotImplementedError()

    def getWorstFlowDeadlineMargin(self) -> float:
        return NotImplemented
    
class FeedForwardNetwork(NetworkInterface):
    """This class represent a feed-forward FIFO network with the TFA method
    """
    name: str                       #Name of the network
    flows: List[Flow]               #List of the flows in the network (only one class)
    physicalTopo: networkx.Graph    #Graph representing the physical topology
    gif: networkx.DiGraph           #Graph induced by the flows, see Chapter 2 of the manuscript
    doMultithread: bool             #True if we want the mutlithread feature (all ready nodes ar computed in //)
    netFlags: dict                  #The network-level computational flags
    
    def __init__(self) -> None:
        super().__init__()
        self.doMultithread = False
        self.netFlags = dict()
        self.physicalTopo = networkx.Graph()
        self.gif = networkx.DiGraph()
        self.flows = list()

    def setArrivalCurveForAllFlowsAtSource(self, curve: mpt.Curve) -> None:
        """utility method that overwrites all the source arrival curve

        Args:
            curve (mpt.Curve): arrival curve to set to all flows
        """
        for flow in self.flows:
            flow.sourceArrivalCurve = curve

    def getFlowFromName(self, flowName: str) -> Optional[Flow]:
        """Obtain a Flow object from the flow name

        Args:
            flowName (str): name to look for

        Returns:
            Flow: the Flow whose name is the provided name
        """
        for f in self.flows:
            if (f.name == flowName):
                return f
        return None

    def countFlowName(self, flowName: str) -> int:
        """Count the number of flows that have the same name - Should never be more than 1

        Args:
            flowName (str): the name to look for

        Returns:
            int: the number of matching flows (should equal 1 at all times)
        """
        count = 0
        for f in self.flows:
            if(f.name == flowName):
                count += 1
        return count
    
    def setServiceCurveForAllFifoContentionSteps(self, serviceCurve: mpt.Curve) -> None:
        """Method to overwritte the service curve of all nodes

        Args:
            serviceCurve (mpt.Curve): the service curve to set
        """ 
        for node in self.gif.nodes:
            model = self.gif.nodes[node]["model"]
            for contentionStep in model.contentionPipeline._pipelineSteps:
                if(isinstance(contentionStep, contentionPipelines.FifoContentionStep)):
                    contentionStep.setServiceCurve(serviceCurve)

    def setPacketSizeForAllFlows(self, maxPacketSize: int, minPacketSize: Optional[int]=0) -> None:
        """Method to overwritte the packet sizes of all flows

        Args:
            maxPacketSize (int): max packet size to set
            minPacketSize (Optional[int], optional): min packet size to set. Defaults to 0.
        """
        for flow in self.flows:
            flow.maxPacketLength = maxPacketSize
            flow.minPacketLength = minPacketSize
    
    def setShapingCapacityForAllInputShapingSteps(self, shapingCapacity: float) -> None:
        """Method to overwritte the shaping capacity (ie transmission rate) of all nodes

        Args:
            shapingCapacity (float): the shaping capacity to set
        """
        commonCurve = mpt.LeakyBucket(shapingCapacity, 0)
        for node in self.gif.nodes:
            model = self.gif.nodes[node]["model"]
            for inputStep in model.inputPipeline.pipeline:
                if(isinstance(inputStep, inputPipelines.InputPortShapingInputPipelineStep)):
                    inputStep.overrideAllShapingCurvesForAlreadyConfiguredEdges(commonCurve)
                    
    
    def setTransmissionSpeedForAllMohammadpourImprovementSteps(self, transmissionSpeed: float) -> None:
        """Method to overwritte the tranmission rate for the Mohammadpour improvement in all nodes

        Args:
            transmissionSpeed (float): transmission rate to set
        """
        for node in self.gif.nodes:
            model = self.gif.nodes[node]["model"]
            for contentionStep in model.contentionPipeline._pipelineSteps:
                if(isinstance(contentionStep, contentionPipelines.MohammadpourEtAlImprovementStep)):
                    contentionStep.setOutputLinkSpeed(transmissionSpeed)
    
    def setReferenceLinkSpeedForAllPacketizers(self, linkSpeed: float) -> None:
        """Set the transmission rate for all packetizers in all nodes

        Args:
            linkSpeed (float): tranmission rate used by the packetizer model
        """
        for node in self.gif.nodes:
            model = self.gif.nodes[node]["model"]
            for inputStep in model.inputPipeline.pipeline:
                if(isinstance(inputStep, inputPipelines.PacketizationInputPipelineStep)):
                    for edge in inputStep.getEdgeListInLinkSpeedDictionnary():
                        inputStep.setLinkSpeedForIncommingEdge(edge, linkSpeed)

    def printFlowResults(self):
        """Prints the results for all flows
        """
        for flow in self.flows:
            print(">> Flow %s" % flow.name)
            for node in flow.graph.nodes:
                print(str(node) + " [", end='')
                for fs in flow.graph.nodes[node]["flow_states"]:
                    print(fs.toStringWithoutAt() + ",", end="")
                print("\b]")

    def setPlotDelayComputations(self, nodeList: List[str], **kargs) -> None:
        """ Plots the delay in all the nodes provided in the node list

        Args:
            nodeList (List[str]): list of nodes on which to plot the computation of the delay
        """
        if(nodeList):
            self.doMultithread = False
        for node in self.gif.nodes:
            if (node in nodeList) or ("all" in nodeList):
                self.gif.nodes[node]["computational_flags"]["plot-delay-computation"] = "True"
                self.gif.nodes[node]["computational_flags"]["plot-delay-computation-flags"] = kargs
            else:
                self.gif.nodes[node]["computational_flags"]["plot-delay-computation"] = "False"

    def setPlotPartitionResults(self, nodeList: List[str], **kargs) -> None:
        """ Enable the plot of the partitions (for debuging) on selected nodes

        Args:
            nodeList (List[str]): list of node on which to plot the partitions
        """
        if(nodeList):
            self.doMultithread = False
        for node in self.gif.nodes:
            if (node in nodeList) or ("all" in nodeList):
                self.gif.nodes[node]["computational_flags"]["plot-partition-result"] = "True"
                self.gif.nodes[node]["computational_flags"]["plot-partition-result-flags"] = kargs
            else:
                self.gif.nodes[node]["computational_flags"]["plot-partition-result"] = "False"

    def auto_install_pipelines(self):
        """Automatically install the computational models (ie computational pipelines) based on the computational flags
        """
        for nodeName in self.gif.nodes:
            n = nodes.Node(nodeName, self.name)
            self.gif.nodes[nodeName]["model"] = n
            n.autoInstallPipelines(self.gif.nodes[nodeName]["computational_flags"], self)

    def isNodeReadyForComputation(self, nodeName):
        if not self.gif.in_edges(nodeName):
            return True
        for edge in self.gif.in_edges(nodeName):
            if not self.gif.edges[edge].get("edge_ready", False):
                return False
        return True
    
    def readyNodesCount(self) -> int:
        c = 0
        for node in self.gif.nodes:
            if not (self.gif.nodes[node]["model"].isFinished()) and (self.isNodeReadyForComputation(node)):
                c += 1
        return c
    
    def remainingNodesCount(self) -> int:
        c = 0
        for node in self.gif.nodes:
            if not (self.gif.nodes[node]["model"].isFinished()):
                c += 1
        return c

    def getReadyNodes(self):
        l = list()
        for node in self.gif.nodes:
            if ((not (self.gif.nodes[node]["model"].isFinished())) and (self.isNodeReadyForComputation(node))):
                l.append(node)
        return l

    def feedForwardComputation(self):
        """Perform the TFA computation
        """
        while(self.remainingNodesCount() > 0):
            #print("[FFC] Iteration: %d. Remaining nodes: %d. Ready nodes: %d" % (feedForwardIteration, self.remainingNodesCount(), self.readyNodesCount()))
            readyNodes = self.getReadyNodes() 
            if(not readyNodes):
                raise AssertionError("No node ready")
            loggerff.info("%s:Remaining nodes:%d | Nodes ready:%d" % (self.name, self.remainingNodesCount(),len(readyNodes)))
            runningThreads = list()
            for node in readyNodes:
                newTh = ProcessANode(self, node)
                if(self.doMultithread):
                    newTh.start()
                else:
                    newTh.run()
                runningThreads.append(newTh)
            for th in runningThreads:
                if(self.doMultithread):
                    th.join()
                allRequirePostpone = False
                if(not th.postpone):
                    allRequirePostpone = False
                    th.propagate()
                if(allRequirePostpone):
                    raise AssertionError("All nodes require postponing their computation due to FRER/ATS curve not being known upstream. This can occur in a network with cyclic-dependencies and can be due to not having enough cuts in the topology. The following nodes are requesting postponement of their computation: %r" % list(tt._nodeName for tt in runningThreads))
    
    def compute(self, **kargs) -> None:
        return self.feedForwardComputation()
    
    def setMultiThread(self, enabled: bool) -> None:
        self.doMultithread = enabled

    def stringMinMaxDelayUpperBound(self) -> None:
        """ Returns min/max delay upper bounds across all flows
        """
        delayList = self.getOrderedDelayUpperBoundList()
        return("MinUpperBound=%.2e MaxUpperBound=%.2e" % (min(delayList), max(delayList)))

    def getOrderedDelayUpperBoundListOnePerFlow(self) -> List[float]:
        delayList = list()
        for flow in self.flows:
            delayList.append(max(flow.graph.nodes[node]["flow_states"][0].maxDelayFrom['source'] for node in flow.graph.nodes if (not flow.graph.out_degree(node))))
        delayList.sort()
        return delayList

    def getOrderedDelayUpperBoundListWithDeadlinesOnePerFlow(self) -> Tuple[List[float],List[float]]:
        delayList = list()
        deadlineList = list()
        for flow in self.flows:
            delayList.append(max(flow.graph.nodes[node]["flow_states"][0].maxDelayFrom['source'] for node in flow.graph.nodes if (not flow.graph.out_degree(node))))
            deadlineList.append(unitUtility.readTime(flow.properties.get("deadline",0)))
        deadlineList = [x for _,x in sorted(zip(delayList,deadlineList))] 
        delayList.sort()
        return (delayList, deadlineList)

    def getOrderedDelayUpperBoundList(self) -> List[float]:
        delayList = list()
        for flow in self.flows:
            for node in flow.graph.nodes:
                if not flow.graph.out_degree(node):
                    delayList.append(flow.graph.nodes[node]["flow_states"][0].maxDelayFrom['source'])
        delayList.sort()
        return delayList

    def getOrderedDelayUpperBoundListWithDeadlines(self) -> Tuple[List[float],List[float]]:
        delayList = list()
        deadlineList = list()
        for flow in self.flows:
            for node in flow.graph.nodes:
                if not flow.graph.out_degree(node):
                    delayList.append(flow.graph.nodes[node]["flow_states"][0].maxDelayFrom['source'])
                    deadlineList.append(unitUtility.readTime(flow.properties.get("deadline",0)))
        deadlineList = [x for _,x in sorted(zip(delayList,deadlineList))] 
        delayList.sort()
        return (delayList, deadlineList)

    def getRemotePhyNode(self, outputPort) -> Optional[str]:
        localNode, localPort = outputPort.rsplit("-", 1)
        for edge in self.physicalTopo.edges(localNode):
            if (self.physicalTopo.edges[edge]["from"] == localNode) and (self.physicalTopo.edges[edge]["fromPort"] == localPort):
                    return self.physicalTopo.edges[edge]["to"]
            if (self.physicalTopo.edges[edge]["to"] == localNode) and (self.physicalTopo.edges[edge]["toPort"] == localPort):
                    return self.physicalTopo.edges[edge]["from"]
        return None 

    def getServiceCurveIfAllSameForPhyNode(self, phyNode):
        candidateServiceCurve = None

        for outLink in self.physicalTopo.edges(phyNode):
            outPortIndex = (self.physicalTopo.edges[outLink]["fromPort"]) if (self.physicalTopo.edges[outLink]["from"] == phyNode) else (self.physicalTopo.edges[outLink]["toPort"])
            outPort = phyNode + "-" + outPortIndex
            outPortModel = self.gif.nodes[outPort]["model"]
            thisServiceCurve = self.getServiceCurveOnNodeIfExistsInModel(outPortModel)
            if(candidateServiceCurve == None):
                candidateServiceCurve = thisServiceCurve
            else:
                if(not candidateServiceCurve == thisServiceCurve):
                    return None
        return candidateServiceCurve
            
    def getServiceCurveOnNodeIfExistsInModel(self, node: nodes.Node):
        for el in node.contentionPipeline._pipelineSteps:
            if(isinstance(el, contentionPipelines.FifoContentionStep)):
                return el.getServiceCurveCopy()
        return None

    def drawPhyNetFromInternalCoordinates(self, **kargs):
        fig = plt.figure()
        a = plt.axes()
        if(kargs.get("usage", None)):
            mD = kargs.get("usage")
            for node in mD.keys():
                x,y = self.getDrawPositionOfPort(node, weight=0.7)
                plt.text(x, y, "%.1f%%" % (mD[node] * 100), color="r", horizontalalignment='center', verticalalignment='center')
        if(kargs.get("obtain_delay", None)):
            m = kargs.get("obtain_delay")
        mPos = {node: (float(self.physicalTopo.nodes[node]["x"]), float(self.physicalTopo.nodes[node]["y"])) for node in self.physicalTopo.nodes}
        networkx.draw_networkx(self.physicalTopo, with_labels=True, pos=mPos, ax=a)

    def drawFlowOnPhyUsingInternalCoordinates(self, flowNameToDraw: str, **kargs):
        head_size = kargs.get("head_size", 1)
        f = self.getFlowFromName(flowNameToDraw)
        for node in f.graph.nodes.keys():
            fromPhy = f.graph.nodes[node]["phynode_name"]
            toPhy = self.getRemotePhyNode(node)
            fromX, fromY = (float(self.physicalTopo.nodes[fromPhy][a]) for a in ['x','y'])
            toX, toY = (float(self.physicalTopo.nodes[toPhy][b]) for b in ['x','y'])
            plt.arrow(fromX, fromY, toX - fromX, toY - fromY, color='red', length_includes_head=True, head_width=(0.1*head_size), head_length=(0.2*head_size))

    def drawOdgUsingInternalCoordinates(self, **kargs):
        plt.figure()
        w = kargs.get("weight",0.8)
        mPos = {node: self.getDrawPositionOfPort(node, weight=w) for node in self.gif.nodes}
        networkx.draw(self.gif, with_labels=True, pos=mPos)
    
    def drawOdgOfOneFlowUsingInternalCoordinates(self, flowName: str, **kargs):
        plt.figure()
        w = kargs.get("weight",0.8)
        mPos = {node: self.getDrawPositionOfPort(node, weight=w) for node in self.gif.nodes}
        networkx.draw(self.gif, with_labels=True, pos=mPos, edgelist=self.getFlowFromName(flowName).graph.edges)


    def getDrawPositionOfPort(self, outPort: str, **kargs) -> Tuple[float, float]:
        weight = kargs.get("weight",0.8)
        phyNode = outPort.split("-")[0]
        remotePhyNode = self.getRemotePhyNode(outPort)
        x, y = (float(self.physicalTopo.nodes[phyNode][a]) for a in ["x", "y"])
        xRemote, yRemote = (float(self.physicalTopo.nodes[remotePhyNode][a]) for a in ["x", "y"])

        x = weight * x + (1 - weight) * xRemote
        y = weight * y + (1 - weight) * yRemote
        return (x, y)
    
    def getDelayBoundFlowDestination(self, flowName: str, nodeName: str) -> float:
        f = self.getFlowFromName(flowName)
        candidates = list()
        for node in self.gif.nodes.keys():
            if self.getRemotePhyNode(node) == nodeName:
                candidates.append(f.graph.nodes[node]["flow_states"][0].maxDelayFrom['source'])
        return max(candidates)
    
    def getDelayBoundFlowLeafVertex(self, flowName: str, nodeName: str) -> float:
        f = self.getFlowFromName(flowName)
        candidates = list()
        for node in self.gif.nodes.keys():
            if node == nodeName:
                candidates.append(f.graph.nodes[node]["flow_states"][0].maxDelayFrom['source'])
        return max(candidates)
    
    def getEteMaxBoundFlow(self, flowname: str) -> float:
        f = self.getFlowFromName(flowname)
        return max(max(f.graph.nodes[node]["flow_states"][i].maxDelayFrom['source'] for i in range(len(f.graph.nodes[node]["flow_states"]))) for node in f.graph.nodes)
        
    def getWorstEteDelay(self) -> float:
        tempF = self.flows[0]
        dmax = self.getEteMaxBoundFlow(tempF.name)
        for flow in self.flows:
            thisD = self.getEteMaxBoundFlow(flow.name)
            dmax = max(dmax, thisD)
        return dmax

    def getWorstFlowDeadlineMargin(self) -> float:
        tempF = self.flows[0]
        margin = (unitUtility.readTime(tempF.properties["deadline"]) - self.getEteMaxBoundFlow(tempF.name))
        for flow in self.flows:
            thisMargin = (unitUtility.readTime(flow.properties["deadline"]) - self.getEteMaxBoundFlow(flow.name))
            margin = min(margin, thisMargin)
        return margin
    
    def save_delay_bounds_per_destination_in_file(self, outfile: str, listOfFlows: List[str] = None):
        myList: List[Flow]
        if(listOfFlows):
            myList = [flow for flow in self.flows if flow.name in listOfFlows]
        else:
            myList = self.flows
        with open(outfile,'w') as f:
            f.write("Flow;Destination;Deadline;Bound\n")
            for flow in myList:
                for dest in flow.getListLeafVertices():
                    f.write("%s;%s;%f;%f\n" % (flow.name, dest, unitUtility.readTime(flow.properties.get("deadline",0)), self.getDelayBoundFlowLeafVertex(flow.name,dest)))

    def save_delay_bounds_per_node_in_file(self, outfile: str):
        with open(outfile,'w') as f:
            f.write("Node;Bound\n")
            for n in self.gif.nodes:
                f.write("%s;%f\n" % (n,self.gif.nodes[n]["model"].contentionDelayMax))
            

class CyclicNetwork(FeedForwardNetwork):
    """This represents a network with cyclic dependencies, it uses a fix point"""

    cuts: List[Tuple[str,str]]
    fasMethod: xtfa.fasUtility.FeedbackArcSetMethod
    _currentCutFlowStates: Mapping[Tuple[str,str], FlowState]
    logger: logging.Logger
    fixPointFailure: bool
    fixPointLimit : int
    matchDmax : bool

    def __init__(self, fasMethod) -> None:
        super().__init__()
        self.name = ""
        self.fasMethod = fasMethod
        self.fixPointFailure = False
        self.fixPointLimit = 100
        self.matchDmax = False

    def getOrderedDelayUpperBoundList(self) -> List[float]:
        if(self.fixPointFailure):
            return [0.0]
        else:
            return super().getOrderedDelayUpperBoundList()

    def _getFirstFlowStatesAtCuts(self) -> Mapping[Tuple[str,str],List[FlowState]]:
        myDict = dict()
        for edge in self.cuts:
            listFsForEdge = list()
            for flow in self.flows:
                if edge in flow.graph.edges.keys():
                    #Flow goes through the edge, create a flowstate from the initial arrival curve
                    theFs = FlowState(flow)
                    theFs.clock = Clock ("tai")
                    theFs.atEdge = edge
                    #The following could also be NoCurve, it should'nt change the results. #TODO to check
                    theFs.arrivalCurve = flow.sourceArrivalCurve
                    #For Packet Elimination computations, I need to have dictionnary that I can intersect with other flow states, so I'm going to create dictionnary with dummy values for at least the 'source' key
                    theFs.minDelayFrom['source'] = 0.0
                    theFs.maxDelayFrom['source'] = 0.0
                    theFs.rtoFrom['source'] = 0.0
                    listFsForEdge.append(theFs)
            myDict[edge] = listFsForEdge
        return myDict

    def _areCutSituationsIdentical(self, sitA: Mapping[Tuple[str,str], List[FlowState]], sitB: Mapping[Tuple[str,str], List[FlowState]]) -> bool:
        for edge in self.cuts:
            if(not self._areTheFlowStateIdentical(sitA.get(edge,list()), sitB.get(edge, list()))):
                return False
        return True

    def _areTheFlowStateIdentical(self, a: List[FlowState], b: List[FlowState]) -> bool:
        #They should have the same size (same number of flow states)
        if(len(a) != len(b)):
            return False
        #Then check that for each element in a, there exists an element of b that is the same flow state:
        for fs in a:
            found = False
            for ffs in b:
                if (fs.isEqualFlowByNameAllKeysMustMatch(ffs, match_d_max=self.matchDmax)):
                    found = True
            if(not found):
                return False
        #Then same in the other direction
        for fs in b:
            found = False
            for ffs in a:
                if(ffs.isEqualFlowByNameAllKeysMustMatch(fs, match_d_max=self.matchDmax)):
                    found = True
            if(not found):
                return False
        return True

    def _stringDeltaB(self, sitA: Mapping[Tuple[str,str], List[FlowState]], sitB: Mapping[Tuple[str,str], List[FlowState]]):
        m = 0.0
        for key in sitA.keys():
            sumA = sum(fs.arrivalCurve.get_burst() for fs in sitA[key])
            sumB = sum(fs.arrivalCurve.get_burst() for fs in sitB[key])
            diff = sumB - sumA
            if(diff > m):
                m = diff
        return("Max burst difference: %.2e" % m) 

    def _clearNetworkComputations(self):
        #Clean flow graph
        for flow in self.flows:
            for node in flow.graph.nodes:
                flow.graph.nodes[node].pop("flow_states", None)
            for edge in flow.graph.edges:
                flow.graph.edges[edge].pop("flow_states", None)
        #Clean odg
        for node in self.gif.nodes:
            self.gif.nodes[node]["model"].clearComputations()
        for edge in self.gif.edges:
            self.gif.edges[edge]["edge_ready"] = False
            self.gif.edges[edge]["flow_states"] = list()

    def _loadCurrentCutFlowStatesAssumptions(self):
        for edge in self._currentCutFlowStates.keys():
            if "flow_states" not in self.gif.edges[edge]:
                self.gif.edges[edge]["flow_states"] = list()
            self.gif.edges[edge]["edge_ready"] = True
            for oldFs in self._currentCutFlowStates[edge]:
                newFs = oldFs.copy()
                #also populate flow graph
                flow = newFs.flow
                #check we did not duplicate anything too much
                assert(flow in self.flows)
                #append to odg
                self.gif.edges[edge]["flow_states"].append(newFs)
                if("flow_states" not in flow.graph.edges[edge].keys()):
                    flow.graph.edges[edge]["flow_states"] = list()
                flow.graph.edges[edge]["flow_states"].append(newFs)
                # note that we do not populate the "flow_states" key in the vertex of the flow graph

    def _extractNewCutSituation(self) -> Mapping[Tuple[str,str], List[FlowState]]:
        newSituation = dict()
        for edge in self.cuts:
            listFs = list()
            for fs in self.gif.edges[edge]["flow_states"]:
                listFs.append(fs.copy())
            newSituation[edge] = listFs
        return newSituation

    def setFasMethod(self, aFasMethod: xtfa.fasUtility.FeedbackArcSetMethod) -> None:
        self.fasMethod = aFasMethod

    def getNodeUsage(self) -> Mapping[str,float]:
        retDic = dict()
        for node in self.gif.nodes:
            nodeModel = self.gif.nodes[node]["model"]
            if(isinstance(nodeModel, nodes.Node)):
                totalAc = nodeModel._aggregatedArrivalCurveAtContention
            if(isinstance(totalAc, mpt.NoCurve)):
                totalRate = 0.0
            if(isinstance(totalAc, mpt.LeakyBucket)):
                totalRate = totalAc.get_rate()
            if(isinstance(totalAc, mpt.GVBR)):
                totalRate = totalAc._getLastLb().get_rate()
            totalCapacity = unitUtility.readRate(self.gif.nodes[node]["computational_flags"]["transmission-capacity"])
            usage = totalRate / totalCapacity
            retDic[node] = usage
        result = dict(sorted(retDic.items(), key=lambda item: item[1]))
        return result

    def get_max_load(self) -> float:
        d = self.getNodeUsage()
        return max(d[node] for node in d.keys())

    def cyclicComputation(self, **kargs):
        # First, get the cuts from the FAS (Feedback Arc Set) method
        self.cuts = self.fasMethod.get_fas(self.gif)
        # Then get an initial value for the flow states at 
        self._previousCutFlowsStates = dict()
        self._currentCutFlowStates = self._getFirstFlowStatesAtCuts()
        i = 0
        while(not self._areCutSituationsIdentical(self._previousCutFlowsStates, self._currentCutFlowStates) or (i <1)):
            loggercc.info("%s:Iteration %d starting..." % (self.name,i))
            self._clearNetworkComputations()
            self._loadCurrentCutFlowStatesAssumptions()
            self.feedForwardComputation()
            loggercc.debug(self.stringMinMaxDelayUpperBound())
            self._previousCutFlowsStates = self._currentCutFlowStates
            self._currentCutFlowStates = self._extractNewCutSituation()
            loggercc.info(self._stringDeltaB(self._previousCutFlowsStates, self._currentCutFlowStates))
            if("plotter" in kargs.keys()):
                kargs["plotter"].plotCdf(label=str(i))
            loggercc.info("%s:Iteration %d finished." % (self.name,i))
            i += 1
            if(i > self.fixPointLimit):
                self.fixPointFailure = True
                return
    
    def compute(self, **kargs) -> None:
        return self.cyclicComputation(**kargs)
            