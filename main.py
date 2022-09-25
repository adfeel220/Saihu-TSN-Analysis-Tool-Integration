from tsn_analyzer import tsn_analyzer


# Initialize an analyzer
analyzer = tsn_analyzer("networks/network_def.json")

# Solve ordinary TFA problem (without shapers)
optimal_delay = analyzer.solve_tfa()
print(f"TFA\tdelays = {optimal_delay} ; \tTotal delay = {sum(optimal_delay)}")

# Solve TFA++ problem (with shapers)
optimal_delay_shapers = analyzer.solve_tfa_pp()
print(f"TFA++\tdelays = {optimal_delay_shapers} ; \tTotal delay = {sum(optimal_delay_shapers)}")