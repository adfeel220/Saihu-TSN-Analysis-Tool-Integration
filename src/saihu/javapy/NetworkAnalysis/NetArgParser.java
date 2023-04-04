package NetworkAnalysis;

import NetworkAnalysis.NetworkAnalysis.AnalysisTool;

import java.util.ArrayList;

import org.apache.commons.cli.*;


public class NetArgParser {

    /* Variables */
    private static String inFilePath;
    private static String outFilePath;
    private static ArrayList<AnalysisTool> tools = new ArrayList<AnalysisTool>();
    private static boolean printHelp = false;

    /* Methods */

    public NetArgParser() {}
    public NetArgParser(String[] args) {
        printHelp = parseArgument(args);
    }

    public String getInFilePath() { return inFilePath; }
    public String getOutFilePath() { return outFilePath; }
    public ArrayList<AnalysisTool> getTools() { return tools; }
    public boolean isPrintHelp() { return printHelp; }

    public static void main(String[] args) {
        parseArgument(args);
        System.out.println(inFilePath);
        System.out.println(outFilePath);
        for (AnalysisTool t : tools) {
            System.out.println(t.toString());
        }
    }

    public static boolean parseArgument(String[] args) {
        CommandLine commandLine;
        Options options = new Options();

        Option inputFileArg = Option.builder("i")
                .argName("file")
                .hasArg()
                .required(true)
                .desc("Path to input file")
                .longOpt("input")
                .build();

        Option outputFileArg = Option.builder("o")
                .argName("file")
                .hasArg()
                .required(false)
                .desc("Path to output file. Print to console if no output file specified")
                .longOpt("output")
                .build();

        Option methodArg = Option.builder("t")
                .argName("toolName")
                .hasArg()
                .required(false)
                .desc("Name of analysis tool: TFA, SFA, PMOO, TMA with/without ++. Separate multiple methods by comma")
                .longOpt("tool")
                .build();


        /* Create the help interface */
        Option help = Option.builder("h")
                .hasArg(false)
                .required(false)
                .desc("Print this help")
                .longOpt("help")
                .build();

        CommandLineParser parser = new DefaultParser();
        options.addOption(inputFileArg);
        options.addOption(outputFileArg);
        options.addOption(methodArg);
        options.addOption(help);

        // Ignore all other arguments if help is in arguments
        if (checkHasHelp(args, options)) return true;

        // Parsing the options
        try {
            commandLine = parser.parse(options, args);
            inFilePath  = commandLine.getOptionValue(inputFileArg);
            outFilePath = commandLine.getOptionValue(outputFileArg, "");
            String[] toolStrs = commandLine.getOptionValue(methodArg, "TFA").split(",");

            for (int i=0; i<toolStrs.length; i++) {
                String toolStr = toolStrs[i];
                try {
                    if (toolStr.endsWith("++")) {
                        toolStr = toolStr.replace('+', 'p');
                    }
                    tools.add(AnalysisTool.valueOf(toolStr));
                } catch (Exception e) {
                    System.out.format("\"%s\" is not a valid method\n", toolStr);
                    e.printStackTrace();
                }
            }


        } catch (Exception e) {
            e.printStackTrace();
        }

        return false;
    }


    /* Check if "help" is within arguments */
    private static boolean checkHasHelp(String[] args, Options options) {
        Option helpOption = Option.builder("h")
                .hasArg(false)
                .required(false)
                .longOpt("help")
                .build();
        Options ops = new Options().addOption(helpOption);

        try {
            CommandLineParser parser = new DefaultParser();
            CommandLine cmdLine = parser.parse(ops, args, true);
            if (cmdLine.hasOption(helpOption)) {
                HelpFormatter helpFormatter = new HelpFormatter();
                helpFormatter.printHelp("Network Analysis Tool", options);
                return true;
            }
            return false;

        } catch (Exception e) {
            e.printStackTrace();
        }
        return false;
    }
}
