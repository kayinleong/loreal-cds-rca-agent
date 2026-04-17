import yaml
import psycopg2
from psycopg2 import OperationalError
from google.cloud import storage
from space_stage_target_etl.utils.secret import get_secret
from space_stage_target_etl.utils.logger import CloudLogger
from space_stage_target_etl.config import CONFIG

# Setup Google Cloud Logging
logger = CloudLogger().get_logger()

def get_database(environment, market_code, db_mapping_path):
    bucket_name = db_mapping_path.split("gs://")[-1].split("/")[0]
    file_path = db_mapping_path.replace(f"gs://{bucket_name}/", "")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(file_path)
    yaml_content = blob.download_as_text()
    data = yaml.safe_load(yaml_content)
    try:
        database = data.get("environments").get(environment).get("databases").get(market_code)
        return database
    except KeyError:
        logger.error(
            f"Missing key in YAML file for database configuration: '{environment}', 'databases', or '{market_code}'.",
        )
        raise KeyError(f"Missing key in YAML file for database configuration: '{environment}', 'databases', or '{market_code}'.")

def get_credentials(business_type):
    #get business_type from dataflow pipeline options
    str_pswd = 'space_cds-srt-cloudsql_' + business_type + '_pwd'
    str_usr = 'space_cds-srt-cloudsql_' + business_type + '_user'
    #str_host = 'space_cds-srt-cloudsql_instance_ip'
    pswd = get_secret(str_pswd)
    user = get_secret(str_usr)
    #host = get_secret(str_host)
    return user, pswd#, host

def get_database_config(environment, market_code, db_mapping_path,business_type):
    user, pswd = get_credentials(business_type)
    database = get_database(environment, market_code, db_mapping_path)
    db_config = {
        "host": CONFIG[environment]["SQL_INSTANCE_IP"][market_code.lower()],
        "database": database,
        "user": user,
        "password": pswd
    }
    return db_config

def create_connection(environment, market_code, db_mapping_path,business_type):
    db_config = get_database_config(environment, market_code, db_mapping_path,business_type)
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            dbname=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
            port=db_config.get("port", 5432)
        )
        return conn
    except OperationalError as e:
        logger.error(
            f"Failed to connect to the PostgreSQL database: {e}",
        )
        raise RuntimeError(f"Failed to connect to the PostgreSQL database: {e}")
    except Exception as e:
        logger.error(
            f"Unexpected error during database connection: {e}",
        )
        raise RuntimeError(f"Unexpected error during database connection: {e}")
 