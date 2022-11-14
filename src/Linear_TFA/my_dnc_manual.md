DNC Manual
==================
Author: Chun-Tso Tsai
Date: Oct. 12, 2022 (last updated)
Advisors: Hossein Tabatabaee, Stéphan Plassart
Institute: École Polytechnique Fédérale de Lausanne

About
----------
This is a manual for [NetCal DNC](https://github.com/NetCal/DNC) tool. Since such manual is not available on their official website, I decided to create my own version of it.

## utility
### Num
Use `import org.networkcalculus.num.Num`

To create a `Num` class with `double`/`int` 10:
```
Num number = Num.getFactory(Calculator.getInstance().getNumBackend()).create(10);
```
The command `create` can be changed to other instances: $+\infty, 0$ or basic $+,-,\times,\div$ of other `Num` objects.

### Curves
Use `import org.networkcalculus.dnc.curves.*;` to use the following functions.
* **Types**: Classes include generic `Curve`, `ArrivalCurve`, `ServiceCurve`, `MaxServiceCurve`. The basic token-bucket and rate-latency curve can be initialized by
    ```
    Curve.getFactory().createTokenBucket(rate, burst);
    Curve.getFactory().createRateLatency(rate, latency);
    Curve.getFactory().createRateLatencyMSC(rate, latency); // Max Service Curve version
    ```
* **Curve Operations**: To perform operations over curves, use `Curve.getUtils()`. This contains `add`, `sub`, `min`, `max` of the same curve class. (`Curve`, `ServiceCurve`, `ArrivalCurve`.)
* **Add Segments** A linear segment can be added into a curve using `curve.addSegment(linear_segment)` where the argument is a `LinearSegment` object.
    It seems we can only add finite number of segments, I didn't find the periodic segment definition like in the RTC tool.
* **Create Segments** A `LinearSegment` can be created by `LinearSegment.createLinearSegment(Num x, Num y, Num grad)`. The 3 arguments correspond to the (x,y) coordinate of the starting point and the slope.
* **Get curve inverse function**`f_inv`: Suppose `cur` is a `Curve` object, `cur.f_inv(y)` can find the leftmost x-coordinate of given y value. To select rightmost x-coordinate, use `cur.f_inv(y, true)`.
* **Derive curve bounds**: In `org.networkcalculus.dnc.bounds.disco.pw_affine`, there are functions `deriveARB` and `deriveFIFO` take arguments as `deriveFIFO(arrival_curve, service_curve)`. For FIFO curves, it derives the leftmost x-coordinate on the service curve corresponding to the arrival burst.



### Server Graph
Use `import org.networkcalculus.dnc.network.server_graph.ServerGraph;`

Class `ServerGraph` can be initialized
```
ServerGraph sg = new ServerGraph();
```

### Server
Use `import org.networkcalculus.dnc.network.server_graph.Server;`

* **Define a server**: A server can be initialized and added to a `ServerGraph sg` by
    ```
    Server server_0 = sg.addServer(service_curve)
    ```
    given a defined `service_curve`.

    One can also specify more server information by
    ```
    Server s0 = sg.addServer(service_curve, max_service_curve, Multiplexing.FIFO, use_max_service_curve, use_max_service_output_rate);
    ```
    where a maximum service curve can be given by a `MaxServiceCurve` object. A multiplexing strategy can be specified using `Multiplexing` enum, _Arbitrary_ strategy is specified if no explicit multiplexing assigned. `use_max_service_curve` and `use_max_service_output_rate` decide whether to use maximum service curve or maximum service output rate.

* **Max Service Curve/Rate** The difference between `use_max_sc` and `use_max_sc_output_rate` is
    - If `use_max_sc` is true, it convolves the Maximum Service Curve (MSC) with the arrival curve **before** deriving the output bound.
    - If `use_max_sc_output_rate` is true, it convolves the MSC with the output bound.


* **Multiplexing Strategy** The default multiplexing policy for a server is **Arbitrary**. The multiplexing strategies can be found in `org.networkcalculus.dnc.AnalysisConfig.Multiplexing`. After importing it, we can select `Multiplexing.FIFO` for FIFO policy.
    If FIFO, then the delay bound per server is computed by the x-coordinate of service curve with y = burst of arrival curve.
    If Arbitrary, the delay bound per server is the smallest x-coordinate where the arrival curve and service curve intersects.


### Turns
A `Turn` represents a link in a network. It's also a basic element to define a path in a network.

* **Create Links** Suppose there are 2 servers `s0` and `s1` in a ServerGraph `sg`. A turn can defined as
    ```
    Turn t_0_1 = sg.addTurn(s0, s1);
    ```
* **Path** A path is a sequence of turns to define a path of a flow. It can be constructed as follows:
    ```
    LinkedList<Turn> path0 = new LinkedList<Turn>();
    path0.add(t_0_1);
    path0.add(t_1_2);
    ```
    The above code creates a path from server 0->1->2


### Flows
Use `import org.networkcalculus.dnc.network.server_graph.Flow;`
* **Single hop**: A single hop flow passes through only 1 server.
    ```
    Flow flow_single = sg.addFlow(arrival_curve, s0); // pass through only s0
    ```

* **Shortest Path**: Given 2 servers, the function automatically finds the shortest path from the first to last. e.g. a network s0->s1->s2,
    ```
    Flow flow_sp = sg.addFlow(arrival_curve, s0, s2);
    ```
    Goes from s0 to s2.

* **Specified Path**: Set flow with path defined as previous section.
    ```
    Flow flow_path = sg.addFlow(arrival_curve, path0);
    ```


### Analysis
```
import org.networkcalculus.dnc.tandem.analyses.TotalFlowAnalysis;
import org.networkcalculus.dnc.tandem.analyses.SeparateFlowAnalysis;
import org.networkcalculus.dnc.tandem.analyses.PmooAnalysis;
import org.networkcalculus.dnc.tandem.analyses.TandemMatchingAnalysis;
```
After a ServerGraph is defined, we can conduct the following analysis.
(FIFO servers can only do TFA & SFA)

* **Flow of interest**: We need to specify a flow of interest (F.o.I) for the analysises. The simplest way is to iterate through all flows in a server graph `for (Flow foi : sg.getFlows())`

* **Analysis Configuration**: Before usage, choose a global multiplexing, otherwise `ARBITRARY` is the default setting.
    - Multiplexing
        ```
        AnalysisConfig config = new AnalysisConfig();
        config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_FIFO);
        config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.SERVER_LOCAL);
        ```
        `GLOBAL_FIFO` means FIFO will apply to all servers; `SERVER_LOCAL` means the multiplexing strategy depends on the multiplexing policy defined on each server.
    - Arrival Bound Method
        ```
        config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_PBOO_CONCATENATION);
        ```
        Choose different methods to derive output arrival bounds. Supports `AGGR_PBOO_CONCATENATION`, `AGGR_PBOO_PER_SERVER`, `AGGR_PMOO`, `AGGR_TM`, `SEGR_PBOO`, `SEGR_PMOO`, `SEGR_TM`, `SINKTREE_AFFINE_DIRECT`, `SINKTREE_AFFINE_HOMO`, `SINKTREE_AFFINE_MINPLUS`.
        Note that not all arrival bounds methods are available in all analysis methods.

* **TFA** (Total Flow Analysis): for each server, it finds the aggregate arrival and computes `service_curve.f_inv(arrival_curve.getBurst())` 
The output curve (as an arrival curve for the next server) depends on the mode selected in `config`. The default is `AGGR_PBOO_CONCATENATION`, which is the (min,plus) deconvolution of arrival curve and service curve.
    - We need to initialize an object to analyze. `config` is optional.
        ```
        TotalFlowAnalysis tfa = new TotalFlowAnalysis(sg, config);
        ```
    - TFA supports analysis on delay bounds (total & per server), backlog bounds (total & per server), and arrival bounds on each server.
        ```
        tfa.performAnalysis(flow_of_interest);
        System.out.println("delay bound     : " + tfa.getDelayBound());
        System.out.println("     per server : " + tfa.getServerDelayBoundMapString());
        System.out.println("backlog bound   : " + tfa.getBacklogBound());
        System.out.println("     per server : " + tfa.getServerBacklogBoundMapString());
        System.out.println("alpha per server: " + tfa.getServerAlphasMapString());
        ```

* **SFA** (Separate Flow Analysis)
    - Init (config is optional)
        ```
        SeparateFlowAnalysis sfa = new SeparateFlowAnalysis(sg, config);
        ```
    - SFA supports analysis on the leftover service curves, arrival bounds on servers, total delay, and backlog.
        ```
        sfa.performAnalysis(flow_of_interest);
        System.out.println("e2e SFA SCs     : " + sfa.getLeftOverServiceCurves());
        System.out.println("     per server : " + sfa.getServerLeftOverBetasMapString());
        System.out.println("xtx per server  : " + sfa.getServerAlphasMapString());
        System.out.println("delay bound     : " + sfa.getDelayBound());
        System.out.println("backlog bound   : " + sfa.getBacklogBound());
        ```
* **PMOO** (Pay Multiplexing Only Once)
    - Init (config is optional)
        ```
        PmooAnalysis pmoo = new PmooAnalysis(sg, config);
        ```
    - PMOO supports analysis on the leftover service curves, arrival bounds on servers, total delay, and backlog.
        ```
        pmoo.performAnalysis(flow_of_interest);
        System.out.println("e2e PMOO SCs    : " + pmoo.getLeftOverServiceCurves());
        System.out.println("xtx per server  : " + pmoo.getServerAlphasMapString());
        System.out.println("delay bound     : " + pmoo.getDelayBound());
        System.out.println("backlog bound   : " + pmoo.getBacklogBound());
        ```
* **Tandem Matching**: Return the smallest worst-case delay among all servers on F.o.I
    - Init (config is optional)
        ```
        TandemMatchingAnalysis tma = new TandemMatchingAnalysis(sg, config);
        ```
    - Tandem matching supports analysis on the leftover service curves, arrival bounds on servers, total delay, and backlog.
        ```
        tma.performAnalysis(flow_of_interest);
        System.out.println("e2e TMA SCs    : " + tma.getLeftOverServiceCurves());
        System.out.println("xtx per server  : " + tma.getServerAlphasMapString());
        System.out.println("delay bound     : " + tma.getDelayBound());
        System.out.println("backlog bound   : " + tma.getBacklogBound());
        ```
* **FIFO Tandem**: Return the smallest FIFO delay among all servers on F.o.I
    - Init (config is optional)
        ```
        FIFOTandem ft = new FIFOTandem(sg, config);
        ```
    - FIFOTandem supports analysis on the leftover service curves, arrival bounds on servers, total delay, and backlog.
        ```
        ft.performAnalysis(flow_of_interest);
        System.out.println("e2e FT SCs    : " + ft.getLeftOverServiceCurves());
        System.out.println("xtx per server  : " + ft.getServerAlphasMapString());
        System.out.println("delay bound     : " + ft.getDelayBound());
        System.out.println("backlog bound   : " + ft.getBacklogBound());
        ```

* **Nested Tandem**: LUDB_FF, LB_FF, DS_FF, GS. 
The usage is different from other analysis. First we need to import it from the following directory.
    ```
    import org.networkcalculus.dnc.tandem.fifo.NestedTandemAnalysis;
    ```

    Then
    ```
    NestedTandemAnalysis nta = new NestedTandemAnalysis(path0, foi, flows, config);
    ```
    where `path0` is a path, `foi` is a flow object, `flows` is a `List<Flow>` or `Set<Flow>`. config is optional.

    Nested Tandem supports LUDB, LB, DS, GS analysis for leftover service curves.
    ```
    nta.selected_mode = NestedTandemAnalysis.mode.LUDB_FF;
    ServiceCurve curve = nta.getServiceCurve();
    ```
    `LUDB_FF` can be changed to `LB_FF`, `DS_FF`, `GS` as well.

    Delay bound is also possible by
    ```
    Num d = nta.performAnalysis();
    ```
