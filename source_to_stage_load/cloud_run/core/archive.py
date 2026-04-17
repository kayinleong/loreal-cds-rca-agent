from google.cloud import storage
import re
from core.logger import Logger
logger = Logger(name="batch log").create_logger()

def archive_file(source_uri: str, destination_bucket_name: str):
    """
    Move a file from a GCS URI to another GCS bucket, preserving the full folder path.
    
    Args:
        source_uri (str): Full GCS URI, e.g., gs://source-bucket/folder1/sub/file.csv
        destination_bucket_name (str): Destination bucket name, e.g., my-destination-bucket
    """
    destination_bucket_name = destination_bucket_name.replace("gs://", "")
    match = re.match(r'gs://([^/]+)/(.+)', source_uri)
    if not match:
        raise ValueError("Source URI must be in the format 'gs://bucket-name/path/to/file'")

    source_bucket_name, source_object_path = match.groups()

    client = storage.Client()
    source_bucket = client.bucket(source_bucket_name)
    destination_bucket = client.bucket(destination_bucket_name)

    source_blob = source_bucket.blob(source_object_path)
    if not source_blob.exists():
        raise FileNotFoundError(f"Source file not found: {source_uri}")

    source_bucket.copy_blob(
        source_blob, destination_bucket, source_object_path
    )
    source_blob.delete()
    
    logger.info(f"Moved file from {source_uri} to gs://{destination_bucket_name}/{source_object_path}")
