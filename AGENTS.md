# ha-intesis-modbus Agent Guide

You are helping maintain `intesis_modbus`, a Home Assistant custom integration
for Intesis INMBS Modbus air-conditioner gateways, distributed through HACS and
built on the [intesis-gw-modbus](https://github.com/TimoPtr/intesis-gw-modbus)
library. The same integration is being proposed for Home Assistant core; this
repository will be archived once the core version ships.

The project is independent of HMS Networks and Intesis; keep the README's
disclaimer and never present it as official.

## Essential commands

```bash
python3.15 -m venv .venv && .venv/bin/pip install ".[test]"
pytest                                 # 100 % coverage is enforced
mypy custom_components/intesis_modbus/ # strict
ruff check . && ruff format --check .  # select = ["ALL"], run before committing
yamllint .
```

## Layout

- `custom_components/intesis_modbus/`: the integration. `config_flow.py`
  (serial or network link, probe, model, temperature format, vane),
  `coordinator.py` (one poll per gateway every 15 seconds), `entity.py` (base
  entity, availability, write error handling, entities for indoor units that
  appear later), one module per platform (`climate`, `sensor`, `binary_sensor`,
  `number`, `switch`, `button`), `diagnostics.py`, `helpers.py`, `const.py`.
- `custom_components/intesis_modbus/brand/`: the icons HACS and Home Assistant
  show. They are the official Intesis wordmark from hms-networks.com, rendered
  in black for light themes and in its original white for the `dark_`
  variants; do not redraw or restyle it.
- `tests/`: one module per platform plus the config flow, setup and
  multi-unit gateways, with syrupy snapshots in `tests/snapshots/`.

## Development standards

- Every Python file starts with `# Copyright (c) 2026 Timothy (TimoPtr)`.
- Test-driven: write the failing test first, watch it fail, then write the
  minimal code. Keep coverage at 100 %.
- Follow Home Assistant's integration quality scale; `quality_scale.yaml`
  records every rule and must stay truthful.
- All user-facing text lives in `strings.json` (the source, which may
  reference shared keys) and `translations/en.json` (the resolved English
  text Home Assistant loads); change both together.
- The integration never opens a serial port or socket itself: links come from
  the `modbus` integration's shared connection, and register knowledge lives
  in the library. A register fact that is wrong is fixed in the library.
- Typing-only imports go under `if TYPE_CHECKING:`. A `# noqa` is acceptable
  only where a Home Assistant signature imposes it, such as an unused `hass`
  argument.

## Testing

Tests use `pytest-homeassistant`, Home Assistant's own harness, whose release
pins the matching `homeassistant` version: bump the two together with the
minimum version in `hacs.json`. The requirements of the core integrations this
one depends on (`modbus`, `usb`) are pinned in the `test` extra to what that
Home Assistant release ships. `pyproject.toml` and the manifest pin the same
`intesis-gw-modbus` release; bump them together. Everything runs against the
`modbus-connection` mock backend, so no hardware is needed. A fixture in
`tests/conftest.py` fails any test in which Home Assistant reports a
deprecated usage.

## Workflows and releases

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
