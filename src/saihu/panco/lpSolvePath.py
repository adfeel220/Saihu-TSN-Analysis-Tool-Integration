#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of the panco project.
# https://github.com/Huawei-Paris-Research-Center/Panco

__author__ = "Anne Bouillard"
__maintainer__ = "Anne Bouillard"
__email__ = "anne.bouillard@huawei.com"
__copyright__ = "Copyright (C) 2022, Huawei Technologies France"
__license__ = "BSD-3"


import os.path
import json

# LPSOLVEPATH = ["wsl", "lp_solve", "-s5"]
LPSOLVEPATH = [os.path.dirname(__file__), "lp_solve"]

if not os.path.exists(os.path.join(*LPSOLVEPATH)):
    path_file = json.load(
        open(
            os.path.join(os.path.dirname(__file__), "..", "resources", "paths.json"),
            "r",
        )
    )
    LPSOLVEPATH = path_file["lpsolve"]
