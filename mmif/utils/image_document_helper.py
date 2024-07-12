from collections import defaultdict
from typing import Dict, List, Tuple

from mmif import AnnotationTypes, Mmif, Annotation

Point = Tuple[int, int]
Box = Tuple[Point, Point]


def _find_relevant_small_boxes(mmif: Mmif):
    """
    Finds all ``BoundingBox` annotations that are aligned with a ``TimePoint`` annotation. 
    
    :return: dict from TP annotation to a list of BB annotations
    """
    tp_to_bb = defaultdict(list)
    for view in mmif.get_all_views_contain(AnnotationTypes.TimePoint):
        for tp in view.get_annotations(AnnotationTypes.TimePoint):
            for aligned in tp.get_all_aligned():
                if aligned.at_type == AnnotationTypes.BoundingBox:
                    tp_to_bb[tp].append(aligned)
    return tp_to_bb


def _normalize_box_coords(coords) -> Box:
    """
    Because some apps use four-point, some use two-point bounding boxes, we need to normalize them.
    Normalization is done as two-point representation, i.e., top-left and bottom-right corners.
    Note that a coordinate is always a tuple of two integers: the x and y coordinates.
    """
    if len(coords) == 2:
        return coords
    elif len(coords) == 4:
        top = min(coor[1] for coor in coords)
        left = min(coor[0] for coor in coords)
        bottom = max(coor[1] for coor in coords)
        right = max(coor[0] for coor in coords)
        return (left, top), (right, bottom)


def concatenate_boxes(boxes: List[Box]) -> Box:
    """
    Concatenates a list of bounding boxes into a single bounding box.
    Each "box" is a tuple of two points: the top-left and bottom-right corners, 
    and each "point" is a tuple of two integers: the x and y coordinates.
    
    :param boxes: list of bounding boxes
    :return: a single bounding box
    """
    normalized_boxes = [_normalize_box_coords(box) for box in boxes]
    tl = (min([box[0][0] for box in normalized_boxes]), min([box[0][1] for box in normalized_boxes]))
    br = (max([box[1][0] for box in normalized_boxes]), max([box[1][1] for box in normalized_boxes]))
    return tl, br
        
        
def concatenate_timestamped_boundingboxes(mmif: Mmif) -> Dict[Annotation, Box]:
    """
    Concatenates bounding boxes that are aligned with the same time point.
    
    :param mmif: MMIF object with ``BoundingBox`` and ``TimePoint`` annotations
    :return: a dict from ``TimePoint`` annotation to a pair of coordinates to represent a concatenated "big" box 
             in two-point representation (top-left and bottom-right corners)
    """
    concated = {}
    tp_to_bb = _find_relevant_small_boxes(mmif)
    for tp, bbs in tp_to_bb.items():
        if len(bbs) > 1:
            concated[tp] = concatenate_boxes([bb.get_property("coordinates") for bb in bbs])
    return concated
