import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
# Absolute path to ensure HA can always find the cache
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
        self._headers = {
            "Origin": "https://www.icloud.com",
            "Referer": "https://www.icloud.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Content-Type": "text/plain", # Apple expects text/plain for these specific POSTs
        }

    def _sync_images(self):
        """Downloads images from the shared album to local storage."""
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR)
                _LOGGER.info("Created cache directory at %s", CACHE_DIR)
            
            session = requests.Session()
            session.headers.update(self._headers)
            
            # 1. Fetch metadata (Must be a POST with empty JSON string or specific ctag)
            _LOGGER.info("Fetching metadata from iCloud for token: %s", self._token)
            r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}')
            r.raise_for_status()
            
            photos = r.json().get("photos", [])
            if not photos:
                _LOGGER.warning("No photos found in the iCloud Shared Album. Is it empty?")
                return

            guids = [p["photoGuid"] for p in photos]
            _LOGGER.info("Found %s photos, fetching asset URLs...", len(guids))

            # 2. Get direct asset URLs
            r = session.post(f"{self._base_url}/webasseturls", data=json.dumps({"photoGuids": guids}))
            r.raise_for_status()
            assets = r.json().get("items", {})

            count = 0
            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    download_url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(download_url).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
                    count += 1
            
            _LOGGER.info("Sync complete. Downloaded %s new images.", count)
            self._last_sync = time.time()
        except Exception as e:
            _LOGGER.error("iCloud Sync Failed: %s", str(e))

    def camera_image(self, width=None, height=None):
        """Returns the current random image from the local cache."""
        now = time.time()
        
        # Sync once an hour OR if cache is empty
        if (now - self._last_sync) > 3600 or not os.listdir(CACHE_DIR):
            self._sync_images()

        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files:
            return None

        # Change image every 5 minutes
        random.seed(int(now // 300))
        selected_file = random.choice(files)
        
        with open(os.path.join(CACHE_DIR, selected_file), 'rb') as f:
            return f.read()

    @property
    def name(self):
        return "iCloud Photo Frame"

    @property
    def unique_id(self):
        return f"icloud_photoframe_{self._entry_id}"
