import argparse
import hashlib
import json
import sys
import textwrap
from pathlib import Path
from typing import Union, List, Tuple, Optional

from mmif import Mmif


def split_appname_appversion(
    long_app_id: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Split app name and version from a long app identifier.

    Assumes the identifier looks like "uri://APP_DOMAIN/APP_NAME/APP_VERSION"

    :param long_app_id: Full app identifier URI
    :return: Tuple of (app_name, app_version), either may be None if not found
    """
    app_path = Path(long_app_id).parts
    app_name = app_path[2] if len(app_path) > 2 else None
    app_version = app_path[3] if len(app_path) > 3 else None
    if (app_version is not None and app_name is not None
            and app_name.endswith(app_version)):
        app_name = app_name[:-len(app_version) - 1]
    if app_version == 'unresolvable':
        app_version = None
    return app_name, app_version


def generate_param_hash(params: dict) -> str:
    """
    Generate MD5 hash from a parameter dictionary.

    Parameters are sorted alphabetically, joined as key=value pairs,
    and hashed using MD5. This is not for security purposes, only for
    generating consistent identifiers.

    :param params: Dictionary of parameters
    :return: MD5 hash string (32 hex characters)
    """
    if not params:
        param_string = ""
    else:
        param_list = ['='.join([k, str(v)]) for k, v in params.items()]
        param_list.sort()
        param_string = ','.join(param_list)
    return hashlib.md5(param_string.encode('utf-8')).hexdigest()


def get_pipeline_specs(mmif_file: Union[str, Path]):
    import warnings
    warnings.warn("get_pipeline_specs is deprecated, use get_workflow_specs instead", DeprecationWarning)
    return get_workflow_specs(mmif_file)


def get_workflow_specs(
    mmif_file: Union[str, Path]
) -> Tuple[
    List[Tuple[str, Optional[str], dict, Optional[str], Optional[dict], int, dict]],
    List[str], List[str], List[str]
]:
    """
    Read a MMIF file and extract the workflow specification from it.

    Extracts app configurations, profiling data, and annotation statistics
    for each contentful view. Views with errors, warnings, or no annotations
    are tracked separately.

    :param mmif_file: Path to the MMIF file
    :return: Tuple of (spec_list, error_views, warning_views, empty_views)
             where spec_list contains tuples of (view_id, app_name, configs,
             running_time_ms, running_hardware, annotation_count,
             annotations_by_type) for each contentful view, and the three
             lists contain view IDs for error/warning/empty views respectively
    """
    if not isinstance(mmif_file, (str, Path)):
        raise ValueError(
            "MMIF file path must be a string or a Path object."
        )

    with open(mmif_file, "r") as f:
        mmif_str = f.read()

    data = Mmif(mmif_str)
    spec = []
    error_views = []
    warning_views = []
    empty_views = []

    for view in data.views:
        # Track error, warning, and empty views (mutually exclusive)
        if view.has_error():
            error_views.append(view.id)
            continue
        elif view.has_warnings():
            warning_views.append(view.id)
            continue
        elif len(view.annotations) == 0:
            empty_views.append(view.id)
            continue

        app = view.metadata.get("app")
        configs = view.metadata.get("appConfiguration", {})

        # Get running time string (H:MM:SS.microseconds format)
        # Support both new (appProfiling.runningTime) and old (appRunningTime)
        running_time = None
        if "appProfiling" in view.metadata:
            profiling = view.metadata["appProfiling"]
            if isinstance(profiling, dict) and "runningTime" in profiling:
                running_time = profiling["runningTime"]
        elif "appRunningTime" in view.metadata:
            running_time = view.metadata["appRunningTime"]

        # Support both new (appProfiling.hardware) and old (appRunningHardware)
        running_hardware = None
        if "appProfiling" in view.metadata:
            profiling = view.metadata["appProfiling"]
            if isinstance(profiling, dict) and "hardware" in profiling:
                running_hardware = profiling["hardware"]
        elif "appRunningHardware" in view.metadata:
            running_hardware = view.metadata["appRunningHardware"]

        # Count annotations and group by type
        annotation_count = len(view.annotations)
        annotations_by_type = {}
        for annotation in view.annotations:
            at_type = str(annotation.at_type)
            annotations_by_type[at_type] = annotations_by_type.get(
                at_type, 0
            ) + 1

        spec.append((
            view.id, app, configs, running_time, running_hardware,
            annotation_count, annotations_by_type
        ))

    return spec, error_views, warning_views, empty_views


def generate_pipeline_identifier(mmif_file: Union[str, Path]) -> str:
    import warnings
    warnings.warn("generate_pipeline_identifier is deprecated, use generate_workflow_identifier instead", DeprecationWarning)
    return generate_workflow_identifier(mmif_file)


def generate_workflow_identifier(mmif_file: Union[str, Path]) -> str:
    """
    Generate a workflow identifier string from a MMIF file.

    The identifier follows the storage directory structure format:
    app_name/version/param_hash/app_name2/version2/param_hash2/...

    Uses view.metadata.parameters (raw user-passed values) for hashing
    to ensure reproducibility. Views with errors or warnings are excluded
    from the identifier; empty views (no annotations) are included.

    :param mmif_file: Path to the MMIF file
    :return: Workflow identifier string
    """
    if not isinstance(mmif_file, (str, Path)):
        raise ValueError(
            "MMIF file path must be a string or a Path object."
        )

    with open(mmif_file, "r") as f:
        mmif_str = f.read()

    data = Mmif(mmif_str)
    segments = []

    for view in data.views:
        # Skip views with errors or warnings
        if view.has_error() or view.has_warnings():
            continue

        app = view.metadata.get("app")
        if app is None:
            continue
        app_name, app_version = split_appname_appversion(app)

        # Use raw parameters for reproducibility
        try:
            param_dict = view.metadata.parameters
        except (KeyError, AttributeError):
            param_dict = {}

        param_hash = generate_param_hash(param_dict)

        # Build segment: app_name/version/hash
        name_str = app_name if app_name else "unknown"
        version_str = app_version if app_version else "unversioned"
        segments.append(f"{name_str}/{version_str}/{param_hash}")

    return '/'.join(segments)



def describe_argparser():
    """
    Returns two strings: one-line description of the argparser, and
    additional material, which will be shown in `clams --help` and
    `clams <subcmd> --help`, respectively.
    """
    oneliner = (
        'provides CLI to describe the workflow specification from a MMIF '
        'file.'
    )
    additional = textwrap.dedent("""
    MMIF describe extracts workflow information from a MMIF file and outputs
    a JSON summary including:

    - workflowId: unique identifier for the workflow based on apps, versions,
      and parameter hashes (excludes error/warning views)
    - stats: annotation counts (total and per-view), counts by annotation type,
      and lists of error/warning/empty view IDs
    - views: map of view IDs to app configurations and profiling data

    Views with errors or warnings are tracked but excluded from the workflow
    identifier and annotation statistics.""")
    return oneliner, oneliner + '\n\n' + additional


def prep_argparser(**kwargs):
    parser = argparse.ArgumentParser(
        description=describe_argparser()[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        **kwargs
    )
    parser.add_argument(
        "MMIF_FILE",
        nargs="?",
        type=argparse.FileType("r"),
        default=None if sys.stdin.isatty() else sys.stdin,
        help='input MMIF file path, or STDIN if `-` or not provided.'
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
    - pipeline_id: unique identifier for the pipeline
    - stats: view counts, annotation counts (total/per-view/per-type),
      and lists of error/warning/empty view IDs
    - views: map of view IDs to app configurations and profiling data

    :param args: Parsed command-line arguments
    """
    # Read MMIF content
    mmif_content = args.MMIF_FILE.read()

    # For file input, we need to handle the path
    # If input is from stdin, create a temp file
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.mmif', delete=False
    ) as tmp:
        tmp.write(mmif_content)
        tmp_path = tmp.name

    try:
        spec, error_views, warning_views, empty_views = get_workflow_specs(
            tmp_path
        )
        pipeline_id = generate_workflow_identifier(tmp_path)

        # Convert to JSON-serializable format and calculate stats
        views = {}
        annotation_count_stats = {"total": 0}
        annotation_count_by_type = {}

        for (view_id, app, configs, running_time, running_hardware,
             annotation_count, annotations_by_type) in spec:
            entry = {
                "app": app,
                "appConfiguration": configs,
            }
            # Output in new appProfiling format
            if running_time is not None or running_hardware is not None:
                profiling = {}
                if running_time is not None:
                    profiling["runningTime"] = running_time
                if running_hardware is not None:
                    profiling["hardware"] = running_hardware
                entry["appProfiling"] = profiling

            views[view_id] = entry

            # Build annotation count stats
            annotation_count_stats["total"] += annotation_count
            annotation_count_stats[view_id] = annotation_count

            # Build annotation count by type stats
            for at_type, count in annotations_by_type.items():
                if at_type not in annotation_count_by_type:
                    annotation_count_by_type[at_type] = {"total": 0}
                annotation_count_by_type[at_type]["total"] += count
                annotation_count_by_type[at_type][view_id] = count

        output = {
            "pipeline_id": pipeline_id,
            "stats": {
                "viewCount": len(views),
                "errorViews": error_views,
                "warningViews": warning_views,
                "emptyViews": empty_views,
                "annotationCount": annotation_count_stats,
                "annotationCountByType": annotation_count_by_type
            },
            "views": views
        }

        # Write output
        if args.pretty:
            json.dump(output, args.output, indent=2)
        else:
            json.dump(output, args.output)
        args.output.write('\n')
    finally:
        # Clean up temp file
        import os
        os.unlink(tmp_path)


if __name__ == "__main__":
    parser = prep_argparser()
    args = parser.parse_args()
    main(args)
