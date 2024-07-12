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


if __name__ == '__main__':
    
    def read_small_boxes(mmif_obj, **parameters):
        alignment_annotations = mmif_obj.get_alignments(
            at_type1=AnnotationTypes.TimePoint, at_type2=AnnotationTypes.BoundingBox
        )
        bbox_annotations = mmif_obj.get_view_contains(AnnotationTypes.BoundingBox)
        tpoint_annotations = mmif_obj.get_view_contains(AnnotationTypes.TimePoint)
        
        # extract annotations from mmif => python dict
        box_dict = defaultdict(list)
        anno_id_to_annotation = {
            annotation.id: annotation
            for view_id, annotations in alignment_annotations.items()
            for annotation in annotations
        }
        if bbox_annotations:
            anno_id_to_annotation.update(
                {annotation.id: annotation for annotation in bbox_annotations.annotations}
            )
            
        if tpoint_annotations:
            anno_id_to_annotation.update(
                {annotation.id: annotation for annotation in tpoint_annotations.annotations}
            )

        for viewID, annotations in alignment_annotations.items():
            for annotation in annotations:
                if annotation.at_type == AnnotationTypes.Alignment:
                    timepoint_id = annotation.properties["source"]
                    box_id = annotation.properties["target"]
                    timepoint_anno = anno_id_to_annotation[timepoint_id].properties[
                        "timePoint"
                    ]
                    box_anno = anno_id_to_annotation[box_id].properties["coordinates"]
                    if (
                        anno_id_to_annotation[box_id].properties["label"]
                        == parameters["label"]
                    ):
                        box_dict[timepoint_anno].append(box_anno)

        # concatenate bounding boxes and add to mmif
        out_coords = make_big_boxes(box_dict)
        
        return mmif_obj


    @staticmethod
    def make_big_boxes(boundingbox_dictionary) -> Dict[float, List[List[float]]]:
        """Perform bounding-box concatenation

        ### params 
        - boundingbox_dictionary:
            a dict mapping bbox coords (val) to timepoints (key) 

        ### returns 
        a dictionary of the form 
        `{timepoint: [[top_left_x, top_left_y],...,[bot_right_x, bot_right_y]]}`
        """
        out = {}
        for timepoint, boxes in boundingbox_dictionary.items():
            current_min_x = None
            current_max_x = None
            current_min_y = None
            current_max_y = None

            for box in boxes:
                tl, br = box[0], box[3]
                current_min_x = (
                    tl[0]
                    if current_min_x is None or tl[0] < current_min_x
                    else current_min_x
                )
                current_max_x = (
                    br[0]
                    if current_max_x is None or br[0] > current_max_x
                    else current_max_x
                )

                current_min_y = (
                    tl[1]
                    if current_min_y is None or tl[1] < current_min_y
                    else current_min_y
                )
                current_max_y = (
                    br[1]
                    if current_max_y is None or br[1] > current_max_y
                    else current_max_y
                )

            a, b = current_min_x, current_min_y
            c, d = current_max_x, current_max_y
            out[timepoint] = [[a, b], [c, b], [a, d], [c, d]]
        return out
