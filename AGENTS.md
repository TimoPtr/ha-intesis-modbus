# ha-intesis-modbus Agent Guide

You are helping maintain the HACS preview of the `intesis_modbus` Home
Assistant integration for Intesis INMBS Modbus air-conditioner gateways. The
integration itself is developed in Home Assistant core
(`homeassistant/components/intesis_modbus`, pull request pending) on top of
the [intesis-gw-modbus](https://github.com/TimoPtr/intesis-gw-modbus)
library. This repository exists so the integration can be installed and
tested before the core version ships; it will be archived afterwards.

The project is independent of HMS Networks and Intesis; keep the README's
disclaimer and never present it as official.

## Where changes go

- `custom_components/intesis_modbus/` and `tests/` are copies of the core
  integration and its tests. Do not edit them by hand: change the core
  branch, then run `python scripts/sync_from_core.py /path/to/core`, which
  copies both trees, rewrites `homeassistant.components.intesis_modbus` to
  `custom_components.intesis_modbus`, adds the custom-integration manifest
  keys (`version`, `documentation`, `issue_tracker`) and the deprecation
  guard fixture in `tests/conftest.py`, and re-sorts imports with ruff. The
  `brand/` folder inside the component is this repository's: HACS needs the
  icons there, core keeps them in the brands repository, and the script
  carries the folder over on every sync.
- Behaviour the core version does not have (a workaround for an older Home
  Assistant, for example) is not added here either; raise the minimum
  Home Assistant version in `hacs.json` instead.
- Everything else in the repository (`scripts/`, `pyproject.toml`,
  `hacs.json`, workflows, README, this file) is owned here and follows the
  conventions below.

## Essential commands

```bash
python3.15 -m venv .venv && .venv/bin/pip install ".[test]"
pytest                                 # 100 % coverage is enforced
mypy custom_components/intesis_modbus/
ruff check . && ruff format --check .  # repository-owned files only; copied trees are exempt
yamllint .
python scripts/sync_from_core.py /path/to/core
```

Until `intesis-gw-modbus` 0.1.0 is on PyPI, `pyproject.toml` installs the
library from a pinned commit of its pull-request branch; the manifest keeps the
PyPI requirement. Switch the dependency to `==0.1.0` after the release.

Tests use `pytest-homeassistant`, Home Assistant's own harness, whose release
pins the matching `homeassistant` version: bump the two together with the
minimum version in `hacs.json`. The requirements of the core integrations this
one depends on (`modbus`, `usb`) are pinned in the `test` extra to what that
Home Assistant release ships.

## Conventions

- Repository-owned files start with `# Copyright (c) 2026 Timothy (TimoPtr)`;
  copied files keep core's headers.
- Workflows pin actions by SHA, declare the least permissions and document
  every permission with a comment; `zizmor` must stay clean.
- Renovate keeps dependencies and actions current (`renovate.json5`).
- Releases are GitHub releases tagged `vX.Y.Z` after bumping `version` in
  `custom_components/intesis_modbus/manifest.json` and `pyproject.toml`.
  HACS installs from the release tag.

## Pull requests

Keep pull requests small and focused, with the tests that prove them. A human
reviews, understands and can explain every change before it is submitted: do
not open issues or pull requests, and do not post review replies, without the
maintainer's go-ahead.
