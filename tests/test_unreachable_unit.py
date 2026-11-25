# Copyright (c) 2026 Timothy (TimoPtr)
"""Tests for a single-unit gateway that cannot reach its air conditioner."""

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.typing import WebSocketGenerator

from custom_components.intesis_modbus.const import DOMAIN, SCAN_INTERVAL

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


def _count(caplog: pytest.LogCaptureFixture, *parts: str) -> int:
    return sum(
        all(part in record.getMessage() for part in parts) for record in caplog.records
    )


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
    # Home Assistant words and grades this line differently from 2026.12 on
    assert _count(caplog, "air conditioner", "cannot reach the air conditioner") == 1
    assert _count(caplog, "air conditioner data recovered") == 0
    unit.holding[11] = 0
    await _poll(hass, freezer)
    await _poll(hass, freezer)
    assert _count(caplog, "air conditioner data recovered") == 1


async def test_setup_with_unreachable_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway that cannot reach its unit still loads, and says why."""
    mock_connection.for_unit(1).holding[11] = COMM_ERROR_CODE
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.inmbsmhi001r000_air_conditioner").state == (
        STATE_UNAVAILABLE
    )
    assert hass.states.get("sensor.inmbsmhi001r000_error").state == (
        "communication_error"
    )


async def test_air_conditioner_device_cannot_be_removed(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Neither the gateway nor the air conditioner behind it can be removed."""
    assert await async_setup_component(hass, "config", {})
    entry_id = init_integration.entry_id
    client = await hass_ws_client(hass)
    for identifier in (entry_id, f"{entry_id}_unit"):
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, identifier), config_entry_id=entry_id
        )
        assert device is not None
        assert not (await client.remove_device(device.id))["success"]


async def test_manual_update_polls_the_gateway(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Updating an entity of the unit by hand reads the gateway right away."""
    assert await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})
    mock_connection.for_unit(1).holding[1] = 4
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "climate.inmbsmhi001r000_air_conditioner"},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("climate.inmbsmhi001r000_air_conditioner").state == "cool"
