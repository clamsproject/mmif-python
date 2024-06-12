import mmif
from mmif import Annotation


def slice_text(mmif_obj, start: int, end: int, unit: str = "milliseconds") -> str:
    token_type = "http://vocab.lappsgrid.org/Token"
    anns_found = mmif_obj.get_annotations_between_time(start, end, unit)
    tokens_sliced = []
    for ann in anns_found:
        if ann.is_type(token_type):
            tokens_sliced.append(ann.get_property('word'))
    return ' '.join(tokens_sliced)
