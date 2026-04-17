from flask import Flask, request
from core.batch import BatchJobExecutor
import logging
import os
from core.logger import Logger
from core.b2b.b2b_batch import B2BBatchJobExecutor

environment = os.environ.get("ENV")
if environment == "pd":
    logger = Logger(name = "batch log",level=logging.INFO).create_logger()
else:
    logger = Logger(name = "batch log",level=logging.DEBUG).create_logger()

app = Flask(__name__)


@app.route("/", methods=["POST"])
def main():
    request_json = request.get_json(silent=True)

    try:
        if request_json is None:
            logging.error("Request JSON is None")
            raise ValueError("Request JSON is None")
        market_code = request_json.get("market_code")
        db_mapping_path = request_json.get("db_mapping_path")
        table = request_json["table"]
        table = table.lower()
        sp_name = request_json.get("sp_name")
        business_type = request_json.get("business_type", "b2c").lower()
        if business_type not in ["b2c", "b2b"]:
            raise ValueError(f"Unsupported business type: {business_type}")
        

    except KeyError as e:
        logger.error(f"ValueError: {e}")
        raise KeyError(f"missing table key in request JSON: {e}")
    
    if business_type == "b2b":
        batchJobExecutor = B2BBatchJobExecutor(environment,market_code,db_mapping_path,table)
        batchJobExecutor.call_stored_procedure(sp_name)
    else:
        batchJobExecutor = BatchJobExecutor(environment,market_code,db_mapping_path,table)
        batchJobExecutor.call_stored_procedure(sp_name)

    return 'pipeline completed'
    
