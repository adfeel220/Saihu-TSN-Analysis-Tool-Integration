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
This module contains the definition of the delay-bound computation computation pipeline
In the software, the delay-bound computation pipeline is called the "contention pipeline" (legacy name)
The role of this pipeline is to compute the worst-case delay of the aggregate in this node.

The file is split in two parts:
-First all the possible computational blocks inside the pipeline are defined
-Then the low-state computation pipeline itself is defined.
"""

from typing import List, Mapping, Set, Tuple
import re
import copy
import logging

from xtfa.clocks import Clock
from xtfa import flows
from xtfa import minPlusToolbox as mpt
from xtfa import unitUtility




#contention pipeline
logger = logging.getLogger("CP")

class ContentionPipelineStep:
    """ This interface represents a step in the contention pipeline (= the pipeline that computes the delay suffered by the flows of this class)

    Attributes:
        _nodeName (str): the name of the node on which the pipeline step is installed
    """

    _nodeName: str

    def __init__(self, theNodeName) -> None:
        super().__init__()
        self._nodeName = theNodeName
    
    def executeStep(self, flowStates: List[flows.FlowState], aggregatedArrivalCurve: mpt.Curve, previousMinDelay: float, previousMaxDelay: float, flags: Mapping) -> Tuple[float,float]:
        """ Executes the step of the contention pipeline. Returns the lower- and upper-bounds for the delay that the flows suffer at this step. The subclass must override this method.

        Args:
            flowStates (List[flows.FlowState]): the list of all the flow states at the input of the contention pipeline (not at at the input of this specific pipeline step). The subclass MAY NOT modify the list or its content.
            aggregatedArrivalCurve (mpt.Curve): the aggregated arrival curve at the input of the contention pipeline (not at at the input of this specific pipeline step). The subclass MAY NOT modify this curbe.
            previousMinDelay (float): the previously accumulated minimum delay in all the previous steps in the contention pipeline
            previousMaxDelay (float): the previously accumulated maximum delay in all the previous steps in the contention pipeline
            flags (Mapping): a dictionnary of flags that can be read to receive informations from previous pipeline steps and that CAN BE MODIFIED to send informations to future pipeline steps

        Returns:
            Tuple[float,float]: (minDelay,maxDelay) where minDelay is the minimum delay suffered at this step, maximumDelay is the maximum delay suffered at this step. Both delay MAY BE NEGATIVE if the current step represents some sort of delay improvement due to NC's results.
        """
        return (NotImplemented,NotImplemented)


    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """Checks if an instance of the contention step should be installed at this node. The subclass MUST OVERRIDE this method. 

        Args:
            compuFlags (Mapping): the dictionnary of computationnal flags as extracted for this output port on this physical node of this network.
            net (Network): the reference to the Network object that nodeName belongs to
            nodeName (str): the name of the current node, on which we want to check if we need to install an instance of this pipeline element

        Returns:
            bool: True if an instance of the current class must be installed on the contention pipeline of the node 'nodeName', False otherwise
        """
        return False

    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'ContentionPipelineStep':
        """ Retrieves a configured instance of the current class for the node nodeName

        Args:
            compuFlags (Mapping): the dictionnary of computationnal flags as extracted for this output port on this physical node of this network.
            net (Network): the reference to the Network object that nodeName belongs to
            nodeName (str): the name of the current node, on which we want to check if we need to install an instance of this pipeline element

        Returns:
            ContentionPipelineStep : a configured instance of the subclass, configured for the node 'nodeName'
        """
        return NotImplemented

class FifoContentionStep(ContentionPipelineStep):
    """This implementation of ContentionPipelineStep represents the classic FIFO service provided to the aggregate of flows, served by a service curve
    """
    
    _plotDelayComputation: bool
    _plotKargs: Mapping
    _serviceCurve: mpt.Curve


    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ In this implementation of the checkInstall interface method, we answer yes if the key "service-policy" of compuFlags is set to "FIRST_IN_FIRST_OUT"

        Args:
            compuFlags (Mapping): the dictionnary of computationnal flags as extracted for this output port on this physical node of this network.
            net (Network): the reference to the Network object that nodeName belongs to
            nodeName (str): the name of the current node, on which we want to check if we need to install an instance of this pipeline element

        Returns:
            bool: True if the key "service-policy" of compuFlags is set to "FIRST_IN_FIRST_OUT". False otherwise
        """
        if (compuFlags.get("service-policy","") == "FIRST_IN_FIRST_OUT") or ("FIFO" in re.split("\+|\:|\/", compuFlags.get("technology","")) and ("transmission-capacity" in compuFlags.keys())):
            return True
        return False
    
    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'ContentionPipelineStep':
        """ Retrieves a configured instance of the current class for the node 'nodeName'

        Args:
            compuFlags (Mapping): the dictionnary of computationnal flags as extracted for this output port on this physical node of this network.
            net (Network): the reference to the Network object that nodeName belongs to
            nodeName (str): the name of the current node, on which we want to check if we need to install an instance of this pipeline element

        Returns:
            ContentionPipelineStep : a configured instance of the subclass, configured for the node 'nodeName'
        """
        step = FifoContentionStep(nodeName)
        #Service is a rate-latency service curve. 
        # 'tech-latency' is supposed to be the MAXIMAL tech latency, min is supposed to be 0
        # rate is the 'service-rate' if present, otherwise it is transmission-capacity
    
        rate = unitUtility.readRate(compuFlags.get("service-rate","0"))
        latency = unitUtility.readTime(compuFlags.get("service-latency","0"))
        step.setServiceCurve(mpt.RateLatencyServiceCurve(rate, latency))
        # a flag to plot the delay computation
        if(compuFlags.get("plot-delay-computation","") == "True"):
            step._plotDelayComputation = True
            step._plotKargs = compuFlags.get("plot-delay-computation-flags", dict())
        return step

    def __init__(self, nodeName) -> None:
        super().__init__(nodeName)
        self._plotDelayComputation = False
    
    def setServiceCurve(self, curve: mpt.Curve) -> None:
        """ Sets the service curve serving the aggregate

        Args:
            curve (mpt.Curve): the service curve for this FIFO element
        """
        self._serviceCurve = curve
    
    def getServiceCurveCopy(self) -> mpt.Curve:
        return copy.deepcopy(self._serviceCurve)

    def executeStep(self, flowStates: List[flows.FlowState], aggregatedArrivalCurve: mpt.Curve, previousMinDelay: float, previousMaxDelay: float, flags: dict) -> Tuple[float,float]:
        """ In this implementation of the interface method, the maximum delay bound is obtained by deconvolution of the aggregate arrival curve with the self._serviceCurve

        Args:
            flowStates (List[flows.FlowState]): not used in this subclass
            aggregatedArrivalCurve (mpt.Curve): used to compute the delay bound as being the maximum horizontal distance between aggregatedArrivalCurve and the service curve of self
            previousMinDelay (float): not used in this subclass
            previousMaxDelay (float): not used in this subclass
            flags (dict): this class ADDS the following keys to the FLAGS: 
                - flags["service_is_rate_latency"] is set to True if the service of self is Rate-Latency, False otherwise
                - if flags["service_is_rate_latency"] == True:
                    - flags["rate_latency_service_rate"] contains the rate of the Rate-Latency service curve of self
                    - flags["rate_latency_service_latency"] contains the latency of the Rate-Latency service curve of self

        Returns:
            Tuple[float,float]: (0,maxDelayBound) where maxDelayBound is the maximum horizontal distance between the aggregate arrival curve and the service curve computed using the mpt's modulo (%) operation. Minimum delay is always assumed to equal zero, use other pipeline steps or other pipelines to set the minimum delay
        """
        # set some flags to pass on information for next steps in the contention pipeline
        flags["service_is_rate_latency"] = isinstance(self._serviceCurve, mpt.RateLatencyServiceCurve)
        if(flags["service_is_rate_latency"]):
            flags["rate_latency_service_rate"] = self._serviceCurve.get_rate()
            flags["rate_latency_service_latency"] = self._serviceCurve.get_latency()
 
        # compute delay bound (max horizontal distance between aggregated arrival curve and this service curve)
        # minimum delay is assumed to be 0
        #Always in TAI strat
        sc = Clock.worsen_service_curve(self._serviceCurve)
        Dmax = aggregatedArrivalCurve  % sc
        if(flags.get("plot-delay-computation", False) or self._plotDelayComputation):
            #set the name of the curves for the plot
            aggregatedArrivalCurve.set_name("AC")
            self._serviceCurve.set_name("SC")
            mpt.plot_a_delay_computation(aggregatedArrivalCurve, self._serviceCurve, title=self._nodeName, **self._plotKargs)
        logger.debug("%s:Fifo:Dmax=%.4e" % (self._nodeName, Dmax))
        return (0, Dmax)
    
