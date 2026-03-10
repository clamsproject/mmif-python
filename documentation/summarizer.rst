.. _summarizer:


MMIF Summarizer
===============

The Summarizer is a MMIF consumer that creates a JSON summary from a MMIF file. It
makes some simplifying assumptions, including:

- There is one video in the MMIF documents list. All start and end properties
  are pointing to that video.
- The time unit is assumed to be milliseconds.


The summarizer is accessible via the ``mmif`` command line script. To run the
summarizer over a MMIF file and write the JSON summary to OUTFILE:

.. code-block:: bash

    mmif summarize -i INFILE -o OUTFILE

In all cases, the summarizer summarizes only the information that is there, it
does not fix any mistakes and in general it does not add any information that is
not explicitly or implicitly in the MMIF file. In rare cases some information is
added, for example if an ASR tool does not group tokens in sentence-like objects
then the summarizer will do that, but then only by creating token groups of the 
same length.

The summary includes the MMIF version, the list of documents, a summary of the
metadata of all views (identifier, CLAMS app, timestamp, total number of
annotations and number of annotations per type, it does not show parameters and
application configuration), time frames, transcript, captions and entities.