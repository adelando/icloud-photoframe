import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera
from homeassistant.components.persistent_notification import async_create, async_dismiss
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CACHE_BASE_DIR = "/config/www/icloud_photoframe_cache/"

# --- SETTINGS ---
TEST_MODE = True 
# ----------------

async def async_setup_entry(hass, entry, async_add_entities):
    token = entry.data["token"]
    album_name = entry.data.get("album_name", "iCloud Album")
    camera = ICloudPhotoFrameCamera(token, album_name, entry.entry_id)
    async_add_entities([camera], True)
    
    # Create a notification ID unique to this album
    notification_id = f"icloud_sync_{entry.entry_id}"
    
    # Notify user that sync is starting
    hass.async_create_task(
        hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"iCloud Sync: {album_name}",
                "message": f"Starting initial download for '{album_name}'. This may take a few minutes...",
                "notification_id": notification_id
            }
        )
    )

    # Run sync and dismiss notification when done
    def sync_and_notify():
        camera._sync_images()
        hass.add_job(async_dismiss, hass, notification_id)
        # Create a final brief notification that it's done
        hass.add_job(
            async_create, 
            hass, 
            f"Download complete! {album_name} is ready.", 
            "iCloud Sync Complete", 
            f"done_{notification_id}"
        )

    await hass.async_add_executor_job(sync_and_notify)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, album_name, entry_id):
        super().__init__()
        self._token = token.split("#")[-1] if "#" in token else token
        self._album_name = album_name
        self._entry_id = entry_id
        self.entity_id = f"camera.icloud_photoframe_{entry_id[-4:]}"
        self._cache_dir = os.path.join(CACHE_BASE_DIR, entry_id)
        
        self._base_url = f"https://p23-sharedstreams.icloud.com/{self._token}/sharedstreams"
        self._last_sync = 0
        self._headers = {
            "Origin": "https://www.icloud.com",
            "Referer": "https://www.icloud.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "text/plain",
        }

    def _sync_images(self):
        _LOGGER.info("[%s] Starting sync...", self._album_name)
        try:
            if not os.path.exists(self._cache_dir):
                os.makedirs(self._cache_dir, exist_ok=True)

            session = requests.Session()
            url = f"{self._base_url}/webstream"
            
            for _ in range(3):
                r = session.post(url, data='{"streamCtag":null}', headers=self._headers)
                if r.status_code == 330:
                    data = r.json()
                    host = data.get("X-Apple-MMe-Host")
                    self._base_url = f"https://{host}/{self._token}/sharedstreams"
                    url = f"{self._base_url}/webstream"
                    continue
                break
            
            r.raise_for_status()
            photos = r.json().get("photos", [])

            if not photos:
                _LOGGER.warning("[%s] No photos found.", self._album_name)
                return

            guids = [p["photoGuid"] for p in photos]
            r_assets = session.post(f"{self._base_url}/webasseturls", 
                                    data=json.dumps({"photoGuids": guids}), 
                                    headers=self._headers)
            assets = r_assets.json().get("items", {})

            count = 0
            for guid, asset in assets.items():
                file_path = os.path.join(self._cache_dir, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    img_url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(img_url, timeout=15).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)
                    count += 1

            valid_filenames = [f"{g}.jpg" for g in guids]
            for filename in os.listdir(self._cache_dir):
                if filename not in valid_filenames:
                    os.remove(os.path.join(self._cache_dir, filename))
            
            self._last_sync = time.time()
            _LOGGER.info("[%s] Sync complete.", self._album_name)

        except Exception as e:
            _LOGGER.error("[%s] Sync failed: %s", self._album_name, str(e))

    def camera_image(self, width=None, height=None):
        now = time.time()
        if (now - self._last_sync) > 3600:
            self.hass.add_job(self._sync_images)

        if not os.path.exists(self._cache_dir): return None
        files = [f for f in os.listdir(self._cache_dir) if f.endswith('.jpg')]
        if not files: return None

        interval = 10 if TEST_MODE else 300
        random.seed(int(now // interval))
        selected_file = random.choice(files)
        
        with open(os.path.join(self._cache_dir, selected_file), 'rb') as f:
            return f.read()

    @property
    def name(self): return self._album_name

    @property
    def unique_id(self): return f"icloud_photoframe_{self._entry_id}"
