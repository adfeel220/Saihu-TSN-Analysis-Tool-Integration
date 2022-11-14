#!/usr/bin/env python3
from subprocess import check_output
from os.path import join

def dnc_exe(ifpath:str, dnc_jar_path:str="./", tools:list=["TFA"])->str:
    '''
    Execute dnc via .jar and input arguments

    param:
    ---------
    ifpath: the path to the network definition file
    '''

    args = ["-i", ifpath, "-t", ",".join(tools)]
    return check_output("java -jar " + join(dnc_jar_path, "dnc_analysis.jar") + ' ' + ' '.join(args), shell=True).decode("utf-8")


if __name__ == "__main__":
    print(dnc_exe("demo4.json"))
