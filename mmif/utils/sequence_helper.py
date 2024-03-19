"""
This module provides helpers for handling sequence labeling. Specifically, it provides

* a generalized label re-mapper for "post-binning" of labels
* conversion from a list of CLAMS annotations (with ``classification`` props) into a list of reals (scores by labels), can be combined with the label re-mapper mentioned above
* :py:meth:`mmif.utils.sequence_helper.smooth_short_intervals`: a simple smoothing algorithm by trimming "short" ridges or valleys

However, it DOES NOT provide 

* direct conversion between CLAMS annotations. For example, it does not directly handle stitching of ``TimePoint`` into ``TimeFrames``. 
* support for multi-class scenario, such as handling of _competing_ subsequence or overlapping labels.

Some functions can use optional external libraries (e.g., ``numpy``) for better performance. 
Hence, if you see a warning about missing optional packages, you might want to install them by running ``pip install mmif-python[seq]``.
"""

import importlib
import itertools
import warnings
from typing import List, Tuple, Dict, Union, Iterable, Callable

import mmif
from mmif import Annotation
from mmif.serialize.model import PRMTV_TYPES

for seq_dep in ['numpy']:
    try:
        importlib.__import__(seq_dep)
    except ImportError as e:
        warnings.warn(f"Optional package \"{e.name}\" is not found. "
                      f"You might want to install Sequence Helper dependencies "
                      f"by running `pip install mmif-python[seq]=={mmif.__version__}`")

NEG_LABEL = '-'


def smooth_short_intervals(scores: List[float],
                           min_pseq_size: int,
                           min_nseq_size: int,
                           min_score: float = 0.5,
                           ):
    """
    From a list of scores, a score threshold, and smoothing parameters, 
    identify the intervals of "positive" scores by smoothing the short 
    positive sequences ("pseq") and negative sequences ("nseq"). To decide 
    the positivity, first step is binarization of the scores by the 
    ``min_score`` threshold. Given ``Sr`` as "raw" input real-number scores 
    list, and ``min_score=0.5``, 
    
        .. code-block:: javascript
        
            Sr: [0.3, 0.6, 0.2, 0.8, 0.2, 0.9, 0.8, 0.5, 0.1, 0.5, 0.8, 0.3, 1.0, 0.7, 0.5, 0.5, 0.5, 0.8, 0.3, 0.6]


    
    the binarization is done by simply comparing each score with the threshold
    to get ``S`` list of binary scores
    
        .. code-block:: javascript
        
            1.0 :                                     |                      
            0.9 :                |                    |                      
            0.8 :          |     |  |           |     |              |       
            0.7 :          |     |  |           |     |  |           |       
            0.6 :    |     |     |  |           |     |  |           |     | 
            0.5 :----+-----+-----+--+--+-----+--+-----+--+--+--+--+--+-----+-
            0.4 :    |     |     |  |  |     |  |     |  |  |  |  |  |     | 
            0.3 : |  |     |     |  |  |     |  |  |  |  |  |  |  |  |  |  | 
            0.2 : |  |  |  |  |  |  |  |     |  |  |  |  |  |  |  |  |  |  | 
            0.1 : |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | 
            0.0 +------------------------------------------------------------
            raw :.3 .6 .2 .8 .2 .9 .8 .5 .1 .5 .8 .3 1. .7 .5 .5 .5 .8 .3 .6
             S  : 0  1  0  1  0  1  1  0  0  0  1  0  1  1  0  1  1  1  0  1 
            
    Note that these positive or negative sequences can be simpley singleton
    lists, meaning their size can be as small as 1. 
       
    Then, here are examples of smoothing a list of binary scores into 
    intervals:
    
    .. note::
       legends: 
       
       * ``t`` is unit index (e.g. time index)
       * ``S`` is the list of binary scores (zeros and ones)
       * ``I`` is the list of intervals after stitching
    
    #. with params ``min_pseq_size==1``, ``min_nseq_size==4``
        
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
           I: [0, 1--1--1--1--1--1--1--1--1--1--1--1, 0--0--0--0--0--0, 1]
        
        Explanation: ``min_nseq_size`` is used to smooth short sequences of 
        negative predictions. In this, zeros from t[7:10] are smoothed into 
        "one" I, while zeros from t[13:19] are kept as "zero" I. Note that 
        the "short" nseqs at the either ends (t[0:1]) are never smoothed.
        
    #. with params ``min_pseq_size==4``, ``min_nseq_size==2``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
           I: [0, 1--1--1--1--1--1, 0--0--0--0--0--0--0--0--0--0--0--0--0]
        
        Explanation: ``min_pseq_size`` is used to smooth short sequences of
        positive predictions. In this example, the pseqs of ones from both 
        t[10:13] and t[19:20] are smoothed. Note that the "short" pseqs at 
        the either ends (t[19:20]) are always smoothed.
                
    #. with params ``min_pseq_size==4``, ``min_nseq_size==4``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
           I: [0, 1--1--1--1--1--1--1--1--1--1--1--1--0--0--0--0--0--0--0]
        
        Explanation: When two threshold parameters are working together,
        the algorithm will prioritize the smoothing of the nseqs over the 
        smoothing of the pseqs. Thus, in this example, the nseq t[7:10] 
        is first smoothed "up" before the pseq t[10:13] is smoothed "down", 
        resulting in a long final I.
    
    #. with params ``min_pseq_size==4``, ``min_nseq_size==4``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
           I: [1--1--1--1--1--1--1, 0--0--0--0, 1--1--1--1--1--1--1--1--1]
        
        Explanation: Since smoothing of nseqs is prioritized, short pseqs at 
        the beginning or the end can be kept. 
    
    #. with params ``min_pseq_size==1``, ``min_nseq_size==1``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
           I: [0--0--0, 1--1--1--1, 0--0--0--0, 1--1--1--1, 0--0--0, 1--1]
        
        Explanation: When both width thresholds are set to 1, the algorithm
        works essentially in the "stitching" only mode.
                 
    :param scores: **SORTED** list of scores to be stitched. The score list
                   is assumed to be "exhaust" the entire time or space of 
                   the underlying document segment.
                   (Sorted by the start, and then by the end of anchors)
    :param min_score: minimum threshold to use to discard 
                      low-scored units (strictly less than)
    :param min_pseq_size: minimum size of a positive sequence not to be 
                          smoothed (greater or equal to)
    :param min_nseq_size: minimum size of a negative sequence not to be
                          smoothed (greater or equal to)
    :return: list of tuples of start(inclusive)/end(exclusive) indices
             of the "positive" sequences. Negative sequences (regardless of 
             their size) are not included in the output.
    """

    def trimmer(elems, min_width, target=False, keep_short_ends=False):
        """
        This will loop through a list of bools and convert short ``target`` 
        subsequences to ¬target (or not-target). A "short" subsequence is 
        defined by its size being strictly smaller than ``min_width``.
        When ``always_trim_ends``, the first and the last subsequences are 
        always converted to ¬target, regardless of their size.
        """
        try:
            assert min_width > 0
        except AssertionError:
            raise ValueError(f"minimum width threshold must be a positive number, but got {min_width}")
        group_gen = itertools.groupby(elems)
        new_membership = None
        last_membership = None
        last_membersnum = 0
        added = 0
        for i, (positivity, group) in enumerate(group_gen):
            membersnum = len(list(group))
            for _ in range(last_membersnum):  # won't be executed for the first group (last_membersnum=0)
                yield new_membership
                added += 1
            new_membership = not target
            # keep target as target if 
            # 1. the sequence is wide enough
            # 2. the sequence is at the beginning of the list and "keep_ends"
            if positivity == target and (membersnum >= min_width or (keep_short_ends and i == 0)):
                new_membership = target
            last_membersnum = membersnum
            last_membership = positivity
        # and finally 3. the sequence is at the final of the list and "keep_ends"
        new_membership = not target
        if last_membership == target and (last_membersnum >= min_width or keep_short_ends):
            new_membership = target
        for _ in range(last_membersnum):
            yield new_membership
            added += 1

    # first pass to smooth short gaps first
    pass1 = trimmer(
        map(lambda x: x >= min_score, scores),
        min_nseq_size, target=False, keep_short_ends=True)
    pass2 = trimmer(
        pass1, min_pseq_size, target=True, keep_short_ends=False)
    return _sequence_to_intervals(pass2)


