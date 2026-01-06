from homeassistant.components.button import ButtonEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    # We find the camera entity we created to link the buttons to it
    # For a simple custom integration, we can pass the camera instance 
    # Or use the hass.data storage.
    
    # Since we want these buttons to work specifically with our camera:
    camera_entity = hass.data[DOMAIN][entry.entry_id]
    
    async_add_entities([
        RefreshButton(camera_entity, entry.entry_id),
        NextImageButton(camera_entity, entry.entry_id)
    ])

class RefreshButton(ButtonEntity):
    def __init__(self, camera, entry_id):
        self._camera = camera
        self._attr_name = "iCloud Photo Frame Refresh"
        self._attr_unique_id = f"{entry_id}_refresh"
        self._attr_icon = "mdi:refresh"

    async def async_press(self):
        """Force a sync when pressed."""
        await self.hass.async_add_executor_job(self._camera._sync_images)

class NextImageButton(ButtonEntity):
    def __init__(self, camera, entry_id):
        self._camera = camera
        self._attr_name = "iCloud Photo Frame Next"
        self._attr_unique_id = f"{entry_id}_next"
        self._attr_icon = "mdi:skip-next"

    def press(self):
        """Skip to the next image."""
        self._camera.next_image()
