
Analysis Report - "demo.json"
=============================

Table of Contents
=================

* [General Information](#general-information)
	* [Topology of network](#topology-of-network)
	* [Performance](#performance)
* [Flow End-to-end Delays](#flow-end-to-end-delays)
	* [End-to-end delay bound using TFA (unit = milliseconds)](#end-to-end-delay-bound-using-tfa-unit--milliseconds)
	* [End-to-end delay bound using PLP with shaper (unit = milliseconds)](#end-to-end-delay-bound-using-plp-with-shaper-unit--milliseconds)
* [Server Delay/Backlogs](#server-delaybacklogs)
	* [Delay bound using TFA](#delay-bound-using-tfa)
	* [Delay bound using PLP with shaper](#delay-bound-using-plp-with-shaper)
	* [Backlog bound using TFA](#backlog-bound-using-tfa)
	* [Backlog bound using PLP with shaper](#backlog-bound-using-plp-with-shaper)
* [Per Flow Delays](#per-flow-delays)
	* [Flow "fl_0_p0"](#flow-fl_0_p0)
	* [Flow "fl_1_p0"](#flow-fl_1_p0)


The is a automatically generated report with ...

# General Information


This report contains 5 analysis over network **"demo.json"**.
There are **9** servers and **2** flows in the system.
## Topology of network
  
![Network graph][topo]
## Performance
  
Unit in milliseconds
|method name|DNC|Linear|xTFA|PLP|
| :---: | :---: | :---: | :---: | :---: |
|TFA|25.000|22.943|16.486|22.729|
|PLP with shaper|N/A|N/A|N/A|79.310|

# Flow End-to-end Delays

## End-to-end delay bound using TFA (unit = milliseconds)

|Flow name|DNC|Linear|xTFA|PLP|
| :---: | :---: | :---: | :---: | :---: |
|fl_0_p0|71.479|71.828|71.828|71.828|
|fl_1_p0|59.600|59.848|59.848|59.848|

## End-to-end delay bound using PLP with shaper (unit = milliseconds)

|Flow name|PLP|
| :---: | :---: |
|fl_0_p0|62.210|
|fl_1_p0|52.120|

# Server Delay/Backlogs

## Delay bound using TFA
  
Unit in millisecond
|server name|DNC|Linear|xTFA|PLP|
| :---: | :---: | :---: | :---: | :---: |
|sw_0|N/A|0.000|0.000|0.000|
|sw_1-0|11.000|11.000|11.000|11.000|
|sw_2-0|11.000|11.000|11.000|11.000|
|sw_3-0|11.100|11.110|11.110|11.110|
|sw_4-0|12.300|12.331|12.331|12.331|
|sw_5-0|12.500|12.578|12.578|12.578|
|sw_6-0|12.700|12.829|12.829|12.829|
|sw_7-0|11.439|11.487|11.487|11.487|
|sw_8-0|11.539|11.602|11.602|11.602|
|Total|93.579|93.938|93.938|93.938|

## Delay bound using PLP with shaper
  
Unit in millisecond
|server name|PLP|
| :---: | :---: |
|sw_0|N/A|
|sw_1-0|N/A|
|sw_2-0|N/A|
|sw_3-0|N/A|
|sw_4-0|N/A|
|sw_5-0|N/A|
|sw_6-0|N/A|
|sw_7-0|N/A|
|sw_8-0|N/A|
|Total|N/A|

## Backlog bound using TFA
  
Unit in kilobit
|server name|DNC|Linear|xTFA|PLP|
| :---: | :---: | :---: | :---: | :---: |
|sw_0|N/A|N/A|N/A|N/A|
|sw_1-0|11.000|N/A|N/A|N/A|
|sw_2-0|11.000|N/A|N/A|N/A|
|sw_3-0|12.000|N/A|N/A|N/A|
|sw_4-0|25.000|N/A|N/A|N/A|
|sw_5-0|27.000|N/A|N/A|N/A|
|sw_6-0|29.000|N/A|N/A|N/A|
|sw_7-0|15.393|N/A|N/A|N/A|
|sw_8-0|16.393|N/A|N/A|N/A|
|Max|29.000|N/A|N/A|N/A|

## Backlog bound using PLP with shaper
  
Unit in kilobit
|server name|PLP|
| :---: | :---: |
|sw_0|N/A|
|sw_1-0|N/A|
|sw_2-0|N/A|
|sw_3-0|N/A|
|sw_4-0|N/A|
|sw_5-0|N/A|
|sw_6-0|N/A|
|sw_7-0|N/A|
|sw_8-0|N/A|
|Max|N/A|

# Per Flow Delays

## Flow "fl_0_p0"
  
The name in the table is written according to the path
### Cumulative delay using TFA
  
Unit in milliseconds
|server name|DNC|Linear|xTFA|PLP|
| :---: | :---: | :---: | :---: | :---: |
|sw_2-0|11.000|11.000|11.000|11.000|
|sw_4-0|23.300|23.331|23.331|23.331|
|sw_5-0|35.800|35.909|35.909|35.909|
|sw_6-0|48.500|48.738|48.738|48.738|
|sw_7-0|59.939|60.225|60.225|60.226|
|sw_8-0|71.479|71.828|71.828|71.828|

### Cumulative delay using PLP with shaper
  
Unit in milliseconds
|server name|PLP|
| :---: | :---: |
|sw_2-0|N/A|
|sw_4-0|N/A|
|sw_5-0|N/A|
|sw_6-0|N/A|
|sw_7-0|N/A|
|sw_8-0|N/A|

## Flow "fl_1_p0"
  
The name in the table is written according to the path
### Cumulative delay using TFA
  
Unit in milliseconds
|server name|DNC|Linear|xTFA|PLP|
| :---: | :---: | :---: | :---: | :---: |
|sw_1-0|11.000|11.000|11.000|11.000|
|sw_3-0|22.100|22.110|22.110|22.110|
|sw_4-0|34.400|34.441|34.441|34.441|
|sw_5-0|46.900|47.019|47.019|47.019|
|sw_6-0|59.600|59.848|59.848|59.848|

### Cumulative delay using PLP with shaper
  
Unit in milliseconds
|server name|PLP|
| :---: | :---: |
|sw_1-0|N/A|
|sw_3-0|N/A|
|sw_4-0|N/A|
|sw_5-0|N/A|
|sw_6-0|N/A|



[topo]: /Users/chunzuo/Documents/tony/courses/ica2_project/src/example/demo.json_topo.png
