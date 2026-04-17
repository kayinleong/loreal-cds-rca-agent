import logging
from datetime import datetime, timezone
import os
import sys

class Logger:
    _instance = None

    def __new__(cls, name):
        if cls._instance is None:
            name_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            level = logging.INFO
            if os.environ.get("ENVIRONMENT") == "pd":
                level = logging.INFO
            else:
                level = logging.DEBUG

            cls._instance = cls._Logger(name, level, log_file=f"{name_prefix}.log")
        return cls._instance

    def create_logger(self):
        return self._instance.create_logger()

    class _Logger:
        def __init__(self, name: str = "pipeline", level: int = logging.INFO, log_file: str = "pipeline.log"):
            self.name = name
            self.log_file = log_file
            self.level = level

        def get_log_file_name(self):
            return self.log_file

        def create_logger(self):
            logger = logging.getLogger(self.name)
            logger.setLevel(self.level)

            if logger.hasHandlers():  # changed from `if logger.handlers` for correctness
                return logger

            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # File handler (not visible in Cloud Run logs)
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(self.level)  
            file_handler.setFormatter(formatter)

            # Console handler using sys.stdout (Cloud Run reads stdout)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.level)  
            console_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

            return logger
