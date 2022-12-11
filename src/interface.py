import sys
import os.path
LOCAL_PATH = os.path.abspath(os.path.dirname(__file__))
if LOCAL_PATH not in sys.path:
    sys.path.append(LOCAL_PATH)

import xtfa.networks
import xtfa.fasUtility

from Linear_TFA.Linear_TFA import Linear_TFA
from netscript.netscript import *
from javapy.dnc_exe import dnc_exe
from panco.panco_analyzer import panco_analyzer
from result import TSN_result
import netscript.unit_util as unit_util

from enum import Enum
from time import time
from typing import Union
from collections.abc import Iterable
import json
import networkx as nx
import numpy as np
from mdutils.mdutils import MdUtils as mdu
import matplotlib.pyplot as plt


def list_update_none(x1:list, x2:list) -> list:
    '''
    Replace None element in x1 with x2 with the same index
    '''
    return [x2[i] if x is None and i<len(x2) else x for i,x in enumerate(x1)]


class FORCE_SHAPER(Enum):
    '''The enum to select using shaper or not'''
    AUTO = 1
    ON   = 2
    OFF  = 3

class TSN_Analyzer():
    '''
    The general analyzer interface to use

    Attributes:
    --------------
    netfile        : Path to a network file to be analyzed
    script_handler : Script handler to manipulating network definition scripts
    results        : Contains the analysis results computed before
    _jar_path      : Path to the JAR file generated from DNC package
    _temp_path     : Path to store computation artifacts
    serv_delay_mul : Per server Delay multiplier for all the loaded results
    flow_delay_mul : End-to-end Delay multiplier for all the loaded results
    backlog_mul    : Backlog multiplier for all the loaded results (not used)
    exec_time_mul  : Multiplier for execution time by each analysis 
    output_shaping     : Enum number to choose use shaper or not

    Methods:
    --------------
    set_shaping_mode : Select whether to use shaper. Can be "AUTO", "ON", or "OFF"
    convert_netfile  : Convert a netfile into both physical and output-port network from either format
    analyze_all      : Analyze the network with all tools available
    analyze_xtfa     : Analyze the network with xTFA
    analyze_linear   : Analyze the network with linear TFA solver
    analyze_panco    : Analyze the network with panco FIFO analyzer
    analyze_dnc      : Analyze the network with DNC
    write_result     : Write the output report
    clear            : Reset analyzer
    '''
    netfile        : str                    # Path to a network file to be analyzed
    script_handler : NetworkScriptHandler   # Script handler to manipulating network definition scripts
    results        : list                   # Contains the analysis results computed before
    _jar_path      : str                    # Path to the JAR file generated from DNC package
    _temp_path     : str                    # Path to store computation artifacts
    serv_delay_mul : str                    # Per server Delay multiplier for all the loaded results
    flow_delay_mul : str                    # End-to-end Delay multiplier for all the loaded results
    backlog_mul    : str                    # Backlog multiplier for all the loaded results (not used)
    exec_time_mul  : str                    # Multiplier for execution time by each analysis 
    output_shaping     : int                    # Enum number to choose use shaper or not


    def __init__(self, netfile:str=None, 
                 jar_path:str=os.path.abspath(os.path.join(os.path.dirname(__file__),"javapy/")), 
                 temp_path:str=os.path.abspath("./"),
                 output_shaping:str="AUTO") -> None:
        '''
        Inputs:
        -----------
        netfile: (Optional) [str] path to network definition file. Default is None
        jar_path: (Optional) [str] path to the directory of DNC .jar file. Default is "./javapy/"
        temp_path: (Optional) [str] path to temp (storage for computation artifacts). Default is "./"
        output_shaping: (Optional) [str] select to use shaper or not. Default is "AUTO", can choose "ON" or "OFF" as well
        '''
        self.script_handler = NetworkScriptHandler()
        self.results = list()
        self.netfile = netfile
        self._jar_path = jar_path
        self._temp_path = temp_path
        self.serv_delay_mul = None
        self.flow_delay_mul = None
        self.backlog_mul = None
        self.exec_time_mul = None
        self.set_shaping_mode(output_shaping)

    def clear(self) -> None:
        '''Reset current analyzer'''
        self.script_handler = NetworkScriptHandler()
        self.results = list()
        self.netfile = None
        self.serv_delay_mul = None
        self.flow_delay_mul = None
        self.backlog_mul = None
        self.exec_time_mul = None
        self.output_shaping = FORCE_SHAPER.AUTO


    def set_shaping_mode(self, enforce:str) -> None:
        '''
        Set to enforce output shaping usage mode, available values are
        - AUTO: consider output shaping while available
        - ON: consider output shaping, if shaper is not defined, raise error
        - OFF: Do not consider output shaping

        Upper/lower case doesn't matter
        '''
        if enforce.upper() == "AUTO":
            self.output_shaping = FORCE_SHAPER.AUTO
        elif enforce.upper() == "ON":
            self.output_shaping = FORCE_SHAPER.ON
        elif enforce.upper() == "OFF":
            self.output_shaping = FORCE_SHAPER.OFF
        else:
            # Default as "AUTO"
            print(f"No such shaper enforcement {enforce}, must in {list(FORCE_SHAPER)} ignore")
            self.output_shaping = FORCE_SHAPER.AUTO

    def write_result(self, output_file:str, clear:bool=True) -> None:
        '''
        Write the currently stored results as a Markdown file

        Inputs:
        --------------
        output_file: [str] path of the output report
        clear: (Optional) [bool] Clear all content after finishing writing report. Default is True
        '''
        print("Writing output report...", end="")

        if len(self.results) == 0:
            print("Abort writing result: No results analyzed before")
            return

        outpath = os.path.abspath(os.path.dirname(output_file))
        ## Start writing
        # Resolve the number of networks in results
        networks = dict()
        for res in self.results:
            if res.name not in networks:
                networks[res.name] = list()
            networks[res.name].append(res)
            
        output_index = 0
        # We summarize one output file for each network
        for net_name, res in networks.items():

            # sort results by "tool-method" in alphabetical order
            res_sorted = dict(zip(["{m}{t}".format(t=r.tool, m=r.method) for r in res], res))
            res_sorted = dict(sorted(res_sorted.items()))
            res_sorted = dict(zip(["{t}-{m}".format(t=r.tool, m=r.method) for r in res_sorted.values()], res_sorted.values()))

            ## Output tool-method specific results
            # divide the results by method used
            res_by_methods = dict()
            for r in res:
                if r.method not in res_by_methods:
                    res_by_methods[r.method] = list()
                res_by_methods[r.method].append(r)

            # Determine report filename
            output_file = check_file_ext(output_file, "md")
            if output_index > 0:
                output_file = add_text_in_ext(output_file, str(output_index), sep='-')
            output_index += 1

            # Create the output Markdown file to write
            mdFile = mdu(file_name=output_file, title=f"Analysis Report - \"{net_name}\"")
            mdFile.new_paragraph("The is a automatically generated report with project `TSN Analysis Tools Intergration`\n")
 
            ## General flow end-to-end delay
            mdFile.new_header(level=1, title="Flow End-to-end Delays")
            self._build_flow_summary(mdFile, res_sorted)

            ## Write general network information
            mdFile.new_header(level=1, title="Network Information")
            mdFile.new_paragraph(f"This report contains {len(res)} analysis over network **\"{net_name}\"**.\n")
            mdFile.write(f"There are **{res[0].num_servers}** servers and **{res[0].num_flows}** flows in the system.")
            # topology
            fig, ax = plt.subplots()
            nx.draw(res[0].graph, with_labels=True)
            graph_file_path = os.path.join(outpath, f"{net_name}_topo.png")
            fig.savefig(graph_file_path, dpi=300, bbox_inches='tight')
            plt.close(fig)
            # utility
            self._build_utility_map(mdFile, res_sorted)

            mdFile.new_header(level=2, title="Topology of network")
            mdFile.new_line(mdFile.new_reference_image(text="Network graph", path=graph_file_path, reference_tag='topo'))
            # performance
            mdFile.new_header(level=2, title="Execution Time")
            self._build_performance_table(mdFile, res_sorted)
            
            
            # Server delays / backlogs
            mdFile.new_header(level=1, title="Server Delays")
            self._build_server_result_table(mdFile, res_sorted, "delay")
            
            ## 2022.11.26 : Since only DNC returns backlog data, remove printing backlog
            #####################################
            # # check if there's any backlog data
            # backlog_mapping = self._create_mapping(res, "server_backlogs")
            # if len(backlog_mapping) > 0:
            #     self._build_server_result_table(mdFile, res_by_methods, "backlog")
            #####################################
                
            ## Per flow result
            mdFile.new_header(level=1, title="Per Flow Delays")
            for foi in res[0].flow_paths.keys():
                self._build_flow_result_table(mdFile, res_sorted, foi)
                
            
            # Create table of contents
            mdFile.new_table_of_contents(table_title="Table of Contents", depth=2)

            # Finally create the output file
            mdFile.create_md_file()

        # Clear the current results if 
        if clear:
            self.clear()

        print("Done")


    def analyze_all(self, netfile:str=None, methods:Union[list,str]=["TFA"], use_tfa:bool=True, use_sfa:bool=True) -> int:
        '''
        Analyze the network with 4 methods: DNC, xTFA, Linear Solver, and panco

        Parameters:
        -------------
        netfile: (Optional) [str] File name of the network definition, must in either WOPANet XML format or output-port JSON.
                 Default is to select the netfile stored in the class, raise error if both are not defined.
        methods: (Optional) [list | str] List of methods "TFA", "SFA", or "PLP", or a single string of one of the method
        use_tfa, use_sfa: (Optional) [bool] to use TFA and/or SFA in panco PLP analysis.

        Return:
        -------------
        result_num: Number of results loaded from execution
        '''
        if netfile is None:
            if self.netfile is None:
                raise RuntimeError("No network definition file loaded")
            netfile = self.netfile

        op_net_path, phy_net_path = self.convert_netfile(netfile)

        start_res_num = len(self.results)
        self.analyze_dnc(op_net_path, methods=methods)
        self.analyze_linear(op_net_path, methods=methods)
        self.analyze_xtfa(phy_net_path, methods=methods)
        self.analyze_panco(op_net_path, methods=methods, use_tfa=use_tfa, use_sfa=use_sfa)

        return len(self.results) - start_res_num


    def analyze_xtfa(self, netfile:str=None, methods:Union[list,str]=["TFA"]) -> None:
        '''
        Analyze the network with xTFA

        Parameters:
        -------------
        netfile: (Optional) [str] File name of the network definition, must in either WOPANet XML format or output-port JSON.
                 Default is to select the netfile stored in the class, raise error if both are not defined.
        methods: (Optional) [list | str] List of "TFA", "SFA", or "PLP", or a single string of one of the method. Ignores methods other than TFA
                 Default is TFA
        '''
        netfile, methods = self._arg_check(netfile, methods, "xml")
        from_converted_file = self.script_handler.get_network_info(netfile, "converted", "")

        for mthd in methods:
            print(f"Analyzing \"{netfile}\" using xTFA-{mthd}...", end="", flush=True)
            if mthd.upper() != "TFA":
                print(f"Skip, no such method \"{mthd}\" for xTFA")
                continue

            if self.output_shaping == FORCE_SHAPER.AUTO or self.output_shaping == FORCE_SHAPER.ON:
                include_tech = ["FIFO+IS"]
                exclude_tech = []
            elif self.output_shaping == FORCE_SHAPER.OFF:
                include_tech = ["FIFO"]
                exclude_tech = ["IS"]

            # xTFA use the "technology" entry defined in the file for shaper usage, generate a new file that enforces the shaper technology
            file_enforce_method = self.script_handler.enforce_technology(in_filename=netfile, include_tech=include_tech, exclude_tech=exclude_tech, out_filename=add_text_in_ext(os.path.join(self._temp_path, "tempnet.xml"), "enforced"))
            jsonnet = self.script_handler.phynet_to_opnet_json(file_enforce_method)

            # Load the network into xTFA network to prepare for computation
            xtfa_net = xtfa.networks.CyclicNetwork(xtfa.fasUtility.TopologicalSort())
            reader = xtfa.networks.WopanetReader()
            reader.configure_network_from_xml(xtfa_net, file_enforce_method)
            xtfa_net.auto_install_pipelines()

            # compute and measure execution time
            start_time = time()
            xtfa_net.compute()
            exec_time = time() - start_time
            # determine execution time multiplier
            new_time, mul = unit_util.decide_multiplier(exec_time)
            if self.exec_time_mul is None:
                self.exec_time_mul = mul
            elif unit_util.multipliers[mul] < unit_util.multipliers[self.exec_time_mul]:
                self.exec_time_mul = mul

            # Extract delay information
            server_delays, total_network_delay = self._xtfa_delay_per_server(xtfa_net, len(from_converted_file)>0)
            flow_paths, flow_cmu_delays = self._xtfa_delay_per_flow(xtfa_net, len(from_converted_file)>0)
            # determine delay multiplier
            min_mul = unit_util.decide_min_multiplier(server_delays.values())
            if self.serv_delay_mul is None:
                self.serv_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.serv_delay_mul]:
                self.serv_delay_mul = min_mul

            flow_delays = dict()
            for fl_name, cmu_delays in flow_cmu_delays.items():
                flow_delays[fl_name] = cmu_delays[-1]
            # determine delay multiplier
            min_mul = unit_util.decide_min_multiplier(flow_delays.values())
            if self.flow_delay_mul is None:
                self.flow_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.flow_delay_mul]:
                self.flow_delay_mul = min_mul

            # Ensure graph
            # if it's converted, name without port
            if len(from_converted_file)>0:
                server_names = [serv["name"].rsplit('-',1)[0] if serv["name"] in xtfa_net.gif.nodes else serv["name"] for serv in jsonnet["servers"]]
            else:
                server_names = [serv["name"] for serv in jsonnet["servers"]]
            graph = nx.DiGraph(xtfa_net.gif.subgraph(server_names))
            for nd in server_names:
                if nd not in graph.nodes:
                    graph.add_node(nd)
                if nd not in server_delays:
                    server_delays[nd] = 0.0

            # Extract general network information
            result = TSN_result(
                name  = xtfa_net.name,
                tool  = "xTFA",
                method = mthd.upper(),
                graph  = graph,
                num_servers = len(server_delays),
                num_flows   = len(flow_paths),
                total_delay = total_network_delay,
                server_delays = server_delays,
                flow_paths  = flow_paths,
                flow_cmu_delays = flow_cmu_delays,
                flow_delays = flow_delays,
                exec_time   = exec_time,
                network_source      = netfile,
                from_converted_file = from_converted_file
            )
            self.results.append(result)
            
            print("Done")


    def analyze_linear(self, netfile:str=None, methods:Union[list,str]=["TFA"]) -> None:
        '''
        Analyze the network with Linear solver

        Parameters:
        -------------
        netfile: (Optional) [str] File name of the network definition, must in either WOPANet XML format or output-port JSON.
                 Default is to select the netfile stored in the class, raise error if both are not defined.
        methods: (Optional) [list | str] List of "TFA", "SFA", or "PLP", or a single string of one of the method. Ignores methods other than TFA
                 Default is TFA
        '''
        netfile, methods = self._arg_check(netfile, methods, "json")

        for mthd in methods:
            print(f"Analyzing \"{netfile}\" using LinearSolver-{mthd}...", end="", flush=True)
            if mthd.upper() not in {"TFA"}:
                print(f"Skip, no such method \"{mthd}\" for Linear solver")
                continue

            linear_solver = Linear_TFA(netfile)

            # solve and time measuring
            start_time = time()
            if self.output_shaping == FORCE_SHAPER.AUTO:
                delays = linear_solver.solve()
            elif self.output_shaping == FORCE_SHAPER.ON:
                delays = linear_solver.solve_tfa_pp()
            elif self.output_shaping == FORCE_SHAPER.OFF:
                delays = linear_solver.solve_tfa()
            exec_time = time() - start_time

            # determine multiplier
            new_time, mul = unit_util.decide_multiplier(exec_time)
            if self.exec_time_mul is None:
                self.exec_time_mul = mul
            elif unit_util.multipliers[mul] < unit_util.multipliers[self.exec_time_mul]:
                self.exec_time_mul = mul

            # Get server info
            server_delays = dict()
            server_names = list()
            for serv_id, server in enumerate(linear_solver.servers):
                server_names.append(server.get("name", f"sw_{serv_id}"))
                server_delays[server_names[-1]] = delays[serv_id]
            # determine min multiplier
            min_mul = unit_util.decide_min_multiplier(server_delays.values())
            if self.serv_delay_mul is None:
                self.serv_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.serv_delay_mul]:
                self.serv_delay_mul = min_mul
                
            # Get flow info
            flow_paths = dict()
            flow_cmu_delays = dict()
            flow_delays = dict()
            for flow_id, flow in enumerate(linear_solver.flows):
                flow_name = flow.get("name", f"fl_{flow_id}")
                flow_paths[flow_name] = list()
                flow_cmu_delays[flow_name] = list()

                delay = 0
                for serv_id in flow["path"]:     # list of server indices
                    flow_paths[flow_name].append(server_names[serv_id])
                    delay += delays[serv_id]
                    flow_cmu_delays[flow_name].append(delay)
                flow_delays[flow_name] = delay
            
            # determine delay multiplier
            min_mul = unit_util.decide_min_multiplier(flow_delays.values())
            if self.flow_delay_mul is None:
                self.flow_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.flow_delay_mul]:
                self.flow_delay_mul = min_mul
                
            # Create a directed graph
            net_graph = nx.from_numpy_array(linear_solver.adjacency_mat, create_using=nx.DiGraph)
            graph_name_mapping = dict(zip(list(range(len(server_names))), server_names))
            net_graph = nx.relabel_nodes(net_graph, graph_name_mapping)

            # Create a result container
            result = TSN_result(
                name = linear_solver.network_info.get("name", ""),
                tool = "Linear",
                method = mthd.upper(),
                graph = net_graph,
                num_servers = linear_solver.num_servers,
                num_flows   = linear_solver.num_flows,
                total_delay = sum(delays),
                server_delays = server_delays,
                flow_paths  = flow_paths,
                flow_cmu_delays = flow_cmu_delays,
                flow_delays = flow_delays,
                exec_time   = exec_time,
                network_source      = netfile,
                from_converted_file = self.script_handler.get_network_info(netfile, "converted", "")
            )
            self.results.append(result)

            print("Done")


    def analyze_panco(self, netfile:str=None, methods:list=["PLP"], use_tfa:bool=True, use_sfa:bool=True) -> None:
        '''
        Analyze the network with panco FIFO analyzer

        Parameters:
        -------------
        netfile: (Optional) [str] File name of the network definition, must in either WOPANet XML format or output-port JSON.
                 Default is to select the netfile stored in the class, raise error if both are not defined.
        methods: (Optional) [list | str] List of "TFA", "SFA", or "PLP", or a single string of one of the method.
                 Default is TFA
        '''
        netfile, methods = self._arg_check(netfile, methods, "json")


        for mthd in methods:
            print(f"Analyzing \"{netfile}\" using panco-{mthd}...", end="", flush=True)
            if mthd not in {"TFA", "SFA", "PLP", "ELP"}:
                print(f"Skip, no such method \"{mthd}\" for PLP solver")
                continue
                
            panco_anzr = panco_analyzer(netfile)
            output_shaping = self.output_shaping == FORCE_SHAPER.AUTO or self.output_shaping == FORCE_SHAPER.ON
            panco_anzr.build_network(output_shaping)
                
            # analyze result and check time
            start_time = time()
            delay_per_flow, delay_per_server = panco_anzr.analyze(method=mthd, lp_file=os.path.join(self._temp_path, f"fifo_{mthd}.lp"), use_tfa=use_tfa, use_sfa=use_sfa, output_shaping=output_shaping)
            exec_time = time() - start_time

            # determine execution time multiplier
            new_time, mul = unit_util.decide_multiplier(exec_time)
            if self.exec_time_mul is None:
                self.exec_time_mul = mul
            elif unit_util.multipliers[mul] < unit_util.multipliers[self.exec_time_mul]:
                self.exec_time_mul = mul

            server_delays = None
            total_delay = None
            flow_cmu_delays = None
            if delay_per_server is not None:
                server_delays = dict(zip(panco_anzr.server_names, delay_per_server))
                total_delay = sum(delay_per_server)

                # determine min multiplier
                min_mul = unit_util.decide_min_multiplier(server_delays.values())
                if self.serv_delay_mul is None:
                    self.serv_delay_mul = min_mul
                elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.serv_delay_mul]:
                    self.serv_delay_mul = min_mul

                # resolve flow cmu
                flow_cmu_delays = dict()
                for fl in panco_anzr.flows_info:
                    flow_cmu_delays[fl["name"]] = list()

                    delay = 0
                    for serv_id in fl["path"]:     # list of server indices
                        delay += delay_per_server[serv_id]
                        flow_cmu_delays[fl["name"]].append(delay)

            else:
                # determine min multiplier
                min_mul = unit_util.decide_min_multiplier(delay_per_flow)
                if self.serv_delay_mul is None:
                    self.serv_delay_mul = min_mul
                elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.serv_delay_mul]:
                    self.serv_delay_mul = min_mul

            flow_paths = dict()
            for fl in panco_anzr.flows_info:
                flow_paths[fl["name"]] = [panco_anzr.server_names[p] for p in fl["path"]]

            flow_delays = dict(zip(panco_anzr.flow_names, delay_per_flow))
            # determine delay multiplier
            min_mul = unit_util.decide_min_multiplier(flow_delays.values())
            if self.flow_delay_mul is None:
                self.flow_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.flow_delay_mul]:
                self.flow_delay_mul = min_mul

            # Create a directed graph
            net_graph = nx.from_numpy_array(panco_anzr.adjacency_mat, create_using=nx.DiGraph)
            graph_name_mapping = dict(zip(list(range(len(panco_anzr.server_names))), panco_anzr.server_names))
            net_graph = nx.relabel_nodes(net_graph, graph_name_mapping)

            # Create a result container
            result = TSN_result(
                name = panco_anzr.network_info.get("name", ""),
                tool = "Panco",
                method = mthd.upper(),
                graph = net_graph,
                num_servers = panco_anzr.num_servers,
                num_flows   = panco_anzr.num_flows,
                total_delay = total_delay,
                server_delays = server_delays,
                flow_paths  = flow_paths,
                flow_cmu_delays = flow_cmu_delays,
                flow_delays = flow_delays,
                exec_time   = exec_time,
                network_source      = netfile,
                from_converted_file = self.script_handler.get_network_info(netfile, "converted", "")
            )
            self.results.append(result)

            print("Done")


    def analyze_dnc(self, netfile:str=None, methods:Union[list,str]=["TFA"]) -> None:
        '''
        Analyze the network with xTFA

        Parameters:
        -------------
        netfile: (Optional) [str] File name of the network definition, must in either WOPANet XML format or output-port JSON.
                 Default is to select the netfile stored in the class, raise error if both are not defined.
        methods: (Optional) [list | str] List of "TFA", "SFA", or "PLP", or a single string of one of the method. Ignores "PLP"
                 Default is TFA
        '''
        netfile, methods = self._arg_check(netfile, methods, "json")

        # result is a UTF-8 string containing json format of result separated by flows
        print("Analyzing \"{fname}\" using DNC-{methods}...".format(fname=netfile, methods=','.join(methods)), end="", flush=True)
        # check if methods are valid
        supported_methods = {"TFA", "SFA", "PMOO", "TMA"}
        if not set(methods).issubset(supported_methods):
            not_supported = set(methods) - supported_methods
            executable_methods = list(set(methods).intersection(supported_methods))
            if len(executable_methods) == 0:
                print(f"Skip, all methods {methods} are not available")
                return
            else:
                print(f"\n -> Methods {not_supported} are not available for DNC, choose executable methods {executable_methods}...", end="")
                # For PMOO & TMA, allow manual shaping control
                for mid in range(len(executable_methods)):
                    if executable_methods[mid] in {"PMOO", "TMA"}:
                        if self.output_shaping == FORCE_SHAPER.AUTO or self.output_shaping == FORCE_SHAPER.ON:
                            executable_methods[mid] += "++"
                methods = executable_methods
            
            

        if self.output_shaping == FORCE_SHAPER.ON:
            print("Skip. DNC doesn't support FIFO analysis with shaper")

        # determine if network is cyclic
        self.script_handler.load_opnet(netfile)
        if self.script_handler.is_cyclic():
            print("Abort: network is cyclic")
            return
            
        dnc_result_json_str = dnc_exe(netfile, self._jar_path, methods)

        # parse individual flows/methods into dictionaries
        result_by_methods = self._split_dnc_result(dnc_result_json_str)
        if len(result_by_methods) == 0:
            raise RuntimeError("No result obtained from DNC solver!")

        # extract result obtained by each method
        for method, res_per_method in result_by_methods.items():
            result = dict() # one result dictionary of all involved flows
            
            result["name"] = res_per_method[0].get("name", "")
            result["tool"] = "DNC"
            result["method"] = method
            server_names = res_per_method[0]["server_names"]
            result["num_servers"] = res_per_method[0].get("num_servers", len(server_names))

            # determine delays
            result["server_delays"] = res_per_method[0]["server_delays"]
            # determine min multiplier
            min_mul = unit_util.decide_min_multiplier(result["server_delays"].values())
            if self.serv_delay_mul is None:
                self.serv_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.serv_delay_mul]:
                self.serv_delay_mul = min_mul

            # determine backlogs
            result["server_backlogs"] = res_per_method[0]["server_backlogs"]
            # determine min multiplier
            min_mul = unit_util.decide_min_multiplier(result["server_backlogs"].values())
            if self.backlog_mul is None:
                self.backlog_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.backlog_mul]:
                self.backlog_mul = min_mul
            max_backlogs = list()
            

            flow_name = res_per_method[0]["flow_name"]
            result["flow_paths"] = dict()
            result["flow_cmu_delays"] = dict()
            result["flow_delays"] = dict()
            result["flow_paths"][flow_name] = res_per_method[0]["flow_paths"]
            result["flow_cmu_delays"][flow_name] = res_per_method[0]["flow_cmu_delays"]
            result["flow_delays"][flow_name] = res_per_method[0]["flow_delays"]

            result["exec_time"] = res_per_method[0]["exec_time"]
            # determine multiplier
            new_time, mul = unit_util.decide_multiplier(result["exec_time"])
            if self.exec_time_mul is None:
                self.exec_time_mul = mul
            elif unit_util.multipliers[mul] < unit_util.multipliers[self.exec_time_mul]:
                self.exec_time_mul = mul

            for res_per_flow in res_per_method[1:]:
                flow_name = res_per_flow["flow_name"]
                result["flow_paths"][flow_name] = res_per_flow["flow_paths"]
                result["flow_cmu_delays"][flow_name] = res_per_flow["flow_cmu_delays"]
                result["flow_delays"][flow_name] = res_per_flow["flow_delays"]

                result["server_delays"].update(res_per_flow["server_delays"])
                result["server_backlogs"].update(res_per_flow["server_backlogs"])

                server_names = list_update_none(server_names, res_per_flow["server_names"])
                max_backlogs.append(float(res_per_flow["max_backlog"]))
                result["exec_time"] += res_per_flow["exec_time"]

            result["num_flows"] = res_per_method[0].get("num_flows", len(result["flow_delays"]))

            # determine delay multiplier
            min_mul = unit_util.decide_min_multiplier(result["flow_delays"].values())
            if self.flow_delay_mul is None:
                self.flow_delay_mul = min_mul
            elif unit_util.multipliers[min_mul] < unit_util.multipliers[self.flow_delay_mul]:
                self.flow_delay_mul = min_mul

            # Check empty result, change to None if all empty
            if all([len(delays)==0 for delays in result["flow_cmu_delays"].values()]):
                result["flow_cmu_delays"] = None

            if result["server_delays"] == None:
                result["total_delay"] = None
            else:
                result["total_delay"] = sum(result["server_delays"].values())
            result["max_backlog"] = max(max_backlogs)

            # Create a directed graph
            adj_mat = np.array(res_per_method[0]["adjacency_matrix"])
            result["graph"] = nx.from_numpy_array(adj_mat, create_using=nx.DiGraph)
            graph_name_mapping = dict(zip(list(range(len(server_names))), server_names))
            result["graph"] = nx.relabel_nodes(result["graph"], graph_name_mapping)

            result["network_source"] = netfile
            result["from_converted_file"] = self.script_handler.get_network_info(netfile, "converted", "")

            # Push result into result pool
            self.results.append(TSN_result(**result))

        print("Done")


    def convert_netfile(self, in_netfile:str, out_netfile:str=None, target:str=None) -> tuple:
        '''
        Convert the network definition file to another format, returns the paths to files having both formats in the order of .json, .xml

        Inputs:
        ----------
        in_netfile  : Path of a network description file as a source
        out_netfile : Path to dump the output network description file converted from "in_netfile"
        target      : If target is None, then this method convert anyway and return 2 formats
                      If target is given as "xml" or "json", it only convert the file when necessary and return the other unnecessary one as None

        Return:
        ----------
        op_net_path  : path to output port network file
        phy_net_path : path to physical network file
        '''
        phy_net_path = out_netfile
        op_net_path = out_netfile

        # In case receiving a physical net
        if in_netfile.endswith("xml"):
            # Check if it's already target
            if type(target) is str:
                if target.lower() == "xml":
                    return None, in_netfile
            # Conversion is needed
            print("Receiving an XML file, converting to a JSON ...",end="")
            if op_net_path is None:
                op_net_path = os.path.join(self._temp_path, "tempnet.json")
            self.script_handler.phynet_to_opnet_json(in_netfile, op_net_path)
            phy_net_path = in_netfile
            print("Done")

        # incase receiving a 
        elif in_netfile.endswith("json"):
            # Check if it's already target
            if type(target) is str:
                if target.lower() == "json":
                    return in_netfile, None

            # Conversion is needed
            print("Receiving a JSON file, converting to an XML ...",end="")
            if phy_net_path is None:
                phy_net_path = os.path.join(self._temp_path, "tempnet.xml")
            self.script_handler.opnet_json_to_phynet(in_netfile, phy_net_path)
            op_net_path = in_netfile
            print("Done")

        return op_net_path, phy_net_path
        

    def _arg_check(self, netfile:str, methods:Union[list,str], target_format:str) -> tuple:
        '''
        Check the arguments of each "analyze_xxx" method and returns the desired network file and methods as a list

        Inputs:
        ----------
        netfile : File name of the network definition, must in either WOPANet XML format or output-port JSON.
                  Default is to select the netfile stored in the class, raise error if both are not defined.
        methods : List of "TFA", "SFA", or "PLP", or a single string of one of the method. Default is TFA.
        target_format : either "json" or "xml" to select the output netfile format

        Returns:
        ----------
        netfile: path to the file with desired network format
        methods: a list of all methods
        '''

        if netfile is None:
            if self.netfile is None:
                raise RuntimeError("No network definition file loaded")
            netfile = self.netfile
        if type(methods) is str:
            methods = [methods]
        elif type(methods) is not list:
            methods = list(methods)
        
        for mid in range(len(methods)):
            methods[mid] = methods[mid].upper()

        # want json file
        if target_format.lower() == "json":
            netfile, phynet = self.convert_netfile(in_netfile=netfile, target=target_format)
        elif target_format.lower() == "xml":
            opnet, netfile  = self.convert_netfile(in_netfile=netfile, target=target_format)
        else:
            raise ValueError("Unrecognized file format \"{ufm}\" as target for file conversion".format(ufm=target_format))

        return netfile, methods

    def _split_dnc_result(self, dnc_result:str) -> dict:
        '''
        Split the dnc results from json string to dictionary of
        key = method used. e.g. "TFA", "SFA"
        value = list of results by each flow (dict)
        '''
        result_by_methods = dict()
        for result_per_flow in dnc_result.splitlines(keepends=False):
            try:
                result_json = json.loads(result_per_flow)
            except Exception as e:
                raise RuntimeError("Incorrect DNC output, you may need to check the DNC output")

            method = result_json.pop("method")
            if method not in result_by_methods:
                result_by_methods[method] = list()

            result_by_methods[method].append(result_json)
                
        return result_by_methods


    def _xtfa_delay_per_server(self, xtfa_net:xtfa.networks.CyclicNetwork, is_converted:bool=False, ignore_dummy:bool=True) -> tuple:
        '''
        Return the per server delay in a dictionary and also the total delay among all servers

        Parameters:
        -------------
        xtfa_net: the xTFA networks object after processing
        ignore_dummy: ignore the servers with 0 delay if set True

        Returns:
        -------------
        server_delays: dictionary with key=server_name & value=delay
        total_delay: total delay for all servers in the network
        '''
        total_delay = 0
        server_delay = dict()
        for nd in xtfa_net.gif.nodes:
            delay = xtfa_net.gif.nodes[nd]["model"].contentionDelayMax
            if ignore_dummy and delay <= 0:
                continue
            ser_name = nd.rsplit('-', 1)[0] if is_converted else nd
            server_delay[ser_name] = delay
            total_delay += delay

        return server_delay, total_delay

    def _xtfa_delay_per_flow(self, xtfa_net:xtfa.networks.CyclicNetwork, is_converted:bool=False, ignore_dummy=True) -> dict:
        '''
        Return the per flow delay

        Parameters:
        -------------
        xtfa_net: the xTFA networks object after processing
        ignore_dummy: ignore the servers with 0 delay if set True

        Returns:
        -------------
        flow_paths: dictionary with key=flow_name & value=list of paths (written in server names)
        flow_cum_delays: dictionary with key=flow_name & value=list of cumulative delays along the path
        '''
        flow_paths = dict()
        flow_cmu_delays = dict()

        for flow in xtfa_net.flows:
            cumulative_delays = list()
            for nd in flow.graph.nodes:
                cum_delay = flow.graph.nodes[nd]["flow_states"][0].maxDelayFrom["source"]
                if ignore_dummy and cum_delay <= 0:
                    continue
                ser_name = nd.rsplit('-', 1)[0] if is_converted else nd
                cumulative_delays.append((ser_name, cum_delay))

            cumulative_delays.sort(key=lambda d: d[1])
            flow_paths[flow.name] = [d[0] for d in cumulative_delays]
            flow_cmu_delays[flow.name] = [d[1] for d in cumulative_delays]
        
        return flow_paths, flow_cmu_delays


    def _build_flow_summary(self, mdFile:mdu, tm_results:dict)->None:
        '''
        Build a server result table on mdFile using result_dict, dict key = "tool-method", value is result object

        Inputs:
        ---------
        mdFile: the markdown file to write
        tm_results: a dictionary with key="tool-method", value=corresponding result
        '''
        mdFile.new_header(level=2, title=f"End-to-End delay bound")
        mdFile.new_line(f"Unit in {unit_util.multiplier_names[self.flow_delay_mul]}seconds")

        paths = dict()
        tlm_mapping = dict(zip(tm_results.keys(), range(len(tm_results))))
        flow_mapping = self._create_mapping(tm_results.values(), "flow_delays")
        table_res = np.empty((len(flow_mapping)+1, len(tlm_mapping)+1), dtype='object')
        table_res[:] = "N/A"

        # Column labels
        table_res[0,:] = ["Flow name", *tlm_mapping.keys()]
        # row labels
        table_res[1:,0] = list(flow_mapping.keys())

        for tlm, res in tm_results.items():
            paths.update(res.flow_paths)
            for flow_name, flow_delay in res.flow_delays.items():
                table_res[flow_mapping[flow_name]+1, tlm_mapping[tlm]+1] = "{:.3f}".format(flow_delay / unit_util.multipliers[self.flow_delay_mul])

        # write into MD
        table_res = table_res.flatten().tolist()
        mdFile.new_table(rows=len(flow_mapping)+1, columns=len(tlm_mapping)+1, text=table_res)
        
        # Write flow paths
        mdFile.new_header(level=2, title=f"Flow paths")
        path_to_print = list()
        for flow_name, path in paths.items():
            italic_path = [f"_{p}_" for p in path]
            path_to_print.append(f"**{flow_name}**: {' -> '.join(italic_path)}")
            # mdFile.new_line(f"**{flow_name}**: {' -> '.join(italic_path)}")
        mdFile.new_list(items=path_to_print)


    def _build_server_result_table(self, mdFile:mdu, tm_results:dict, target:str)->None:
        '''
        Build a server result table on mdFile using result_dict

        Inputs:
        ---------
        mdFile: the markdown file to write
        tm_results: a dictionary with key="tool-method", value=corresponding result
        target: delay or backlog to print different attributes
        '''
        if target.lower()=="delay":
            title_name = "Delay"
            attr_name = "server_delays"
            summary_label = "Total"
            summary_attr = "total_delay"
            multiplier = self.serv_delay_mul
            unit = "second"
        if target.lower()=="backlog":
            title_name = "Backlog"
            attr_name = "server_backlogs"
            summary_label = "Max"
            summary_attr = "max_backlog"
            multiplier = self.backlog_mul
            unit = "bit"

        if all([getattr(res, attr_name) is None for res in tm_results.values()]):
            return
        
        mdFile.new_header(level=2, title=f"{title_name} bound")
        mdFile.new_line(f"Unit in {unit_util.multiplier_names[multiplier]}{unit}")

        # Table with mapping assigned
        server_mapping = self._create_mapping(tm_results.values(), ["graph", "nodes"])
        tlm_mapping = dict(zip(tm_results.keys(), range(len(tm_results))))
        table_res = np.empty((len(server_mapping)+2, len(tlm_mapping)+1), dtype='object')
        table_res[:] = "N/A"

        # column/row labels
        table_res[0,:] = ["server name", *tlm_mapping.keys()]
        table_res[1:-1,0] = list(server_mapping.keys())
        table_res[-1,0] = summary_label

        for tlm, res in tm_results.items():
            if getattr(res, attr_name) is None:
                continue
            for server_name, attr_num in getattr(res, attr_name).items():
                table_res[server_mapping[server_name]+1, tlm_mapping[tlm]+1] = "{:.3f}".format(attr_num / unit_util.multipliers[multiplier])

            summary = getattr(res,summary_attr)
            if summary is None:
                table_res[-1,tlm_mapping[tlm]+1] = "N/A"
            else:
                table_res[-1,tlm_mapping[tlm]+1] = "{:.3f}".format(summary/unit_util.multipliers[multiplier])

        # write into MD
        table_res = table_res.flatten().tolist()
        mdFile.new_table(rows=len(server_mapping)+2, columns=len(tlm_mapping)+1, text=table_res)
        


    def _build_flow_result_table(self, mdFile:mdu, tm_results:dict, flow_of_interest:str)->None:
        '''
        Build a flow result table on flow_of_interest over mdFile using result_dict

        Inputs:
        ---------
        mdFile: the markdown file to write
        tm_results: a dictionary with key="tool-method", value=corresponding result
        flow_of_interest: the name of flow to print
        '''
        if all([res.flow_cmu_delays is None for res in tm_results.values()]):
            return

        mdFile.new_header(level=2, title=f"Flow \"{flow_of_interest}\"")
        mdFile.new_line("The name in the table is written according to the path")
        path = next(iter(tm_results.values())).flow_paths[flow_of_interest]

        mdFile.new_header(level=3, title=f"Cumulative delay according to path")
        mdFile.new_line(f"Unit in {unit_util.multiplier_names[self.serv_delay_mul]}seconds")
        
        # Table as a numpy array with initial value ""
        tlm_mapping = dict(zip(tm_results.keys(), range(len(tm_results))))
        table_res = np.empty((len(path)+1, len(tlm_mapping)+1), dtype='object')
        table_res[:] = "N/A"
        
        # column labels
        table_res[0,:] = ["server name", *tlm_mapping.keys()]
        # row labels
        table_res[1:,0] = path

        # fill in the contents
        for tlm, res in tm_results.items():
            if res.flow_cmu_delays is None:
                continue
            vals = np.array(res.flow_cmu_delays[flow_of_interest]) / unit_util.multipliers[self.serv_delay_mul]
            if len(vals) > 0:
                table_res[1:,tlm_mapping[tlm]+1] = list(map("{:.3f}".format, vals))

        # write into MD
        table_res = table_res.flatten().tolist()
        mdFile.new_table(rows=len(path)+1, columns=len(tlm_mapping)+1, text=table_res)


    def _build_performance_table(self, mdFile:mdu, tm_results:dict)->None:
        '''
        Build a flow result table on flow_of_interest over mdFile using result_dict

        Inputs:
        ---------
        mdFile: the markdown file to write
        tm_results: a dictionary with key="tool-method", value=corresponding result
        '''

        result_method_dict = dict()
        for r in tm_results.values():
            if r.method not in result_method_dict:
                result_method_dict[r.method] = list()
            result_method_dict[r.method].append(r)

        mdFile.new_line(f"Unit in {unit_util.multiplier_names[self.exec_time_mul]}seconds")

        col_num = max([len(ress) for ress in result_method_dict.values()])+1
        table_perv = np.empty((len(result_method_dict)+1, col_num), dtype='object')
        table_perv[:] = "N/A"
        # row labels
        table_perv[:,0] = ["method name", *result_method_dict.keys()]
        # column labels
        tools = set()
        for ress in result_method_dict.values():
            for r in ress:
                tools.add(r.tool)
        tool_mapping = dict(zip(sorted(list(tools)), range(len(tools))))
        table_perv[0,1:] = list(tool_mapping.keys())

        # fill in the contents
        for mid, res_same_method in enumerate(result_method_dict.values()):
            for res in res_same_method:
                table_perv[mid+1, tool_mapping[res.tool]+1] = "{:.3f}".format(res.exec_time / unit_util.multipliers[self.exec_time_mul])

        # write into MD
        table_perv = table_perv.flatten().tolist()
        mdFile.new_table(rows=len(result_method_dict)+1, columns=col_num, text=table_perv)


    def _build_utility_map(self, mdFile:mdu, tm_results:dict)->None:
        '''
        Build a table of utility map, load of each server i is computed as (sum of arrival rates at server i) / (service rate at server i)

        Inputs:
        ---------
        mdFile: the markdown file to write
        tm_results: a dictionary with key="tool-method", value=corresponding result
        '''
        ## Calculate utility
        for i, res in enumerate(tm_results.values()):
            if res.is_converted() and i<(len(tm_results)-1):
                continue
            
            utility = self.script_handler.get_network_utility(res.network_source)
            max_utility = max(utility.values())

            mdFile.new_header(level=2, title="Network Link Utilization")
            mdFile.new_line("Utilization for each link:")
            util_to_print = list()
            for ser_name, ser_utility in utility.items():
                util_to_print.append(f"`{ser_name}`: {ser_utility}")
            mdFile.new_list(items=util_to_print)
            mdFile.new_line(f"**Maximum Link Utilization** = {max_utility}")
            return
            

    def _create_mapping(self, x:list, attr_name:Union[str,list], start:int=0)->dict:
        '''
        creating a mapping for list x according the attr_name in each element of x

        example:
        >>> x = [{"attr": 1, ...}, {"attr": 2, ...}, {"attr": 1, ...}]
        >>> self._create_mapping(x, "attr")
        {1:0, 2:1}
        '''
        y = dict()
        index = start
        for elem in x:
            
            # solve attribute value
            if type(attr_name) is str:
                attr_val = getattr(elem, attr_name)
            if type(attr_name) is list:
                attr_val = elem
                for attr in attr_name:
                    attr_val = getattr(attr_val, attr)
                
            # Assign mapping value
            if type(attr_val) == str:
                if attr_val not in y:
                    y[attr_val] = index
                    index += 1
            elif isinstance(attr_val, Iterable):
                for k in attr_val:
                    if k not in y:
                        y[k] = index
                        index += 1
        return y

