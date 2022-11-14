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
This module contains the definition of the flow-state computation pipeline
In the software, the flow-state computation pipeline computational pipeline is called the "output pipeline" (legacy name)
The role of this pipeline is, once the delay bound in this node has been computed, to update all the individual flow states with the individual arrival curves.

The file is split in two parts:
-First all the possible computational blocks inside the pipeline are defined
-Then the low-state computation pipeline itself is defined.
"""



from typing import List, Mapping, Set, Tuple
import re
import networkx
import math

from xtfa import unitUtility
from xtfa.clocks import Clock
from xtfa import flows
from xtfa import minPlusToolbox as mpt
from xtfa import unitUtility
from xtfa import inputPipelines




class OutputPipelineStep:
    """This is the interface for a computational block in the output pipeline.
    The structure of the class is similar to an ACP computational block we refer to the ACP (ie input pipeline) for details.
    """
    _nodeName: str

    def __init__(self, nodeName) -> None:
        super().__init__()
        self._nodeName = nodeName

    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        raise NotImplementedError()

    @classmethod
    def checkInstall(cls, compuFlags, net, nodeName) -> bool:
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags, net, nodeName):
        return NotImplemented

class FromKeyTaggingOutputPipelineStep(OutputPipelineStep):
    """This computational block does not exactly compute anything.
    It adds the current node to the list of ancestors in all outgoing flow states.
    This correspond to adding the current node to the set \mathcal{U} defined in the manuscript.
    As a consequence, all the flow states wil 'automatically' remember the delay they have suffered since the current node.
    """

    _selectiveTag: bool
    _tagList: List[flows.Flow]

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)
        self._selectiveTag = False
        self._tagList = list()
        
    
    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ To install this block, the tag "tag-reference-point" should be in compuFlags.
        """
        if ("tag-reference-point" in compuFlags.keys()):
            return True
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str):
        """ If the tag "tag-reference-point" in compuFlags equal "all", all flow states will be tagged, otherwise it should contain a comma-separated list of flow names to tag.
        """
        instance = FromKeyTaggingOutputPipelineStep(nodeName)
        if (compuFlags["tag-reference-point"] == "all"):
            return instance
        # selective mode enabled
        instance._selectiveTag = True
        flowTagStr = compuFlags["tag-reference-point"].split(",")
        instance._tagList = [f for f in flows if f.name in flowTagStr]
        return instance

    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        for fs in flowStates:
            if ((not self._selectiveTag) or (fs.flow in self._tagList)):
                fs.addDelayFromEntry(flags["node_name"])
                fs.addRtoFromEntry(flags["node_name"])

class DeltaDDeconvolutionOutputPipelineStep(OutputPipelineStep):
    """This computationnal step takes the input flow state and worsens it by the delay bound in this node.
    """

    @classmethod
    def checkInstall(cls, compuFlags: dict, net: 'networks.Network', nodeName: str) -> bool:
        return ("PROP" in re.split("\+|\:|\/", compuFlags.get("technology","")))

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags : dict, net : 'networks.Network', nodeName: str):
        step = DeltaDDeconvolutionOutputPipelineStep(nodeName)
        return step

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)

    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        deconvolutionService = mpt.BoundedDelayServiceCurve(maxContentionDelay - minContentionDelay)
        for flow in flowStates:
            flow.addSufferedDelay(maxContentionDelay,minDelay=minContentionDelay)
            flow.arrivalCurve = flow.arrivalCurve / deconvolutionService

class FromSourceDeltaDDeconvolutionOutputPipelineStep(OutputPipelineStep):
    """This computationnal step differs from the previous one as it performs the deconvolution not of the input flow state but of the source arrival curve (or the arrival curve of the last regulator)
    """

    @classmethod
    def checkInstall(cls, compuFlags, net, nodeName) -> bool:
        if ("PROP" in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            return False
        return True
    
    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags, net, nodeName):
        return FromSourceDeltaDDeconvolutionOutputPipelineStep(nodeName)

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)

    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        for fs in flowStates:
            fs.addSufferedDelay(maxContentionDelay,minDelay=minContentionDelay)
            lastFresh = fs.flags.get("last-fresh", "source")
            lastFreshAc = fs.flow.getArrivalCurveAfterOutputPort(lastFresh)
            #in TAI
            lastFreshAc = Clock.worsen_arrival_curve(lastFreshAc)
            minD = fs.minDelayFrom[lastFresh]
            maxD = fs.maxDelayFrom[lastFresh]
            fs.arrivalCurve = lastFreshAc / mpt.BoundedDelayServiceCurve(maxD - minD)

