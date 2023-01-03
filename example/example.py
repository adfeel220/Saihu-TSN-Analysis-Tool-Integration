import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))

from interface import TSN_Analyzer
from netscript.net_gen import *

if __name__ == "__main__":
    analyzer = TSN_Analyzer("demo_net.json", temp_path="./temp/")
    analyzer.analyze_linear(methods=["TFA"])
    analyzer.analyze_panco(methods=["TFA", "PLP"])
    analyzer.analyze_dnc(methods=["TFA", "SFA"])
    analyzer.export("test")
    # generate_mesh(size=7,
    #               burst=1,
    #               arr_rate=1,
    #               pkt_leng=0,
    #               latency=1,
    #               ser_rate=8,
    #               capacity=8,
    #               dir="mesh.json")
    # analyzer.set_shaping_mode("ON")
    # analyzer.analyze_panco("mesh.json", methods=["ELP", "PLP"])
    # analyzer.analyze_xtfa("mesh.json", methods=["TFA"])
    # analyzer.write_result("mesh-with-shape.md")
