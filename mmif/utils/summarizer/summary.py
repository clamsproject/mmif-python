"""MMIF Summarizer

MMIF consumer that creates a JSON summary from a MMIF file.

Makes some simplifying assumptions, including:

- There is one video in the MMIF documents list. All start and end properties
  are pointing to that video.
- The time unit is assumed to be milliseconds. 

Other assumptions are listed with the options below.


USAGE:

    $ python summary.py [OPTIONS] 

    Reads the MMIF file and creates a JSON summary file with the document list
    and any requested extra information.

Example:

    $ python summary -i input.mmif -o output.json --transcript

    Reads input.mmif and creates output.json with just transcript
    information added to the documents list and the views.

In all cases, the summarizer will summarize what is there and use the information
that is there, if the output of CLAMS is bad, then the results of the summarizer
will be bad (although it may hide a lot of the badness). In some rare cases some
information is added. For example if the ASR tool does not group tokens then the
summarizer will do that, but then only by simply grouping in equal chunks and not
trying to infer sentence-like groupings.

The summary always includes the MMIF version, the list of documents and a summary
of the metadata of all views (identifier, CLAMS app, timestamp, total number of
annotations and number of annotations per type, it does not show parameters and
application configuration).


OPTIONS:

-i INFILE -o OUTFILE

Run the summarizer over a single MMIF file and write the JSON summary to OUTFILE.

-- timeframes

Shows basic information of all timeframes. This groups the timeframes according to
the apps it was found in.

--transcript

Shows the text from the transcript in pseudo sentences.

The transcript is taken from the last non-warning ASR view, so only the last added
transcript will be summarized. It is assumed that Tokens in the view are ordered on
text occurrence.

--captions

Shows captions from the Llava captioner app.

--entities

Include entities from spaCy or other NER.

--full

Include all the above.

"""

# TODO:
# - For the time unit we should really update get_start(), get_end() and other methods.


import os, sys, io, json, argparse, pathlib
from collections import defaultdict

from mmif.serialize import Mmif
from mmif.vocabulary import DocumentTypes

from mmif.utils.summarizer import config
from mmif.utils.summarizer.utils import CharacterList
from mmif.utils.summarizer.utils import get_aligned_tokens, timestamp
from mmif.utils.summarizer.utils import get_transcript_view, get_last_segmenter_view, get_captions_view
from mmif.utils.summarizer.graph import Graph


VERSION = '0.2.0'


DEBUG = False

def debug(*texts):
    if DEBUG:
        for text in texts:
            sys.stderr.write(f'{text}\n')


class SummaryException(Exception):
    pass


class Summary(object):

    """Implements the summary of a MMIF file.

    fname           -  name of the input mmif file
    mmif            -  instance of mmif.serialize.Mmif
    graph           -  instance of graph.Graph
    documents       -  instance of Documents
    views           -  instance of Views
    transcript      -  instance of Transcript
    timeframes      -  instance of TimeFrames
    entities        -  instance of Entities
    captions        -  instance of get_captions_view

    """

    def __init__(self, mmif_file):
        self.fname = mmif_file
        #self.mmif = mmif if type(mmif) is Mmif else Mmif(mmif)
        self.mmif = Mmif(pathlib.Path(mmif_file).read_text())
        self.warnings = []
        self.graph = Graph(self.mmif)
        self.mmif_version = self.mmif.metadata['mmif']
        self.documents = Documents(self)
        self.annotations = Annotations(self)
        self.document = Document(self)
        self.views = Views(self)
        self.timeframes = TimeFrames(self)
        self.timeframe_stats = TimeFrameStats(self)
        self.transcript = Transcript(self)
        self.captions = Captions(self)
        self.entities = Entities(self)
        self.validate()
        self.print_warnings()

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def validate(self):
        """Minimal validation of the input. Mostly a place holder because all it
        does now is to check how many video documents there are."""
        if len(self.video_documents()) > 1:
            raise SummaryException("More than one video document in MMIF file")

    def video_documents(self):
        return self.mmif.get_documents_by_type(DocumentTypes.VideoDocument)

    def report(self, outfile=None):
        json_obj = {
            'mmif_version': self.mmif.metadata.mmif,
            'document': self.document.data,
            'documents': self.documents.data,
            'annotations': self.annotations.data,
            'views': self.views.data,
            'transcript': self.transcript.data,
            'captions': self.captions.as_json(),
            'timeframes': self.timeframes.as_json(),
            'timeframe_stats': self.timeframe_stats.data,
            'entities': self.entities.as_json()
        }
        report = json.dumps(json_obj, indent=2)
        if outfile is None:
            return report
        else:
            with open(outfile, 'w') as fh:
                fh.write(report)

    def print_warnings(self):
        for warning in self.warnings:
            print(f'WARNING: {warning}')

    def pp(self):
        self.documents.pp()
        self.views.pp()
        self.transcript.pp()
        self.timeframes.pp()
        self.entities.pp()
        print()


