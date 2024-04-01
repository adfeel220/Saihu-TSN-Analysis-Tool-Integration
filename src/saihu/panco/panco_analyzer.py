import json
import warnings
from copy import deepcopy
import numpy as np

from netscript.netdef import OutputPortNet

# Import panco PLP modules
from panco.descriptor.curves import TokenBucket, RateLatency
from panco.descriptor.flow import Flow
from panco.descriptor.server import Server
from panco.descriptor.network import Network

from panco.fifo.fifoLP import FifoLP
from panco.fifo.tfaLP import TfaLP
from panco.fifo.sfaLP import SfaLP

# set custom warning message
def warning_override(
    message, category=UserWarning, filename="", lineno=-1, file=None, line=None
):
    print("Warning:", message, category)


warnings.showwarning = warning_override

def flow_is_multicast(flow:dict) -> bool:
    '''
    Return whether a flow is a multicast flow
    '''
    if "multicast" in flow:
        return len(flow["multicast"]) > 0
    return False

class panco_analyzer:
    """
    This class serves 3 purposes:
    1. Parse the network definition file
    2. Run analysis based on user selection
    3. Return result
    """

    network_info: dict
    adjacency_mat: np.ndarray
    flows_info: list
    servers_info: list
    server_no_flow: list

    network: Network
    servers: list
    flows: list
    server_names: list
    flows_names: list

    _methods = {"TFA", "SFA", "PLP"}

    def __init__(self, filename: str = None) -> None:
        # Directly loaded information, may not all used in analysis
        self.network_info = None
        self.adjacency_mat = None
        self.flows_info = list()
        self.servers_info = list()

        self.server_no_flow = set()
        self.shaper_defined = True

        # Translated info for PLP tool
        self.network = None
        self.flows = list()
        self.flow_names = list()
        self.servers = list()
        self.server_names = list()

        self.units = {"time": None, "data": None, "rate": None}

        if filename is not None:
            self.load(filename)

    def load(self, filename: str) -> None:
        """
        Load from a predefined network in json
        """
        with open(filename) as f:
            network_def = json.load(f)

        try:
            self.parse(network_def)
        except Exception as e:
            print(f"Capturing error while loading file {filename}.")
            raise e

    def parse(self, network_def: dict) -> None:
        """
        Parse the network into the information needed for this tool
        """
        # Read by output port network
        output_port_net = OutputPortNet(network_def=network_def)

        # Load general network information
        self.network_info = deepcopy(output_port_net.network_info)
        self.units = deepcopy(output_port_net.base_unit)
        self.adjacency_mat = output_port_net.adjacency_mat.copy()
        self.flows_info = deepcopy(output_port_net.flows)
        self.servers_info = deepcopy(output_port_net.servers)

        # Assign
        for ser in self.servers_info:
            ## Check server capacity
            # Turn off shaper if any of the server doesn't have shaper
            if "capacity" not in ser:
                self.shaper_defined = False
            elif ser["capacity"] <= 0:
                warnings.warn(
                    'Capacity of server "{0}" is non-positive, should at least >0. Ignore using shaper.'.format(
                        ser["name"]
                    )
                )

            # Assign server packet lengths by the maximum of max-packet-length of all flows that passes through this server
            pkt_len = [
                fl.get("max_packet_length", None) for fl in self.__get_flows(ser["id"])
            ]  # packet lengths of the involved flows
            if len(pkt_len) == 0:
                warnings.warn(
                    'No flow passes through server "{0}", you may remove it from the analysis'.format(
                        ser["name"]
                    )
                )
                self.server_no_flow.add(ser["id"])

            pkt_len = [mpl for mpl in pkt_len if mpl is not None]
            if len(pkt_len) > 0:
                ser["max_packet_length"] = max(pkt_len)
            else:
                self.shaper_defined = False

    def is_loaded(self) -> bool:
        """
        Return whether the analyzer has network loaded in
        """
        if self.network_info is None:
            return False
        if self.adjacency_mat is None:
            return False
        return True

    def build_network(self, use_shaper: bool = False) -> None:
        """
        Build a PLP network from currently stored network
        """
        if not self.is_loaded():
            raise RuntimeError(
                "Try to build a network without any network object loaded in the analyzer"
            )

        self.servers = list()
        self.server_names = list()

        ## Servers with service curves
        for ser_id, ser in enumerate(self.servers_info):
            self.server_names.append(ser.get("name", f"sw_{ser_id}"))

            service_curves = list()
            shapers = list()
            latencies = ser["service_curve"]["latencies"]
            rates = ser["service_curve"]["rates"]
            for i in range(len(rates)):
                rl_curve = RateLatency(rate=rates[i], latency=latencies[i])
                service_curves.append(rl_curve)
            if use_shaper:
                if self.shaper_defined:
                    packet_size = (
                        ser["max_packet_length"]
                        if self.network_info.get("packetizer", False)
                        else 0.0
                    )
                    tb_curve = TokenBucket(packet_size, ser["capacity"])
                    shapers.append(tb_curve)
                else:
                    warnings.warn(
                        "No shaper defined in network while trying to force applying shapers, switch to no shaper"
                    )

            # Append servers
            self.servers.append(Server(service_curves, shapers))

        self.flows = list()
        self.flow_names = list()
        ## Flows
        for fl_id, fl in enumerate(self.flows_info):
            self.flow_names.append(fl.get("name", f"fl_{fl_id}"))
            # Resolve path
            path = fl["path"]

            arrival_curves = list()
            bursts = fl["arrival_curve"]["bursts"]
            rates = fl["arrival_curve"]["rates"]
            for i in range(len(rates)):
                tb_curve = TokenBucket(bursts[i], rates[i])
                arrival_curves.append(tb_curve)

            # append flow
            self.flows.append(Flow(arrival_curves, path))

            # multicast flow
            if flow_is_multicast(fl):
                for mpath in fl["multicast"]:
                    path_name = mpath["name"]
                    path = mpath["path"]
                    self.flow_names.append(fl.get("name", f"fl_{fl_id}"))
                    self.flows.append(Flow(arrival_curves, path))

        ## Create a network for analysis
        self.network = Network(self.servers, self.flows)

    def analyze(
        self,
        method: str = "PLP",
        lp_file: str = "fifo.lp",
        use_tfa: bool = True,
        use_sfa: bool = True,
        output_shaping: bool = True,
    ) -> None:
        """
        Analyse the stored network

        method: Allow methods are "TFA", "SFA", "PLP"
        lp_file: LP solver file directory
        use_tfa: use TFA result to improve PLP result, relevant only when using PLP or PLP++
        use_sfa: use SFA result to improve PLP result, relevant only when using PLP or PLP++
        """
        # Build network for analysis
        if self.network is None:
            self.build_network(output_shaping)

        # Analyse result
        if method.upper() == "PLP":
            return self.analyze_fifo(lp_file, True, use_tfa, use_sfa)
        if method.upper() == "ELP":
            return self.analyze_fifo(lp_file, False, use_tfa, use_sfa)
        if method.upper() == "TFA":
            return self.analyze_tfa(lp_file)
        if method.upper() == "SFA":
            return self.analyze_sfa(lp_file)

    def analyze_fifo(
        self,
        lp_file: str = "fifo.lp",
        polynomial: bool = True,
        use_tfa: bool = True,
        use_sfa: bool = True,
    ) -> tuple:
        """
        Analyse using PLP with a pre-built network
        """
        if self.network is None:
            raise RuntimeError("An analysis called before a network is built")

        plp = FifoLP(
            self.network,
            polynomial=polynomial,
            tfa=use_tfa,
            sfa=use_sfa,
            filename=lp_file,
        )
        delay_per_flow = plp.all_delays
        flow_names = list()
        flow_delays = list()
        index = 0
        for fl in self.flows_info:
            if not flow_is_multicast(fl):
                num_paths = 1
                flow_names.append(self.flow_names[index])
                flow_delays.append(delay_per_flow[index])
            else:
                num_paths = 1 + len(fl["multicast"])
                argmax = max(range(index, index + num_paths), key=lambda x : delay_per_flow[x])  # hacky argmax
                flow_names.append(self.flow_names[argmax])
                flow_delays.append(delay_per_flow[argmax])
            index += num_paths

        self.flow_names = flow_names

        return flow_delays, None

    def analyze_tfa(self, lp_file: str = "fifo.lp") -> tuple:
        """
        Analyse using TFA with a pre-built network
        """
        if self.network is None:
            raise RuntimeError("An analysis called before a network is built")

        tfa = TfaLP(self.network, filename=lp_file)
        delay_per_flow = tfa.all_delays
        delay_per_server = tfa.delay_servers

        flow_names = list()
        flow_delays = list()
        index = 0
        for fl in self.flows_info:
            if not flow_is_multicast(fl):
                num_paths = 1
                flow_names.append(self.flow_names[index])
                flow_delays.append(delay_per_flow[index])
            else:
                num_paths = 1 + len(fl["multicast"])
                argmax = max(range(index, index + num_paths), key=lambda x : delay_per_flow[x])  # hacky argmax
                flow_names.append(self.flow_names[argmax])
                flow_delays.append(delay_per_flow[argmax])
            index += num_paths

        self.flow_names = flow_names

        for sid in self.server_no_flow:
            delay_per_server[sid] = 0.0

        return flow_delays, delay_per_server

    def analyze_sfa(self, lp_file: str = "fifo.lp") -> tuple:
        """
        Analyse using SFA with a pre-built network
        """
        if self.network is None:
            raise RuntimeError("An analysis called before a network is built")

        sfa = SfaLP(self.network, filename=lp_file)
        delay_per_flow = sfa.all_delays

        flow_names = list()
        flow_delays = list()
        index = 0
        for fl in self.flows_info:
            if not flow_is_multicast(fl):
                num_paths = 1
                flow_names.append(self.flow_names[index])
                flow_delays.append(delay_per_flow[index])
            else:
                num_paths = 1 + len(fl["multicast"])
                argmax = max(range(index, index + num_paths), key=lambda x : delay_per_flow[x])  # hacky argmax
                flow_names.append(self.flow_names[argmax])
                flow_delays.append(delay_per_flow[argmax])
            index += num_paths

        self.flow_names = flow_names

        return flow_delays, None

    def __get_flows(self, server: int) -> list:
        """
        Given a server j, find the indices of flow Fl(j) that passes server j
        the answer is returned in a list
        """
        output = []
        for fl in self.flows_info:
            if server in fl["path"]:
                output.append(fl)

        return output
