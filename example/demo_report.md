
Analysis Report - "demo.json"
=============================

Table of Contents
=================

* [General Information](#general-information)
	* [Topology of network](#topology-of-network)
	* [Performance](#performance)
* [Server Delay/Backlogs](#server-delaybacklogs)
	* [Delay bound using TFA (unit = millisecond)](#delay-bound-using-tfa-unit--millisecond)
	* [Delay bound using TFA++ (unit = millisecond)](#delay-bound-using-tfa-unit--millisecond)
	* [Backlog bound using TFA (unit = kilobit)](#backlog-bound-using-tfa-unit--kilobit)
	* [Backlog bound using TFA++ (unit = kilobit)](#backlog-bound-using-tfa-unit--kilobit)
* [Per Flow Delays](#per-flow-delays)
	* [Flow "fl_0_p0"](#flow-fl_0_p0)
	* [Flow "fl_1_p0"](#flow-fl_1_p0)


The is a automatically generated report with ...

# General Information


This report contains 6 analysis over network **"demo.json"**.
There are **9** servers and **2** flows in the system.
## Topology of network
  
![Network graph][topo]
## Performance
  
Unit in milliseconds
|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|TFA|49.000|62.401|40.747|
|TFA++|27.000|66.704|39.157|

# Server Delay/Backlogs

## Delay bound using TFA (unit = millisecond)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_0|N/A|0.000|0.000|
|sw_1-0|11.000|11.000|11.000|
|sw_2-0|11.000|11.000|11.000|
|sw_3-0|11.100|11.110|11.110|
|sw_4-0|12.300|12.331|12.331|
|sw_5-0|12.500|12.578|12.578|
|sw_6-0|12.700|12.829|12.829|
|sw_7-0|11.439|11.487|11.487|
|sw_8-0|11.539|11.602|11.602|
|Total|93.579|93.938|93.938|

## Delay bound using TFA++ (unit = millisecond)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_0|N/A|0.000|0.000|
|sw_1-0|11.000|11.000|11.000|
|sw_2-0|11.000|11.000|11.000|
|sw_3-0|11.100|11.000|11.000|
|sw_4-0|12.300|12.210|12.210|
|sw_5-0|12.500|12.321|12.321|
|sw_6-0|12.700|12.544|12.544|
|sw_7-0|11.439|11.334|11.334|
|sw_8-0|11.539|11.436|11.436|
|Total|93.579|92.846|92.846|

## Backlog bound using TFA (unit = kilobit)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_0|N/A|N/A|N/A|
|sw_1-0|11.000|N/A|N/A|
|sw_2-0|11.000|N/A|N/A|
|sw_3-0|12.000|N/A|N/A|
|sw_4-0|25.000|N/A|N/A|
|sw_5-0|27.000|N/A|N/A|
|sw_6-0|29.000|N/A|N/A|
|sw_7-0|15.393|N/A|N/A|
|sw_8-0|16.393|N/A|N/A|
|Max|29.000|N/A|N/A|

## Backlog bound using TFA++ (unit = kilobit)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_0|N/A|N/A|N/A|
|sw_1-0|11.000|N/A|N/A|
|sw_2-0|11.000|N/A|N/A|
|sw_3-0|12.000|N/A|N/A|
|sw_4-0|25.000|N/A|N/A|
|sw_5-0|27.000|N/A|N/A|
|sw_6-0|29.000|N/A|N/A|
|sw_7-0|15.393|N/A|N/A|
|sw_8-0|16.393|N/A|N/A|
|Max|29.000|N/A|N/A|

# Per Flow Delays

## Flow "fl_0_p0"
  
The name in the table is written according to the path
### Cumulative delay using TFA (unit = millisecond)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_2-0|11.000|11.000|11.000|
|sw_4-0|23.300|23.331|23.331|
|sw_5-0|35.800|35.909|35.909|
|sw_6-0|48.500|48.738|48.738|
|sw_7-0|59.939|60.225|60.225|
|sw_8-0|71.479|71.828|71.828|

### Cumulative delay using TFA++ (unit = millisecond)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_2-0|11.000|11.000|11.000|
|sw_4-0|23.300|23.210|23.210|
|sw_5-0|35.800|35.532|35.532|
|sw_6-0|48.500|48.075|48.075|
|sw_7-0|59.939|59.409|59.409|
|sw_8-0|71.479|70.846|70.846|

## Flow "fl_1_p0"
  
The name in the table is written according to the path
### Cumulative delay using TFA (unit = millisecond)

|name|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_1-0|11.000|11.000|11.000|
|sw_3-0|22.100|22.110|22.110|
|sw_4-0|34.400|34.441|34.441|
|sw_5-0|46.900|47.019|47.019|
|sw_6-0|59.600|59.848|59.848|

### Cumulative delay using TFA++ 
(unit = millisecond)

|server|DNC|Linear|xTFA|
| :---: | :---: | :---: | :---: |
|sw_1-0|11.000|11.000|11.000|
|sw_3-0|22.100|22.000|22.000|
|sw_4-0|34.400|34.210|34.210|
|sw_5-0|46.900|46.532|46.532|
|sw_6-0|59.600|59.075|59.075|



[topo]: /Users/chunzuo/Documents/tony/courses/ica2_project/src/example/demo.json_topo.png
