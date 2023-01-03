
import networkx as nx

class TSN_result():
    '''All analysis results will be converted into this format, the output report writer only takes this format'''
    name            : str           # Name of the network
    tool            : str           # Tool used in this analysis. e.g. DNC or panco
    method          : str           # Analysis method. e.g. TFA or PLP
    graph           : nx.DiGraph    # The graph representation of the network, including unused links
    num_servers     : int           # Number of servers in the network
    num_flows       : int           # Number of flows in the network
    server_delays   : dict          # Delays stored according to server names, unit in seconds. e.g. {'s_1': 1.0, 's_2': 2.0}
    total_delay     : float         # Sum of all server delays
    server_backlogs : dict          # Delays stored according to server names, unit in bits. e.g. {'s_1': 1.0, 's_2': 2.0}
    max_backlog     : int           # Maximum of all server backlogs
    flow_paths      : dict          # Path of each flow as a list of servers according to flow names. e.g. {'fl_1': ['s_1', 's_2']}
    flow_cmu_delays : dict          # Cumulative delays by each flow. e.g. {'fl_1': {'s_1': 1.0, 's_2': 3.0}}
    flow_delays     : dict          # End-to-end delays of each flow. e.g. {'fl_1': 4.0, 'fl_2': 7.0}
    exec_time       : float         # Execution time of the analysis, unit in seconds
    units           : dict          # Units used in the values, can take 'time', 'data' and 'rate'. e.g. {'time': 'us', 'data': 'MB', 'rate': 'Gbps}

    network_source  : str           # Source file for network definition where the result is computed
    converted_from  : str           # Which file it's converted from, "" if it's original



    def __init__(self, **kargs) -> None:
        self._name  = kargs.get("name", "NONAME")
        self._tool  = kargs.get("tool", "UNKNOWN_TOOL")
        self._graph = kargs.get("graph", nx.DiGraph())
        self._method = kargs.get("method", "UNKNOWN_METHOD")

        self._server_delays = kargs.get("server_delays", None)
        self._server_backlogs = kargs.get("server_backlogs", None)

        self._flow_paths = kargs.get("flow_paths", None)
        self._flow_delays = kargs.get("flow_delays", None)

        self._exec_time = kargs.get("exec_time", None)

        self._units = {"time": None, "data": None, "rate": None}
        self._units.update(kargs.get("units", dict()))
        # self._units.setdefault("time", None)
        # self._units.setdefault("data", None)
        # self._units.setdefault("rate", None)

        self._network_source = kargs.get("network_source", None)
        self._converted_from  = kargs.get("converted_from" , "")

    def __repr__(self) -> str:
        return "TSN_Result(name:{name}, tool:{tool}-{method})".format(name=self._name, tool=self._tool, method=self._method)


    def __str__(self) -> str:
        return self.__repr__()

    def __sizeof__(self) -> int:
        return self._num_servers

    def __hash__(self) -> int:
        return hash(self._name)

    def __eq__(self, __o: object) -> bool:
        return __o.name==self._name

    def get_general_info(self):
        '''
        Obtain a general information
        '''

    # Define read only properties
    @property
    def name(self)->str:
        return self._name

    @property
    def tool(self)->str:
        return self._tool
    
    @property
    def method(self)->str:
        return self._method

    @property
    def graph(self)->nx.DiGraph:
        return self._graph

    @property
    def num_servers(self)->int:
        return self._graph.number_of_nodes()

    @property
    def num_flows(self)->int:
        return len(self._flow_delays)
    
    @property
    def server_delays(self)->dict:
        return self._server_delays

    @property
    def total_delay(self)->float:
        if self._server_delays is None:
            return None
        return sum(self.server_delays.values())

    @property
    def server_backlogs(self)->dict:
        return self._server_backlogs

    @property
    def max_backlog(self)->float:
        if self._server_backlogs is None:
            return None
        return max(self._server_backlogs.values())

    @property
    def network_source(self)->dict:
        return self._network_source

    @property
    def flow_paths(self)->dict:
        return self._flow_paths

    @property
    def flow_cmu_delays(self)->dict:
        return self._flow_cmu_delays

    @property
    def flow_delays(self)->dict:
        return self._flow_delays

    @property
    def exec_time(self)->int:
        return self._exec_time

    @property
    def units(self)->dict:
        return self._units

    @property
    def converted_from(self)->bool:
        return self._converted_from

    def is_converted(self)->bool:
        return len(self._converted_from)>0