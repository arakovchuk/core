"""Support for DaikinNA Cloud climate systems."""

from typing import Any

from homeassistant.components.climate import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import _LOGGER, DOMAIN

# from . import DaikinData
from .daikincloud import DaikinCloud, DaikinDevice, DaikinInstallation


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Daikin device."""
    cloud: DaikinCloud = hass.data[DOMAIN][entry.entry_id]
    _LOGGER.debug("Initializing Daikin climate devices: %s", cloud.client.user_name)

    for i in cloud.installations:
        inst: DaikinInstallation = cloud.installations[i]
        async_add_entities(
            [DaikinNAClimate(inst.devices[device]) for device in inst.devices]
        )


DKN_MODE_TO_HVAC_MODE = {
    5: HVACMode.DRY,
    4: HVACMode.FAN_ONLY,
    3: HVACMode.HEAT,
    2: HVACMode.COOL,
    1: HVACMode.HEAT_COOL,
}

DKN_MODE_TO_FAN_MODE = {0: FAN_AUTO, 2: FAN_LOW, 4: FAN_MEDIUM, 6: FAN_HIGH}

# This enum seems rather limited;  Observed values were always only 2 or 3.
DKN_MODE_TO_HA_HVAC_ACTION = {
    3: HVACAction.HEATING,
    2: HVACAction.COOLING,
}


class DaikinNAClimate(ClimateEntity):
    """Representation of a DaikinNA Device."""

    should_pool = False

    supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )

    def __init__(self, device: DaikinDevice) -> None:
        """Representation of a DaikinNA Device."""
        # super().__init__(device)
        self.device = device
        self._attr_hvac_modes = list(DKN_MODE_TO_HVAC_MODE.values())
        self._attr_hvac_modes.append(HVACMode.OFF)
        self._attr_unique_id = device.mac
        self._attr_name = device.name
        _LOGGER.debug(
            "Created DaikinNAClimate '%s':'%s'", self.device.mac, self.device.name
        )

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        self.device.register_on_update_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.device.unregister_on_update_callback(self.async_write_ha_state)
        # self._roller.remove_callback(self.async_write_ha_state)

    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self.device.mac)},
            # If desired, the name for the device could be different to the entity
            "name": self.device.name,
            # "sw_version": self.device.._roller.firmware_version,
            # "model": self._roller.model,
            "manufacturer": "Daikin",
        }

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return bool(self.device.data.isConnected) and bool(
            self.device.data.machineready
        )

    def _hvac_mode_to_dkn_mode(self, hvac_mode: HVACMode) -> int:
        return list(DKN_MODE_TO_HVAC_MODE.keys())[
            list(DKN_MODE_TO_HVAC_MODE.values()).index(hvac_mode)
        ]

    def _fan_mode_to_dkn_mode(self, fan_mode: str) -> int:
        return list(DKN_MODE_TO_FAN_MODE.keys())[
            list(DKN_MODE_TO_FAN_MODE.values()).index(fan_mode)
        ]

    # @property
    # def name(self):
    #    """Name of the entity."""
    #    return self.device.name

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        if self.device.data.units == 1:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac operation if supported."""
        if self.device.data.power is False:
            return HVACAction.OFF
        return DKN_MODE_TO_HA_HVAC_ACTION[int(self.device.data.real_mode)]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        if bool(self.device.data.power) is False:
            return HVACMode.OFF
        return DKN_MODE_TO_HVAC_MODE[int(self.device.data.mode)]

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.device.data.work_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.hvac_mode == HVACMode.COOL:
            return self.device.data.setpoint_air_cool
        if self.hvac_mode == HVACMode.HEAT:
            return self.device.data.setpoint_air_heat
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self.device.data.setpoint_air_auto
        return None

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            return float(self.device.data.range_sp_cool_air_max)
        if self.hvac_mode == HVACMode.HEAT:
            return float(self.device.data.range_sp_hot_air_max)
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return float(self.device.data.range_sp_auto_air_max)
        return DEFAULT_MAX_TEMP

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            return float(self.device.data.range_sp_cool_air_min)
        if self.hvac_mode == HVACMode.HEAT:
            return float(self.device.data.range_sp_hot_air_min)
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return float(self.device.data.range_sp_auto_air_min)
        return DEFAULT_MIN_TEMP

    @property
    def fan_mode(self) -> str:
        """Return the fan mode."""
        return DKN_MODE_TO_FAN_MODE[int(self.device.data.speed_state)]

    @property
    def fan_modes(self) -> list[str]:
        """Return the list of fan mode."""
        return list(DKN_MODE_TO_FAN_MODE.values())

    # @property
    # def available(self) -> bool:
    #    return (
    #        self._device.device_data.isConnected
    #        and self._device.device_data.machineready
    #    )

    @property
    def sw_version(self) -> str:
        """Gets the device firmware version."""
        return str(self.device.data.version)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        current_power_state = self.device.data.power is True
        new_power_state = hvac_mode != HVACMode.OFF
        if new_power_state is True:
            await self.device.set_device_value(
                "mode", str(self._hvac_mode_to_dkn_mode(hvac_mode))
            )
        if new_power_state != current_power_state:
            await self.device.set_device_value("power", str(new_power_state))
        # self.async_schedule_update_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self.device.set_device_value(
            "speed_state", str(self._fan_mode_to_dkn_mode(fan_mode))
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            raise UpdateFailed("No target temperature specified")
        property_to_update = ""
        if self.hvac_mode == HVACMode.COOL:
            property_to_update = "setpoint_air_cool"
        elif self.hvac_mode == HVACMode.HEAT:
            property_to_update = "setpoint_air_heat"
        elif self.hvac_mode == HVACMode.HEAT_COOL:
            property_to_update = "setpoint_air_auto"
        else:
            raise UpdateFailed("Invalid hvac_mode:  %s")
        try:
            await self.device.set_device_value(property_to_update, temperature)
        except Exception as exc:
            raise UpdateFailed("set_temperature update failed") from exc
