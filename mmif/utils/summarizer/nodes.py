import json
from collections.abc import MutableMapping

from typing import Any

from mmif.serialize.annotation import canonicalize_prop_name
from mmif.serialize.model import MmifObject
from mmif.utils.summarizer import config


class NodeProperties(MutableMapping):

    """Read-through view of an annotation's properties for use in a Node. Reads
    resolve, in order, local writes made by the summarizer, the annotation's own
    properties (deprecated spellings included, e.g. `word` for `text`), and the
    view-level defaults for the annotation's type in the view's `contains`
    metadata. Values are plain JSON types, as they would be after a serialization
    round trip. Writes never reach the annotation; they are kept locally so that
    summarizing leaves the loaded MMIF unchanged.

    Note on the alternative: the SDK could instead copy `contains` defaults into
    each annotation's `.properties` at deserialization and rely on
    `Mmif.factor_out_shared_properties` to lift them back out on serialization.
    That round trip is not shape-preserving when a type has a single annotation
    in the view, when the key is non-factorable (`start`, `source`, `target`, ...),
    or when another annotation of the type overrides the default, so the SDK
    keeps defaults out of `.properties` and this class resolves them here."""

    def __init__(self, annotation, view):
        self.annotation = annotation
        contains = {} if view is None else view.metadata.contains.get(annotation.at_type, {})
        self.defaults = {canonicalize_prop_name(annotation.at_type, k): v for k, v in contains.items()}
        self.local = {}

    @staticmethod
    def _as_json(value):
        return json.loads(str(value)) if isinstance(value, MmifObject) else value

    def __getitem__(self, key):
        if key in self.local:
            return self.local[key]
        if key in self.annotation.properties:
            return self._as_json(self.annotation.properties[key])
        return self.defaults[canonicalize_prop_name(self.annotation.at_type, key)]

    def __setitem__(self, key, value):
        self.local[key] = value

    def __delitem__(self, key):
        del self.local[key]

    def __iter__(self):
        seen = set()
        for key in (*self.annotation.properties, *self.defaults, *self.local):
            if key not in seen:
                seen.add(key)
                yield key

    def __len__(self):
        return sum(1 for _ in self)