class Documents(object):

    """Contains a list of document summaries, which are dictionaries with just
    the id, type and location properties."""

    def __init__(self, summary: Summary):
        self.data = [self.summary(doc) for doc in summary.graph.documents]

    def __len__(self):
        return len(self.data)

    @staticmethod
    def summary(doc):
        return { 'id': doc.id,
                 'type': doc.at_type.shortname,
                 'location': doc.location }

    def pp(self):
        print('\nDocuments -> ')
        for d in self.data:
            print('    %s %s' % (d['type'], d['location']))


class Annotations(object):

    """Contains a dictionary of Annotation object summaries, indexed on view
    identifiers."""

    def __init__(self, summary):
        self.data = defaultdict(list)
        # summary.graph.get_nodes(config.ANNOTATION, view_id=view.id)
        for anno in summary.graph.get_nodes(config.ANNOTATION):
            self.data[anno.view.id].append(anno.properties)

    def get(self, item):
        return self.data.get(item, [])

    def get_all_annotations(self):
        annotations = []
        for annos in self.data.values():
            annotations.extend(annos)
        return annotations


class Document(object):

    """Collects some document-level information, including MMIF version, size of
    the MMIF file and some information from the SWT document annotation."""

    def __init__(self, summary):
        self.data = {
            'mmif_version': summary.mmif_version,
            'size': os.path.getsize(summary.fname) }
        annotations = summary.annotations.get_all_annotations()
        if annotations:
            # TODO: this if fragile because it assumes that the annotation we want
            # (which is the one from SWT) is always the first
            doc_level_annotation = annotations[0]
            if 'fps' in doc_level_annotation:
                self.data['fps'] = doc_level_annotation['fps']
            if 'frameCount' in doc_level_annotation:
                self.data['frames'] = doc_level_annotation['frameCount']
            if 'duration' in doc_level_annotation:
                duration = doc_level_annotation['duration']
                # both in milliseconds and as a timestamp
                self.data['duration_ms'] = duration
                self.data['duration_ts'] = timestamp(duration)


class Views(object):

    """Contains a list of view summaries, which are dictionaries with just
    the id, app and timestamp properties."""

    def __init__(self, summary):
        self.summary = summary
        self.data = [self.get_view_summary(view) for view in summary.mmif.views]

    def __getitem__(self, i):
        return self.data[i]

    def __len__(self):
        return len(self.data)

    #@staticmethod
    def get_view_summary(self, view):
        annotation_types = defaultdict(int)
        for annotation in view.annotations:
            annotation_types[annotation.at_type.shortname] += 1
        basic_info = {
            'id': view.id,
            'app': view.metadata.app,
            'timestamp': view.metadata.timestamp,
            'contains': [str(k) for k in view.metadata.contains.keys()],
            'annotation_count': len(view.annotations),
            'annotation_types': dict(annotation_types),
            'parameters': view.metadata.parameters,
            'appConfiguration': view.metadata.appConfiguration }
        if view.metadata.warnings:
            basic_info['warnings'] = view.metadata.warnings
        if view.metadata.error:
            basic_info['error'] = view.metadata.error
        return basic_info

    def pp(self):
        print('\nViews -> ')
        for v in self.data:
            print('    %s' % v['app'])