def _sequence_to_intervals(seq: Iterable[bool]) -> List[Tuple[int, int]]:
    pos_ints = []
    cur = 0
    for positivity, members in itertools.groupby(seq):
        l = len(list(members))
        if positivity:
            pos_ints.append((cur, cur + l))
        cur += l
    return pos_ints


def validate_labelset(annotations: List[Annotation]) -> List[str]:
    """
    Simple check for a list of annotations to see if they have the same label set.
    
    :raise: AttributeError if an element in the input list doesn't have the ``labelset`` property
    :raise: ValueError if different ``labelset`` values are found
    :return: a list of the common ``labelset`` value (list of label names)
    """
    # first, grab the label set from the source annotations
    try:
        src_labels = set(annotations[0].get_property('labelset'))
    except KeyError:
        raise AttributeError("The annotation in the list doesn't have "
                             "'labelset' property. Are they annotated by"
                             "a classification task?")

    # and validate that all annotations have the same label set
    for a in annotations:
        if set(a.get_property('labelset')) != src_labels:
            raise ValueError("All annotations must have the same label set, "
                             f"but found {a.get_property('labelset')}, "
                             f"different from {src_labels}")
    return list(src_labels)


def build_label_remapper(src_labels: List[str], dst_labels: Dict[str, PRMTV_TYPES]) -> Dict[str, PRMTV_TYPES]:
    """
    Build a label remapper dictionary from source and destination labels.
    
    :param src_labels: a list of all labels on the source side
    :param dst_labels: a dict from source labels to destination labels. 
                       Source labels not in this dict will be remapped to a negative label (``-``).
    :return: a dict that exhaustively maps source labels to destination labels
    """
    if len(dst_labels) == 0:
        return dict(zip(src_labels, src_labels))
    else:
        return {**dst_labels, **dict((k, NEG_LABEL) for k in src_labels if k not in dst_labels)}


