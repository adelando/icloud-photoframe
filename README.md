# iCloud Shared Album Photo Frame for Home Assistant

A lightweight, high-performance integration that transforms any Home Assistant dashboard into a dynamic digital photo frame using an Apple iCloud Shared Album.

## Why this integration?
Most iCloud integrations require complex 2-Factor Authentication (2FA) which frequently breaks. This integration uses the **Public Website** feature of iCloud Shared Albums, meaning:
* **No 2FA Required:** No more annoying verification codes.
* **Privacy Focused:** Only the specific album you choose to share is accessible.
* **Auto-Sync:** Add or remove photos on your iPhone, and they automatically sync to your dashboard.
* **Local Caching:** Images are cached locally to ensure fast loading and reduced data usage.

## Installation

### Step 1: Prepare your iCloud Album
1. Open the **Photos** app on your iPhone or Mac.
2. Go to a **Shared Album** (or create a new one).
3. Tap the "People" icon or "..." menu and toggle on **Public Website**.
4. Copy the **Share Link** (it will look like `https://www.icloud.com/sharedalbum/#TOKEN`).

### Step 2: Install via HACS
1. Open **HACS** in Home Assistant.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Paste your GitHub URL: `https://github.com/adelando/icloud_photoframe`
4. Select **Integration** as the category and click **Add**.
5. Find "iCloud Photo Frame" in HACS and click **Download**.
6. **Restart Home Assistant.**

### Step 3: Configuration
1. Go to **Settings > Devices & Services**.
2. Click **Add Integration** and search for **iCloud Photo Frame**.
3. Paste the full URL you copied in Step 1.

---

## The Entities Created

Once installed, the integration creates a single, clean entity:

| Entity ID | Description |
| :--- | :--- |
| `camera.icloud_photoframe` | A camera entity that serves a random image from your album. |

### Camera Behavior
* **Rotation:** The image automatically rotates every 5 minutes (300 seconds).
* **Sync:** The integration checks for new or deleted photos in your iCloud album every hour.
* **Cleanup:** If you delete a photo from your iPhone, it is automatically removed from the Home Assistant cache during the next sync.

