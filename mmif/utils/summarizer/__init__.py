
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


"""
There used to be an option to process a whole directory, but I never used it and decided
that if needed it would better be done by an extra script or a separate function.

The code for when there was a -d option is here just in case.

if args.d:
    for mmif_file in pathlib.Path(args.d).iterdir():
        if mmif_file.is_file() and mmif_file.name.endswith('.mmif'):
            print(mmif_file)
            json_file = str(mmif_file)[:-4] + 'json'
            mmif_summary = Summary(mmif_file.read_text())
            mmif_summary.report(outfile=json_file)
"""