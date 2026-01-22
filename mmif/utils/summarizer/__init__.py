"""

MMIF consumer that creates a JSON summary from a MMIF file.

Makes some simplifying assumptions, including:

- There is one video in the MMIF documents list. All start and end properties
  are pointing to that video.
- The time unit is assumed to be milliseconds.

USAGE:

    $ mmif summarize -i INFILE -o OUTFILE 

    Run the summarizer over a MMIF file and write the JSON summary to OUTFILE.

In all cases, the summarizer summarizes the information that is there, it does
not fix any mistakes and in general it does not add any information that is not
explicitly or implicitly in the MMIF file. In rare cases some information is
added, for example if an ASR tool does not group tokens in sentence-like objects
then the summarizer will do that, but then only by creating token groups of the 
same length.

The summary includes the MMIF version, the list of documents, a summary of the
metadata of all views (identifier, CLAMS app, timestamp, total number of
annotations and number of annotations per type, it does not show parameters and
application configuration), time frames, transcript, captions and entities.

"""


import argparse

from mmif.utils.summarizer.summary import Summary


def argparser():
    parser = argparse.ArgumentParser(description='Create a JSON Summary for a MMIF file')
    parser.add_argument('-i', metavar='MMIF_FILE', help='input MMIF file', required=True)
    parser.add_argument('-o', metavar='JSON_FILE', help='output JSON summary file', required=True)
    return parser


def pp_args(args):
    for a, v in args.__dict__.items():
        print(f'{a:12s}  -->  {v}')


def main():
    parser = argparser()
    args = parser.parse_args()
    #pp_args(args)
    mmif_summary = Summary(args.i)
    mmif_summary.report(outfile=args.o)
