"""The queue wiring fails silently: dictConfig builds the QueueListener but leaves it
stopped, so a missing start() means every record is dropped with no error anywhere."""

import json
import logging
import logging.handlers

import pytest
import yaml

from app.core import logging as app_logging


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    """Run the real config, but write the JSON sink into tmp."""
    config = yaml.safe_load(app_logging.CONFIG_FILE.read_text())
    target = tmp_path / "log.jsonl"
    config["handlers"]["file"]["filename"] = str(target)

    config_copy = tmp_path / "logging_config.yaml"
    config_copy.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(app_logging, "CONFIG_FILE", config_copy)

    yield target

    logging.root.handlers.clear()


def test_record_reaches_the_json_sink(log_file):
    # Created before setup_logging, like every app.services logger is.
    logger = logging.getLogger("service.test")

    app_logging.setup_logging()
    logger.info("board initialized: seeded=%s", True)
    queue_handler = logging.getHandlerByName("queue_handler")
    assert isinstance(queue_handler, logging.handlers.QueueHandler)
    assert queue_handler.listener is not None
    queue_handler.listener.stop()  # drains the queue

    entry = json.loads(log_file.read_text().splitlines()[-1])
    assert entry["message"] == "board initialized: seeded=True"
    assert entry["logger"] == "service.test"
    assert entry["otelTraceID"] == "0"  # injected even with OTEL disabled
    assert entry["correlation_id"] == "-"


def test_creates_a_missing_log_directory(tmp_path, monkeypatch):
    """logs/ is gitignored, so a fresh checkout has none and the file handler cannot
    make its own -- dictConfig used to die with "Unable to configure handler 'file'"."""
    config = yaml.safe_load(app_logging.CONFIG_FILE.read_text())
    target = tmp_path / "does" / "not" / "exist" / "log.jsonl"
    config["handlers"]["file"]["filename"] = str(target)

    cfg_file = tmp_path / "logging_config.yaml"
    cfg_file.write_text(yaml.safe_dump(config))
    monkeypatch.setattr(app_logging, "CONFIG_FILE", cfg_file)

    app_logging.setup_logging()

    assert target.parent.is_dir()
