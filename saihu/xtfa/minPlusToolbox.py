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
This module contains a toolbox for classical min-plus curves and min-plus operations
"""

import copy
import itertools
from typing import List, Tuple, Union
import numpy as np
import matplotlib.pyplot as plt
import math

def copydoc(fromfunc, sep="\n"):
    """
    Decorator: Copy the docstring of `fromfunc`
    """
    def _decorator(func):
        sourcedoc = fromfunc.__doc__
        if func.__doc__ == None:
            func.__doc__ = sourcedoc
        else:
            func.__doc__ = sep.join([sourcedoc, func.__doc__])
        return func
    return _decorator

#EXCEPTIONS

class ArrivalCurveNotDefinedForThisValue(Exception):
    def __init__(self,s_value,**kargs):
        self._s_value = s_value
        self._string = kargs.get("string","The arrival curve is not defined for value %e" % (self._s_value))
    def __str__(self):
        return(self._string)
    def getSValue(self):
        return self._s_value

class LocallyUnstableSystem(Exception):
    def __str__(self):
        return("Cannot compute delay bound because the system bounds are unstable: the long-term rate of the service curve is lower than the long-term rate of the arrival curve")

#CURVES
class Curve:
    '''
    General interface for arrival curves
    '''
    _name: str

    def __init__(self, **kargs):
        self._name = kargs.get("name","")

    def set_name(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name
    
    def ceil_bursts(self) -> None:
        raise NotImplementedError()

    def __mul__(self, curve: 'Curve') -> 'Curve':
        """ Min-Plus convolution of two curves

        Arguments:
            curve {Curve} -- the curve with which to do the min-plus convolution
        
        Returns:
            Curve -- self (min-plus convolution) serviceCurve
        """
        return NotImplemented
    
    def __mod__(self, sc: 'Curve') -> float:
        """ (Positive) Maximal horizontal distance between self as arrival curve et sc as service curve, or 0 if self is always left

        Arguments:
            sc {Curve} -- the service curve
        
        Returns:
            float -- h(self,sc), maximum horizontal distance
        """
        return NotImplemented

    def get_max_vertical_distance(self, serviceCurve: 'Curve') -> float:
        return NotImplemented


    def worsen_arrival_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        """Worsen the arrival curve because we change the observing clock
        When the network is not synchronized

        Args:
            rho (float): stability bound of the clocks in the network
            eta (float): time-jitter bound of the clocks in the network

        Returns:
            Curve: the worsened curve
        """
        return NotImplemented
    
    def worsen_arrival_curve_due_to_clock_sync(self, rho: float, eta: float, delta:float) -> 'Curve':
        """Worsen the arrival curve because we change the observing clock.
        When the network is synchronized.

        Args:
            rho (float): stability bound of the clocks in the network
            eta (float): time-jitter bound of the clocks in the network
            delta (float): synchronization precision

        Returns:
            Curve: the worsened curve
        """
        return NotImplemented


    def __add__(self, curve: 'Curve') -> 'Curve':
        """ Addition of two curves

        Arguments:
            curve {Curve} -- the curve to add to self
        
        Returns:
            Curve -- the addition self + curve
        """
        return NotImplemented
    
    def __truediv__(self, curve: 'Curve') -> 'Curve':
        """ Min-plus deconvolution of 'self' by 'curve'

        Args:
            curve (Curve): the curve on the right of the deconvolution

        Returns:
            Curve: the result of the min-plus deconvolution
        """
        return NotImplemented

    def __eq__(self, o: object) -> bool:
        """Checks the equality between two curves
        """
        return False

    def is_dominating(self, other: 'Curve') -> bool:
        """ Returns True if self is dominating other. 
            That is for all t>=0, self(t) >= other(t)

            in convex piecewise linear curve, self dominates other if self * other is the same as other
        """
        return (self * other).__eq__(other)

    def get_value_at_s(self, s: float) -> float:
        """Returns the value of the arrival curve at s - if it exists
        
        Arguments:
            s {float} -- the value at which to compute the arrival curve
        
        Returns:
            float -- the value of the arrival curve at s - if it exists
        """
        return NotImplemented

    def get_value_at_s_plus(self, s: float) -> float:
        """Returns lim_{x->s,x>s} of the value of the arrival curve
        
        Arguments:
            s {float} -- s
        
        Returns:
            float -- lim_{x->s,x>s}(alpha(x))
        """
        return NotImplemented
    
    def get_value_at_s_moins(self, s: float) -> float:
        """Returns lim_{x->s,x<s} of the value of the arrival curve - if it exists
        
        Arguments:
            s {float} -- s
        Returns:
            float -- lim_{x->s,x<s}(alpha(x)) 
        """
        return NotImplemented

    def return_curve_with_packetization(self, packetMaxSize: int, **kargs) -> 'Curve':
        """Returns a new curve that is representing self, whose burst has been increased due to a packetizer

        Args:
            packetMaxSize (int): the maximum packet size for the flow packetized
            **link_capacity (float): (optional) the capacity of the input link to which the packetizer is connected

        Returns:
            Curve: the arrival curve with augmented burst due to packetization
        """
        return NotImplemented

    def get_packetization_penalty_curve(self, packetMaxSize: int, **kargs) -> 'Curve':
        """ Returns only the penalty due to packetization.
        Ie self.addPacketizationEffectReturnNewCurve() = self + self.getPacketizationPenaltyCurve()
        """
        raise NotImplementedError()

    def __str__(self, **kargs) -> str:
        return "Curve"

    def get_interesting_xmax_for_plot(self) -> float:
        return 10

    def to_leaky_bucket_with_minimum_burst(self) -> 'LeakyBucket':
        """Returns the leaky-bucket arrival curve that 
            - dominates the curve self
            - is not dominated
            - has the minimum burst among the leaky-bucket satifying the above conditions

        Returns:
            LeakyBucket: the leaky bucket meeting the above rules
        """
        return NotImplemented

    def to_leaky_bucket_with_minimum_rate(self) -> 'LeakyBucket':
        """Returns the leaky-bucket arrival curve that 
            - dominates the curve self
            - is not dominated
            - has the minimum rate among the leaky-bucket satifying the above conditions

        Returns:
            LeakyBucket: the leaky bucket meeting the above rules
        """
        return NotImplemented
    
    def worsen_service_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        return NotImplemented

    def worsen_service_curve_due_to_clock_sync(self, rho: float, eta: float, delta: float) -> 'Curve':
        return NotImplemented

class NoCurve(Curve):
    '''
    Arrival curve of a 'no flow'
    '''

    def __init__(self, **kargs) -> None:
        super(NoCurve,self).__init__(**kargs)
    
    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        return float(0)

    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self, s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        return float(0)

    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        return float(0)

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:
        return float(0)

    @copydoc(Curve.__mul__)
    def __mul__(self, o: Curve) -> Curve:
        if (isinstance(o, Curve)):
            return NoCurve()
        raise TypeError("unsupported operand type(s) for * or mul(): %s and %s" % (type(self).__name__, type(o).__name__))

    @copydoc(Curve.__add__)
    def __add__(self, o: Curve) -> Curve:
        if(isinstance(o,Curve)):
            return copy.deepcopy(o)
        raise TypeError("unsupported operand type(s) for + or add(): %s and %s" % (type(self).__name__, type(o).__name__))

    def __eq__(self, o: object) -> bool:
        if(isinstance(o, NoCurve)):
            return True
        if(isinstance(o, Curve)):
            return o.__eq__(self)
        return super().__eq__(o)

    @copydoc(Curve.return_curve_with_packetization)
    def return_curve_with_packetization(self, packetMaxSize: int, **kargs) -> Curve:
        return NoCurve()
    
    @copydoc(Curve.get_packetization_penalty_curve)
    def get_packetization_penalty_curve(self, packetMaxSize: int, **kargs) -> 'Curve':
        return NoCurve()

    def __str__(self, **kargs):
        return "NoCurve"
    
    def to_leaky_bucket_with_minimum_burst(self) -> 'LeakyBucket':
        return LeakyBucket(0.0, 0.0)

    def to_leaky_bucket_with_minimum_rate(self) -> 'LeakyBucket':
        return LeakyBucket(0.0, 0.0)
        
    def worsen_arrival_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        return NoCurve()
    
    def worsen_arrival_curve_due_to_clock_sync(self, rho: float, eta: float, delta: float) -> 'Curve':
        return NoCurve()

class InfiniteCurve(Curve):
    '''
    this corresponds to delta_0
    '''

    def __init__(self, **kargs):
        super().__init__(**kargs)
    
    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        if(s <= 0):
            return float(0)
        return float('inf')

    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self, s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        return float('inf')

    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        return float('inf')

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:
        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))

    @copydoc(Curve.__mul__)
    def __mul__(self, o: Curve) -> Curve:
        return copy.deepcopy(o)

    @copydoc(Curve.__add__)
    def __add__(self, o: Curve) -> Curve:
        return InfiniteCurve()

    def __eq__(self, o: object) -> bool:
        if(isinstance(o, InfiniteCurve)):
            return True
        return False

    @copydoc(Curve.return_curve_with_packetization)
    def return_curve_with_packetization(self, packetMaxSize: int, **kargs) -> Curve:
        return InfiniteCurve()
    
    @copydoc(Curve.get_packetization_penalty_curve)
    def get_packetization_penalty_curve(self, packetMaxSize: int, **kargs) -> 'Curve':
        #There is no penalty to add to an already-infinite arrival curve"
        return NoCurve()
    
    def __str__(self, **kargs):
        return "InfinitveCurve"
    
    def worsen_arrival_curve_due_to_clock_sync(self, rho: float, eta: float, delta: float) -> 'Curve':
        return InfiniteCurve()
    
    def worsen_arrival_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        return InfiniteCurve()

class LeakyBucket(Curve):
    '''
    Leaky-bucket arrival curve: alpha(s) = s*self._rate + self.burst
    '''

    def __init__(self, rate: float, burst: float, **kargs) -> None:
        super(LeakyBucket,self).__init__(**kargs)
        self._burst = burst
        self._rate = rate
    
    def ceil_bursts(self) -> None:
        self._burst = math.ceil(self._burst)

    def get_rate(self) -> float:
        return self._rate

    def get_burst(self) -> float:
        return self._burst
    
    def is_same_lb(self, lb: 'LeakyBucket') -> bool:
        return ((self._burst == lb._burst) and (self._rate == lb._rate))
    
    def yToX(self, y:float)->float:
        if (y<= self.get_burst()):
            return 0
        return ((y-self.get_burst())/self.get_rate())
    
    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        if(s==0):
            return 0
        return self.get_value_at_s_plus(s)

    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        return self._burst + float(s) * self._rate
    
    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self, s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        return self.get_value_at_s_plus(s)

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:
        if( isinstance(serviceCurve, NoCurve) ):
            raise LocallyUnstableSystem()
        if( isinstance(serviceCurve, RateLatencyServiceCurve) ):
            if(self.get_rate() > serviceCurve.get_rate()):
                raise LocallyUnstableSystem()
            return (serviceCurve.get_latency() + self.get_burst() / serviceCurve.get_rate())
        if(isinstance(serviceCurve, MaxOfRateLantencies)):
            m = serviceCurve.y_to_x(self.get_burst())
            for x2 in serviceCurve._discontinuities:
                x1 = self.yToX(serviceCurve.get_value_at_s(x2))
                m = max(m, x2-x1)
            return m
        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))

    def get_max_vertical_distance(self, serviceCurve: Curve) -> float:
        if(isinstance(serviceCurve, RateLatencyServiceCurve)):
            return (self._burst + (self._rate * serviceCurve.get_latency()))
        if(isinstance(serviceCurve, BoundedDelayServiceCurve)):
            return (self.get_value_at_s_plus(serviceCurve.getDelay()))
        if(isinstance(serviceCurve, DGVBR)):
            if(serviceCurve.get_gvbr().get_first_lb().get_rate() < self.get_rate()):
                raise AssertionError("The current min plus toolbox cannot compute the highest vertical distance of LB versus GVBR when the first LB in the GVBR has a rate striclty lower than our rate")
            return self.get_value_at_s(serviceCurve.get_latency())
        if(isinstance(serviceCurve, LeakyBucket)):
            if(serviceCurve.get_rate() < self.get_rate()):
                raise LocallyUnstableSystem()
            return (self.get_burst() - serviceCurve.get_burst())
        raise TypeError("unsupported type(s) for getMaxVerticalDistance: %s and %s" % (type(self).__name__, type(serviceCurve).__name__))

    def compute_intersection(self, lbArrival: 'LeakyBucket') -> Tuple[float, bool]:
        """Computes the intersection point with another leaky-bucket arrival curbe
        
        Arguments:
            lbArrival {LeakyBucket} -- the leaky bucket arrival curve whith which to compute the 
        
        Returns:
            tuple -- (x_inter,belowBefore) : with x_inter, the intersection point between the two leaky buckets, or -1 if they have the same rate
                                                belowBefore is true if self is before the intersection, false otherwise. If x_inter = -1, belowBefore is true if self is below lbArrival everywhere.
        """
        
        if(self._rate == lbArrival._rate):
            return (-1, self._burst < lbArrival._burst)
        x_intersection = (lbArrival._burst - self._burst)/(self._rate - lbArrival._rate)
        if(x_intersection <= 0):
            #they intersect in the negative domain, so in the positive (utile) domain, one of them dominates the other
            #the one that has the smallest rate is always below
            return (-1, self._rate < lbArrival._rate)
        #x positive, self is below before if it has a higher rate
        return (x_intersection, (self._rate > lbArrival._rate))

    def __mul__(self, o: Curve) -> Curve:
        if(isinstance(o,NoCurve)):
            return NoCurve
        if(isinstance(o,LeakyBucket)):
            return GVBR([copy.deepcopy(self),copy.deepcopy(o)]).simplify()
        if(isinstance(o,GVBR)):
            return (o * self)
        if(isinstance(o,BoundedDelayServiceCurve)):
            return DGVBR(o.getDelay(), GVBR([copy.deepcopy(self)]))
        #TODO here
        raise TypeError("unsupported operand type(s) for * or mul(): %s and %s" % (type(self).__name__, type(o).__name__))
    
    def __add__(self, curve: Curve) -> Curve:
        if(isinstance(curve, LeakyBucket)):
            return LeakyBucket(self._rate + curve._rate, self._burst + curve._burst)
        if(isinstance(curve, NoCurve)):
            return LeakyBucket(self._rate, self._burst)
        if(isinstance(curve, GVBR)):
            return (curve + self)
        raise TypeError("unsupported operand type(s) for + or add(): %s and %s" % (type(self).__name__, type(curve).__name__))

    @copydoc(Curve.__truediv__)
    def __truediv__(self, curve: Curve) -> Curve:
        if (isinstance(curve, BoundedDelayServiceCurve)):
            return LeakyBucket(self._rate, self._burst + self._rate * curve.getDelay())
        if (isinstance(curve, RateLatencyServiceCurve)):
            return LeakyBucket(self._rate, self._burst + self._rate * curve.get_latency())
        raise TypeError("unsupported operand type(s) for * or mul(): %s and %s" % (type(self).__name__, type(curve).__name__))

    def __eq__(self, o: object) -> bool:
        if(isinstance(o,NoCurve)):
            return ((self._rate == 0.0) and (self._burst == 0.0))
        if(isinstance(o, LeakyBucket)):
            return ((self._rate == o._rate) and (self._burst == o._burst))
        if(isinstance(o, Curve)):
            return o.__eq__(self)
        return super().__eq__(o)


    @copydoc(Curve.get_packetization_penalty_curve)
    def get_packetization_penalty_curve(self, packetMaxSize: int, **kargs) -> 'Curve':
        if ("link_capacity" in kargs.keys()):
            c = kargs.get("link_capacity")
            if (c > self._rate):
                #link capacity provided, can use better result 
                # see thm1, doi:10.1109/RTSS46320.2019.00035
                return LeakyBucket(0.0, (self._rate / c) * packetMaxSize)
                #else: in any case the burst increase cannot be more than packetMaxSize, so proceed to default return
        #link capacity not provided, traditionnal result
        return LeakyBucket(0.0, packetMaxSize)

    @copydoc(Curve.return_curve_with_packetization)
    def return_curve_with_packetization(self, packetMaxSize: int, **kargs) -> Curve:
        return self + self.get_packetization_penalty_curve(packetMaxSize, **kargs)

    def __str__(self, **kargs) -> str:
        return "LB" + self.rate_burst_string_pair(**kargs) + "(bit/s,bit)"
    
    def rate_burst_string_pair(self, **kargs) -> str:
        digits = kargs.get("digits", 2)
        return ("(%.*e,%.*e)" % (digits, self._rate, digits,  self._burst))

    def get_interesting_xmax_for_plot(self) -> float:
        return (2*self.get_burst() / self.get_rate())

    def to_leaky_bucket_with_minimum_burst(self) -> 'LeakyBucket':
        return self

    def to_leaky_bucket_with_minimum_rate(self) -> 'LeakyBucket':
        return self
    
    def worsen_arrival_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        newRate = rho*self.get_rate()
        newBurst = self.get_burst() + self.get_rate() * eta
        return LeakyBucket(newRate,newBurst)
    
    def worsen_arrival_curve_due_to_clock_sync(self, rho: float, eta: float, delta: float) -> 'Curve':
        firstLb = self.worsen_arrival_curve_due_to_clock_async(rho,eta)
        secondBurst = self.get_burst() + 2 * self.get_rate() * delta
        return (firstLb * LeakyBucket(self.get_rate(), secondBurst))
        
class GVBR(Curve):
    """Generalized VBR arrival curve - see example and proposition 1.4.1 of the network calculus book
        A convolution of 2 or more leaky-bucket arrival curves   
    """
    _listLb: List[LeakyBucket]

    def __init__(self, *args, **kargs) -> None:
        super(GVBR,self).__init__(**kargs)
        self._listDiscontinuities = list()
        self._listLbIndexes = list()
        if(args):
            self._listLb = self.copy_remove_duplicates(args[0])
            self.__update_discontinuityLists()
        else:
            self._listLb = list()
            
    def get_burst(self) -> float:
        """Return the burst of the most bursty leaky-bucket

        Returns:
            float: The burst of the most bursty leaky-bucket
        """
        return self._getLastLb().get_burst()
    
    def simplify(self) -> Curve:
        """Simplify to a leaky bucket object if self is composed of a unique leakybucket

        Returns:
            Curve: either self or its unique leaky bucket if self is made of one unisue LB
        """
        if(not(self._listDiscontinuities)):
            return self._listLb[self._listLbIndexes[0]]
        return self
    
    def copy_remove_duplicates(self, initialList: List[LeakyBucket]) -> List[LeakyBucket]:
        retList = list()
        for lb in initialList:
            found = False
            for lbb in retList:
                if lb.is_same_lb(lbb):
                    found = True
            if(not found):
                retList.append(copy.deepcopy(lb))
        return retList

    def y_to_x(self, y:float)->float:
        return (max(lb.yToX(y) for lb in self._listLb))
        
    def __mul__(self, o: Curve) -> Curve:
        if(isinstance(o,GVBR)):
            return GVBR(copy.deepcopy(self._listLb) + copy.deepcopy(o._listLb)).simplify()
        if(isinstance(o,LeakyBucket)):
            l = copy.deepcopy(self._listLb)
            l.append(copy.deepcopy(o))
            return GVBR(l).simplify()
        if(isinstance(o,NoCurve)):
            return NoCurve()
        raise TypeError("unsupported operand type(s) for * or mul(): %s and %s" % (type(self).__name__, type(o).__name__))

    @copydoc(Curve.__truediv__)
    def __truediv__(self, curve: Curve) -> Curve:
        if (isinstance(curve, BoundedDelayServiceCurve)):
            newList = [lb / curve for lb in self._listLb]
            return GVBR(newList)

    def __add__(self, o: Curve) -> Curve:
        if(isinstance(o,NoCurve)):
            return copy.deepcopy(self)
        if(isinstance(o,LeakyBucket)):
            return self + GVBR([o])
        if(isinstance(o,GVBR)):
            return (self.__add_with_GVBR(o))
        raise TypeError("unsupported operand type(s) for + or add(): %s and %s" % (type(self).__name__, type(o).__name__))

    @copydoc(Curve.return_curve_with_packetization)
    def return_curve_with_packetization(self, packetMaxSize: int, **kargs) -> Curve:
        newLbList = list()
        for lb in self._listLb:
            # add packetization effect to each of the leaky-buckets
            newLbList.append(lb.return_curve_with_packetization(packetMaxSize, **kargs))
        #create a new GVBR flow from this new list of leaky buckets
        return GVBR(newLbList).simplify()

    def _getActiveLBJustBeforeX(self, x: float) -> int:
        if x in self._listDiscontinuities:
            index = self._listDiscontinuities.index(x)
            return self._listLb[self._listLbIndexes[index]]
        return self._get_active_lb_at_s(x)
    
    def _getLastLb(self) -> Union[LeakyBucket,NoCurve]:
        if(not self._listLb):
            return NoCurve()
        if(not self._listLbIndexes):
            return self._listLb[0]
        return self._listLb[self._listLbIndexes[-1]]

    def _getFirstLb(self) -> Curve:
        if(not self._listLb):
            return NoCurve()
        if(not self._listLbIndexes):
            return self._listLb[0]
        return self._listLb[self._listLbIndexes[0]]
    
    def to_leaky_bucket_with_minimum_rate(self) -> 'LeakyBucket':
        return self._getLastLb().to_leaky_bucket_with_minimum_rate()
    
    def to_leaky_bucket_with_minimum_burst(self) -> 'LeakyBucket':
        return self._getFirstLb().to_leaky_bucket_with_minimum_burst()


    def __add_with_GVBR(self, other: 'GVBR') -> 'GVBR':
        new_lb_list = list()
        discontinuitySet = set(self._listDiscontinuities)
        discontinuitySet = discontinuitySet.union(other._listDiscontinuities)
        
        discontinuities = list(discontinuitySet)
        discontinuities.sort()

        for discont in discontinuities:
            #Two leaky buckets valid just before the discontinuity...
            lb0 = self._getActiveLBJustBeforeX(discont)
            lb1 = other._getActiveLBJustBeforeX(discont)
            #sum them
            lbsum = lb0 + lb1
            #add result to new lb list
            new_lb_list.append(lbsum)
        #Now, add the last segment (after all the discontinuity)
        new_lb_list.append(self._getLastLb() + other._getLastLb())

        retObj = GVBR(new_lb_list)
        return(retObj)

    def get_discontinuity_list(self):
        return self._listDiscontinuities
    
    def get_index_list(self):
        return self._listLbIndexes

    def get_first_left_lb_index(self) -> int:
        candidateI = 0
        candidate = self._listLb[0]
        for j in range(len(self._listLb) - 1):
            iI = j + 1
            lb = self._listLb[iI]
            if (lb.get_burst() <= candidate.get_burst()):
                if (lb.get_burst() < candidate.get_burst()):
                    candidateI = iI
                    candidate = self._listLb[candidateI]
                    continue
                if (lb.get_rate() < candidate.get_rate()):
                    candidateI = iI
                    candidate = self._listLb[candidateI]
        return candidateI

    def ceil_bursts(self) -> None:
        for lb in self._listLb:
            lb.ceil_bursts()

    def get_lb_with_smallest_rate(self, m: List[int]):
        candidate = m[0]
        for current in m:
            if (self._listLb[current].get_rate() < self._listLb[candidate].get_rate()):
                candidate = current
        return candidate
    
    def get_first_lb(self) -> LeakyBucket:
        return self._listLb[self.get_first_left_lb_index()]

    def __update_discontinuityLists(self):
        self._listDiscontinuities.clear()
        self._listLbIndexes.clear()

        discontinuityDictionnary = dict()
        dominationDictionnary = dict()

        #select two leaky buckets
        for indexes in itertools.combinations(range(len(self._listLb)),r=2):
            lb0 = self._listLb[indexes[0]]
            lb1 = self._listLb[indexes[1]]
            #compute intersection
            (intersection,lb0Belowlb1Before) = lb0.compute_intersection(lb1)
            if(intersection < 0):
                #no intersection, we have a domination
                dominant = None
                domine = None
                if(lb0Belowlb1Before):
                    dominant = indexes[1]
                    domine = indexes[0]
                else:
                    dominant = indexes[0]
                    domine = indexes[1]
                if(dominant not in dominationDictionnary.keys()):
                    dominationDictionnary[dominant] = list()
                dominationDictionnary[dominant].append(domine)
            else:
                before = None
                after = None
                if(lb0Belowlb1Before):
                    before = indexes[0]
                    after = indexes[1]
                else:
                    before = indexes[1]
                    after = indexes[0]
                #Intersection, we add it to the discontinuity dictionnary if not already existing
                if(intersection not in discontinuityDictionnary.keys()):
                    # We might have several intersections at the same point
                    # yeah, it's corner case, and yeah, real-number equality and so and so
                    # but here, let's have a workaround by storing all the intersections situations and then
                    # finding the true (min) instersection
                    discontinuityDictionnary[intersection] = list()

                discontinuityDictionnary[intersection].append((before, after))

        #Now, we can change our data into lists
        #We first need to know which arrival curve is below all others at beginning.
        sorted_keys = list(discontinuityDictionnary.keys())
        sorted_keys.sort()
        #get first LB
        currentBelow = self.get_first_left_lb_index()
        #Then we start building the list
        for current_intersection in sorted_keys:
            chainFinished = False
            foundNext = False
            mNext = currentBelow
            while(not chainFinished):
                #If the lb below before the intersection is the lb currently below, process:
                possibleNexts = list()
                for possibleIntersection in discontinuityDictionnary[current_intersection]:
                    if(possibleIntersection[0]==mNext):
                        possibleNexts.append(possibleIntersection[1])
                if(possibleNexts):
                    foundNext = True
                    mNext = self.get_lb_with_smallest_rate(possibleNexts)
                else: 
                    chainFinished = True
            if(foundNext):
                self._listLbIndexes.append(currentBelow)
                self._listDiscontinuities.append(current_intersection)
                currentBelow = mNext
        #And at the end add the current below as the last lb below
        self._listLbIndexes.append(currentBelow)
    

    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        if(s==0):
            return 0
        return self.get_value_at_s_plus(s)

    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self, s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        return self.get_value_at_s_plus(s)
    

    def _get_active_lb_at_s(self, s: float) -> Curve:
        if(not self._listLb):
            return NoCurve()
        if(not self._listDiscontinuities):
            return (self._listLb[self._listLbIndexes[0]])
        i = -1
        val = 0
        while(val < s):
            i += 1
            if(i >= len(self._listDiscontinuities)):
                break
            val = self._listDiscontinuities[i]
        #We have identified the leaky bucket "in action" at s, get its value
        if (i<0):
            i = 0
        return (self._listLb[self._listLbIndexes[i]])


    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        return self._get_active_lb_at_s(s).get_value_at_s_plus(s)
    
    def get_delay_bound_location(self, serviceCurve: 'RateLatencyServiceCurve') -> Tuple[float,float,float]:
        i=0
        x=0
        lb=self._listLb[self._listLbIndexes[i]]
        while((i < len(self._listDiscontinuities)) and (lb.get_rate() > serviceCurve.get_rate())):
            x = self._listDiscontinuities[i]
            i += 1
            lb=self._listLb[self._listLbIndexes[i]]
        if(lb.get_rate() > serviceCurve.get_rate()):
            raise LocallyUnstableSystem()
        y = float(self.get_value_at_s_plus(x))
        if(isinstance(serviceCurve,RateLatencyServiceCurve)):
            x_2 = serviceCurve.get_latency() + (y/serviceCurve.get_rate())
            self.x_2 = x_2
            self.x = x
            return (x,x_2,y)

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:

        if(isinstance(serviceCurve,RateLatencyServiceCurve)):
            x, x_2, y = self.get_delay_bound_location(serviceCurve)
            return (x_2 - x)

        if (isinstance(serviceCurve,BoundedDelayServiceCurve)):
            return serviceCurve.getDelay()
        
        if (isinstance(serviceCurve,MaxOfRateLantencies)):
            m = 0
            for x1 in [0] + self._listDiscontinuities:
                x2 = serviceCurve.y_to_x(self.get_value_at_s_plus(x1))
                m = max(m,x2-x1)
            for x2 in serviceCurve._discontinuities:
                x1 = self.y_to_x(serviceCurve.get_value_at_s(x2))
                m = max(m,x2-x1)
            return m

        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))

    def get_max_vertical_distance(self, serviceCurve: Curve) -> float:
        if(isinstance(serviceCurve,RateLatencyServiceCurve)):
            candidateBacklog = self.get_value_at_s_plus(0.0)
            for x in self._listDiscontinuities + [serviceCurve.get_latency()] :
                #the max vertical distance is necessarely at a discontinuity (either one of ours OR the rate-latency discontinuity)
                thisBacklog = (self.get_value_at_s_plus(x) - serviceCurve.get_value_at_s_plus(x))
                if(thisBacklog > candidateBacklog):
                    candidateBacklog = thisBacklog
            return candidateBacklog
        if(isinstance(serviceCurve, BoundedDelayServiceCurve)):
            return (self.get_value_at_s_plus(serviceCurve.getDelay()))

        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))


    def get_interesting_xmax_for_plot(self) -> float:
        if(self._listDiscontinuities):
            return 1.5*self._listDiscontinuities[-1]
        return self._listLb[self._listLbIndexes[0]].get_interesting_xmax_for_plot()
    
    def __eq__(self, o: object) -> bool:
        if(isinstance(o, NoCurve) or isinstance(o, LeakyBucket)):
            for i in self._listLbIndexes:
                lb = self._listLb[i]
                if (lb != o):
                    return False
            return True
        if(isinstance(o, GVBR)):
            if (set(self._listDiscontinuities) != set(o._listDiscontinuities)):
                return False
            # same size for discontinuities, so same size as well for indexes
            for i in range(len(self._listLbIndexes)):
                if(self._listLb[self._listLbIndexes[i]] != o._listLb[o._listLbIndexes[i]]):
                    return False
            return True
        if(isinstance(o, Curve)):
            return o.__eq__(self)
        return super().__eq__(o)

    def __str__(self, **kargs) -> str:
        s = "GVBR"
        for i in self._listLbIndexes:
            s += self._listLb[i].rate_burst_string_pair(**kargs)
        s += "(bit/s,bit)"
        return s
    
    def worsen_arrival_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        newCurve = InfiniteCurve()
        for mlb in self._listLb:
            new_mlb = mlb.worsen_arrival_curve_due_to_clock_async(rho,eta)
            newCurve = newCurve * new_mlb
        return newCurve
    
    def worsen_arrival_curve_due_to_clock_sync(self, rho: float, eta: float, delta: float) -> 'Curve':
        newCurve = InfiniteCurve()
        for mlb in self._listLb:
            new_mlb = mlb.worsen_arrival_curve_due_to_clock_sync(rho,eta,delta)
            newCurve = newCurve * new_mlb
        return newCurve
    
    def get_packetization_penalty_curve(self, packetMaxSize: int, **kargs) -> 'Curve':
        retCurve = InfiniteCurve()
        for lb in self._listLb:
            penaltyLb = lb.get_packetization_penalty_curve(packetMaxSize,**kargs)
            retCurve = retCurve * penaltyLb
        return retCurve


class RateLatencyServiceCurve(Curve):
    def __init__(self, rate: float, latency: float, **kargs) -> None:
        super(RateLatencyServiceCurve,self).__init__(**kargs)
        self._rate=rate
        self._latency=latency
        
    def y_to_x(self, y:float)->float:
        return ((y/self.get_rate())+self.get_latency())

    def get_rate(self) -> float:
        return self._rate

    def get_latency(self) -> float:
        return self._latency
    
    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        if(s <= self._latency):
            return float(0)
        else:
            return (float(s) - self._latency) * self._rate

    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        return self.get_value_at_s(s)
    
    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self,s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        return self.get_value_at_s(s)

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:
        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))
    
    def __mul__(self, o: Curve) -> Curve:
        if (isinstance(o,BoundedDelayServiceCurve)):
            new_rl = copy.deepcopy(self)
            new_rl._latency += o.getDelay()
            return new_rl
        if (isinstance(o,RateLatencyServiceCurve)):
            #Add latencies, get minimum rate
            new_latency = self.get_latency() + o.get_latency()
            new_rate = min(self.get_rate(), o.get_rate())
            new_rl = RateLatencyServiceCurve(new_rate,new_latency)
            return new_rl
        raise TypeError("unsupported operand type(s) for * or mul(): %s and %s" % (type(self).__name__, type(o).__name__))
    
    def __eq__(self, o: object) -> bool:
        if(isinstance(o, NoCurve)):
            return (self._rate == 0.0)
        if(isinstance(o,LeakyBucket) or isinstance(o,GVBR)):
            if(self._rate > 0.0):
                if(self._latency > 0.0):
                    return False
                return o.__eq__(LeakyBucket(self._rate, 0.0))
            return o.__eq__(NoCurve())
        if(isinstance(o, RateLatencyServiceCurve)):
            return ((self._rate == o._rate) and (self._latency ==  o._latency))
        return super().__eq__(o)

    def substract_latest_lb(self, curveToSubstract: Curve) -> None:
        if(isinstance(curveToSubstract, NoCurve)):
            #do not substract anything
            return
        if(isinstance(curveToSubstract, LeakyBucket)):
            b = curveToSubstract.get_burst()
            r = curveToSubstract.get_rate()
            R = self._rate
            T = self._latency
            #substract rate
            self._rate = R - r
            #latency is increased by the following formula
            self._latency = T + (b / (R - r)) + ((T * r) / (R - r))
            return
        if(isinstance(curveToSubstract, GVBR)):
            self.substract_latest_lb(curveToSubstract._getLastLb())
            return
        raise TypeError("unsupported substractLatestLB with %s" % (type(curveToSubstract).__name__))

    def __str__(self, **kargs) -> str:
        digits = kargs.get("digits", 2)
        return ("RL(%.*e,%.*e)(bit/s,s)" % (digits, self._rate, digits, self._latency)) 
    
    def compute_intersection(self, rl: 'RateLatencyServiceCurve') -> Tuple[float,float]:
        """Returns the (x,y) intersection with rl
        """
        if (self.get_rate() == rl.get_rate()):
            return (-1,-1)
        highestLatency: RateLatencyServiceCurve
        lowestLatency: RateLatencyServiceCurve
        if (self.get_latency() > rl.get_latency()):
            highestLatency = self
            lowestLatency = rl
        else:
            highestLatency = rl
            lowestLatency = self
        if (lowestLatency.get_rate() > highestLatency.get_rate()):
            return (-1,-1)
        x = ((rl.get_rate()*rl.get_latency())-(self.get_rate()*self.get_latency()))/(rl.get_rate()-self.get_rate())
        return(x, self.get_value_at_s(x))
    
    def worsen_service_curve_due_to_clock_async(self, rho: float, eta: float) -> 'Curve':
        return RateLatencyServiceCurve(self.get_rate()/rho,eta+rho*self.get_latency())
    
    def worsen_service_curve_due_to_clock_sync(self, rho: float, eta: float, delta: float) -> 'Curve':
        rl1 = RateLatencyServiceCurve(self.get_rate()/rho,eta+rho*self.get_latency())
        rl2 = RateLatencyServiceCurve(self.get_rate(),self.get_latency()+2*delta)
        r = MaxOfRateLantencies(rl1)
        r.max_with_rate_latency(rl2)
        return r


class MaxOfRateLantencies(Curve):
    """
    Describes the maximum of several rate-latency service curves

    Inheritance:
        Curve:
    """
    
    _curves: List[RateLatencyServiceCurve]
    _discontinuities: List[float]
    
    def __init__(self, initialCurve: RateLatencyServiceCurve, **kargs):
        
        self._curves = list()
        self._curves.append(initialCurve)
        self._discontinuities = list()
        self._discontinuities.append(initialCurve.get_latency())
        self._name = kargs.get("name", "maxOfRlServiceCurve")
    
    def max_with_rate_latency(self, rl: RateLatencyServiceCurve):
        for i in range(len(self._curves)):
            if (self._curves[i].get_latency() > rl.get_latency()):
                self._curves.insert(i,rl)
                self._update_list_discontinuities()
                self._clean_list_rl()
                return
        self._curves.append(rl)
        self._update_list_discontinuities()
        self._clean_list_rl()
        return
            
    def _update_list_discontinuities(self):
        self._discontinuities.clear()
        self._discontinuities.append(self._curves[0].get_latency())
        for i in range(len(self._curves)-1):
            x,y = self._curves[i].compute_intersection(self._curves[i+1])
            self._discontinuities.append(x)
        
            
    def _clean_list_rl(self):
        newList: List[RateLatencyServiceCurve] = list()
        for i in range(len(self._curves)):
            if (i-1) >=0:
                #Must have rate higher than the preceeding one with lower latency
                if self._curves[i].get_rate() > self._curves[i-1].get_rate():
                    if(i+1) < len(self._curves):
                        #Its intersection with the next curve should be above the previous curve
                        x,y = self._curves[i].compute_intersection(self._curves[i+1])
                        if y > self._curves[i-1].get_value_at_s(x):
                            newList.append(self._curves[i])
                    else:
                        #No curve after, add
                        newList.append(self._curves[i])
            else:
                #no curve before, ass
                newList.append(self._curves[i])
        self._curves = newList    
                                    
    def get_value_at_s(self, s: float) -> float:
        for i in range(len(self._discontinuities)):
            if (self._discontinuities[i] > s):
                if(i<1):
                    return 0
                else:
                    return self._curves[i-1].get_value_at_s(s)
        return self._curves[-1].get_value_at_s(s)
            

    def get_value_at_s_plus(self, s: float) -> float:
        #continuous
        return self.get_value_at_s(s)
    
    def get_value_at_s_moins(self, s: float) -> float:
        #continuous
        return self.get_value_at_s(s)
    
    def y_to_x(self, y:float)->float:
        return (min(c.y_to_x(y) for c in self._curves))

    
    
class BoundedDelayServiceCurve(Curve):

    
    def __init__(self, boundedDelay: float, **kargs) -> None:
        super().__init__(**kargs)
        self._d = boundedDelay
        self._name = kargs.get("name", "deltaDService")
    
    def getDelay(self) -> float:
        return self._d

    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        if(s <= 0):
            return float(0)
        else:
            return float("inf")

    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        return float("inf")
    
    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self, s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        return float("inf")

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:
        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))
    
    def __mul__(self, o: Curve) -> Curve:
        if(isinstance(o,BoundedDelayServiceCurve)):
            new_d = copy.deepcopy(self)
            new_d._d += o._d
            return new_d
        if(isinstance(o,RateLatencyServiceCurve)):
            return (o * self)
        raise TypeError("unsupported operand type(s) for * or mul(): %s and %s" % (type(self).__name__, type(o).__name__))

    def __str__(self, **kargs) -> str:
        digits = kargs.get("digits",2)
        return ("Gamma(%.*e)(s)" % (digits, self._d))

class DGVBR(Curve):
    def __init__(self, latency: float, gvbr: GVBR, **kargs) -> None:
        super(DGVBR,self).__init__(**kargs)
        self._latency = latency
        self._gvbr = gvbr

    @copydoc(Curve.get_value_at_s)
    def get_value_at_s(self, s: float) -> float:
        if(s <= self._latency):
            return float(0)
        else:
            return self._gvbr.get_value_at_s(s-self._latency)

    @copydoc(Curve.get_value_at_s_plus)
    def get_value_at_s_plus(self, s: float) -> float:
        if(s < self._latency):
            return float(0)
        else:
            return self._gvbr.get_value_at_s_plus(s-self._latency)
      
    @copydoc(Curve.get_value_at_s_moins)
    def get_value_at_s_moins(self, s: float) -> float:
        if(s<=0):
            raise ArrivalCurveNotDefinedForThisValue(s,string=("Value not defined for lim_{x<%e,x->%e}" % (s,s)))
        if(s <= self._latency):
            return float(0)
        else:
            return self._gvbr.get_value_at_s_moins(s-self._latency)

    @copydoc(Curve.__mod__)
    def __mod__(self, serviceCurve: Curve) -> float:
        raise TypeError("unsupported operand type(s) for %% or mod(): %s and %s" % (type(self).__name__, type(serviceCurve).__name__))

    def get_gvbr(self) -> GVBR:
        return self._gvbr

    def get_latency(self) -> float:
        return self._latency

    def __str__(self, **kargs) -> str:
        return "DGVBR"

def plot_a_delay_computation(arrivalCurve: Curve, serviceCurve: Curve, **kargs):
    plt.figure()
    if (not serviceCurve.get_name()):
        serviceCurve.set_name("Service Curve")
    if (not arrivalCurve.get_name()):
        arrivalCurve.set_name("Arrival Curve")
    x = 0
    x_2 = 0
    y = 0
    if (isinstance(serviceCurve, RateLatencyServiceCurve)):
        if (isinstance(arrivalCurve, LeakyBucket)):
            y = arrivalCurve.get_burst()
            x_2 = arrivalCurve % serviceCurve
            x = 0
        if (isinstance(arrivalCurve, GVBR)):
            x, x_2, y = arrivalCurve.get_delay_bound_location(serviceCurve)
            
    if(x_2 > 0):
        kargs["x_max"] = kargs.get("x_max", 1.1*x_2)
    plt.ticklabel_format(axis="x", style="sci", scilimits=(0,0))
    plt.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    colorAc = "blue"
    colorSc = "red"
    if (len(kargs.get("colors",list())) > 0):
        colorAc = kargs.get["colors"][0]
    if (len(kargs.get("colors",list())) > 1):
        colorSc = kargs.get["colors"][1]
    kargs.pop("colors", None)
    plot_an_arrival_curve(arrivalCurve, **kargs, color=colorAc)
    plot_an_arrival_curve(serviceCurve, **kargs, color=colorSc)
    digits = kargs.get("digits", 2)
    plt.plot([x, x_2], [y,y], label=("Delay Bound: %.*es" % (digits, arrivalCurve % serviceCurve)), color="green")
    plt.legend()
    plt.title(kargs.get("title","Delay bound computation"))

def plot_an_arrival_curve(arrivalCurve: Curve,**kargs):
    x_min = kargs.get("x_min",0)
    x_max = kargs.get("x_max",arrivalCurve.get_interesting_xmax_for_plot())
    y_min = kargs.get("y_min",0)
    y_max = kargs.get("y_max",10)
    n_points = kargs.get("n_points",10000)
    x = np.linspace(x_min,x_max,num=n_points)
    if(kargs.get("without_zero", False)):
        x = x[1:]
    y = [arrivalCurve.get_value_at_s(x_v) for x_v in x]
    additionnalParams = dict()
    if 'color' in kargs.keys():
        additionnalParams["color"] = kargs.get("color")
    if(arrivalCurve.get_name() != ""):
        plt.plot(x,y, label=arrivalCurve.get_name() + " - " + arrivalCurve.__str__(**kargs), **additionnalParams)
    else:
        plt.plot(x,y, label=arrivalCurve.__str__(**kargs), **additionnalParams)
    if (("y_min" in kargs.keys()) or ("y_max" in kargs.keys())):
        plt.ylim(y_min,y_max)

def plot_arrival_curves(*arrivalCurves: Curve,**kargs):
    """
    Description of plotArrivalCurves

    Args:
        *arrivalCurves (Curve): arrival curves to plot
    """
    fig = plt.figure()
    fig.tight_layout()
    if ("x_max" not in kargs.keys()):
        kargs["x_max"] =max(arrivalCurve.get_interesting_xmax_for_plot() for arrivalCurve in arrivalCurves)
    mColors = list()
    if "colors" in kargs.keys():
        mColors = kargs.pop("colors")
    for ac in arrivalCurves:
        if(mColors):
            color = mColors[arrivalCurves.index(ac)%len(mColors)]
            kargs["color"] = color
        plot_an_arrival_curve(ac,**kargs)
    plt.legend()
    plt.ticklabel_format(axis="x", style="sci", scilimits=(0,0))
    plt.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
    plt.xlabel("Time interval (s)")
    plt.ylabel("Data (bits)")
    plt.title(kargs.get("title","Arrival curves"))


if __name__ == "__main__":
    
    lb1 = LeakyBucket(1,10,name="Test")
    lb2 = LeakyBucket(2,5)
    ac1 = lb1 * lb2
    
    s1 = RateLatencyServiceCurve(5,2)
    s2 = RateLatencyServiceCurve(10,4)
    m = MaxOfRateLantencies(s1)
    m.max_with_rate_latency(s2)
    
    print(ac1 % m)
    plot_arrival_curves(m,ac1)
    print(m._discontinuities)
    plt.show()

    
    

