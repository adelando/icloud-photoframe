import requests
import random
import time
import os
import logging
import json
from homeassistant.components.camera import Camera
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Base path where all album folders will live
CACHE_BASE_DIR = "/config/www/icloud_photoframe_cache/"

# --- SETTINGS ---
# Set to False to use the standard 5-minute (300s) rotation
TEST_MODE = True 
# ----------------

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the camera platform from a config entry."""
    token = entry.data["token"]
    album_name = entry.data.get("album_name", "iCloud Album")
    
    # We pass the entry_id to create a unique folder for this instance
    camera = ICloudPhotoFrameCamera(token, album_name, entry.entry_id)
    async_add_entities([camera], True)
    
    # Start the initial sync in a background thread to avoid blocking HA
    hass.loop.run_in_executor(None, camera._sync_images)

class ICloudPhotoFrameCamera(Camera):
    def __init__(self, token, album_name, entry_id):
        """Initialize the camera."""
        super().__init__()
        self._token = token.split("#")[-1]
        self._album_name = album_name
        self._entry_id = entry_id
        
        # Unique Entity ID and Cache Directory based on this specific integration entry
        self.entity_id = f"camera.icloud_photoframe_{entry_id[-4:]}"
        self._cache_dir = os.path.join(CACHE_BASE_DIR, entry_id)
        
        self._base_url = f"https://p23-sharedstreams.icloud.com/{self._token}/sharedstreams"
        self._last_sync = 0
        self._headers = {
            "Origin": "https://www.icloud.com",
            "Referer": "https://www.icloud.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "text/plain",
        }

    @property
    def name(self):
        """Return the custom name provided in the config flow."""
        return self._album_name

    @property
    def unique_id(self):
        """Return a truly unique ID for this entity."""
        return f"icloud_photoframe_{self._entry_id}"

    def _sync_images(self):
        """Perform the sync: Download new photos and remove deleted ones."""
        _LOGGER.info("Starting sync for album: %s", self._album_name)
        try:
            if not os.path.exists(self._cache_dir):
                os.makedirs(self._cache_dir, exist_ok=True)
            
            session = requests.Session()
            # Handshake with Apple
            r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)
            
            # Handle Shard Redirection (if Apple moved your data to a different server)
            if r.status_code == 330:
                host = r.json().get("X-Apple-MMe-Host")
                self._base_url = f"https://{host}/{self._token}/sharedstreams"
                r = session.post(f"{self._base_url}/webstream", data='{"streamCtag":null}', headers=self._headers)

            r.raise_for_status()
            photos = r.json().get("photos", [])
            valid_guids = {p["photoGuid"] for p in photos}

            if not valid_guids:
                _LOGGER.warning("No photos found for %s. Check if Public Website is enabled.", self._album_name)
                return

            # Request direct download URLs for all GUIDs
            r_assets = session.post(f"{self._base_url}/webasseturls", 
                                    data=json.dumps({"photoGuids": list(valid_guids)}), 
                                    headers=self._headers)
            assets = r_assets.json().get("items", {})

            # Download missing images
            for guid, asset in assets.items():
                file_path = os.path.join(self._cache_dir, f"{guid}.jpg")
                if not os.path.exists(file_path):
                    url = f"https://{asset['url_location']}{asset['url_path']}"
                    img_data = session.get(url, timeout=10).content
                    with open(file_path, 'wb') as f:
                        f.write(img_data)

            # Cleanup: Delete local files that are no longer in the iCloud album
            for filename in os.listdir(self._cache_dir):
                guid = filename.split('.')[0]
                if guid not in valid_guids:
                    os.remove(os.path.join(self._cache_dir, filename))
            
            self._last_sync = time.time()
            _LOGGER.info("Sync successful for %s. Total images: %s", self._album_name, len(os.listdir(self._cache_dir)))

        except Exception as e:
            _LOGGER.error("Fatal sync error for %s: %s", self._album_name, e)

    def camera_image(self, width=None, height=None):
        """Serve a random image from this instance's folder."""
        now = time.time()
        # Trigger an hourly sync if needed
        if (now - self._last_sync) > 3600:
            self.hass.add_job(self._sync_images)

        if not os.path.exists(self._cache_dir):
            return None
            
        files = [f for f in os.listdir(self._cache_dir) if f.endswith('.jpg')]
        if not files:
            return None

        # Determine rotation interval
        interval = 10 if TEST_MODE else 300
        
        # Use a time-based seed so all viewers see the same image at the same time
        random.seed(int(now // interval))
        selected_file = random.choice(files)
        
        try:
            with open(os.path.join(self._cache_dir, selected_file), 'rb') as f:
                return f.read()
        except Exception as e:
            _LOGGER.error("Error reading image %s: %s", selected_file, e)
            return None
