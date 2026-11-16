# Copyright (c) 2026 Timothy (TimoPtr)
"""Config flow for the Intesis Modbus integration."""

import logging
from typing import TYPE_CHECKING, Any, override

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from intesis_gw_modbus import (
    MODELS,
    GatewayFamily,
    GatewayModel,
    GatewayProbe,
    async_probe_gateway,
)
from modbus_connection import (
    ModbusError,
)

from .const import (
    CONF_BAUDRATE,
    CONF_FRAMING,
    CONF_HAS_VANE,
    CONF_MODEL,
    CONF_TEMPERATURE_FORMAT,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    FRAMING_RTU_OVER_TCP,
    FRAMING_TCP,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params, link_match

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

STEP_MODEL = "model"
STEP_FEATURES = "features"
STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

NO_PROBE = GatewayProbe(
    device_id=None,
    model=None,
    unsupported_brand=None,
    temperature_format=None,
    vane_reported=False,
)

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)
BAUDRATE_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
    probatio.Coerce(int),
)

STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): BAUDRATE_SELECTOR,
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
        probatio.Required(CONF_FRAMING, default=FRAMING_TCP): SelectSelector(
            SelectSelectorConfig(
                options=[FRAMING_TCP, FRAMING_RTU_OVER_TCP],
                translation_key="framing",
                mode=SelectSelectorMode.LIST,
            )
        ),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): BAUDRATE_SELECTOR,
    }
)

STEP_MODEL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_MODEL): SelectSelector(
            SelectSelectorConfig(
                options=sorted(MODELS), mode=SelectSelectorMode.DROPDOWN
            )
        ),
    }
)

STEP_FEATURES_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_HAS_VANE, default=True): BooleanSelector()}
)


async def _async_probe(hass: HomeAssistant, data: dict[str, Any]) -> GatewayProbe:
    """Ask the gateway behind the link who it is, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        return await async_probe_gateway(unit)


class IntesisModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Intesis Modbus config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow."""
        self._link: dict[str, Any] = {}
        self._link_form: tuple[str, str, probatio.Schema] | None = None
        self._probe = NO_PROBE
        self._pending: dict[str, Any] = {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the gateway is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_SERIAL, TYPE_TCP]
        )

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a gateway reached over a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a gateway reached over the network."""
        return await self._async_step_link(
            TYPE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Let the user pick how the gateway is reached from now on."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=[STEP_RECONFIGURE_SERIAL, STEP_RECONFIGURE_TCP],
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this gateway over a serial port from now on."""
        return await self._async_step_link(
            STEP_RECONFIGURE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reach this gateway over the network from now on."""
        return await self._async_step_link(
            STEP_RECONFIGURE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the gateway behind them."""
        self._link_form = (step_id, connection_type, schema)
        errors: dict[str, str] = {}
        if user_input is not None:
            self._link = {CONF_TYPE: connection_type, **user_input}
            if self.source != SOURCE_RECONFIGURE:
                self._async_abort_entries_match(link_match(self._link))
            try:
                self._probe = await _async_probe(self.hass, self._link)
            except HomeAssistantError:
                errors["base"] = "device_in_use"
            except ModbusError:
                errors["base"] = "cannot_connect"
            else:
                if (brand := self._probe.unsupported_brand) is not None:
                    return self.async_abort(
                        reason="unsupported_brand",
                        description_placeholders={"brand": brand},
                    )
                if (model := self._probe.model) is None:
                    return await self.async_step_model()
                if self._is_starting(model):
                    errors["base"] = "gateway_starting"
                else:
                    return await self._async_finish(model)
        return self._async_show_link_form(user_input, errors)

    def _async_show_link_form(
        self, user_input: dict[str, Any] | None, errors: dict[str, str]
    ) -> ConfigFlowResult:
        """Show the link form the user came through, with what they entered."""
        if TYPE_CHECKING:
            assert self._link_form is not None
        step_id, connection_type, schema = self._link_form
        suggested = user_input
        if suggested is None and self.source == SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            if entry.data[CONF_TYPE] == connection_type:
                suggested = dict(entry.data)
            else:
                suggested = {CONF_UNIT_ID: entry.data[CONF_UNIT_ID]}
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    def _is_starting(self, model: GatewayModel) -> bool:
        """
        Whether a single-unit gateway reports no values yet.

        Its temperature format is detected from the setpoint it reports, so it
        cannot be set up until it does.
        """
        return (
            model.family is GatewayFamily.SINGLE_UNIT
            and self._probe.temperature_format is None
        )

    async def async_step_model(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which gateway this is when its registers do not say."""
        errors: dict[str, str] = {}
        if user_input is not None:
            model = MODELS[user_input[CONF_MODEL]]
            probed = self._probe.device_id
            if (
                model.family is GatewayFamily.SINGLE_UNIT
                and probed is not None
                and model.brand.device_id != probed
            ):
                errors["base"] = "wrong_model"
            elif self._is_starting(model):
                # Only the link step probes the gateway, so the retry starts there
                return self._async_show_link_form(
                    {k: v for k, v in self._link.items() if k != CONF_TYPE},
                    {"base": "gateway_starting"},
                )
            else:
                return await self._async_finish(model)
        return self.async_show_form(
            step_id=STEP_MODEL, data_schema=STEP_MODEL_DATA_SCHEMA, errors=errors
        )

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """
        Confirm what the unit behind the gateway can do.

        The gateway has no capability register for the vane, so the probe's
        hint only pre-fills the answer.
        """
        if user_input is not None:
            return self._async_create_or_update(
                self._pending, {CONF_HAS_VANE: user_input[CONF_HAS_VANE]}
            )
        if self.source == SOURCE_RECONFIGURE:
            has_vane = self._get_reconfigure_entry().options.get(CONF_HAS_VANE, True)
        else:
            has_vane = self._probe.vane_reported
        return self.async_show_form(
            step_id=STEP_FEATURES,
            data_schema=self.add_suggested_values_to_schema(
                STEP_FEATURES_DATA_SCHEMA, {CONF_HAS_VANE: has_vane}
            ),
        )

    async def _async_finish(self, model: GatewayModel) -> ConfigFlowResult:
        """Finish a multi-unit gateway, or ask what a single unit can do."""
        data = {**self._link, CONF_MODEL: model.name}
        if model.family is not GatewayFamily.SINGLE_UNIT:
            return self._async_create_or_update(data, {})
        fmt = self._probe.temperature_format
        if TYPE_CHECKING:
            assert fmt is not None
        self._pending = {**data, CONF_TEMPERATURE_FORMAT: fmt.value}
        return await self.async_step_features()

    def _async_create_or_update(
        self, data: dict[str, Any], options: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create the entry, or update the one being reconfigured."""
        title = data[CONF_MODEL]
        match = link_match(data)
        if self.source != SOURCE_RECONFIGURE:
            # Another flow for the same gateway may have finished meanwhile
            self._async_abort_entries_match(match)
            return self.async_create_entry(title=title, data=data, options=options)
        entry = self._get_reconfigure_entry()
        if data[CONF_MODEL] != entry.data[CONF_MODEL]:
            return self.async_abort(reason="wrong_device")
        for other in self._async_current_entries():
            if other.entry_id != entry.entry_id and all(
                other.data.get(key) == value for key, value in match.items()
            ):
                return self.async_abort(reason="already_configured")
        return self.async_update_reload_and_abort(
            entry, data=data, options=options, title=title
        )
