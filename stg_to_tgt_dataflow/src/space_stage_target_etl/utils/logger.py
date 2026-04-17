import logging
from google.cloud.logging_v2.handlers import StructuredLogHandler
from google.cloud import storage
from datetime import datetime
from zoneinfo import ZoneInfo
def upload_log_to_gcs(bucket_name, source_sys_name, destination_blob_name):
    """
    Uploads a file to Google Cloud Storage.

    Args:
        bucket_name: Name of the GCS bucket.
        source_sys_name: Path to the local file.
        destination_blob_name: Destination path in the GCS bucket.
    """
    bucket_name = bucket_name.replace("gs://", "")
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_sys_name)

def create_file_name(market, source_sys_name, job_name):
    today_date = datetime.now(ZoneInfo("UTC")).date()
    today_date = str(today_date)
    current_utc_time = datetime.now(ZoneInfo("UTC"))
    zulu_time = current_utc_time.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    file_name = f"{market.upper()}/{source_sys_name}/{today_date}/{zulu_time}_{job_name}.log"
    return file_name



class CloudLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CloudLogger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance

    def _initialize_logger(self):
        cloud_handler = StructuredLogHandler()
        file_handler = logging.FileHandler('application_logs.log')

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        self.logger = logging.getLogger("dataflow-logger")

        if not self.logger.handlers:
            self.logger.addHandler(cloud_handler)
            self.logger.addHandler(file_handler)

    def get_logger(self, level=logging.INFO):
        self.logger.setLevel(level)  # Dynamically set log level
        return self.logger