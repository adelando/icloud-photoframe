import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)
# Absolute path to ensure no confusion
CACHE_DIR = "/config/www/icloud_photoframe_cache/"

# --- SETTINGS ---
TEST_MODE = True 
# ----------------

async def async_setup_entry(hass, entry, async_add_entities):
    token = entry.data["token"]
    camera = ICloudPhotoFrameCamera(token, entry.entry_id)
    async_add_entities([camera], True)
    hass.loop.run_in_executor(None, camera._sync_images)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, entry_id):
        super().__init__()
        self._token = token.split("#")[-1] # Ensure we only have the token
        self.entity_id = "camera.icloud_photoframe"
        self._base_url = f"https://p23-sharedstreams.icloud.com/{self._token}/sharedstreams"
        self._last_sync = 0
        self._headers = {
            "Origin": "https://www.icloud.com",
            "Referer": "https://www.icloud.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        _LOGGER.info("DEBUG: Starting Sync for Token: %s", self._token)
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR, exist_ok=True)
            
            session = requests.Session()
            # 1. Handshake
            r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)
            
            if r.status_code == 330:
                host = r.json().get("X-Apple-MMe-Host")
                _LOGGER.info("DEBUG: Shard Redirect to %s", host)
                self._base_url = f"https://{host}/{self._token}/sharedstreams"
                r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)

            r.raise_for_status()
            photos = r.json().get("photos", [])
            _LOGGER.info("DEBUG: Found %s photos in Apple response", len(photos))

            if not photos:
                _LOGGER.error("FAIL: Album is empty or 'Public Website' is disabled on iPhone.")
                return

            # 2. Asset Discovery
            guids = [p["photoGuid"] for p in photos]
            r_assets = session.post(f"{self._base_url}/webasseturls", 
                                    data=json.dumps({"photoGuids": guids}), 
                                    headers=self._headers)
            assets = r_assets.json().get("items", {})

            # 3. Download
            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(url, timeout=10).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
            
            self._last_sync = time.time()
            _LOGGER.info("SUCCESS: Cache now contains %s images", len(os.listdir(CACHE_DIR)))

        except Exception as e:
            _LOGGER.error("SYNC FATAL ERROR: %s", str(e))

    def camera_image(self, width=None, height=None):
        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files: return None
        interval = 10 if TEST_MODE else 300
        random.seed(int(time.time() // interval))
        with open(os.path.join(CACHE_DIR, random.choice(files)), 'rb') as f:
            return f.read()

    @property
    def name(self): return "iCloud Photo Frame"
    @property
    def unique_id(self): return f"icloud_photoframe_{self._token}"