class Transcript(object):

    """The transcript contains the string value from the first text document in the
    last ASR view. It issues a warning if there is more than one text document in
    the view."""

    def __init__(self, summary):
        self.summary = summary
        self.data = []
        view = get_transcript_view(summary.mmif.views)
        if view is not None:
            documents = view.get_documents()
            if len(documents) > 1:
                summary.add_warning(f'More than one TextDocument in ASR view {view.id}')
            t_nodes = summary.graph.get_nodes(config.TOKEN, view_id=view.id)
            s_nodes = summary.graph.get_nodes(config.SENTENCE, view_id=view.id)
            if not t_nodes:
                return
            if s_nodes:
                # Whisper has Sentence nodes
                sentences = self.collect_targets(s_nodes)
                sentence_ids = [n.identifier for n in s_nodes]
            else:
                # But Kaldi does not
                sentences = self.create_sentences(t_nodes)
                sentence_ids = [None] * len(sentences)
            # initialize the transcripts with all blanks, most blanks will be
            # overwrite with characters from the tokens
            transcript = CharacterList(self.transcript_size(sentences))
            for s_id, s in zip(sentence_ids, sentences):
                transcript_element = TranscriptElement(s_id, s, transcript)
                self.data.append(transcript_element.as_json())

    def __str__(self):
        return str(self.data)

    @staticmethod
    def transcript_size(sentences):
        try:
            return sentences[-1][-1].properties['end']
        except IndexError:
            return 0

    def collect_targets(self, s_nodes):
        """For each node (in this context a sentence node), collect all target nodes
        (which are tokens) and return them as a list of lists, with one list for each
        node."""
        targets = []
        for node in s_nodes:
            node_target_ids = node.properties['targets']
            node_targets = [self.summary.graph.get_node(stid) for stid in node_target_ids]
            targets.append(node_targets)
        return targets

    def create_sentences(self, t_nodes, sentence_size=12):
        """If there is no sentence structure then we create it just by chopping th
        input into slices of some pre-determined length."""
        # TODO: perhaps the size paramater should be set in the config file or via a
        # command line option.
        return [t_nodes[i:i + sentence_size]
                for i in range(0, len(t_nodes), sentence_size)]


class TranscriptElement:

    """Utility class to handle data associated with an element from a transcript,
    which is created from a sentence which is a list of Token Nodes. Initialization
    has the side effect of populating the full transcript which is an instance of
    CharacterList and which is also accessed here."""

    def __init__(self, identifier: str, sentence: list, transcript: CharacterList):
        for t in sentence:
            # this adds the current token to the transcript
            start = t.properties['start']
            end = t.properties['end']
            word = t.properties['word']
            transcript.set_chars(word, start, end)
        self.id = identifier
        self.start = sentence[0].anchors['time-offsets'][0]
        self.end = sentence[-1].anchors['time-offsets'][1]
        self.start_offset = sentence[0].properties['start']
        self.end_offset = sentence[-1].properties['end']
        self.text = transcript.getvalue(self.start_offset, self.end_offset)

    def __str__(self):
        text = self.text if len(self.text) <= 50 else self.text[:50] + '...'
        return f'<TranscriptElement {self.id} {self.start} {self.end}  "{text}">'

    def as_json(self):
        json_obj = {
            "start-time": self.start,
            "end-time": self.end,
            "text": self.text }
        if self.id is not None:
            json_obj["id"] = self.id
        return json_obj


class Nodes(object):

    """Abstract class to store instances of subclasses of graph.Node. The
    initialization methods of subclasses of Nodes can guard what nodes will
    be allowed in, for example, as of July 2022 the TimeFrames class only
    allowed time frames that had a frame type (thereby blocking the many
    timeframes from Kaldi).

    Instance variables:

    summary    -  an instance of Summary
    graph      -  an instance of graph.Graph, taken from the summary
    nodes      -  list of instances of subclasses of graph.Node

    """

    def __init__(self, summary):
        self.summary = summary
        self.graph = summary.graph
        self.nodes = []

    def __getitem__(self, i):
        return self.nodes[i]

    def __len__(self):
        return len(self.nodes)

    def add(self, node):
        self.nodes.append(node)

    def get_nodes(self, **props):
        """Return all the nodes that match the given properties."""
        def prop_check(p, v, props_given):
            return v == props_given.get(p) if p in props_given else False
        return [n for n in self
                if all([prop_check(p, v, n.annotation.properties)
                        for p, v in props.items()])]


class TimeFrames(Nodes):

    """For now, we take only the TimeFrames that have a frame type, which rules out
    all the frames we got from Kaldi."""

    def __init__(self, summary):
        super().__init__(summary)
        # a dictionary mapping app names to lists of timeframe summaries
        self.data = defaultdict(list)
        for tf_node in self.graph.get_nodes(config.TIME_FRAME):
            if tf_node.has_label():
                self.add(tf_node)
        self._collect_timeframe_summaries()
        self._sort_timeframe_summaries()

    def _collect_timeframe_summaries(self):
        for tf in self.nodes:
            label = tf.frame_type()
            try:
                start, end = tf.anchors['time-offsets']
            except KeyError:
                # TODO: 
                # - this defies the notion of using the anchors for this, but 
                #   maybe in this case we should go straight to the start/end
                # - this code below also raises an error if there are no start
                #   and end properties
                start = tf.properties['start']
                end = tf.properties['end']
            representatives = tf.representatives()
            rep_tps = [rep.properties['timePoint'] for rep in representatives]
            score = tf.properties.get('classification', {}).get(label)
            app = tf.view.metadata.app
            self.data[app].append(
                { 'identifier': tf.identifier, 'label': label, 'score': score,
                  'start-time': start, 'end-time': end, 'representatives': rep_tps })

    def _sort_timeframe_summaries(self):
        """Sort the data on their start time, do this for all apps."""
        for app in self.data:
            sort_function = lambda x: x['start-time']
            self.data[app] = list(sorted(self.data[app], key=sort_function))

    def as_json(self):
        return self.data

    def pp(self):
        print('\nTimeframes -> ')
        for tf in self.nodes:
            summary = tf.summary()
            print('    %s:%s %s' % (summary['start'], summary['end'],
                                    summary['frameType']))


