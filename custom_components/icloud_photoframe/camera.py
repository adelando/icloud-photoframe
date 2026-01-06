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

# --- TESTING SETTINGS ---
TEST_MODE = True  # Set to False for production (5-minute rotation)
# ------------------------

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the camera platform."""
    token = entry.data["token"]
    camera = ICloudPhotoFrameCamera(token, entry.entry_id)
    async_add_entities([camera], True)
    
    # Initial sync on startup
    await hass.async_add_executor_job(camera._sync_images)

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
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        """Fetch images and remove local files that are no longer in the album."""
        _LOGGER.debug("Starting iCloud Sync and Cleanup")
        try:
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR)
            
            session = requests.Session()
            webstream_url = f"{self._base_url}/webstream"
            r = session.post(webstream_url, data='{"streamCtag":null}', headers=self._headers)
            
            if r.status_code == 330 or "X-Apple-MMe-Host" in r.headers:
                host = r.headers.get("X-Apple-MMe-Host") or r.json().get("X-Apple-MMe-Host")
                if host:
                    self._base_url = f"https://{host}/{self._token}/sharedstreams"
                    webstream_url = f"{self._base_url}/webstream"
                    r = session.post(webstream_url, data='{"streamCtag":null}', headers=self._headers)

            r.raise_for_status()
            data = r.json()
            photos = data.get("photos", [])
            if not photos: return

            # Get set of GUIDs currently in iCloud
            valid_guids = {p["photoGuid"] for p in photos}
            
            # Download missing
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

            # CLEANUP: Remove local files not in iCloud anymore
            for filename in os.listdir(CACHE_DIR):
                guid = filename.split('.')[0]
                if guid not in valid_guids:
                    os.remove(os.path.join(CACHE_DIR, filename))
            
            self._last_sync = time.time()
            _LOGGER.info("iCloud Sync & Cleanup Complete")
        except Exception as e:
            _LOGGER.error("Sync Error: %s", e)

    def camera_image(self, width=None, height=None):
        """Return random image with fallback for deleted files."""
        now = time.time()
        if (now - self._last_sync) > 3600:
            self._sync_images()

        files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.jpg')]
        if not files: return None

        # Rotation timing logic
        interval = 10 if TEST_MODE else 300
        
        # We try up to 5 times to find a file that actually exists
        # (in case one was deleted manually but the hourly sync hasn't run)
        for attempt in range(5):
            random.seed(int(now // interval) + attempt)
            selected_file = random.choice(files)
            full_path = os.path.join(CACHE_DIR, selected_file)
            
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'rb') as f:
                        return f.read()
                except Exception:
                    continue
        return None

    @property
    def name(self): return "iCloud Photo Frame"

    @property
    def unique_id(self): return f"icloud_photoframe_{self._entry_id}"
