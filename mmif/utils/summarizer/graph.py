import sys, json
from collections import defaultdict
from operator import itemgetter
from pathlib import Path
import argparse

from typing import Any
from mmif import Mmif

from mmif.utils.summarizer import config
from mmif.utils.summarizer.utils import compose_id, normalize_id
from mmif.utils.summarizer.nodes import Node, Nodes, EntityNode, TimeFrameNode


class Graph(object):

    """
    Graph implementation for a MMIF document. Each node contains an annotation
    or document. Alignments are stored separately. Edges between nodes are created
    from the alignments and added to the Node.targets property. The first edge added
    to Node.targets is the document that the Node points to (if there is one).

    The goal for the graph is to store all useful annotation and to have simple ways
    to trace nodes all the way up to the primary data.

    :var mmif:        the MMIF document that we are creating a graph for
    :var documents:   list of the top-level documents
    :var nodes:       dictionary of nodes, indexed on node identifier
    :var alignments:  list of <View, Annotation> pairs
    :var token_idx:   an instance of TokenIndex

    """

    def __init__(self, mmif: Any):
        # TODO: the type hint should really be "MMif | str", but pytype did not
        # like that.
        self.mmif = mmif if type(mmif) is Mmif else Mmif(mmif)
        self.documents = []
        self.nodes = {}
        self.alignments = []
        self._init_nodes()
        self._init_edges()
        # Third pass to add links between text elements, in particular from
        # entities to tokens, adding lists of tokens to entities.
        tokens = self.get_nodes(config.TOKEN)
        entities = self.get_nodes(config.NAMED_ENTITY)
        self.token_idx = TokenIndex(tokens)
        #self.token_idx.pp()
        for e in entities:
            #print('>>>', e, e.anchors)
            e.tokens = self.token_idx.get_tokens_for_node(e)

    def _init_nodes(self):
        # The top-level documents are added as nodes, but they are also put in
        # the documents list.
        for doc in self.mmif.documents:
            self.add_node(None, doc)
            self.documents.append(doc)
        # First pass over all annotations and documents in all views and save
        # them in the graph.
        doc_ids = [d.id for d in self.documents]
        for view in self.mmif.views:
            for annotation in view.annotations:
                normalize_id(doc_ids, view, annotation)
                if annotation.at_type.shortname == config.ALIGNMENT:
                    # alignments are not added as nodes, but we do keep them around
                    self.alignments.append((view, annotation))
                else:
                    self.add_node(view, annotation)

    def _init_edges(self):
        # Second pass over the alignments so we create edges.
        for view, alignment in self.alignments:
            self.add_edge(view, alignment)

    def __str__(self):
        return "<Graph nodes=%d>" % len(self.nodes)

    def add_node(self, view, annotation):
        """Add an annotation as a node to the graph."""
        node = Nodes.new(self, view, annotation)
        self.nodes[node.identifier] = node

    def add_edge(self, view, alignment):
        source_id = alignment.properties['source']
        target_id = alignment.properties['target']
        #print(alignment.id, source_id, target_id)
        source = self.get_node(source_id)
        target = self.get_node(target_id)
        if source is None or target is None:
            print('WARNING: could not add edge ',
                  'because the source and/or target does not extst')
        else:
            # make sure the direction goes from token or textdoc to annotation
            if target.annotation.at_type.shortname in (config.TOKEN, config.TEXT_DOCUMENT):
                source, target = target, source
            source.targets.append(target)
            source.add_anchors_from_alignment(target)
            target.add_anchors_from_alignment(source)

    def get_node(self, node_id: str) -> Node | None:
        """Return the Node instance from the node index."""
        return self.nodes.get(node_id)

    # def get_nodes(self, short_at_type: str, view_id : str = None):
    # replaced the above because the code coverage is picky on type hints
    def get_nodes(self, short_at_type: str, view_id=None):
        """Get all nodes for an annotation type, using the short form. If a view
        identifier is provided then only include nodes from that view."""
        return [node for node in self.nodes.values()
                if (node.at_type.shortname == short_at_type
                    and (view_id is None or node.view.id == view_id))]

    def statistics(self) -> defaultdict:
        """
        Collect counts for node types in each view.
        """
        stats = defaultdict(int)
        for node in self.nodes.values():
            stats[f'{str(node.view_id):4} {node.at_type.shortname}'] += 1
        return stats

    def trim(self, start: int, end: int):
        """
        :meta private:

        Trim the graph and keep only those nodes that are included in the graph
        between two timepoints (both in milliseconds). This assumes that all nodes
        are anchored on the time in the audio or video stream. At the moment it 
        keeps all nodes that are not explicitly anchored. Private for now because
        it is still useless.
        """
        remove = set()
        for node_id, node in self.nodes.items():
            if 'time-point' in node.anchors:
                if not start <= node.anchors['time-point'] <= end:
                    remove.add(node_id)
            if 'time-offsets' in node.anchors:
                p1, p2 = node.anchors['time-offsets']
                if not (start <= p1 <= end and start <= p2 <= end):
                    remove.add(node_id)
        new_nodes = [n for n in self.nodes.values() if not n.identifier in remove]
        self.nodes = { node.identifier: node for node in new_nodes }

    def pp(self, fname=None, skip_timepoints=False):
        """
        :meta private:
        """
        fh = sys.stdout if fname is None else open(fname, 'w')
        fh.write("%s\n" % self)
        for view in self.mmif.views:
            fh.write("  <View %s %s>\n" % (view.id, str(view.metadata['app'])))
        for node_id, node in self.nodes.items():
            if node.at_type.shortname == 'TimePoint':
                continue
            fh.write("  %-40s" % node)
            targets = [str(t) for t in node.targets]
            fh.write(' -->  [%s]\n' % ' '.join(targets))

    def pp_statistics(self):
        """
        :meta private:
        """
        stats = self.statistics()
        for at_type in sorted(stats):
            print(f'{at_type:20} {stats[at_type]:>5}')


