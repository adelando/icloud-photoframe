from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_ALBUM_NAME, CONF_TOKEN, DEFAULT_ALBUM_NAME, DOMAIN


class ICloudPhotoFrameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iCloud Photo Frame."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if not _is_valid_shared_album_url(user_input[CONF_TOKEN]):
                errors["base"] = "invalid_url"
            else:
                await self.async_set_unique_id(user_input[CONF_TOKEN])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_ALBUM_NAME],
                    data={
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_ALBUM_NAME: user_input[CONF_ALBUM_NAME],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ALBUM_NAME, default=DEFAULT_ALBUM_NAME): str,
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
        )


def _is_valid_shared_album_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc not in {"www.icloud.com", "icloud.com"}:
        return False

    return parsed.path.startswith("/sharedalbum/") and bool(parsed.fragment)
