import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class ICloudPhotoFrameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iCloud Photo Frame."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Basic validation: check if the link contains the shared album hashtag
            if "#" not in user_input["token"]:
                errors["base"] = "invalid_url"
            else:
                return self.async_create_entry(
                    title=user_input["album_name"],
                    data={
                        "token": user_input["token"],
                        "album_name": user_input["album_name"]
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("album_name", default="My Photo Album"): str,
                vol.Required("token"): str,
            }),
            errors=errors,
        )