class CeilBurstsOutputPipelineStep(OutputPipelineStep):
    """ This block is only used with the fix-point version of xTFA, it ceils the burst and the lmax delay so that fix point can be reached with strict equality
    """

    decimalsDelay: int

    @classmethod
    def checkInstall(cls, compuFlags, net, nodeName) -> bool:
        if("CEIL" in re.split("\+|\:|\/", compuFlags.get("technology",""))):
            return True
        if(compuFlags.get("ceil-bursts", "False") == "True"):
            return True
        return super().checkInstall(compuFlags, net, nodeName)
    
    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags, net, nodeName):
        instance = CeilBurstsOutputPipelineStep(nodeName)
        return instance

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)
        self.decimalsDelay = 15

    def round_decimals_up(self, number:float, decimals:int=2):
        """
        Returns a value rounded up to a specific number of decimal places.
        """
        if not isinstance(decimals, int):
            raise TypeError("decimal places must be an integer")
        elif decimals < 0:
            raise ValueError("decimal places has to be 0 or more")  
        elif decimals == 0:
            return math.ceil(number)
        factor = 10 ** decimals

        if(round(number, decimals) == number):
            return number

        return math.ceil(number * factor) / factor

    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        for fs in flowStates:
            fs.arrivalCurve.ceil_bursts()
            
            #only rounding up the max from source, the min and rto are not rounded cause not used as convergence variables
            fs.maxDelayFrom["source"] = self.round_decimals_up(fs.maxDelayFrom["source"], self.decimalsDelay)
    

class PacketEliminationFunctionFlowStateMergingOutputPipelineStep(OutputPipelineStep):
    """This block merges the flow states of a flow that has been processed by a PEF, if it was not already done in the input pipeline.
    Basically when two flow states belonging to the same flow cross the node and their duplicates are eliminated by a PEF, this block merges them into a single flow state.
    """
    _selectiveMerge: bool
    _flowsToMerge: Set[flows.Flow]

    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        if(inputPipelines.PacketEliminationFunctionFlowStateForceMergingInputPipelineStep.checkInstall(compuFlags, net, nodeName)):
            #do not install if already present in input
            return False
        if ( ("PE" not in re.split("\+|\:|\/", compuFlags.get("technology",""))) and ("SPE" not in re.split("\+|\:|\/", compuFlags.get("technology","")))):
            return False
        if ("packet-elimination-function" in compuFlags.keys()):
            return True
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str):
        instance = PacketEliminationFunctionFlowStateMergingOutputPipelineStep(nodeName)
        if (compuFlags["packet-elimination-function"] == "all"):
            return instance
        # selective mode enabled
        instance._selectiveMerge = True
        flowMergeStr = compuFlags["packet-elimination-function"].split(",")
        instance._flowsToMerge = [f for f in flows if f.name in flowMergeStr]
        return instance

    def __init__(self, aNodeName) -> None:
        super().__init__(aNodeName)
        self._selectiveMerge = False       

    
    def _countFlowInFlowStates(self, flow: flows.Flow, flowStates: List[flows.FlowState]):
        count = 0
        for fs in flowStates:
            if (flow == fs.flow):
                count += 1
        return count

    def _getSetOfFlowsToMerge(self, flowStates) -> Set[flows.Flow]:
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

    def _filterFlowStatesForAFlow(self, flowStates: List[flows.FlowState], flow: flows.Flow) -> List[flows.FlowState]:
        flowStatesForThisFlow = list()
        #get the list of flowStates
        for ffs in flowStates:
            if (ffs.flow == flow):
                flowStatesForThisFlow.append(ffs)
        return flowStatesForThisFlow
            
    def _addSufferedRtoForNodesBeforeTheSplit(self, flowState: flows.FlowState, rto: float, closestAncestor: str):
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
            

    def _mergeDelayDictionnaries(self, mergingFlowStates: List[flows.FlowState]) -> Tuple[Mapping[str,float], Mapping[str,float]]:
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
    
    def mergeRtoDict(self, mergingFlowStates: List[flows.FlowState]) -> Mapping[str,float]:
        rtoDict = dict()
        possibleKeys= set()
        for fs in mergingFlowStates:
            possibleKeys = possibleKeys.union(fs.rtoFrom.keys())
        #Then for any key, get the max of the rto
        for key in possibleKeys:
            rtoDict[key] = max(fs.rtoFrom[key] for fs in mergingFlowStates if key in fs.rtoFrom.keys()) 
        return rtoDict
    

    def mergeFlags(self, mergingFlowStates: List[flows.FlowState]) -> Mapping:
        md = dict()
        for key in mergingFlowStates[0].flags.keys():
            inAll = True
            for fs in mergingFlowStates:
                if key not in fs.flags.keys():
                    inAll = False
                    break
            if(inAll):            
                md[key] = mergingFlowStates[0].flags[key]
        return md

    def _getJitterFromKey(self, key: str, mergingFlowStates: List[flows.FlowState]) -> float:
        minFromKey = min(fs.minDelayFrom[key] for fs in mergingFlowStates if key in fs.minDelayFrom.keys()) 
        maxFromKey = max(fs.maxDelayFrom[key] for fs in mergingFlowStates if key in fs.maxDelayFrom.keys())
        return (maxFromKey - minFromKey)


    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
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
            newFlowState = flows.FlowState(flow)

            # clock: current node
            newFlowState.clock = refClock

            #We take the interection of flags. Duplicates are resolved arbitrarely
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
            #and of course we remove all the constituing flow states from the list
            for fs in flowStatesForThisFlow:
                flowStates.remove(fs)
            #then we can add this new flow state to the list of flow states
            flowStates.append(newFlowState)

