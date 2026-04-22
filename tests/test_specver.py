"""
Drift-detection tests for the bundled MMIF schema and spec version.

These tests assert that the committed ``mmif/res/mmif.json`` and the
``__specver__`` string match what the MMIF spec repo currently publishes.
When the spec repo releases a new version, CI goes red, prompting a
developer to re-fetch the schema and bump ``__specver__``.

Skipped gracefully when the GitHub API is unreachable (offline local
builds).
"""
import json
import subprocess

import pytest

from mmif import __specver__, get_mmif_json_schema


def _gh_api(endpoint, jq_expr='.'):
    """
    Call ``gh api`` and return parsed JSON.

    :raises pytest.skip: if ``gh`` is unavailable or the call fails
    """
    try:
        result = subprocess.run(
            ['gh', 'api', endpoint, '--jq', jq_expr],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("gh CLI not available or timed out")
    if result.returncode != 0:
        pytest.skip(f"gh api failed: {result.stderr.strip()}")
    return result.stdout.strip()


class TestSpecVersionDrift:

    def test_specver_matches_latest_remote(self):
        """
        Fail when the MMIF spec repo has a newer release than what
        we target.
        """
        raw = _gh_api('repos/clamsproject/mmif/tags', '.[].name')
        if not raw:
            pytest.skip("No tags returned from spec repo")
        tags = raw.splitlines()
        # spec tags are bare X.Y.Z (no prefix)
        versions = sorted(
            [t for t in tags if t.replace('.', '').isdigit()],
            key=lambda v: list(map(int, v.split('.'))),
        )
        if not versions:
            pytest.skip("No version tags found in spec repo")
        latest = versions[-1]
        schema_url = (
            f"https://raw.githubusercontent.com/clamsproject"
            f"/mmif/main/schema/mmif.json"
        )
        assert __specver__ == latest, (
            f"MMIF spec moved to {latest}, we target {__specver__}. "
            f"To fix:\n"
            f"  1. Update __specver__ in mmif/ver/__init__.py\n"
            f"  2. curl -sL {schema_url} -o mmif/res/mmif.json\n"
            f"  3. Commit both changes"
        )

    def test_bundled_schema_matches_remote(self):
        """
        Fail when the committed ``mmif.json`` diverges from the spec
        repo's schema at the targeted spec version.
        """
        import base64
        bundled = json.loads(get_mmif_json_schema())
        encoded = _gh_api(
            f'repos/clamsproject/mmif/contents/schema/mmif.json'
            f'?ref={__specver__}',
            '.content',
        )
        if not encoded:
            pytest.skip("Could not fetch remote schema")
        remote = json.loads(base64.b64decode(encoded))
        schema_url = (
            f"https://raw.githubusercontent.com/clamsproject"
            f"/mmif/{__specver__}/schema/mmif.json"
        )
        assert bundled == remote, (
            f"Bundled mmif/res/mmif.json differs from spec repo. "
            f"To fix:\n"
            f"  curl -sL {schema_url} -o mmif/res/mmif.json"
        )
