
import xtfa.networks
import networkx as nx

class TSN_result():

    name            : str
    tool            : str
    method          : str
    graph           : nx.DiGraph
    num_servers     : int
    num_flows       : int
    server_delays   : dict
    total_delay     : float
    server_backlogs : dict
    max_backlog     : float
    flow_paths      : dict
    flow_cmu_delays : dict
    exec_time       : float

    def __init__(self, **kargs) -> None:
        self._name  = kargs.get("name", "")
        self._tool  = kargs.get("tool", "")
        self._graph = kargs.get("graph", nx.DiGraph())
        self._method = kargs.get("method", "")

        self._num_servers = kargs.get("num_servers", 0)
        self._num_flows = kargs.get("num_flows", 0)

        self._server_delays = kargs.get("server_delays", dict())
        self._total_delay = kargs.get("total_delay", None)

        self._server_backlogs = kargs.get("server_backlogs", dict())
        self._max_backlog = kargs.get("max_backlog", None)

        self._flow_paths = kargs.get("flow_paths", None)
        self._flow_cmu_delays = kargs.get("flow_delays", None)

        self._exec_time = kargs.get("exec_time", None)

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
        return self._num_servers

    @property
    def num_flows(self)->int:
        return self._num_flows
    
    @property
    def server_delays(self)->dict:
        return self._server_delays

    @property
    def total_delay(self)->float:
        return self._total_delay

    @property
    def server_backlogs(self)->dict:
        return self._server_backlogs

    @property
    def max_backlog(self)->float:
        return self._max_backlog

    @property
    def flow_paths(self)->dict:
        return self._flow_paths

    @property
    def flow_cmu_delays(self)->dict:
        return self._flow_cmu_delays

    @property
    def exec_time(self)->int:
        return self._exec_time