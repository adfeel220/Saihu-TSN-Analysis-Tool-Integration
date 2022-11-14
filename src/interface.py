import sys
import os.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

import xtfa.networks
import xtfa.fasUtility

from Linear_TFA.Linear_TFA import Linear_TFA
from netscript.netscript import *
from javapy.dnc_exe import dnc_exe
from result import TSN_result

from time import time
from typing import Union
from collections.abc import Iterable
import json
import networkx as nx
import numpy as np
from mdutils.mdutils import MdUtils as mdu
from matplotlib.pyplot import plot, savefig


def list_update_none(x1:list, x2:list) -> list:
    '''
    Replace None element in x1 with x2 with the same index
    '''
    return [x2[i] if x is None and i<len(x2) else x for i,x in enumerate(x1)]


class TSN_Analyzer():

    netfile        : str
    script_handler : NetworkScriptHandler
    results        : list
    _jar_path      : str
    _temp_path     : str

    def __init__(self, netfile:str=None, jar_path:str=os.path.abspath(os.path.join(os.path.dirname(__file__),"javapy/")), temp_path:str=os.path.abspath("./")) -> None:
        self.script_handler = NetworkScriptHandler()
        self.results = list()
        self.netfile = netfile
        self._jar_path = jar_path
        self._temp_path = temp_path

    def clear(self) -> None:
        self.script_handler = NetworkScriptHandler()
        self.results = list()
        self.netfile = None


    def write_result(self, output_file:str, clear:bool=True) -> None:
        '''
        Write the currently stored results
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
                output_file = add_text_in_ext(output_file, output_index)
            output_index += 1

            # Create the output Markdown file to write
            mdFile = mdu(file_name=output_file, title=f"Analysis Report - \"{net_name}\"")
            mdFile.new_paragraph("The is a automatically generated report with ...\n")
 
            ## Write general network information
            mdFile.new_header(level=1, title="General Information")
            mdFile.new_paragraph(f"This report contains {len(res)} analysis over network **\"{net_name}\"**.\n")
            mdFile.write(f"There are **{res[0].num_servers}** servers and **{res[0].num_flows}** flows in the system.")
            # topology
            nx.draw(res[0].graph, with_labels=True)
            graph_file_path = os.path.join(outpath, f"{net_name}_topo.png")
            savefig(graph_file_path, dpi=300, bbox_inches='tight')
            mdFile.new_header(level=2, title="Topology of network")
            mdFile.new_line(mdFile.new_reference_image(text="Network graph", path=graph_file_path, reference_tag='topo'))
            # performance
            mdFile.new_header(level=2, title="Performance")
            mdFile.new_line("Unit in seconds")
            self._build_performance_table(mdFile, res_by_methods)
            
            
            # Server delays / backlogs
            mdFile.new_header(level=1, title="Server Delay/Backlogs")
            self._build_server_result_table(mdFile, res_by_methods, "delay")
            
            # check if there's any backlog data
            backlog_mapping = self._create_mapping(res, "server_backlogs")
            if len(backlog_mapping) > 0:
                self._build_server_result_table(mdFile, res_by_methods, "backlog")
                
            ## Per flow result
            mdFile.new_header(level=1, title="Per Flow Delays")
            for foi in res[0].flow_paths.keys():
                mdFile.new_header(level=2, title=f"Flow \"{foi}\"")
                mdFile.new_line("The name in the table is written according to the path")
                self._build_flow_result_table(mdFile, res_by_methods, foi)
                
            
            # Create table of contents
            mdFile.new_table_of_contents(table_title="Table of Contents", depth=2)

            # Finally create the output file
            mdFile.create_md_file()

        # Clear the current results if 
        if clear:
            self.clear()

        print("Done")


    def analyze_all(self, netfile:str=None, methods:list=["TFA"]) -> int:
        '''
        Analyze the network with 3 methods: DNC, xTFA, Linear Solver

        Parameters:
        -------------
        netfile: File name of the network definition, must in either WOPANet XML format or output-port JSON : str
        methods: (Optional) List of either "TFA" or "TFA++"

        Return:
        -------------
        result_num: Number of results loaded from execution
        '''
        if netfile is None:
            netfile = self.netfile

        if netfile.endswith("xml"):
            print("Receiving an XML file, converting to a JSON ...",end="")
            op_net_path = os.path.join(self._temp_path, "tempnet.json")
            self.script_handler.phynet_to_opnet_json(netfile, op_net_path)
            phy_net_path = netfile
            print("Done")

        elif netfile.endswith("json"):
            print("Receiving a JSON file, converting to an XML ...",end="")
            phy_net_path = os.path.join(self._temp_path, "tempnet.xml")
            self.script_handler.opnet_json_to_phynet(netfile, phy_net_path)
            op_net_path = netfile
            print("Done")

        start_res_num = len(self.results)
        self.analyze_dnc(op_net_path, methods=methods)
        self.analyze_linear(op_net_path, methods=methods)
        self.analyze_xtfa(phy_net_path, methods=methods)

        return len(self.results) - start_res_num


    def analyze_xtfa(self, netfile:str=None, methods:list=["TFA"]) -> None:
        '''
        Analyze the network with xTFA

        Parameters:
        -------------
        netfile: File name of the network definition, must in WOPANet XML format : str
        methods: (Optional) List of either "TFA" or "TFA++"
        '''
        if netfile is None:
            netfile = self.netfile

        for mthd in methods:
            print(f"Analyzing \"{netfile}\" using xTFA-{mthd}...", end="")
            if mthd.upper() == "TFA":
                include_tech = ["FIFO"]
                exclude_tech = ["IS"]
            elif mthd.upper() == "TFA++":
                include_tech = ["FIFO+IS"]
                exclude_tech = []

            file_enforce_method = self.script_handler.enforce_technology(in_filename=netfile, include_tech=include_tech, exclude_tech=exclude_tech)
            jsonnet = self.script_handler.phynet_to_opnet_json(file_enforce_method)

            xtfa_net = xtfa.networks.CyclicNetwork(xtfa.fasUtility.TopologicalSort())
            reader = xtfa.networks.WopanetReader()
            reader.configure_network_from_xml(xtfa_net, file_enforce_method)
            xtfa_net.auto_install_pipelines()

            # compute and measure execution time
            start_time = time()
            xtfa_net.compute()
            exec_time = time() - start_time

            # Extract delay information
            server_delays, total_network_delay = self._xtfa_delay_per_server(xtfa_net)
            flow_paths, flow_cmu_delays = self._xtfa_delay_per_flow(xtfa_net)

            # Ensure graph
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
                method  = mthd.upper(),
                graph = graph,
                num_servers = len(server_delays),
                num_flows   = len(flow_paths),
                total_delay = total_network_delay,
                server_delays = server_delays,
                flow_paths  = flow_paths,
                flow_delays = flow_cmu_delays,
                exec_time   = exec_time
            )
            self.results.append(result)
            
            print("Done")


    def analyze_linear(self, netfile:str=None, methods:list=["TFA"]) -> None:
        '''
        Analyze the network with Linear solver

        Parameters:
        -------------
        netfile: File name of the network definition, must in JSON format : str
        methods: (Optional) List of either "TFA" or "TFA++"
        '''
        if netfile is None:
            netfile = self.netfile

        for mthd in methods:
            print(f"Analyzing \"{netfile}\" using LinearSolver-{mthd}...", end="")

            linear_solver = Linear_TFA(netfile)

            # solve and time measuring
            start_time = time()
            if mthd.upper() == "TFA":
                delays = linear_solver.solve_tfa()
            elif mthd.upper() == "TFA++":
                delays = linear_solver.solve_tfa_pp()
            exec_time = time() - start_time

            # Get server info
            server_delays = dict()
            server_names = list()
            for serv_id, server in enumerate(linear_solver.servers):
                server_names.append(server.get("name", f"sw_{serv_id}"))
                server_delays[server_names[-1]] = delays[serv_id]
                
            # Get flow info
            flow_paths = dict()
            flow_cmu_delays = dict()
            for flow_id, flow in enumerate(linear_solver.flows):
                flow_name = flow.get("name", f"fl_{flow_id}")
                flow_paths[flow_name] = list()
                flow_cmu_delays[flow_name] = list()

                flow_delay = 0
                for serv_id in flow["path"]:     # list of server indices
                    flow_paths[flow_name].append(server_names[serv_id])
                    flow_delay += delays[serv_id]
                    flow_cmu_delays[flow_name].append(flow_delay)
                
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
                flow_delays = flow_cmu_delays,
                exec_time   = exec_time
            )
            self.results.append(result)

            print("Done")

    def analyze_dnc(self, netfile:str=None, methods:list=["TFA"]) -> None:
        '''
        Analyze the network with xTFA

        Parameters:
        -------------
        netfile: File name of the network definition, must in JSON format : str
        methods: (Optional) List of either "TFA" or "TFA++"
        '''
        if netfile is None:
            netfile = self.netfile

        # result is a UTF-8 string containing json format of result separated by flows
        print("Analyzing \"{fname}\" using DNC-{methods}...".format(fname=netfile, methods='.'.join(methods)), end="")
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
            result["num_servers"] = res_per_method[0]["num_servers"]
            result["num_flows"] = res_per_method[0]["num_flows"]
            server_names = res_per_method[0]["server_names"]

            result["server_delays"] = res_per_method[0]["server_delays"]
            result["server_backlogs"] = res_per_method[0]["server_backlogs"]
            max_backlogs = list()

            flow_name = res_per_method[0]["flow_name"]
            result["flow_paths"] = dict()
            result["flow_delays"] = dict()
            result["flow_paths"][flow_name] = res_per_method[0]["flow_paths"]
            result["flow_delays"][flow_name] = res_per_method[0]["flow_delays"]

            result["exec_time"] = res_per_method[0]["exec_time"]

            for res_per_flow in res_per_method[1:]:
                flow_name = res_per_flow["flow_name"]
                result["flow_paths"][flow_name] = res_per_flow["flow_paths"]
                result["flow_delays"][flow_name] = res_per_flow["flow_delays"]

                result["server_delays"].update(res_per_flow["server_delays"])
                result["server_backlogs"].update(res_per_flow["server_backlogs"])

                server_names = list_update_none(server_names, res_per_flow["server_names"])
                max_backlogs.append(float(res_per_flow["max_backlog"]))
                result["exec_time"] += res_per_flow["exec_time"]

            result["total_delay"] = sum(result["server_delays"].values())
            result["max_backlog"] = max(max_backlogs)

            # Create a directed graph
            adj_mat = np.array(res_per_method[0]["adjacency_matrix"])
            result["graph"] = nx.from_numpy_array(adj_mat, create_using=nx.DiGraph)
            graph_name_mapping = dict(zip(list(range(len(server_names))), server_names))
            result["graph"] = nx.relabel_nodes(result["graph"], graph_name_mapping)

            # Push result into result pool
            self.results.append(TSN_result(**result))

        print("Done")
        

    def _split_dnc_result(self, dnc_result:str) -> dict:
        '''
        Split the dnc results from json string to dictionary of
        key = method used. e.g. "TFA", "TFA++"
        value = list of results by each flow (dict)
        '''
        result_by_methods = dict()
        for result_per_flow in dnc_result.splitlines(keepends=False):
            result_json = json.loads(result_per_flow)

            method = result_json.pop("method")
            if method not in result_by_methods:
                result_by_methods[method] = list()

            result_by_methods[method].append(result_json)
                
        return result_by_methods


    def _xtfa_delay_per_server(self, xtfa_net:xtfa.networks.CyclicNetwork, ignore_dummy=True) -> tuple:
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
            server_delay[nd] = delay
            total_delay += delay

        return server_delay, total_delay

    def _xtfa_delay_per_flow(self, xtfa_net:xtfa.networks.CyclicNetwork, ignore_dummy=True) -> dict:
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
                cumulative_delays.append((nd, cum_delay))

            cumulative_delays.sort(key=lambda d: d[1])
            flow_paths[flow.name] = [d[0] for d in cumulative_delays]
            flow_cmu_delays[flow.name] = [d[1] for d in cumulative_delays]
        
        return flow_paths, flow_cmu_delays


    def _build_server_result_table(self, mdFile:mdu, result_method_dict:dict, target:str)->None:
        '''
        Build a server result table on mdFile using result_dict
        '''
        if target.lower()=="delay":
            title_name = "Delay"
            attr_name = "server_delays"
            summary_label = "Total"
            summary_attr = "total_delay"
            unit = "second"
        if target.lower()=="backlog":
            title_name = "Backlog"
            attr_name = "server_backlogs"
            summary_label = "Max"
            summary_attr = "max_backlog"
            unit = "bit"

        for method, res_same_method in result_method_dict.items():

            mdFile.new_header(level=2, title=f"{title_name} bound using {method} (unit = {unit})")
            # Table as a numpy array with initial value ""
            server_mapping = self._create_mapping(res_same_method, ["graph", "nodes"])
            tool_mapping = self._create_mapping(res_same_method, "tool")
            table_res_same_method = np.empty((len(server_mapping)+2, len(tool_mapping)+1), dtype='object')
            table_res_same_method[:] = "N/A"
            
            # column labels
            table_res_same_method[0,:] = ["name", *tool_mapping.keys()]

            # row labels
            table_res_same_method[1:-1,0] = list(server_mapping.keys())
            table_res_same_method[-1,0] = summary_label

            # fill in the contents
            for res in res_same_method:
                for server_name, attr_num in getattr(res, attr_name).items():
                    table_res_same_method[server_mapping[server_name]+1, tool_mapping[res.tool]+1] = attr_num
                    
                # table_res_same_method[1:-1,rid+1] = [getattr(res, attr_name).get(nd,"N/A") for nd in table_res_same_method[1:-1,0]]
                table_res_same_method[-1,tool_mapping[res.tool]+1] = getattr(res,summary_attr)

            # write into MD
            table_res_same_method = table_res_same_method.flatten().tolist()
            mdFile.new_table(rows=len(server_mapping)+2, columns=len(tool_mapping)+1, text=table_res_same_method)


    def _build_flow_result_table(self, mdFile:mdu, result_method_dict:dict, flow_of_interest:str)->None:
        '''
        Build a flow result table on flow_of_interest over mdFile using result_dict
        '''
        for method, res_same_method in result_method_dict.items():
            
            path = res_same_method[0].flow_paths[flow_of_interest]

            mdFile.new_header(level=3, title=f"Cumulative delay using {method} (unit = second)")
            # Table as a numpy array with initial value ""
            tool_mapping = self._create_mapping(res_same_method, "tool")
            table_res_same_method = np.empty((len(path)+1, len(tool_mapping)+1), dtype='object')
            table_res_same_method[:] = ""
            
            # column labels
            table_res_same_method[0,:] = ["name", *tool_mapping.keys()]

            # row labels
            table_res_same_method[1:,0] = path

            # fill in the contents
            for res in res_same_method:
                table_res_same_method[1:,tool_mapping[res.tool]+1] = res.flow_cmu_delays[flow_of_interest]

            # write into MD
            table_res_same_method = table_res_same_method.flatten().tolist()
            mdFile.new_table(rows=len(path)+1, columns=len(res_same_method)+1, text=table_res_same_method)


    def _build_performance_table(self, mdFile:mdu, result_method_dict:dict)->None:
        '''
        Build a flow result table on flow_of_interest over mdFile using result_dict
        '''
        col_num = max([len(ress) for ress in result_method_dict.values()])+1
        table_perv = np.empty((len(result_method_dict)+1, col_num), dtype='object')
        # row labels
        table_perv[:,0] = ["name", *result_method_dict.keys()]
        # column labels
        tool_mapping = dict()
        for ress in result_method_dict.values():
            tool_mapping = {**self._create_mapping(ress, "tool"), **tool_mapping}
        table_perv[0,1:] = list(tool_mapping.keys())

        # fill in the contents
        for mid, res_same_method in enumerate(result_method_dict.values()):
            for res in res_same_method:
                table_perv[mid+1, tool_mapping[res.tool]+1] = res.exec_time

        # write into MD
        table_perv = table_perv.flatten().tolist()
        mdFile.new_table(rows=len(result_method_dict)+1, columns=col_num, text=table_perv)


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


if __name__ == "__main__":
    analyzer = TSN_Analyzer("../test_new.json", temp_path="../temp/")
    analyzer.analyze_all(methods=["TFA"])
    analyzer.write_result("./out.md", clear=False)