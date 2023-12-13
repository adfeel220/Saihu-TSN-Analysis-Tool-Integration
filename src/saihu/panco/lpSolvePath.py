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

# The Saihu author Chun-Tso Tsai has modified the methods to resolve
# lp_solve executable path. This file is thus different from the original
# Panco implementation.

from platform import system
import os.path
import json
import subprocess
import shutil
import warnings


def _parse_lp_values(lp_solve_stdout: str):
    tab_values = lp_solve_stdout.split("\n")[4:-1]
    values = [
        [token for token in line.split(" ") if not token == ""] for line in tab_values
    ]
    return dict(values)


def _is_valid_path(solver_path: list):
    """Test if lp_solve executable is properly set"""
    if len(solver_path) == 0:
        return False
    if len(solver_path[0]) == 0:
        return False
    if not os.path.exists(solver_path[0]):
        return False

    test_lp_path = os.path.join(os.path.dirname(__file__), "test.lp")
    lp_solve_stdout = subprocess.run(
        solver_path + [test_lp_path], stdout=subprocess.PIPE, encoding="utf-8"
    ).stdout

    values = _parse_lp_values(lp_solve_stdout)
    return values.get("x", "") == "2" and values.get("y", "") == "3"


# Priority 1: the path written in saihu/resources/paths.json, by default getting empty
def _get_lpsolve_path_from_resource_file():
    with open(
        os.path.join(os.path.dirname(__file__), "..", "resources", "paths.json"), "r"
    ) as f:
        path_file = json.load(f)
        return [path_file.get("lpsolve", "")]


# Priority 2: try to find lp_solve by asking system-wide "which lp_solve"
def _auto_resolve_system_lpsolve():
    """System independent equivalent of trying command line 'which lp_solve'"""
    # Try common alias for lp_solve
    for solver_alias_name in ["lp_solve", "lpsolve"]:
        path = shutil.which(solver_alias_name)
        if path is not None:
            return [path]
    return []


def _resolve_path():
    """Resolve a valid lp_solve executable path, print warning if no valid executable is found"""
    path = _get_lpsolve_path_from_resource_file()
    if _is_valid_path(path):
        return path

    path = _auto_resolve_system_lpsolve()
    if _is_valid_path(path):
        return path

    # 3: program entry directory
    if _is_valid_path(["./lp_solve"]):
        return ["./lp_solve"]

    os_genre = system()
    if os_genre == "Windows":
        suggestion = "You may go to https://sites.math.washington.edu/~conroy/m381-general/lpsolveHowToPC/runningLPsolveCommandLineWindows.htm for the tutorial of installing lp_solve executable."
    elif os_genre == "Darwin":
        suggestion = "You may go to https://sites.math.washington.edu/~conroy/m381-general/lpsolveHowToMac/lpsolveMacHow.html for the tutorial of installing lp_solve executable."
    elif os_genre == "Linux":
        suggestion = (
            "You may use 'sudo apt-get lp-solve' to download a system-wide lp_solve."
        )
    else:
        suggestion = ""

    warnings.warn(
        "Warning: No valid lp_solve executable is found, will skip Panco during the analysis. "
        "To include Panco in the analysis, please download lp_solve for your machine "
        "and either 1: indicate path in saihu/resources/paths.json, "
        "2: install it as a system command, or 3: put it at your program entry path\n"
        + suggestion
    )
    return []


LPSOLVEPATH = _resolve_path()
