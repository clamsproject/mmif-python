import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Dict, Type, Union, cast

from pydantic import BaseModel

from mmif.utils.cli import open_cli_io_arg

# gen_param_hash is imported for backward compatibility
from mmif.utils.workflow_helper import (
    CollectionMmifDesc,
    SingleMmifDesc,
    describe_mmif_collection,
    describe_single_mmif,
    generate_workflow_identifier,
)

models_to_help = [SingleMmifDesc, CollectionMmifDesc]
model_modules = set(model.__module__ for model in models_to_help)
def get_all_models() -> Dict[str, Type[BaseModel]]:
    return {
        name: cls for name, cls in models_to_help
    }

def get_pipeline_specs(mmif_file: Union[str, Path]):
    import warnings
    warnings.warn("get_pipeline_specs is deprecated, use mmif.utils.workflow_helper.describe_single_mmif instead",
                  DeprecationWarning)
    return describe_single_mmif(mmif_file)


def generate_pipeline_identifier(mmif_file: Union[str, Path]) -> str:
    import warnings
    warnings.warn("generate_pipeline_identifier is deprecated, use generate_workflow_identifier instead",
                  DeprecationWarning)
    return cast(str, generate_workflow_identifier(mmif_file))


def describe_argparser():
    oneliner = (
        'Describe the workflow specification from a MMIF file or a '
        'collection of MMIF files.'
    )

    additional = textwrap.dedent(f"""
    This command extracts workflow information from a single MMIF file or 
    a directory of MMIF files. The output is serialized as JSON.
    
    Use `--help-schemas` to inspect the structure of the JSON output.
    """)
    return oneliner, additional


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
        default=None,
        help='input MMIF file, a directory of MMIF files, or STDIN if `-` or not provided.'
    )
    parser.add_argument(
        "-o", "--output",
        type=str, default=None,
        help='output file path, or STDOUT if not provided.'
    )
    parser.add_argument(
        "-p", "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )
    parser.add_argument(
        "--help-schemas",
        nargs="*",
        choices=["all"] + [m.__name__ for m in models_to_help],
        metavar="SCHEMA_NAME",
        help=f"Print the JSON schema for the output. For human-readable documentation, "
             f"visit https://clams.ai/mmif-python and see the following modules: "
             f"{', '.join(model_modules)}.\nOptions: all, {', '.join([m.__name__ for m in models_to_help])}."
    )
    return parser


def main(args):
    """
    Main block for the describe CLI command.
    This function basically works as a wrapper around
    :func:`describe_single_mmif` (for single file input) or 
    :func:`describe_mmif_collection` (for directory input).
    """
    if hasattr(args, 'help_schemas') and args.help_schemas is not None:
        models_map = {m.__name__: m for m in models_to_help}
        to_show = []
        if len(args.help_schemas) == 0 or 'all' in args.help_schemas:
            to_show = models_to_help
        else:
            to_show = args.help_schemas
        
        for name in to_show:
            model_cls = models_map[name]
            schema = model_cls.model_json_schema()
            print(json.dumps(schema, indent=2))
            print()
        sys.exit(0)

    output = {}
    # if input is a directory
    if Path(str(args.MMIF_FILE)).is_dir():
        output = describe_mmif_collection(args.MMIF_FILE)
    # if input is a file or stdin
    else:
        # Read MMIF content
        with open_cli_io_arg(args.MMIF_FILE, 'r', default_stdin=True) as input_file:
            mmif_content = input_file.read()

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
        # Convert Pydantic models to dicts
        with open_cli_io_arg(args.output, 'w', default_stdin=True) as output_file:
            json.dump(output, output_file, indent=2 if args.pretty else None)
            output_file.write('\n')


if __name__ == "__main__":
    parser = prep_argparser()
    args = parser.parse_args()
    main(args)
