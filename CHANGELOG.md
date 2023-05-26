
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
