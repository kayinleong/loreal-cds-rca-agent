import os
import json
import requests
import re
from google.auth.transport.requests import Request
from google.cloud import storage
import google.auth
import logging
from google.cloud import logging as cloud_logging
from google.auth import default
import time

# Set up Google Cloud Logging handler
client = cloud_logging.Client()
client.setup_logging()

logger = logging.getLogger(__name__)

RETRY_COUNT = 5
RETRY_DELAY = 60

env = os.environ.get('ENV', 'pd').lower() 
if env in ('dv', 'qa'):
    logger.setLevel(logging.DEBUG)
    logger.info("Setting log level to DEBUG")
elif env == 'pd':
    logger.setLevel(logging.INFO)
    logger.info("Setting log level to INFO")
else:
    logger.setLevel(logging.INFO)
    logger.warning(f"Unknown environment: {env}, defaulting to INFO")

CONCURRENT_BUSINESS_TYPES = ["b2b"]


def get_country_folder(business_type, country):
    """Return config market folder name based on business type and country."""
    if country in ("AU", "NZ"):
        return "ANZ"
    return "WW" if business_type == "b2b" else "COMMON"

def get_access_token():
    """Retrieve the OAuth2 access token using the Cloud Function's service account."""
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    return credentials.token

def read_json_from_gcs(bucket_name, file_path):
    """
    Reads a JSON file from Google Cloud Storage and returns its content as a JSON object.

    Args:
        bucket_name (str): The name of the GCS bucket.
        file_path (str): The path to the JSON file within the bucket.

    Returns:
        dict: The JSON content of the file, or None if an error occurs.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_path)

    try:
        config_file = blob.download_as_string()
        config_json = json.loads(config_file)
        return config_json
    except Exception as e:
        logger.error(f"Error reading {file_path} from {bucket_name}: {e}")
        return None


def is_execution_blocked(project_id, region, target_job_pattern, business_type):
    """
    Check if execution is blocked due to a running concurrent job.
    
    Args:
        project_id (str): The GCP project ID
        region (str): The GCP region
        target_job_pattern (str): The job name pattern to check
        business_type (str): The business type
        
    Returns:
        bool: True if execution is blocked, False otherwise
    """
    return is_dataflow_job_running(project_id, region, target_job_pattern) and business_type not in CONCURRENT_BUSINESS_TYPES


def launch_dataflow_job(template_path, parameters, job_name, network, subnetwork, service_account_email, sdk_container_image, region, project_id):
    """Launch a Dataflow job with the given parameters."""

    dataflow_api_url = f"https://dataflow.googleapis.com/v1b3/projects/{project_id}/locations/{region}/flexTemplates:launch"

    # Prepare the launch parameters
    launch_parameters = {
        "jobName": job_name,
        "containerSpecGcsPath": template_path,
        "parameters": parameters,
        "environment": {
            "sdkContainerImage": sdk_container_image,
            "network": network,
            "subnetwork": subnetwork,
            "serviceAccountEmail": service_account_email,
            "additionalExperiments": ["enable_preflight_validation=false"],
            "ipConfiguration": "WORKER_IP_PRIVATE"
        }
    }

    # Prepare the request body
    body = {
        "launchParameter": launch_parameters
    }

    # Get the access token
    access_token = get_access_token()

    # Prepare the headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Make the POST request
    logger.info(f"Running Dataflow job: {job_name}")
    response = requests.post(dataflow_api_url, headers=headers, json=body)

    # Check the response
    if response.status_code == 200:
        logger.info("Job successfully launched!")
        logger.info("Job started. Check the Dataflow console for status.")
        return response.json()
    else:
        logger.error(f"Failed to launch job: {response.status_code}, {response.text}")
        return None


def main(request):

    request_json = request.get_json(silent=True)
    if not request_json:
        logger.error("Invalid request: JSON body required")
        return "Invalid request: JSON body required"
    # Extract data from the Cloud Storage event
    bucket_name = request_json['bucket']
    file_name = request_json['name']
    logger.info(f"Event Received: {request_json}")
    logger.info(f"Bucket: {bucket_name}, File: {file_name}")

    # Validate if file exists in the bucket
    full_file_path = f"gs://{bucket_name}/{file_name}"
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    if not blob.exists():
        logger.info(f"The File {full_file_path} likely has already been processed from previous event trigger.")
        return "The file likely has already been processed", 200

    # Environment  short_region_name , env is environment variables
    _, project_id = google.auth.default()
    region = os.environ.get('REGION')
    region_short = os.environ.get('SHORT_REGION_NAME')


    business_type = bucket_name[10:13]
    if 'batch_inbound' in bucket_name:
        # Parse file path with validation
        file_parts = file_name.split('/')
        if len(file_parts) != 3:
            logger.error(f"Invalid file path format. Expected 'country/source/filename', received: {full_file_path}")
            return f"Invalid file path format. Expected 'country/source/filename', got: {file_name}"
        
        country = file_parts[0]
        source = file_parts[1]
        filename = file_parts[2]

        # Load patterns and details from JSON from GCS
        config_bucket_name = f"space_cds_{business_type}-gcs-config-{region_short}-{env}"
        file_path = "dataflow-job-params.json" #path will change
        config_json = read_json_from_gcs(config_bucket_name,file_path)
           
        file_match_flag = False
        # Check if business_type and source exist in config_json
        if business_type not in config_json or source not in config_json[business_type]:
            logger.error("File match not found: business_type or source missing in config_json")
            return 'File Match Not Found'
        
        if 'allowed_markets' in config_json[business_type]:
            allowed_markets = config_json[business_type]['allowed_markets']
            if country not in allowed_markets:
                logger.error(f"Market {country} not allowed to trigger dataflow job for business type {business_type}")
                return f"Market {country} not allowed to trigger dataflow job for business type {business_type}"
            
        for key, value in config_json[business_type][source].items():

            if re.match(key, filename):
                logger.info("match  found")
                pattern = key[1:]
                config_path = value['config_path']
                domain_name_validation = value['domain_name_validation']
                table = value['table']
                load_type = value['load_type']
                frequency = value.get('frequency',None) 
                description = value['description']
                next_df_params = value['next_df_params']
                json_schema = value.get('validation_json',None)
                validation_json = str(json_schema) if json_schema else None
                file_match_flag = True
                logger.info(value)
                break
            else:
                continue
        if not file_match_flag:
            logger.error(f"File match not found for {full_file_path}")
            return 'File Match Not Found'
        dependency_lookback_window_hours = config_json[business_type]['dependency_lookback_window_hours']
        sp_name = next_df_params.get('sp_name','')
        next_df_params['dependency_lookback_window_hours']=dependency_lookback_window_hours
        # get sdk container image
        sdk_container_image = read_json_from_gcs(f"space_cds_b2c-gcs-config-{region_short}-{env}",'flex-template.json')['image']
        load_type_folder = "migration" if load_type.lower()=='migr' else "integration"
        country_folder = get_country_folder(business_type, country)
        
        template_path = f"gs://space_cds_b2c-gcs-config-{region_short}-{env}/flex-template.json"  ##can retrive dyanmically
        # sdk_container_image need to check
        network = f"space-cds-vpc-{region_short}-{env}"
        subnetwork = f"regions/{region}/subnetworks/space-cds-subnet-{region_short}-{env}"
        #sdk_container_image = f"{region}-docker.pkg.dev/{project_id}/spacecds-docker/space-cds-etl-core:latest"
        input_path = f"gs://{bucket_name}/{country}/{source}/{pattern}" 
        market_code = country
        source_system_name = source
        service_account_email = f"dataflow-sa-deploy-{env}@{project_id}.iam.gserviceaccount.com"
        if business_type=="b2b":
            config_gcs_path = f"gs://space_cds_{business_type}-gcs-config-{region_short}-{env}/src/{load_type_folder}/{country_folder}/PPD/{source}/config/{config_path}" 
        else:
            config_gcs_path = f"gs://space_cds_{business_type}-gcs-config-{region_short}-{env}/src/{load_type_folder}/{country_folder}/{source}/config/{config_path}" 
        db_mapping_config = f"gs://space_cds_{business_type}-gcs-config-{region_short}-{env}/db_mapping_config.yaml"
        archive_bucket_name = f"gs://space_cds_{business_type}-gcs-batch_archive-{region_short}-{env}"
        baton_file_bucket = f"gs://space_cds_{business_type}-gcs-batch_dataflow_baton-{region_short}-{env}"
        environment = env
        gcs_uri_error = f"gs://space_cds_{business_type}-gcs-batch_error-{region_short}-{env}"
        gcs_uri_log = f"gs://space_cds_{business_type}-gcs-batch_log-{region_short}-{env}"


        ## this block is for migration of SGMY in pt
        ## block started
        # check for pt environment
        if env == 'qa' and bucket_name.split("-")[-1] == 'pt':
            environment = 'pt'
            archive_bucket_name = f"gs://space_cds_{business_type}-gcs-batch_archive-{region_short}-{environment}"
            baton_file_bucket = f"gs://space_cds_{business_type}-gcs-batch_dataflow_baton-{region_short}-{environment}"

        if load_type.lower()=='int':
            job_name = business_type + '-' + country + "-" + source.replace("_", "") + "-to-cds-" + load_type + "-" + description.lower().replace("_", "").replace(" ", "") + "-in-" + frequency + "-" + environment
        else:
            job_name = business_type + '-' + country + "-" + source.replace("_", "") + "-to-cds-" + load_type + "-" + description.lower().replace("_", "").replace(" ", "") + "-in-"  + environment
        job_name = job_name.lower()

        ## block ended    

        """Launch the Dataflow job."""
        

        # Prepare parameters
        parameters = {
            "input_path": input_path,
            "market_code": market_code,
            "source_system_name": source_system_name,
            "config_gcs_path": config_gcs_path,
            "environment": environment,
            "domain_name_validation": domain_name_validation,
            "db_mapping_config": db_mapping_config,
            "table": table,
            "error_bucket": gcs_uri_error,
            "validation_json": validation_json,
            "gcs_uri_log": gcs_uri_log,
            "archive_bucket_name": archive_bucket_name,
            "business_type": business_type,
            "sdk_container_image": sdk_container_image,
            "next_df_params" :  str(next_df_params),
            "baton_file_bucket" : baton_file_bucket
            
        }
        logger.info(f'Parameters to be passed : {parameters} ')

        if load_type.lower() == 'int':
            target_job_pattern = f'stg-to-tgt-{load_type}-{sp_name}-in-{frequency}-{environment}'
        else:
            target_job_pattern = f'stg-to-tgt-{load_type}-{sp_name}-in-{environment}'
        target_job_pattern = target_job_pattern.replace('_','-').lower().replace('--', '-')
        logger.info(f'Checking if Dataflow job {target_job_pattern} is already running.')
        if not is_multi_market_job_running(project_id, region, target_job_pattern, business_type) and not is_dataflow_job_running(project_id, region, job_name):
            response = launch_dataflow_job(template_path, parameters, job_name, network, subnetwork, service_account_email, sdk_container_image, region, project_id)
        else:
            logger.info("Dataflow job is already running.")
            return "Dataflow job is already running.", 200

        # Check the response
        if response:
            return response
        else:
            logger.error("Failed to launch Dataflow job.")
            return "Failed to launch Dataflow job"
    elif 'dataflow_baton' in bucket_name:
        full_file_path = f"gs://{bucket_name}/{file_name}"
        baton_json = read_json_from_gcs(bucket_name,file_name)
        db_mapping_config = f"gs://space_cds_{business_type}-gcs-config-{region_short}-{env}/db_mapping_config.yaml"
        sdk_container_image = read_json_from_gcs(f"space_cds_b2c-gcs-config-{region_short}-{env}",'dataflow-target-load/flex-template.json')['image']
        market_code = baton_json['market_code']
        sp_name = baton_json.get('sp_name', '')
        frequency = baton_json.get('frequency', '')
        load_type = baton_json['loadtype']
        source_system_name = baton_json['source_system_name']
        log_bucket = f"space_cds_{business_type}-gcs-batch_log-{region_short}-{env}"
        environment = env
        # this block is for migration of SGMY in pt
        # block started 
         # check for pt environment
        if env == 'qa' and bucket_name.split("-")[-1] == 'pt':
            environment = 'pt'
        ## block ended    
        # Prepare parameters
        parameters = {
            "baton_file_path":full_file_path,
            "market_code": market_code,
            "db_mapping_path": db_mapping_config,
            "sp_name": sp_name,
            "business_type": business_type,
            "env": environment,
            "source_system_name": source_system_name,
            "log_bucket": log_bucket
        }
        logger.info(f'Parameters to be passed : {parameters} ')
        template_path = f"gs://space_cds_b2c-gcs-config-{region_short}-{env}/dataflow-target-load/flex-template.json"  
        # sdk_container_image need to check

        network = f"space-cds-vpc-{region_short}-{env}"
        subnetwork = f"regions/{region}/subnetworks/space-cds-subnet-{region_short}-{env}"
        service_account_email = f"dataflow-sa-deploy-{env}@{project_id}.iam.gserviceaccount.com"
        

        #sdk_container_image = "asia-southeast1-docker.pkg.dev/oa-apmena-spacecds-ap-dv/spacecds-docker/space-cds-etl-tgt-load-dataflow:41abbbc"
        if load_type.lower() == 'int':
            job_name = business_type + '-' + market_code + '-stg-to-tgt-' + load_type + '-' + sp_name + '-in-' + frequency  + '-' + environment
        else:
            job_name = business_type + '-' + market_code + '-stg-to-tgt-' + load_type + '-' + sp_name + '-in-' + environment
        job_name = job_name.replace('_','-').lower().replace('--', '-')

        if load_type.lower() == 'int':
            target_job_pattern = f'stg-to-tgt-{load_type}-{sp_name}-in-{frequency}-{environment}'
        else:
            target_job_pattern = f'stg-to-tgt-{load_type}-{sp_name}-in-{environment}'
        target_job_pattern = target_job_pattern.replace('_','-').lower().replace('--', '-')
        logger.info(f'Checking if Dataflow job {target_job_pattern} is already running.')

        if not is_multi_market_job_running(project_id, region, target_job_pattern, business_type) and not is_dataflow_job_running(project_id, region, job_name) : 
            response = launch_dataflow_job(template_path, parameters, job_name, network, subnetwork, service_account_email, sdk_container_image, region, project_id)
        else:
            logger.info("Dataflow job is already running.")
            return "Dataflow job is already running.", 200

        if response:
            delete_file(full_file_path)
            return response
        else:
            logger.error("Failed to launch Dataflow job.")
            return "Failed to launch Dataflow job"
    else:
        logger.info(f'Bucket name {bucket_name} is not considered in event')
        return f'Bucket name {bucket_name} is not considered in event'

def is_dataflow_job_running(project_id, region, job_name_filter, timeout=60):
    """Check if a Dataflow job matching the filter is currently running or pending."""
    try:
        # Get access token for authentication
        creds, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(Request())
        access_token = creds.token
        
        # Use REST API directly to avoid httplib2 timeout issues
        api_url = f"https://dataflow.googleapis.com/v1b3/projects/{project_id}/locations/{region}/jobs"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        jobs_data = response.json()
        active_states = ("JOB_STATE_RUNNING", "JOB_STATE_PENDING", "JOB_STATE_QUEUED", "JOB_STATE_STARTING")
        for job in jobs_data.get("jobs", []):
            if job_name_filter in job["name"] and job["currentState"] in active_states:
                logger.info(f"Found running/pending job: {job['name']} with state: {job['currentState']}")
                return True
        
        logger.info(f"No running/pending job found matching: {job_name_filter}")
        return False
        
    except Exception as e:
        logger.error(f"Error checking Dataflow jobs: {e}")
        return True
    



def is_multi_market_job_running(project_id, region, target_job_pattern, business_type):
    retry = 0
    while retry < RETRY_COUNT:
        retry += 1
        if is_execution_blocked(project_id, region, target_job_pattern, business_type):
            time.sleep(RETRY_DELAY)
            logger.info("Dataflow job is already running.")
        else:
            return False
        if retry == RETRY_COUNT:
            logger.info("Max retries reached. Exiting.")
            return True

def delete_file(file_path):
    """Delete a file from Google Cloud Storage."""
    try:

        client = storage.Client()
        bucket_name = file_path.split('/')[2]
        blob_name = '/'.join(file_path.split('/')[3:])
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
        logger.info(f"File '{file_path}' deleted successfully.")
    except Exception as e:
        logger.error(f"Error deleting file '{file_path}': {e}")