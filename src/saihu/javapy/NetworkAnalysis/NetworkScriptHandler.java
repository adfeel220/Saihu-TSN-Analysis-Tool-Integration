package NetworkAnalysis;

import org.json.*;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Set;
import java.util.Map;
import java.util.LinkedList;
import com.google.common.collect.ImmutableMap;

/*Network calculus DNC*/
import org.networkcalculus.dnc.AnalysisConfig;
import org.networkcalculus.dnc.curves.ArrivalCurve;
import org.networkcalculus.dnc.curves.Curve;
import org.networkcalculus.dnc.curves.MaxServiceCurve;
import org.networkcalculus.dnc.curves.ServiceCurve;
import org.networkcalculus.dnc.network.server_graph.Flow;
import org.networkcalculus.dnc.network.server_graph.Server;
import org.networkcalculus.dnc.network.server_graph.Turn;
import org.networkcalculus.dnc.network.server_graph.ServerGraph;


public class NetworkScriptHandler {

    /*Variables*/
    static JSONObject networkInfo;
    static ServerGraph network;
    static JSONArray jsonFlows;
    static ArrayList<Flow> netFlows = new ArrayList<Flow>();
    static JSONArray jsonServers;
    static ArrayList<Server> netServers = new ArrayList<Server>();
    static JSONArray jsonAdjacency;
    static final Map<String, String> keys = ImmutableMap.<String, String>builder()
            .put("networkInfo", "network")
            .put("servers", "servers")
            .put("servers_name", "name")
            .put("servers_serviceCurve", "service_curve")
            .put("servers_serviceCurve_latency", "latencies")
            .put("servers_serviceCurve_rate", "rates")
            .put("servers_capacity", "capacity")
            .put("flows", "flows")
            .put("flows_name", "name")
            .put("flows_path", "path")
            .put("flows_arrivalCurve", "arrival_curve")
            .put("flows_arrivalCurve_burst", "bursts")
            .put("flows_arrivalCurve_rate", "rates")
            .put("flows_packetLength", "packet_length")
            .put("adjacencyMatrix", "adjacency_matrix")
            .build();

    /*Methods*/

