#!/usr/bin/python3

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
This module defines a set of useful methods for plotting the results of a xTFA computation
"""

import matplotlib.pyplot as plt
import numpy as np
import pickle

class PlotDelays:

    _net: 'networks.Network'

    def __init__(self, network: 'networks.NetworkInterface') -> None:
            self._net = network

    def plotCdf(self, *args, **kargs):
        deadline_args = kargs.pop("deadline_args", ["--"])
        do_deadlines = False
        xshift = kargs.pop("xshift", 0)
        all_destinations = kargs.pop("all_destinations", False)
        if(kargs.pop("deadlines", False)):
            do_deadlines = True
        if(not do_deadlines):
            if(all_destinations):
                delayList = self._net.getOrderedDelayUpperBoundList()
            else:
                delayList = self._net.getOrderedDelayUpperBoundListOnePerFlow()
            x,y = sorted(delayList), np.arange(len(delayList)) + xshift
            pp = plt.plot(y, x, *args, **kargs)
        else: 
            if(all_destinations):
                delayList, deadlineList = self._net.getOrderedDelayUpperBoundListWithDeadlines()
            else:
                delayList, deadlineList = self._net.getOrderedDelayUpperBoundListWithDeadlinesOnePerFlow()
            x,y = sorted(delayList), np.arange(len(delayList)) + xshift
            xD = [xx for _,xx in sorted(zip(delayList,deadlineList))]
            p = plt.plot(y, x, *args, **kargs)
            pp = plt.plot(y, xD, *deadline_args, color=p[0].get_color())
        plt.ylabel("Delay (s)")
        plt.xlabel("Flow count")
        plt.title("CDF")
        plt.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
        return pp
    
    def compareTwoCdfFromLists(self, listOfNames, listOfLists, listOfStyles):
        if(not listOfStyles):
            listOfLists = ["-" for _ in range(len(listOfLists))]
        for i in range(len(listOfLists)):
            mlist = listOfLists[i]
            mname = listOfNames[i]
            x,y = sorted(mlist), np.arange(len(mlist))
            plt.plot(y, x, listOfStyles[i], label=mname)
            plt.ylabel("Delay (s)")
            plt.xlabel("Flow count")
        plt.title("CDF")
        plt.ticklabel_format(axis="y", style="sci", scilimits=(0,0))
        plt.ylim(bottom=0)

    def compareTwoCdfFromFiles(self, *args):
        listOfNames = list()
        listOfLists = list()
        for fn in args:
            with open(fn,'rb') as f:
                delayList = pickle.load(f)
                listOfNames.append(fn)
                listOfLists.append(delayList)
        self.compareTwoCdfFromLists(listOfNames, listOfLists, ["-"] * len(listOfLists))


from xtfa import networks