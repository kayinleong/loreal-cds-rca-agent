import apache_beam as beam
from datetime import datetime
from datetime import timezone
from google.cloud import storage
from psycopg2 import sql
from psycopg2.extras import execute_values
import json
from space_cds_etl_core.utils.exceptions import DatabaseException
from psycopg2 import DatabaseError
from space_cds_etl_core.utils.constants import (
    GSUTIL_URI_PREFIX, AUDIT_TABLE_NAME
)
from space_cds_etl_core.utils.util_gcs import archive_file
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()


class AuditLogger(beam.DoFn):
    """Generic transformer that applies rules based on a per-source config file."""


    def __init__(self, db_connector,config,df_args):
        self.db_connector = db_connector
        self.df_args = df_args
        self.table = df_args['table']
        self.loadendtime = datetime.now(timezone.utc)
        self.loadtype = "stg"
        self.input_bucket = df_args['input_path'].split(GSUTIL_URI_PREFIX)[-1].split("/")[0]  
        self.prefix = df_args['input_path'].split(GSUTIL_URI_PREFIX)[-1].split("/")[:-1]
        self.prefix = "/".join(self.prefix)
        self.loadedrecordcount = None
        self.log_table = AUDIT_TABLE_NAME[df_args['business_type']]
        self.input_path = df_args['input_path']
        self.isTargetLoad = config.get("isTargetLoad", False)

    def setup(self):
        self.connection = self.db_connector.create_connection()

    def process(self, element):
        cursor = self.connection.cursor()
        logger.info(f"Loaded record count: {self.loadedrecordcount}")
        if not self.isTargetLoad:
            loadstage = "SOURCE to STAGE"
        else:
            loadstage = "SOURCE to TARGET"
            self.loadtype = "Integration Load"

        audit_record = {

            "loadendtime": self.loadendtime,
            "loadtype": self.loadtype,
            "loadstarttime": self.df_args['loadstarttime'],
            "issuccess" : True,
            "jobname": self.df_args['job_name'],
            "sourcename": self.df_args['source_system_name'],
            "targetname": self.table.split('.')[-1].upper(),
            "jobid": self.df_args['job_id'],
            "domainname": self.df_args['domain_name_validation'],
            "loadstage": loadstage
        }
        row_count = 0
        for file_name, counts in element.items():

            valid_count = counts.get("valid", 0)
            invalid_count = counts.get("error", 0)
            audit_record["sourcefilename"] = file_name
            audit_record["loadedrecordcount"] = valid_count
            audit_record["sourcerecordcount"] = valid_count + invalid_count
            audit_record["errorrecordcount"] = invalid_count
            row_count += valid_count
            logger.info(f"Audit record: {audit_record}")
            if audit_record["sourcerecordcount"] >= 0:
                logger.info(f"Inserting audit record into {self.log_table}")
                columns = list(audit_record.keys())
                values = [tuple(audit_record.values())] 
                
                sql_query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
                    sql.SQL(self.log_table),
                    sql.SQL(', ').join(map(sql.Identifier, columns))
                )
                try:
                    execute_values(cursor, sql_query, values)
                except DatabaseException:
                    raise DatabaseException(f"Failed to insert record into {self.log_table}") from None
                archive_file(file_name, self.df_args['archive_bucket_name'],self.df_args)
                if self.df_args.get('input_json_path'):
                    archive_file(self.df_args['input_json_path'], self.df_args['archive_bucket_name'],self.df_args)
        
        self.baton_handler(row_count)
        
    def baton_handler(self,row_count):
        if row_count > 0 and 'sp_name' in self.df_args.get('next_df_params', {}):
            if 'dependent_tables' in self.df_args.get('next_df_params', {}):
                if self.check_dependency() or self.df_args['next_df_params']['dependent_tables'] == []:
                    self.create_baton_file(self.df_args['baton_file_bucket'], f"{self.df_args['job_name']}.json")
            else:
                self.create_baton_file(self.df_args['baton_file_bucket'], f"{self.df_args['job_name']}.json")

    def fetch_file_name(self):
        cursor = self.connection.cursor()
        sql_query = f"""
        SELECT sourcefilename 
        FROM {self.table}
        order by stagecreatetimestamp desc limit 1;
        """
        cursor.execute(sql_query)
        result = cursor.fetchone()
        if result:
            return result[0]
        return "unable to fetch file name"
    


    def create_baton_file(self,bucket_name, file_path):
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        self.df_args['next_df_params']['market_code'] = self.df_args['job_name'].split("-")[1].lower()
        self.df_args['next_df_params']['loadtype'] = self.df_args['job_name'].split("-")[5].lower()
        self.df_args['next_df_params']['frequency'] = self.df_args['job_name'].split("-")[-2].lower()
        self.df_args['next_df_params']['dependent_tables'] = self.df_args['next_df_params'].get('dependent_tables', [])
        self.df_args['next_df_params']['source_system_name'] = self.df_args['source_system_name']
        
        blob.upload_from_string(
            json.dumps(
                self.df_args['next_df_params'], indent=4
            ),
            content_type='application/json'
        )


    def check_dependency(self):
        if not self.connection:
            raise RuntimeError("Database connection is not initialized.")
        try:
            cursor = self.connection.cursor()
            query = sql.SQL("SELECT FUNC_CHECK_TABLE_DEPENDENCIES(%s,%s,%s)")
            dependent_tables = self.df_args['next_df_params']['dependent_tables']
            window = self.df_args['next_df_params']['dependency_lookback_window_hours']
            market_code = self.df_args['market_code'].upper()
            cursor.execute(query, (dependent_tables,window,market_code))
            result = cursor.fetchone()
            if result is not None:
                return bool(result[0])
            else:
                return False
        except DatabaseError:
            raise RuntimeError("Error executing FUNC_CHECK_TABLE_DEPENDENCIES.")
        except Exception:
            raise RuntimeError("Unexpected error during dependency check.")

    def finish_bundle(self):
        """Close all database connections."""
        self.connection.commit()
        self.db_connector.close()
