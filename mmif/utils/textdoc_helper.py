import mmif


def slice_text(mmif_obj, start: int, end: int) -> str:
    sort_token_anns = mmif_obj.get_annotations_between_time(start, end)
    tokens_sliced = []
    for ann in sort_token_anns:
        tokens_sliced.append(ann.get_property('text'))  # FIXME: Sometimes the string attribute "word" is used for getting property value
    return ' '.join(tokens_sliced)
