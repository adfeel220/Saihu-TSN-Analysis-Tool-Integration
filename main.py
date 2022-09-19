from tsn_analyzer import tsn_analyzer
import numpy as np


# Global arrival/service parameters
BURST    = 1 # arrival burst
ARR_RATE = 1 # arrival rate
LATENCY  = 1 # service latency
SER_RATE = 4 # service rate
# Network
ADJ_MAT = np.array([[0, 1], [0, 0]])    # network topology, from server 0 -> server 1
FLOWS = [[0,1], [0], [1]]                # data flows
NUM_FLOW = len(FLOWS)
NUM_SERVER = ADJ_MAT.shape[0]

# shaper definition
PKT_LENGTH = 0
CAPACITY = 4


# Initialize an analyzer
analyzer = tsn_analyzer()

analyzer.set_topology(ADJ_MAT)
analyzer.add_flows(FLOWS, [BURST]*NUM_FLOW, [ARR_RATE]*NUM_FLOW)
analyzer.set_service_all([SER_RATE]*NUM_SERVER, [LATENCY]*NUM_SERVER)

optimal_delay = analyzer.solve_tfa()
print(f"TFA delays = {optimal_delay} ; Total delay = {sum(optimal_delay)}")

analyzer.set_shaper_all([PKT_LENGTH]*NUM_SERVER, [CAPACITY]*NUM_SERVER)
optimal_delay_shapers = analyzer.solve_tfa_pp()
print(f"TFA++ delays = {optimal_delay_shapers} ; Total delay = {sum(optimal_delay_shapers)}")