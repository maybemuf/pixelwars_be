import logging
import logging.config
import pathlib

import yaml

from .json_formatter import AppJSONFormatter


def setup_logging(json_logs: bool = False):
    config_file = pathlib.Path("logging_config.yaml")
    with open(config_file) as f:
        config = yaml.safe_load(f)
        
    logging.config.dictConfig(config)

__all__ = ["setup_logging", 'AppJSONFormatter']