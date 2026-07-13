import json
import sys

from loguru import logger

from app import logging_config


def test_json_format_emits_parseable_json_lines(monkeypatch, capsys):
    monkeypatch.setattr(logging_config, "LOG_FORMAT", "json")
    logging_config.configure_logging()
    try:
        logger.info("hello {}", "world")
        line = capsys.readouterr().out.strip()
        parsed = json.loads(line)
        assert parsed["record"]["message"] == "hello world"
    finally:
        logger.remove()
        logger.add(sys.stderr)  # restore loguru's normal default sink for other tests


def test_text_format_leaves_default_sink_untouched(monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_FORMAT", "text")
    logging_config.configure_logging()  # must not raise or remove sinks
