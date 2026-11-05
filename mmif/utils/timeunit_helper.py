from collections.abc import Iterator
from datetime import datetime
from typing import cast


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


def iter_windows(
    start_ms: int,
    end_ms: int | None,
    window_ms: int,
    stride_ms: int | None = None,
) -> Iterator[tuple[int, int]]:
    """
    Iterates over time windows within a half-open interval.

    The final window is clipped to ``end_ms``. A stride smaller than the
    window creates overlapping windows; a larger stride leaves gaps. With
    ``end_ms`` of ``None`` the windows do not end, for callers that find the
    end of the interval while consuming them.

    :param start_ms: inclusive start of the interval
    :param end_ms: exclusive end of the interval, or ``None``
    :param window_ms: window length in milliseconds; must be positive
    :param stride_ms: distance between window starts; defaults to
        ``window_ms`` and must be positive
    :returns: integer-millisecond start/end pairs
    :raises ValueError: if the interval is reversed or a size is not positive
    """
    if end_ms is not None and end_ms < start_ms:
        raise ValueError("end_ms must be greater than or equal to start_ms")
    if window_ms <= 0:
        raise ValueError("window_ms must be positive")
    if stride_ms is None:
        stride_ms = window_ms
    elif stride_ms <= 0:
        raise ValueError("stride_ms must be positive")
    return _iter_windows(start_ms, end_ms, window_ms, stride_ms)


def _iter_windows(
    start_ms: int,
    end_ms: int | None,
    window_ms: int,
    stride_ms: int,
) -> Iterator[tuple[int, int]]:
    window_start_ms = start_ms
    while end_ms is None or window_start_ms < end_ms:
        window_end_ms = window_start_ms + window_ms
        if end_ms is not None:
            window_end_ms = min(window_end_ms, end_ms)
        yield window_start_ms, window_end_ms
        window_start_ms += stride_ms


def _isoformat_to_millisecond(isoformat: str) -> int:
    t = datetime.strptime(isoformat, '%H:%M:%S.%f')
    return int(1000 * (t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1000000))


def _millisecond_to_isoformat(millisecond: int | float) -> str:
    t = datetime.utcfromtimestamp(millisecond / 1000)
    return t.strftime('%H:%M:%S.%f')[:-3]


def _second_to_isoformat(second: float) -> str:
    t = datetime.utcfromtimestamp(second)
    return t.strftime('%H:%M:%S.%f')[:-3]  # python strftime will return "microsecond" with 6 digits


def convert(t: int | float | str, in_unit: str, out_unit: str, fps: float) -> int | float | str:
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
    t = cast(int | float, t)
    # s>s, ms>ms, f>f
    if in_unit == out_unit:
        return t
    elif out_unit == 'frame':
        # ms>f
        if in_unit == 'millisecond':
            return round(t / 1000 * fps)
        # s>f
        else:
            return round(t * fps)
    # s>(ms or i)
    elif in_unit == 'second':
        return round(t * 1000) if out_unit == 'millisecond' else _second_to_isoformat(t)
    # ms>(s or i)
    elif in_unit == 'millisecond':
        return t / 1000 if out_unit == 'second' else _millisecond_to_isoformat(t)
    # f>
    else:
        # f>s
        if out_unit == 'second':
            return t / fps
        # f>ms
        elif out_unit == 'millisecond': 
            return round(round(t / fps, 3) * 1000)
        # f>i
        else:
            return _second_to_isoformat(t / fps)
