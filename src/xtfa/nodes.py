#!/usr/bin/python3#
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
This class represent the model of a node, as made of an input pipeline (an aggregate computation pipeline), a contention pipeline (a delay-bound pipeline) and an output pipeline (a flow-state computation pipeline).
It also stores the FlowStates of the flow at various observation points
"""

from typing import List, Mapping
from enum import Enum

from xtfa import flows
from xtfa import inputPipelines, contentionPipelines, outputPipelines
from xtfa import minPlusToolbox as mpt
from xtfa.clocks import Clock

class FlowStatesDictKeysEnum(Enum):
    input = "at_node_input" #ie $n^{\text{in}}$
    afterInputPipeline = "after_input_pipeline" #ie $n^{\dagger}$
    output = "at_node_output" #ie $n'$

class Node:

    _name: str
    _netName: str
    inputPipeline: inputPipelines.InputPipeline
    contentionPipeline: contentionPipelines.ContentionPipeline
    outputPipeline: outputPipelines.OutputPipeline

    _flowStates: Mapping[FlowStatesDictKeysEnum, List[flows.FlowState]]
    _aggregatedArrivalCurveAtContention: mpt.Curve

    contentionDelayMin: float
    contentionDelayMax: float
    clock: Clock

    def __init__(self, nodeName, netName) -> None:
        super().__init__()
        self._name = nodeName
        self._netName = netName
        self._flowStates = dict()
        for e in FlowStatesDictKeysEnum:
            self._flowStates[e] = list()
        self.inputPipeline = inputPipelines.InputPipeline(self._name)
        self.contentionPipeline = contentionPipelines.ContentionPipeline(self._name)
        self.outputPipeline = outputPipelines.OutputPipeline(self._name)
        self.clock = Clock("H"+self._name)

    def autoInstallPipelines(self, compuFlags: dict, net: 'networks.FeedForwardNetwork'):
        """Auto install the blocks in the pipeline, see the pipelines for more details
        """
        self.inputPipeline.autoInstall(compuFlags, net, self._name)
        self.contentionPipeline.autoInstall(compuFlags, net, self._name)
        self.outputPipeline.autoInstall(compuFlags, net, self._name)

    def getAggregateArrivalCurveAtContention(self) -> mpt.Curve:
        """Return the class aggregate arrival curve

        Returns:
            mpt.Curve: class aggregae arrival curve at n^\dagger
        """
        return self._aggregatedArrivalCurveAtContention

    def processNode(self):
        """Computes all the pipelines of the node
        """
        # Prepare input pipeline
        self.inputPipeline.setInputFlowStates(self._flowStates[FlowStatesDictKeysEnum.input])
        # Execute input pipeline
        self.inputPipeline.processPipeline()
        # Retrieve results
        self._aggregatedArrivalCurveAtContention = self.inputPipeline.getFinalArrivalCurve()
        self._flowStates[FlowStatesDictKeysEnum.afterInputPipeline] = self.inputPipeline.getOutputFlowStates()
        # Prepare contention pipeline
        self.contentionPipeline.setInputAggregate(self._aggregatedArrivalCurveAtContention)
        self.contentionPipeline.setInputFlowStates(self._flowStates[FlowStatesDictKeysEnum.afterInputPipeline])
        # Execute input pipeline
        self.contentionPipeline.processPipeline()
        # Retrieve results
        self.contentionDelayMin, self.contentionDelayMax = self.contentionPipeline.getContentionDelayBounds()
        # Prepare output pipeline
        toPass = self._flowStates[FlowStatesDictKeysEnum.afterInputPipeline]
        self.outputPipeline.setInputFlowStates(toPass)
        self.outputPipeline.setContentionDelayBounds(self.contentionDelayMin, self.contentionDelayMax)
        # Execute output pipeline
        self.outputPipeline.processPipeline()
        # Retrieve results
        self._flowStates[FlowStatesDictKeysEnum.output] = self.outputPipeline.getOutputFlowStates()
        pass


    def addIncomingFlowState(self, flowState: flows.FlowState):
        """ add a flow state to the list of incoming flow states

        Args:
            flowState (flows.FlowState): flow state to add
        """
        self._flowStates[FlowStatesDictKeysEnum.input].append(flowState.copy())

    def getOutputFlowStates(self) -> List[flows.FlowState]:
        """Returns the flow states at n^*

        Returns:
            List[flows.FlowState]: flow states at n^*
        """
        l = list()
        for fs in self._flowStates[FlowStatesDictKeysEnum.output]:
            l.append(fs.copy())
        return l


    def isFinished(self) -> bool:
        """ Check if all pipelines have been computed

        Returns:
            bool: True if the node has been computed (delay bound AND individual flow states)
        """
        return (self.inputPipeline.isFinished() and self.contentionPipeline.isFinished() and self.outputPipeline.isFinished())

    def clearComputations(self):
        """Clears the intermediate results
        """
        self.inputPipeline.clearPipelineComputations()
        self.contentionPipeline.clearPipelineComputations()
        self.outputPipeline.clearPipelineComputations()
        for e in FlowStatesDictKeysEnum:
            self._flowStates[e] = list()
        self._aggregatedArrivalCurveAtContention = None
        self.contentionDelayMax = None
        self.contentionDelayMin = None

from xtfa import networks