# Intesis Modbus for Home Assistant

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=ha-intesis-modbus&owner=timoptr)

Home Assistant custom integration for [Intesis](https://www.intesis.com) INMBS Modbus gateways, the boxes that put an air conditioner's indoor unit on a Modbus RTU or TCP bus. It exposes the unit as a climate entity, with sensors for the temperatures and status the gateway reports and controls for the gateway's own settings.

## This is a preview of a core integration

The same integration is being proposed for Home Assistant core as `intesis_modbus`. This repository publishes it through HACS so it can be installed and tested before the core version ships.

Once the core integration is released, uninstall this one and restart Home Assistant. The domain is the same, so your gateways and entities carry over. This repository will then be archived.

## Disclaimer

This is an independent, community project. It is not affiliated with, endorsed by or supported by HMS Networks, Intesis or any air-conditioner manufacturer; Intesis and the gateway part numbers are their trademarks and are used only to identify the hardware. The register maps come from the public user manuals.

This integration was built with the help of [Claude](https://claude.ai) (Anthropic).

## Supported gateways

| Gateway | Family | Status |
| --- | --- | --- |
| INMBSMHI001R000 (Mitsubishi Heavy Industries, Modbus RTU) | single unit | Modelled from the manual (r6.4), verified against a Modbus simulator |
| INMBSMHI048O000, INMBSMHI128O000 (Mitsubishi Heavy Industries, Modbus RTU or TCP) | multi unit | Modelled from the manual (r1.0), verified against a Modbus simulator only |

The other brands' single-unit gateways (INMBSDAI001R000, INMBSPAN001R000, INMBSTOS001R000, INMBSLGE001R000, INMBSHIT001R000, INMBSSAM001R000) share the same register map. Their code and error tables are not written yet, so setup aborts with a message naming the brand; the [intesis-gw-modbus](https://github.com/TimoPtr/intesis-gw-modbus) library explains how to contribute one.

## Requirements

- Home Assistant 2026.11.0 or newer
- The [intesis-gw-modbus](https://github.com/TimoPtr/intesis-gw-modbus) Python library ([PyPI](https://pypi.org/project/intesis-gw-modbus/), installed automatically)
- For a single-unit gateway: an RS-485 adapter on the Home Assistant host, or a serial server on the network that forwards the RS-485 line byte for byte
- For a multi-unit gateway: its Ethernet port, or an RS-485 adapter

## Installation

### HACS (recommended)

Click the badge above to open your Home Assistant instance with this repository pre-filled, or add it manually:

1. Open HACS in Home Assistant
2. Click the three dots menu (top right) > **Custom repositories**
3. Add this repository URL with category **Integration**
4. Search for "Intesis Modbus" and install
5. Restart Home Assistant

### Manual

Copy the `custom_components/intesis_modbus` folder into your Home Assistant `config/custom_components/` directory and restart.

## Wiring

A single-unit gateway speaks Modbus RTU over its EIA-485 port. Wire it to an RS-485 adapter on the Home Assistant host, or to a serial server on the network that forwards the line byte for byte. Prefer the adapter's stable path under `/dev/serial/by-id/` over `/dev/ttyUSBx`, which can change after a reboot.

A multi-unit gateway has both an RS-485 port and an Ethernet port; use whichever is wired.

## Before you start: DIP switches (single-unit gateways)

The gateway's DIP switches set how it talks on the bus. Note them before setting up the integration; every change needs a power cycle of the gateway.

- **Modbus slave address** (SW3, 1 to 63; factory default 1): the *Modbus unit ID* the integration asks for.
- **Baud rate** (SW3/SW4; factory default 9600): the *baud rate* the integration asks for. The gateway always uses 8 data bits, no parity and 2 stop bits.
- **Temperature format** (SW4): degrees Celsius, tenths of a degree Celsius, or degrees Fahrenheit. The integration detects it from the gateway's setpoint register and only asks when the gateway is still starting up. Home Assistant always shows and accepts degrees Celsius whatever the switch says.
- **Termination resistor** (SW4): enable it when the gateway is at the end of the RS-485 bus.
- **XY bus role** (SW1; factory default slave): whether the gateway is the master or a slave on the air conditioner's own XY bus. As a slave it needs a Mitsubishi Heavy Industries wired remote controller on the bus acting as master. As a master it needs none, and any remote controller present must itself be set as slave. Exactly one device on the XY bus must be the master. The role does not change how the integration is set up, but it changes what the *External temperature reference* does: as master the value is applied to the indoor unit directly, as slave the gateway shifts the setpoint to compensate, so the wall remote can show a different setpoint than Home Assistant.

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **Intesis Modbus**
3. Pick **Serial** for a gateway wired to an RS-485 adapter, or **Network** for a gateway reached over TCP
4. Enter the connection details; the integration reads the gateway to identify it

| Parameter | Description |
| --- | --- |
| **Serial port** | The RS-485 adapter the gateway is wired to. |
| **Baud rate** | The speed set on the gateway's DIP switches. The Intesis default is 9600. |
| **Modbus unit ID** | The gateway's Modbus slave address, set on its DIP switches. The Intesis default is 1. |
| **Host**, **Port** | For a gateway reached over the network, its address and TCP port (502 by default). |
| **Framing** | *Modbus TCP* for a multi-unit gateway with an Ethernet port. *RTU over TCP* for a single-unit gateway behind a serial server. |
| **Gateway model** | Only asked when the gateway does not identify itself, which is the case for multi-unit gateways. |
| **Temperature format** | Only asked when it could not be detected, usually because the gateway was still initialising. Pick the format set on the SW4 DIP switches. |
| **Unit has a swing vane** | Single-unit gateways only. Pre-filled from the last vane position the gateway reported; turn it off for a unit without a motorised vane and the climate entity will not offer swing modes. |

The integration has no options. The gateway is polled every 15 seconds.

## Entities

### Climate

One climate entity per air conditioner: on/off, mode (auto, heat, dry, fan only, cool), target temperature within the limits the unit reports, fan speed (auto, low, medium, high and, where the unit has four speeds, powerful) and, when the unit has a vane, swing mode (swing or vane positions 1 to 4). The current temperature is the unit's own ambient reading. Indoor units behind a multi-unit gateway also report an HVAC action from their compressor and thermostat status.

### Sensors

Single-unit gateways: ambient temperature, applied setpoint, outdoor intake temperature, return path temperature, error (with the remote-controller code and its description as attributes) and operation time. Disabled by default: input reference temperature, minimum and maximum setpoint, undervoltage time, control lock, fan speed count. Indoor units behind a multi-unit gateway: error.

### Binary sensors

Single-unit gateways: alarm, window. Indoor units: filter sign, compressor (disabled by default). Multi-unit gateways: hardware communication.

### Numbers

Single-unit gateways: external temperature reference, the temperature the unit regulates on when you feed it one from another sensor. Disabled by default: open window timeout.

### Switches

Single-unit gateways: window contact, remote controller lock. Disabled by default: gateway disabled, block repeated commands, XY bus master. Indoor units: remote controller lock.

The *XY bus master* switch mirrors the SW1 role (register 98). Leave it alone unless you are also changing the wall remote's role: with no master left on the XY bus, the indoor unit stops answering the gateway.

### Buttons

Single-unit gateways: reset error. Disabled by default: reset gateway. Indoor units: reset filter sign, reset error.

## Data updates

The integration polls the gateway every 15 seconds, one request per documented register block. After a command it refreshes right away. If the gateway stops answering, its entities become unavailable and come back on the next successful poll.

On a multi-unit gateway, indoor units the gateway starts talking to after setup are found automatically: each poll also checks a few empty unit slots, so a unit that was off at startup appears with its own device within a few minutes. A unit the gateway stops talking to keeps its device and shows as unavailable.

## Use cases

- Control a Mitsubishi Heavy Industries indoor unit from Home Assistant without the manufacturer's cloud or a wall remote.
- Regulate on a room sensor of your choice: feed its reading to the *External temperature reference* number and the unit regulates on it instead of its own intake sensor.
- Let the gateway switch the unit off when a window opens: mirror your window sensor onto the *Window contact* switch and the gateway counts down the *Open window timeout* by itself.

## Example

Keep the unit regulating on a separate temperature sensor:

```yaml
automation:
  - alias: "Living room AC regulates on the room sensor"
    triggers:
      - trigger: state
        entity_id: sensor.living_room_temperature
        not_to:
          - unavailable
          - unknown
    actions:
      - action: number.set_value
        target:
          entity_id: number.inmbsmhi001r000_external_temperature_reference
        data:
          value: "{{ states('sensor.living_room_temperature') | float | round(1) }}"
```

## Known limitations

- Single-unit gateways do not report whether the unit is actively heating or cooling, so their climate entity has no HVAC action.
- The gateway's own bus settings (address, baud rate) are never written by the integration; change them on the DIP switches.
- The manual does not say whether the SW1 switch or a value written through the *XY bus master* switch wins after the gateway is power-cycled.
- Multi-unit gateways are modelled from the manual and have not been tested on hardware.
- Gateways are not discovered; set them up from the integrations page.

## Troubleshooting

- **The flow says the gateway answered with another device ID** — The gateway on that port is not the model you picked. Check the label and pick the matching model, or let the integration detect it.
- **Every value is unknown right after setup** — The gateway initialises for about two minutes after power-up and reports no values meanwhile; the *Error* sensor shows *Initialising*. Wait, nothing to fix.
- **The Error sensor shows a communication error with the unit** — The gateway answers on Modbus but cannot talk to the indoor unit. Check the XY bus wiring, then the bus roles: exactly one device must be the master. A gateway set as slave (SW1, the factory default) with no wall remote, or with a wall remote that is also a slave, has no master to talk to; a gateway and a remote both set as master collide.
- **Timeouts or unavailable entities** — Check the RS-485 wiring (A/B polarity), the termination resistor at the ends of the bus, the baud rate against the DIP switches, and that the gateway's address matches the unit ID. The gateway uses 2 stop bits; some adapters need that set explicitly.
- **A repair issue says the temperature format changed** — Someone moved the SW4 DIP switches. Reconfigure the gateway in Home Assistant and pick the matching format, or set the switches back and power-cycle the gateway.

## Removal

1. Go to **Settings > Devices & Services**
2. Find **Intesis Modbus** and delete its entries
3. Uninstall the integration from HACS and restart Home Assistant

## Development

```bash
python3.15 -m venv .venv && .venv/bin/pip install ".[test]"
.venv/bin/pytest          # 100 % coverage is enforced
.venv/bin/mypy custom_components/intesis_modbus/
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

Tests run on `pytest-homeassistant`, Home Assistant's own test harness, against the mock Modbus backend of `modbus-connection`; no hardware is needed.
