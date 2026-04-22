# MMIF Examples

Example MMIF documents used for two purposes:

1. **Test fixtures** — loaded by `tests/mmif_examples.py` with template
   substitution against the currently installed `clams-vocabulary`.
2. **Docs source** — rendered by the `_mmif_example_builder` Sphinx
   extension (`documentation/_mmif_example_builder/`) into
   `documentation/examples.md` at docs build time, which is then
   included into the mmif-python docs site as the canonical example
   page.

## Files

- `examples.json` — ordered metadata for the docs builder. Each entry
  is `{dir, title, description}`. Adding a new example means dropping a
  new subdirectory with `raw.json` and appending an entry here.
- `<example-dir>/raw.json` — full MMIF document with `$TypeName_VER`
  and `$VERSION` template variables. Substituted at runtime by both
  consumers above so the examples automatically reflect whatever
  vocabulary versions are currently installed.
- `1.0.5-old-shortid.json` — historical MMIF sample with type URIs
  hardcoded at 1.0.5-era versions and the pre-migration
  `http://mmif.clams.ai/vocabulary/...` prefix. Used only as a
  backward-compat test fixture; **not** rendered in the docs.
  `alsoKnownAs` entries in `clams-vocabulary` resolve these URIs at
  deserialization time.
- `others/` — legacy prototype-format samples from the earliest MMIF
  drafts, kept for historical reference. Not referenced by any current
  code.

## URL convention

Current-version `raw.json` fixtures use the canonical CLAMS vocabulary
URL prefix: `http://clams.ai/vocabulary/type/TypeName/$TypeName_VER`.
The historical `1.0.5-old-shortid.json` uses the old
`http://mmif.clams.ai/vocabulary/TypeName/vN` format intentionally,
since it's testing backward compatibility with pre-migration documents.
