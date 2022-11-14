import warnings

## Helper functions
def var_set_name(name: str, *indices) -> str:
    '''
    Format the variable name. For example,
    base name: 'x', indices are 1 and 2, then the name is set as 'x_1,2'
    '''
    name += '_'
    for idx in indices:
        name += str(idx) + ','

    return name[:-1]

def var_get_name(name: str) -> tuple:
    '''
    Obtain the base name and indices from the formated variable name. For example,
    "x_1,2" -> ('x', [1,2])
    '''
    base_name, indices = name.split('_')
    indices = indices.split(',')
    indices = [int(idx) for idx in indices]
    
    return base_name, indices


def display_foi_delay(delays:list, flows:list) -> None:
    '''
    Print the delays along flow 

    INPUT:
    delays: list of floats represent delays experienced at each server. len(delays) == (# of servers)
    flows: list of flow objects, each flow object is a dict. Should at least contains "path" attribute to define flow paths
    '''
    for fl_idx, fl in enumerate(flows):
        path = fl["path"]
        print(f"Flow {fl_idx}: {path}")
        total_delay = 0
        for ser_id in path:
            print(f"\td_{ser_id} = {delays[ser_id]}")
            total_delay += delays[ser_id]
        print(f"Total = {total_delay}\n")


def warning_override(message, category = UserWarning, filename = '', lineno = -1, file=None, line=None):
    '''
    To override warnings.showwarning for simpler warning display
    '''
    print("Warning:", message, category)