class TokenIndex(object):

    """
    The tokens are indexed on the identifier on the TextDocument that they occur
    in and for each text document we have a list of <offsets, Node> pairs

    .. code-block:: python

        {'v_4:td1': [
            ((0, 5), <summarizer.graph.Node object at 0x1039996d0>),
            ((5, 6), <summarizer.graph.Node object at 0x103999850>),
            ...]
        }

    """

    # TODO: 
    # - Benchmark get_tokens_for_node(). I may want to use something like this
    #   to  determine enclosed nodes and enclosing nodes and that may blow up since
    #   that would be O(n^2). If it does matter, probably start using binary search
    #   or add an index from character offset to nodes.
    # - It is also not sure whether we still need this since the new spaCy gives
    #   targets to tokens.

    def __init__(self, tokens):
        self.tokens = {}
        self.token_count = len(tokens)
        for t in tokens:
            tup = ((t.properties['start'], t.properties['end']), t)
            self.tokens.setdefault(t.document.identifier, []).append(tup)
        # Make sure the tokens for each document are ordered.
        for document, token_list in self.tokens.items():
            self.tokens[document] = sorted(token_list, key=itemgetter(0))
        # In some cases there are two tokens with identical offset (for example
        # with tokenization from both Kaldi and spaCy, not sure what to do with
        # these, but should probably be more careful on what views to access

    def __len__(self):
        return self.token_count

    def __str__(self):
        return f'<TokenIndex with {len(self)} tokens>'

    def get_tokens_for_node(self, node: Node):
        """Return all tokens included in the span of a node."""
        doc = node.document.identifier
        try:
            start = node.properties['start']
            end = node.properties['end']
        except KeyError:
            start, end = node.anchors['text-offsets']
        tokens = []
        for (t_start, t_end), token in self.tokens.get(doc, []):
            if t_start >= start and t_end <= end:
                tokens.append(token)
        return tokens

    def pp(self, fname=None):
        fh = sys.stdout if fname is None else open(fname, 'w')
        for document in self.tokens:
            fh.write("\n[%s] -->\n" % document)
            for t in self.tokens[document]:
                fh.write('    %s %s\n' % (t[0], t[1]))



if __name__ == '__main__':

    graph = Graph(open(sys.argv[1]).read())
    print(graph)
    #graph.pp()
    #graph.nodes['v_7:st12'].pp()
    #graph.nodes['v_2:s1'].pp()
    #graph.nodes['v_4:tf1'].pp()
    exit()
    for node in graph.nodes.values():
        print(node.at_type.shortname, node.identifier, node.anchors)


'''

Printing some graphs:

uv run graph.py -i examples/input-v9.mmif -e dot -f png -o examples/dot-v9-1-full -p -a -v
uv run graph.py -i examples/input-v9.mmif -e dot -f png -o examples/dot-v9-2-no-view-links -p -a
uv run graph.py -i examples/input-v9.mmif -e dot -f png -o examples/dot-v9-3-no-anchor-to-doc -p

'''
