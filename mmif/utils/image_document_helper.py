"""
This app takes in a mmif which has been annotated with bounding boxes. 
For each timepoint that has a bounding box, the app produces a larger bounding box
using the outermost coordinates of the initial set. This produces a "concatenation"
effect, wherein the box is guaranteed to contain every other bounding box. This
is a useful bit of processing for downstream tasks.
"""
# ====================================|
# Import Statements
import argparse
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Union

# Imports needed for Clams and MMIF.
# Non-NLP Clams applications will require AnnotationTypes

from clams import ClamsApp, Restifier
from mmif import Mmif, View, Annotation, Document, AnnotationTypes, DocumentTypes

# For an NLP tool we need to import the LAPPS vocabulary items
from lapps.discriminators import Uri
# ====================================|

class BoundingboxConcatenation(ClamsApp):
    def __init__(self):
        super().__init__()

    def _appmetadata(self):
        # see `metadata.py`
        pass

    def _annotate(self, mmif: Union[str, dict, Mmif], **parameters) -> Mmif:
        # see https://sdk.clams.ai/autodoc/clams.app.html#clams.app.ClamsApp._annotate

        # initialize mmif view
        if not isinstance(mmif, Mmif):
            mmif_obj = Mmif(mmif)
        else:
            mmif_obj = mmif
        new_view = mmif_obj.new_view()
        config = self.get_configuration(**parameters)
        self.sign_view(new_view, config)
        new_view.new_contain(
            AnnotationTypes.BoundingBox
        ) 

        # get bounding-box alignment
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
                        anno_id_to_annotation[box_id].properties["boxType"]
                        == config["boxType"]
                    ):
                        box_dict[timepoint_anno].append(box_anno)

        # concatenate bounding boxes and add to mmif
        out_coords = self.make_boxes(box_dict)
        mmif_obj = self.annotate_boxes(mmif_obj, new_view, out_coords, **config)

        
        return mmif_obj

    @staticmethod
    def make_boxes(boundingbox_dictionary) -> Dict[float, List[List[float]]]:
        """Perform bounding-box concatenation

        ### params 
        - boundingbox_dictionary:
            a dict mapping bbox coords (val) to timepoints (key) 

        ## # returns 
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

    @staticmethod
    def annotate_boxes(mmif: Mmif, 
                       view: View, 
                       coords: Dict, 
                       **config) -> Mmif:
        """Perform mmif annotation with new coordinates.
        
        ### params
        - mmif   => Mmif object we are annotating
        - view   => View to which we are adding annotations
        - coords => Dict of individual bounding boxes for each timepoint

        ### returns
        Mmif object with new view annotations
        """
        for time_point, box_coords in coords.items():
            bb_annotation = view.new_annotation(AnnotationTypes.BoundingBox)
            tp_annotation = view.new_annotation(AnnotationTypes.TimePoint)
            tp_annotation.add_property("timeUnit", config["timeUnit"])
            tp_annotation.add_property("timePoint", time_point)

            bb_annotation.add_property("boxType", config["boxType"])

            bb_annotation.add_property("coordinates", box_coords)

            alignment_annotation = view.new_annotation(AnnotationTypes.Alignment)
            alignment_annotation.add_property("source", tp_annotation.id)
            alignment_annotation.add_property("target", bb_annotation.id)

        return mmif


def get_app():
    """
    This function effectively creates an instance of the app class, without any arguments passed in, meaning, any 
    external information such as initial app configuration should be set without using function arguments. The easiest
    way to do this is to set global variables before calling this. 
    """
    return BoundingboxConcatenation()
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", action="store", default="5000", help="set port to listen")
    parser.add_argument("--production", action="store_true", help="run gunicorn server")

    parsed_args = parser.parse_args()

    # create the app instance
    app = get_app()

    http_app = Restifier(app, port=int(parsed_args.port))
    # for running the application in production mode
    if parsed_args.production:
        http_app.serve_production()
    # development mode
    else:
        app.logger.setLevel(logging.DEBUG)
        http_app.run()
