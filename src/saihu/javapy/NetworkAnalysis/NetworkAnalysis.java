package NetworkAnalysis;

import NetworkAnalysis.FileGetter;

import org.networkcalculus.dnc.AnalysisConfig;
import org.networkcalculus.dnc.network.server_graph.Path;
import org.networkcalculus.dnc.tandem.analyses.*;
import org.networkcalculus.num.Num;
import org.networkcalculus.dnc.network.server_graph.Flow;
import org.networkcalculus.dnc.network.server_graph.ServerGraph;
import org.networkcalculus.dnc.network.server_graph.Server;

import org.json.JSONObject;
import org.json.JSONArray;

import java.util.Set;
import java.util.Map;

public class NetworkAnalysis {
    public NetworkAnalysis(){}

    public enum AnalysisTool {
        TFA,    // Total flow analysis
        TFApp,  // Total flow analysis with maximum service curve
        SFA,    // Separate flow analysis
        SFApp,  // Separate flow analysis with maximum service curve
        PMOO,   // Pay Multiplexing Only Once
        PMOOpp, // Pay Multiplexing Only Once with maximum service curve
        TMA,    // Tandem Matching Analysis
        TMApp,  // Tandem Matching Analysis with maximum service curve
        LUDB,   // LUDB FIFO Tandem
        LUDBpp
    }

    private static FileGetter fileGetter = new FileGetter();
    private static NetworkScriptHandler netScript;


    public static void main(String[] args) {
        try {
            NetArgParser argParser = new NetArgParser(args);
            if (argParser.isPrintHelp()) return;

            String fpath = argParser.getInFilePath();
            netScript = new NetworkScriptHandler();
            netScript.parse(fpath);

            for (AnalysisTool tool : argParser.getTools()) {
                analysis(tool);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void analysis(AnalysisTool tool) {
        for (Flow foi : netScript.getFlows()) {
            analysis(tool, foi);
        }
    }

    /* Perform analysis based on the selected tool and F.O.I (Flow of interest) */
    public static void analysis(AnalysisTool tool, Flow foi) {

        AnalysisConfig config = new AnalysisConfig();
        // Determine multiplexing technique
        String mux = netScript.getNetworkInfo().getString("multiplexing");
        if (mux.equalsIgnoreCase("FIFO")){
            config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_FIFO);
        } else if (mux.equalsIgnoreCase("ARBITRARY")) {
            config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
        } else {
            config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.SERVER_LOCAL);
        }

        config.path_to_cplex = fileGetter.cplex_path;
        config.path_to_lp_dir = fileGetter.fileDir;

        ServerGraph sg = netScript.getNetwork();

        switch (tool) {
            case TFA:
                // Configure analysis parameters
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_PBOO_CONCATENATION);
                TotalFlowAnalysis tfa = new TotalFlowAnalysis(sg, config);

                // Run and print in JSON format
                try{
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    tfa.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = tfa.getDelayBound();
                    Num maxBacklog = tfa.getBacklogBound();
                    JSONObject serverDelays = new JSONObject();
                    JSONObject serverBacklogs = new JSONObject();

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    Map<Server, Set<Num>> delayMap = tfa.getServerDelayBoundMap();
                    Map<Server, Set<Num>> backlogMap = tfa.getServerBacklogBoundMap();

                    double cumulativeDelay = 0.0;
                    for (Server server : foi.getPath().getServers()) {
                        String serverName = server.getAlias();
                        // Resolve name and path
                        flow_path.put(serverName);

                        // Parse delay
                        Set<Num> delaySet = delayMap.get(server);
                        double delay = 0.0;
                        if (delaySet.size() > 1) {
                            System.out.println("More than 1 delay for server " + serverName);
                        } else {
                            delay = Double.parseDouble(delaySet.stream().toList().get(0).toString());
                        }
                        cumulativeDelay += delay;

                        // Parse backlog
                        Set<Num> backlogSet = backlogMap.get(server);
                        double backlog = 0.0;
                        if (backlogSet.size() > 1) {
                            System.out.println("More than 1 backlog for server " + serverName);
                        } else {
                            backlog = Double.parseDouble(backlogSet.stream().toList().get(0).toString());
                        }

                        // Put result into container
                        serverDelays.put(serverName, delay);
                        serverBacklogs.put(serverName, backlog);
                        flow_cmu_delay.put(cumulativeDelay);

                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "TFA");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", cumulativeDelay);
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);

                } catch (Exception e) {
                    System.out.println("TFA analysis failed");
                    e.printStackTrace();
                }
                break;

            case TFApp:
                // Configure
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_PBOO_CONCATENATION);
                TotalFlowAnalysis tfapp = new TotalFlowAnalysis(sg, config);

