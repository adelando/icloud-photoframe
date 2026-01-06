import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera
from homeassistant.components.persistent_notification import async_create, async_dismiss

_LOGGER = logging.getLogger(__name__)
CACHE_BASE_DIR = "/config/www/icloud_photoframe_cache/"
TEST_MODE = True 

async def async_setup_entry(hass, entry, async_add_entities):
    token = entry.data["token"]
    album_name = entry.data.get("album_name", "iCloud Album")
    camera = ICloudPhotoFrameCamera(token, album_name, entry.entry_id)
    async_add_entities([camera], True)
    
    notification_id = f"icloud_sync_{entry.entry_id}"
    
    # 1. Immediate Logging
    _LOGGER.info("Camera setup complete. Starting notification and sync for %s", album_name)

    async_create(hass, f"Starting sync for '{album_name}'...", "iCloud Sync", notification_id)

    def run_sync_task():
        try:
            # Re-verify path inside the thread
            _LOGGER.info("[%s] Sync thread started...", album_name)
            camera._sync_images()
        finally:
            hass.add_job(async_dismiss, hass, notification_id)

    # Use a direct executor call
    await hass.async_add_executor_job(run_sync_task)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, album_name, entry_id):
        super().__init__()
        self._token = token.split("#")[-1] if "#" in token else token
        self._album_name = album_name
        self._entry_id = entry_id
        self.entity_id = f"camera.icloud_photoframe_{entry_id[-4:]}"
        self._cache_dir = os.path.join(CACHE_BASE_DIR, entry_id)
        self._last_sync = 0
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        # IF THIS LINE DOESN'T SHOW IN LOGS, THE FUNCTION ISN'T RUNNING
        _LOGGER.warning("!!! SYNC FUNCTION EXECUTING NOW for %s !!!", self._album_name)
        
        try:
            if not os.path.exists(self._cache_dir):
                os.makedirs(self._cache_dir, exist_ok=True)
                _LOGGER.info("Created folder: %s", self._cache_dir)

            session = requests.Session()
            url = f"https://p23-sharedstreams.icloud.com/{self._token}/sharedstreams/webstream"
            
            # Shard handling
            r = session.post(url, data='{"streamCtag":null}', headers=self._headers, timeout=10)
            if r.status_code == 330:
                host = r.json().get("X-Apple-MMe-Host")
                url = f"https://{host}/{self._token}/sharedstreams/webstream"
                r = session.post(url, data='{"streamCtag":null}', headers=self._headers, timeout=10)

            r.raise_for_status()
            photos = r.json().get("photos", [])
            _LOGGER.info("Apple returned %s photos.", len(photos))

            if photos:
                guids = [p["photoGuid"] for p in photos]
                # Asset URLs
                asset_url = url.replace("webstream", "webasseturls")
                r_assets = session.post(asset_url, data=json.dumps({"photoGuids": guids}), headers=self._headers)
                assets = r_assets.json().get("items", {})

                for guid, asset in assets.items():
                    path = os.path.join(self._cache_dir, f"{guid}.jpg")
                    if not os.path.exists(path):
                        img_url = f"https://{asset['url_location']}{asset['url_path']}"
                        with open(path, 'wb') as f:
                            f.write(session.get(img_url).content)
            
            self._last_sync = time.time()
            _LOGGER.warning("!!! SYNC FINISHED for %s - Cache size: %s !!!", self._album_name, len(os.listdir(self._cache_dir)))

        except Exception as e:
            _LOGGER.error("CRITICAL SYNC ERROR: %s", str(e))

    def camera_image(self, width=None, height=None):
        if not os.path.exists(self._cache_dir): return None
        files = [f for f in os.listdir(self._cache_dir) if f.endswith('.jpg')]
        if not files: return None
        interval = 10 if TEST_MODE else 300
        random.seed(int(time.time() // interval))
        with open(os.path.join(self._cache_dir, random.choice(files)), 'rb') as f:
            return f.read()

    @property
    def name(self): return self._album_name
    @property
    def unique_id(self): return f"icloud_photoframe_{self._entry_id}"
