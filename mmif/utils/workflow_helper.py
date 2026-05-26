import datetime
import hashlib
import itertools
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, overload

from pydantic import BaseModel, ConfigDict, Field

from mmif.serialize.mmif import Mmif, ViewsList


def group_views_by_app(views: ViewsList) -> List[List[Any]]:
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


def _read_mmif_from_path(mmif_input: Union[str, Path, Mmif]) -> Mmif:
    """
    Helper function to get a Mmif object from various input types.

    :param mmif_input: Either a file path (str or Path) or an existing Mmif object
    :return: Mmif object
    :raises ValueError: If input is not a valid type
    """
    if isinstance(mmif_input, Mmif):
        return mmif_input
    elif isinstance(mmif_input, (str, Path)):
        with open(mmif_input, "r") as f:
            mmif_str = f.read()
        return Mmif(mmif_str)
    else:
        raise ValueError(
            "MMIF input must be a string path, a Path object, or a Mmif object."
        )


@overload
def generate_workflow_identifier(mmif_input: Union[str, Path, Mmif], 
                                 return_param_dicts: Literal[True]
                                 ) -> Tuple[str, List[dict]]: ...


@overload
def generate_workflow_identifier(mmif_input: Union[str, Path, Mmif],
                                 return_param_dicts: Literal[False] = False
                                 ) -> str: ...


def generate_workflow_identifier(mmif_input: Union[str, Path, Mmif],
                                  return_param_dicts: bool = False
                                  ) -> Union[str, Tuple[str, List[dict]]]:
    """
    Generate a workflow identifier string from a MMIF file or object.

    The identifier follows the storage directory structure format:
    source_composition/app_name/version/param_hash/app_name2/version2/param_hash2/...

    The leading ``source_composition`` segment encodes the top-level
    document mix as ``Type-N`` pairs joined by ``-`` and sorted by type
    name (e.g. ``TextDocument-1-VideoDocument-1``).

    Uses view.metadata.parameters (raw user-passed values) for hashing
    to ensure reproducibility. Views with errors or warnings are excluded
    from the identifier; empty views are included.

    :param mmif_input: Path to MMIF file (str or Path) or a Mmif object
    :param return_param_dicts: If True, also return the parameter dictionaries
    :return: Workflow identifier string, or tuple of (identifier, param_dicts) if return_param_dicts=True
    """
    data = _read_mmif_from_path(mmif_input)
    segments = []

    # First prefix is source information, sorted by document type
    sources = Counter(doc.at_type.shortname for doc in data.documents)
    segments.append('-'.join([f'{k}-{sources[k]}' for k in sorted(sources.keys())]))

    # Group views into runs
    grouped_apps = group_views_by_app(data.views)

    param_dicts = []
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
        param_dicts.append(param_dict)

        param_hash = generate_param_hash(param_dict)

        # Build segment: app_name/version/hash
        name_str = app_name if app_name else "unknown"
        version_str = app_version if app_version else "unversioned"
        segments.append(f"{name_str}/{version_str}/{param_hash}")

    if return_param_dicts:
        return '/'.join(segments), param_dicts
    return '/'.join(segments)


## single MMIF summarization 

class SingleMmifStats(BaseModel):
    """
    Aggregated statistics for a single MMIF file.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    app_count: int = Field(..., alias="appCount", description="Total number of app executions identified.")
    error_views: List[str] = Field(default_factory=list, alias="errorViews", description="List of view IDs that contain errors.")
    warning_views: List[str] = Field(default_factory=list, alias="warningViews", description="List of view IDs that contain warnings.")
    empty_views: List[str] = Field(default_factory=list, alias="emptyViews", description="List of view IDs that contain no annotations.")
    annotation_count_by_type: Dict[str, int] = Field(default_factory=dict, alias="annotationCountByType", description="Total annotation counts across the file.")

class AppProfiling(BaseModel):
    """
    Profiling data for a single app execution.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    running_time_ms: Optional[int] = Field(default=None, alias="runningTimeMS", description="Execution time in milliseconds.")

