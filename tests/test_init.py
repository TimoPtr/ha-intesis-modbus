# Copyright (c) 2026 Timothy (TimoPtr)
"""Tests for the Intesis Modbus integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from custom_components.intesis_modbus.const import (
    CONF_HAS_VANE,
    DOMAIN,
    MANUFACTURER,
    SCAN_INTERVAL,
)

from . import MOCK_MULTI_ENTRY_DATA, MOCK_SERIAL_ENTRY_DATA


async def test_manifest_loads(hass: HomeAssistant) -> None:
    """The integration manifest declares what the quality scale needs."""
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.quality_scale == "custom"
    assert "modbus" in integration.dependencies


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The entry loads, registers the gateway and its unit, and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    gateway, unit = dr.async_entries_for_config_entry(
        device_registry, init_integration.entry_id
    )
    assert (DOMAIN, init_integration.entry_id) in gateway.identifiers
    assert gateway.manufacturer == MANUFACTURER
    assert gateway.model == "INMBSMHI001R000"
    assert gateway.sw_version == "20"
    assert (DOMAIN, f"{init_integration.entry_id}_unit") in unit.identifiers
    assert unit.manufacturer == "Mitsubishi Heavy Industries"
    assert unit.name == "INMBSMHI001R000 air conditioner"
    assert unit.via_device_id == gateway.id
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_silent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway that does not answer puts the entry in setup retry."""
    mock_connection.for_unit(1).fail_requests(ModbusTimeoutError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_wrong_model_is_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    mock_connection: MockModbusConnection,
) -> None:
    """A gateway of another brand than the entry says is a setup error."""
    mock_connection.for_unit(1).holding[49] = 0x0801
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_temperature_format_follows_the_dip_switches(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A gateway switched to whole degrees is read in whole degrees, unprompted."""
    unit = mock_connection.for_unit(1)
    for address, value in {4: 22, 5: 20, 23: 22, 24: 30, 25: 16}.items():
        unit.holding[address] = value
    await _poll(hass, freezer)
    state = hass.states.get("climate.inmbsmhi001r000_air_conditioner")
    assert state is not None
    assert state.attributes["temperature"] == 22
    assert state.attributes["current_temperature"] == 20
    assert state.attributes["target_temp_step"] == 1
    assert not issue_registry.issues


async def test_entry_from_an_older_version_is_migrated(
    hass: HomeAssistant,
    mock_get_unit: MagicMock,
) -> None:
    """The vane moves to the options and the link settings stop being an id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0:1",
        data={**MOCK_SERIAL_ENTRY_DATA, CONF_HAS_VANE: False},
        title="INMBSMHI001R000",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id is None
    assert entry.data == MOCK_SERIAL_ENTRY_DATA
    assert entry.options == {CONF_HAS_VANE: False}
    state = hass.states.get("climate.inmbsmhi001r000_air_conditioner")
    assert state is not None
    assert "swing_modes" not in state.attributes


async def test_multi_unit_entry_from_an_older_version_is_migrated(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """An entry that never had a vane setting gets no option."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.50:502:1",
        data=MOCK_MULTI_ENTRY_DATA,
        title="INMBSMHI048O000",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.minor_version == 2
    assert entry.unique_id is None
    assert entry.data == MOCK_MULTI_ENTRY_DATA
    assert entry.options == {}


async def test_entry_from_a_newer_version_is_not_set_up(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Home Assistant does not set up an entry a newer version rewrote."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=MOCK_SERIAL_ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert mock_setup_entry.call_count == 0
