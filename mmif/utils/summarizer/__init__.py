"""
Package containing the code to generate a summary from a MMIF file.
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
