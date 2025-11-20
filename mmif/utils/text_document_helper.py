import mmif
from mmif import Annotation
from mmif.vocabulary import AnnotationTypes


def slice_text(mmif_obj, start: int, end: int, unit: str = "milliseconds") -> str:
    """
    Extracts text from tokens within a specified time range.

    :param mmif_obj: MMIF object to search for tokens
    :param start: start time point
    :param end: end time point
    :param unit: time unit for start and end parameters (default: "milliseconds")
    :return: space-separated string of token words found in the time range
    """
    token_type = AnnotationTypes.Token
    anns_found = mmif_obj.get_annotations_between_time(start, end, unit)
    tokens_sliced = []
    for ann in anns_found:
        if ann.is_type(token_type):
            tokens_sliced.append(ann.get_property('word'))
    return ' '.join(tokens_sliced)
