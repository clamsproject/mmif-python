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
    oneliner = 'Create a JSON Summary for a MMIF file'
    return oneliner, oneliner


def prep_argparser(**kwargs):
    """
    Create the ArgumentParser instance for the summarizer.
    """
    parser = argparse.ArgumentParser(
        description=describe_argparser()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs)
    parser.add_argument("-i", metavar='MMIF_FILE', help='input MMIF file', required=True)
    parser.add_argument("-o", metavar='OUTPUT_FILE', help='output JSON summary file', required=True)
    return parser


def main(args: argparse.Namespace):
    """
    The main summarizer command.
    """
    mmif_summary = Summary(args.i)
    mmif_summary.report(outfile=args.o)
