"""The Daikin Cloud NA integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .daikincloud import DaikinCloud

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Daikin Cloud NA from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    cloud = DaikinCloud()

    email = entry.data["username"]
    password = entry.data["password"]

    try:
        await cloud.login(email, password)
    except Exception as exc:
        raise exc

    hass.data[DOMAIN][entry.entry_id] = cloud

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
