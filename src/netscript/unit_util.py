from typing import Iterable

MAX_MULTIPLIER = "E"
MIN_MULTIPLIER = "a"

multipliers = {
    'a': 1e-18, # atto
    'f': 1e-15, # femto
    'p': 1e-12, # pico
    'n': 1e-9,  # nano
    'u': 1e-6,  # micro
    'm': 1e-3,  # milli
    '' : 1,
    'k': 1e3,   # kilo
    'M': 1e6,   # Mega
    'G': 1e9,   # Giga
    'T': 1e12,  # Tera
    'P': 1e15,  # Peta
    'E': 1e18   # Exa
}

multiplier_names = {
    'a': 'atto',
    'f': 'femto',
    'p': 'pico',
    'n': 'nano',
    'u': 'micro',
    'm': 'milli',
    '' : '',
    'k': 'kilo',
    'M': 'Mega',
    'G': 'Giga',
    'T': 'Tera',
    'P': 'Peta',
    'E': 'Exa'
}

time_units = {
    'h': 3600,  # hour
    'm': 60,    # minute
    's': 1      # second
}

data_units = {
    'b': 1,     # bit
    'B': 8      # Byte
}

def is_number(num_str:str) -> bool:
    '''
    Check if a string if a number
    '''
    if num_str is None:
        return False
    try:
        num = float(num_str)
    except Exception:
        return False
    else:
        return True

def is_time_unit(unitstr:str) -> bool:
    '''
    Determine if the unit is a time unit
    '''
    for tu in time_units:
        if unitstr.endswith(tu):
            return True
    return False

def is_data_unit(unitstr:str) -> bool:
    '''
    Determine if the unit is a data unit
    '''
    for tu in data_units:
        if unitstr.endswith(tu):
            return True
    return False

def is_rate_unit(unitstr:str) -> bool:
    '''
    Determine if the unit is a rate unit
    '''
    try:
        interpret_rate(unitstr[-3:])
        return True
    except ValueError:
        return False

def split_multiplier_unit(unitstr:str) -> tuple:
    '''
    split the multiplier and unit from the combination
    '''
    # time/data unit without multiplier
    if len(unitstr)==1:
        return '', unitstr
    # time/data unit
    if len(unitstr)==2:
        return unitstr[0], unitstr[1]
    # pure rate unit
    if len(unitstr)==3:
        return '', unitstr
    # rate unit with multiplier
    if len(unitstr)==4:
        return unitstr[0], unitstr[1:]
    
    return '', ''
        


def split_num_unit(numstr:str, default_unit:str='') -> tuple:
    '''
    split the number string with unit into number and unit

    Input:
    -----------
    numstr: [str] the number string with unit. e.g. "1.2ms" returns (1.2, "ms")
    default_unit: [str] the return value unit if the numstr is a number

    Output:
    -----------
    num: [float] the number in the string
    unit: [str] the unit attached to the number string
    '''
    if is_number(numstr):
        return float(numstr), default_unit

    for i in range(1, len(numstr)+1):
        if is_number(numstr[:-i]):
            return float(numstr[:-i]), numstr[-i:].replace(' ','')
    
    return None, None


def interpret_rate(unit:str) -> float:
    '''
    Check if it's a valid rate unit derived from time and data units.
    It must be 3 characters long as "{data unit}p{time unit}". For example "bps" stands for "bits-per-second"
    '''
    if len(unit) != 3:
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())}; "
                          +f"2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")

    if unit[0] not in data_units:
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())}; "
                          +f"2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")
    # data unit
    du = data_units[unit[0]]

    if unit[1] != 'p':
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())}; "
                        +f"2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")

    if unit[2] not in time_units:
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())}; "
                        +f"2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")
    # rate unit
    tu = time_units[unit[2]]

    return du/tu


def get_time_unit(unitstr:str, target_unit:str='s') -> float:
    '''
    Convert the time unit to the target unit
    '''
    if unitstr is None or target_unit is None:
        return 1

    tu = time_units[unitstr[-1]]
    mtp = multipliers[unitstr[-2]] if len(unitstr)>1 else 1
    orig_unit = tu*mtp

    tu = time_units[target_unit[-1]]
    mtp = multipliers[target_unit[-2]] if len(target_unit)>1 else 1
    trg = tu*mtp
    
    return orig_unit/trg


