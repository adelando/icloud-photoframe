import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

class ICloudPhotoFrameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for iCloud Photo Frame."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step when user adds the integration via UI."""
        if user_input is not None:
            url = user_input["url"]
            token = url.split("#")[-1] if "#" in url else url
            
            return self.async_create_entry(
                title="iCloud Photo Frame", 
                data={"token": token}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("url"): str
            })
        )
