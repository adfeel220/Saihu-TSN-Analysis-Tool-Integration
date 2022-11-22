import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))

from interface import TSN_Analyzer

if __name__ == "__main__":
    analyzer = TSN_Analyzer("./demo.json", temp_path="./temp/")
    analyzer.analyze_all(methods=["TFA", "PLP++"])
    analyzer.write_result("./demo_report.md")