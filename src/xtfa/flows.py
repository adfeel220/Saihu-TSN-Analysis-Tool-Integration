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
This module containts the definition of flows and the definition of flow states
"""

import networkx
import copy
from typing import List, Mapping

from xtfa import minPlusToolbox as mpt
from xtfa import unitUtility
from xtfa import clocks

class AtsCurveNotKnown(AssertionError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class CurveNotKnown(AssertionError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class Flow:
    """ Represents a flow. = serie of data units originating from a single application in a single end-system.
    Each data unit follows a directed acyclic graph with a unique graph source (the source of the flow), the packets transporting the data unit may be duplicated/eliminated within the network.

        Attributes:
            name:   the name of the flow
            source: the name of the source = of the output port at the source, not the name of the physical node. #TODO allow a flow to generate from several output ports
            sourceArrivalCurve: the arrival curve of the flow at the exit of the source application (before the output port of the source end-system)
            maxPacketLength:    the maximum length of any packet belonging to the flow
            minPacketLength:    the minimum length of any packet belonging to the flow
            graph:  the graph that any data unit follows in the network. 
                    Vertexes = output port names. 
                    Edges = from one output port name A to another output port name B if the data unit goes through A and then just after through B.
                    In the graph, a vertex that has two outgoing edges (A->B and A->C) represents the fact that multiplexing occurs and the packets are duplicated (the same data unit ends up being transported by several packets, one on the A->B path, the other on the A->C path). In the network switch fabric that contains output ports B and C, packets of the flow are duplicated and forwarded to both output ports B and C.
                    In the graph, elimination of packets (due to network failure OR due to duplicate elimination) ARE NOT REPRESENTED.
                        If X->Z, Y->Z and Z->A in the flow graph, then it DOES NOT NECESSARELY MEAN that the network switch containing output port Z eliminates the duplicate. The rate of the flow in output port Z and output port A MAY BE twice the flow rate.
                        In the present program paradigm, we do not model it by saying that we have two flows, we model it by saying that at Z or A, we may have two FlowState objects, representing the fact that we see packets that transport the data units OF THE SAME FLOW twice.
                        Wether the switch containing port Z, or the one containing port A, or the switch containing any following port performs duplicate elimination depends PIPELINE CONFIGURATION (input and output pipelines) of Z, A or any following port.
            trafficClass: the class of traffic that this flow belongs to
            properties: an additionnal dictionnary to store additionnal proporties of the flow, that are not required for the xTFA, such as deadline, etc.
    """

    name: str
    sources: List[str]
    sourceArrivalCurve: mpt.Curve
    maxPacketLength: int
    minPacketLength: int
    graph: networkx.DiGraph
    trafficClass: str
    properties: dict

    def __init__(self) -> None:
        super().__init__()
        self.properties = dict()
        self.graph = networkx.DiGraph()
        self.sources = list()

    @classmethod
    def getFlowFromWopanetParams(cls, **kargs) -> 'Flow':
        """ Returns a Flow object, configured as per the keywords arguments provided, assuming the keywords are the same as in Wopanet. In particular, the arrival curve is described based on packet length, period and jitter

        Keyword arguments:
            - "name": the name of the flow (str)
            
            - "max-payload":    the maximum size of the packets for this flow (I will not add any overhead) (int)
            - "min-paylaod":    the minimum size of the packets for this flow (I will not add any overhead) (int)
            - "priority":   the traffic class (str)
            - "period": the period of the packets (float)(s)
            - "jitter": the jitter bound of the packets at the application's output (float)(s)
            - any other keyword is stored in the 'properties' dictionnary of the flow

        Returns:
            Flow: the configured instance
        """
        localD = copy.deepcopy(kargs)
        f = cls()
        # pop name and packet lengths to avoid duplicate information to be stored
        f.name = localD.pop("name")
        f.maxPacketLength = unitUtility.readDataUnit(localD.pop("max-payload","1500B"))
        f.minPacketLength = unitUtility.readDataUnit(localD.pop("min-payload","0"))
        #add overhead
        f.maxPacketLength += unitUtility.readDataUnit(localD.pop("overhead","16B"))
        f.minPacketLength += unitUtility.readDataUnit(localD.pop("overhead","16B"))
        #minimum 64 bytes
        f.maxPacketLength = max(f.maxPacketLength, unitUtility.readDataUnit(localD.pop("minimum-packet-size","64B")))
        f.minPacketLength = max(f.minPacketLength, unitUtility.readDataUnit(localD.pop("minimum-packet-size","64B")))
        f.trafficClass = unitUtility.readPriority(localD.pop("priority","0"))
        if(localD.pop("arrival-curve","") == "leaky-bucket"):
            burst = unitUtility.readDataUnit(localD.pop("lb-burst","0"))
            rate = unitUtility.readRate(localD.pop("lb-rate","0"))
            f.sourceArrivalCurve = mpt.LeakyBucket(rate, burst)
        elif "period" in localD.keys():
            f.setLeakyBucketInitialArrivalCurveWithPeriodAndJitter(unitUtility.readTime(localD.pop("period")), unitUtility.readTime(localD.pop("jitter","0")), int(localD.pop("max-simultaneous-packets","1")))
            # here in the future maybe look for other ways to configure the LB, such as having directly the burst/rate as keys in wopanet's xml
        else:
            f.sourceArrivalCurve = mpt.NoCurve()
        f.properties = localD
        return f

    def toWopanetAttributes(self) -> Mapping:
        """ Write the flow as a dictionnary that can be given to the wopanet writter """
        theDict = dict()
        theDict["name"] = self.name
        theDict["max-payload"] = str(self.maxPacketLength // 8)
        theDict["min-payload"] = str(self.minPacketLength // 8)
        theDict["priority"] = self.trafficClass
        if(isinstance(self.sourceArrivalCurve,mpt.LeakyBucket)):
            theDict["arrival-curve"] = "leaky-bucket"
            theDict["lb-burst"] = str(self.sourceArrivalCurve.get_burst())
            theDict["lb-rate"] = str(self.sourceArrivalCurve.get_rate())
        for key in self.properties:
            theDict[key] = self.properties[key]
        return theDict    

    

    def getArrivalCurveAfterOutputPort(self, outputPort: str) -> mpt.Curve:
        """ Returns the arrival curve for this flow at the OUTPUT of the output port 'outputPort'. If several flow states are present, their respective arrival curves are summed to obtain the arrival curve for this flow after the output port

        Args:
            outputPort (str): the output port for which we want the arrival curve of the flow AFTER

        Raises:
            AssertionError: in case xTFA has not computed output port 'outputPort' and hence such arrival curve is not known yet

        Returns:
            mpt.Curve: the arrival curve
        """

        if(outputPort == "source"):
            return self.sourceArrivalCurve
        
        if(outputPort.startswith("ats:")):
            port = outputPort.split("ats:")[1]
            if ("ats-curve" not in self.graph.nodes[port].keys()):
                raise AtsCurveNotKnown("ATS shaped curve not knwon yet at port %s for flows %s. Either ATS does not exists in this port OR it has not been computed yet (case of fix-point computation)" % (port, self.name))
            return self.graph.nodes[port]["ats-curve"]
            
        outgoingEdges = self.graph.out_edges(outputPort)
        # Arrival curves on all the edges are the same cause they all represent the same output port, the same physical link, so take first
        edge = list(outgoingEdges)[0]
        if ("flow_states" not in self.graph.edges[edge].keys()):
            raise CurveNotKnown("Arrival curve for %s is not known yet at port %s" % (self.name, outputPort))
        #Sum all the flow states if we have several
        curve = mpt.NoCurve()
        for fs in self.graph.edges[edge]["flow_states"]:
            curve = curve + fs.arrivalCurve
        return curve

    def registerSpecialInternalCurve(self, type: str, node: str, curve: mpt.Curve):
        self.graph.nodes[node][type] = curve

    def setLeakyBucketInitialArrivalCurveWithPeriodAndJitter(self, period: float, sourceJitter: float, maxSimultaneousPackets: int =1) -> None:
        """Sets the source arrival curve of self using a period-and-jitter description: the packets are supposed to be periodic at the output of the application but they may have a bounded jitter wrt a perfect periodic flow.

        Args:
            period (float): the ideal period of the packets in the flow
            sourceJitter (float): a bound on the jitter that the packets for this flow have at the output of the sending application
            maxSimultaneousPackets (int): a bound on the number of packets that can simultanously together, every period
        """

        sourceJitterService = mpt.BoundedDelayServiceCurve(sourceJitter)
        #This is the ideal arrival curve the flow would have if perfectly periodic
        sourceArrivalCurve = mpt.LeakyBucket(self.maxPacketLength*maxSimultaneousPackets/period, self.maxPacketLength)
        #The deconvolution with the deltaD arrival curve representing the jitter gives the result
        self.sourceArrivalCurve = sourceArrivalCurve / sourceJitterService
    
    def getListLeafVertices(self) -> List[str]:
        ans = list()
        for n in self.graph.nodes:
            if (not (self.graph.out_degree[n])):
                ans.append(n)
        return ans

class FlowState:
    """ Represents the (stationarry) state of a Flow at a specific point in the network

        Attributes:
            flow:   The flow for which the current object represents the state
            atEdge: The name of the graph edge that is the location of the considered FlowState. If A->B is the edge, then this FlowState represents the state of the flow JUST AFTER A. 'source' is reserved to represent the output of the sending application (BEFORE the source end-system output port).
            arrivalCurve:   The arrival curve of the flow at the specific above point.
            flags:  A dictionnary that can be used to store flags for computationnal purposes.
            minDelayFrom:   A dictionnary containing the minimum delay between the entries and the current position of this flow state: 
                If A is an entry of minDelayFrom, then minDelayFrom[A] holds the minimum delay suffered by the flow between the OUTPUT of A and self.atEdge.
                'source' is reserved: minDelayFrom['source'] is the minimum delay suffered between the output of the sending application (BEFORE the source end-system output port) and self.atEdge
            maxDelayFrom:   Same as minDelayFrom, but for maximum delay bounds
            rtoFrom:    Same as above, but for RTO bounds  
    """
    flow: Flow
    atEdge: str
    arrivalCurve: mpt.Curve
    clock: clocks.Clock
    flags: dict
    minDelayFrom: dict
    maxDelayFrom: dict
    rtoFrom: dict


    def __init__(self, flow: Flow) -> None:
        """ Constructor
        Args:
            flow (Flow): the flow for which the current object represent a state (a situation of the flow) at some point in the network
        """
        super().__init__()
        self.flow = flow
        self.arrivalCurve = mpt.NoCurve()
        #initialize the dictionnaries with at least the 'source' key
        self.flags = dict()
        self.clock = clocks.Clock("H")
        self.minDelayFrom = dict()
        self.maxDelayFrom = dict()
        self.rtoFrom = dict()
        self.minDelayFrom["source"] = 0
        self.maxDelayFrom["source"] = 0
        self.rtoFrom["source"] = 0
        self.atEdge = ""

    def isEqualFlowByNameAllKeysMustMatch(self, o: 'FlowState', **kargs) -> bool:
        """ Checks equality of flow states. Answer True if all the following conditions are met:
                - the name of the flow associated with this flow state (self.flow.name) is the same as the name of the flow associated with the other flow state (o.flow.name). Warning: no other field of self.flow and o.flow is checked, the name of the flow is here supposed to uniquely identify the Flow object.
                - both flow states are at the same edge (that is self.atEdge == o.atEdge)
                - both flow states have the same arrival curve (tested using the mpt equality definition)
                - both flow states have EXACTLY the same minDelayFrom/maxDelayFrom/rtoFrom dictionnaries. In particular, it means that they must have the same keys.

        Args:
            o (FlowState): the other flow state to test equality with

        Returns:
            bool: if content of flow states is the same, False otherwise
        """
        matchDmax = kargs.get("match_d_max", False)
        if(self.flow.name != o.flow.name):
            return False
        if(self.atEdge != o.atEdge):
            return False
        if(not (self.arrivalCurve == o.arrivalCurve)):
            return False
        if(matchDmax):
            if 'source' not in o.maxDelayFrom.keys():
                return False
            if (self.maxDelayFrom['source'] != o.maxDelayFrom['source']):
                return False
        return True

    def addDelayFromEntry(self, fromEntryName: str) -> None:
        """ Add a 'From' entry into the dictionnary of delay bounds. Min and Max delays at this 'from' entry are initialized at 0.0

        Args:
            fromEntryName (str): the name of the node that is a reference. The origin of the delay is the OUTPUT of the node. 'source' is reserved to represent the output of the source application (ie before the output port of the source end-system).
        """
        self.minDelayFrom[fromEntryName] = 0.0
        self.maxDelayFrom[fromEntryName] = 0.0

    def addRtoFromEntry(self, fromEntryName: str) -> None:
        """ Add a 'From' entry into the dictionnary of the RTO bounds. The RTO is initialized at 0 for this entry.

        Args:
            fromEntryName (str): the name of the node that is a reference. The origin of the RTO is always the OUTPUT (or for a source, the internal application) of the node. 'source' is reserved to represent the output of the source application (ie before the output port of the source end-system).
        """
        self.rtoFrom[fromEntryName] = 0.0

    def addDelaysToDisctionnaryWithoutChangingRto(self, maxDelay: float, minDelay=0.0) -> None:
        """Add the min/max delay bound to all the entries in the min/max dictionnary. This DOES NOT change the arrival curve contained in the state. It DOES NOT change the RTO either.

        Args:
            maxDelay (float): maximum delay suffered to add
            minDelay (float, optional): minimum delay suffered to add. Defaults to 0.0.
        """
        for k in self.minDelayFrom.keys():
            self.minDelayFrom[k] += minDelay
        for k in self.maxDelayFrom.keys():
            self.maxDelayFrom[k] += maxDelay

    def addSufferedDelay(self, maxDelay: float, minDelay=0.0, **kargs) -> None:
        """ Change the current FlowState min/max/rto informations to include the fact that the flow suffered a variable delay. 
        Set jitter_fifo = False in the kargs to notify that the suffered jitter is non FIFO (by default the jitter is assumed to be FIFO)
        This DOES NOT change the arrival curve of the flow state, don't forget to update the arrival curve as well.

        Args:
            maxDelay (float): the maximum delay suffered
            minDelay (float, optional): the minimum delay suffered. Defaults to 0.0.
        """
        jitterFifo = kargs.get("jitter_fifo", True)
        self.addDelaysToDisctionnaryWithoutChangingRto(maxDelay, minDelay)
        for k in self.rtoFrom.keys():
            if ( (self.rtoFrom[k] > 0.0) or (not jitterFifo)):
                #EITHER RTO was already strictly positive, then any jitter (even FIFO) increases RTO
                #OR the jitter was non-FIFO, and then the RTO is increased for all entries in the dictionnary
                self.rtoFrom[k] += (maxDelay - minDelay)

    def copy(self) -> 'FlowState':
        """Returns a copy of self. Returns a FlowState with the same flow attribute (reference to the same object Flow), and the rest of the attributes are deepcopied.

        Returns:
            FlowState: a copy of self
        """
        
        f = FlowState(self.flow)
        f.arrivalCurve = copy.deepcopy(self.arrivalCurve)
        f.minDelayFrom = copy.deepcopy(self.minDelayFrom)
        f.maxDelayFrom = copy.deepcopy(self.maxDelayFrom)
        f.rtoFrom = copy.deepcopy(self.rtoFrom)
        f.atEdge = copy.deepcopy(self.atEdge)
        f.flags = copy.deepcopy(self.flags)
        f.clock = copy.deepcopy(self.clock)
        return f

    def toStringWithoutAt(self, **kargs) -> str:
        """ Generates a string to represent the FlowState self, without prompting the atEdge information

        Returns:
            str: a string to represent the flow state
        """
        d = kargs.get("digits", 2)
        s = "%s D_max=%.*e D_min=%.*e RTO=%.*e (s)(from source)" % (self.arrivalCurve.__str__(**kargs), d, self.maxDelayFrom["source"], d, self.minDelayFrom["source"], d, self.rtoFrom["source"])
        return s

    def toString(self, **kargs) -> str:
        s = "%s @ %s" % (self.flow.name, self.atEdge)
        return s + " " + self.toStringWithoutAt(**kargs)

    def getCopyInternalArrivalCurve(self) -> mpt.Curve:
        """Returns a copy of the arrival curve, to which we add the burst penalty of the flag internal-burst-penalty if present

        Returns:
            mpt.Curve: the arrival Curve, perhaps worsens by a burst penalty if such a flag is present in the flow state flags
        """
        retC = copy.deepcopy(self.arrivalCurve)
        if("internal-penalty" in self.flags.keys()):
            penaltyC = self.flags["internal-penalty"]
            return (retC + penaltyC)
        return (retC)

    def changeClock(self, newClock: clocks.Clock):
        self.clock = newClock
        if (self.clock.equals(newClock)):
            return
        self.arrivalCurve = clocks.Clock.worsen_arrival_curve(self.arrivalCurve)
        for key in self.minDelayFrom.keys():
            self.minDelayFrom[key] = clocks.Clock.worsen_delay_lower_bound(self.minDelayFrom[key])
        for key in self.maxDelayFrom.keys():
            self.maxDelayFrom[key] = clocks.Clock.worsen_delay_upper_bound(self.maxDelayFrom[key])
        for key in self.rtoFrom.keys():
            if(self.rtoFrom[key]>0):
                #We only do this if the RTO is > 0 because otherwise we're simply FIFO and we remain FIFO
                self.rtoFrom[key] = clocks.Clock.worsen_delay_upper_bound(self.rtoFrom[key])
        