                // Run and print
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    tfapp.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = tfapp.getDelayBound();
                    Num maxBacklog = tfapp.getBacklogBound();
                    JSONObject serverDelays = new JSONObject();
                    JSONObject serverBacklogs = new JSONObject();

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    Map<Server, Set<Num>> delayMap = tfapp.getServerDelayBoundMap();
                    Map<Server, Set<Num>> backlogMap = tfapp.getServerBacklogBoundMap();

                    double cumulativeDelay = 0.0;
                    for (Server server : foi.getPath().getServers()) {
                        String serverName = server.getAlias();
                        // Resolve name and path
                        flow_path.put(serverName);

                        // Parse delay
                        Set<Num> delaySet = delayMap.get(server);
                        double delay = 0.0;
                        if (delaySet.size() > 1) {
                            System.out.println("More than 1 delay for server " + serverName);
                        } else {
                            delay = Double.parseDouble(delaySet.stream().toList().get(0).toString());
                        }
                        cumulativeDelay += delay;

                        // Parse backlog
                        Set<Num> backlogSet = backlogMap.get(server);
                        double backlog = 0.0;
                        if (backlogSet.size() > 1) {
                            System.out.println("More than 1 backlog for server " + serverName);
                        } else {
                            backlog = Double.parseDouble(backlogSet.stream().toList().get(0).toString());
                        }

                        // Put result into container
                        serverDelays.put(serverName, delay);
                        serverBacklogs.put(serverName, backlog);
                        flow_cmu_delay.put(cumulativeDelay);

                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "TFA++");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", cumulativeDelay);
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("TFA++ analysis failed");
                    e.printStackTrace();
                }
                break;

            case SFA:
                // Configure
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.SEGR_PBOO);
                SeparateFlowAnalysis sfa = new SeparateFlowAnalysis(sg, config);

                // Run and print
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    sfa.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = sfa.getDelayBound();
                    Num maxBacklog = sfa.getBacklogBound();
                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "SFA");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", Double.parseDouble(totalDelay.toString()));
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("SFA analysis failed");
                    e.printStackTrace();
                }
                break;

            case SFApp:
                // Configure
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.SEGR_PBOO);
                SeparateFlowAnalysis sfapp = new SeparateFlowAnalysis(sg, config);

                // Run and print
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    sfapp.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = sfapp.getDelayBound();
                    Num maxBacklog = sfapp.getBacklogBound();
                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "SFA++");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", Double.parseDouble(totalDelay.toString()));
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("SFA analysis failed");
                    e.printStackTrace();
                }
                break;

            case PMOO:
                // Configure
                config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_PMOO);
                PmooAnalysis pmoo = new PmooAnalysis(sg, config);

                // Run and print
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    pmoo.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = pmoo.getDelayBound();
                    Num maxBacklog = pmoo.getBacklogBound();
                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "PMOO");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", Double.parseDouble(totalDelay.toString()));
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("PMOO analysis failed");
                    e.printStackTrace();
                }
                break;

            case PMOOpp:
                // Configure
                config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_PMOO);
                PmooAnalysis pmoopp = new PmooAnalysis(sg, config);

                // Run and print
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    pmoopp.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = pmoopp.getDelayBound();
                    Num maxBacklog = pmoopp.getBacklogBound();
                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "PMOO++");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", Double.parseDouble(totalDelay.toString()));
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("PMOO++ analysis failed");
                    e.printStackTrace();
                }
                break;

            case TMA:
                // Configure
                config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_TM);
                TandemMatchingAnalysis tma = new TandemMatchingAnalysis(sg, config);

                // Run and write
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    tma.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = tma.getDelayBound();
                    Num maxBacklog = tma.getBacklogBound();
                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "TMA");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", Double.parseDouble(totalDelay.toString()));
                    result.put("max_backlog", Double.parseDouble(maxBacklog.toString()));
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", Double.parseDouble(totalDelay.toString()));
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("TMA analysis failed");
                    e.printStackTrace();
                }
                break;

            case TMApp:
                // Configure
                config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.setArrivalBoundMethod(AnalysisConfig.ArrivalBoundMethod.AGGR_TM);
                TandemMatchingAnalysis tmapp = new TandemMatchingAnalysis(sg, config);

                // Run and write
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    tmapp.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = tmapp.getDelayBound();
                    Num maxBacklog = tmapp.getBacklogBound();
                    double totalDelayDouble = Double.parseDouble(totalDelay.toString());
                    if (totalDelay.isInfinite())
                        totalDelayDouble = -1;
                    double maxBacklogDouble = Double.parseDouble(maxBacklog.toString());
                    if (maxBacklog.isInfinite())
                        maxBacklogDouble = -1;

                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "TMA++");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", totalDelayDouble);
                    result.put("max_backlog", maxBacklogDouble);
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", totalDelayDouble);
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("TMA++ analysis failed");
                    e.printStackTrace();
                }
                break;

            case LUDB:
                // Configure
                config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_OFF);
                FIFOTandemAnalysis ludb = new FIFOTandemAnalysis(sg, config);

                // Run and write
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    ludb.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = ludb.getDelayBound();
                    Num maxBacklog = ludb.getBacklogBound();
                    double totalDelayDouble = Double.parseDouble(totalDelay.toString());
                    if (totalDelay.isInfinite())
                        totalDelayDouble = -1;
                    double maxBacklogDouble = Double.parseDouble(maxBacklog.toString());
                    if (maxBacklog.isInfinite())
                        maxBacklogDouble = -1;

                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "LUDB");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", totalDelayDouble);
                    result.put("max_backlog", maxBacklogDouble);
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", totalDelayDouble);
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("LUDB analysis failed");
                    e.printStackTrace();
                }
                break;

            case LUDBpp:
                // Configure
                config.enforceMultiplexing(AnalysisConfig.MultiplexingEnforcement.GLOBAL_ARBITRARY);
                config.enforceMaxSC(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                config.enforceMaxScOutputRate(AnalysisConfig.MaxScEnforcement.GLOBALLY_ON);
                FIFOTandemAnalysis ludbpp = new FIFOTandemAnalysis(sg, config);

                // Run and write
                try {
                    // perform analysis and measure the execution time
                    long startTime = System.currentTimeMillis();
                    ludbpp.performAnalysis(foi);
                    long exec_time = System.currentTimeMillis() - startTime;

                    // Assign server names
                    JSONArray server_names = new JSONArray();
                    for (Server server : sg.getServers()) {
                        server_names.put(server.getId(), server.getAlias());
                    }

                    // Get server delay/backlog and flow information
                    Num totalDelay = ludbpp.getDelayBound();
                    Num maxBacklog = ludbpp.getBacklogBound();
                    double totalDelayDouble = Double.parseDouble(totalDelay.toString());
                    if (totalDelay.isInfinite())
                        totalDelayDouble = -1;
                    double maxBacklogDouble = Double.parseDouble(maxBacklog.toString());
                    if (maxBacklog.isInfinite())
                        maxBacklogDouble = -1;

                    JSONObject serverDelays = new JSONObject(JSONObject.NULL);
                    JSONObject serverBacklogs = new JSONObject(JSONObject.NULL);

                    JSONArray flow_path = new JSONArray();
                    JSONArray flow_cmu_delay = new JSONArray();

                    for (Server server : foi.getPath().getServers()) {
                        flow_path.put(server.getAlias());
                    }

                    // Writing result as json for easy interpretation
                    JSONObject result = new JSONObject();
                    result.put("name", netScript.getNetworkInfo().optString("name", ""));
                    result.put("flow_name", foi.getAlias());
                    result.put("server_names", server_names);
                    result.put("method", "LUDB++");
                    result.put("adjacency_matrix", netScript.getAdjacency());
                    result.put("num_servers", netScript.getJsonServers().length());
                    result.put("num_flows", netScript.getJsonFlows().length());
                    result.put("server_delays", serverDelays);
                    result.put("server_backlogs", serverBacklogs);
                    result.put("total_delay", totalDelayDouble);
                    result.put("max_backlog", maxBacklogDouble);
                    result.put("flow_paths", flow_path);
                    result.put("flow_cmu_delays", flow_cmu_delay);
                    result.put("flow_delays", totalDelayDouble);
                    result.put("exec_time", exec_time/1000.0);

                    System.out.println(result);
                } catch (Exception e) {
                    System.out.println("LUDB++ analysis failed");
                    e.printStackTrace();
                }
                break;

            default:
                break;
        }
    }


}
