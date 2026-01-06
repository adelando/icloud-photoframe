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
    """Set up the camera platform from a config entry."""
    token = entry.data["token"]
    camera = ICloudPhotoFrameCamera(token, entry.entry_id)
    async_add_entities([camera], True)
    
    # Run the first sync immediately in the background
    await hass.async_add_executor_job(camera._sync_images)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, entry_id):
        super().__init__()
        self._token = token
        self._entry_id = entry_id
        # Start with the default p23 shard
        self._base_url = f"https://p23-sharedstreams.icloud.com/{token}/sharedstreams"
        self._last_sync = 0
        self._headers = {
            "Origin": "https://www.icloud.com",
            "Referer": "https://www.icloud.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        """Fetch and download images, handling Apple shard redirection."""
        _LOGGER.debug("Starting iCloud Sync for token %s", self._token)
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR)
            
            session = requests.Session()
            
            # Step 1: Handshake with webstream
            # We use text/plain and a raw JSON string because Apple's API is quirky
            webstream_url = f"{self._base_url}/webstream"
            r = session.post(webstream_url, data='{"streamCtag":null}', headers=self._headers)
            
            # Handle Shard Redirection (e.g., if your album is on p04 instead of p23)
            if r.status_code == 330 or "X-Apple-MMe-Host" in r.headers:
                host = r.headers.get("X-Apple-MMe-Host") or r.json().get("X-Apple-MMe-Host")
                if host:
                    _LOGGER.debug("Redirecting to new Apple host: %s", host)
                    self._base_url = f"https://{host}/{self._token}/sharedstreams"
                    webstream_url = f"{self._base_url}/webstream"
                    r = session.post(webstream_url, data='{"streamCtag":null}', headers=self._headers)

            r.raise_for_status()
            data = r.json()
            
            photos = data.get("photos", [])
            if not photos:
                _LOGGER.error("Apple returned successfully but the photo list is empty. Check if 'Public Website' is enabled.")
                return

            # Step 2: Get direct download URLs
            guids = [p["photoGuid"] for p in photos]
            asset_url = f"{self._base_url}/webasseturls"
            r_assets = session.post(asset_url, data=json.dumps({"photoGuids": guids}), headers=self._headers)
            r_assets.raise_for_status()
            assets = r_assets.json().get("items", {})

            # Step 3: Download missing images
            download_count = 0
            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(url).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
                    download_count += 1
            
            self._last_sync = time.time()
            _LOGGER.info("iCloud Sync complete. Total photos in album: %s. New downloads: %s", len(photos), download_count)

        except Exception as e:
            _LOGGER.error("CRITICAL SYNC ERROR: %s", e)

    def camera_image(self, width=None, height=None):
        """Return a random image from cache, changing every 5 minutes."""
        # Refresh if it's been an hour
        if (time.time() - self._last_sync) > 3600:
            self._sync_images()

        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files:
            return None

        # Rotate every 300 seconds (5 minutes)
        random.seed(int(time.time() // 300))
        selected_file = random.choice(files)
        
        with open(os.path.join(CACHE_DIR, selected_file), 'rb') as f:
            return f.read()

    @property
    def name(self):
        return "iCloud Photo Frame"

    @property
    def unique_id(self):
        return f"icloud_photoframe_{self._entry_id}"