def build_score_lists(classifications: List[Dict], label_remapper: Dict,
                      score_remap_op: Callable[..., float] = max) \
        -> Tuple[Dict[str, int], "numpy.ndarray"]:  # pytype: disable=name-error

    """
    Build lists of scores indexed by the label names. 

    :param classifications: list of dictionaries of classification results, taken from input annotation objects
    :param label_remapper: a dictionary that maps source label names to destination label names (formerly "postbin")
    :param score_remap_op: a function to remap the scores from multiple source labels binned to a destination label
                            common choices are ``max``, ``min``, or ``sum``
    :return: 1. a dictionary that maps label names to their index in the score list
             2. 2-d numpy array of scores, of which rows are indexed by label map dict (first return value)
    """
    import numpy
    scores = {lbl: [] for lbl in label_remapper.values()}
    for c_idx, classification in enumerate(classifications):
        for src_label, src_score in classification.items():
            dst_label = label_remapper[src_label]
            if len(scores[dst_label]) == c_idx:  # means this is the first score for this label for this loop iter
                scores[dst_label].append(src_score)
            else:
                scores[dst_label][-1] = score_remap_op((scores[dst_label][-1], src_score))
    label_idx = {label: i for i, label in enumerate(scores.keys())}
    score_lists = list(scores.values())

    return label_idx, numpy.array(score_lists)


def _example_stitch_from_swt4(annotations: List[Annotation],
                              postbin: Dict[str, str],
                              min_timeframe_length: int = 2,
                              min_tp_score: float = 0.01,
                              min_tf_score: float = 0.5
                              ) -> List[Annotation]:
    """
    Reference implementation of the sequence stitching algorithm, replicating "stitcher" in 
    https://apps.clams.ai/swt-detection/v4.2/
    THIS FUNCTION IS NOT PART OF THE OFFICIAL API. USE AT YOUR OWN RISK.
    
    :param annotations: ``TimePoint`` annotations
    :param postbin: post-binning dict
    :param min_timeframe_length: required number of consecutive TP to be stitched into a TF
    :param min_tp_score: required score of TP to be considered as "positive" label
    :param min_tf_score: average score of TPs in a TF to make the TF significant (i.e., not to be discarded)
    :return: list of ``TimeFrame`` annotations
    """
    from mmif.vocabulary import AnnotationTypes
    # first, validate the input annotations
    src_labels = validate_labelset(annotations)
    # and build the label remapper
    label_remapper = build_label_remapper(src_labels, postbin)
    # then, build the score lists
    label_idx, scores = build_score_lists([a.get_property('classification') for a in annotations], 
                                          label_remapper=label_remapper, score_remap_op=sum)
    # and stitch the scores
    tf_annotations = []
    for label, lidx in label_idx.items():
        if label == NEG_LABEL:
            continue
        stitched = smooth_short_intervals(scores[lidx], min_timeframe_length, 1, min_tp_score)
        for positive_interval in stitched:
            tp_scores = scores[lidx][positive_interval[0]:positive_interval[1]]
            tf_score = tp_scores.mean()
            rep_idx = tp_scores.argmax() + positive_interval[0]
            if tf_score > min_tf_score:
                tf = Annotation()
                tf.at_type = AnnotationTypes.TimeFrame
                # tf.add_property('labelset', list(label_remapper.values()))
                tf.add_property('classification', {label: tf_score})
                tf.add_property('targets', [a.id for a in annotations[positive_interval[0]:positive_interval[1]]])
                tf.add_property('representatives', [annotations[rep_idx].id])
                tf_annotations.append(tf)
    return tf_annotations

if __name__ == '__main__':
    # EXPERIMENTAL code to use the reference re-implementation of the "stitcher" in swt 3.x and 4.x
    # THIS PART IS NOT PART OF THE OFFICIAL API. USE AT YOUR OWN RISK.
    import sys
    from mmif import Mmif
    from mmif.vocabulary import AnnotationTypes
    m = Mmif(open(sys.argv[1]).read())
    if len(sys.argv) > 2:
        tf_min_dur = int(sys.argv[2])
    else:
        tf_min_dur = 2
    anns = m.get_view_contains(AnnotationTypes.TimePoint).get_annotations(AnnotationTypes.TimePoint)
    example_postbin = {"B": "bars", "S": "slate", "S:H": "slate", "S:C": "slate", "S:D": "slate", "S:G": "slate", "I": "chyron", "N": "chyron", "Y": "chyron", "C": "credits",}
    tfs = _example_stitch_from_swt4(list(anns), example_postbin, min_timeframe_length=tf_min_dur)
    for tf in tfs:
        print(tf.serialize(pretty=True))
    