class Node(object):

    def __init__(self, graph, view, annotation):
        self.graph = graph
        self.view = view
        self.view_id = None if self.view is None else self.view.id
        self.annotation = annotation
        # copy some information from the Annotation
        self.at_type = annotation.at_type
        self.identifier = annotation.id
        self.properties = NodeProperties(annotation, view)
        # get the document from the view or the properties
        self.document = self._get_document()
        # The targets property contains a list of annotations or documents that
        # the node content points to. This includes the document the annotation
        # points to as well as the alignment from a token or text document to a
        # bounding box or time frame (which is added later).
        # TODO: the above does not seem to be true since there is no evidence of
        # data from alignments being added.
        self.targets = [] if self.document is None else [self.document]
        self.anchors = {}
        self.add_local_anchors()
        self.add_anchors_from_targets()

    def __str__(self):
        anchor = ''
        if self.at_type.shortname == config.TOKEN:
            anchor = " %s:%s '%s'" % (self.properties['start'],
                                      self.properties['end'],
                                      self.properties.get('text','').replace('\n', '\\n'))
        return "<%s %s%s>" % (self.at_type.shortname, self.identifier, anchor)

    def add_local_anchors(self):
        """Get the anchors that you can get from the annotation itself, which 
        includes the start and end offsets, the coordinates, the timePoint of
        a BoundingBox and any annotation with targets."""
        props = self.properties
        attype = self.annotation.at_type.shortname
        if 'start' in props and 'end' in props:
            # TimeFrame is the only non-character based interval so this simple
            # if-then-else should work
            if attype == config.TIME_FRAME:
                self.anchors['text-offsets'] = (props['start'], props['end'])
            else:
                self.anchors['time-offsets'] = (props['start'], props['end'])
        if 'coordinates' in props:
            self.anchors['coordinates'] = props['coordinates']
        if 'timePoint' in props:
            self.anchors['time-point'] = props['timePoint']
        if 'targets' in props:
            self.anchors['targets'] = props['targets']

    def add_anchors_from_targets(self):
        """Get start and end offsets or timePoints from the targets and add them to
        the anchors, but only if there were no anchors on the node already. This has
        two cases: one for TimeFrames and one for text intervals."""
        props = self.properties
        attype = self.annotation.at_type.shortname
        if 'targets' in props:
            try:
                t1 = self.graph.nodes[props['targets'][0]]
                t2 = self.graph.nodes[props['targets'][-1]]
                if attype == config.TIME_FRAME:
                    if not 'time-offsets' in props:
                        self.anchors['time-offsets'] = (
                            t1.properties['timePoint'], t2.properties['timePoint'])
                else:
                    if not 'text-offsets' in props:
                        self.anchors['text-offsets'] = (
                            t1.properties['start'], t2.properties['end'])
            except IndexError:
                print(f'WARNING: Unexpected empty target list for {self.identifier}')

    def add_anchors_from_alignment(self, target: Any, debug=False):
        if target is None:
            return
        source_attype = self.at_type.shortname
        target_attype = target.at_type.shortname
        if debug:
            print('\n@ DEBUG SOURCE->TARGET ', source_attype, target_attype)
            print('@ DEBUG SOURCE.PROPS   ', list(self.properties.keys()))
            print('@ DEBUG TARGET.PROPS   ', list(target.properties.keys()))
            print('@ DEBUG TARGET.ANCHORS ', target.anchors)
        # If a TextDocument is aligned to a BoundingBox then we grab the coordinates
        # TODO: how are we getting the time point?
        if source_attype == 'TextDocument' and target_attype == 'BoundingBox':
            if 'coordinates' in target.properties:
                self.anchors['coordinates'] = target.properties['coordinates']
            #print(source_attype, self.anchors)
        elif source_attype == 'BoundingBox' and target_attype == 'TextDocument':
            pass
        # If a TextDocument is aligned to a TimeFrame then we copy time anchors
        # but also targets and representatives, the latter because some alignments
        # are not precise
        elif source_attype == 'TextDocument' and target_attype == 'TimeFrame':
            if 'start' in target.properties and 'end' in target.properties:
                self.anchors['time-offsets'] = (target.properties['start'],
                                                target.properties['end'])
            if 'time-offsets' in target.anchors:
                # TODO: is this ever used?
                self.anchors['time-offsets'] = target.anchors['time-offsets']
            if 'targets' in target.properties:
                self.anchors['targets'] = target.properties['targets']
            if 'representatives' in target.properties:
                self.anchors['representatives'] = target.properties['representatives']
            #print('-', source_attype, self.anchors, self, target)
        elif source_attype == 'TimeFrame' and target_attype == 'TextDocument':
            pass
        # Simply copy the time point
        elif source_attype == 'TextDocument' and target_attype == 'TimePoint':
            self.anchors['time-point'] = target.anchors['time-point']
            if debug:
                print('+ ADDED SOURCE.ANCHORS ', self.anchors)
        # For Token-TimeFrame alignments all we need are the start and end time points
        elif source_attype == 'Token' and target_attype == 'TimeFrame':
            if 'start' in target.properties and 'end' in target.properties:
                self.anchors['time-offsets'] = (target.properties['start'],
                                                target.properties['end'])
            #print(source_attype, self.anchors)
        elif source_attype == 'TimeFrame' and target_attype == 'Token':
            pass
        # TODO: check whether some action is needed for the next options
        elif source_attype == 'TextDocument' and target_attype == 'VideoDocument':
            pass
        elif source_attype == 'VideoDocument' and target_attype == 'TextDocument':
            pass
        elif source_attype == 'BoundingBox' and target_attype == 'TimePoint':
            pass
        elif source_attype =='TimePoint' and target_attype == 'BoundingBox':
            pass
        elif source_attype == 'BoundingBox' and target_attype in ('Token', 'Sentence', 'Paragraph'):
            pass
        elif source_attype in ('Token', 'Sentence', 'Paragraph') and target_attype == 'BoundingBox':
            pass
        elif source_attype == 'TextDocument' and target_attype == 'TimePoint':
            pass
        elif source_attype == 'TimePoint' and target_attype == 'TextDocument':
            pass
        else:
            print('-', source_attype, target_attype)
        #if debug:
        #    print('DEBUG', self.anchors)

    def _get_document(self):
        """Return the document or annotation node that the annotation/document in
        the node refers to via the document property (the annotation's own, or the
        view-level default). Return None if there is none."""
        docid = self.properties.get('document')
        return None if docid is None else self.graph.get_node(docid)

    def summary(self):
        """The default summary is just the identfier, this should typically be
        overriden by sub classes."""
        return { 'id': self.identifier }

    def has_label(self):
        """Only TimeFrameNodes can have labels so this returns False."""
        return False

    def pp(self, close=True):
        print('-' * 80)
        print(self)
        print(f'    document = {self.document}')
        for prop in self.properties:
            print(f'    {prop} = {self.properties[prop]}')
        print('    targets = ')
        for target in self.targets:
            print('       ', target)
        print('    anchors = ')
        for anchor in self.anchors:
            print(f'        {anchor} -> {self.anchors[anchor]}')
        if close:
            print('-' * 80)


class TimeFrameNode(Node):

    def __str__(self):
        label = f' {self.label()}' if self.has_label() else ''
        return ('<TimeFrameNode %s %s:%s%s>'
                % (self.identifier, self.start(), self.end(), label))

    def start(self):
        return self.properties.get('start', -1)

    def end(self):
        return self.properties.get('end', -1)

    def label(self):
        return self.properties.get('label')

    def has_label(self):
        return self.label() is not None

    def representatives(self) -> list:
        """Return a list of the representative TimePoints."""
        # TODO: why could I not get this from the anchors?
        rep_ids = self.properties.get('representatives', [])
        reps = [self.graph.get_node(rep_id) for rep_id in rep_ids]
        return reps

    def summary(self):
        """The summary of a time frame just contains the identifier, start, end
        and frame type."""
        return { 'id': self.identifier,
                 'start': self.properties['start'],
                 'end': self.properties['end'],
                 'frameType': self.label() }


