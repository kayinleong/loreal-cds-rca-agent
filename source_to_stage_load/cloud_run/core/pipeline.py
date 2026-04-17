from core.reader import ReadFromGCS
from core.validator import JsonValidator
from core.transform import Transfomer
from core.logger import Logger
from core.writer import PostgresRecordWriter
from core.file_writer import error_writer, create_empty_file,upload_file_to_gcs_uri
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from psycopg2 import sql

logger = Logger(name = "batch log").create_logger()

class Pipeline:
    def __init__(self, request_json):
        self._parse_request_json(request_json)

    def setup(self):
        self.reader_obj = ReadFromGCS(self.input_path, self.config_path, self.environment)
        self.fstream,self.blob_name = self.reader_obj.create_file_stream()
        if self.fstream is None:
            return "no file stream found"
        self.reader = self.reader_obj.create_reader(self.fstream)
        self.field_mapping = self.reader_obj.get_field_mapping()
        self.header = self.reader_obj.get_file_header(self.reader)
        self.source_sys_name = self.reader_obj.get_source_sys_name()
        self.validator = JsonValidator(self.market_code, self.validation_json)
        self.flattend_schema = self.validator.get_schema()
        self.db_writer = PostgresRecordWriter(self.environment, self.market_code, self.db_mapping_path)
        self.conn = self.db_writer.create_connection()
        file_name = self.blob_name.split("/")[-1]
        self.error_file = "/tmp/" + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z" + "_reject_" + file_name
        create_empty_file(self.error_file)
        # self.log_file = "/tmp/" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + "_" +file_name.split(".")[0] + ".jsonl"
        # create_empty_file(self.log_file)


    def run(self):
        data = self.reader_obj.get_file_data(self.reader, self.header, self.field_mapping, self.batch_size)
        if not data:
            logger.info("Batch has no data.")
            return len(data),0
        transfomer = Transfomer(self.config_path, data)
        transform_data = transfomer.transform()
        error,valid_data = self.validator.validate_data_quality(transform_data, self.flattend_schema)
        if valid_data:
            self.db_writer.write(valid_data, self.table, self.conn)
        else:
            error_writer(self.error_file, error)
            # log_writer(self.log_file, log)
        return len(data),len(valid_data)
    
    def _parse_request_json(self,request_json):
        try:
            self.input_path = request_json['input_path']
            self.config_path = request_json['config_path']
            self.environment = request_json['environment']
            self.market_code = request_json['market_code']
            self.table = request_json['table']
            self.validation_json = request_json.get('validation_json', False)
            self.gcs_uri_log = request_json['gcs_uri_log']
            self.gcs_uri_error = request_json['gcs_uri_error']
            self.db_mapping_path = request_json['db_mapping_path']
            self.batch_size = request_json.get('batch_size', 1000)
            self.domainname = request_json.get("domainname", "CONSUMER")
            self.archive_bucket_name = request_json['archive_bucket_name']
        except KeyError as e:
            logger.error(f"Missing required key: {e}") 
            raise ValueError(f"Missing required key: {e}")
    
    def cleanup(self):
        upload_file_to_gcs_uri(self.error_file,f"{self.gcs_uri_error}/{self.error_file.split('/')[-1]}")
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_file_name = Logger(name = "batch log").get_log_file_name()
        log_file_name_gcs = log_file_name.split(".log")[0] + "_" + self.table + ".log"
        upload_file_to_gcs_uri(log_file_name,f"{self.gcs_uri_log}/{date}/{log_file_name_gcs}")



    def write_audit(self, kwargs):
        """
        Dynamically writes key-value pairs to the batch_audit_log table.
        """
        cursor = self.conn.cursor()

        columns = list(kwargs.keys())
        values = [tuple(kwargs.values())] 

        insert_query = sql.SQL("INSERT INTO batch_audit_log ({}) VALUES %s").format(
            sql.SQL(', ').join(map(sql.Identifier, columns))
        )

        execute_values(cursor, insert_query, values)


        
        


        