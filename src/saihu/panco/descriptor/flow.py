#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of the panco project.
# https://github.com/Huawei-Paris-Research-Center/Panco

from __future__ import annotations

__author__ = "Anne Bouillard"
__maintainer__ = "Anne Bouillard"
__email__ = "anne.bouillard@huawei.com"
__copyright__ = "Copyright (C) 2022, Huawei Technologies France"
__license__ = "BSD-3"


import numpy as np
from typing import List, Tuple
from panco.descriptor.curves import TokenBucket


class Flow:
    """
    The Flow class encodes a flow circulating in the network, characterized by

        - a arrival curve :math:`\\alpha(t) = \\min_i (\\sigma_i + \\rho_i t)`
        - a path :math:`\\pi`: the sequence of servers crossed by the flow.

    :param arrival_curve: the arrival curve, given by a minimum of the token-bucket functions :math:`\\alpha`
    :type arrival_curve: List[TokenBucket]
    :param path: the path (list of servers) followed by the flow :math:`\\pi`
    :type path: List[int]
    :param self.length: the length of the path
    :type self.length: int


    >>> Flow([TokenBucket(1, 2), TokenBucket(3, 4)], [1, 2, 3])
    <Flow: α(t) = min [1 + 2t, 3 + 4t]; π = [1, 2, 3]>
    <BLANKLINE>
    """

    def __init__(self, arrival_curve: List[TokenBucket], path: List[int]):
        self.arrival_curve = arrival_curve
        self.path = path
        self.length = len(path)

    def __str__(self) -> str:
        return "α(t) = min %s; π = %s" % (self.arrival_curve, self.path)

    def __repr__(self) -> str:
        return "<Flow: %s>\n" % self.__str__()

    def __eq__(self, other: Flow) -> bool:
        return self.path == other.path and self.arrival_curve == other.arrival_curve