class AppExecution(BaseModel):
    """
    Represents a single execution of an app, which may produce multiple views.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    app: str = Field(..., description="The URI of the app.")
    view_ids: List[str] = Field(..., alias="viewIds", description="List of view IDs generated by this execution.")
    app_configuration: Dict = Field(default_factory=dict, alias="appConfiguration", description="Configuration parameters used for this execution.")
    app_profiling: AppProfiling = Field(default_factory=lambda: AppProfiling(), alias="appProfiling", description="Profiling data for this execution.")
    annotation_count_by_type: Dict[str, int] = Field(default_factory=dict, alias="annotationCountByType", description="Counts of annotations produced, grouped by type.")


class SingleMmifDesc(BaseModel):
    """
    Description of a workflow extracted from a single MMIF file.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    workflow_id: str = Field(..., alias="workflowId", description="Unique identifier for the workflow structure.")
    stats: SingleMmifStats = Field(..., description="Statistics about the views and annotations.")
    apps: List[AppExecution] = Field(..., description="Sequence of app executions in the workflow.")


def _get_profile_data(view) -> AppProfiling:
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
        return AppProfiling(runningTimeMS=None)

    # the format is datetime.timedelta string, e.g. '0:00:02.345678'
    # need to convert to milliseconds integer
    time_obj = datetime.datetime.strptime(running_time_str, "%H:%M:%S.%f").time()
    milliseconds = (time_obj.hour * 3600 + time_obj.minute * 60 + time_obj.second) * 1000 + time_obj.microsecond // 1000
    return AppProfiling(runningTimeMS=milliseconds)


def describe_single_mmif(mmif_input: Union[str, Path, Mmif]) -> dict:
    """
    Reads a MMIF file or object and extracts the workflow specification from it.

    This function provides an app-centric summarization of the workflow. The
    conceptual hierarchy is that a **workflow** is a sequence of **apps**,
    and each **app** execution can produce one or more **views**. This function
    groups views that share the same ``app`` and ``metadata.timestamp`` into
    a single logical "app execution".

    .. note::
        For MMIF files generated by apps based on ``clams-python`` <= 1.3.3, all 
        views are independently timestamped. This means that even if multiple 
        views were generated by a single execution of an app, their
        ``metadata.timestamp`` values will be unique. As a result, the grouping
        logic will treat each view as a separate app execution. The change
        that aligns timestamps for views from a single app execution is
        implemented in `clams-python PR #271
        <https://github.com/clamsproject/clams-python/pull/271>`_.

    The output is a serialized :class:`~SingleMmifDesc` object.

    .. pydantic_model:: SingleMmifDesc
       :noindex:
    
    :param mmif_input: Path to MMIF file (str or Path) or a Mmif object
    :return: A dictionary containing the workflow specification.
    """
    mmif = _read_mmif_from_path(mmif_input)

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

        # Prepare annotation counts
        total_annotations_in_exec = sum(execution_ann_counter.values())
        if total_annotations_in_exec > 0:
            count_dict = dict(execution_ann_counter)
            count_dict['total'] = total_annotations_in_exec
        else:
            count_dict = {}
        
        grouped_apps.append(AppExecution(
            app=first_view.metadata.app,
            viewIds=execution_view_ids,
            appConfiguration=first_view.metadata.get("appConfiguration", {}),
            appProfiling=_get_profile_data(first_view),
            annotationCountByType=count_dict
        ))

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
        grouped_apps.append(AppExecution(
            app="http://apps.clams.ai/non-existing-app/v1",
            viewIds=sorted(list(unassigned_view_ids)),
            appConfiguration={},
            appProfiling=AppProfiling(runningTimeMS=None),
            annotationCountByType={}
        ))

    # aggregate total annotation counts
    total_annotations_by_type = Counter()
    for execution in grouped_apps:
        # Only aggregate from actual apps, not the special unassigned entry
        if execution.app != "http://apps.clams.ai/non-existing-app/v1":
            if execution.annotation_count_by_type:
                exec_counts = execution.annotation_count_by_type.copy()
                if 'total' in exec_counts:
                    del exec_counts['total']
                total_annotations_by_type.update(Counter(exec_counts))

    final_total_annotations = sum(total_annotations_by_type.values())
    final_annotation_counts = dict(total_annotations_by_type)
    if final_total_annotations > 0:
        final_annotation_counts['total'] = final_total_annotations

    return SingleMmifDesc(
        workflowId=generate_workflow_identifier(mmif, return_param_dicts=False),
        stats=SingleMmifStats(
            appCount=app_count,
            errorViews=error_view_ids,
            warningViews=warning_view_ids,
            emptyViews=empty_view_ids,
            annotationCountByType=final_annotation_counts
        ),
        apps=grouped_apps
    ).model_dump(by_alias=True)


