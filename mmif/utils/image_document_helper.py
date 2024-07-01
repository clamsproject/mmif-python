from collections import defaultdict
from typing import Dict, List

from mmif import AnnotationTypes

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