def parse_num_unit_time(numstr:str, target_unit:str='s') -> float:
    '''
    Parse the number string with unit to a number in target unit. Default converting into 'second'
    For example:
    >>> parse_num_unit_time("10ms", 's')
    0.01
    >>> parse_num_unit_time("60ks", 'm')
    1000
    >>> parse_num_unit_time("3us")
    3e-6

    Inputs:
    --------
    numstr: string with number and unit
    target_unit: (Optional) string specify a unit

    Outputs:
    --------
    target_number: the value in target unit
    '''
    
    if is_number(numstr):
        return float(numstr)

    if numstr is None:
        return None
    
    if target_unit is None:
        raise ValueError(f"No target unit is specified but the number string \"{numstr}\" is not a number")

    # parse multiplier and unit into seconds
    # tu: time unit, mpt: multiplier
    # parse time unit
    tu = numstr[-1]
    if tu not in time_units:
        raise ValueError(f"A time unit must end with either {list(time_units.keys())} but get \"{tu}\" in \"{numstr}\" instead.")
    tu = time_units[tu]

    # parse multiplier
    mtp = 1
    if not is_number(numstr[:-1]):
        mtp = numstr[-2]
        if mtp not in multipliers:
            raise ValueError(f"A multiplier must end with either {list(multipliers.keys())} but get \"{mtp}\" in \"{numstr}\" instead.")
        mtp = multipliers[mtp]


    # parse number
    orig_num = numstr[:-1] if mtp==1 else numstr[:-2]
    if not is_number(orig_num):
        raise ValueError(f"{numstr} is not a proper number with time unit")

    orig_num = float(orig_num) * mtp * tu

    
    # Parse target unit and multiplier
    # parse time unit
    tu = target_unit[-1]
    if tu not in time_units:
        raise ValueError(f"A time unit must end with either {list(time_units.keys())} but get \"{tu}\" in \"{target_unit}\" instead.")
    tu = time_units[tu]

    # parse multiplier
    mtp = 1
    if not is_number(target_unit[:-1]) and len(target_unit)>1:
        mtp = target_unit[-2]
        if mtp not in multipliers:
            raise ValueError(f"A multiplier must end with either {list(multipliers.keys())} but get \"{mtp}\" in \"{target_unit}\" instead.")
        mtp = multipliers[mtp]

    trg = tu*mtp

    return orig_num / trg


def get_data_unit(unitstr:str, target_unit:str='b') -> float:
    '''
    Convert the data unit to the target unit
    '''
    if unitstr is None or target_unit is None:
        return 1

    du = data_units[unitstr[-1]]
    mtp = multipliers[unitstr[-2]] if len(unitstr)>1 else 1
    orig_unit = du*mtp

    du = data_units[target_unit[-1]]
    mtp = multipliers[target_unit[-2]] if len(target_unit)>1 else 1
    trg = du*mtp
    
    return orig_unit/trg


def parse_num_unit_data(numstr:str, target_unit:str='b') -> float:
    '''
    Parse the number string with unit to a number in target unit. Default converting into 'bits'
    For example:
    >>> parse_num_unit_data("10kb", 'b')
    1000
    >>> parse_num_unit_data("80Mb", 'B')
    1e7
    >>> parse_num_unit_data("2GB")
    1.6e10

    Inputs:
    --------
    numstr: string with number and unit
    target_unit: (Optional) string specify a unit

    Outputs:
    --------
    target_number: the value in target unit
    '''
    
    if is_number(numstr):
        return float(numstr)
    
    if numstr is None:
        return None

    if target_unit is None:
        raise ValueError(f"No target unit is specified but the number string \"{numstr}\" is not a number")

    # parse multiplier and unit into seconds
    # du: data unit, mpt: multiplier
    # parse time unit
    du = numstr[-1]
    if du not in data_units:
        raise ValueError(f"A data unit must end with either {list(data_units.keys())} but get \"{du}\" in \"{numstr}\" instead.")
    du = data_units[du]

    # parse multiplier
    mtp = 1
    if not is_number(numstr[:-1]):
        mtp = numstr[-2]
        if mtp not in multipliers:
            raise ValueError(f"A multiplier must end with either {list(multipliers.keys())} but get \"{mtp}\" in \"{numstr}\" instead.")
        mtp = multipliers[mtp]

    if mtp < 1:
        raise ValueError(f"Data multiplier must >= 1, get \"{mtp}\" instead")

    # parse number
    orig_num = numstr[:-1] if mtp==1 else numstr[:-2]
    if not is_number(orig_num):
        raise ValueError(f"{numstr} is not a proper number with data unit")

    orig_num = float(orig_num) * mtp * du

    
    # Parse target unit and multiplier
    # parse data unit
    du = target_unit[-1]
    if du not in data_units:
        raise ValueError(f"A data unit must end with either {list(data_units.keys())} but get \"{du}\" in \"{target_unit}\" instead.")
    du = data_units[du]

    # parse multiplier
    mtp = 1
    if not is_number(target_unit[:-1]) and len(target_unit)>1:
        mtp = target_unit[-2]
        if mtp not in multipliers:
            raise ValueError(f"A multiplier must end with either {list(multipliers.keys())} but get \"{mtp}\" in \"{target_unit}\" instead.")
        mtp = multipliers[mtp]
    if mtp < 1:
        raise ValueError(f"Data multiplier must >= 1, get \"{mtp}\" instead")

    trg = float(du*mtp)

    return orig_num / trg


