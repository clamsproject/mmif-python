# Documentation notes

Various temporary notes on the documentation. Parts of this should maybe be added to [issue #348](https://github.com/clamsproject/mmif-python/issues/348) or to a more general issue on mmif-python documentation.

Do not keep this file here forever.

--

In the [346-summarizer](https://github.com/clamsproject/mmif-python/tree/346-summarizer) branch I added one line trying to generate API documentation for the sumarizer:

```rest
.. toctree::
   :maxdepth: 4

   autodoc/mmif.serialize
   autodoc/mmif.vocabulary
   autodoc/mmif.utils
   autodoc/mmif.utils.summarizer
```

However, it looks like this needs to be done elsewhere since after `make doc` no `mmif.utils.summarizer.html` file is added to `doct-test/develop/autodoc` and we get a warning that the TOC cannot add the module.

Also note that this doesn't work for the mmif.utils.cli package either.

--

At the moment `documentation/index.rst` imports the top-level readme file. Should probably revisit that because the goal of that file is different from what we are doing here.

Update: I removed the include and wrote a shorter intro, but there is already something along those lines in `documentation/introduction.rst` so there is still some smoothing to be done here.

--

In the summarizer branch there is a markdown file in the mmif.utils.summary package, that should maby be added here as `documentation/creating-clis.rst`/

--

All the source links in the generated documentation are dead. I thought that maybe editing `documentation/conf.py` and changing the line

```python
html_show_sourcelink = True  # Furo handles this well, no need to hide
```

by setting the variable to False might work, but that was a wild guess and it did not work.

On second thought, this is probably because the source links go to pages that do not exist yet.

--

When reading the changes for a version frm the changelog file some of the typesetting does not translate well, for example in version 1.2.1 we get the raw text for the note:

```
[!NOTE] mmif describe (and the underlying mmif.utils.workflow_helper) is still experimental and subject to change in future releases without notice. Backward compatibility is not guaranteed.
```

--

Some changes already made (but not necessarily pushed up yet):

- Fixing some types and minor style errors.
- Some type setting changes.
- Refactored the way the "what's new in section X" is generated.
- Removed the Search Page link from the main page. It was leading nowhere and there is a perfectly fine search box on the left anyway.
- Updated python requirement.