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
This module defines the interface for a MILP solver.
In xtfa, we provide an implementation based on Gurobi.
To use a different solver, implement the MilpInterface
"""

class MilpInterface:
    '''Interface for a mixed-integer linear programming software (MILP)
    '''

    def solve(self, coverMatrix, costs, startingPoint):
        '''Solve the minimum set cover problem. Returns a selection vector Y. y(j) equals 1 if edge j is in the Minimum Feedback Arc Set
        
        Arguments:
            coverMatrix {np.array} -- The cover matrix. a(i,j) equals 1 if edge j is in cycle i, 0 otherwise. Constraint of the problem: For each i, sum(a(i,j)*y(j) for j) greater or equals than 1.
            costs {list} -- w(j) is the cost of edge i. Objective of the problem : min(sum(w(j)*y(j)) for j)
            startingPoint {list} -- A starting point (optionnal)
        Returns:
            list -- The selection list.
        '''



        pass