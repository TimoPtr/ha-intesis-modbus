# Copyright (c) 2026 Timothy (TimoPtr)
"""Diagnostics support for Intesis Modbus gateways."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST
from modbus_connection import ModbusError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import IntesisConfigEntry

TO_REDACT = {CONF_DEVICE, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: IntesisConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry: the live raw register map."""
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "state": entry.state.value,
        "family": None,
        "updated": None,
        "failed": None,
        "read_error": None,
        "registers": None,
    }
    # An entry that is not set up, one waiting to retry included, has no
    # runtime data: the download then says so instead of failing.
    if entry.state is not ConfigEntryState.LOADED:
        return diagnostics
    runtime_data = entry.runtime_data
    diagnostics["family"] = runtime_data.family
    try:
        diagnostics["registers"] = await runtime_data.device.async_read_raw()
    except ModbusError as err:
        diagnostics["read_error"] = type(err).__name__
    if report := runtime_data.coordinator.data:
        diagnostics["updated"] = sorted(report.updated)
        diagnostics["failed"] = {name: str(err) for name, err in report.failed.items()}
    return diagnostics
