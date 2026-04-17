import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions,GoogleCloudOptions
from space_cds_etl_core.pipeline.reader import ReadFromGCS
from space_cds_etl_core.pipeline.transformer import GenericTransformer
import yaml
import os
import argparse
from space_cds_etl_core.pipeline.validate_data import ValidateData
import tempfile
from datetime import datetime,timezone
from apache_beam.io.filesystems import FileSystems
from space_cds_etl_core.pipeline.writer import GenericWriter
from space_cds_etl_core.utils.writeinvalid import WriteInvalidData
from space_cds_etl_core.utils.db_connector import DBConnector
from space_cds_etl_core.pipeline.validator import JsonValidator
import ast
from space_cds_etl_core.utils.json_csv import process_json_to_csv
from space_cds_etl_core.utils.audit_logger import AuditLogger
from space_cds_etl_core.utils.logger import CloudLogger, upload_log_to_gcs, create_file_name
import re
from space_cds_etl_core.config import DEFAULT_BATCH_SIZE
logger = CloudLogger().get_logger()
GSUTIL_URI_PREFIX = "gs://"


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_path", required=True, help="The GCS path to the input data.")
    parser.add_argument("--market_code", required=True, help="The 2-character ISO market code (e.g., SG, AU).")
    parser.add_argument("--source_system_name", required=True, help="The name of the source system (e.g., SAP, MARS).")
    parser.add_argument("--config_gcs_path", required=True, help="GCS path to the config.yaml file.")
    parser.add_argument("--environment",required=True,help="setting the environment")
    parser.add_argument("--db_mapping_config",required=True,help="db mapping file")
    parser.add_argument("--table",required=True,help="table to be loaded")
    parser.add_argument("--business_type",required=True,help="table to be loaded")
    parser.add_argument("--error_bucket",required=True,help="store rejected records")
    parser.add_argument("--next_df_params",required=True,help="params for next dataflow")
    parser.add_argument("--archive_bucket_name",required=True,help="bucket for archiving the files")
    parser.add_argument("--baton_file_bucket",required=True,help="bucket for baton file")
    parser.add_argument("--validation_json",required=True,help="bucket for baton file")
    parser.add_argument("--gcs_uri_log",required=True,help="gcs_uri_log")
    parser.add_argument("--domain_name_validation",required=True,help="domain name")


    known_args, pipeline_args = parser.parse_known_args()    
    return known_args, pipeline_args

def validate_arguments(known_args):
    """Validate command-line arguments."""
    market_code = str(known_args.market_code)
    if not (re.fullmatch(r"[A-Z]{2}", market_code) or market_code == "COMMON"):
        logger.error("Invalid market_code: Must be a 2-letter string (e.g., 'US', 'SG') or 'COMMON'.")
        exit(1)


    if not known_args.config_gcs_path.startswith(GSUTIL_URI_PREFIX):
        logger.error("Invalid config_gcs_path: Must be a GCS bucket path (e.g., 'gs://test-bucket/config.yaml').")
        exit(1)
    
    if known_args.business_type not in ["b2b", "B2B", "b2c", "B2C"]:
        logger.error("Invalid business_type: Must be either 'b2b' or 'b2c'.")
        exit(1)

def download_from_gcs(gcs_path, local_path):
    """Download a file from GCS to a local path."""

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with FileSystems.open(gcs_path) as gcs_file:
        with open(local_path, 'wb') as local_file:
            local_file.write(gcs_file.read())

    logger.info("Downloaded %s to %s", gcs_path, local_path)

