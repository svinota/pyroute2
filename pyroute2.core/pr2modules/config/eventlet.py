import logging
from pr2modules.config.asyncio import asyncio_config

log = logging.getLogger(__name__)
log.warning("Please use pr2modules.config.asyncio.asyncio_config")
log.warning("The eventlet module will be dropped soon ")

eventlet_config = asyncio_config
