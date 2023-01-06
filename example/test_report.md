
Analysis Report - "demo"
========================

Table of Contents
=================

* [Network Analysis Result](#network-analysis-result)
	* [Per flow end-to-end delay bound](#per-flow-end-to-end-delay-bound)
	* [Per server delay bound](#per-server-delay-bound)
	* [Execution Time](#execution-time)
* [Network Information](#network-information)
	* [Network Topology](#network-topology)
	* [Flow paths](#flow-paths)
	* [Network Link Utilization](#network-link-utilization)


The is a automatically generated report with project `TSN Analysis Tools Intergration`

# Network Analysis Result

## Per flow end-to-end delay bound
  
Unit in s
|Flow name|Panco-PLP|DNC-TFA|Linear-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: | :---: |
|f0|2.812|3.156|3.292|3.292|3.236|
|f1|2.958|2.906|3.000|3.000|2.917|
|f2|1.743|1.656|1.792|1.792|1.736|

## Per server delay bound
  
Unit in s
|server name|Panco-PLP|DNC-TFA|Linear-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: | :---: |
|s0-o0|N/A|1.500|1.500|1.500|1.500|
|s1-o0|N/A|1.656|1.792|1.792|1.736|
|s1-o1|N/A|1.406|1.500|1.500|1.417|
|Total|N/A|4.562|4.792|4.792|4.653|

## Execution Time
  
Unit in milliseconds
|method\tool|DNC|Linear|Panco|xTFA|
| :---: | :---: | :---: | :---: | :---: |
|PLP|N/A|N/A|162.277|N/A|
|TFA|15.000|38.296|28.989|6.404|

# Network Information


This report contains 5 analysis over network **"demo"**.
There are **3** servers and **3** flows in the system.
## Network Topology
  
![Network graph][topo]
## Flow paths

**f0**: `s0-o0` -> `s1-o0`
**f1**: `s0-o0` -> `s1-o1`
**f2**: `s1-o0`

## Network Link Utilization
  
Utilization for each link:
- `s0-o0`: 0.5
- `s1-o0`: 0.5
- `s1-o1`: 0.25
  
**Maximum Link Utilization** = 0.5


[topo]: ./demo_topo.png
