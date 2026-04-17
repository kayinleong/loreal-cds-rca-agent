from google.cloud import secretmanager
import google.auth
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()
def get_secret(secret_name):
    """Fetch the secret value from GCP Secret Manager."""
    secret_client = secretmanager.SecretManagerServiceClient()
    _, project_id = google.auth.default()
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    logger.info("Fetching secret: %s", secret_name)
    try:
        response = secret_client.access_secret_version(name=secret_path)
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error("Failed to fetch secret %s: %s", secret_name, str(e))
        raise