class EntityNode(Node):

    def __init__(self, graph, view, annotation):
        super().__init__(graph, view, annotation)
        self.tokens = []
        self._paths = None
        self._anchor = None

    def __str__(self):
        try:
            start = self.properties['start']
            end = self.properties['end']
        except KeyError:
            start, end = self.anchors['text-offsets']
        return ("<NamedEntityNode %s %s:%s '%s'>"
                % (self.identifier, start, end, self.properties['text']))

    def start_in_video(self):
        #print('+++', self.document.properties)
        try:
            return self.document.anchors['time-point']
        except KeyError:
            return -1
        #return self.anchor()['video-start']

    def end_in_video(self):
        return self.anchor().get('video-end')

    '''
    Commented this out because the type checking in the code coverage tests requires 
    the default vaue for the close parameter to be the same as on Node.pp().

    def pp(self, close=False):
        super().pp(close=close)
        try:
            for i, p in enumerate(self.paths_to_docs()):
                print('    %s' % ' '.join([str(n) for n in p[1:]]))
        except ValueError:
            print('    WARNING: error in path_to_docs in NamedEntityNode.pp()')
        print('-' * 80)
    '''

    def summary(self):
        """The summary for entities needs to include where in the video or image
        the entity occurs, it is not enough to just give the text document."""
        # TODO: in the old days this used an anchor() method which was fragile
        # TODO: revamping it now  
        return {
            'id': self.identifier,
            'group': self.properties['group'],
            'cat': self.properties['category'],
            'document': self.document.identifier,
            # Entities in a TextDocument that is a full transcript without any
            # alignments do not have a TimePoint
            #'time-point': self.document.anchors.get('time-point'),
            #'text-offsets': self.anchors.get('text-offsets'),
            'time-point': self.document.anchors.get('time-point', -1),
            'text-offsets': self.anchors.get('text-offsets', (-1 ,-1)),
            #'document': self._get_document_plus_span(),
            #'video-start': anchor.get('video-start'),
            #'video-end': anchor.get('video-end'),
            #'coordinates': self._coordinates_as_string(anchor)
            }

    def anchor(self) -> dict:
        """The anchor is the position in the video that the entity is linked to.
        This anchor cannot be found in the document property because that points
        to a text document that was somehow derived from the video document. Some
        graph traversal is needed to get the anchor, but we know that the anchor
        is always a time frame or a bounding box.
        """
        # TODO: deal with the case where the primary document is not a video
        self.paths = self.paths_to_docs()
        bbtf = self.find_boundingbox_or_timeframe()
        # for path in paths:
        #     print('... [')
        #     for n in path: print('     ', n)
        # print('===', bbtf)
        if bbtf.at_type.shortname == config.BOUNDING_BOX:
            return {'video-start': bbtf.properties['timePoint'],
                    'coordinates': bbtf.properties['coordinates']}
        elif bbtf.at_type.shortname == config.TIME_FRAME:
            return {'video-start': bbtf.properties['start'],
                    'video-end': bbtf.properties['end']}
        else:
            return {}

    def anchor2(self):
        """The anchor is the position in the video that the entity is linked to.
        This anchor cannot be found in the document property because that points
        to a text document that was somehow derived from the video document. Some
        graph traversal is needed to get the anchor, but we know that the anchor
        is always a time frame or a bounding box.
        """
        # TODO: with this version you get an error that the paths variable does
        #       not exist yet, must get a clearer picture on how to build a graph
        #       where nodes have paths to anchors
        # TODO: deal with the case where the primary document is not a video
        if self._anchor is None:
            self._paths = self.paths_to_docs()
            bbtf = self.find_boundingbox_or_timeframe()
            # for path in self._paths:
            #    print('... [')
            #    for n in path: print('     ', n)
            # print('===', bbtf)
            if bbtf.at_type.shortname == config.BOUNDING_BOX:
                self._anchor = {'video-start': bbtf.properties['timePoint'],
                                'coordinates': bbtf.properties['coordinates']}
            elif bbtf.at_type.shortname == config.TIME_FRAME:
                self._anchor = {'video-start': bbtf.properties['start'],
                                'video-end': bbtf.properties['end']}
        return self._anchor

    def find_boundingbox_or_timeframe(self):
        return self.paths[-1][-2]

    @staticmethod
    def _coordinates_as_string(anchor):
        if 'coordinates' not in anchor:
            return None
        return ','.join(["%s:%s" % (pair[0], pair[1])
                         for pair in anchor['coordinates']])


class Nodes(object):

    """Factory class for Node creation. Use Node for creation unless a special
    class was registered for the kind of annotation we have."""

    node_classes = { config.NAMED_ENTITY: EntityNode,
                     config.TIME_FRAME: TimeFrameNode }

    @classmethod
    def new(cls, graph, view, annotation):
        node_class = cls.node_classes.get(annotation.at_type.shortname, Node)
        return node_class(graph, view, annotation)

