
from datetime import datetime
from zoneinfo import ZoneInfo
import re
from google.cloud import storage

from space_cds_etl_core.utils.constants import GSUTIL_URI_PREFIX
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()   

def copy_file(source_uri: str, destination_bucket_name: str, destination_blob):
    """
    Move a file from a GCS URI to another GCS bucket, preserving the full folder path.
        
    Args:
        source_uri (str): Full GCS URI, e.g., gs://source-bucket/folder1/sub/file.csv
        destination_bucket_name (str): Destination bucket name, e.g., my-destination-bucket
    """
    if destination_bucket_name.startswith(GSUTIL_URI_PREFIX):
        destination_bucket_name = destination_bucket_name.removeprefix(GSUTIL_URI_PREFIX)
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
        source_blob, destination_bucket, destination_blob
    )
    return source_blob


def archive_file(source_uri: str, destination_bucket_name: str, df_args):
    destination_blob = get_file_path(source_uri, df_args)
    source_blob = copy_file(source_uri, destination_bucket_name, destination_blob)
    source_blob.delete()

def get_file_path(source_uri: str, df_args: dict) -> str:
    today_date = datetime.now(ZoneInfo("UTC")).date()
    today_date = str(today_date)
    file_name = source_uri.split("/")[-1]
    destination_blob = f"{df_args['market_code']}/{df_args['source_system_name']}/inbound/{today_date}/{file_name}"
    return destination_blob