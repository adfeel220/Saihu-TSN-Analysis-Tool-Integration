
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


The is a automatically generated report with `Saihu` [Github Link](https://github.com/adfeel220/TSN_Analysis_Tool_Integration)

# Network Analysis Result

## Per flow end-to-end delay bound
  
Unit in microsecond
|Flow name|Panco-PLP|DNC-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: |
|f0|80.050|100.004|100.125|99.324|
|f1|80.070|80.075|80.125|79.322|
|f2|50.070|50.004|50.125|49.324|

## Per server delay bound
  
Unit in microsecond
|server name|Panco-PLP|DNC-TFA|Panco-TFA|xTFA-TFA|
| :---: | :---: | :---: | :---: | :---: |
|s0-o0|N/A|50.000|50.000|50.000|
|s1-o0|N/A|50.004|50.125|49.324|
|s1-o1|N/A|30.075|30.125|29.322|
|Total|N/A|130.079|130.250|128.646|

## Execution Time
  
Unit in millisecond
|method\tool|DNC|Panco|xTFA|
| :---: | :---: | :---: | :---: |
|PLP|N/A|176.434|N/A|
|TFA|19.000|33.201|65.094|

# Network Information


This report contains 4 analysis over network **"demo"**.
There are **3** servers and **3** flows in the system.
## Network Topology
  
![Network graph][topo]
## Flow paths

**f0**: `s0-o0` -> `s1-o0`
**f1**: `s0-o0` -> `s1-o1`
**f2**: `s1-o0`

## Network Link Utilization
  
Utilization for each link:
- `s0-o0`: 0.005
- `s1-o0`: 0.005
- `s1-o1`: 0.0025
  
**Maximum Link Utilization** = 0.005


[topo]: ./demo_topo.png
