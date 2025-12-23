import sys
import argparse

from mmif.utils.summarizer.summary import Summary



def describe_argparser() -> tuple:
    """
    Returns two strings: a one-line description of the argparser and additional
    material, which will be shown for `mmif --help` and `mmif summarize --help`,
    respectively. For now they return the same string. The retun value should 
    still be a tuple because mmif.cli() depends on it.
    """
    oneliner = 'provides a CLI to create a JSON Summary for a MMIF file'
    return oneliner, oneliner


def prep_argparser(**kwargs):
    parser = argparse.ArgumentParser(
        description=describe_argparser()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs)
    parser.add_argument("-i", metavar='MMIF_FILE', help='input MMIF file', required=True)
    parser.add_argument("-o", metavar='JSON_FILE', help='output JSON summary file', required=True)
    parser.add_argument("--full", action="store_true", help="print full report")
    parser.add_argument('--transcript', action='store_true', help='include transcript')
    parser.add_argument('--captions', action='store_true', help='include Llava captions')
    parser.add_argument('--timeframes', action='store_true', help='include all time frames')
    parser.add_argument('--entities', action='store_true', help='include entities from transcript')
    return parser


def main(args):
    #print('>>>', args)
    mmif_summary = Summary(args.i)
    #print('>>>', mmif_summary)
    mmif_summary.report(
        outfile=args.o, full=args.full,
        #timeframes=args.timeframes, transcript=args.transcript,
        #captions=args.captions, entities=args.entities
        )