class TransmissionDelayOnlyAddMinimumDelayDoNotChangeMaxDelay(OutputPipelineStep):
    """This output pipeline step adds a minimumDelay of Lmin / c where Lmin is the minimum size of any packet in the flow.

    IT DOES NOT CHANGE THE MAXIMUM DELAYS
    IT DOES NOT CHANGE THE ARRIVAL CURVE
    """

    _linkSpeed: float

    @classmethod
    def checkInstall(cls, compuFlags, net, nodeName) -> bool:
        return ("TDMI" in re.split("\+|\:|\/", compuFlags.get("technology",""))) and ("transmission-capacity" in compuFlags.keys())
    
    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags, net, nodeName):
        instance = cls(nodeName)
        instance._linkSpeed = unitUtility.readRate(compuFlags["transmission-capacity"])
        return instance
    
    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        for fs in flowStates:
            dmin = fs.flow.minPacketLength / self._linkSpeed
            #do not add a maximum delay bound, set 0
            fs.addDelaysToDisctionnaryWithoutChangingRto(0, dmin)

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)

class ConstantPropagationDelayOutputPipelineStep(OutputPipelineStep):
    """ This adds a constant propagation delay propD to all the flow States

    ALL THE DELAY MAX BOUNDS ARE INCREASED BY propD
    ALL THE DELAY MIN BOUNDS ARE INCREASED BY propD
    IT DOES NOT CHANGE ANY ARRIVAL CURVE
    """

    propD: float

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)
    
    def executeStep(self, flowStates: List[flows.FlowState], minContentionDelay: float, maxContentionDelay: float, flags: Mapping):
        for fs in flowStates:
            fs.addSufferedDelay(self.propD, self.propD)
    
    @classmethod
    def checkInstall(cls, compuFlags, net, nodeName) -> bool:
        return ("PD" in re.split("\+|\:|\/", compuFlags.get("technology",""))) and ("prop-delay" in compuFlags.keys())

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags, net, nodeName):
        instance = cls(nodeName)
        instance.propD = unitUtility.readTime(compuFlags["prop-delay"])
        return instance

class OutputPipeline:
    #order matters!
    availableModules = [PacketEliminationFunctionFlowStateMergingOutputPipelineStep, DeltaDDeconvolutionOutputPipelineStep, FromSourceDeltaDDeconvolutionOutputPipelineStep,  FromKeyTaggingOutputPipelineStep, TransmissionDelayOnlyAddMinimumDelayDoNotChangeMaxDelay, CeilBurstsOutputPipelineStep, ConstantPropagationDelayOutputPipelineStep]
    
    pipeline: List[OutputPipelineStep]
    flags: dict
    
    flowStates: List[flows.FlowState]
    delayMinInContention: float
    delayMaxInContention: float
    nodeName: str

    def __init__(self,nodeName) -> None:
        super().__init__()
        self.pipeline = list()
        self.flags = dict()
        self.flags["pipeline_finished"] = False
        self._flowStates = list()
        self.nodeName = nodeName

    def autoInstall(self, compuFlags, net, nodeName):
        for avType in self.availableModules:
            if(avType.checkInstall(compuFlags, net, nodeName)):
                self.appendPipelineElement(avType.getConfiguredInstanceForNode(compuFlags, net, nodeName))

    def appendPipelineElement(self, pipelineElement: OutputPipelineStep) -> None:
        self.pipeline.append(pipelineElement)
    
    
    def setInputFlowStates(self, flowStates: List[flows.FlowState]) -> None:
        for fs in flowStates:
            self._flowStates.append(fs.copy())

    def getOutputFlowStates(self) -> List[flows.FlowState]:
        if (not self.flags.get("pipeline_finished", False)):
            raise AssertionError("Pipeline must be computed before calling getFinalArrivalCurve")
        l = list()
        for f in self._flowStates:
            l.append(f.copy())
        return l

    def setContentionDelayBounds(self, lowerBound: float, upperBound: float) -> None:
        self.delayMinInContention = lowerBound
        self.delayMaxInContention = upperBound

    def processPipeline(self):
        """Processes the pipeline (each step, in their order in the list of pipeline element)
        """
        if(self.flags.get("pipeline_finished",False)):
            raise AssertionError("'pipeline_finished' must be 'False' to process the pipeline. Cannot do it twice")
        #Call each step of the pipeline
        localFlags = dict()
        localFlags["node_name"] = self.nodeName
        for outputPipelineStep in self.pipeline:    
            outputPipelineStep.executeStep(self._flowStates, self.delayMinInContention, self.delayMaxInContention, localFlags)
        self.flags["pipeline_finished"] = True


    def isFinished(self):
        return self.flags.get("pipeline_finished", False)

    def clearPipelineComputations(self) -> None:
        self.flags["pipeline_finished"] = False
        self._flowStates = list()
        self.delayMinInContention = None
        self.delayMaxInContention = None


from xtfa import networks