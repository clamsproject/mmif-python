
## releasing 1.1.2 (2025-07-28)
### Overview
Patch release with a hotfix of a bug. 

### Changes
* Fixed bug with handling "list of ID" props in 1.0.x MMIF. 

## releasing 1.1.1 (2025-07-26)
### Overview
Patch release to support installation on python 3.12 and newer (fixes https://github.com/clamsproject/mmif-python/issues/314). 

### Additions
- `setup.py` is now compatible with the latest setuptools (80) .
- [Since python 3.12 no longer ship `setuptools` as a part of standard installation](https://docs.python.org/3/whatsnew/3.12.html#ensurepip), added setuptools as a `dev` dependency.

## releasing 1.1.0  (2025-07-23)
### Overview
This is a minor version release, but it includes several significant changes and improvements across the codebase. 

### Additions
* Added support for synonyms and property aliases from LAPPS type migration in MMIF spec 1.1.0 (#321).
* Migrated CLI modules from `clams-python` to `mmif` (#317).

### Changes
* Updated minimum Python version to 3.10 (#310).  
* Transitioned `Annotation.id` to a "long" form for better disambiguation as now explicitly specified in MMIF 1.1.0 (#318).
* Fixed missing ISO format conversion in timeunit helper (#315).
* Fixed issues with videodocument helper's `extract_frames_as_images` destroying input frame lists (#303). 
* Miscellaneous cleanup and improvements on documentation and unused code. 


## releasing 1.0.19 (2024-07-29)
### Overview
Patch to fix a critical bug. 

### Changes
- bugfix when `Annotation` instance and "warnings" view both are involved, MMIF is not properly returned (#299)

## releasing 1.0.18 (2024-07-15)
### Overview
Patch release with a bugfix. 

### Additions
- document location (docloc) plugins now have a common function to provide formatting guidelines (https://github.com/clamsproject/mmif-python/issues/297)
### Changes
- fixed bug when adding custom properties to a newly generated `TextDocument` object (https://github.com/clamsproject/mmif-python/issues/290)

## releasing 1.0.17 (2024-06-26)
### Overview
This release adds caching mechanism for annotation alignments (via `Alignment` annotation, the alignment via `targets` property is not yet supported). 

### Additions
- `Annotation` class now has [`.aligned_to_by(alignment: Annotation)`](https://clams.ai/mmif-python/latest/autodoc/mmif.serialize.html#mmif.serialize.annotation.Annotation.aligned_to_by) and [`.get_all_aligned()`](https://clams.ai/mmif-python/latest/autodoc/mmif.serialize.html#mmif.serialize.annotation.Annotation.get_all_aligned) method to quickly retrieve cached alignment counterparts (https://github.com/clamsproject/mmif-python/issues/285). The caching occurs 
    1. when MMIF JSON is deserialized
    2. when `view.add_annotation` or `view.new_annotation` is called

### Changes
- `mmif.utils.text_document_helper.slice_text` received a major speed boost from the alignment caching. 


## releasing 1.0.16 (2024-06-14)
### Overview
This release includes an _experimental_ implementation for helpers to slice `text_value` from text documents. 

### Additions
* `mmif.utils.text_document_helper` module to address https://github.com/clamsproject/mmif-python/issues/280


## releasing 1.0.15 (2024-06-07)
### Overview
Minor release to add/improve helper methods.

### Additions
- `video_document_helper` now has convenient helpers to grab `TimeFrame` annotations' `representative` points. (https://github.com/clamsproject/mmif-python/pull/278)

### Changes
- `Mmif.__getitem__()` now works with short annotation IDs (https://github.com/clamsproject/mmif-python/issues/279)


## releasing 1.0.14 (2024-04-10)
### Overview
This release contains small fixes and improvements. 

### Additions
- added getter helpers at various levels to access errors encoded in MMIF json in human-friendly format
    - `Mmif.get_view_with_error`
    - `Mmif.get_views_with_error`
    - `Mmif.get_last_error`
    - `View.get_error`
    - `ViewMetadata.get_error_as_text`

### Changes
- "empty" annotation property values are correctly retrievable

## releasing 1.0.13 (2024-04-02)
### Overview
This version includes small, but helpful improvements.

### Changes
* `Annotation` object now has `long_id` property that returns the cross-view reference-ready ID in `view_id:annotation_id` form
* time unit conversion is now more stable (change of rounding)
* video frame sampling can now use fractional sampling rate (in terms of frame numbers)


## releasing 1.0.12 (2024-04-01)
### Overview
Hot-fixing a wrong field name. 

### Changes
- `views[].metadata.app_configuration` is renamed to `appConfiguration`, correctly following the MMIF json schema. 


## releasing 1.0.11 (2024-03-31)
### Overview
This release includes changes from MMIF spec 1.0.3 and 1.0.4, and a new helper module to handle sequence annotations

### Additions
- `mmif.utils.sequence_helper` module (fixing https://github.com/clamsproject/mmif-python/issues/267) is added to provide 
    - a generalized label re-mapper for "post-binning" of labels
    - conversion from a list of CLAMS annotations (with ``classification`` props) into a list of reals (scores by labels), can be combined with the label re-mapper mentioned above
    - `smooth_outlying_short_intervals()`: a simple smoothing algorithm by trimming "short" outlier sequences
- added support for the new `views[].metadata.appConfiguration` field (https://github.com/clamsproject/mmif/issues/208 & https://github.com/clamsproject/mmif-python/issues/269)

### Changes
- fixed querying views by strings of annotation types weren't working (https://github.com/clamsproject/mmif-python/issues/263)
- added annotation type prop aliases added in MMIF 1.0.3 (https://github.com/clamsproject/mmif/pull/222)
- getting start or end anchor points on annotations objects only with `targets` are no longer require the targets list is already sorted
- sphinx-based public API documentation for old versions is back

## releasing 1.0.10 (2024-03-01)
### Overview
This version includes minor bug fixes and support for MMIF spec 1.0.2. 

### Additions
* support for _aliases_ for annotation properties. This is due to MMIF spec 1.0.2's introduction of the general `label` property that replaces `frameType` and `boxType` properties  in `TimeFrame` and `BoundingBox` respectively. Specifically, for example, the value of `label` or `frameType` property of a `TimeFrame` annotation object is accessible either via `timeframe.get_property("label")` or `timeframe.get_property("frameType")`. **This is primarily only for backward-compatibility** , and for the future, using `frameType`/`boxType` is NOT recommended in preference to the more general `label` property. 

### Changes
* The `mmif-python` SDK website no longer holds API docs for old versions.
* ISO-like time unit conversion now consistently returns only to third decimal place.


## releasing 1.0.9 (2024-02-10)
### Overview
This is a feature-packed release.

### Additions
* Based on MMIF 1.0.1 
* Added a default handler for `http://`/`https://` document locations
* Added `get_start` and `get_end` methods to `Mmif` class to help getting start and end points of `Interval` and `Timepoint` vocabulrary types (https://github.com/clamsproject/mmif-python/issues/253)
* Added a conversion helper for ISO-format time strings (https://github.com/clamsproject/mmif-python/issues/258)

### Changes
* Fixed `Document.text_value()` was only working with `file://` location (https://github.com/clamsproject/mmif-python/issues/246)
* `Annotation` objects' `properties` attribute is no longer limited to primitives and list of primitives (https://github.com/clamsproject/mmif/issues/215)
* Fixed annotation URI equivalence checker wasn't working in set-like collections (https://github.com/clamsproject/mmif-python/issues/257)

## releasing 1.0.8 (2023-07-24)
### Overview
This release includes polishing and bug fixes around the `mmif.utils.video_document_helper` module.

### Changes
* API documentation for the module is now included in the public documentation website (#242) 
* when opening a video file using `vdhelper.capture` function, an error is now raised the video file is not found in the local file system (#243)
* `frameCount` and `duration` of a video are recorded as document properties #244)
* `Annotation.get_property` now provide more intuitive access to "view-level" annotation properties found in `view.metadata.contains.some_at_type` dict 


## releasing 1.0.7 (2023-07-20)
### Overview
Minor updates in VideoDucment helper module

### Additions
* when a VideoDocument is open, the total duration of the video is now recorded as a document property.



## releasing 1.0.6 (2023-07-19)
### Overview
This release relaxes checks for optional CV dependencies in video utils module, so that users don't have install all of `[cv]` dependencies when they don't use them all. 

### Changes
* when any of `[cv]` dependencies is not found during `mmif.utils.video_document_helper` module is being loaded, instead of raising and an error, a warning is issued.


## releasing 1.0.5 (2023-07-19)
### Overview
This release contains a minor fix in video_document_helper module

### Changes
* fixed time unit normalization was missing some important string


## releasing 1.0.4 (2023-07-19)
### Overview
This release fixes installation error in the previous version. 


## releasing 1.0.3 (2023-07-19)
### Overview
This release is primarily about adding `mmif.utils` package and `mmif.utils.video_document_helper` module. The module provides many helper functions to handle frame-based and time-based documents and annotations. 

### Additions
* `mmif.utils` package and `mmif.utils.video_document_helper` module (#233) 

### Changes
* dropped support for `mmif-utils-` plugins (#230)
* fixed bug in `Annotation.get_property` (#232)


## releasing 1.0.2 (2023-07-11)
### Overview
This release includes support for plugins, and a "magic" helper for using `Annotation` annotations for documents in MMIF. 

### Additions
* a "magic" helper to automatically generate the "capital" `Annotation` annotations when an app adds properties to `Document` objects using `Document.add_property()` method. (#226)
* support for `mmif-docloc-` plugins for arbitrary URI scheme in `Document.location` property. (#222)
* (EXPERIMENTAL) support for `mmif-utils-` plugins for monkeypatching `MmifObject` classes (#224)



## releasing 1.0.1 (2023-05-26)
### Overview
`mmif-python` 1.0.0 included MMIF 0.5.0 instead of  MMIF 1.0.0. This release fixes it

### Changes
* now based on MMIF specification 1.0.0

## releasing 1.0.0 (2023-05-25)
### Overview
This release will be numbered as 1.0.0, but actually is re-numbering of 0.5.2, hence no technical changes are included in 1.0.0. 


## releasing 0.5.2 (2023-05-19)
### Overview
This release fixes an oversight bug in `__eq__` in `MmifObject`s. Also includes updates of the sphinx documentation. 

### Changes
* Fixed bug some fields must be ignored when computing differences in  `__eq__` (#214 )
* Updated sphinx documentation (#215 )


## releasing 0.5.1 (2023-05-02)
### Overview
This release includes "fuzzy" matching of at_types and sanitized `serialize` of `Mmif` objects.

### Additions
* CLAMS vocab type subclasses now support "fuzzy" `__eq__` check (#209 . Fuzzy matching will ignore differences in versions of two at_types, but still issue python warnings when there's a version mismatch. By default, all CLAMS vocab type subclasses are initiated with fuzzy mode "on". 
* `Mmif. serialize` now supports sanitizing the output JSON (#205) . Can be turned on by passing `sanitize=True` argument. Sanitizing will perform 
    * removal of non-existing annotation types from `contains` metadata    
    * validating output using built-in MMIF jsonschema
    

### Changes
* fixed a small bug in `Mmif.get_alignments` 
* fixed `view.metadata` serialized into an invalid MMIF due to a *oneOf* condition in jsonschema

## releasing 0.5.0 (2023-04-30)
### Overview
This release is a synchronization of `mmif-python` with the latest [MMIF 0.5.0 release](https://github.com/clamsproject/mmif/pull/199). 

### Changes
* Enum-like subclasses for annotation `@type`s in the `mmif.vocabulary` package are updated to accommodate the new way of checking I/O compatibility (as `__eq__()` in the SDK).


## releasing 0.4.8 (2023-02-10)
This is a small PR that doesn't include any code in the SDK, but the target MMIF version is bumped up to [0.4.2](https://github.com/clamsproject/mmif/blob/master/CHANGELOG.md#version-042---2023-02-09). 

## releasing 0.4.7 (2023-02-09)
This release includes

* removed "freezing" behaviors of MMIF objects (#193)
* made `properties` map to behave like a map (#194)
* updated python dependencies (#196, #198)

## releasing 0.4.6 (2022-03-25)
This release includes 

* fixes in the development & release pipelines. (#189 #187)
* upgrade in the text retrieval from TextDocument (#185)

## releasing 0.4.5 (2021-07-11)
This release contains minor bug fixes

* fixed `view.new_annotation` wasn't adding annotation properties correctly
* fixed how `develop` version of vocab URIs were handled
* colon (`:`) is now a class constant for gluing view_id and annotation_id

## releasing 0.4.4 (2021-06-19)
This release contains small but breaking changes. See d5198cb2304ad488975644a87fba51906abc5299 for details. 


## releasing 0.4.3 (2021-06-18)
This release fixes minor bugs from the previous version.


## releasing 0.4.2 (2021-06-17)
This release adds `new_textdocument` helper method to `View` class. 

## releasing 0.4.1 (2021-06-14)
The release contains a small bug fix in deserialization of `Mmif` object. 

## releasing 0.4.0  (2021-06-10)
New release to correspond to the MMIF specification 0.4.0. 

## releasing 0.3.5 (2021-06-05)
The release includes ...

* re-designed `vocabulary` module and how `AnnotationTypes` works better with version compatibility (#64)
* automatic annotation ID generation (also #64)
* full implementation of backward (+forward?) version compatibility is WIP (#163)
* various bug fixes and clean-up


## releasing 0.3.4 (2021-05-24)
This release includes major bug fixes (#131, #164) and a new documentation generation pipeline (#167). 

## releasing 0.3.3 (2021-05-12)
This release contains various bug fixes. 

## releasing 0.3.2 (2021-05-12)
A version to match changes in the specification 0.3.1. 

## releasing 0.3.1 (2021-03-30)
0.3.1 contains mostly small bugfixes.


## release candidate for 0.3.0 (2021-03-14)
release note for mmif-python 0.3.0

* new in specification: added support for `parameters` 
* new in specification: file paths are now stored as `file://` URIs
* bugfix: added type restrictions to annotation properties
