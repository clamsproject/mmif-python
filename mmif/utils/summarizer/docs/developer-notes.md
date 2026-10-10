# Summarizer Notes

Mostly descriptions of the data that the summarizer has to work with.

> These should be moved elsewhere now that this repo is just for the inspector.


## Scope

The descriptions and strategies here are based on using real data from the MMIF Server. In June 2025 that server contained output from the following pipelines:

```
<aapb-pua-kaldi-wrapper v3>
<chyron-detection v1.0>
<clipsearch v1-6-g8e7a0ff>
<dbpedia-spotlight-wrapper 5dad157>
<dbpedia-spotlight-wrapper v1.1>
<distil-whisper-wrapper v1.1>
<east-textdetection v1.1>
<east-textdetection v1.1> ==> <parseqocr-wrapper v1.0>
<east-textdetection v1.1> ==> <tesseractocr-wrapper v1.0>
<gentle-forced-aligner-wrapper v1.0>
<slatedetection v2.0>
<spacy-wrapper v1.1>
<swt-detection v5.0>
<swt-detection v5.1>
<swt-detection v5.1> ==> <doctr-wrapper v1.1>
<swt-detection v5.1> ==> <paddleocr-wrapper becfa66>
<swt-detection v6.0-1-g627f8dd>
<swt-detection v6.0-2-gdea09ae>
<swt-detection v6.1>
<swt-detection v6.1> ==> <doctr-wrapper v1.1>
<swt-detection v6.1> ==> <simple-timepoints-stitcher v3.0>
<swt-detection v6.1> ==> <simple-timepoints-stitcher v3.1>
<whisper-wrapper v3>
<whisper-wrapper v6-3-ge33e60f>
<whisper-wrapper v7>
<whisper-wrapper v8>
<whisper-wrapper v8-3-g737e280>
```

In addition, I am working with some sample output files from two captioners and the spaCy app applied to one of them, using he following pipelines:

```
<swt-detection v7.4> ==> <llava-captioner v1.2-6-gc824c97>
<swt-detection v7.7> ==> <smolvlm2-captioner>
<swt-detection v7.7> ==> <smolvlm2-captioner> ==> <spacy-wrapper v2.1>
```

The example files are all stored in the `code/examples/pipelines` folder in subdirectories that encode the pipeline name. Various output files are also stored in those subdirectories with suffixes or perhaps in further subdirectories.

> Note. The above only holds for those that have downloaded the pipelines from a here undisclosed location, that is, this is for developers only.
 
The following links go into some pipelines one by one:

- [Whisper](pipelines/whisper.md)
- [Kaldi](pipelines/kaldi.md)
- [SWT ⟹ DocTR](pipelines/swt-doctr.md)
- [SWT ⟹ Llava](pipelines/swt-llava.md)
- [SWT ⟹ SmolVLM](pipelines/swt-smolvlm.md)
- [spaCy](pipelines/spacy.md)
