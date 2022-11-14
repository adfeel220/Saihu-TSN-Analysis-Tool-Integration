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
This module contains an interface with the Gurobi Integer Linear Programming (ILP) Solver.
It requires the gurobipy python module, an installation of gurobi and a gurobi license.
See www.gurobi.com for obtaining the gurobi software and a license.
"""

import logging
from xtfa import MilpInterface
from gurobipy import Model, GRB

logger = logging.getLogger("GRB_INTERFACE")

class GurobiInterface(MilpInterface.MilpInterface):
    '''Implementation of the MilpInterface using Gurobi solver and its python api, gurobipy.

    '''

    def __init__(self,**kargs):
        '''Initialize the class.

        Kargs arguments:
            "debug" : Print debug infos if on True. Default: False
        '''
    
    def solve(self, coverMatrix, costs, startingPoint):
        m = coverMatrix.shape[1] #m edges
        l = coverMatrix.shape[0] #l cycles
        model = Model("coverSet")
        model.setParam('OutputFlag', False)
        #Creation of variables
        y=model.addVars(range(m), name='y', vtype=GRB.BINARY)

        #Cover constraint
        model.addConstrs(sum(coverMatrix[i,j] * y[j] for j in range(m)) >= 1 for i in range(l))

        #Objectif de cout
        model.setObjective(sum(y[j]*costs[j] for j in range(m)), GRB.MINIMIZE)

        #Lancement
        logger.info("--------- Starting Gurobi ---------")
        model.optimize()
        logger.info("--------- End of Gurobi ---------")
        
        theVars = model.getVars()
        solution = [int(theVars[j].x) for j in range(m)]
        return solution

        