class TimeFrameStats(object):

    def __init__(self, summary):
        # a dictionary mapping app names to frameType->duration dictionaries,
        # where the duration is cumulative over all instances
        self.timeframes = summary.timeframes
        self.data = {}
        self._collect_durations()
        self._collect_other_morsels()

    def _collect_durations(self):
        timeframes = self.timeframes.data
        for app in timeframes:
            self.data[app] = {}
            for tf in timeframes[app]:
                label = tf.get('label')
                if label not in self.data[app]:
                    self.data[app][label] = {'count': 0, 'duration': 0}
                self.data[app][label]['count'] += 1
                duration = tf['end-time'] - tf['start-time']
                if label is not None:
                    # TODO: these gave weird values for duration
                    #print('---',app, label, duration)
                    self.data[app][label]['duration'] += duration
                duration = self.data[app][label]['duration']
                count = self.data[app][label]['count']
                self.data[app][label]['average'] = duration // count 

    def _collect_other_morsels(self):
        # First we want everything grouped by app and label
        timeframes = self.timeframes.data
        grouped_timeframes = defaultdict(lambda: defaultdict(list))
        for app in timeframes:
            for tf in timeframes[app]:
                label = tf.get('label')
                grouped_timeframes[app][label].append(tf)
        # The we pick the morsels for each label
        for app in grouped_timeframes:
            for label in grouped_timeframes[app]:
                tfs = grouped_timeframes[app][label]
                sort_on_start = lambda tf: tf['start-time']
                sort_on_length = lambda tf: tf['end-time'] - tf['start-time']
                first_tf = list(sorted(tfs, key=sort_on_start))[0]
                longest_tf = list(sorted(tfs, key=sort_on_length, reverse=True))[0]                
                self.data[app][label]['first'] = first_tf['start-time']
                self.data[app][label]['longest'] = longest_tf['start-time']


class Entities(Nodes):

    """Collecting instances of graph.EntityNode.

    nodes_idx  -  lists of instances of graph.EntityNode, indexed on entity text
                  { entity-string ==> list of graph.EntityNode }
    bins       -  an instance of Bins

    """

    def __init__(self, summary):
        super().__init__(summary)
        self.nodes_idx = {}
        self.bins = None
        for ent in self.graph.get_nodes(config.NAMED_ENTITY):
            self.add(ent)
        self._create_node_index()
        self._group()

    def __str__(self):
        return f'<Entities with {len(self.nodes_idx)} nodes and {len(self.bins)} bins>'

    def _create_node_index(self):
        """Put all the entities from self.nodes in self.node_idx. This first puts
        the nodes into the dictionary indexed on text string and then sorts the
        list of nodes for each string on video position."""
        for ent in self:
            self.nodes_idx.setdefault(ent.properties['text'], []).append(ent)
        for text, entities in self.nodes_idx.items():
            self.nodes_idx[text] = sorted(entities,
                                          key=(lambda e: e.start_in_video()))

    def _group(self):
        """Groups all the nodes on the text and sorts them on position in the video,
        for the latter it will also create bins of entities that occur close to each
        other in the text."""
        # create the bins, governed by the summary's granularity
        self.bins = Bins(self.summary)
        for text, entities in self.nodes_idx.items():
            self.bins.current_bin = None
            for entity in entities:
                self.bins.add_entity(text, entity)
        self.bins.mark_entities()

    def _add_tags(self, tags):
        for tag in tags:
            tag_doc = tag.properties['document']
            tag_p1 = tag.properties['start']
            tag_p2 = tag.properties['end']
            entities = self.nodes_idx.get(tag.properties['text'], [])
            for entity in entities:
                props = entity.properties
                doc = props['document']
                p1 = props['start']
                p2 = props['end']
                if tag_doc == doc and tag_p1 == p1 and tag_p2 == p2:
                    entity.properties['tag'] = tag.properties['tagName']

    def as_json(self):
        json_obj = []
        for text in self.nodes_idx:
            entity = {"text": text, "instances": []}
            json_obj.append(entity)
            for e in self.nodes_idx[text]:
                entity["instances"].append(e.summary()) # e.summary(), E_PROPS)
        return json_obj

    def pp(self):
        print('\nEntities -> ')
        for e in self.nodes_idx:
            print('    %s' % e)
            for d in self.nodes_idx[e]:
                props = ["%s=%s" % (p, v) for p, v in d.summary().items()]
                print('        %s' % ' '.join(props))

    def print_groups(self):
        for key in sorted(self.nodes_idx):
            print(key)
            for e in self.nodes_idx[key]:
                print('   ', e, e.start_in_video())


