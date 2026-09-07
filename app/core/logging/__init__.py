import atexit
import logging
import logging.config
import pathlib

import yaml

from .json_formatter import AppJSONFormatter

CONFIG_FILE = pathlib.Path("logging_config.yaml")


def setup_logging(json_logs: bool = False):
    config = yaml.safe_load(CONFIG_FILE.read_text())
    if json_logs:
        config["handlers"]["stdout"]["formatter"] = "json"

    logging.config.dictConfig(config)

    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        atexit.register(queue_handler.listener.stop)

__all__ = ["setup_logging", "AppJSONFormatter"]
