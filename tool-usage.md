
Tool Usage
============
This file covers the information about which part of functionalities among these tools that I used to build the interface.

xTFA
-----------
We use the class `CyclicNetwork` defined in `xtfa/networks/` to do the analysis. Although there are `FeedForwardNetwork` and `CyclicNetwork` defined in `xtfa/networks/`, cyclic network can also solve feed-forward networks. As a result we use the `CyclicNetwork` to contruct the network.

Since `xtfa` was already capable of reading directly from any network file defined in `WOPANet` format, we only need to call `WopanetReader` in `xtfa/networks/` to load the network.

To do the analysis, we simply do the following
```
xtfa_net = xtfa.networks.CyclicNetwork(xtfa.fasUtility.TopologicalSort())
reader = xtfa.networks.WopanetReader()
reader.configure_network_from_xml(xtfa_net, network_file)
xtfa_net.auto_install_pipelines()

xtfa_net.compute()
```


NetCal/DNC
------------
Generally, in `DNC` you need to construct your network with several functions. They are:
- `ServerGraph`: Defined in `org.networkcalculus.dnc.network.server_graph`. You need to define the network topology, flows, and servers for a `ServerGraph` to do analysis.
- `Server`: A `ServerGraph` is composed with multiple `Server` objects. To define a server, you may also need `ServiceCurve` and/or `MaxServiceCurve`. A service curve can be built using
    ```
    ServiceCurve sCurve = Curve.getFactory().createRateLatency(rate, lat);
    ```
    where you need to import `org.networkcalculus.dnc.curves.ServiceCurve` and `org.networkcalculus.dnc.curves.Curve`.

    Then you can add a server into the server graph using
    ```
    Server newServer = serverGraph.addServer(serverName, sCurve, max_sCurve));
    ```
- `Turn`: A `Turn` represents a connection link in the server graph. You can use the following function to make connections.
    ```
    serverGraph.addTurn(server_i, server_j);
    ```
    `Turn` is defined in `import org.networkcalculus.dnc.network.server_graph.Turn`
- `Flow`: Defined in `import org.networkcalculus.dnc.network.server_graph.Flow`. It represents a flow in a server graph. You first need an arrival curve for a flow:
    ```
    import org.networkcalculus.dnc.curves.ArrivalCurve;
    ...
    ArrivalCurve aCurve = Curve.getFactory().createTokenBucket(rate, bur);
    Flow flowByPath = serverGraph.addFlow(flowName, aCurve, path);
    Flow flowOneHop = serverGraph.addFlow(flowName, aCurve, server);
    Flow flowShortestPath = serverGraph.addFlow(flowName, aCurve, server_source, server_destination);
    ```

You can see how to use them in demos presented in `DNC/src/main/java/org/networkcalculus/dnc/demos/`, or `NetworkAnalysis/NetworkScriptHandler.java` to see how we parse our `.json` files into a DNC server graph.


To do the analysis, you can use any analysis methods defined in `org.networkcalculus.dnc.tandem.analyses`. For example to do `TFA`:
```
import org.networkcalculus.dnc.tandem.analyses.TotalFlowAnalysis;

TotalFlowAnalysis tfa = new TotalFlowAnalysis(sg); // sg is a ServerGraph
tfa.performAnalysis(foi); // foi is a Flow object, as your flow of interest
```

In this project, we simply parse the `.json` format and use the information to construct a `ServerGraph`, then use the analysis tool to analyze the server graph. We later format the analysis result from DNC and then captured by the Python interface.

panco
------------
In `panco`, you may use the following definition to build a network for analysis.
```
from panco.descriptor.curves import TokenBucket, RateLatency
from panco.descriptor.flow import Flow
from panco.descriptor.server import Server
from panco.descriptor.network import Network
```
- `Arrival/Service Curves`: Use class `TokenBucket` or `RateLatency` to contruct curves. For example:
    ```
    service_curve = RateLatency(rate, latency)
    arrival_curve = TokenBucket(burst, rate)
    ```
- `Server`: Use class `Server` to construct a server. For example:
    ```
    server = Server(service_curves, max_service_curves)
    ```
    `service_curves` is a list of `RateLatency` curves, it means the service curve of this server is the maximum of these rate-latency curves.
    `max_service_curves` is a list of `TokenBucket` curves, it means the maximum service curve of this server is the minimum of these token-bucket curves.

- `Flow`: Use class `Flow` to construct a flow. For example:
    ```
    flow = Flow(arrival_curves, path)
    ```
    `arrival_curves` is a list of `TokenBucket` curves, it means the arrival curve of this flow is the minimum of these token-bucket curves.
    `path` is a list of server indices to represent the path of the flow. For example `path = [0,1,4]`.

- `Network`: Use class `Network` to construct a network. For example:
    ```
    network = Network(servers, flows)
    ```
    `servers` is a list of `Server` objects and `flows` is a list of `flows`. Note that the server indices used in `path` defined in each `Flow` should be consistent with `servers`.

To do the analysis, you can use the following modules
```
from panco.fifo.fifoLP import FifoLP
from panco.fifo.tfaLP import TfaLP
from panco.fifo.sfaLP import SfaLP
```
`FifoLP` can perform `PLP` (Polynomial Linear Program) or `ELP` (Exponential Linear Program) methods, and the other 2 are `TFA` and `SFA`.

You can do analysis as the following example:
```
# TFA analysis
tfa = TfaLP(network)
delay_per_server = tfa.delay_servers
delay_per_flow = tfa.all_delays
delay_flow_i = tfa.delay(i)

# SFA analysis
sfa = SfaLP(network)
delay_per_flow = sfa.all_delays
delay_flow_i = sfa.delay(i)

# PLP analysis
plp = FifoLP(network, polynomial=True, tfa=True, sfa=True)  # tfa/sfa constrols whether to use TFA or SFA results to improve delay bound
delay_per_flow = plp.all_delays
delay_flow_i = plp.delay(i)

# ELP analysis
elp = FifoLP(network, polynomial=False, tfa=True, sfa=True)  # tfa/sfa constrols whether to use TFA or SFA results to improve delay bound
delay_per_flow = elp.all_delays
delay_flow_i = elp.delay(i)
```