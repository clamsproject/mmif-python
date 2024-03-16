"""
This module provides helpers for handling sequence labeling. Specifically, it provides

* a generalized label re-mapper for "post-binning" of labels
* conversion from a list of CLAMS annotations (with ``classifications`` props) into a list of reals (scores by labels), can be combined with the label re-mapper mentioned above
* :py:meth:`mmif.utils.sequence_helper.smooth_short_intervals`: a simple smoothing algorithm by trimming "short" peaks or valleys

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
                           min_peak_width: int,
                           min_gap_width: int,
                           min_score: float = 0.5,
                           ):
    """
    From a list of scores and a score threshold, identify the intervals of
    "positive" scores by smoothing the short gaps and peaks. 
    
    Here are examples of smoothing a list of binary scores (threshold=0.5)
    into intervals:
    
    .. note::
       legends: 
       
       * ``t`` is unit index (e.g. time index)
       * ``S`` is the list of binary scores (zeros and ones)
       * ``I`` is the list of intervals after stitching
       
    #. with params ``min_peak_width==1``, ``min_gap_width==4``
        
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
           I: [0, 1--1--1--1--1--1--1--1--1--1--1--1, 0--0--0--0--0--0, 1]
        
        Explanation: ``min_gap_width`` is used to smooth negative 
        predictions. In this, zeros from t[7:10] are smoothed into "one" I, 
        while zeros from t[13:19] are kept as "zero" I. Note that the 
        "short" negatives at the either ends (t[0:1]) are never smoothed.
        
    #. with params ``min_peak_width==4``, ``min_gap_width==2``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
           I: [0, 1--1--1--1--1--1, 0--0--0--0--0--0--0--0--0--0--0--0--0]
        
        Explanation: ``min_peak_width`` is used to smooth short peaks of
        positive predictions. In this example, the peak of ones from both 
        t[10:13] and t[19:20] are smoothed. Note that the "short" positive 
        peaks at the either ends (t[19:20]) are always smoothed.
                
    #. with params ``min_peak_width==4``, ``min_gap_width==4``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1]
           I: [0, 1--1--1--1--1--1--1--1--1--1--1--1--0--0--0--0--0--0--0]
        
        Explanation: When two threshold parameters are working together,
        the algorithm will prioritize the smoothing of the gaps over the 
        smoothing of the peaks. Thus, in this example, the valley t[7:10] 
        is first smoothed "up" before the peak t[10:13] is smoothed "down", 
        resulting in a long final I.
    
    #. with params ``min_peak_width==4``, ``min_gap_width==4``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
           I: [1--1--1--1--1--1--1, 0--0--0--0, 1--1--1--1--1--1--1--1--1]
        
        Explanation: Since smoothing of gaps is prioritized, short peaks at 
        the beginning or the end can be kept. 
    
    #. with params ``min_peak_width==1``, ``min_gap_width==1``
    
        .. code-block:: javascript
        
           t: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
           S: [0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1]
           I: [0--0--0, 1--1--1--1, 0--0--0--0, 1--1--1--1, 0--0--0, 1--1]
        
        Explanation: When both width thresholds are set to 1, the algorithm
        works essentially in the "stitching" only mode.
                 
    :param scores: **SORTED** list of annotations to be stitched. 
                   Annotations in the list must "exhaust" the entire time 
                   or space of the underlying document.
                   (Sorted by the start, and then by the end of anchors)
    :param min_score: minimum threshold to use to discard 
                      low-scored units (strictly less than)
    :param min_peak_width: minimum width of a positive "peak". i.e.,
                           a peak must be wider or equal to this value to 
                           be included in the output.
    :param min_gap_width: minimum length of a negative "gap" to separate
                          two positive peaks. i.e., a gap must be wider or 
                          equal to this value to be considered as a 
                          negative gap.
    :return: list of tuples of start(inclusive)/end(exclusive) indices
             of the "positive" labels intervals. Negative-labeled
             intervals are not included in the output.
    """
    def trimmer(elems, min_width, target=False, keep_short_ends=False):
        """
        This will loop through a list of bools and convert short ``target`` 
        subsequences to ¬target (or not-target). A "short" subsequence is 
        defined by its length being strictly smaller than ``min_width``.
        When ``always_trim_ends``, the first and the last subsequences are 
        always converted to ¬target, regardless of their length.
        """
        try:
            assert min_width > 0
        except AssertionError:
            raise ValueError(f"minimum width threshold must be a positive number, but got {min_width}")
        group_gen = itertools.groupby(elems)
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
        min_gap_width, target=False, keep_short_ends=True)
    pass2 = trimmer(
        pass1, min_peak_width, target=True, keep_short_ends=False)
    return _sequence_to_intervals(pass2)
        
        
def _sequence_to_intervals(seq: Iterable[bool]) -> List[Tuple[int, int]]:
    
    pos_ints = []
    cur = 0
    for positivity, members in itertools.groupby(seq):
        l = len(list(members))
        if positivity:
            pos_ints.append((cur, cur+l))
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
        src_labels = [annotations[0].get_property('labelset')]
    except KeyError:
        raise AttributeError("The annotation in the list doesn't have "
                             "'labelset' property. Are they annotated by"
                             "a classification task?")

    # and validate that all annotations have the same label set
    for a in annotations:
        if a.get_property('labelset') != src_labels[0]:
            raise ValueError("All annotations must have the same label set, "
                             f"but found {a.get_property('labelset')}, "
                             f"different from {src_labels}")
    return src_labels


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


def build_score_lists(classificationses: List[Dict], label_remapper: Dict, 
                      score_remap_op: Callable[[float, float], float] =max, as_numpy: bool = False)\
        -> Tuple[Dict[str, int], Union[Dict[str, List[float]], "np.ndarray"]]:
    """
    Build lists of scores indexed by the label names. 

    :param classificationses: list of dictionaries of classifications results, taken from input annotation objects
    :param label_remapper: a dictionary that maps source label names to destination label names (formerly "postbin")
    :param score_remap_op: a function to remap the scores from multiple source labels binned to a destination label
                            common choices are ``max``, ``min``, or ``sum``
    :param as_numpy: whether to return the scores as a numpy array
    :return: 1. a dictionary that maps label names to their index in the score list
             2. a dictionary that maps label names to their list of scores 
                OR a numpy array of scores, of which rows are indexed by label map dict (first return value)
    """
    import numpy as np
    scores = {lbl: [] for lbl in label_remapper.values()}
    for c_idx, classifications in enumerate(classificationses):
        for src_label, src_score in classifications.items():
            dst_label = label_remapper[src_label]
            if len(scores[dst_label]) == c_idx:  # means this is the first score for this label for this loop iter
                scores[dst_label].append(src_score)
            else:
                scores[dst_label][-1] = score_remap_op((scores[dst_label][-1], src_score))
    label_idx = {label: i for i, label in enumerate(scores.keys())}

    return label_idx, np.array(list(scores.values())) if as_numpy else scores
