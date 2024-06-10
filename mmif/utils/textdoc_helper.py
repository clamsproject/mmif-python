import mmif


def slice_text(mmif_obj: mmif, start: int, end: int) -> str:
    sort_token_anns = mmif_obj.get_annotations_between(start, end)
    tokens_sliced = []
    for ann in sort_token_anns:
        tokens_sliced.append(ann.get_property('word'))
    return ' '.join(tokens_sliced)