def get_rate_unit(unitstr:str, target_unit:str='bps') -> float:
    '''
    Convert the rate unit to the target unit
    '''
    if unitstr is None or target_unit is None:
        return 1

    ru = interpret_rate(unitstr[-3:])
    mtp = multipliers[unitstr[-4]] if len(unitstr)>3 else 1
    orig_unit = ru*mtp

    ru = interpret_rate(target_unit[-3:])
    mtp = multipliers[target_unit[-4]] if len(target_unit)>3 else 1
    trg = ru*mtp
    
    return orig_unit/trg



def parse_num_unit_rate(numstr:str, target_unit:str='bps') -> int:
    '''
    Parse the number string with unit to a number in target unit. Default converting into 'bps'
    For example:
    >>> parse_num_unit_rate("1kbps", 'bps')
    1000
    >>> parse_num_unit_rate("8MBps", 'bpm')
    6e7
    >>> parse_num_unit_rate("2kBps")
    1.6e4

    Inputs:
    --------
    numstr: string with number and unit
    target_unit: (Optional) string specify a unit

    Outputs:
    --------
    target_number: the value in target unit
    '''
    
    if is_number(numstr):
        return float(numstr)

    if numstr is None:
        return None

    if target_unit is None:
        raise ValueError(f"No target unit is specified but the number string \"{numstr}\" is not a number")

    # parse multiplier and unit into seconds
    # ru: rate unit, tu: time unit, du: data unit, mpt: multiplier
    
    ru = numstr[-3:]
    # parse rate unit
    ru = interpret_rate(ru)

    # parse multiplier
    mtp = 1
    if not is_number(numstr[:-3]):
        mtp = numstr[-4]
        if mtp not in multipliers:
            raise ValueError(f"A multiplier must end with either {list(multipliers.keys())} but get \"{mtp}\" in \"{numstr}\" instead.")
        mtp = multipliers[mtp]


    # parse number
    orig_num = numstr[:-3] if mtp==1 else numstr[:-4]
    if not is_number(orig_num):
        raise ValueError(f"{numstr} is not a proper number with rate unit")

    orig_num = float(orig_num) * mtp * ru

    
    # Parse target unit and multiplier
    # parse rate unit
    ru = interpret_rate(target_unit[-3:])

    # parse multiplier
    mtp = 1
    if not is_number(target_unit[:-3]) and len(target_unit)>3:
        mtp = target_unit[-4]
        if mtp not in multipliers:
            raise ValueError(f"A multiplier must end with either {list(multipliers.keys())} but get \"{mtp}\" in \"{target_unit}\" instead.")
        mtp = multipliers[mtp]

    trg = float(ru*mtp)

    return orig_num / trg


def decide_multiplier(x:float)->tuple:
    '''
    Choose the best multiplier from input number
    Example:
    >>> decide_multiplier(1000)
    1.0, 'k'
    >>> decide_multiplier(0.01)
    10.0, 'm'

    Input:
    --------
    x : the number you want to decide

    Outputs:
    --------
    new_x : the new value that should be used with the assigned multiplier
    mul : the assigned multiplier
    '''
    if x is None:
        return None, None
    if x == 0:
        return x, ''

    for mul_ch, mul_num in multipliers.items():
        if x/mul_num < 1e3 and x/mul_num >= 1:
            return x/mul_num, mul_ch
    # Handle special case, larger than biggest or smaller than smallest
    max_mul_ch = max(multipliers, key=multipliers.get)
    if x/multipliers[max_mul_ch] >= 1e3:
        return x/multipliers[max_mul_ch], max_mul_ch
    
    min_mul_ch = min(multipliers, key=multipliers.get)
    if x/multipliers[min_mul_ch] < 1.0:
        return x/multipliers[min_mul_ch], min_mul_ch

    # None of above cases fit, best with no multiplier
    return x, ''


def decide_min_multiplier(x:Iterable, unit:str=None)->str:
    '''
    Determine the minimum multiplier among a list of values
    Example:
    >>> decide_min_multiplier([10, 0.1, 200])
    'm'
    >>> decide_min_multiplier([2e3, 5e3, 1e8])
    'k'

    Input:
    -------
    x : [Iterable] an interable where all elements are numbers
    unit : [str] the unit where the entries of x are written in.
           If unit is not None, then the output minimum multiplier will return the multiplier with respect to the unit without original multiplier

    Output:
    -------
    min_mul : the minimum suitable multiplier for all elements in x
    '''
    if all([elem is None for elem in x]):
        return ''
    min_mul = MAX_MULTIPLIER
    for elem in x:
        if elem is None:
            continue
        if unit is not None:
            orig_mul, orig_unit = split_multiplier_unit(unit)
            if is_time_unit(unit):
                elem = parse_num_unit_time(f"{elem}{unit}", target_unit=orig_unit)
            if is_data_unit(unit):
                elem = parse_num_unit_data(f"{elem}{unit}", target_unit=orig_unit)
            if is_rate_unit(unit):
                elem = parse_num_unit_rate(f"{elem}{unit}", target_unit=orig_unit)

        new_num, mul = decide_multiplier(elem)
        if multipliers[mul] < multipliers[min_mul]:
            min_mul = mul

    return min_mul

