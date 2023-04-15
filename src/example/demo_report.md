
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


The is a automatically generated report with [Saihu](https://github.com/adfeel220/Saihu-TSN-Analysis-Tool-Integration)

# Network Analysis Result

## Per flow end-to-end delay bound
  
Unit in microsecond
|Flow name|Panco-ELP|DNC-LUDB|Panco-PLP|DNC-PMOO|DNC-SFA|xTFA-TFA|Minimum (best)|
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
|f0|80.050|80.050|80.050|80.201|80.050|99.324|80.050|
|f1|80.080|60.050|79.270|60.125|60.050|79.322|60.050|
|f2|49.280|50.004|49.280|50.201|50.125|49.324|49.280|

## Per server delay bound
  
Unit in microsecond
|server name|Panco-ELP|DNC-LUDB|Panco-PLP|DNC-PMOO|DNC-SFA|xTFA-TFA|Minimum (best)|
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
|s0-o0|N/A|N/A|N/A|N/A|N/A|50.000|50.000|
|s1-o0|N/A|N/A|N/A|N/A|N/A|49.324|49.324|
|s1-o1|N/A|N/A|N/A|N/A|N/A|29.322|29.322|
|Total|N/A|0.000|N/A|0.000|0.000|128.646|128.646|

## Execution Time
  
Unit in millisecond
|method\tool|DNC|Panco|xTFA|
| :---: | :---: | :---: | :---: |
|ELP|N/A|130.085|N/A|
|LUDB|189.000|N/A|N/A|
|PLP|N/A|142.683|N/A|
|PMOO|8.000|N/A|N/A|
|SFA|11.000|N/A|N/A|
|TFA|N/A|N/A|6.002|

# Network Information


This report contains 6 analysis over network **"demo"**.
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
