import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions,GoogleCloudOptions
import argparse
from space_stage_target_etl.pipeline.stored_procedure_dofn import CallStoredProcedureDoFn
from space_stage_target_etl.pipeline.batch_audit_log_dofn import BatchAuditLogDoFn
from space_stage_target_etl.utils.logger import CloudLogger, upload_log_to_gcs, create_file_name

# Setup Google Cloud Logging
logger = CloudLogger().get_logger()

def parse_args():
    parser = argparse.ArgumentParser(description="Run Dataflow ETL pipeline")
    parser.add_argument('--baton_file_path', required=True, help='Path of Baton file')
    parser.add_argument('--market_code', required=True, help='Market code')
    parser.add_argument('--db_mapping_path', required=True, help='DB mapping path')
    parser.add_argument('--sp_name', required=True, help='Stored procedure name')
    parser.add_argument('--business_type', required=True, choices=['b2c', 'b2b'], help='Business type')
    parser.add_argument('--env', required=True , help='Environment')
    parser.add_argument('--source_system_name', required=True , help='Source system name')
    parser.add_argument('--log_bucket', required=True , help='Log bucket Name')
    # ...add other pipeline-specific arguments as needed...
    known_args, pipeline_args = parser.parse_known_args()
    return known_args, pipeline_args

def run():
    args, pipeline_args = parse_args()
    environment = args.env

    try:
        business_type = args.business_type.lower()
        if business_type not in ["b2c", "b2b"]:
            raise ValueError(f"Unsupported business type: {business_type}")
    except ValueError as e:
        logger.error(f"Argument conversion error: {e}")
        raise

    pipeline_options = PipelineOptions(pipeline_args)
    google_cloud_options=pipeline_options.view_as(GoogleCloudOptions)
    job_name = google_cloud_options.job_name
    job_id = google_cloud_options.template_location.split('/')[5]
    with beam.Pipeline(options=pipeline_options) as p:

        (
            p
            | 'Initialization' >> beam.Create([None])
            | 'Calling stored procedure' >> beam.ParDo(
                CallStoredProcedureDoFn(
                    job_id,job_name,environment, args.market_code, args.db_mapping_path, args.sp_name, args.business_type, args.baton_file_path
                )
            )
            | 'Batch Audit Log' >> beam.ParDo(
                BatchAuditLogDoFn(
                    environment, args.market_code, args.db_mapping_path, args.business_type, job_id , args.baton_file_path
                )
            )
        )
    logger.info("Pipeline completed")
    log_file = create_file_name(args.market_code, args.source_system_name, job_name)
    upload_log_to_gcs(args.log_bucket, 'application_logs.log', log_file)

if __name__ == '__main__':
    known_args, _ = parse_args()
    logger.info("Starting pipeline with arguments %s", known_args)
    run()