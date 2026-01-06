import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CACHE_DIR = "/config/www/icloud_photoframe_cache/"

async def async_setup_entry(hass, entry, async_add_entities):
    token = entry.data["token"]
    camera = ICloudPhotoFrameCamera(token, entry.entry_id)
    async_add_entities([camera], True)
    
    # Force an initial sync in the background so you don't have to wait
    hass.async_add_executor_job(camera._sync_images)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, entry_id):
        super().__init__()
        self._token = token
        self._entry_id = entry_id
        self._base_url = f"https://p23-sharedstreams.icloud.com/{token}/sharedstreams"
        self._last_sync = 0
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        _LOGGER.debug("Starting iCloud Sync for token %s", self._token)
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR)
            
            session = requests.Session()
            # Handshake with Apple
            r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)
            r.raise_for_status()
            
            photos = r.json().get("photos", [])
            if not photos:
                _LOGGER.error("Sync failed: No photos found in album. Is 'Public Website' enabled?")
                return

            guids = [p["photoGuid"] for p in photos]
            r = session.post(f"{self._base_url}/webasseturls", data=json.dumps({"photoGuids": guids}), headers=self._headers)
            assets = r.json().get("items", {})

            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(url).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
            
            self._last_sync = time.time()
            _LOGGER.info("iCloud Sync successful. Images are in %s", CACHE_DIR)
        except Exception as e:
            _LOGGER.error("CRITICAL SYNC ERROR: %s", e)

    def camera_image(self, width=None, height=None):
        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files:
            _LOGGER.warning("Camera requested image but cache is empty!")
            return None

        random.seed(int(time.time() // 300))
        with open(os.path.join(CACHE_DIR, random.choice(files)), 'rb') as f:
            return f.read()

    @property
    def name(self): return "iCloud Photo Frame"

    @property
    def unique_id(self): return f"icloud_photoframe_{self._entry_id}"
