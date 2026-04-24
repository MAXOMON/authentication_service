import logging.config

from pythonjsonlogger import jsonlogger


LOGGING = {
    "version": 1,
    "filename": "app.log",
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(levelname)s %(message)s %(module)s",
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        }
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "level": "INFO",
            "formatter": "json",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "app/log_file.log",
            "level": "INFO",
            "formatter": "json",
        },
    },
    "loggers": {"app": {"handlers": ["stdout", "file"], "level": "INFO"}},
}

logging.config.dictConfig(LOGGING)
logging.basicConfig
