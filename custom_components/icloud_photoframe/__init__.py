import logging
import os
import shutil

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CACHE_BASE_DIR, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iCloud Photo Frame from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("Setting up iCloud Photo Frame: %s", entry.entry_id)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry and clean up the cache folder."""
    cache_dir = os.path.join(CACHE_BASE_DIR, entry.entry_id)
    if os.path.exists(cache_dir):
        _LOGGER.info("Removing cache directory for deleted entry: %s", cache_dir)
        await hass.async_add_executor_job(shutil.rmtree, cache_dir)
