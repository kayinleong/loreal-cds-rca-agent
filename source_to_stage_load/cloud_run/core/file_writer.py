import json
from google.cloud import storage
from datetime import datetime, timezone
from urllib.parse import urlparse
from core.logger import Logger
logger = Logger(name = "batch log").create_logger()

def get_file_name(prefix="file", ext=".jsonl"):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    filename = f"/tmp/{prefix}_{timestamp}{ext}"
    return filename



def create_empty_file(file_path: str):
    """Creates an empty file at the given path."""
    with open(file_path, "w", encoding="utf-8"):
        pass  # Simply creates the file, does nothing else
    logger.info(f"Empty file created at {file_path}")


def error_writer(file_path: str, lines):
    """Appends lines to the existing file."""
    with open(file_path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def log_writer(file_path: str, records):
    """Writes a list of dicts to a JSONL file."""
    with open(file_path, "a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")




def upload_file_to_gcs_uri(local_path: str, gcs_path: str) -> None:
    """
    Uploads a local file to GCS using a full GCS path.

    Args:
        local_path (str): Local path to the file.
        gcs_path (str): Full GCS path (e.g., gs://bucket-name/path/to/blob.txt).
    """
    try:
        # Parse GCS URI
        if not gcs_path.startswith("gs://"):
            raise ValueError("gcs_path must start with 'gs://'")
        
        parsed = urlparse(gcs_path)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")

        # Upload
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)

        logger.info(f"Uploaded {local_path} to {gcs_path}")
    except Exception as e:
        logger.error(f"Failed to upload file to GCS: {e}")
        raise

