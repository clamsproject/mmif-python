
from mmif.vocabulary import DocumentTypes
from mmif.vocabulary import AnnotationTypes


# The name of CLAMS applications, used to select views and to determine whether
# the summarizer is appropriate for the app version.
# TODO: this now requires an exhaustive listing of all allowed apps and their
# versions, we need a more maintainable system.

KALDI = [
    # The first two use MMIF 0.4 and should probably be retired
    'http://apps.clams.ai/aapb-pua-kaldi-wrapper/0.2.2',
    'http://apps.clams.ai/aapb-pua-kaldi-wrapper/0.2.3',
    'http://apps.clams.ai/aapb-pua-kaldi-wrapper/v3']

WHISPER = [
    'http://apps.clams.ai/whisper-wrapper/v7',
    'http://apps.clams.ai/whisper-wrapper/v8',
    'http://apps.clams.ai/whisper-wrapper/v8-3-g737e280']

CAPTIONER = [
    'http://apps.clams.ai/llava-captioner/v1.2-6-gc824c97',
    'http://apps.clams.ai/smolvlm2-captioner']

NER = [
    'http://apps.clams.ai/spacy-wrapper/v1.1',
    'http://apps.clams.ai/spacy-wrapper/v2.1']

SEGMENTER = 'http://apps.clams.ai/audio-segmenter'


# When a named entity occurs 20 times we do not want to generate 20 instances of
# it. If the start of the next entity occurs within the below number of
# milliseconds after the end of the previous, then it is just added to the
# previous one. Taking one minute as the default so two mentions in a minute end
# up being the same instance. This setting can be changed with the 'granularity'
# parameter.
# TODO: this seems broken

GRANULARITY = 1000


# Properties used for the summary for various tags

DOC_PROPS = ('id', 'type', 'location')
VIEW_PROPS = ('id', 'timestamp', 'app')
TF_PROPS = ('id', 'start', 'end', 'frameType')
E_PROPS = ('id', 'group', 'cat', 'tag', 'video-start', 'video-end', 'coordinates')


# Names of types

TEXT_DOCUMENT = DocumentTypes.TextDocument.shortname
VIDEO_DOCUMENT = DocumentTypes.VideoDocument.shortname
TIME_FRAME = AnnotationTypes.TimeFrame.shortname
BOUNDING_BOX = AnnotationTypes.BoundingBox.shortname
ALIGNMENT = AnnotationTypes.Alignment.shortname

ANNOTATION = 'Annotation'
TOKEN = 'Token'
SENTENCE = 'Sentence'
PARAGRAPH = 'Paragraph'
NAMED_ENTITY = 'NamedEntity'
NOUN_CHUNK = 'NounChunk'
VERB_CHUNK = 'VerbChunk'

TIME_BASED_INTERVALS = {TIME_FRAME}
SPAN_BASED_INTERVALS = {TOKEN, SENTENCE, PARAGRAPH, NAMED_ENTITY, NOUN_CHUNK, VERB_CHUNK}
