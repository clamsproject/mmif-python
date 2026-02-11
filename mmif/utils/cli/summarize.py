import argparse
import json
import pathlib
import sys
import tempfile

from mmif.utils.summarizer.summary import Summary


def describe_argparser() -> tuple:
    """
    returns two strings: one-line description of the argparser, and addition material, 
    which will be shown in `clams --help` and `clams <subcmd> --help`, respectively.
    """
    oneliner = 'Create a JSON Summary for a MMIF file.'
    additional = 'The output is serialized as JSON and includes various statistics and summaries of the MMIF content.'
    return oneliner, oneliner + '\n\n' + additional


def prep_argparser(**kwargs):
    """
    Create the ArgumentParser instance for the summarizer.
    """
    parser = argparse.ArgumentParser(description=describe_argparser()[1],
                                     formatter_class=argparse.RawDescriptionHelpFormatter, **kwargs)
    parser.add_argument("MMIF_FILE",
                        nargs="?", type=argparse.FileType("r"),
                        default=None if sys.stdin.isatty() else sys.stdin,
                        help='input MMIF file path, or STDIN if `-` or not provided.')
    parser.add_argument("-o", "--output",
                        type=argparse.FileType("w"),
                        default=sys.stdout,
                        help='output file path, or STDOUT if not provided.')
    parser.add_argument("-p", "--pretty", action="store_true",
                        help="Pretty-print JSON output")
    return parser


def main(args: argparse.Namespace):
    """
    The main summarizer command.
    """
    if args.MMIF_FILE is None:
        raise ValueError("No input MMIF provided.")
        
    mmif_content = args.MMIF_FILE.read()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.mmif', delete=False
        ) as tmp:
            tmp.write(mmif_content)
            tmp_path = pathlib.Path(tmp.name)
        mmif_summary = Summary(tmp_path)
        output = mmif_summary.to_dict()
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

    json.dump(output, args.output, indent=2 if args.pretty else None)


if __name__ == "__main__":
    parser = prep_argparser()
    args = parser.parse_args()
    main(args)
