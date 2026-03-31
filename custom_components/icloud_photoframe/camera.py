import json
import logging
import os
import random
import time
from datetime import timedelta

import requests
from homeassistant.components.camera import Camera
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CACHE_BASE_DIR,
    CONF_ALBUM_NAME,
    CONF_TOKEN,
    DEFAULT_ALBUM_NAME,
    ROTATION_INTERVAL_SECONDS,
    SYNC_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up iCloud photo frame camera."""
    token = entry.data[CONF_TOKEN]
    album_name = entry.data.get(CONF_ALBUM_NAME, DEFAULT_ALBUM_NAME)
    camera = ICloudPhotoFrameCamera(hass, token, album_name, entry.entry_id)
    hass.data[entry.domain][entry.entry_id] = camera
    async_add_entities([camera], True)

    notification_id = f"icloud_sync_{entry.entry_id}"
    async_create(hass, f"Starting sync for '{album_name}'...", "iCloud Sync", notification_id)

    try:
        await camera.async_sync_images()
    finally:
        await async_dismiss(hass, notification_id)


class ICloudPhotoFrameCamera(Camera):
    """Camera entity backed by iCloud shared album photos."""

    def __init__(self, hass, token, album_name, entry_id):
        super().__init__()
        self.hass = hass
        self._token = token.split("#")[-1] if "#" in token else token
        self._album_name = album_name
        self._entry_id = entry_id
        self._attr_name = album_name
        self._attr_unique_id = f"icloud_photoframe_{entry_id}"
        self._cache_dir = os.path.join(CACHE_BASE_DIR, entry_id)
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }
        self._last_sync = 0.0
        self._last_error = None
        self._current_image = None

    @property
    def extra_state_attributes(self):
        return {
            "cache_dir": self._cache_dir,
            "last_sync": int(self._last_sync) if self._last_sync else None,
            "last_error": self._last_error,
        }

    async def async_added_to_hass(self):
        """Start scheduled sync once entity is added."""
        remove_listener = async_track_time_interval(
            self.hass,
            self._handle_periodic_sync,
            timedelta(seconds=SYNC_INTERVAL_SECONDS),
        )
        self.async_on_remove(remove_listener)

    async def _handle_periodic_sync(self, _now):
        await self.async_sync_images()

    async def async_sync_images(self):
        await self.hass.async_add_executor_job(self._sync_images)
        self.async_write_ha_state()

    def _sync_images(self):
        try:
            os.makedirs(self._cache_dir, exist_ok=True)

            session = requests.Session()
            url = f"https://p23-sharedstreams.icloud.com/{self._token}/sharedstreams/webstream"
            response = session.post(url, data='{"streamCtag":null}', headers=self._headers, timeout=15)

            if response.status_code == 330:
                host = response.json().get("X-Apple-MMe-Host")
                if host:
                    url = f"https://{host}/{self._token}/sharedstreams/webstream"
                    response = session.post(url, data='{"streamCtag":null}', headers=self._headers, timeout=15)

            response.raise_for_status()
            photos = response.json().get("photos", [])
            guids = [p.get("photoGuid") for p in photos if p.get("photoGuid")]

            current_files = {
                filename
                for filename in os.listdir(self._cache_dir)
                if filename.endswith(".jpg")
            }
            expected_files = {f"{guid}.jpg" for guid in guids}

            # Remove stale cache files for deleted photos.
            for stale_file in current_files - expected_files:
                os.remove(os.path.join(self._cache_dir, stale_file))

            if guids:
                asset_url = url.replace("webstream", "webasseturls")
                assets_response = session.post(
                    asset_url,
                    data=json.dumps({"photoGuids": guids}),
                    headers=self._headers,
                    timeout=15,
                )
                assets_response.raise_for_status()
                assets = assets_response.json().get("items", {})

                for guid, asset in assets.items():
                    path = os.path.join(self._cache_dir, f"{guid}.jpg")
                    if os.path.exists(path):
                        continue

                    img_url = f"https://{asset['url_location']}{asset['url_path']}"
                    image_response = session.get(img_url, timeout=30)
                    image_response.raise_for_status()
                    with open(path, "wb") as image_file:
                        image_file.write(image_response.content)

            self._last_sync = time.time()
            self._last_error = None
            _LOGGER.info("Synced %s photos for %s", len(guids), self._album_name)

        except Exception as err:  # pylint: disable=broad-except
            self._last_error = str(err)
            _LOGGER.error("Failed to sync iCloud album '%s': %s", self._album_name, err)

    def next_image(self):
        """Force selection of a new cached image."""
        images = self._get_images()
        if not images:
            return

        if len(images) == 1:
            self._current_image = images[0]
        else:
            candidates = [img for img in images if img != self._current_image]
            self._current_image = random.choice(candidates)

        self.async_write_ha_state()

    def _get_images(self):
        if not os.path.exists(self._cache_dir):
            return []
        return sorted(
            [
                os.path.join(self._cache_dir, f)
                for f in os.listdir(self._cache_dir)
                if f.endswith(".jpg")
            ]
        )

    def camera_image(self, width=None, height=None):
        images = self._get_images()
        if not images:
            return None

        if self._current_image not in images:
            interval_slot = int(time.time() // ROTATION_INTERVAL_SECONDS)
            self._current_image = images[interval_slot % len(images)]

        with open(self._current_image, "rb") as image_file:
            return image_file.read()
