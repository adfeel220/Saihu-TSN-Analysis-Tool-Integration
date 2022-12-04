TSN Analysis Tools Intergration
=======================
Author: Chun-Tso Tsai
Advisors: Seyed Mohammadhossein Tabatabaee, Stéphan Plassart, Jean-Yves Le Boudec
Date: Dec 4, 2022
Institute: Computer Communications and Applications Laboratory 2 (LCA2), École Polytechnique Fédérale de Lausane (EPFL)

Table of Contents
========================
* [Introduction](#introduction)
    * [Credit](#credit)
* [Project Structure](#project-structure)
    * [File Description](#file-description)
    * [Credits to Files](#credits-to-files)
* [Installation](#installation)
    * [Dependency](#dependency)
* [How to Use This Tool](#how-to-use)
    * [Network Description File](#network-description-file)
        * [Physical Network](#physical-network)
        * [Output-Port Network](#output-port-network)
    * [Analysis Tools](#analysis-tools)
    * [Network Generation](#network-generation)
* [Example](#example)
    * [Specific Tool](#specific-tool)
    * [Selecting Shaper](#selecting-shaper)
    * [Specific Networks](#specific-networks)
    * [Generate Network and Analysis](#generate-network-and-analysis)
* [Extend this Project](#extend-this-project)
    * [Files](#files)
    * [Standard Analysis Result](#standard-analysis-result)
* [Contact](#contact)


# Introduction
**Time-Sensitive Network (TSN)** analysis focuses on giving deterministic delay or backlog guarantees. This project integrates 4 different TSN analysis tools, including `Linear TFA Solver`, [NetCal/DNC](https://github.com/NetCal/DNC), [xTFA](https://gitlab.isae-supaero.fr/l.thomas/xtfa), and [panco](https://github.com/Huawei-Paris-Research-Center/panco). The users can use a unified interface to compute network delay bounds obtained by different tools, and write the results into a formated report. 

## Credit
Here are the authors that implemented the individual tools used in this project.
- `Linear TFA Solver`: I implemented it myself following the algorithm used in [Trade-off between accuracy and tractability of Network Calculus in FIFO networks](https://doi.org/10.1016/j.peva.2021.102250).
- `xTFA`: This tool is implemented by [Ludovic Thomas](https://people.epfl.ch/ludovic.thomas/?lang=en).
- `NetCal/DNC`: This tool is implemented by the NetCal team. You can visit [their repository](https://github.com/NetCal/DNC) and here are the academic references:
    - Arbitrary Multiplexing:
    ```
    @inproceedings{DiscoDNCv2,
        author    = {Steffen Bondorf and Jens B. Schmitt},
        title     = {The {DiscoDNC} v2 -- A Comprehensive Tool for Deterministic Network Calculus},
        booktitle = {Proc. of the International Conference on Performance Evaluation Methodologies and Tools},
        series    = {ValueTools '14},
        pages     = {44--49},
        month     = {December},
        year      = 2014,
        url       = {https://dl.acm.org/citation.cfm?id=2747659}
    }
    ```
    - FIFO Multiplexing:
    ```
    @inproceedings{LUDBFF,
        author    = {Alexander Scheffler and Steffen Bondorf},
        title     = {Network Calculus for Bounding Delays in Feedforward Networks of {FIFO} Queueing Systems},
        booktitle = {Proc. of the 18th International Conference on Quantitative Evaluation of Systems},
        series    = {QEST '21},
        pages     = {149--167},
        month     = {August},
        year      = 2021,
        url       = {https://link.springer.com/chapter/10.1007/978-3-030-85172-9_8}
    }
    ```
- `panco`: The tool is implemented by [Anne Bouillard](https://ieeexplore.ieee.org/author/38526153500) at Huawei Paris Research Center. Here is the [original repository](https://github.com/Huawei-Paris-Research-Center/panco). The following is the academic reference:
    ```
    @article{BOUILLARD2022102250,
        title    = {Trade-off between accuracy and tractability of Network Calculus in FIFO networks},
        journal  = {Performance Evaluation},
        volume   = {153},
        pages    = {102250},
        year     = {2022},
        issn     = {0166-5316},
        doi      = {https://doi.org/10.1016/j.peva.2021.102250},
        url      = {https://www.sciencedirect.com/science/article/pii/S0166531621000675},
        author   = {Anne Bouillard},
        keywords = {Network Calculus, FIFO systems, Linear programming},
        abstract = {Computing accurate deterministic performance bounds is a strong need for communication technologies having stringent requirements on latency and reliability. Within new scheduling protocols such as TSN, the FIFO policy remains at work inside each class of communication. In this paper, we focus on computing deterministic performance bounds in FIFO networks in the Network Calculus framework. We propose a new algorithm based on linear programming that presents a trade-off between accuracy and tractability. This algorithm is first presented for tree networks. Next, we generalize our approach and present a linear program for computing performance bounds for arbitrary topologies, including cyclic dependencies. Finally, we provide numerical results, both of toy examples and realistic topologies, to assess the interest of our approach.}
    }
    ```


# Project Structure
```
.
└- interface.py
└- result.py
└- environment.yml
└- README.md
└- example
│  └- example.py
│  └- demo.json
│  └- demo.xml
│  └- demo_report.md
│  └- temp
│     └- ... (execution artifacts)
│
└- src
   └- javapy
   │  └- dnc_analysis.jar
   │  └- dnc_exe.py
   │  └- NetworkAnalysis
   │     └- NetArgParser.java
   │     └- NetworkScriptHandler.java
   │     └- NetworkAnalysis.java
   │
   └- Linear_TFA
   │  └- Linear_TFA.py
   │  └- ...
   │
   └- xTFA
   │  └- ...
   │
   └- panco
   │  └- lp_solve
   │  └- lpSolvePath.py
   │  └- panco_analyzer.py
   │  └- ...
   └- netscript
      └- netdef.py
      └- netscript.py
      └- net_gen.py
      └- unit_util.py
```
## File description
- `interface.py`: The general interface to use the analysis tools. Generally user can only use this one.
- `result.py`: The formated result class from all tools.
- `example/`:
    - `example.py`: Example on how to use it.
    - `demo.json`: A demo network definition file in output-port json format.
    - `demo.xml`: A demo network definition file in physical network XML format.
    - `demo_report.md`: A example of report.
- `src/`:
    - `javapy/`:
        - `dnc_analysis.jar`: The custom `.jar` file that can execute DNC analysis.
        - `dnc_exe.py`: The `Python` implementation on executing `dnc_analysis.jar` and capture the results.
        - `NetworkAnalysis`: A folder that represents a java package of my implementation on the interaction between my interface and DNC tool.
            - `NetArgParser.java`: Parsing the input arguments.
            - `NetworkScriptHandler.java`: Construct a DNC `ServerGraph` object for further analysis based on the input network description file.
            - `NetworkAnalysis`: Perform analysis given the tools specified in input arguments and print them in `.json` format.
    - `Linear_TFA/Linear_TFA.py`: The implementation of Linear TFA solver.
    - `xTFA/`: The original `xTFA` module from [xTFA](https://gitlab.isae-supaero.fr/l.thomas/xtfa)
    - `panco/`:
        - `...`: The original `panco` module from [panco](https://github.com/Huawei-Paris-Research-Center/panco)
        - `lp_solve`: The `lp_solve` executable downloaded and installed from [lpsolve](https://sourceforge.net/projects/lpsolve/)
        - `lpSolvePath.py`: You need to change `LPSOLVEPATH` in this file if you place your lpsolve executable at a different directory.
        - `panco_analyzer.py`: To load and build networks, and performing analysis using `panco` tools.
    - `netscript/`:
        - `netdef.py`: The `Python` representation of physical network in _WOPANet_ `.xml` format and output-port abstraction of `.json` format.
        - `netscript.py`: The sciprt handler to manipulate network definition files.
        - `net_gen.py`: Methods to automatically generate interleave/ring/mesh network with arbitrary number of homogeneous servers.
        - `unit_util.py`: Methods to do multiplier/unit parsing and manipulation.
- `README.md`: This `README`

## Credits to Files
- `NetCal/DNC`: The file `dnc_analysis.jar` is built based on the project [DNC](https://github.com/NetCal/DNC). I only implemented `NetworkAnalysis` package to allow analysing with `DNC` while using my network description file as input and my standard result format as output. More you can find more details about my input/output at [network description file](#network-description-file) and [standard result](#standard-analysis-result).
- `xTFA`: All files under the folder `xtfa` are implemented by [Ludovic Thomas](https://people.epfl.ch/ludovic.thomas/?lang=en) on this [repository](https://gitlab.isae-supaero.fr/l.thomas/xtfa).
- `panco`: Under the folder `panco`, I only implemented `panco_analyzer.py` to bridge my input/output format to panco tools. All files other than `panco_analyzer.py` and `lp_solve` are credited to [Anne Bouillard](https://ieeexplore.ieee.org/author/38526153500) with the complete project at [this repository](https://github.com/Huawei-Paris-Research-Center/panco)

# Installation
Please install the following requirements on your machine.
## Requirements
- `lpsolve`: Download and installed from [lpsolve](https://sourceforge.net/projects/lpsolve/). The `lp_solve` in the project is built on `macOS 12.6`, you may need to build a different version on your machine.
- `Java`: `JDK 16.0.2`
- `Python`: Create an environment using `environment.yml` or installing `numpy`, `networkx`, `matplotlib`, `pulp`, and `mdutils` with `Python>=3.8`.

# How to Use
You need to write your network in one of the network description format specified below. Then use the Python interface to do the analysis.
You may also generate a network by the built-in function specified in [Network Generation](#network-generation).
## Network Description File
The tool accepts 2 formats of network description file. Please find details below.
### Physical Network
A physical network is defined in `WOPANet` format as a `.xml` file. It contains only one `elements` with the following attributes:
- `network`: Has the following attributes
    - `name`: Name of the network
    - `technology`: Global specifications connected by _"+"_, where you can use
        1. `FIFO`: FIFO property
        2. `IS`: Input shaper
        3. `PK`: Packetizer
        4. `CEIL`: Fixed precision, can reduce computation time but slightly reduce precision.
        5. `MOH` and `TDMI`: Can improve delay bounds. For technical details please contact the author of `xTFA` [Ludovic Thomas](mailto:ludovic.thomas@epfl.ch).
    - Other attributes are optional, but used as a global parameter. If some parameters are not specified in each server/flow, the system uses the global parameter defined here instead.

    Example:
    ```
	<network name="example-network" technology="FIFO+IS+CEIL" overhead="0" maximum-packet-size="0"/>
    ```
- `station`/`switch`: The two names would not affect the analysis result, but for representing the physical network and readability. Can have the following attributes
    - `name`: Name of station/switch.
    - `service-latency`: The latency of the rate-latency curve. Can assign different time units, `s`/`ms`/`us`, etc.
    - `service-rate`: The service rate of the rate-latency curve. Can assign different rate units, `Mbps`... (But not `bps` alone)
    - `transmission-capacity`: The output capacity of station/switch. Can assign different rate units, `Mbps`... (But not `bps` alone)

    Example:
    ```
    <station service-latency="1s" transmission-capacity="200" service-rate="200" name="st0"/>
	<switch service-latency="1s" transmission-capacity="200" service-rate="200" name="sw0"/>
    ```
- `link`: Connection link between ports, has the following attributes
    - `name`: Name of link.
    - `from`: Which station/switch the link is connected from. Need to be name of station/switch.
    - `to`: Which station/switch the link is connected to. Need to be name of station/switch.
    - `fromPort`: The port number used for incoming station/switch.
    - `toPort`: The port number used for outgoing station/switch.

    Example:
    ```
	<link from="src" to="sw0" fromPort="0" toPort="0" name="src_sw_0"/>
    ```
    Note: Service curve can also be defined on links as defined on station/switches.
- `flow`: Flow of network, has attributes:
    - `name`: Name of flow
    - `arrival-curve`: Type of arrival curve, `leaky-bucket` for example. The curve can also be periodic but currently tools other than `xTFA` can not process it.
    - `lb-burst`: burst of leaky-bucket curve. Can assign different data units, `B` for Byte or `b` for bit, defulat is `B`.
    - `lb-rate`: arrival rate of leady-bucket curve. Can assign different rate units, `Mbps`... (But not `bps` alone)
    - `source`: The source of this flow, must be a station or switch.
    
    A `flow` element can have multiple paths, it is then treated as separated flows with the same arrival parameters.
    - `target`: Each target is a path, can assign a `name` to it. A list of nodes is written as its sub-element-tree. Each node is specified by a `path` entry with attribute `node` equals to a station/switch.

    Example:
    ```
    <flow name="f0" arrival-curve="leaky-bucket" lb-burst="1b" lb-rate="1" source="st-0">
        <target name="p1">
            <path node="sw0"/>
            <path node="sw1"/>
            <path node="sw2"/>
            <path node="sw3"/>
	    </target>
        <target name="p2">
            <path node="sw0"/>
            <path node="sw3"/>
            <path node="sw5"/>
            <path node="sw6"/>
        </target>
	</flow>
    ```

### Output-Port Network
An Output-port network is defined as a `.json` file. It contains only one `JSON Object` with the following attributes:
- `network`: (Optional) General network information, for example
    ```
    "network": {
        "name": "my network"
    }
    ```
- `adjacency_matrix`: the adjacency matrix to represent the network topology as a directed graph, for example
    ```
    "adjacency_matrix": [
        [0, 1, 0],
        [0, 0, 1],
        [0, 0, 0]
    ]
    ```
    The indices of servers are the order defined later in `servers`.
- `flows`: array of flows, each flow has the following attributes
    - `name`: (Optional) Name of flow, automatically assigned as `fl_x` if name is not defined, where `x` is the order appears in this flow array.
    - `path`: An array to represent path of flow, written as indices of servers defined in `servers`. 
    - `arrival_curve`: A multi-segment curve, which has 2 attributes `bursts` and `rates`. Both attributes are arrays and must have the same length. Burst and arrival rate wit hthe same index correspond to a token-bucket curve, and the final arrival curve is defined as minimum of all these curves. Burst unit in `bit` and rate unit in `bps`.
    - `packet_length`: An integer to represent the maximum packet length of the flow and would affect shaper. A server's shaper is a token-bucket curve with its burst defined as the maximum packet length along all flows pass through that server. Unit in `bit`.

    Example:
    ```
    "flows": [
        {
            "name": "flow-0",
            "path": [2,4,5,6,7,8],
            "arrival_curve": {
                "bursts": [0.01e6],
                "rates": [0.1e6]
            },
            "packet_length": 0
        },
        ...
    ]
    ```
- `servers`: an array of servers, each server has the following attributes
    - `name`: (Optional) Name of server. Default is `sw_x` where `x` is the server index.
    - `service_curve`: A multi-segment curve, which has 2 attributes `latencies` and `rates`. Both attributes must have the same length. Latency and service rate with the same index correspond to a rate-latency curve. The final service curve is the maximum of all these curves. Latency unit is in `second` and rate unit is in `bps`.
    - `capacity`: The output capacity of server, used as the rate of the token-bucket shaper. Unit in `bps`.

    Example:
    ```
    "servers": [
        {
            "name": "server-0",
            "service_curve": {
                "latencies": [1e-2],
                "rates": [10e6]
            },
            "capacity": 100e6
        },
        ...
    ]
    ```

## Analysis Tools
To use our general interface, you need to first import class `TSN_Analyzer` from the file `src/interface.py`.
```
from interface import TSN_Analyzer
```
Here is a list of all available methods
* [init](#init)
* [set_shaper_usage](#set_shaper_usage)
* [convert_netfile](#convert_netfile)
* [analyze_all](#analyze_all)
* [analyze_xtfa](#analyze_xtfa)
* [analyze_linear](#analyze_linear)
* [analyze_panco](#analyze_panco)
* [analyze_dnc](#analyze_dnc)
* [write_result](#write_result)
* [clear](#clear)

### Init
An analyzer can be initialized by
```
analyzer = TSN_Analyzer(netfile, jar_path, temp_path, use_shaper)
```
All arguments are optional, each of them represents
- `netfile`: The path to the network definition file, either a physical network or an output-port network.
- `jar_path`: The path to the DNC `.jar` file.
- `temp_path`: The path to the tempary directory to put the execution artifacts.
- `use_shaper`: A string to select shaper mode, can be _AUTO_, _ON_, or _OFF_. Default is _AUTO_, which means to use shaper if possible.

### set_shaper_usage
```
analyzer.set_shaper_usage(mode)
```
Set the shaper usage of the analyzer by a string of either _AUTO_, _ON_, or _OFF_. _AUTO_ means using shaper if possible. _ON_ and _OFF_ are forcing analyzer to use shaper or not, and don't compute result if not possible.

### convert_netfile
```
outputport_net_file, physical_net_file = analyzer.convert_netfile(in_netfile, out_netfile, target)
```
Convert a network description file from either physical network or output-port network and return both paths of network definition files, where one is converted from the original infile.
- `in_netfile`: The path to input network description file in either physical network ending in `.xml` or output-port port network ending in `.json`.
- `out_netfile`: (Optional) The output path you want to store the converted file. If not assigned, it automatically generate a file in `temp_path`.
- `target`: (Optional) String of either `json` or `xml`. Return the target format only with the other output being `None` if target is specified and no conversion needed. Default is `None`, where it outputs both formats anyway.

The 2 return values are paths to the network description files, one is the output-port network and the other is the physical network.

### analyze_all
```
num_results = analyzer.analyze_all(netfile, methods, use_tfa, use_sfa)
```
Use all available tools to do analysis given the methods. Return number of results that are computed.
All parameters are optional:
- `netfile`: Executing using a specific network description file, use the one stored in the `analyzer.netfile` if it's `None`.
- `methods`: A list of strings or a string specifying the analysis method. In value either **TFA**, **SFA**, or **PLP**. Default is **TFA**.
- `use_tfa`/`use_sfa`: Boolean variables to select whether to use TFA/SFA bounds for improving PLP bounds. Only relevant when using PLP. Default is both `True`.

The function returns the number of results loaded from the process.

### analyze_xtfa
```
analyzer.analyze_xtfa(netfile, methods)
```
Analyze the network with `xTFA`. All parameters are optional:
- `netfile`: Executing using a specific network description file, conversion is done if needed. Use the network stored in the `analyzer.netfile` if it's `None`.
- `methods`: A list of strings or a string specifying the analysis method. In value **TFA**, ignore other methods. Default is **TFA**.

### analyze_linear
```
analyzer.analyze_linear(netfile, methods)
```
Analyze the network with `Linear TFA solver`. All parameters are optional:
- `netfile`: Executing using a specific network description file, conversion is done if needed. Use the network stored in the `analyzer.netfile` if it's `None`.
- `methods`: A list of strings or a string specifying the analysis method. In value **TFA**, ignore other methods. Default is **TFA**.

### analyze_panco
```
analyzer.analyze_panco(netfile, methods, )
```
Analyze the network with `panco`. All parameters are optional:
- `netfile`: Executing using a specific network description file, use the one stored in the `analyzer.netfile` if it's `None`.
- `methods`: A list of strings or a string specifying the analysis method. In value either **TFA**, **SFA**, or **PLP**. Default is **PLP**.
- `use_tfa`/`use_sfa`: Boolean variables to select whether to use TFA/SFA bounds for improving PLP bounds. Only relevant when using PLP. Default is both `True`.

### analyze_dnc
```
analyzer.analyze_panco(netfile, methods, )
```
Analyze the network with `DNC`. All parameters are optional:
- `netfile`: Executing using a specific network description file, use the one stored in the `analyzer.netfile` if it's `None`.
- `methods`: A list of strings or a string specifying the analysis method. In value either **TFA** or **SFA**. Default is **TFA**.

### write_result
```
analyzer.write_result(output_file, clear)
```
Write the analyze result report from all the stored results.
- `output_file`: path to the output report, must be an `.md` file.
- `clear`: (Optional) Boolean deciding whether to clear the analyzer after finishing writing. Default is `True`.


### clear
Reset the analyzer.
```
analyzer.clear()
```

## Network Generation
Use functions from `src/netscript/net_gen.py`, there are 3 types of network that can be generated automatically. All servers and flows would have the same arrival curve, service curve, and shaper. Networks will be generated into output-port network in `.json` format.
- `generate_interleave_tandem()`
    The network with a chain topology. i.e. **s0** -> **s1** -> ... -> **sn-1**. 1 flow goes through all servers, and $n-1$ flows go from $k \rightarrow k+1$ for $k \in [0, n-2]$
- `generate_ring()`
    The network with a ring topology. i.e. **s0** -> **s1** -> ... -> **sn-1** -> **s0**. $n$ flows go from $k \rightarrow k-1\ mod\ n$
- `generate_mesh()`
    The network with a mesh topology. i.e.
    ```
    ------   ------      --------
    | s0 | - | s2 | ---- | sn-2 |
    ------   ------      --------   ------
           X        X ...         > | sn |
    ------   ------      --------   ------
    | s1 | - | s3 | ---- | sn-1 |
    ------   ------      --------
    ```
    Flows are all $2^{n/2}$ possible combinations from **s0** or **s1** to **sn**.

All 3 methods take the same parameters:
- `size`: The number of servers in the network.
- `burst`: The burst of arrival curve of each flow.
- `arr_rate`: The arrival rate of arrival curve of each flow.
- `pkt_leng`: Packet length of each flow.
- `latency`: Latency of each server.
- `ser_rate`: Service rate of each server.
- `capacity`: The transmission capacity of each server.
- `dir`: (Optional) The output file to store the generated network. Default is `None`, which is not writing the network to file, but return a dictionary of all information instead (the dictionary as loaded from a `.json` file.)

# Example
You may check [example.py](./example/example.py) for the simple example. Here I present the basic usage.
```
import sys
import os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src/")))

from interface import TSN_Analyzer

if __name__ == "__main__":
    analyzer = TSN_Analyzer("./demo.json", temp_path="./temp/", use_shaper="AUTO")
    analyzer.analyze_all()
    analyzer.write_result("./demo_report.md")
```

## Specific Tools
While `analyze_all` tries all possible tools, you may also specify which tool you want to use. For example,
```
analyzer = TSN_Analyzer("./demo.json")
analyzer.analyze_panco(methods=["TFA", "PLP"])
analyzer.analyze_dnc(methods="TFA")
analyzer.write_result("./demo_report.md")     # Containing both panco and DNC results
```
Note that any function called `analyze_xxx` only puts the result into the analyzer's internal buffer. When you call `write_result`, it simply takes all the stored results and write them into the report. Under default setting, the buffer is cleaned after writing results.

You can also choose to not clearing the result buffer after writing a report.
```
analyzer = TSN_Analyzer("./demo.json")
analyzer.analyze_panco(methods=["TFA", "PLP"])
analyzer.write_result("./demo_panco_report.md", clear=False) # Write panco results

analyzer.analyze_dnc(methods="TFA")
analyzer.write_results("./demo_panco_dnc_report.md") # Write results including both panco and DNC
```


## Selecting Shaper
You may change shaper selection any time you want.
```
analyzer = TSN_Analyzer("./demo.json", use_shaper="ON")
analyzer.analyze_panco(methods=["TFA", "PLP"]) # Analysis with shaper
analyzer.set_shaper_usage("OFF")               # Turn off using shaper
analyzer.analyze_xtfa(methods="TFA")           # Analysis without shaper
analyzer.write_result("./demo_report.md")      # panco TFA & PLP is with shaper, xtfa is without shaper
```

## Specific Networks
### Late assignment of network
You may assign different networks every time you want to analyze.
```
analyzer = TSN_Analyzer()
analyzer.analyze_linear(netfile="./demo.json")
analyzer.write_report("./linear_report.md")
```
### Multiple networks
When there are multiple networks (different network names defined in `network` attributes of description files), the program generate multiple reports for each network. The extra report files are named by adding index to the original file. For example,
```
analyzer = TSN_Analyzer("./demo.xml", temp_path="./temp/", use_shaper="AUTO")
analyzer.analyze_all(methods=["TFA", "PLP"]) # Analyze "demo.xml"
analyzer.analyze_linear("./mesh.json")       # Analyze "mesh.json"
analyzer.write_result("./report.md")
```
Such code generates 2 files `report.md` and `report-1.md`, one reports `demo` and the other reports `mesh`.
However, I suggest users to manually write each result when needed because the suitable multiplier is chosen among all results.

### Incorrect type of network
The interface automatically converts the network description file when the input file is not in the right format for the tool. The desired input format for `xTFA` is physical network and all other tools take output-port network.
```
analyzer = TSN_Analyzer("./demo.xml", temp_path="./temp/", use_shaper="AUTO")
analyzer.analyze_linear()
analyzer.write_result("./report.md")
```
The above analysis still gives the report although `linear TFA solver` should take a output-port network in `.json` format.

## Generate Network and Analysis
You can use the network generation functions to generate the following 3 types of networks `interleave tandem`, `ring`, and `mesh`. About their topology and how the flows are assigned, please see [Network Generation](#network-generation).
Say you would like to generate a ring network of 10 servers, you can do the following.
```
from interface import TSN_Analyzer
from netscript.net_gen import *

generate_ring(size=10,
              burst=1,
              arr_rate=1,
              pkt_leng=0,
              latency=1,
              ser_rate=20,
              capacity=20,
              dir="./ring.json")
analyzer = TSN_Analyzer("./ring.json", temp_path="./temp/", use_shaper="AUTO")
analyzer.analyze_all()
analyzer.write_result("./ring_report.md")
```
The arguments for each type of network are the same, you can simply change `ring` to other generating functions.

# Extend this Project
This project is possible to extend for more functionality and possibly includes more TSN analysis tools. Here explains how can anyone extend the scope of this project.

## Files
Here are some files you may use/edit to allow the tool to fit your new tool.
- `interface.py`: You can add a new method in class `TSN_Analyzer` that takes the result from your new tool into a `TSN_result` class (see [here](#standard-analysis-result) for more details). This new method should be able to take 2 arguments:
    1. `netfile`: a path that specifies a network description file, it should use `self.netfile` if it's not specified. Depending on what type of network you need, you can use the private function `_arg_check` in `TSN_Analyzer` to obtain the desired input for analysis.
    2. `methods`: a list that can take method names as strings. Currently only support `TFA`, `SFA`, `PLP`, but feel free to add more since tools automatically ignores unavailable methods.

Depends on how your tool defines a network, you may need to implement the interface to take one of the [network description file format](#network-description-file), and load the analysis result into a `TSN_result` class.

- `netscript/netscript.py`: This file provides some methods to manipulate network description files including conversion between 2 formats; determine if a loaded network is cyclic; and get general network info.

- `netscript/unit_util.py`: This file provides utilities to parse string of values with multipliers and units. This file supports time, data, and data rate values.
    - `parse_num_unit_time(numstr, target_unit)`: Parse a number with time unit words into target number and unit, with any combination of multipliers and time units. Default converting into `s`. For example,
    ```
    >>> parse_num_unit_time("10ms", 's')
    0.01
    >>> parse_num_unit_time("60ks", 'm')
    1000
    >>> parse_num_unit_time("3us")
    3e-6
    ```
    - `parse_num_unit_data(numstr, target_unit)`: Parse a number with data unit words into target number and unit, with any combination of multipliers and data units. Default converting into `b`. For example,
    ```
    >>> parse_num_unit_data("10kb", 'b')
    1000
    >>> parse_num_unit_data("80Mb", 'B')
    1e7
    >>> parse_num_unit_data("2GB")
    1.6e10
    ```
    - `parse_num_unit_rate(numstr, target_unit)`: Parse a number with rate unit words into target number and unit, with any combination of multipliers and rate units. A rate unit is composed by 3 characters `{data_unit}p{time_unit}`. Default converting into `bps`. For example,
    ```
    >>> parse_num_unit_rate("1kbps", 'bps')
    1000
    >>> parse_num_unit_rate("8MBps", 'bpm')
    6e7
    >>> parse_num_unit_rate("2kBps")
    1.6e4
    ```
    - `decide_multiplier(number)`: Decide a suitable multiplier where the leading number is $1 \leq x < 1000$ with a multiplier. For example any number from 1,000 to 999,999 should use `k`.
    ```
    >>> decide_multiplier(1000)
    (1.0, 'k')
    >>> decide_multiplier(0.01)
    (10.0, 'm')
    ```

    - `decide_min_multiplier(numbers_iterable)`: Decide the minimum suitable multiplier for the iterable containing numbers. For example,
    ```
    >>> decide_min_multiplier([10, 0.1, 200])
    'm'
    >>> decide_min_multiplier([2e3, 5e3, 1e8])
    'k'
    ```


## Standard Analysis Result
Please refer to the file `result.py`, any analysis result should be stored as a `TSN_result` class. So that you don't need to worry about how to write your result. The method `TSN_Analyzer.write_result` automatically processes `TSN_result` and write the corresponding output.
It's OK if your tool cannot fit all the properties of `TSN_result`, they all have default values. But I recommend you should at least specify `name`, `tool`, `method`, `graph`, and `flow_delays` for the redability of report.

Here are the meaning of each property in `TSN_result`:
- `name`: Name of the network
- `tool`: Tool used in this analysis. e.g. `DNC` or `panco`
- `method`: Analysis method. e.g. `TFA` or `PLP`
- `graph`: The graph representation of the network, including unused links
- `num_servers`: Number of servers in the network
- `num_flows`: Number of flows in the network
- `server_delays`: Delays stored according to server names, unit in seconds. e.g. `{'s_1': 1.0, 's_2': 2.0}`
- `total_delay`: Sum of all server delays
- `server_backlogs`: Delays stored according to server names, unit in bits. e.g. `{'s_1': 1, 's_2': 2}`
- `max_backlog`: Maximum of all server backlogs
- `flow_paths`: Path of each flow as a list of servers according to flow names. e.g. `{'fl_1': ['s_1', 's_2']}`
- `flow_cmu_delays`: Cumulative delays along the path by each flow. e.g. `{'fl_1': {'s_1': 1.0, 's_2': 3.0}}`
- `flow_delays`: End-to-end delays of each flow. e.g. `{'fl_1': 4.0, 'fl_2': 7.0}`
- `exec_time`: Execution time of the analysis, unit in seconds
- `converted_from`: Which file it's converted from, it's an empty string if it's original

# Contact
Regarding any question/problem about this project, please contact me via E-mail: [academic](mailto:chun-tso.tsai@epfl.ch), [primary](mailto:tsai.chuntso@gmail.com), or [secondary](mailto:adfeel220@gmail.com).