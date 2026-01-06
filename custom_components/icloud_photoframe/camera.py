import requests
import random
import time
import os
import logging
from homeassistant.components.camera import Camera
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CACHE_DIR = "/config/www/icloud_photoframe_cache/"

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the camera platform."""
    token = entry.data["token"]
    async_add_entities([ICloudPhotoFrameCamera(token, entry.entry_id)], True)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, entry_id):
        super().__init__()
        self._token = token
        self._entry_id = entry_id
        self._base_url = f"https://p23-sharedstreams.icloud.com/{token}/sharedstreams"
        self._last_sync = 0

    def _sync_images(self):
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR)
            
            session = requests.Session()
            r = session.post(f"{self._base_url}/webstream", json={"streamCtag": None})
            guids = [p["photoGuid"] for p in r.json().get("photos", [])]

            r = session.post(f"{self._base_url}/webasseturls", json={"photoGuids": guids})
            assets = r.json().get("items", {})

            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    with open(file_path, 'wb') as f:
                        f.write(requests.get(url).content)
            self._last_sync = time.time()
        except Exception as e:
            _LOGGER.error("Sync error: %s", e)

    def camera_image(self, width=None, height=None):
        now = time.time()
        if (now - self._last_sync) > 3600:
            self._sync_images()

        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files: return None

        random.seed(int(now // 300))
        with open(os.path.join(CACHE_DIR, random.choice(files)), 'rb') as f:
            return f.read()

    @property
    def name(self):
        return "iCloud Photo Frame"

    @property
    def unique_id(self):
        return f"icloud_photoframe_{self._entry_id}"
