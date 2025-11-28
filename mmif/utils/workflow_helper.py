import datetime
import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import List, Any, Tuple, Optional, Union
import itertools
from mmif import Mmif


def group_views_by_app(views: List[Any]) -> List[List[Any]]:
    """
    Groups views into app executions based on app and timestamp.

    An "app" is a set of views produced by the same app at the
    exact same timestamp.
    """
    # Filter out views that don't have a timestamp or app, as they can't be grouped.
    groupable_views = [
        v for v in views
        if v.metadata.get("app") and v.metadata.get("timestamp") is not None
    ]

    # Sort views by timestamp first, then by app URI to ensure deterministic grouping
    groupable_views.sort(key=lambda v: (v.metadata.timestamp, v.metadata.app))

    # Group by app and timestamp
    grouped_apps = []
    for key, group in itertools.groupby(groupable_views, key=lambda v: (v.metadata.app, v.metadata.timestamp)):
        grouped_apps.append(list(group))

    return grouped_apps


def _split_appname_appversion(
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


def generate_workflow_identifier(mmif_file: Union[str, Path]) -> str:
    """
    Generate a workflow identifier string from a MMIF file.

    The identifier follows the storage directory structure format:
    app_name/version/param_hash/app_name2/version2/param_hash2/...

    Uses view.metadata.parameters (raw user-passed values) for hashing
    to ensure reproducibility. Views with errors or warnings are excluded
    from the identifier; empty views are included.
    """
    if not isinstance(mmif_file, (str, Path)):
        raise ValueError(
            "MMIF file path must be a string or a Path object."
        )

    with open(mmif_file, "r") as f:
        mmif_str = f.read()

    data = Mmif(mmif_str)
    segments = []

    # First prefix is source information, sorted by document type
    sources = Counter(doc.at_type.shortname for doc in data.documents)
    segments.append('-'.join([f'{k}-{sources[k]}' for k in sorted(sources.keys())]))

    # Group views into runs
    grouped_apps = group_views_by_app(data.views)

    for app_execution in grouped_apps:
        # Use the first view in the run as representative for metadata
        first_view = app_execution[0]

        # Skip runs where the representative view has errors or warnings
        if first_view.has_error() or first_view.has_warnings():
            continue

        app = first_view.metadata.get("app")
        if app is None:
            continue
        app_name, app_version = _split_appname_appversion(app)

        # Use raw parameters from the first view for reproducibility
        try:
            param_dict = first_view.metadata.parameters
        except (KeyError, AttributeError):
            param_dict = {}

        param_hash = generate_param_hash(param_dict)

        # Build segment: app_name/version/hash
        name_str = app_name if app_name else "unknown"
        version_str = app_version if app_version else "unversioned"
        segments.append(f"{name_str}/{version_str}/{param_hash}")

    return '/'.join(segments)


def _get_profile_data(view) -> dict:
    """
    Extract profiling data from a view's metadata.

    :param view: MMIF view object
    :return: Dictionary of profiling data
    """
    # TODO (krim @ 2025-11-27): the GPU part is heavily rely on how clams-python implements _cuda_memory_to_str funct
    # also it's not clear how helpful vram usage in the describe output is
    # So I'm not using vram records here. Perhaps should `describe` be moved to clams-python instead?

    # running time can be found two ways: either in appProfiling.runningTime or appRunningTime (legacy) key
    profiling = view.metadata.get("appProfiling", {})
    if "runningTime" not in profiling:
        running_time_str = view.metadata.get("appRunningTime")
    else:
        running_time_str = profiling.get("runningTime")

    if running_time_str is None:
        return {}

    # the format is datetime.timedelta string, e.g. '0:00:02.345678'
    # need to convert to milliseconds integer
    time_obj = datetime.datetime.strptime(running_time_str, "%H:%M:%S.%f").time()
    milliseconds = (time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second) * 1000 + time_obj.microsecond // 1000
    return {"runningTimeMS": milliseconds}


def describe_single_mmif(mmif_file: Union[str, Path]) -> dict:
    """
    Reads a MMIF file and extracts the workflow specification from it.

    This function provides an app-centric summarization of the workflow. The
    conceptual hierarchy is that a **workflow** is a sequence of **apps**,
    and each **app** execution can produce one or more **views**. This function
    groups views that share the same ``app`` and ``metadata.timestamp`` into
    a single logical "app execution".

    .. note::
        For MMIF files generated by ``clams-python`` <= 1.3.3, all views
        are independently timestamped. This means that even if multiple views
        were generated by a single execution of an app, their
        ``metadata.timestamp`` values will be unique. As a result, the grouping
        logic will treat each view as a separate app execution. The change
        that aligns timestamps for views from a single app execution is
        implemented in `clams-python PR #271
        <https://github.com/clamsproject/clams-python/pull/271>`_.

    The output format is a dictionary with the following keys:

    * ``workflowId``: A unique identifier for the workflow, based on the
      sequence of app executions (app, version, parameter hashes). App
      executions with errors are excluded from this identifier. App
      executions with warnings are still considered successful for the purpose of this identifier.
    * ``stats``:
        * ``appCount``: Total number of identified app executions.
        * ``errorViews``: A list of view IDs that reported errors.
        * ``warningViews``: A list of view IDs that reported warnings.
        * ``emptyViews``: A list of view IDs that contain no annotations.
        * ``annotationCountByType``: A dictionary mapping each annotation
          type to its count, plus a ``total`` key for the sum of all
          annotations across all app executions.
    * ``apps``: A list of objects, where each object represents one app
      execution. It includes metadata, profiling, and aggregated statistics
      for all views generated by that execution. A special entry for views
      that could not be assigned to an execution will be at the end of the list.

    ---
    The docstring above is used to generate help messages for the CLI command.
    Do not remove the triple-dashed lines.

    :param mmif_file: Path to the MMIF file
    :return: A dictionary containing the workflow specification.
    """
    if not isinstance(mmif_file, (str, Path)):
        raise ValueError(
            "MMIF file path must be a string or a Path object."
        )

    workflow_id = generate_workflow_identifier(mmif_file)
    with open(mmif_file, "r") as f:
        mmif_str = f.read()

    mmif = Mmif(mmif_str)

    error_view_ids = []
    warning_view_ids = []
    empty_view_ids = []

    # Generate the new "apps" list
    grouped_apps = []
    processed_view_ids = set()
    view_groups = group_views_by_app(mmif.views)
    for group in view_groups:
        first_view = group[0]
        # skip executions with errors or warnings
        if first_view.has_error() or first_view.has_warnings():
            continue

        execution_ann_counter = Counter()
        for view in group:
            if len(view.annotations) == 0:
                empty_view_ids.append(view.id)
            execution_ann_counter.update(Counter(str(ann.at_type) for ann in view.annotations))

        execution_view_ids = [v.id for v in group]
        processed_view_ids.update(execution_view_ids)

        app_data = {
            "app": first_view.metadata.app,
            "viewIds": execution_view_ids,
            "appConfiguration": first_view.metadata.get("appConfiguration", {}),
            "appProfiling": _get_profile_data(first_view),
        }
        total_annotations_in_exec = sum(execution_ann_counter.values())
        if total_annotations_in_exec > 0:
            app_data['annotationCountByType'] = dict(execution_ann_counter)
            app_data['annotationCountByType']['total'] = total_annotations_in_exec
        grouped_apps.append(app_data)

    # Handle unassigned and problematic views
    all_view_ids = set(v.id for v in mmif.views)

    for view in mmif.views:
        if view.id not in processed_view_ids:
            if view.has_error():
                error_view_ids.append(view.id)
            elif view.has_warnings():
                warning_view_ids.append(view.id)
            elif len(view.annotations) == 0:
                empty_view_ids.append(view.id)

    unassigned_view_ids = all_view_ids - processed_view_ids - set(error_view_ids) - set(warning_view_ids)

    # Store app_count before potentially adding the special entry
    app_count = len(grouped_apps)

    if unassigned_view_ids:
        grouped_apps.append({
            "app": "http://apps.clams.ai/non-existing-app/v1",
            "viewIds": sorted(list(unassigned_view_ids))
        })

    # aggregate total annotation counts
    total_annotations_by_type = Counter()
    for execution in grouped_apps:
        # Only aggregate from actual apps, not the special unassigned entry
        if execution.get('app') != "http://apps.clams.ai/non-existing-app/v1":
            if 'annotationCountByType' in execution:
                exec_counts = execution['annotationCountByType'].copy()
                del exec_counts['total']
                total_annotations_by_type.update(Counter(exec_counts))

    final_total_annotations = sum(total_annotations_by_type.values())
    final_annotation_counts = dict(total_annotations_by_type)
    if final_total_annotations > 0:
        final_annotation_counts['total'] = final_total_annotations

    return {
        "workflowId": workflow_id,
        "stats": {
            "appCount": app_count,
            "errorViews": error_view_ids,
            "warningViews": warning_view_ids,
            "emptyViews": empty_view_ids,
            "annotationCountByType": final_annotation_counts
        },
        "apps": grouped_apps
    }


def describe_mmif_collection(mmif_dir: Union[str, Path]) -> dict:
    """
    Reads all MMIF files in a directory and extracts a summarized workflow specification.

    This function provides an overview of a collection of MMIF files, aggregating
    statistics across multiple files.

    The output format is a dictionary with the following keys:

    * ``mmifCountByStatus``: A dictionary summarizing the processing status of
      all MMIF files in the collection. It includes:
        * ``total``: Total number of MMIF files found.
        * ``successful``: Number of MMIF files processed without errors (may contain warnings).
        * ``withErrors``: Number of MMIF files containing app executions that reported errors.
        * ``withWarnings``: Number of MMIF files containing app executions that reported warnings.
        * ``invalid``: Number of files that failed to be parsed as valid MMIF.
    * ``workflows``: A list of "workflow" objects found in the "successful" MMIF files (files with errors
        are excluded), where each object contains:
        * ``workflowId``: The unique identifier for the workflow.
        * ``apps``: A list of app objects, each with ``app`` (name+ver identifier),
          ``appConfiguration``, and ``appProfiling`` statistics (avg, min, max, stdev running times)
          aggregated per workflow.
        * ``mmifs``: A list of MMIF file basenames belonging to this workflow.
        * ``mmifCount``: The number of MMIF files in this workflow.
    * ``annotationCountByType``: A dictionary aggregating annotation counts
      across the entire collection. It includes a ``total`` key for the grand
      total, plus integer counts for each individual annotation type.

    ---
    The docstring above is used to generate help messages for the CLI command.
    Do not remove the triple-dashed lines.

    :param mmif_dir: Path to the directory containing MMIF files.
    :return: A dictionary containing the summarized collection specification.
    """
    import statistics
    from collections import defaultdict, Counter

    mmif_files = list(Path(mmif_dir).glob('*.mmif'))

    status_summary = defaultdict(int)
    status_summary['total'] = len(mmif_files)
    status_summary['successful'] = 0
    status_summary['withErrors'] = 0
    status_summary['withWarnings'] = 0
    status_summary['invalid'] = 0

    aggregated_counts = Counter()

    workflows_data = defaultdict(lambda: {
        'mmifs': [],
        'apps': defaultdict(lambda: {
            'appConfiguration': None,  # Store the first config here
            'execution_times': []
        })
    })

    for mmif_file in mmif_files:
        try:
            single_report = describe_single_mmif(mmif_file)
        except Exception as e:
            status_summary['invalid'] += 1
            continue

        if single_report['stats']['errorViews']:
            status_summary['withErrors'] += 1
            continue  # Exclude from all other stats

        # If we get here, the MMIF has no errors and is considered "successful"
        status_summary['successful'] += 1
        if single_report['stats']['warningViews']:
            status_summary['withWarnings'] += 1

        wf_id = single_report['workflowId']
        workflows_data[wf_id]['mmifs'].append(Path(mmif_file).name)

        # Aggregate annotation counts for successful mmifs
        report_counts = single_report['stats'].get('annotationCountByType', {})
        if 'total' in report_counts:
            del report_counts['total']  # don't add the sub-total to the main counter
        aggregated_counts.update(report_counts)

        for app_exec in single_report.get('apps', []):
            app_uri = app_exec.get('app')
            # skip the special "unassigned" app
            if app_uri and app_uri != "http://apps.clams.ai/non-existing-app/v1":
                running_time = app_exec.get('appProfiling', {}).get('runningTimeMS')
                if running_time is not None:
                    workflows_data[wf_id]['apps'][app_uri]['execution_times'].append(running_time)

                # Store the first non-empty app configuration we find for this app in this workflow
                if workflows_data[wf_id]['apps'][app_uri]['appConfiguration'] is None:
                    config = app_exec.get('appConfiguration', {})
                    if config:
                        workflows_data[wf_id]['apps'][app_uri]['appConfiguration'] = config

    # Process collected data into the final output format
    final_workflows_list = []
    for wf_id, wf_data in sorted(workflows_data.items()):
        workflow_object = {
            'workflowId': wf_id,
            'mmifs': sorted(wf_data['mmifs']),
            'mmifCount': len(wf_data['mmifs']),
            'apps': []
        }

        for app_uri, app_data in sorted(wf_data['apps'].items()):
            times = app_data['execution_times']
            if times:
                profiling_stats = {
                    'avgRunningTimeMS': statistics.mean(times),
                    'minRunningTimeMS': min(times),
                    'maxRunningTimeMS': max(times),
                    'stdevRunningTimeMS': statistics.stdev(times) if len(times) > 1 else 0
                }
            else:
                profiling_stats = {}

            app_object = {
                'app': app_uri,
                'appConfiguration': app_data['appConfiguration'] or {},  # Default to empty dict
                'appProfiling': profiling_stats
            }
            workflow_object['apps'].append(app_object)

        final_workflows_list.append(workflow_object)

    # Finalize annotation counts
    final_annotation_counts = dict(aggregated_counts)
    grand_total = sum(final_annotation_counts.values())
    if grand_total > 0:
        final_annotation_counts['total'] = grand_total

    return {
        'mmifCountByStatus': dict(status_summary),
        'workflows': final_workflows_list,
        'annotationCountByType': final_annotation_counts
    }