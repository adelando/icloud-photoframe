import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iCloud Photo Frame from a config entry."""
    _LOGGER.debug("Initializing iCloud Photo Frame integration")
    
    hass.data.setdefault(DOMAIN, {})
    
    # Ensure the camera platform is loaded
    try:
        await hass.config_entries.async_forward_entry_setups(entry, ["camera"])
        _LOGGER.debug("Camera platform setup forwarded successfully")
    except Exception as e:
        _LOGGER.error("Failed to setup camera platform: %s", e)
        return False
        
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["camera"])
