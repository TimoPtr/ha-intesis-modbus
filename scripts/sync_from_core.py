# Copyright (c) 2026 Timothy (TimoPtr)
"""
Copy the ``intesis_modbus`` integration and its tests out of a core checkout.

The integration lives in Home Assistant core (``homeassistant/components/
intesis_modbus``); this repository is a preview of it for HACS. Run this
script against a core checkout instead of editing the copied files by hand,
so the two never drift:

    python scripts/sync_from_core.py /path/to/core

It rewrites the import paths, adds the manifest keys a custom integration
needs, and adds the deprecation guard fixture to ``tests/conftest.py``.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "intesis_modbus"
TESTS = ROOT / "tests"
REPO_URL = "https://github.com/TimoPtr/ha-intesis-modbus"
EXPECTED_ARGC = 2

REWRITES = (
    ("homeassistant.components.intesis_modbus", "custom_components.intesis_modbus"),
    # Home Assistant reports every custom integration's quality scale as "custom".
    (
        'assert integration.quality_scale == "platinum"',
        'assert integration.quality_scale == "custom"',
    ),
)

CONFTEST_PREAMBLE = '''\
@pytest.fixture(autouse=True)
def fail_on_deprecated_usage(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    """
    Fail any test in which Home Assistant reports a deprecated usage.

    Core raises for these reports; for custom integrations it only logs a
    warning that is easy to miss, so treat those reports as errors here.
    """
    yield
    reports = [
        record.getMessage()
        for when in ("setup", "call")
        for record in caplog.get_records(when)
        if record.name == "homeassistant.helpers.frame"
        and record.levelno >= logging.WARNING
    ]
    if reports:
        pytest.fail("Deprecated usage reported:\\n" + "\\n".join(reports))


'''


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def _rewrite(path: Path) -> None:
    text = path.read_text()
    for old, new in REWRITES:
        text = text.replace(old, new)
    path.write_text(text)


def _patch_manifest(version: str) -> None:
    path = COMPONENT / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["documentation"] = REPO_URL
    manifest["issue_tracker"] = f"{REPO_URL}/issues"
    manifest["version"] = version
    # hassfest wants domain and name first, then the other keys sorted.
    ordered = {key: manifest.pop(key) for key in ("domain", "name")}
    ordered.update(sorted(manifest.items()))
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")


def _patch_conftest() -> None:
    path = TESTS / "conftest.py"
    text = path.read_text()
    if "import logging" not in text:
        text = text.replace(
            "from collections.abc import",
            "import logging\nfrom collections.abc import",
            1,
        )
    text = re.sub(
        r"from collections\.abc import ([^\n]+)", _add_iterator, text, count=1
    )
    marker = "\n\n\n@pytest.fixture"
    head, sep, tail = text.partition(marker)
    path.write_text(head + "\n\n\n" + CONFTEST_PREAMBLE.rstrip("\n") + sep + tail)


def _add_iterator(match: re.Match[str]) -> str:
    names = {name.strip() for name in match.group(1).split(",")}
    names.add("Iterator")
    return "from collections.abc import " + ", ".join(sorted(names))


def main(argv: list[str]) -> int:
    """Sync from the core checkout named on the command line."""
    if len(argv) != EXPECTED_ARGC:
        print(__doc__, file=sys.stderr)
        return 2
    core = Path(argv[1]).resolve()
    version = json.loads((COMPONENT / "manifest.json").read_text())["version"]
    _copy_tree(core / "homeassistant" / "components" / "intesis_modbus", COMPONENT)
    _copy_tree(core / "tests" / "components" / "intesis_modbus", TESTS)
    for path in [
        *COMPONENT.rglob("*.py"),
        *TESTS.rglob("*.py"),
        *TESTS.rglob("*.ambr"),
    ]:
        _rewrite(path)
    _patch_manifest(version)
    _patch_conftest()
    _format()
    print(f"synced from {core} at version {version}")
    return 0


def _format() -> None:
    """Re-sort imports for this repository's first-party package, if ruff is here."""
    for args in (("check", "--fix", "--quiet"), ("format", "--quiet")):
        subprocess.run(  # noqa: S603
            [sys.executable, "-m", "ruff", *args, str(COMPONENT), str(TESTS)],
            check=False,
        )


if __name__ == "__main__":
    sys.exit(main(sys.argv))
