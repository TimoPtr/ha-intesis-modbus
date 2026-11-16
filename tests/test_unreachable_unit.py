# Copyright (c) 2026 Timothy (TimoPtr)
"""Tests for a single-unit gateway that cannot reach its air conditioner."""

from datetime import timedelta

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.intesis_modbus.const import SCAN_INTERVAL

COMM_ERROR_CODE = 65535

# The entities that report on the gateway itself or act on it: they keep
# working, and the error sensor is what says why the others stopped.
GATEWAY_ENTITIES = {
    "button.inmbsmhi001r000_reset_gateway",
    "number.inmbsmhi001r000_open_window_timeout",
    "sensor.inmbsmhi001r000_error",
    "sensor.inmbsmhi001r000_undervoltage_time",
    "switch.inmbsmhi001r000_block_repeated_commands",
    "switch.inmbsmhi001r000_gateway_disabled",
    "switch.inmbsmhi001r000_window_contact",
    "switch.inmbsmhi001r000_xy_bus_master",
}


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _available(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entry: MockConfigEntry
) -> set[str]:
    return {
        entity.entity_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if (state := hass.states.get(entity.entity_id)) is not None
        and state.state != STATE_UNAVAILABLE
    }


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unreachable_unit_takes_its_entities_down(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Only what belongs to the gateway stays available, until the unit is back."""
    everything = _available(hass, entity_registry, init_integration)
    assert everything > GATEWAY_ENTITIES
    unit = mock_connection.for_unit(1)
    unit.holding[11] = COMM_ERROR_CODE
    await _poll(hass, freezer)
    assert _available(hass, entity_registry, init_integration) == GATEWAY_ENTITIES
    assert hass.states.get("sensor.inmbsmhi001r000_error").state == (
        "communication_error"
    )
    unit.holding[11] = 0
    await _poll(hass, freezer)
    assert _available(hass, entity_registry, init_integration) == everything


async def test_unreachable_unit_is_logged_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Losing the unit and getting it back are each logged a single time."""
    unit = mock_connection.for_unit(1)
    unit.holding[11] = COMM_ERROR_CODE
    await _poll(hass, freezer)
    await _poll(hass, freezer)
    assert caplog.text.count("cannot reach the air conditioner") == 1
    assert "reaches the air conditioner again" not in caplog.text
    unit.holding[11] = 0
    await _poll(hass, freezer)
    await _poll(hass, freezer)
    assert caplog.text.count("reaches the air conditioner again") == 1
