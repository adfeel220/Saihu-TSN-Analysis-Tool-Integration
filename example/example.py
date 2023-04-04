# This is an example execution of saihu using the network generation tool

from saihu.interface import TSN_Analyzer
from saihu.netscript.net_gen import *

if __name__ == "__main__":
    num_flows = 5
    connections = {
        "S1": ["S2", "S3", "S8"],
        "S2": ["S4", "S5", "S8"],
        "S3": ["S4", "S5", "S7", "S8"],
        "S4": ["S6", "S7", "S8"],
        "S5": ["S6", "S7"],
        "S6": ["S7", "S8"],
        "S7": ["S8"],
        "S8": [],
    }
    generate_fix_topology_network(
        num_flows=num_flows,
        connections=connections,
        burst=("10B", "1024B"),
        arrival_rate=("200bps", "20kbps"),
        max_packet_length="128B",
        latency=("2us", "200ms"),
        service_rate=("1Mbps", "50Mbps"),
        capacity="256Mbps",
        save_dir=f"industry{num_flows}.json",
        network_attrib={"name": f"industry{num_flows}"},
        link_prob=0.8,
    )
    analyzer = TSN_Analyzer(f"industry{num_flows}.json", temp_path="./temp/")
    analyzer.analyze_xtfa()
    analyzer.analyze_panco(methods=["PLP", "ELP"])
    analyzer.analyze_dnc(methods=["SFA", "PMOO", "TMA"])
    analyzer.export(f"ind{num_flows}")
