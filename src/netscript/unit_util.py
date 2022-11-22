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
    except ValueError as e:
        return False
    else:
        return True

def get_rate_unit(unit:str) -> float:
    '''
    Check if it's a valid rate unit derived from time and data units
    '''
    if len(unit) != 3:
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())};\
                          2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")

    if unit[0] not in data_units:
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())};\
                          2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")
    du = data_units[unit[0]]

    if unit[1] != 'p':
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())};\
                          2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")


    if unit[2] not in time_units:
        raise ValueError(f"\"{unit}\" is not a valid rate unit, the format must be 3 parts. 1st data unit must be either {list(data_units.keys())};\
                          2nd must be \"p\", stands for \"per\"; 3rd time unit must be either {list(time_units.keys())}")
    tu = time_units[unit[2]]

    return du/tu


def parse_num_unit_time(numstr:str, target_unit:str='s') -> float:
    '''
    Parse the number string with unit to a number in target unit.
    For example:
    >>> numstr = "10ms"
    >>> parse_unit_time(numstr, 's')
    0.01

    Inputs:
    --------
    numstr: string with number and unit
    target_unit: string specify a unit
    '''
    
    if is_number(numstr):
        return float(numstr)

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
        raise ValueError(f"{numstr} is not a number")

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


def parse_num_unit_data(numstr:str, target_unit:str='b') -> float:
    '''
    Parse the number string with unit to a number in target unit.
    For example:
    >>> numstr = "10kb"
    >>> parse_unit_data(numstr, 'b')
    1000

    Inputs:
    --------
    numstr: string with number and unit
    target_unit: string specify a unit
    '''
    
    if is_number(numstr):
        return int(numstr)

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
        raise ValueError(f"{numstr} is not a number")

    orig_num = int(orig_num) * mtp * du

    
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

    trg = int(du*mtp)

    return orig_num / trg


def parse_num_unit_rate(numstr:str, target_unit:str='bps') -> int:
    '''
    Parse the number string with unit to a number in target unit.
    For example:
    >>> numstr = "1kbps"
    >>> parse_unit_rate(numstr, 'bps')
    1000

    Inputs:
    --------
    numstr: string with number and unit
    target_unit: string specify a unit
    '''
    
    if is_number(numstr):
        return float(numstr)

    # parse multiplier and unit into seconds
    # ru: rate unit, tu: time unit, du: data unit, mpt: multiplier
    
    ru = numstr[-3:]
    # parse rate unit
    ru = get_rate_unit(ru)

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
        raise ValueError(f"{numstr} is not a number")

    orig_num = float(orig_num) * mtp * ru

    
    # Parse target unit and multiplier
    # parse rate unit
    ru = get_rate_unit(target_unit[-3:])

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
    '''
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


def decide_min_multiplier(x:Iterable)->str:
    '''
    Determine the minimum multiplier among a list of values
    '''
    min_mul = MAX_MULTIPLIER
    for elem in x:
        new_num, mul = decide_multiplier(elem)
        if multipliers[mul] < multipliers[min_mul]:
            min_mul = mul

    return min_mul


if __name__ == "__main__":
    # print(parse_num_unit_rate("123"))
    # print(parse_num_unit_rate("100kbps", 'bps'))
    # print(parse_num_unit_rate("1GBps", 'bps'))
    print(decide_multiplier(1e5))
    print(decide_multiplier(1e10))
    print(decide_multiplier(1e-5))
    print(decide_multiplier(1e3))
    print(decide_multiplier(1e18))
    print(decide_multiplier(1e-18))
    print(decide_multiplier(1e24))
    print(decide_multiplier(1e-20))
    print(decide_multiplier(2))
