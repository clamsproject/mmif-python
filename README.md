## MultiMedia Interchange Format
[MMIF](https://mmif.clams.ai) is a JSON(-LD)-based data format designed for transferring annotation data between computational analysis applications in [CLAMS project](https://clams.ai). 


## mmif-python
`mmif-python` is a Python implementation of the MMIF data format. 
`mmif-python` provides various helper classes and functions to handle MMIF JSON in Python, 
including ; 

1. de-/serialization of MMIF internal data structures to/from JSON
2. validation of MMIF JSON
3. handling of CLAMS vocabulary types
4. navigation of MMIF object via various "search" methods (e.g. `mmif.get_all_views_contain(vocab_type))`)

## For more ...
* [Version history and patch notes](https://github.com/clamsproject/mmif-python/blob/main/CHANGELOG.md)
* [MMIF Python API documentation](https://clamsproject.github.io/mmif-python)
* [MMIF JSON specification and schema](https://clamsproject.github.io/mmif)