    public static void main(String[] args) {
        NetworkScriptHandler nsh = new NetworkScriptHandler();

        try {
            String fpath = "myutil/network_def.json";
            parse(fpath);

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    /* Return network objects */
    public ServerGraph getNetwork() { return network; }
    public ArrayList<Server> getServers() { return netServers; }
    public ArrayList<Flow> getFlows() { return netFlows; }
    public JSONObject getNetworkInfo() { return networkInfo; }
    public JSONArray getAdjacency() { return jsonAdjacency; }
    public JSONArray getJsonServers() { return jsonServers; }
    public JSONArray getJsonFlows() { return jsonFlows; }


    public static void parse(String fpath) {
        JSONObject jsonNetwork = new JSONObject();
        try {
            jsonNetwork = getJSONObject(fpath);
        } catch (Exception e) {
            e.printStackTrace();
        }

        /* Parse general network information */
        try {
            networkInfo = jsonNetwork.getJSONObject(keys.get("networkInfo"));
        } catch (Exception e) {
            System.out.println("No network object defined in file");
            e.printStackTrace();
        }

        /* Initialize network */
        network = new ServerGraph();

        /* Parse server information */
        jsonServers = jsonNetwork.getJSONArray(keys.get("servers"));
        jsonFlows = jsonNetwork.getJSONArray(keys.get("flows"));
        jsonAdjacency = jsonNetwork.getJSONArray(keys.get("adjacencyMatrix"));

        int serverNum = parseServer();
        int serverNumTopo = parseTopology();
        if (serverNum != serverNumTopo) {
            String errorMsg = String.format("Server number defined in \"%s\" (%d servers) is inconsistent to \"%s\" (%d servers).",
                    keys.get("adjacencyMatrix"), serverNumTopo, keys.get("servers"), serverNum);
            throw new RuntimeException(errorMsg);
        }

        parseFlow();

    }


    /* Return the JSON object given a JSON file name */
    public static JSONObject getJSONObject(String fpath) throws IOException{
        Path filename = Path.of(fpath);
        String jsonContentString = Files.readString(filename);
        return new JSONObject(jsonContentString);
    }


    /* parse the server information and add corresponding servers into network */
    private static int parseServer() {
        int serverNum = jsonServers.length();
        for (int i=0; i<serverNum; i++){
            JSONObject serverInfo = jsonServers.getJSONObject(i);
            // service curve construction
            JSONObject serviceCurveInfo = serverInfo.getJSONObject(keys.get("servers_serviceCurve"));
            String serverName = serverInfo.optString(keys.get("servers_name"), String.format("Server_%d", i));

            JSONArray latencies = serviceCurveInfo.getJSONArray(keys.get("servers_serviceCurve_latency"));
            JSONArray rates = serviceCurveInfo.getJSONArray(keys.get("servers_serviceCurve_rate"));

            // Check if length of latencies is the same as rates
            if (latencies.length() == 0) {
                String errorMsg = String.format("Latency of server %d (%s) undefined.", i, serverName);
                throw new RuntimeException(errorMsg);
            }
            if (rates.length() == 0) {
                String errorMsg = String.format("Service rate of server %d (%s) undefined.", i, serverName);
                throw new RuntimeException(errorMsg);
            }
            int curveSegmentsNum = latencies.length();
            if (latencies.length() != rates.length()) {
                System.out.format("Latencies and rates have different lengths on server %d (%s)." +
                        " Lat: %d vs. Rate: %d. Choose shorter one instead.", i, serverName, latencies.length(), rates.length());
                if (latencies.length() > rates.length()){
                    curveSegmentsNum = rates.length();
                }
            }

            // Construct service curve
            double lat = latencies.getDouble(0);
            double rate = rates.getDouble(0);
            ServiceCurve sCurve = Curve.getFactory().createRateLatency(rate, lat);
            for (int j=1; j<curveSegmentsNum; j++){
                lat = latencies.getDouble(j);
                rate = rates.getDouble(j);
                ServiceCurve newSegment = Curve.getFactory().createRateLatency(rate, lat);
                // Update the curve
                sCurve = Curve.getUtils().max(sCurve, newSegment);
            }

            // Construct max service curve
            double maxPacketLength = getMaxPacketLength(i);
            double capacity = serverInfo.optDouble(keys.get("servers_capacity"), 0);
            Curve maxCurve = Curve.getFactory().createTokenBucket(capacity, maxPacketLength);
            MaxServiceCurve msCurve = Curve.getFactory().createMaxServiceCurve(maxCurve);

            // Add server to graph
            Server newServer = network.addServer(serverName, sCurve, msCurve, AnalysisConfig.Multiplexing.FIFO, false, false);
            netServers.add(newServer);
        }
        return serverNum;
    }

    /* parse the adjacency matrix to construct topology (Turns) to the network */
    private static int parseTopology() {
        int serverNum = jsonAdjacency.length();

        // construct the server graph
        for (int i=0; i<serverNum; i++) {
            JSONArray row_i = jsonAdjacency.getJSONArray(i);
            for (int j=0; j<serverNum; j++) {
                int val = row_i.getInt(j);
                if (val > 0) {
                    try{
                        network.addTurn(netServers.get(i), netServers.get(j));
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            }
        }
        return serverNum;
    }

    /* parse the flows information and add it to the network */
    private static int parseFlow() {
        int flowNum = jsonFlows.length();
        for (int i=0; i<flowNum; i++){
            JSONObject flowInfo = jsonFlows.getJSONObject(i);
            String flowName = flowInfo.optString(keys.get("flows_name"), String.format("Flow_%d", i));

            // Get arrival curve information
            JSONObject arrivalCurveInfo = flowInfo.getJSONObject(keys.get("flows_arrivalCurve"));
            JSONArray bursts = arrivalCurveInfo.getJSONArray(keys.get("flows_arrivalCurve_burst"));
            JSONArray rates = arrivalCurveInfo.getJSONArray(keys.get("flows_arrivalCurve_rate"));

            // Check input syntax
            if (bursts.length() == 0) {
                String errorMsg = String.format("Burst of flow %d (%s) undefined.", i, flowName);
                throw new RuntimeException(errorMsg);
            }
            if (rates.length() == 0) {
                String errorMsg = String.format("Arrival rate of flow %d (%s) undefined.", i, flowName);
                throw new RuntimeException(errorMsg);
            }
            int curveSegmentsNum = bursts.length();
            if (bursts.length() != rates.length()) {
                System.out.format("Bursts and rates have different lengths on flow %d (%s)." +
                        " Bur: %d vs. Rate: %d. Choose shorter one instead.", i, flowName, bursts.length(), rates.length());
                if (bursts.length() > rates.length()){
                    curveSegmentsNum = rates.length();
                }
            }

            // Construct the arrival curve
            double bur = bursts.getDouble(0);
            double rate = rates.getDouble(0);
            ArrivalCurve aCurve = Curve.getFactory().createTokenBucket(rate, bur);
            for (int j=1; j<curveSegmentsNum; j++){
                bur = bursts.getDouble(j);
                rate = rates.getDouble(j);
                ArrivalCurve newSegment = Curve.getFactory().createTokenBucket(rate, bur);
                // Update the curve
                aCurve = Curve.getUtils().min(aCurve, newSegment);
            }

            // Resolve path
            JSONArray jsonPath = flowInfo.getJSONArray(keys.get("flows_path"));
            // No path defined
            if (jsonPath.length() <= 0) {
                throw new RuntimeException(String.format("Flow %d (%s) path undefined.", i, flowName));
            }

            /*
            * Create flow object in the network
            * */
            Flow newFlow = Flow.NULL_FLOW;

            // special case, if only one hop
            if (jsonPath.length() == 1) {
                Server hop = netServers.get(jsonPath.getInt(0));
                try{
                    newFlow = network.addFlow(flowName, aCurve, hop);
                } catch (Exception e) {
                    e.printStackTrace();
                }
                continue;
            }

            // general case, a specific path exists
            LinkedList<Turn> path = new LinkedList<Turn>();
            int prevServerID = jsonPath.getInt(0);
            int nextServerID;
            for (int j=1; j<jsonPath.length(); j++){
                nextServerID = jsonPath.getInt(j);
                Turn step = getTurn(prevServerID, nextServerID);
                path.add(step);
                prevServerID = nextServerID;
            }

            try{
                newFlow = network.addFlow(flowName, aCurve, path);
            } catch (Exception e) {
                e.printStackTrace();
            }

            if (newFlow != Flow.NULL_FLOW) {
                netFlows.add(newFlow);
            }

        }
        return flowNum;
    }

    /* Return the turn from s1 to s2 */
    private static Turn getTurn(int s1_idx, int s2_idx) {
        Server s1 = netServers.get(s1_idx);
        Server s2 = netServers.get(s2_idx);
        return getTurn(s1, s2);
    }

    /* Return the turn from s1 to s2 */
    private static Turn getTurn(Server s1, Server s2) {
        Set<Turn> turns = network.getOutTurns(s1);
        turns.retainAll(network.getInTurns(s2));

        if (turns.size() > 1) {
            throw new RuntimeException(String.format("Multiple paths going from %s to %s", s1.getAlias(), s2.getAlias()));
        }

        return turns.iterator().next();
    }

    /* Return the maximum packet length observed by a specific server */
    private static double getMaxPacketLength(int serverIdx) {
        double maxPktLen = 0;
        for (int i=0; i<jsonFlows.length(); i++){
            JSONObject flow = jsonFlows.getJSONObject(i);
            JSONArray path = flow.getJSONArray(keys.get("flows_path"));
            for (int j=0; j<path.length(); j++) {
                // The target server exist in this flow
                if (path.getInt(j) == serverIdx) {
                    double pktlen = flow.optDouble(keys.get("flows_packetLength"), 0);
                    if (pktlen > maxPktLen) {
                        maxPktLen = pktlen;
                    }
                    break;
                }
            }
        }

        return maxPktLen;
    }

}
