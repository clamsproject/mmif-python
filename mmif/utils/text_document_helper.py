import warnings

from mmif.vocabulary import AnnotationTypes


def slice_text(mmif_obj, start: int, end: int, unit: str = "milliseconds") -> str:
    """
    .. deprecated:: 1.8.0
       Will be removed in 2.0.0. Use
       :meth:`~mmif.serialize.mmif.Mmif.get_annotations_between_time` with
       ``at_types=[AnnotationTypes.Token]`` instead.

    Extracts text from tokens within a specified time range, joining the
    tokens of every text document.

    :param mmif_obj: MMIF object to search for tokens
    :param start: start time point
    :param end: end time point
    :param unit: time unit for start and end parameters (default: "milliseconds")
    :return: space-separated string of token words found in the time range
    """
    warnings.warn('slice_text() is deprecated and will be removed in 2.0.0. '
                  'Use Mmif.get_annotations_between_time() instead.',
                  DeprecationWarning, stacklevel=2)
    tokens = mmif_obj.get_annotations_between_time(
        start, end, unit, at_types=[AnnotationTypes.Token])
    return ' '.join(token.get_property('text') for token in tokens)
