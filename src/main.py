# Description: Command line tool to access SAIHU

from os.path import abspath, join, exists, dirname, basename, normpath
from os import makedirs
from argparse import ArgumentParser, Namespace

from saihu.interface import TSN_Analyzer


def parse_args() -> Namespace:
    arg_parser = ArgumentParser(
        prog="Saihu TSN analysis interface",
        description="Supports xTFA, DNC, and Panco for TSN analysis. "
        + "Priority of arguments are: "
        + "1. all > methods > tool > [individual tool] "
        + "2. markdown = json > export"
        + "\nIf no any output file is specified, exports file based on the input network file name",
    )

    arg_parser.add_argument(
        "networkFile", help="Network description file in .xml or .json"
    )
    arg_parser.add_argument(
        "-a", "--all", action="store_true", help="Execute all tools and methods"
    )
    arg_parser.add_argument(
        "-x", "--xtfa", nargs="+", help='Methods to use with xTFA. Can be "TFA"'
    )
    arg_parser.add_argument(
        "-d",
        "--dnc",
        nargs="+",
        help='Methods to use with DNC. Can be "TFA", "SFA", "PMOO", "TMA", or "LUDB"',
    )
    arg_parser.add_argument(
        "-p",
        "--panco",
        nargs="+",
        help='Methods to use with Panco. Can be "TFA", "SFA", "PLP", or "ELP"',
    )
    arg_parser.add_argument(
        "-t",
        "--tool",
        nargs="+",
        help="Tools to use to analyze with all their capabilities",
    )
    arg_parser.add_argument(
        "-m",
        "--method",
        nargs="+",
        help="Methods to use to analyze with all available tools",
    )
    arg_parser.add_argument(
        "--shaping",
        default="AUTO",
        help='Set shaping, default is "AUTO", can also be "ON" or "OFF"',
    )
    arg_parser.add_argument(
        "-e",
        "--export",
        help='Name of files as reports, for example "myNet" gives 2 files: "myNet_report.md" and "myNet_data.json"',
    )
    arg_parser.add_argument("--markdown", help="Name of markdown report file")
    arg_parser.add_argument("--json-out", help="Name of JSON report file")
    
    return arg_parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    temp_path = abspath(join(dirname(__file__), "temp"))
    if not exists(temp_path):
        makedirs(temp_path)

    analyzer = TSN_Analyzer(
        netfile=args.networkFile, temp_path=temp_path, shaping=args.shaping
    )

    # tool/method selection
    if args.all:
        analyzer.analyze_all()
    elif args.method is not None:
        analyzer.analyze_all(methods=args.method)
    elif args.tool is not None:
        input_tools = [tool.lower() for tool in args.tool]
        if "xtfa" in input_tools:
            analyzer.analyze_xtfa()
        if "dnc" in input_tools:
            analyzer.analyze_dnc()
        if "panco" in input_tools:
            analyzer.analyze_panco()
    else:
        if args.xtfa is not None:
            analyzer.analyze_xtfa(methods=args.xtfa)
        if args.dnc is not None:
            analyzer.analyze_dnc(methods=args.dnc)
        if args.panco is not None:
            analyzer.analyze_panco(methods=args.panco)

    # output
    if args.export is None and args.markdown is None and args.json_out is not None:
        analyzer.write_result_json(args.json_out)
    elif args.export is None and args.markdown is not None and args.json_out is None:
        analyzer.write_report_md(args.markdown)
    elif args.export is None:
        analyzer.export(
            basename(normpath(args.networkFile)).rsplit(".", 1)[0],
            args.json_out,
            args.markdown,
        )
    else:
        analyzer.export(args.export, args.json_out, args.markdown)
