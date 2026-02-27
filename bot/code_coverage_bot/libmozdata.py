# -*- coding: utf-8 -*-

from importlib.metadata import version

import structlog
from libmozdata.config import Config
from libmozdata.config import set_config

logger = structlog.get_logger(__name__)


class LocalConfig(Config):
    """
    Provide required configuration for libmozdata
    using an in-memory class instead of an INI file.
    """

    def __init__(self, name, package_version):
        self.user_agent = f"{name}/{package_version}"
        logger.debug("User agent configured", user_agent=self.user_agent)

    def get(self, section, option, default=None, **kwargs):
        if section == "User-Agent" and option == "name":
            return self.user_agent

        return default


def setup(package_name):
    # Get version for main package.
    package_version = version(package_name)

    # Provide a custom libmozdata configuration.
    set_config(LocalConfig(package_name, package_version))
