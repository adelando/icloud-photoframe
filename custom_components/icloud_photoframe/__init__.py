import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iCloud Photo Frame from a config entry."""
    _LOGGER.debug("Initializing iCloud Photo Frame integration for entry: %s", entry.entry_id)
    
    # Create the domain data store if it doesn't exist
    hass.data.setdefault(DOMAIN, {})
    
    # We will store the camera instance here so the button platform can access it
    # hass.data[DOMAIN][entry.entry_id] is set inside camera.py
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
