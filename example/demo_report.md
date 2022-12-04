
Analysis Report - "demo"
========================

Table of Contents
=================

* [General Information](#general-information)
	* [Network Utility (Load)](#network-utility-load)
	* [Topology of network](#topology-of-network)
	* [Execution Time](#execution-time)
* [Flow End-to-end Delays](#flow-end-to-end-delays)
	* [End-to-End delay bound](#end-to-end-delay-bound)
	* [Flow paths](#flow-paths)
* [Server Delay/Backlogs](#server-delaybacklogs)
	* [Delay bound](#delay-bound)
* [Per Flow Delays](#per-flow-delays)
	* [Flow "fl-0"](#flow-fl-0)
	* [Flow "fl-1"](#flow-fl-1)


The is a automatically generated report with project `TSN Analysis Tools Intergration`

# General Information


This report contains 4 analysis over network **"demo"**.
There are **9** servers and **2** flows in the system.
## Network Utility (Load)
  
Utility for each server:
- `sw-0`: 0.0
- `sw-1`: 0.01
- `sw-2`: 0.01
- `sw-3`: 0.01
- `sw-4`: 0.02
- `sw-5`: 0.02
- `sw-6`: 0.02
- `sw-7`: 0.01
- `sw-8`: 0.01
  
**Overall Network Utility** = 0.02  
(Overall network utility is computed by the maximum of utilities)
## Topology of network
  
![Network graph][topo]
## Execution Time
  
Unit in milliseconds
|method name|DNC|Linear|Panco|xTFA|
| :---: | :---: | :---: | :---: | :---: |
|TFA|43.000|29.969|28.532|18.453|

# Flow End-to-end Delays

## End-to-End delay bound
  
Unit in milliseconds
|Flow name|DNC-TFA|Linear-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: |
|fl-0|71.479|70.846|70.846|70.846|
|fl-1|59.600|59.075|59.075|59.075|

## Flow paths

**fl-0**: _sw-2_ -> _sw-4_ -> _sw-5_ -> _sw-6_ -> _sw-7_ -> _sw-8_
**fl-1**: _sw-1_ -> _sw-3_ -> _sw-4_ -> _sw-5_ -> _sw-6_

# Server Delay/Backlogs

## Delay bound
  
Unit in millisecond
|server name|DNC-TFA|Linear-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: |
|sw-0|N/A|0.000|0.000|0.000|
|sw-1|11.000|11.000|11.000|11.000|
|sw-2|11.000|11.000|11.000|11.000|
|sw-3|11.100|11.000|11.000|11.000|
|sw-4|12.300|12.210|12.210|12.210|
|sw-5|12.500|12.321|12.321|12.321|
|sw-6|12.700|12.544|12.544|12.544|
|sw-7|11.439|11.334|11.334|11.334|
|sw-8|11.539|11.436|11.436|11.436|
|Total|93.579|92.846|92.846|92.846|

# Per Flow Delays

## Flow "fl-0"
  
The name in the table is written according to the path
### Cumulative delay according to path
  
Unit in milliseconds
|server name|DNC-TFA|Linear-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: |
|sw-2|11.000|11.000|11.000|11.000|
|sw-4|23.300|23.210|23.210|23.210|
|sw-5|35.800|35.532|35.532|35.532|
|sw-6|48.500|48.075|48.075|48.075|
|sw-7|59.939|59.409|59.409|59.409|
|sw-8|71.479|70.846|70.846|70.846|

## Flow "fl-1"
  
The name in the table is written according to the path
### Cumulative delay according to path
  
Unit in milliseconds
|server name|DNC-TFA|Linear-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: |
|sw-1|11.000|11.000|11.000|11.000|
|sw-3|22.100|22.000|22.000|22.000|
|sw-4|34.400|34.210|34.210|34.210|
|sw-5|46.900|46.532|46.532|46.532|
|sw-6|59.600|59.075|59.075|59.075|



[topo]: /Users/chunzuo/Documents/tony/courses/ica2_project/src/example/demo_topo.png
