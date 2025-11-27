import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Union

from mmif.utils.workflow_helper import generate_workflow_identifier, describe_single_mmif, \
    describe_mmif_collection


def get_pipeline_specs(mmif_file: Union[str, Path]):
    import warnings
    warnings.warn("get_pipeline_specs is deprecated, use mmif.utils.workflow_helper.describe_single_mmif instead",
                  DeprecationWarning)
    return describe_single_mmif(mmif_file)


def generate_pipeline_identifier(mmif_file: Union[str, Path]) -> str:
    import warnings
    warnings.warn("generate_pipeline_identifier is deprecated, use generate_workflow_identifier instead",
                  DeprecationWarning)
    return generate_workflow_identifier(mmif_file)


def describe_argparser():
    """
    Returns two strings: one-line description of the argparser, and
    additional material, which will be shown in `clams --help` and
    `clams <subcmd> --help`, respectively.
    """
    oneliner = (
        'provides CLI to describe the workflow specification from a MMIF '
        'file or a collection of MMIF files.'
    )

    # get and clean docstrings
    single_doc = describe_single_mmif.__doc__.split(':param')[0]
    single_doc = textwrap.dedent(single_doc).strip()
    collection_doc = describe_mmif_collection.__doc__.split(':param')[0]
    collection_doc = textwrap.dedent(collection_doc).strip()

    additional = textwrap.dedent(f"""
    This command extracts workflow information from a single MMIF file or 
    summarizes a directory of MMIF files.
    
    ==========================
    For a single MMIF file
    ==========================
    {single_doc}

    ===============================
    For a directory of MMIF files
    ===============================
    {collection_doc}
    """)
    return oneliner, oneliner + '\n\n' + additional.strip()


def prep_argparser(**kwargs):
    parser = argparse.ArgumentParser(
        description=describe_argparser()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs
    )
    parser.add_argument(
        "MMIF_FILE",
        nargs="?",
        type=str,
        default=None if sys.stdin.isatty() else sys.stdin,
        help='input MMIF file, a directory of MMIF files, or STDIN if `-` or not provided.'
    )
    parser.add_argument(
        "-o", "--output",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help='output file path, or STDOUT if not provided.'
    )
    parser.add_argument(
        "-p", "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    return parser


def main(args):
    """
    Main entry point for the describe CLI command.

    Reads a MMIF file and outputs a JSON summary containing:
    - workflow_id: unique identifier for the source and app sequence
    - stats: view counts, annotation counts (total/per-view/per-type),
      and lists of error/warning/empty view IDs
    - views: map of view IDs to app configurations and profiling data

    :param args: Parsed command-line arguments
    """
    output = {}
    # if input is a directory
    if isinstance(args.MMIF_FILE, str) and Path(args.MMIF_FILE).is_dir():
        output = describe_mmif_collection(args.MMIF_FILE)
    # if input is a file or stdin
    else:
        # Read MMIF content
        if hasattr(args.MMIF_FILE, 'read'):
            mmif_content = args.MMIF_FILE.read()
        else:
            with open(args.MMIF_FILE, 'r') as f:
                mmif_content = f.read()

        # For file input, we need to handle the path
        # If input is from stdin, create a temp file
        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                    mode='w', suffix='.mmif', delete=False
            ) as tmp:
                tmp.write(mmif_content)
                tmp_path = Path(tmp.name)
            output = describe_single_mmif(tmp_path)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

    if output:
        if args.pretty:
            json.dump(output, args.output, indent=2)
        else:
            json.dump(output, args.output)
        args.output.write('\n')


if __name__ == "__main__":
    parser = prep_argparser()
    args = parser.parse_args()
    main(args)
