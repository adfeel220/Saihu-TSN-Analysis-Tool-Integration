#!/usr/bin/python3

# This file is part of xTFA
# Copyright (c) 2021-2022 Ludovic Thomas
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
This modules defines the units used in xTFA. It contains useful method for converting, reading, writing units.
"""

def readRate(s) -> float:
    if(isinstance(s, float)):
        return s
    multiplicators = {
        "Mbps": 1e6,
        "Gbps": 1e9
    }
    for key in multiplicators:
        if s.endswith(key):
            substract = s.split(key)[0]
            val = float(substract)
            return val*multiplicators[key]
    return float(s)
        
def readTime(s) -> float:
    if(isinstance(s,float)):
        return s
    multiplicators = {
        "ns": 1e-9,
        "us": 1e-6,
        "ms": 1e-3,
        "s": 1
    }
    for key in multiplicators:
        if s.endswith(key):
            substract = s.split(key)[0]
            val = float(substract)
            return val*multiplicators[key]
    return (float(s)*1e-3) #default

def readDataUnit(s) -> float:
    if(isinstance(s, float)):
        return s
    if(isinstance(s, int)):
        return float(s)
    byteMultiplicators = {
        "B": 8,
        "b": 1
    }
    multiplicators = {
        "k" : 1e3,
        "M" : 1e6
    }
    firstMultiplicator = 8 #default to 8
    secondMultiplicator = 1
    for key in byteMultiplicators:
        if s.endswith(key):
            s = s.split(key)[0]
            firstMultiplicator = byteMultiplicators[key]
    for k in multiplicators:
        if s.endswith(k):
            s = s.split(key)[0]
            secondMultiplicator = multiplicators[k]
    return float(s)*firstMultiplicator*secondMultiplicator

def readPriority(s) -> int:
    if (isinstance(s,int)):
        return s
    if (isinstance(s,str)):
        #In case of string prioritites (Low/High), then the higher is better convention is used.
        if ("Low".lower() == s.lower()):
            return 0
        if ("High".lower() == s.lower()):
            return 1
        return int(s)
    raise TypeError("Cannot parse priority '%r'" % s)