def load_config_path(config_gcs_path):
    """Download and load configuration from GCS."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        local_config_path = tmp_file.name
        download_from_gcs(config_gcs_path, local_config_path)
        return local_config_path

def load_config(config_gcs_path):
    local_config_path = load_config_path(config_gcs_path)
    with open(local_config_path, "r") as f:
        return yaml.safe_load(f)
    


def run_pipeline():
    known_args, pipeline_args = parse_arguments()

    validate_arguments(known_args)  # Validate arguments before proceeding

    config = load_config(known_args.config_gcs_path)
    try:
        delimiter = config['file_delimiter']
        config['delimiter'] = delimiter
    except KeyError:
        _ = config['delimiter']
    is_target_load = config.get("isTargetLoad", False)
    if is_target_load:
        pipeline_args.append('--worker_machine_type=n1-standard-2')

    db_config = load_config(known_args.db_mapping_config)
    environment = known_args.environment
    env_config = db_config.get("environments")
    market_code = known_args.market_code
    error_bucket = known_args.error_bucket.replace("gs://", "")

    if not env_config:
        raise ValueError(f"Invalid or missing configuration for environment: {environment}")
    
    db_mapping = env_config.get(environment,"dv").get("databases")
    



    pipeline_options = PipelineOptions(pipeline_args)
    gcloud_options = pipeline_options.view_as(GoogleCloudOptions)
    job_name = gcloud_options.job_name

    file_name = known_args.input_path.split("/")[-1]

    try:
        json_schema_name = ast.literal_eval(known_args.validation_json)
    except (ValueError, SyntaxError):
        logger.warning(
            "Error parsing validation_json: expected in list format. "
            "Treating validation_json as a single string."
        )
        json_schema_name = known_args.validation_json

    df_args = {
        "input_path": known_args.input_path,
        "market_code": market_code,
        "source_system_name": known_args.source_system_name,
        "config_gcs_path": known_args.config_gcs_path,
        "environment": environment,
        "db_mapping_config": known_args.db_mapping_config,
        "table": known_args.table,
        "business_type": known_args.business_type.lower(),
        "loadstarttime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "job_name": job_name,
        "next_df_params": ast.literal_eval(known_args.next_df_params),
        "archive_bucket_name": known_args.archive_bucket_name,
        "baton_file_bucket": known_args.baton_file_bucket.replace(GSUTIL_URI_PREFIX, ""),
        "json_schema_name": json_schema_name,
        "log_bucket": known_args.gcs_uri_log.replace(GSUTIL_URI_PREFIX, ""),
        "job_id": gcloud_options.template_location.split('/')[5],
        "domain_name_validation": known_args.domain_name_validation,
        "error_bucket": error_bucket
        
    }

    if '-migr-' in job_name:
        df_args['job_type'] = 'migr'
    elif '-int-' in job_name:
        df_args['job_type'] = 'int'
    
    logger.info("Pipeline arguments: %s", df_args)
    logger.info("next_df_params: %s", df_args['next_df_params'])
     
    error_file = job_name + "-" + df_args['job_id'] + "-" +datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" + ".csv"

    df_args['encoding_error_file'] = f"{GSUTIL_URI_PREFIX}{error_bucket}/{df_args['market_code']}/{df_args['source_system_name']}/encoding_error_file/{error_file}"

    error_file = f"{GSUTIL_URI_PREFIX}{error_bucket}/{df_args['market_code']}/{df_args['source_system_name']}/{error_file}"


    df_args['corrupted_row_file_prefix'] = f"{GSUTIL_URI_PREFIX}{error_bucket}/{df_args['market_code']}/{df_args['source_system_name']}/"

    if ".json" in df_args["input_path"]:
        file_name = df_args['input_path'].split("/")[-1]  # Extract the file name from the input path
        prefix = df_args['input_path'].replace(file_name, "")
        df_args['input_path'], df_args['input_json_path'] = process_json_to_csv(df_args['input_path'], prefix, df_args['market_code'])
        

    db_connector = DBConnector(db_mapping, market_code, df_args['business_type'], df_args['environment'])
    json_validators = []
    if isinstance(df_args['json_schema_name'], str) and df_args['json_schema_name']:
        df_args['json_schema_name'] = [df_args['json_schema_name']]
        logger.info("json_schema_name is a string, converting to list: %s", df_args['json_schema_name'])
    logger.info("Loading schema: %s", df_args['json_schema_name'])
    for schema in df_args['json_schema_name']:

        logger.info("Loading schema: %s", schema)
        json_validators.append(
            JsonValidator(market_code.lower(), 
                          df_args['business_type'], 
                          df_args,
                          schema, 
                          df_args['domain_name_validation'],
                          config
                        )
        )
    with beam.Pipeline(options=pipeline_options) as p:

        data = (
            p
            | "Read from GCS" >> ReadFromGCS(df_args, config , environment)
            | "Apply Transformations" >> beam.ParDo(GenericTransformer(config, df_args,db_connector))
            | "Validate data" >> beam.ParDo(ValidateData(market_code,df_args['json_schema_name'],json_validators)).with_outputs('error', main='valid')
            
        )

            
        # Batch elements before writing to enable TaggedOutput for all records
        batch_size = config.get("batch_size", DEFAULT_BATCH_SIZE)
        write_results = (
            data.valid 
            | "Batch Elements" >> beam.BatchElements(min_batch_size=batch_size, max_batch_size=batch_size)
            | "Write to Cloud SQL" >> beam.ParDo(GenericWriter(config, df_args, db_connector)).with_outputs('database_error', main='success')
        )
            

        data.error | "Write invalid data" >> WriteInvalidData(error_file, 
            delimiter=config.get("delimiter", "|")
        )

        def log_and_count(row, label):
            filename = row.get('sourcefilename', 'unknown') if isinstance(row, dict) else 'unknown'
            return (filename, (label, 1))

        merged_counts = (
            (
                write_results.success
                | "Count valid data" >> beam.Map(lambda row: log_and_count(row, 'valid')),
                data.error
                | "Count DQ Rejected" >> beam.Map(lambda row: log_and_count(row, 'error')),
                write_results.database_error
                | "Count DB Rejected" >> beam.Map(lambda row: log_and_count(row, 'database_error'))
            )
            | "flatten stream" >> beam.Flatten()
            | "Group by file name" >> beam.GroupByKey()
            | "Count per file" >> beam.Map(
                lambda kv: (
                    kv[0],
                    {
                        "valid": sum(v for label, v in kv[1] if label == "valid"),
                        "error": sum(v for label, v in kv[1] if label in ("error", "database_error"))
                    }
                )
            )
            | "to dict" >> beam.combiners.ToDict()
        )

        merged_counts | "Insert to Postgres" >> beam.ParDo(
            AuditLogger(db_connector,config, df_args)
        )


    log_file = create_file_name(df_args['market_code'], df_args['source_system_name'], df_args['job_name'])
    upload_log_to_gcs(df_args['log_bucket'], 'application_logs.log', log_file)


if __name__ == "__main__":
    known_args, _ = parse_arguments()
    validate_arguments(known_args)
    market_code = known_args.market_code
    market_code = market_code.upper()
    config = load_config(known_args.config_gcs_path)
    logger.info("Starting pipeline with arguments %s", known_args)
    run_pipeline()
    