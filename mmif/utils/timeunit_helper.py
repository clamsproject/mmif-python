from datetime import datetime
from typing import Union


UNIT_NORMALIZATION = {
    'm': 'millisecond',
    'ms': 'millisecond',
    'msec': 'millisecond',
    'millisecond': 'millisecond',
    'milliseconds': 'millisecond',
    's': 'second',
    'se': 'second',
    'sec': 'second',
    'second': 'second',
    'seconds': 'second',
    'f': 'frame',
    'fr': 'frame',
    'frame': 'frame',
    'frames': 'frame',
    'i': 'isoformat',
    'iso': 'isoformat',
    'isoformat': 'isoformat',
}


def _isoformat_to_millisecond(isoformat: str) -> int:
    t = datetime.strptime(isoformat, '%H:%M:%S.%f')
    return int(1000 * (t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1000000))


def _millisecond_to_isoformat(millisecond: int) -> str:
    t = datetime.utcfromtimestamp(millisecond / 1000)
    return t.strftime('%H:%M:%S.%f')[:-3]


def _second_to_isoformat(second: float) -> str:
    t = datetime.utcfromtimestamp(second)
    return t.strftime('%H:%M:%S.%f')[:-3]  # python strftime will return "microsecond" with 6 digits


def convert(t: Union[int, float, str], in_unit: str, out_unit: str, fps: float) -> Union[int, float, str]:
    """
    Converts time from one unit to another. Works with ``frames``, ``seconds``, ``milliseconds``.

    :param t: time value to convert
    :param in_unit: input time unit, one of ``frames``, ``seconds``, ``milliseconds``
    :param out_unit: output time unit, one of ``frames``, ``seconds``, ``milliseconds``
    :param fps: frames per second
    :return: converted time value
    """
    try:
        in_unit = UNIT_NORMALIZATION[in_unit]
    except KeyError:
        raise ValueError(f"Not supported time unit: {in_unit}")
    try:
        out_unit = UNIT_NORMALIZATION[out_unit]
    except KeyError:
        raise ValueError(f"Not supported time unit: {out_unit}")
    if in_unit == 'isoformat':
        if isinstance(t, str):
            t = _isoformat_to_millisecond(t)
            in_unit = 'millisecond'
        else:
            raise ValueError(f"Invalid time format: ISO format string expected, but got {t} of type {type(t)}")
    # s>s, ms>ms, f>f
    if in_unit == out_unit:
        return t
    elif out_unit == 'frame':
        # ms>f
        if 'millisecond' == in_unit:
            return int(t / 1000 * fps)
        # s>f
        elif 'second' == in_unit:
            return int(t * fps)
    # s>(ms or i)
    elif in_unit == 'second':
        return int(t * 1000) if out_unit == 'millisecond' else _second_to_isoformat(t)
    # ms>(s or i)
    elif in_unit == 'millisecond':
        return t / 1000 if out_unit == 'second' else _millisecond_to_isoformat(t)
    # f>ms, f>s
    else:
        return (t / fps) if out_unit == 'second' else (round(t / fps, 3) * 1000)  # pytype: disable=bad-return-type

