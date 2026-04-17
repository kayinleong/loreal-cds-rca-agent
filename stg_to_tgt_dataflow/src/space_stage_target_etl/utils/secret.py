from google.cloud import secretmanager
import google.auth
from space_stage_target_etl.utils.logger import CloudLogger

# Setup Google Cloud Logging
logger = CloudLogger().get_logger()

def get_secret(secret_name):
    prj_id = google.auth.default()[1]

    client = secretmanager.SecretManagerServiceClient()
    project_id = prj_id  # Replace with your project ID
    secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    try:
        # Access the secret
        response = client.access_secret_version(name=secret_path)
        secret_data = response.payload.data.decode("UTF-8")  # Secret value

        return secret_data
    except Exception as e:
        logger.error(f"Error accessing secret '{secret_name}': {e}")
        raise RuntimeError(f"Error accessing secret '{secret_name}': {e}")