class MohammadpourEtAlImprovementStep(ContentionPipelineStep):
    """ This implementation of ContentionPipelineStep represents the improvement proved by Mohammadpour et al when the output rate is known.

    Attributes:
        abbrvInTechnoThatTriggersInstallation (str): a string that triggers the installation of MohammadpourEtAlImprovementStep instances on every node if present on the technology network-level flag
    """


    _outputLinkSpeed: float
    abbrvInTechnoThatTriggersInstallation = "MOH"

    def __init__(self, nodeName, outputLinkSpeed: float) -> None:
        super().__init__(nodeName)
        self._outputLinkSpeed = outputLinkSpeed

    
    def setOutputLinkSpeed(self, linkSpeed: float) -> None:
        self._outputLinkSpeed = linkSpeed
    
    @classmethod
    def checkInstall(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> bool:
        """ In this implementation of the interface method, we answer True if [the flag 'technology' contains 'MOH' AND compuFlags contain 'transmission-capacity'], False otherwize

        Args:
            compuFlags (Mapping): the dictionnary of computationnal flags as extracted for this output port on this physical node of this network.
            net (Network): the reference to the Network object that nodeName belongs to
            nodeName (str): the name of the current node, on which we want to check if we need to install an instance of this pipeline element

        Returns:
            bool: True if [the flag 'technology' contains 'MOH' AND compuFlags contain 'transmission-capacity'], False otherwize
        """
        if(cls.abbrvInTechnoThatTriggersInstallation in re.split("\+|\:|\/", compuFlags.get("technology","")) and ("transmission-capacity" in compuFlags.keys())):
            return True
        return False
    
    @classmethod
    def getConfiguredInstanceForNode(cls, compuFlags: Mapping, net: 'networks.Network', nodeName: str) -> 'ContentionPipelineStep':
        """ Retrieves a configured instance of the current class for the node nodeName

        Args:
            compuFlags (Mapping): the dictionnary of computationnal flags as extracted for this output port on this physical node of this network.
            net (Network): the reference to the Network object that nodeName belongs to
            nodeName (str): the name of the current node, on which we want to check if we need to install an instance of this pipeline element

        Returns:
            ContentionPipelineStep : a configured instance of the subclass, configured for the node nodeName
        """
        #obtain the outSpeed
        outSpeed = unitUtility.readRate(compuFlags.get("transmission-capacity","1"))
        step = MohammadpourEtAlImprovementStep(nodeName, outSpeed)
        return step
        
    def _getMinimumPacketLength(self, listOfFlowStates: List[flows.FlowState]) -> int:
        """ Returns the minimum packet length on a set of flow states

        Args:
            listOfFlowStates (List[flows.FlowState]): a list of flow states

        Returns:
            int: the minimum packet length across all the flowstates
        """
        return min(fs.flow.minPacketLength for fs in listOfFlowStates)
    

    def executeStep(self, flowStates: List[flows.FlowState], aggregatedArrivalCurve: mpt.Curve, previousMinDelay: float, previousMaxDelay: float, flags: dict) -> Tuple[float,float]:
        """ In this implementation of the interface method, we return a negative maximum delay to represent the improvement proved by Mohammadpour et al.

        Args:
            flowStates (List[flows.FlowState]): the list of flow states at the input of the contention pipeline. Used to obtain min packet size
            aggregatedArrivalCurve (mpt.Curve): not used in this subclass
            previousMinDelay (float): not used in this subclass
            previousMaxDelay (float): not used in this subclass
            flags (dict): this step READS the following flags:
                - if flags["service_is_rate_latency"] == False, no improvement is done. Otherwise, it REQUIRES the following flag:
                    - flags["rate_latency_service_rate"] is the rate of the rate-latency service rate, required for the computation of the delay bound improvement 

        Returns:
            Tuple[float,float]: (0,improvement) where improvement is a negative value that represents the improvement of the delay thanks to the Mohammadpour et al theorem
        """
        if(not flags.get("service_is_rate_latency",False)):
            #service is not rate-latency, no improvement, exit
            return (0,0)
        rate = flags.get("rate_latency_service_rate")
        lmin = self._getMinimumPacketLength(flowStates)
        # see http://doi.org/10.1109/LNET.2019.2927143
        improv = max(lmin * (1/rate - 1/self._outputLinkSpeed), 0)
        #improvement: return negative delay for this contention step
        logger.debug("%s:Moh:Improv=%.4e" % (self._nodeName, improv))
        # no min delay
        return (0,-(improv))
class ContentionPipeline:
    """ This class represents a contention pipeline. A contention pipeline is an ordered list of ContentionPipelineStep instances. Each step is executed one after the other one. Each step computes an additionnal lower and upper bounding value for the delay that the flows suffer in the contention part of the output port (for example constant delay, or jitter in the switch fabric could rather be added to the InputPipeline, though it is not required, it depends on what you want to do). All the lower and upper bounding values from every step are CUMMULATIVE: they are summed to obtain the definitive lower and upper bounding values of the delay that every flow suffers through this output port. Each step makes its decision based on the state of the flows and the aggregate arrival curve AT THE INPUT OF THE CONTENTION PIPELINE (these object are not updated through the contention pipeline AND MUST NOT BE MODIFIED BY ANY of the steps)

    Attributes:
        availableModules: only used at class level. List of available ContentionPipelineStep subclasses. Used for auto install. During auto install, each subclass, IN THE ORDER AT WHICH THEY APPEAR IN THIS LIST, is asked (using a classmethod) if an instance of the subclass should be installed in this contention pipeline, and if so, and instance is created and put in the contention pipeline
    """
    # The available subclasses of ContentionPipelineStep
    availableModules = [FifoContentionStep, MohammadpourEtAlImprovementStep]

    # The instances in this pipeline
    _pipelineSteps: List[ContentionPipelineStep]

    # The flow states and input arrival curve 
    _inputAggregateAC: mpt.Curve
    _flowStates: List[flows.FlowState]

    # Current delay min/max in the pipeline. Values are updated as every step of the pipeline is executed.
    _delayMinInContentionPipeline: float
    _delayMaxInContentionPipeline: float

    # Flags for this pipeline. DOES NOT MEAN the flags that are shared accross the pipeline steps
    _flags: dict

    def autoInstall(self, compuFlags: Mapping, net: 'networks.Network', nodeName: str):
        """ Auto install a contention pipeline. To do so, every sclass in self.availableModules is asked whether an instance of the class should be installed for the contention pipeline of this node, and if so, an instance is added.
        Subclasses are sollicitated in the order of the list self.availableModules, so its order matters.

        Args:
            compuFlags (Mapping): the dictionnary of computational flags
            net (Network): the network
            nodeName (str): the name of the node on which we want to install a pipeline
        """
        for avType in self.availableModules:
            if(avType.checkInstall(compuFlags, net, nodeName)):
                self.appendContentionStep(avType.getConfiguredInstanceForNode(compuFlags, net, nodeName))
        self._flags["node_name"] = nodeName

    def __init__(self, nodeName) -> None:
        super().__init__()
        self._pipelineSteps = list()
        # set the flags of the pipeline: the pipeline is not finished
        self._flags = dict()
        self._flags["pipeline_finished"] = False
        self._flowStates = list()
        self._nodeName = nodeName

    def appendContentionStep(self, step: ContentionPipelineStep) -> None:
        """ Appends a ContentionPipelineStep to the current ContentionPipeline

        Args:
            step (ContentionPipelineStep): the step to add (added at the end of the pipeline)
        """
        self._pipelineSteps.append(step)
    
    def setInputAggregate(self, aggregateAC : mpt.Curve) -> None:
        """ Set the aggregate arrival curve that enters the contention pipeline (that enters the output port of the current node)

        Args:
            aggregateAC (mpt.Curve): the arrival curve of the aggregate
        """
        self._inputAggregateAC = aggregateAC
    
    def setInputFlowStates(self, flowStates: List[flows.FlowState]) -> None:
        """ Sets (by copying) the flow states at the input of the contention pipeline

        Args:
            flowStates (List[flows.FlowState]): the list of the flow states as they enter the contention pipeline
        """
        #empty the list
        self._flowStates = list()
        #do a copy of every flow state 
        for fs in flowStates:
            self._flowStates.append(fs.copy())
            #not that the above copy does not copy the reference to the flow that is included in the flow state. In general, flow states may be copied but flows are never copied and this is the expected behaviour.

    def processPipeline(self):
        """Processes the current contention pipeline

        Raises:
            AssertionError: when the pipeline has already been processed
        """
        #this dict will be shared accross the different steps of the pipeline
        flagsSharedBetweenPipelineSteps = dict()
        # only execute pipeline if not already done (otherwise flow states are updated again as if they went through the pipeline twice)
        if(self._flags.get("pipeline_finished", False)):
            raise AssertionError("'pipeline_finished' must be 'False' to process the pipeline. Cannot do it twice")
        # prepare the delays
        self._delayMaxInContentionPipeline = 0.0
        self._delayMinInContentionPipeline = 0.0
        for step in self._pipelineSteps:
            #execute every step in the order of the pipeline
            thisDelayMin, thisDelayMax = step.executeStep(self._flowStates, self._inputAggregateAC, self._delayMinInContentionPipeline, self._delayMaxInContentionPipeline, flagsSharedBetweenPipelineSteps)
            self._delayMinInContentionPipeline += thisDelayMin
            self._delayMaxInContentionPipeline += thisDelayMax
        #pipeline has finished
        self._flags["pipeline_finished"] = True
        

    def getContentionDelayBounds(self) -> Tuple[float,float]:
        """Returns the lower and upper bounding values for the delays of the flows in the output port represented by the current contention pipeline

        Raises:
            AssertionError: if processPipeline() has not been called beforehand

        Returns:
            Tuple[float,float]: (minDelayBound,maxDelayBound) for this output port
        """
        if(not self._flags.get("pipeline_finished",False)):
            raise AssertionError("Pipeline must be computed before calling getContentionDelayBounds()")
        return self._delayMinInContentionPipeline, self._delayMaxInContentionPipeline



    def isFinished(self) -> bool:
        """ Answers True if the pipeline has been computed, False otherwise

        Returns:
            bool: True is the pipeline has been processed, False otherwise
        """
        return self._flags.get("pipeline_finished", False)

    def clearPipelineComputations(self) -> None:
        self._flags["pipeline_finished"] = False
        self._inputAggregateAC = None
        self._flowStates = list()
        self._delayMinInContentionPipeline = None
        self._delayMaxInContentionPipeline = None
    
from xtfa import networks