class Captions(Nodes):

    def __init__(self, summary):
        super().__init__(summary)
        self.captions = []
        view = get_captions_view(summary.mmif.views)
        if view is not None:
            for doc in self.graph.get_nodes(config.TEXT_DOCUMENT, view_id=view.id):
                text = doc.properties['text']['@value'].split('[/INST]')[-1]
                debug(
                    f'>>> DOC      {doc}',
                    f'>>> PROPS    {list(doc.properties.keys())}',
                    f'>>> TEXT     ' + text.replace("\n", "")[:100],
                    f'>>> ANCHORS  {doc.anchors}')
                if 'time-offsets' in doc.anchors and 'representatives' in doc.anchors:
                    # For older LLava-style captions
                    # http://apps.clams.ai/llava-captioner/v1.2-6-gc824c97
                    # NOTE: probably obsolete, at least the link above is dead
                    tp_id = doc.anchors["representatives"][0]
                    tp = summary.graph.get_node(tp_id)
                    if tp is not None:
                        self.captions.append(
                            { 'identifier': doc.identifier,
                              'time-point': tp.properties['timePoint'],
                              'text': text })
                if 'time-point' in doc.anchors:
                    # For newer SmolVLM-style captions
                    # http://apps.clams.ai/smolvlm2-captioner
                    self.captions.append(
                        { 'identifier': doc.identifier,
                          'time-point': doc.anchors['time-point'],
                          'text': text })

    def as_json(self):
        return self.captions
        #return [(ident, p1, p2, text) for ident, p1, p2, text in self.captions]


class Bins(object):

    def __init__(self, summary):
        self.summary = summary
        self.bins = {}
        self.current_bin = None
        self.current_text = None

    def __str__(self):
        return f'<Bins {len(self.bins)}>'

    def __len__(self):
        return len(self.bins)

    def add_entity(self, text, entity):
        """Add an entity instance to the appropriate bin."""
        if self.current_bin is None:
            # Add the first instance of a new entity (as defined by the text),
            # since it is the first a new bin will be created.
            self.current_text = text
            self.current_bin = Bin(entity)
            self.bins[text] = [self.current_bin]
        else:
            # For following entities with the same text, a new bin may be
            # created depending on the positions and the granularity.
            p1 = self.current_bin[-1].start_in_video()
            p2 = entity.start_in_video()
            # p3 = entity.end_in_video()
            if p2 - p1 < config.GRANULARITY:
                # TODO: should add p3 here
                self.current_bin.add(entity)
            else:
                self.current_bin = Bin(entity)
                self.bins[self.current_text].append(self.current_bin)

    def mark_entities(self):
        """Marks all entities with the bin that they occur in. This is done to export
        the grouping done with the bins to the entities and this way the bins never need
        to be touched again."""
        # TODO: maybe use the bins when we create the output
        for entity_bins in self.bins.values():
            for i, e_bin in enumerate(entity_bins):
                for entity in e_bin:
                    entity.properties['group'] = i

    def print_bins(self):
        for text in self.bins:
            print(text)
            text_bins = self.bins[text]
            for i, text_bin in enumerate(text_bins):
                text_bin.print_nodes(i)
            print()


class Bin(object):

    def __init__(self, node):
        # TODO: we are not using these yet, but a bin should have a begin and
        # end in the video which should be derived from the start and end of
        # entities in the video. The way we put things in bins now is a bit
        # fragile since it depends on the start or end of the last element.
        self.start = 0
        self.end = 0
        self.nodes = [node]

    def __getitem__(self, i):
        return self.nodes[i]

    def add(self, node):
        self.nodes.append(node)

    def print_nodes(self, i):
        for node in self.nodes:
            print(' ', i, node)
