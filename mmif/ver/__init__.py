from importlib.metadata import metadata, version

__version__ = version("mmif-python")

# Derived from the ``mmif-spec`` URL in pyproject.toml [project.urls].
# e.g., "https://mmif.clams.ai/1.1.0" → "1.1.0"
# To change the targeted spec version, update the URL in pyproject.toml,
# NOT this file.
_urls = {
    k: v for k, v in (
        u.split(", ", 1)
        for u in metadata("mmif-python").get_all("Project-URL")
    )
}
__specver__ = _urls["mmif-spec"].rstrip("/").rsplit("/", 1)[-1]
