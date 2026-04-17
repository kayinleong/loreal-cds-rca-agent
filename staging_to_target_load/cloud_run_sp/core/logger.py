import logging
from datetime import datetime, timezone
class Logger:

    _instance = None

    def __new__(cls,name,level: int = logging.INFO):
        if cls._instance is None:
            name_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")

            cls._instance = cls._Logger(name, level,log_file = f"{name_prefix}.log")
        return cls._instance
    
    def create_logger(self):
        return self._instance.create_logger()


    class _Logger:

        def __init__(self,name: str = "pipeline", level: int = logging.INFO,log_file: str = "pipeline.log"):
            self.name = name
            self.log_file = log_file
            self.level = level

        def get_log_file_name(self):
            return self.log_file

            


        def create_logger(self):
            logger = logging.getLogger(self.name)
            logger.setLevel(self.level)


            if logger.handlers:
                return logger

            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )


            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)


            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

            return logger