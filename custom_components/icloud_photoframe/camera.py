import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)
CACHE_DIR = "/config/www/icloud_photoframe_cache/"

# --- SETTINGS ---
TEST_MODE = True  # Set to False for 5-minute rotation
# ----------------

async def async_setup_entry(hass, entry, async_add_entities):
    token = entry.data["token"]
    camera = ICloudPhotoFrameCamera(token, entry.entry_id)
    async_add_entities([camera], True)
    
    # Trigger initial sync
    await hass.async_add_executor_job(camera._sync_images)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, entry_id):
        super().__init__()
        self._token = token
        self._entry_id = entry_id
        # Force the entity ID to be clean
        self.entity_id = "camera.icloud_photoframe"
        
        self._base_url = f"https://p23-sharedstreams.icloud.com/{token}/sharedstreams"
        self._last_sync = 0
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        """Fetch photos and cleanup deleted ones."""
        _LOGGER.info("iCloud Photo Frame: Starting sync for token %s", self._token)
        try:
            # 1. Ensure directory exists and is writable
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR, exist_ok=True)
                _LOGGER.info("iCloud Photo Frame: Created cache directory")

            session = requests.Session()
            
            # 2. Handshake
            r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)
            
            # Shard Redirect
            if r.status_code == 330 or "X-Apple-MMe-Host" in r.headers:
                host = r.headers.get("X-Apple-MMe-Host") or r.json().get("X-Apple-MMe-Host")
                if host:
                    self._base_url = f"https://{host}/{self._token}/sharedstreams"
                    r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)

            r.raise_for_status()
            data = r.json()
            photos = data.get("photos", [])
            valid_guids = {p["photoGuid"] for p in photos}
            
            if not valid_guids:
                _LOGGER.warning("iCloud Photo Frame: No photos found in album response")
                return

            # 3. Sync Assets
            r_assets = session.post(f"{self._base_url}/webasseturls", 
                                    data=json.dumps({"photoGuids": list(valid_guids)}), 
                                    headers=self._headers)
            assets = r_assets.json().get("items", {})

            download_count = 0
            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(url).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
                    download_count += 1

            # 4. Cleanup
            for filename in os.listdir(CACHE_DIR):
                guid = filename.split('.')[0]
                if guid not in valid_guids:
                    os.remove(os.path.join(CACHE_DIR, filename))
            
            self._last_sync = time.time()
            _LOGGER.info("iCloud Photo Frame: Sync successful. New: %s, Total: %s", download_count, len(os.listdir(CACHE_DIR)))
        except Exception as e:
            _LOGGER.error("iCloud Photo Frame: Sync Error: %s", str(e))

    def camera_image(self, width=None, height=None):
        now = time.time()
        if (now - self._last_sync) > 3600:
            self.hass.add_job(self._sync_images)

        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files:
            return None

        interval = 10 if TEST_MODE else 300
        random.seed(int(now // interval))
        selected_file = random.choice(files)
        
        try:
            with open(os.path.join(CACHE_DIR, selected_file), 'rb') as f:
                return f.read()
        except Exception as e:
            _LOGGER.error("iCloud Photo Frame: Error reading file: %s", e)
            return None

    @property
    def name(self): return "iCloud Photo Frame"
    
    @property
    def unique_id(self): return f"icloud_photoframe_{self._entry_id}"
