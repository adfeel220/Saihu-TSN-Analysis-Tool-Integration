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
This module contains the definition of the ACP (Aggregate Computational Pipeline)
In the software, the aggregate computational pipeline is called the "input pipeline" (legacy name)

The file is split in three parts:
-First, the objects for managing FlowState partitions are defined
-Then all the possible computational blocks inside the pipeline are defined
-Last the ACP itself is defined.
"""

import copy
import logging
from typing import List, Mapping, Set, Tuple, FrozenSet, Optional
import re
import networkx
from xtfa import minPlusToolbox as mpt
from xtfa.clocks import Clock
from xtfa.flows import FlowState, Flow, CurveNotKnown
from xtfa import unitUtility



# IP stands for input pipeline
logger = logging.getLogger("IP")


######### PART 1: Definition of the FlowState partitions ###########

class FlowsPartitionElement:
    """This class represents an element in the partition of the flow states. 
    It references a list of flows, the group of which being shaped by the aggregateShaping curve

        Attributes:
            flows:  the list of the flow states that belong to this partition element
            aggregateShaping:   the Curve that shapes the aggregate in this partition element. 
    """
    flows: List[FlowState]
    aggregateShaping: mpt.Curve
    flags: Mapping

    def __init__(self) -> None:
        """ Creates a FlowsPartitionElement with an empty list and a 'None' aggregateShaping
        """
        super().__init__()
        self.flows = list()
        self.aggregateShaping = None
        self.flags = dict()

    def copy(self) -> 'FlowsPartitionElement':
        """Returns a (simple, non-deep) copy of this element. The copy is made of a copied list of the same references to the flow states and a deep copy of the shapingCurve

        Returns:
            FlowsPartitionElement: the copy
        """
        newElement = FlowsPartitionElement()
        #copy list but do not copy FlowStates themselves
        newElement.flows = list(self.flows)
        #but deep copy the shaping curve
        newElement.aggregateShaping = copy.deepcopy(self.aggregateShaping)
        return newElement

    def copyWithFlowStates(self, fsl: List[FlowState]) -> 'FlowsPartitionElement':
        newElement = FlowsPartitionElement()
        newElement.flows = list()
        for fs in self.flows:
            for ffs in fsl:
                if(fs.isEqualFlowByNameAllKeysMustMatch(ffs)):
                    newElement.flows.append(ffs)
        newElement.aggregateShaping = copy.deepcopy(self.aggregateShaping)
        return newElement

    def getMaxPacketLengthInPartitionElement(self) -> int:
        """Returns the max packet length in the aggregate of this paritition element

        Returns:
            int: the maximum packet length among the flows associated with all the flow states in this partition element
        """
        return max(f.flow.maxPacketLength for f in self.flows)

    def getResultingArrivalCurve(self) -> mpt.Curve:
        """Returns the resulting arrival curve for the aggregate of the current partition element.
        That is: alpha_shaping * (sum_f (alpha_f)), or again: the sum of the individual arrival curves, then shaped by the shaping curve.
        If the shaping curve is 'None', then only the sum is performed (no shaping)

        Returns:
            minPlusToolbox.Curve: the resulting arrival curve for this partition element
        """
        sumIndividuals = mpt.NoCurve()
        for fs in self.flows:
            sumIndividuals = sumIndividuals + fs.getCopyInternalArrivalCurve()
        if(not self.aggregateShaping):
            return sumIndividuals
        return (self.aggregateShaping * sumIndividuals)
    
class FlowsPartition:
    """This class represents a partition of the flow states into partition elements

        Attributes:
            partitionElements: list of FlowsPartitionElement
    """

    partitionElements: List[FlowsPartitionElement]
    name: str

    def __init__(self) -> None:
        """ Creates a FlowsPartition with an empty list of partitionElements
        """
        super().__init__()
        self.partitionElements = list()
        self.name = "Partition"
    
    def createPartitionElement(self) -> Optional[FlowsPartitionElement]:
        """Creates a FlowsParitionElement and ADDS it to the current partition

        Returns:
            FlowsPartitionElement: the newly created element, whose reference has been ALREADY ADDED to the current partition
        """
        el = FlowsPartitionElement()
        self.partitionElements.append(el)
        return el
    
    def countElementsContainingFlowState(self, flowState: FlowState) -> int:
        """ Counts the number of partition elements in the current partition that contains a reference to this flow state. NB: equality is done at reference-level, the content of the fields in flowState is NOT checked

        Args:
            flowState (flows.FlowState): the FlowState to search for

        Returns:
            int: the number of partition elements that contain this FlowState (a reference to it)
        """
        count = 0
        for el in self.partitionElements:
            if (flowState in el.flows):
                count += 1
        return count

    def removeFlowStateFromPartition(self, fs: FlowState) -> None:
        """Removes a FlowState fs from the partition. If fs was in a partition elements with other flows, then fs is removed from the partition element. If fs was alone in a partition element, then this partition element is removed from the current partition. If fs was not in any partition element, then nothing is performed. 

        Args:
            fs (flows.FlowState): the FlowState to remove from the current partition
        """
        for el in self.partitionElements:
            if fs in el.flows:
                # flow state found in this element, remove it
                el.flows.remove(fs)
                if not el.flows:
                    #list of flows associated with this element is empty, remove element from partition
                    self.partitionElements.remove(el)
                # we can safely exit - the flow state can only be in one partition element
                return

    def breakPartitionByIncomingEdge(self) -> None:
        """ Breaks the current partition depending on the incoming edge of the flows. Every element of the partition is break into several elements such that all the flows in each of the resulting elements come from the same input port (it does not mean that there will be the same number of partition elements element as the number of input ports). Example: assume partition is made of elements A = {f} and B={g,h}. Assume f and g comes from input port 1 and h comes from input port 2. Then the resulting partition is A={f},B={g},C={h}
        """
        partitionElementCreated = list()
        for el in self.partitionElements:
            # define the reference edge as the incoming edge of the first flow in the partition element
            referenceEdge = el.flows[0].atEdge
            flowsToMove = list()
            #for any other flow state (except the first one)
            for flow in el.flows[1:]:
                if flow.atEdge != referenceEdge:
                    flowsToMove.append(flow)
            if flowsToMove:
                # list is not empty
                # - remove flows from previous element
                for flow in flowsToMove:
                    el.flows.remove(flow)
                # - create new element.
                # I don't use self.createPartitionElement() cause I don't want to add an element to self.partitionElements while I'm looping on it
                newEl = FlowsPartitionElement()
                # - with flows needed to move
                newEl.flows = flowsToMove
                # - with a copy of the shaping curve
                newEl.aggregateShaping = copy.deepcopy(el.aggregateShaping)
                # add new element to list of created element
                partitionElementCreated.append(newEl)
        if partitionElementCreated:
            # new partition elements have been created, add them to the partition
            for nel in partitionElementCreated:
                self.partitionElements.append(nel)
            # recursive call until all no more partition element needs to be created
            self.breakPartitionByIncomingEdge()
        # if no partition element was created, return and break recursive stack

    def copy(self) -> 'FlowsPartition':
        """Creates a copy (level 2) of the present partition. The copy contains a new list, whose elements are each a copy of the FlowsPartitionElement that is present in the current partition. We use FlowsPartitionElement.copy() to copy the partition elements. In particular (look at the doc of FlowsPartitionElement.copy()), the flows states contained in the flow partition elements are not copied, we only copy their reference.

        Returns:
            FlowsPartition: the copy of the current partition (level 2, not a deepcopy)
        """
        newPartition = FlowsPartition()
        newPartition.name = self.name
        for element in self.partitionElements:
            newPartition.partitionElements.append(element.copy())
        return newPartition

    def copyWithFlowStates(self, fsl: List[FlowState]) -> 'FlowsPartition':
        newPartition = FlowsPartition()
        newPartition.name = self.name
        for element in self.partitionElements:
            copiedElement = element.copyWithFlowStates(fsl)
            if(copiedElement.flows):
                newPartition.partitionElements.append(copiedElement)
        return newPartition

    def isPartition(self, flowStates: List[FlowState]) -> bool:
        """Checks if the current FlowsPartition is indeed a valid partition of the provided flowStates

        Args:
            flowStates (list[flows.FlowState]): a list of the FlowStates that should be partitionned

        Returns:
            bool: True is the current object is a valid partition of the argument flowStates. False otherwise.
        """
        #Every fs in flowsStates must be presented once and only once
        for fs in flowStates:
            if (self.countElementsContainingFlowState(fs) != 1):
                return False
        #The partition contains no fs that is not in flowStates
        for element in self.partitionElements:
            for ffs in element.flows:
                if (ffs not in flowStates):
                    return False
        return True

    def addFixedOverheadEffect(self, linkSpeedDictionnary: Mapping[Tuple[str,str],float], overhead: float) -> None:
        for el in self.partitionElements:
            #retrieve the incoming edge associated with this partition element: take the one of the first flow in the partition element, they are all the same since we used partition.breakPartitionByIncomingEdge() beforehand
            if(el.flows[0].atEdge in linkSpeedDictionnary.keys()):
                #link speed known, tighter result
                el.aggregateShaping = el.aggregateShaping.return_curve_with_packetization(overhead,link_capacity=linkSpeedDictionnary[el.flows[0].atEdge])
            else:
                #link speed not known, traditionnal result
                el.aggregateShaping = el.aggregateShaping.return_curve_with_packetization(overhead)


    def addPacketizationEffect(self, linkSpeedDictionnary: Mapping[Tuple[str,str],float]) -> None:
        for el in self.partitionElements:
            if el.aggregateShaping is None:
                el.aggregateShaping = mpt.LeakyBucket(0.0, el.getMaxPacketLengthInPartitionElement())
                continue

            #retrieve the incoming edge associated with this partition element: take the one of the first flow in the partition element, they are all the same since we used partition.breakPartitionByIncomingEdge() beforehand
            if(el.flows[0].atEdge in linkSpeedDictionnary.keys()):
                #link speed known, tighter result
                el.aggregateShaping = el.aggregateShaping.return_curve_with_packetization(el.getMaxPacketLengthInPartitionElement(),link_capacity=linkSpeedDictionnary[el.flows[0].atEdge])
            else:
                #link speed not known, traditionnal result
                el.aggregateShaping = el.aggregateShaping.return_curve_with_packetization(el.getMaxPacketLengthInPartitionElement())


    def getResultingArrivalCurve(self) -> mpt.Curve:
        """Returns the resulting arrival curve for this partition. The resulting arrival curve is defined as the sum of the resulting arrival curves of each of the element in the partitionElements

        Returns:
            minPlusToolbox.Curve: the resulting arrival curve
        """
        thisPartitionCurve = mpt.NoCurve()
        for el in self.partitionElements:
            thisPartitionCurve = thisPartitionCurve + el.getResultingArrivalCurve()
        return thisPartitionCurve

######## PART 2: Definition of the computational blocks in the pipeline ##########

#The two static methods checkInstall and getConfiguredInstanceForNode are used for the auto configuration of the pipeline.
#The idea of the auto configuration is that when the input pipeline of a node is instanciated, for each possible computational block (each subclass of InputPipelineStep), we check whether an instance of this block should be added to the pipeline, based on a set of flags.
#See the checkInstall method documentation for each subclass of InputPipelineStep

class InputPipelineStep:
    """This interface represents a computational steps that:
            - May modify the flow states
            - May group flows into aggregates that are then shaped by a curve. For this it can change existing partitions by modifying/breaking/creating new partition elements in the existing partitions, or it can created a new partition.
    """
    _nodeName: str
    
    def __init__(self, nodeName) -> None:
        super().__init__()
        self._nodeName = nodeName

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        """This function MUST be overwritten by the implementation. 
        It executes the computationnal step. 
        The step SHOULD MODIFY the object referenced by the arguments and return nothing.

        Args:
            flowStates (list[FlowState]): the list of the flow states as they are at the output of the previous element in the input pipeline (or if the current object is the first step in the input pipeline, this is the list of the flow states as they enter the node). The current object may modify these flow states, they are then provided to the next step in the input pipeline.
            partitions (list[FlowsPartition]): the list of all the current existing partitions of the flows as they appear at the output of the previous step in the input pipeline. The current object may modify this list, which is then provided to the next step.
        """
        raise NotImplementedError()

    def clearComputations(self) -> None:
        """
        This function clears the computations of the pipeline computationnal block, in cas it saved temporary variables.
        It can be overwritten and SHALL be overwritten by any block that stores local results.
        """
        pass

    def checkAllPartitions(self, partitions: List[FlowsPartition], flowStates : List[FlowState]):
        """Utility class (no border effect) that checks if a list of partitions is indeed a list of partitions of all the flow states

        Args:
            partitions (List[FlowsPartition]): List of partitions to check
            flowStates (List[FlowState]): The list of flow states (each partition shall contain each flow state)

        Raises:
            AssertionError: Error raised when one of the partitions is invalid.
        """
        for p in partitions:
            if(not p.isPartition(flowStates)):
                raise AssertionError ("Invalid partition")
    

    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """This class function MUST be overwritten by the implementation. It checks if an instance for the current class should be installed on the input pipeline of the considered node. To make this decision, it can rely on the arguments that give the name and the computationnal flags associated with this node, as well as a reference to the entire network, shoudl the installation of the input pipeline step depend on some properties of other nodes or of the flows. The method MUST NOT modify the arguments.

        Args:
            compuFlags (Mapping): a dictionnary that gives the computationnal flags for this node
            net (networks.Network): a reference to the network
            nodeName (str): the name of the node

        Returns:
            bool: True if an instance of the class should be installed in the input pipeline for this node, False otherwise.
        """
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'InputPipelineStep':
        """ This class function MUST be overwritten by the implementation IF checkInstall is susceptible to answer True. Returns a configured instance of the current class to be added as an input pipeline step for the node.

        Args:
            compuFlags (Mapping): a dictionnary that gives the computationnal flags for this node
            net (networks.Network): a reference to the network
            nodeName (str): the name of the node

        Returns:
            InputPipelineStep: the configured instance, that will then be appended to the input pipeline for this node.
        """
        return NotImplemented

class InputPortShapingInputPipelineStep(InputPipelineStep):
    """This implementation of InputPipelineStep represents the effect of the input line shaping on the incoming flows. Specifically, it creates a new parition for each input port that contains the flowstates coming from this input port, and to each partition element, it associates the shaping curve that corresponds to this input port.
    """
    
    flagThatTriggersInstallation = "input-shaping"
    abbrvInTechnoThatTriggersInstallation = "IS"
    _shapingCurves: dict
    _is_packetizer_active: bool
    _inputLinkSpeed: dict

    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ In this implementation, we answer yes if:
                - (either a flag input-shaping="True" is found in the computationnal flags)
                - (PREVIOUS) OR (the abbreviation "IS" is in the technology flags of the computationnal flags)
                - (ALL THE PREVIOUS) AND (the node as at least one incoming edge in the ODG (output port dependency graph))

        Args:
            compuFlags (Mapping): a dictionnary that gives the computationnal flags for this node
            net (networks.Network): a reference to the network
            nodeName (str): the name of the node

        Returns:
            bool: True if an instance of the class should be installed in the input pipeline for this node, False otherwise.
        """
        if (not list(net.gif.predecessors(nodeName))):
            # the node has no predecessor, so no incoming flow is expected, do not install
            return False
        if(bool(compuFlags.get(cls.flagThatTriggersInstallation,""))):
            #flag found
            return True
        if(cls.abbrvInTechnoThatTriggersInstallation in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            #abbreviation 'IS' found
            return True
        if("packet-elimination-function" in compuFlags.keys()):
            return False
        if("ISNPE" in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            return True
        
        return super().checkInstall(compuFlags, net, nodeName)

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> InputPipelineStep:
        """ In this implementation, the InputPortShapingInputPipelineStep is configured by filling the _shapingCurves attribute, which is done by looking at the flag 'transmission-capacity' of the previous nodes
        """
        step = cls(nodeName)
        if("PK" in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            # Packetizer is active, register it
            step._is_packetizer_active = True
        for prevNode in net.gif.predecessors(nodeName):
            linkSpeed = net.gif.nodes[prevNode]["computational_flags"].get("transmission-capacity", None)
            if(linkSpeed):
                linkSpeed = unitUtility.readRate(linkSpeed)
                # the shaping curve is a gamma_c curve, which is the same as a leakybucket with no burst
                shapingCurve = mpt.LeakyBucket(linkSpeed,0)
                step.setShapingCurveForIncommingEdge((prevNode,nodeName), shapingCurve)
                step.setLinkSpeedForIncommingEdge((prevNode,nodeName), linkSpeed)
            else:
                #setting none is the way to tell 'no shaping'
                step.setShapingCurveForIncommingEdge((prevNode,nodeName), None)
        return step

    def __init__(self, nodeName) -> None:
        """Creates an InputPortShapingInputPipelineStep with an empty dictionnary for _shapingCurves
        """
        super().__init__(nodeName)
        self._shapingCurves = dict()
        self._is_packetizer_active = False
        self._inputLinkSpeed = dict()

    def setShapingCurveForIncommingEdge(self, edge, shapingCurve: mpt.Curve) -> None:
        """ Sets the shaping curve for the input port that corresponds to the provided edge in the ODG (Output port dependency graph)

        Args:
            edge: The edge in the ODG that corresponds to the input port
            shapingCurve (minPlusToolbox.Curve): The curve shaping the aggregate from this input port, or None if no shaping for this edge (<=> shaping with an infinite curve)
        """
        self._shapingCurves[edge] = shapingCurve

    def setLinkSpeedForIncommingEdge(self, edge: Tuple[str,str], linkSpeed: float) -> None:
        """ Sets the speed of the link connected to the input port represented by the provided edge. If provided, this information is used to compute a tighter packetization effect.

        Args:
            edge (Tuple[str,str]): An edge in the ODG (output port dependency graph)
            linkSpeed (float): the speed of the link that is connected to the input port represented by the provided edge.
        """
        self._inputLinkSpeed[edge] = linkSpeed
    
    def overrideAllShapingCurvesForAlreadyConfiguredEdges(self, newShapingCurve: mpt.Curve) -> None:
        for k in self._shapingCurves.keys():
            self._shapingCurves[k] = newShapingCurve

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        """Executes the InputPortShapingInputPipelineStep step. See documentation of super class
        """
        # input shaping does not modify flow states:
        # no delay penalty (input shaping is for free)
        
        # input shaping does not need to modify existing partitions (input shaping is for freee), let's create a new partition
        # first, create the dic (edge) -> (list of flow states on this edge)
        repartition = dict()
        for fs in flowStates:
            if (fs.atEdge not in repartition.keys()):
                #edge does not exists in dict, create
                repartition[fs.atEdge] = list()
            repartition[fs.atEdge].append(fs)

        #now, create the new partition
        newPartition = FlowsPartition()
        for edge in repartition.keys():
            # for each edge, create a partition element that contains the flow states comming from this edge and with shaping curve the one stored
            partEl = newPartition.createPartitionElement()
            partEl.aggregateShaping = self._shapingCurves.get(edge, None)
            partEl.flows = repartition[edge]
        if(not newPartition.isPartition(flowStates)):
            raise AssertionError("not a valid partition")
        newPartition.name = "InputShaping"
        if(self._is_packetizer_active):
            # We add the packetization effect to this partition only
            # Only the shaping curve will be affected, the burst of the individual flows will not be increased
            # This is expected as packetization does not affect burst of curves that are obtained through a deconvolution with
            # a delay bound, as the packetizer does not increase the worst-case delay.
            newPartition.addPacketizationEffect(self._inputLinkSpeed)
            newPartition.name = newPartition.name + "+" + "Packetization"
        partitions.append(newPartition)
        self.checkAllPartitions(partitions, flowStates)
             
class InitialPerInputPortAggregatorInputPipelineStep(InputPipelineStep):
    """This implementation of InputPipelineStep is always the first computational block in any pipeline (see the exception for development purposes in checkInstall).
    It groups the flow states per their input port and "shapes" them by the sum of their arrival curves.
    This step is important for all the computational block that MODIFIES the exiting partitions rather than creating new partitions.
    """
    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        repartition = dict()
        for fs in flowStates:
            if (fs.atEdge not in repartition.keys()):
                #edge does not exists in dict, create
                repartition[fs.atEdge] = list()
            repartition[fs.atEdge].append(fs)
        newPartition = FlowsPartition()
        for edge in repartition.keys():
            newEl = newPartition.createPartitionElement()
            shapingCurve = mpt.NoCurve()
            for fs in repartition[edge]:
                shapingCurve = shapingCurve + fs.getCopyInternalArrivalCurve()
                newEl.flows.append(fs)
            newEl.aggregateShaping = shapingCurve
        newPartition.name = "DummySum"
        partitions.append(newPartition)
        self.checkAllPartitions(partitions, flowStates)
    
    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """This module is always installed unless the compuFlags contain the flag "start_from_infinite" set to "true"

        Args:
            compuFlags (Mapping): the computational flags
            net (networks.Network): the network
            nodeName (str): the name of the node

        Returns:
            bool: true if the block should be instanciated, false otherwise
        """
        return (not bool(compuFlags.get("start_from_infinite","").lower() == "true"))

    
    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'InputPipelineStep':
        return InitialPerInputPortAggregatorInputPipelineStep(nodeName)
    
class LocalSourceApplicationsInputPipelineStep(InputPipelineStep):
    """This implementation of InputPipelineStep represents the internal application that locally generate packets

    Attributes:
        _localSourceFlowStates (List[FlowState]): the list of the flow states at the output of their respective application (BEFORE the first output port in their path)
    """
    
    _localSourceFlowStates: List[FlowState]

    def __init__(self, nodeName) -> None:
        """Creates a LocalSourceApplicationsInputPipelineStep with an empty _localSourceFlowStates list
        """
        super().__init__(nodeName)
        self._localSourceFlowStates = list()

    def addSourceFlowState(self, fs: FlowState) -> None:
        """Adds a flow state to the list of locally generated flows

        Args:
            fs (FlowState): the flow state (state of the flow at the output of its generating application)
        """
        self._localSourceFlowStates.append(fs)
    
    @classmethod
    def checkInstall(cls, compuFlags: dict, net: 'networks.Network', nodeName: str) -> bool:
        """ We answer yes if at least one flow has 'nodeName' as a source
        """
        for flow in net.flows:
            if nodeName in flow.sources:
                return True
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: dict, net: 'networks.Network', nodeName: str) -> InputPipelineStep:
        """ We configure the instance by populating the internal list of flow states
        """
        step = LocalSourceApplicationsInputPipelineStep(nodeName)
        for flow in net.flows:
            if nodeName in flow.sources:
                #create new flow state
                fs = FlowState(flow)
                fs.arrivalCurve = flow.sourceArrivalCurve
                #NO COPY of the arrival curve, this is important if we want to change the arrival curve after the installation of
                #micromodels
                fs.atEdge = "source"
                #set the flow state on the graph
                flow.graph.nodes[nodeName]["local_source_fs"] = fs
                fs.clock = Clock("H-"+nodeName)
                #and add the flow state to this pipeline step
                fs.changeClock(Clock("tai"))
                step.addSourceFlowState(fs)
        return step

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        newFsInTAI = self._localSourceFlowStates
                
        for fs in newFsInTAI:
            if(isinstance(fs.arrivalCurve,mpt.LeakyBucket)):
                #initialize data for adam
                fs.flags["adam-data"] = dict()
                fs.flags["adam-data"]["r2"] = Clock.RHO * fs.arrivalCurve.get_rate()
                fs.flags["adam-data"]["b2"] = fs.arrivalCurve.get_burst() + (Clock.ETA * fs.arrivalCurve.get_rate())
        
        # add all new flow states
        flowStates.extend(newFsInTAI)
        # group them into a single element in any partition
        for partition in partitions:
            newEl = partition.createPartitionElement()
            newEl.flows = newFsInTAI
            # no shaping curve (assuming internal stack can send as fast as the applications do)
            newEl.aggregateShaping = None
            partition.name = partition.name + "+" + "LocalSources"    
        #if there was no partition, create one
        if(not partitions):
            newP = FlowsPartition()
            el = newP.createPartitionElement()
            el.flows = newFsInTAI
            el.aggregateShaping = None
            newP.name = "LocalSources"
            partitions.append(newP)
        self.checkAllPartitions(partitions, flowStates)


class PacketEliminationFunctionInputPipelineStep(InputPipelineStep):
    """This implementation of InputPipelineStep represents the effect of the packet elimination functions on the aggregate arrival curve.

    Attributes:
        _selectiveMerge(bool): True if only some flows need to be merged, False if all flows are merged
        _flowsToMerge(Set[Flow]): If _selectiveMerge == True, this set contains the flows that are to be merged
        _nodeName(str): the name of the node
    """
    
    _selectiveMerge: bool
    _flowsToMerge: Set[Flow]

    def __init__(self, aNodeName: str) -> None:
        """Initialize with no selective merge

        Args:
            aNodeName (ste): the name of the node
        """
        self._selectiveMerge = False
        super().__init__(aNodeName)

    def _countFlowInFlowStates(self, flow: Flow, flowStates: List[FlowState]) -> int:
        """Counts the number of flow states in the list 'flowStates' that represents the state of the flow 'flow'

        Args:
            flow (Flow): the flow state to search/look for
            flowStates (List[FlowState]): the list of flow states in which to search

        Returns:
            int: the result
        """
        count = 0
        for fs in flowStates:
            if (flow == fs.flow):
                count += 1
        return count

    def _getSetOfFlowsToMerge(self, flowStates: List[FlowState]) -> Set[Flow]:
        """ Returns the set of Flow instances for which they are stictly more than one flow state to merge together. If selective merge is enabled, only the flow that are in the selective merge list are returned. 

        Args:
            flowStates (List[FlowState]): the list of flow states, potentially containing several flow states for a same flow

        Returns:
            Set[Flow]: the set of flows for which we need to merge the flow states
        """
        flowsToMerge = set()
        # Count the number of flows for which we observe strictly more than one flow state -> means the flow has been duplicated and is potentially to be merged
        for fs in flowStates:
            if (self._countFlowInFlowStates(fs.flow, flowStates) > 1):
                flowsToMerge.add(fs.flow)
        # Intersect with the limiting list of flows to merge for this specific step
        if(self._selectiveMerge):
            flowsToMerge = flowsToMerge.intersection(self._flowsToMerge)
        return flowsToMerge

    def _getClosestKey(self, graphOfFlow: networkx.DiGraph, sourceKeys: List[str]) -> str:
        """ Returns the node name in 'sourceKeys' that is the closest ancestor to self._nodeName in the graph 'graphOfFlow'.

        Args:
            graphOfFlow (networkx.DiGraph): the graph of the flow
            sourceKeys (List[str]): a list of keys, we will return the one that corresponds to the closest ancestor of self._nodeName

        Returns:
            str: the closest ancestor in graphOfFlow
        """
        candidate = sourceKeys[0]
        for key in sourceKeys:
            if(key == 'source'):
                # This key cannot strictly be closer than the current candidate
                continue
            if(candidate == 'source'):
                # The candidate cannot strictly be closer than the current key
                # so we can flip
                candidate = key
                continue
            # Here, neither 'key' nor 'candidate' can be equal to 'source' so they are valid node names in the flow graph
            distance_candidate = networkx.shortest_path_length(graphOfFlow, source=candidate, target=self._nodeName)
            distance_key = networkx.shortest_path_length(graphOfFlow, source=key, target=self._nodeName)
            if(distance_key < distance_candidate):
                # key is closer than candidate, flip
                candidate = key
        return candidate

    def _filterFlowStatesForAFlow(self, flowStates: List[FlowState], flow: Flow) -> List[FlowState]:
        """ Returns the flow states in 'flowStates' that belong to the flow 'flow'

        Args:
            flowStates (List[FlowState]): the list of flow states in which to select the flow states belonging to the flow
            flow (Flow): the flow to search

        Returns:
            List[FlowState]: the list of the flow states belonging to flow 'flow' and in the list 'flowStates'
        """
        flowStatesForThisFlow = list()
        #get the list of flowStates
        for ffs in flowStates:
            if (ffs.flow == flow):
                flowStatesForThisFlow.append(ffs)
        return flowStatesForThisFlow
            

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        """ In this implementation, we will:
            - For each already existing partition:
                - Create a new partition made of copy of the partition, but we have removed the flow states from the same flow from the partitions elements they were in, we have grouped them together, and we have set the shaping function as the right hand-side of the packet elimination output arrival curve theorem.
        """
        addedPartitions = list()
        for partition in partitions:
            #We will keep the partition intact (we can do it because the packet elimination function only removes packet without adding any jitter)
            #So it doesnt change any property of the aggregated traffic
            #so let's copy it
            newPartition = partition.copy()
            listFlowMerge = list(self._getSetOfFlowsToMerge(flowStates))
            orderedList = sorted(listFlowMerge, key=lambda x: x.name)
            for flow in orderedList:
                # get all the related flow states
                flowStatesForThisFlow = self._filterFlowStatesForAFlow(flowStates, flow)
                # Now, we need to obtain the min_i(d_i) and the max_i(D_i) for all the flow states, 
                # To do so, we will interesect the 'from' keys for each flow states:
                fromKeys = set(flowStatesForThisFlow[0].minDelayFrom.keys())
                for ffs in flowStatesForThisFlow:
                    fromKeys = fromKeys.intersection(set(ffs.minDelayFrom.keys()))
                #Now, we select the closest key
                shapingCurve = mpt.InfiniteCurve()
                if(len(fromKeys)>1):
                    logger.warn("More than one ancestor have been detected - The results are not valid if the network has cyclic dependencies")
                for kkey in fromKeys:
                    #we retrieve the arrival curve at the output of the key
                    arrivalCurveAtDivergencePoint = flow.getArrivalCurveAfterOutputPort(kkey)
                    #and compute the min/max delay between the closest key and the current nationFunctionode
                    dmin = min(fs.minDelayFrom[kkey] for fs in flowStatesForThisFlow)
                    dmax = max(fs.maxDelayFrom[kkey] for fs in flowStatesForThisFlow)
                    # and we compute the [alpha_previous (deconvolution) delta_{dmax-dmin}]
                    shapingCurve = shapingCurve * (arrivalCurveAtDivergencePoint / mpt.BoundedDelayServiceCurve(dmax - dmin))
                #In this new partitition which is for the moment the reflect of the previous partition, we need to remove the flow states from any partition elements they were in
                for fs in flowStatesForThisFlow:
                    newPartition.removeFlowStateFromPartition(fs)
                # Now create a new partition element and add the flow states
                el = newPartition.createPartitionElement()
                for fs in flowStatesForThisFlow:
                    el.flows.append(fs)
                el.aggregateShaping = shapingCurve
                el.flags["is_ancestor_deconvolution_partition_element"] = True # mark the element as the one relative to the ancestor deconvolution - can be useful for reordering function
                if(not newPartition.isPartition(flowStates)):
                    raise AssertionError("not a valid partition")
            newPartition.name = newPartition.name + "+" + "PacketElimination"
            addedPartitions.append(newPartition)
            # And now add all the newly created partitions to partitions
        partitions.extend(addedPartitions)
        self.checkAllPartitions(partitions, flowStates)

    @classmethod
    def checkTechno(cls, compuFlags: Mapping) -> bool:
        if("PE" not in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            return False
        return ("SPE" not in re.split("\+|\:|\/", compuFlags.get("technology","")))

    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ In this implementation (see also superclass documentation) we answer 'yes' if "packet-elimination-function" is a key in the compuFlags
        """
        if not cls.checkTechno(compuFlags):
            return False
        if(compuFlags.get("remove-input-pipeline-frer","") == "True"):
            return False
        if ("packet-elimination-function" in compuFlags.keys()):
            return True
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> InputPipelineStep:
        """ In this implementation (see also superclass documentation), we create and return a configured instance. If the "packet-elimination-function" flag is at 'all', then we do not configure selective selective merge. If "packet-elimination-function" is a comma-separated list of flow names, we configure selective merge for the flows that have these names.
        """
        instance = cls(nodeName)
        if (compuFlags["packet-elimination-function"] == "all"):
            return instance
        # selective mode enabled
        instance._selectiveMerge = True
        flowMergeStr = compuFlags["packet-elimination-function"].split(",")
        #search for the flow objects that have these names
        instance._flowsToMerge = [f for f in net.flows if f.name in flowMergeStr]
        return instance


class RegulatorInputPipelineStep(InputPipelineStep):
    """
    This computational block represent either:
        - an Interleaved Regulator placed after a FIFO system
        - or a PFR placed after a FIFO system
        - of a PFR not placed after a FIFO system
    Note that IR after a non-FIFO system is not supported but no test will check it.
    groups: A mapping between a set of flow names and the name of the reference point that defines the arrival curves that should be enforced.

    Inheritance:
        InputPipelineStep:

    """
    
    
    
    
    groups : Mapping[FrozenSet[str],str]
    pofIsPresentBefore: bool
    clockAdaptationMode: str
    adamMargin: float

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)
        self.groups = dict()
        self.pofIsPresentBefore = False
        self.clockAdaptationMode = "none"
        self.adamMargin = 1.05
    
    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ Check if a regulator should be installed here.
        Return TRUE if
        - the flag reg-config-implicit-ac is present in the compuFlags
        - AND 'REG' is present in the 'technology flag'
        """
        if("REG" not in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            return False
        if("reg-config-implicit-ac" in compuFlags.keys()):
            return True
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'InputPipelineStep':
        """Configure the instance.
        If a POF is present before, it MUST have the same configuration as reg-config-implicit-ac
        
        The flag 'reg-config-implicit-ac' should be present in the compuFlags.
        It should be formed as follows:
        "flow1,flow2,flow3:reference1;flow4,flow5:reference2"
        
        With this string, the computationnal block will represent two Interleaved regulators.
        The first one processes flow1,flow2,flow3 in a FIFO maner and for each of them, its shaping curve is defined as the arrival curve it has at reference 1.
        The second one processes flow4,flow5 in a FIFO maner and for each of them, its shaping curve is defined as the arrival curve it has at reference 2.

        The PFRs with the same flows are created with the configuration:
        "flow1:reference1;flow2:reference1;flow3:reference1;flow4:reference2;flow5:reference2"
        
        Warning: the implementation does not check the correctness of the 'reg-config-implicit-ac' string.
             
        """
        reg = cls(nodeName)
        if ("reg-config-implicit-ac" not in compuFlags.keys()):
            raise AssertionError("Computational flags must contain 'reg-config-implicit-ac'")
        if ("POF" in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            if("pof-config-implicit" not in compuFlags.keys()):
                raise AssertionError("Could not find 'pof-config-implicit' in the computational flags, but POF is mentionned")
            if(compuFlags["pof-config-implicit"] != compuFlags["reg-config-implicit-ac"]):
                raise AssertionError("Sorry but xTFA supports only POF followed by REG if they both have the same exact configuration (same groups, same reference)")
            reg.pofIsPresentBefore = True
        ats_config = compuFlags["reg-config-implicit-ac"]
        for group_config in ats_config.split(";"):
            group_config_items = group_config.split(":")
            mSetStr = group_config_items[0][1:-1]
            mSet = set(mSetStr.split(","))
            mfrozenSet = frozenset(mSet)
            reg.groups[mfrozenSet] = group_config_items[1]
        return reg

    def areTheyInTheSameGroup(self, f1: Flow, f2: Flow):
        """Return True if f1 and f2 are in the same group.
        """
        for group in self.groups.keys():
            if (f1.name in group) and (f2.name in group):
                return True
        return False

    def __adaptationMethodIsRequired(self, isPfr):
        if (self.clockAdaptationMode.lower() not in ["adam","cascade"]):
            raise AssertionError("A regulator adaptation method must be provided")
        if ((self.clockAdaptationMode.lower() == "adam") and (not isPfr)):
            raise AssertionError("ADAM cannot be used as an adaptation method for Interleaved Regualtor")

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        #Nw that we have stored all the information we needed (who comes from where, under which partition), we can focus on the main pipeline
        for fs in flowStates:
            itsGroup = None
            for group in self.groups.keys():
                if (fs.flow.name in group):
                    itsGroup = group
                    break
            if(itsGroup):
                iAmPfr = (len(itsGroup) <= 1)
                itsRef = self.groups[itsGroup]
                #get the dmax for the aggregate coming from the same reference point
                if(itsRef not in fs.maxDelayFrom.keys()):
                    raise (CurveNotKnown())
                dmax = fs.maxDelayFrom[itsRef]
                dmin = fs.minDelayFrom[itsRef]
                
                #First we check that we will not lead to unbounded latencies
                
                #First, the clocks
                if(not Clock.PERFECT):
                    if(not Clock.SYNC):
                        self.__adaptationMethodIsRequired(iAmPfr)
                    if(not iAmPfr):
                        #IR and synchronized, adaptation is required
                        self.__adaptationMethodIsRequired(iAmPfr)
                #Then, the non-FIFO
                if(fs.rtoFrom[itsRef] > 0):
                    #system is not FIFO
                    if((not iAmPfr) and (not self.pofIsPresentBefore)):
                        raise AssertionError("POF is required before an IR after a non-FIFO system")
                    if(iAmPfr and (not self.pofIsPresentBefore)):
                        #Theorem 4.4 of the manuscript,
                        #penalty is D-d
                        fs.addSufferedDelay(dmax-dmin)
                
            
                #Now, we add the different penalties
                #First, the aggregate delay penalty (for IR)
                if(not iAmPfr):
                    #The first penalty that we suffer is the penalty of aggregating.
                    #Indeed the IR is 'for free' only for the aggregate, so everyone suffers the worst delay among the flows of the aggregate 
                    for ffs in flowStates:
                        if(self.areTheyInTheSameGroup(fs.flow, ffs.flow)):
                            dmax = max(dmax, ffs.maxDelayFrom[itsRef])
                            dmin = min(dmin, ffs.minDelayFrom[itsRef])
                    myDmax = fs.maxDelayFrom[itsRef]
                    penaltyDueToAggregating = dmax - myDmax
                    fs.addSufferedDelay(penaltyDueToAggregating)
                


                
                # we obtain the arrival curve at the reference point by asking the flow, providing the reference we stored
                ac = fs.flow.getArrivalCurveAfterOutputPort(self.groups[itsGroup])
                if(not Clock.PERFECT):
                    if(self.clockAdaptationMode and isinstance(ac,mpt.GVBR)):
                        ac = ac.get_first_lb()
                    if(self.clockAdaptationMode == "cascade"):
                        #worsen cascade
                        nr = ac.get_rate()*Clock.RHO
                        nb = ac.get_burst() + Clock.ETA * ac.get_rate()
                        ac = mpt.LeakyBucket(nr,nb)
                    if(self.clockAdaptationMode == "adam"):
                        #worsen cascade
                        ac = mpt.LeakyBucket(fs.flow.sourceArrivalCurve.get_rate()*self.adamMargin,fs.flow.sourceArrivalCurve.get_burst())
                # force the ac
                fs.arrivalCurve = copy.deepcopy(ac)
                fs.clock = Clock("H-" + self._nodeName)
                # register the arrival curve
                fs.flow.registerSpecialInternalCurve("ats-curve", self._nodeName, copy.deepcopy(ac))
                # add the current entry to the dictionnary of delays
                fs.addDelayFromEntry("ats:%s" % self._nodeName)
                fs.addRtoFromEntry("ats:%s" % self._nodeName)
                # register self as last fresh ac
                lastref = fs.flags.get("last-fresh","source")
                fs.flags["last-fresh"] = ("ats:%s" % self._nodeName)
                #This flow state is valid in my local time,
                #change for TAI
                fs.changeClock(Clock("tai"))
                if((not Clock.PERFECT) and (iAmPfr) and (Clock.SYNC) and (self.clockAdaptationMode not in ["cascade","adam"])):
                    fs.addSufferedDelay(4*Clock.DELTA)
                if((not Clock.PERFECT) and (self.clockAdaptationMode == "adam")):
                    r0 = fs.flow.sourceArrivalCurve.get_rate()
                    b0 = fs.flow.sourceArrivalCurve.get_burst()
                    d = fs.flags.get("adam-data", {"r2" : r0 * Clock.RHO, "b2": b0 + r0 * Clock.ETA})
                    r2 = d["r2"]
                    b2 = d["b2"]
                    penalty = Clock.ETA * (1 + Clock.RHO) + ((d["b2"] - b0 - Clock.ETA * self.adamMargin * r0) / (Clock.RHO * r0)) * ((Clock.RHO*Clock.RHO-1)/(self.adamMargin - 1))
                    b2 = b2 + Clock.RHO * r0 * (fs.maxDelayFrom.get(lastref,0) - fs.minDelayFrom.get(lastref,0))
                    fs.flags["adam-data"] = dict()
                    fs.flags["adam-data"]["r2"] = r2
                    fs.flags["adam-data"]["b2"] = b2
                #the flow is now is going to be processed alone, so IT MUST be removed from any partition it was in
                for p in partitions:
                    p.removeFlowStateFromPartition(fs)
                    newEl = p.createPartitionElement()
                    newEl.flows.append(fs)
                    # no shaping
                    newEl.aggregateShaping = None
        for p in partitions:
            p.name += "+ATS"
            if(not p.isPartition(flowStates)):
                raise AssertionError("Invalid partition")
        self.checkAllPartitions(partitions, flowStates)

class PacketEliminationFunctionFlowStateForceMergingInputPipelineStep(InputPipelineStep):
    """This computational block forces the flow states of a same flow to be merged into a single flow state prior to being sent to a regulator. This block is used only when a regulator is present just after the PEF and the reason is that the regulator will recreate the flow from fresh so we don't need the flow states to be separated (the separation of flow states is useful only with partitions).
    """
    
    _selectiveMerge: bool
    _flowsToMerge: Set[Flow]

    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """Install if both PEF and ATS are present in the pipeline
        """
        return (PacketEliminationFunctionInputPipelineStep.checkInstall(compuFlags, net, nodeName) and RegulatorInputPipelineStep.checkInstall(compuFlags, net, nodeName))

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str):
        instance = cls(nodeName)
        if (compuFlags["packet-elimination-function"] == "all"):
            return instance
        # selective mode enabled
        instance._selectiveMerge = True
        flowMergeStr = compuFlags["packet-elimination-function"].split(",")
        instance._flowsToMerge = [f for f in net.flows if f.name in flowMergeStr]
        return instance

    def __init__(self, aNodeName) -> None:
        super().__init__(aNodeName)
        self._selectiveMerge = False       

    
    def _countFlowInFlowStates(self, flow: Flow, flowStates: List[FlowState]):
        count = 0
        for fs in flowStates:
            if (flow == fs.flow):
                count += 1
        return count

    def _getSetOfFlowsToMerge(self, flowStates) -> Set[Flow]:
        flowsToMerge = set()
        # Count the number of flows for which we observe more than one flow state -> means the flow has been duplicated
        for fs in flowStates:
            if (self._countFlowInFlowStates(fs.flow, flowStates) > 1):
                flowsToMerge.add(fs.flow)
        # Intersect with the limiting list of flows to merge for this specific step
        if(self._selectiveMerge):
            flowsToMerge = flowsToMerge.intersection(self._flowsToMerge)
        return flowsToMerge

    def _getClosestKey(self, graphOfFlow: networkx.DiGraph, sourceKeys: List[str]):
        candidate = 'source'
        for key in sourceKeys:
            if(":" in key):
                # do not process ATS stuff here
                continue
            if(key == 'source'):
                # This key cannot strictly be closer than the current canditate
                continue
            if(candidate == 'source'):
                # The candidate cannot strictly be closer than the current key
                # so we can flip
                candidate = key
                continue
            # Here, neither 'key' nor 'candidate' can be equal to 'source' so they are valid node names in the flow graph
            distance_candidate = networkx.shortest_path_length(graphOfFlow, source=candidate, target=self._nodeName)
            distance_key = networkx.shortest_path_length(graphOfFlow, source=key, target=self._nodeName)
            if(distance_key < distance_candidate):
                candidate = key
        return candidate

    def _filterFlowStatesForAFlow(self, flowStates: List[FlowState], flow: Flow) -> List[FlowState]:
        flowStatesForThisFlow = list()
        #get the list of flowStates
        for ffs in flowStates:
            if (ffs.flow == flow):
                flowStatesForThisFlow.append(ffs)
        return flowStatesForThisFlow
            
    def _addSufferedRtoForNodesBeforeTheSplit(self, flowState: FlowState, rto: float, closestAncestor: str):
        if((closestAncestor == 'source') and ('source' in flowState.rtoFrom.keys())):
            #Closest ancestor is source, only the source key needs to increase its rto
            flowState.rtoFrom[closestAncestor] += rto
            return
        if(":" in closestAncestor):
            closestAncestor = closestAncestor.split(":")[1]
        for key in flowState.rtoFrom.keys():
            #here I'm assuming that the tagging is complete:
            #meaning if a flowstate is tagged at some point in the network, than all the flowstates for the same flow are ALSO tagged
            #this ensures that, among the rtoFrom.keys(), we have keys that are either common to all paths and preceding the closestAncestor OR at least not present in one of the paths
            #hence the logic is: add the RTO to keys before the closestAncestor, but do not add it to keys that are after hte closest ancestor because we assume that at least one path is not going through this
            #key, so basically the packets are not "reordered" from this key because of this merge
            if key == 'source':
                #key is source, it is necessarely BEFORE the closestAncestor, increase its key
                flowState.rtoFrom[key] += rto
                continue
            if(":" in key):
                subkey = key.split(":")[1]
            if subkey in networkx.ancestors(flowState.flow.graph, closestAncestor):
                flowState.rtoFrom[key] += rto
            

    def _mergeDelayDictionnaries(self, mergingFlowStates: List[FlowState]) -> Tuple[Mapping[str,float], Mapping[str,float]]:
        minDelayDict = dict()
        maxDelayDict = dict()
        possibleKeysMin = set()
        possibleKeysMax = set()
        for fs in mergingFlowStates:
            possibleKeysMin = possibleKeysMin.union(fs.minDelayFrom.keys())
            possibleKeysMax = possibleKeysMax.union(fs.maxDelayFrom.keys())
        #Then for any key, get either the max or the min of the values in the FlowStates that have this key:
        for keyMin in possibleKeysMin:
            minDelayDict[keyMin] = min(fs.minDelayFrom[keyMin] for fs in mergingFlowStates if keyMin in fs.minDelayFrom.keys()) 
        for keyMax in possibleKeysMax:
            maxDelayDict[keyMax] = max(fs.maxDelayFrom[keyMax] for fs in mergingFlowStates if keyMax in fs.maxDelayFrom.keys())
        return minDelayDict, maxDelayDict
    
    def mergeRtoDict(self, mergingFlowStates: List[FlowState]) -> Mapping[str,float]:
        rtoDict = dict()
        possibleKeys= set()
        for fs in mergingFlowStates:
            possibleKeys = possibleKeys.union(fs.rtoFrom.keys())
        #Then for any key, get the max of the rto
        for key in possibleKeys:
            rtoDict[key] = max(fs.rtoFrom[key] for fs in mergingFlowStates if key in fs.rtoFrom.keys()) 
        return rtoDict
    

    def mergeFlags(self, mergingFlowStates: List[FlowState]) -> Mapping:
        flags = dict()
        for fs in mergingFlowStates:
            flags = dict(flags, **fs.flags)
        return flags

    def _getJitterFromKey(self, key: str, mergingFlowStates: List[FlowState]) -> float:
        minFromKey = min(fs.minDelayFrom[key] for fs in mergingFlowStates if key in fs.minDelayFrom.keys()) 
        maxFromKey = max(fs.maxDelayFrom[key] for fs in mergingFlowStates if key in fs.maxDelayFrom.keys())
        return (maxFromKey - minFromKey)

    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        for flow in self._getSetOfFlowsToMerge(flowStates):
            flowStatesForThisFlow = self._filterFlowStatesForAFlow(flowStates, flow)
            #compute the common keys
            fromKeys = set(flowStatesForThisFlow[0].minDelayFrom.keys())
            refClock = flowStatesForThisFlow[0].clock
            for ffs in flowStatesForThisFlow:
                if(not ffs.clock.equals(refClock)):
                    raise AssertionError("The flow states for flow %s at node %s are not observed with the same clock. This is unexpected" % (flow.name, self._nodeName))
                fromKeys = fromKeys.intersection(set(ffs.minDelayFrom.keys()))
            #This will be the future merged flow state. We set the correct flow
            newFlowState = FlowState(flow)
            
            # clock: current node
            newFlowState.clock = refClock

            #We take the union of flags. Duplicates are resolved arbitrarely
            newFlowState.flags = self.mergeFlags(flowStatesForThisFlow)
            # We need to do a few things: first, we need to merge the dictionnaries of min [resp max] delays into a unique min [resp max] delay dictionnary
            newFlowState.minDelayFrom, newFlowState.maxDelayFrom = self._mergeDelayDictionnaries(flowStatesForThisFlow)
            # Now we also merge the RTO dictionnaries before adding the RTO due to the merging
            newFlowState.rtoFrom = self.mergeRtoDict(flowStatesForThisFlow)
            # Now we need to add the RTO due to the merge
            # To do so, we need a bound on non-FIFO jitter between the split and the merge.
            # The smallest bound that we can obtain is the jitter between the closest ancestor and this current node.
            # So first let's obtain the closest ancestor
            closestAncestor = self._getClosestKey(flow.graph,list(fromKeys))
            # And compute the jitter across all the flow states from this closest ancestor
            nonFifoJitterBound = self._getJitterFromKey(closestAncestor, flowStatesForThisFlow)
            # And now we will add the nonFifoJitter
            self._addSufferedRtoForNodesBeforeTheSplit(newFlowState, nonFifoJitterBound, closestAncestor)

            # NOW, WE need to select a leaky-bucket arrival curve valid JUST BEFORE the FIFO contention step
            # This arrival curve will ONLY be needed if the output arrival curve computation uses propagation instead of re-computing from the source
            # For this, we select the key for which the deconvolutated leaky-bucket has the SMALLEST BURST
            theNewCurve = None
            for key in fromKeys:
                try:
                    arrivalCurveAtDivergencePoint = flow.getArrivalCurveAfterOutputPort(key)
                except AssertionError:
                    #curve not known here, do not use it
                    continue
                dmin = min(fs.minDelayFrom[key] for fs in flowStatesForThisFlow)
                dmax = max(fs.maxDelayFrom[key] for fs in flowStatesForThisFlow)
                candidateCurve = arrivalCurveAtDivergencePoint / mpt.BoundedDelayServiceCurve(dmax - dmin)
                if(not isinstance(theNewCurve, mpt.LeakyBucket)):
                    #the new curve was not assigned yet, assign it
                    theNewCurve = candidateCurve
                    continue
                if(candidateCurve.to_leaky_bucket_with_minimum_burst().get_burst() < theNewCurve.get_burst()):
                    theNewCurve = candidateCurve
            newFlowState.arrivalCurve = theNewCurve
            # .edge field has not been set, but it will be by the output arrival curve computation step
            #and of course we remove all the constituing flow states from the lis
            for ffffs in flowStatesForThisFlow:
                for p in partitions:
                    p.removeFlowStateFromPartition(ffffs)
            for fs in flowStatesForThisFlow:
                flowStates.remove(fs)
            #then we can add this new flow state to the list of flow states
            flowStates.append(newFlowState)
            #and to the partitions
            for pp in partitions:
                el = pp.createPartitionElement()
                el.aggregateShaping = None
                el.flows.append(newFlowState)
            for ppp in partitions:
                if not ppp.isPartition(flowStates):
                    raise AssertionError("Invalid partition")
        self.checkAllPartitions(partitions, flowStates)

class PacketOrderingFunctionInputPipelineStep(InputPipelineStep):
    """
    This computational block represent a set of // POF, either per flow or per-aggregate:

    Inheritance:
        InputPipelineStep:

    """
    groups : Mapping[FrozenSet[str],str]  #set of flows, reference

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)
        self.groups = dict()
        self.nonReorderingPfr = False
    
    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ Check if a regulator should be installed here.
        Return TRUE if
        - the flag pof-config-implicit is present in the compuFlags
        - AND 'POF' is present in the 'technology flag'
        """
        if("POF" not in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            return False
        if("pof-config-implicit" in compuFlags.keys()):
            return True
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'InputPipelineStep':
        """Configure the instance.
        
        The flag 'pof-config-implicit' should be present in the compuFlags.
        It should be formed as follows:
        "flow1,flow2,flow3:reference1;flow4,flow5:reference2"
        
        With this string, the computationnal block will represent two POFs.
        The first one processes flow1,flow2,flow3 and reorders them as an aggregate, in the order they had at reference 1.

             
        """
        pofs = cls(nodeName)
        if("pof-config-implicit" in compuFlags.keys()):
            pof_config = compuFlags["pof-config-implicit"]
            for group_config in pof_config.split(";"):
                group_config_items = group_config.split(":")
                mSetStr = group_config_items[0][1:-1]
                mSet = set(mSetStr.split(","))
                mfrozenSet = frozenset(mSet)
                pofs.groups[mfrozenSet] = group_config_items[1]
        return pofs

    def areTheyInTheSameGroup(self, f1: Flow, f2: Flow):
        """Return True if f1 and f2 are in the same group.
        """
        for group in self.groups.keys():
            if (f1.name in group) and (f2.name in group):
                return True
        return False


    def executeStep(self, flowStates: List[FlowState], partitions: List[FlowsPartition]) -> None:
        
        myDataPerGroup : Mapping[FrozenSet(str),List]

        myFlowStates: Mapping[FrozenSet(str),List[FlowState]]

        myDataPerGroup = dict()
        myFlowStates = dict()
        for mset in self.groups.keys():
            myDataPerGroup[mset] = [0,-1,mpt.NoCurve()]
            #dmin for aggregate since ref
            #dmax for aggregate since ref
            #arrival curve of aggregate at ref
            myFlowStates[mset] = list()
        
        for fs in flowStates:
            itsGroup = None
            for group in self.groups.keys():
                if (fs.flow.name in group):
                    itsGroup = group
                    break
            if(itsGroup):
                itsRef = self.groups[itsGroup]
                myFlowStates[itsGroup].append(fs)            
                itsMax = fs.maxDelayFrom[itsRef]
                itsMin = fs.minDelayFrom[itsRef]
                if(myDataPerGroup[itsGroup][1] < 0):
                    myDataPerGroup[itsGroup][1] = itsMax
                myDataPerGroup[itsGroup][0] = min(myDataPerGroup[itsGroup][0],itsMin)
                myDataPerGroup[itsGroup][1] = max(myDataPerGroup[itsGroup][1],itsMax)
                myDataPerGroup[itsGroup][2] += fs.flow.getArrivalCurveAfterOutputPort(itsRef)
        
        for group in self.groups:
            if(not myFlowStates[group]):
                continue
            #First, compute the new individual arrival curve for each, Thm 5 of Ehsan and JYLB paper on reordering metrics
            for fs in myFlowStates[group]:
                fs.arrivalCurve = fs.flow.getArrivalCurveAfterOutputPort(self.groups[group]) / mpt.BoundedDelayServiceCurve(myDataPerGroup[group][1] - myDataPerGroup[group][0])
                #arrival curve at the reference, worsened by the jitter of the AGGREGATE:
                # myDataPerGroup[group][1] is max delay from reference for the aggregate,
                # myDataPerGroup[group][0] is min delay from reference for the aggregate,
                fs.addSufferedDelay(myDataPerGroup[group][1] - fs.maxDelayFrom[self.groups[group]])
                #The POF is for free FOR THE AGGREGATE, but not for the flow individually, so the difference between the aggregate max and the individual max is an additionnal suffered delay
                fs.rtoFrom[self.groups[group]] = 0.0
                #the flow is reordered
            #Then, for each incoming partition
            for p in partitions:
                # We need to remove all flow states from the partition because the POF worsens the arrival curves
                newPartEl = p.createPartitionElement()
                #arrival curve of the group processed by the flow is its arrival curve at the ref, ie myDataPerGroup[group][2], worsened by the jitter of the aggregate since the ref
                newPartEl.aggregateShaping = myDataPerGroup[group][2] / mpt.BoundedDelayServiceCurve(myDataPerGroup[group][1] - myDataPerGroup[group][0])
                for fs in myFlowStates[group]:
                    newPartEl.flows.append(fs)
                    #remove from partition
                    p.removeFlowStateFromPartition(fs)
                p.name += "+POF"
                if(not p.isPartition(flowStates)):
                    raise AssertionError("Invalid partition")
        self.checkAllPartitions(partitions, flowStates)
class InputPipeline:
    """ This object represents an input pipeline. The role of the input pipeline is to compute the arrival curve of the aggregate arriving at the queuing subsystem. A pipeline is made of successive pipeline steps.Each pipeline step may:
        - modify the individual flow states, in particular their arrival curve or add new flow states, in particular to represent a local generation of flows.
        - modify the already existing partitions by modifying, removing or adding partition elements to the already existing partitions or by modifying the shaping curve associated with a partition element. It may also create a new partition.
    Partitions represent way to group several flow states into 'partition elements' and to shape these groups usiong shaping curves. To learn more, see FlowsPartition, FlowsPartitionElements and InputPipelineStep.

    AutoInstall feature: input pipelines can be auto configured using the autoInstall method. Then each class in the availableModules list attribute will be asked (using a class method) if an instance of this module should be installed on the pipeline for this node, and if so, a configured instance will be appended to the current pipeline.

    Attributes:
        - availableModules (class-level): a list of InputPipeline class names, available for auto install. Step will be appended in the same order (if applicatble), so the order in this list is important.
        - pipeline (List[InputPipelineStep]): the pipeline (list of InputPipelineStep instances) for this instance.
        - flags: a dictionnary to store flags on the state of the pipeline 
    """
    
    #List of available computational blocks.
    #The order of these modules mater for autoconfiguration because each of these class, in thi order, will be asked whether it should be instanciated based on the autoconfiguration flags (flags in compuFlag + content of the 'technology' string)
    availableModules = [InitialPerInputPortAggregatorInputPipelineStep, InputPortShapingInputPipelineStep,PacketEliminationFunctionInputPipelineStep, PacketEliminationFunctionFlowStateForceMergingInputPipelineStep, PacketOrderingFunctionInputPipelineStep, RegulatorInputPipelineStep, LocalSourceApplicationsInputPipelineStep]

    pipeline: List[InputPipelineStep]
    flags: dict
    
    _nodeName: str
    _flowStates: List[FlowState]
    _partitions: List[FlowsPartition]

    def __init__(self, nodeName: str) -> None:
        """ Creates a pipeline with an empty pipeline and the flag "pipeline_finished" at False

        Args:
            nodeName (str): the name of the node for this pipeline
        """
        super().__init__()
        self.pipeline = list()
        self.flags = dict()
        self.flags["pipeline_finished"] = False
        self._flowStates = list()
        self._partitions = list()
        self._nodeName = nodeName


    def autoInstall(self, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> None:
        """ Performs the auto install procedure for this pipeline.
                                                                                                                
        Args:
            compuFlags (Mapping): a dictionnary that gives the computationnal flags for this node
            net (networks.Network): a reference to the network
            nodeName (str): the name of the node
        """
        # TODO: check if next line is still necessary
        self.flags["plot-delay-computation"] = bool(compuFlags.get("plot-delay-computations","").lower() == "true")
        self.flags["plot-partition-result"] = bool(compuFlags.get("plot-partition-result","").lower() == "true")
        self.flags["start_from_infinite"] = bool(compuFlags.get("start_from_infinite","").lower() == "true")
        if(self.flags["plot-partition-result"]):
            self.flags["plot-partition-result-flags"] = compuFlags.get("plot-partition-result-flags",{})
        #for each available module, ask and configure
        for avType in self.availableModules:
            if(avType.checkInstall(compuFlags, net, nodeName)):
                self.appendPipelineElement(avType.getConfiguredInstanceForNode(compuFlags, net, nodeName))

    def appendPipelineElement(self, pipelineElement: InputPipelineStep) -> None:
        """Appends an InputPipelineStep to the pipeline

        Args:
            pipelineElement (InputPipelineStep): the step to add
        """
        self.pipeline.append(pipelineElement)

    def setInputFlowStates(self, flowStates: List[FlowState]) -> None:
        """ Sets the flow states at the input of the input pipeline (a copy will be performed using the copy() method of FlowState)

        Args:
            flowStates (List[FlowState]): the flow states entering the input pipeline
        """
        for fs in flowStates:
            self._flowStates.append(fs.copy())

    def getOutputFlowStates(self) -> List[FlowState]:
        """Returns the flow states as they are at the output of the input pipeline (may have been modified by packetizers, regulators etc within the pipeline)

        Raises:
            AssertionError: if the pipeline has not been executed beforehand

        Returns:
            List[FlowState]: the lsit of the flow states at the output of the input pipeline
        """
        if (not self.flags.get("pipeline_finished", False)):
            raise AssertionError("Pipeline must be computed before calling getFinalArrivalCurve")
        l = list()
        for f in self._flowStates:
            l.append(f.copy())
        return l

    def processPipeline(self) -> None:
        """Processes the pipeline (each step, in their order in the list of pipeline element)
        """
        if(self.flags.get("pipeline_finished",False)):
            raise AssertionError("'pipeline_finished' must be 'False' to process the pipeline. Cannot do it twice")
        #Call each step of the pipeline
        for inputPipelineStep in self.pipeline:
            inputPipelineStep.executeStep(self._flowStates, self._partitions)
            for f in self._flowStates:
                if(not Clock.PERFECT and not f.clock.is_tai):
                    raise AssertionError("At the output of the following input pipeline step, not all flow states are observed in TAI, which is unexpected: %s" % inputPipelineStep)
        self.flags["pipeline_finished"] = True


    def isFinished(self) -> bool:
        """ Checks if pipeline has been executed

        Returns:
            bool: True if pipeline is finished, False otherwise
        """
        return self.flags.get("pipeline_finished", False)

    def getFinalArrivalCurve(self) -> mpt.Curve:
        """ Returns the arrival curve for the aggregate at the end of the pipeline

        Returns:
            minPlusToolbox.Curve: the aggregate arrival curve resulting from the pipeline
        """
        #if pipeline not processed, cannot get final arrival curve
        if(not self.flags.get("pipeline_finished",False)):
            raise AssertionError("Pipeline must be computed before calling getFinalArrivalCurve")
        if(not self._flowStates):
            logging.warning("No flow states in the pipeline, return NoCurve()")
            return mpt.NoCurve()
        if(self.flags.get("start_from_infinite",False)):
            curve = mpt.InfiniteCurve()
        else:
            curve = mpt.NoCurve()
            #First, add all the individual flows to get a first convolution element
            for fs in self._flowStates:
                curve = curve + fs.getCopyInternalArrivalCurve()
            #Now, for every parition, sum the resulting arrival curves for every element and convoluate every resulting curve
        if(self.flags.get("plot-partition-result",False)):
            toPlot = list()
        for partition in self._partitions:
            if(self.flags.get("plot-partition-result",False)):
                thisCurve = partition.getResultingArrivalCurve()
                thisCurve.set_name(partition.name)
                toPlot.append(thisCurve)
            thisthisCurve = partition.getResultingArrivalCurve()
            curve = curve * thisthisCurve
        logger.debug("%s:AggregatedAC:%s" % (self._nodeName, curve.__str__()))
        if(self.flags.get("plot-partition-result",False)):
            genCurve = copy.deepcopy(curve)
            genCurve.set_name("Final")
            mpt.plot_arrival_curves(*toPlot, genCurve, title=self._nodeName + " (ACs from partitions)", without_zero=True, **self.flags.get("plot-partition-result-flags",{}))
            t = "%s:PipelineContent:\n" % self._nodeName
            for ips in self.pipeline:
                t += ("- " + type(ips).__name__ + "\n")
            logger.debug(t)

    def clearPipelineComputations(self) -> None:
        self.flags["pipeline_finished"] = False
        self._flowStates = list()
        self._partitions = list()
        for pipeElement in self.pipeline:
            pipeElement.clearComputations()


from xtfa import networks