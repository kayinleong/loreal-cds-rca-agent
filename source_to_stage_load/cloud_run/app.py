from flask import Flask, request
from datetime import datetime, timezone
from core.pipeline import Pipeline
from b2b.b2b_pipeline import B2BPipeline
from core.logger import Logger
from core.archive import archive_file
logger = Logger(name="batch log").create_logger()



app = Flask(__name__)

@app.route("/", methods=["POST"])
def main():

    request_json = request.get_json()
    business_type = request_json.get("business_type", "b2c").lower()
    if business_type == "b2b":
        pipeline = B2BPipeline(request_json)
    elif business_type == "b2c":
        pipeline = Pipeline(request_json)
    else:
        raise ValueError(f"Unsupported business type: {business_type}")
    insert_count = 0
    total_rows = 0
    setup = pipeline.setup()
    if setup:
        return "no file found"

    logger.info(f"batch started to load {pipeline.table}")
    start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    logger.info(f"batch started to load {pipeline.table} at {start_time} UTC")
    start = datetime.now()
    while True:
        data_count,valid_data_count = pipeline.run()
        insert_count += valid_data_count
        total_rows += data_count
        if data_count < pipeline.batch_size:
            input_bucket = pipeline.input_path.split('gs://')[-1].split('/')[0]
            # pipeline.db_writer.close()
            logger.info(f"batch is finished to load {pipeline.table} from gs://{input_bucket}/{pipeline.blob_name}")
            logger.info(f"rows insert in table {pipeline.table} from gs://{input_bucket}/{pipeline.blob_name}: {insert_count}")
            logger.info(f"total rows in file gs://{input_bucket}/{pipeline.blob_name}: {total_rows}")
            break
    input_bucket = pipeline.input_path.split('gs://')[-1].split('/')[0]
    audit_col = {
        "loadstage": "FILE to STAGE",
        "sourcename": pipeline.source_sys_name,
        "targetname": f"{pipeline.table}",
        "sourcefilename": f"{pipeline.blob_name}".split("/")[-1],
        "loadtype": "MIGRATION",
        "sourcerecordcount": total_rows,
        "loadedrecordcount": insert_count,
        "errorrecordcount": total_rows - insert_count,
        "loadstarttime": start_time,
        "loadendtime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "issuccess" : True,
        "jobname": f"B2C_{pipeline.source_sys_name}_to_CDS_MIGR_{pipeline.table}",
        "domainname": pipeline.domainname,
    }
    pipeline.cleanup()
    pipeline.write_audit(audit_col)
    pipeline.db_writer.close()
    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    end = datetime.now()
    diff = end - start
    diff_minutes = diff.total_seconds() / 60
    logger.info(f"batch run completed for {pipeline.table} at {end_time} UTC, took {diff_minutes:.2f} minutes")
    archive_file(f'gs://{input_bucket}/{pipeline.blob_name}', pipeline.archive_bucket_name)
    logger.info(f"archived file gs://{input_bucket}/{pipeline.blob_name} to {pipeline.archive_bucket_name}")
    return "batch run completed"

