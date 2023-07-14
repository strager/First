import first.config
import pytest

website_config = first.config.cfg["website"]

@pytest.fixture
def set_admin_password():
    def set(new_password: str) -> None:
        website_config["admin_password"] = new_password
    old_password = website_config["admin_password"]
    yield set
    website_config["admin_password"] = old_password
