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

# --- SETTINGS ---
TEST_MODE = True  # Set to False for production (5-minute rotation)
# ----------------

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the camera platform."""
    token = entry.data["token"]
    camera = ICloudPhotoFrameCamera(token, entry.entry_id)
    
    # SAVE the camera instance so button.py can find it
    hass.data[DOMAIN][entry.entry_id] = camera
    
    async_add_entities([camera], True)
    await hass.async_add_executor_job(camera._sync_images)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, entry_id):
        super().__init__()
        self._token = token
        self._entry_id = entry_id
        self._base_url = f"https://p23-sharedstreams.icloud.com/{token}/sharedstreams"
        self._last_sync = 0
        self._manual_offset = 0  # Used to skip to next image
        self._headers = {
            "Origin": "https://www.icloud.com",
            "Referer": "https://www.icloud.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }

    def next_image(self):
        """Advance the random seed to skip to the next image."""
        self._manual_offset += 1
        # This tells Home Assistant the state changed so the UI refreshes
        self.async_write_ha_state()

    def _sync_images(self):
        """Fetch photos and cleanup deleted ones."""
        try:
            if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)
            session = requests.Session()
            r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)
            
            if r.status_code == 330 or "X-Apple-MMe-Host" in r.headers:
                host = r.headers.get("X-Apple-MMe-Host") or r.json().get("X-Apple-MMe-Host")
                if host:
                    self._base_url = f"https://{host}/{self._token}/sharedstreams"
                    r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)

            r.raise_for_status()
            photos = r.json().get("photos", [])
            valid_guids = {p["photoGuid"] for p in photos}
            
            # Sync Assets
            r_assets = session.post(f"{self._base_url}/webasseturls", 
                                    data=json.dumps({"photoGuids": list(valid_guids)}), 
                                    headers=self._headers)
            assets = r_assets.json().get("items", {})

            for guid, asset in assets.items():
                file_path = os.path.join(CACHE_DIR, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    with open(file_path, 'wb') as f:
                        f.write(session.get(url).content)

            # Cleanup
            for filename in os.listdir(CACHE_DIR):
                guid = filename.split('.')[0]
                if guid not in valid_guids:
                    os.remove(os.path.join(CACHE_DIR, filename))
            
            self._last_sync = time.time()
            _LOGGER.info("iCloud Photo Frame: Sync & Cleanup Successful")
        except Exception as e:
            _LOGGER.error("iCloud Photo Frame: Sync Error: %s", e)

    def camera_image(self, width=None, height=None):
        """Return the selected image from cache."""
        now = time.time()
        if (now - self._last_sync) > 3600:
            self._sync_images()

        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files: return None

        interval = 10 if TEST_MODE else 300
        
        # Try to find a valid file (adding manual_offset to skip images)
        for attempt in range(5):
            random.seed(int(now // interval) + self._manual_offset + attempt)
            selected_file = random.choice(files)
            full_path = os.path.join(CACHE_DIR, selected_file)
            
            if os.path.exists(full_path):
                with open(full_path, 'rb') as f:
                    return f.read()
        return None

    @property
    def name(self): return "iCloud Photo Frame"

    @property
    def unique_id(self): return f"icloud_photoframe_{self._entry_id}"
