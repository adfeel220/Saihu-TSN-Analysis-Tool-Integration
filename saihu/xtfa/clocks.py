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
This module contains the representation of clocks
"""

from xtfa import minPlusToolbox as mpt

class Clock:
    """
    Represents a clock.
    """
    name: str
    is_tai: bool
    
    #These are only used at the class level (equal for all instances)
    RHO = 1+(2e-4)
    ETA = 4e-9
    SYNC = False
    DELTA = 1e-6
    PERFECT = True
    
    def __init__(self, n: str) -> None:
        self.name = n
        self.is_tai = False
        if(self.name.lower() == "tai"):
            self.is_tai = True
    
    def equals(self, other: 'Clock')->bool:
        """ Checks if self is equal to other

        Args:
            other (Clock): another clock

        Returns:
            bool: True if self is the same clock as other, False otherwise
        """
        if(Clock.PERFECT):
            return True
        if(self.is_tai and other.is_tai):
            return True
        return (other.name == self.name)
    
    @classmethod
    def worsen_delay_upper_bound(cls, d: float)->float:
        """If the clocks are imperfect, worsen the provided delay upper bound according to the time model (sync or not) and the time-model parameters.

        Args:
            d (float): A delay upper bound observed with one clock

        Returns:
            float: A delay upper bound observed with any other clock.
        """
        if(Clock.PERFECT):
            return d
        newD = Clock.RHO*d + Clock.ETA
        if(Clock.SYNC):
            newD = min(newD,d+2*Clock.DELTA)
        return newD
    
    @classmethod
    def worsen_delay_lower_bound(cls, d:float) -> float:
        """If the clocks are imperfect, worsen the provided delay upper bound according to the time model (sync or not) and the time-model parameters.

        Args:
            d (float): A delay lower bound observed with one clock

        Returns:
            float: A delay lower bound observed with any other clock.
        """
        if(Clock.PERFECT):
            return d
        newD = max(0, (d-Clock.ETA)/Clock.RHO)
        if(Clock.SYNC):
            newD = max(newD, d-2*Clock.DELTA)
        return newD

    @classmethod
    def worsen_arrival_curve(cls, ac: mpt.Curve) -> mpt.Curve:
        """If the clocks are imperfect, worsen the arrival curve according to the time model and its parameters

        Args:
            ac (mpt.Curve): An arrival curve observed with one clock

        Returns:
            mpt.Curve: An arrival curve for the same flow, same observation point, observed with any other clock
        """
        if(Clock.PERFECT):
            return ac
        if(Clock.SYNC):
            return ac.worsen_arrival_curve_due_to_clock_sync(Clock.RHO, Clock.ETA, Clock.DELTA)
        return ac.worsen_arrival_curve_due_to_clock_async(Clock.RHO, Clock.ETA)
    
    @classmethod
    def worsen_service_curve(cls, sc: mpt.Curve):
        """If the clocks are imperfect, worsen the service curve according to the time model and its parameters

        Args:
            ac (mpt.Curve): A service curve observed with one clock

        Returns:
            mpt.Curve: A service curve for the same system, observed with any other clock
        """
        if(Clock.PERFECT):
            return sc
        if(Clock.SYNC):
            return sc.worsen_service_curve_due_to_clock_sync(Clock.RHO, Clock.ETA, Clock.DELTA)
        return sc.worsen_service_curve_due_to_clock_async(Clock.RHO, Clock.ETA)
    
    
    