## MMIF collection summarization 

class AppProfilingStats(BaseModel):
    """
    Aggregated profiling statistics for an app across a workflow.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    avg_running_time_ms: Optional[float] = Field(default=None, alias="avgRunningTimeMS", description="Average execution time in milliseconds.")
    min_running_time_ms: Optional[float] = Field(default=None, alias="minRunningTimeMS", description="Minimum execution time in milliseconds.")
    max_running_time_ms: Optional[float] = Field(default=None, alias="maxRunningTimeMS", description="Maximum execution time in milliseconds.")
    stdev_running_time_ms: Optional[float] = Field(default=None, alias="stdevRunningTimeMS", description="Standard deviation of execution time.")




class WorkflowAppExecution(BaseModel):
    """
    Aggregated information about an app's usage within a specific workflow across multiple files.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    app: str = Field(..., description="The URI of the app.")
    app_configuration: Dict = Field(default_factory=dict, alias="appConfiguration", description="Representative configuration (usually from the first occurrence).")
    app_profiling: AppProfilingStats = Field(default_factory=lambda: AppProfilingStats(), alias="appProfiling", description="Aggregated profiling statistics.")


class WorkflowCollectionEntry(BaseModel):
    """
    Summary of a unique workflow found within a collection.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    workflow_id: str = Field(..., alias="workflowId", description="Unique identifier for the workflow.")
    mmifs: List[str] = Field(..., description="List of filenames belonging to this workflow.")
    mmif_count: int = Field(..., alias="mmifCount", description="Number of MMIF files matching this workflow.")
    apps: List[WorkflowAppExecution] = Field(..., description="Sequence of apps in this workflow with aggregated stats.")

class MmifCountByStatus(BaseModel):
    """
    Breakdown of MMIF files in a collection by their processing status.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    total: int = Field(..., description="Total number of MMIF files found.")
    successful: int = Field(..., description="Number of files processed without errors.")
    with_errors: int = Field(..., alias="withErrors", description="Number of files containing error views.")
    with_warnings: int = Field(..., alias="withWarnings", description="Number of files containing warning views.")
    invalid: int = Field(..., description="Number of files that failed to parse as valid MMIF.")


class CollectionMmifDesc(BaseModel):
    """
    Summary of a collection of MMIF files.
    """
    model_config = ConfigDict(populate_by_name=True)
    
    mmif_count_by_status: MmifCountByStatus = Field(..., alias="mmifCountByStatus", description="Counts of MMIF files by status.")
    workflows: List[WorkflowCollectionEntry] = Field(..., description="List of unique workflows identified in the collection.")
    annotation_count_by_type: Dict[str, int] = Field(default_factory=dict, alias="annotationCountByType", description="Total annotation counts across the entire collection.")


def describe_mmif_collection(mmif_dir: Union[str, Path]) -> dict:
    """
    Reads all MMIF files in a directory and extracts a summarized workflow specification.

    This function provides an overview of a collection of MMIF files, aggregating
    statistics across multiple files.

    The output is a serialized :class:`~CollectionMmifDesc` object.

    .. pydantic_model:: CollectionMmifDesc
       :noindex:

    :param mmif_dir: Path to the directory containing MMIF files.
    :return: A dictionary containing the summarized collection specification.
    """
    import statistics
    from collections import Counter

    mmif_files = list(Path(mmif_dir).glob('*.mmif'))

    status_summary = MmifCountByStatus(
        total=len(mmif_files),
        successful=0,
        withErrors=0,
        withWarnings=0,
        invalid=0
    )

    aggregated_counts = Counter()

    # Structure: {workflow_id: {'mmifs': [...], 'apps': {app_uri: {'appConfiguration': ..., 'execution_times': [...]}}}}
    workflows_data: Dict[str, Dict] = {}

    for mmif_file in mmif_files:
        try:
            single_report = SingleMmifDesc.model_validate(describe_single_mmif(mmif_file))
        except Exception:
            status_summary.invalid += 1
            continue

        if single_report.stats.error_views:
            status_summary.with_errors += 1
            continue  # Exclude from all other stats

        # If we get here, the MMIF has no errors and is considered "successful"
        status_summary.successful += 1
        if single_report.stats.warning_views:
            status_summary.with_warnings += 1

        wf_id = single_report.workflow_id
        # Initialize workflow entry if not exists
        if wf_id not in workflows_data:
            workflows_data[wf_id] = {'mmifs': [], 'apps': {}}
        workflows_data[wf_id]['mmifs'].append(Path(mmif_file).name)

        # Aggregate annotation counts for successful mmifs
        report_counts = single_report.stats.annotation_count_by_type.copy()
        if 'total' in report_counts:
            del report_counts['total']  # don't add the sub-total to the main counter
        aggregated_counts.update(report_counts)

        for app_exec in single_report.apps:
            app_uri = app_exec.app
            # skip the special "unassigned" app
            if app_uri and app_uri != "http://apps.clams.ai/non-existing-app/v1":
                # Initialize app entry if not exists
                if app_uri not in workflows_data[wf_id]['apps']:
                    workflows_data[wf_id]['apps'][app_uri] = {
                        'appConfiguration': None,
                        'execution_times': []
                    }
                
                running_time = app_exec.app_profiling.running_time_ms
                if running_time is not None:
                    workflows_data[wf_id]['apps'][app_uri]['execution_times'].append(running_time)

                # Store the first non-empty app configuration we find for this app in this workflow
                if workflows_data[wf_id]['apps'][app_uri]['appConfiguration'] is None:
                    config = app_exec.app_configuration
                    if config:
                        workflows_data[wf_id]['apps'][app_uri]['appConfiguration'] = config

    # Process collected data into the final output format
    final_workflows_list = []
    for wf_id, wf_data in sorted(workflows_data.items()):
        workflow_apps = []

        for app_uri, app_data in sorted(wf_data['apps'].items()):
            times = app_data['execution_times']
            if times:
                profiling_stats = AppProfilingStats(
                    avgRunningTimeMS=statistics.mean(times),
                    minRunningTimeMS=min(times),
                    maxRunningTimeMS=max(times),
                    stdevRunningTimeMS=statistics.stdev(times) if len(times) > 1 else 0
                )
            else:
                profiling_stats = AppProfilingStats(
                    avgRunningTimeMS=None,
                    minRunningTimeMS=None,
                    maxRunningTimeMS=None,
                    stdevRunningTimeMS=None
                )

            workflow_apps.append(WorkflowAppExecution(
                app=app_uri,
                appConfiguration=app_data['appConfiguration'] or {},
                appProfiling=profiling_stats
            ))

        final_workflows_list.append(WorkflowCollectionEntry(
            workflowId=wf_id,
            mmifs=sorted(wf_data['mmifs']),
            mmifCount=len(wf_data['mmifs']),
            apps=workflow_apps
        ))

    # Finalize annotation counts
    final_annotation_counts = dict(aggregated_counts)
    grand_total = sum(final_annotation_counts.values())
    if grand_total > 0:
        final_annotation_counts['total'] = grand_total

    return CollectionMmifDesc(
        mmifCountByStatus=status_summary,
        workflows=final_workflows_list,
        annotationCountByType=final_annotation_counts
    ).model_dump(by_alias=True)
