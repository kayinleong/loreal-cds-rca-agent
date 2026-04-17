from datetime import datetime, timedelta, timezone
from psycopg2 import  OperationalError, DatabaseError
import apache_beam as beam
from space_stage_target_etl.utils.db_utils import create_connection
from space_stage_target_etl.utils.gcs_utils import read_json_gcs
import json
from google.cloud import storage
from psycopg2 import sql
from space_stage_target_etl.config import CONFIG
from space_stage_target_etl.constants import AUDIT_TABLE_NAME, FORBIDDEN_SP_PREFIXES, ALLOWED_AUTO_START_BUSINESS_TYPES
from space_stage_target_etl.utils.logger import CloudLogger

logger = CloudLogger().get_logger()

class BatchAuditLogDoFn(beam.DoFn):
    def __init__(self, 
        environment, 
        market_code, 
        db_mapping_path, 
        business_type, 
        job_id,
        baton_file_path
        ):
        self.environment = environment
        self.market_code = market_code.lower()
        self.db_mapping_path = db_mapping_path
        self.business_type = business_type.lower()
        self.job_id = job_id
        self.baton_file_path = baton_file_path
        self.baton_file_bucket = self.baton_file_path.replace("gs://", "").split("/")[0]
        self.conn = None

    def setup(self):
        self.conn = create_connection(self.environment, self.market_code, self.db_mapping_path, self.business_type)

    def teardown(self):
        if self.conn:
            try:
                self.conn.close()
                logger.info("Connection closed in teardown.")
            except Exception as e:
                logger.error(f"Error closing connection in teardown: {e}")

    def process(self, element):
        if not self.conn:
            raise RuntimeError("Database connection is not initialized.")
        try:
            cursor = self.conn.cursor()
            if self.business_type=='b2b':
                query = """
                    SELECT sourcename, targetname, sourcerecordcount, loadedrecordcount, errorrecordcount, errorcode, errormessage
                    FROM cds_stg.batch_audit_log
                    WHERE jobid = %s
                """
            else:
                query = """
                    SELECT sourcename, targetname, sourcerecordcount, loadedrecordcount, errorrecordcount, errorcode, errormesage
                    FROM batch_audit_log
                    WHERE jobid = %s
                """
            cursor.execute(query, (self.job_id,))
            rows = cursor.fetchall()
            for row in rows:
                record = {
                    "sourcename": row[0],
                    "targetname": row[1],
                    "sourcerecordcount": row[2],
                    "loadedrecordcount": row[3],
                    "errorrecordcount": row[4],
                    "errorcode": row[5],
                    "errormessage": row[6]
                }
                logger.info(f"BatchAuditLog: {record}")
                yield record
            if not rows:
                logger.warning(f"No batch audit log records found for job_id: {self.job_id}")
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Error querying batch_audit_log: {e}")
            raise RuntimeError("Error querying batch_audit_log.")
        except Exception as e:
            logger.error(f"Unexpected error during batch audit log query: {e}")
            raise RuntimeError("Unexpected error during batch audit log query")
        if self.business_type and self.business_type in ALLOWED_AUTO_START_BUSINESS_TYPES:
            self.dependency_resolver()
        self.reupload_recent_files(self.baton_file_bucket)


    def create_baton_file(self, bucket_name, config, file_path, job_name):
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        try:
            logger.info(f"job_name:{ job_name }")
            source_system_name = job_name.split("-")[2].lower()
        except IndexError:
            logger.error("Job name format is incorrect, unable to extract source system name.")
            return 
        config['next_df_params']['market_code'] = self.market_code
        config['next_df_params']['loadtype'] = config['load_type'].lower()
        try:
            config['next_df_params']['frequency'] = config['frequency'].lower()
        except KeyError:
            logger.error("Frequency key not found in config.")
        config['next_df_params']['dependent_tables'] = config['next_df_params'].get('dependent_tables', [])
        config['next_df_params']['source_system_name'] = source_system_name
        logger.info(f"Creating baton file with config: {config['next_df_params']}")
        blob.upload_from_string(
            json.dumps(
                config['next_df_params'], indent=4
            ),
            content_type='application/json'
        )

    def get_dataflow_config(self):
        dataflow_config = list()
        window = 6
        config = read_json_gcs(CONFIG[self.environment]['DATAFLOW_PARAMS_CONFIG'][self.business_type])
        for key,system_conf in config[self.business_type].items():
            if not isinstance(system_conf, dict) and key == "dependency_lookback_window_hours":
                window = system_conf
                continue
            for _, value in system_conf.items():
                dataflow_config.append(value)
        return dataflow_config, window

    def dependency_handler(self, config, window):
        if not self.conn:
            raise RuntimeError("Database connection is not initialized.")
        if config.get('next_df_params', {}).get('sp_name', '').startswith(FORBIDDEN_SP_PREFIXES):
            return False
        try:
            cursor = self.conn.cursor()
            query = sql.SQL("SELECT FUNC_CHECK_TABLE_DEPENDENCIES(%s,%s,%s)")
            dependent_tables = config.get('next_df_params',{}).get('dependent_tables',[])
            stg_table = config.get('table').split('.')[-1]
            market_code = self.market_code.upper()
            load_type = config.get('load_type','').lower()
            cursor.execute(query, (dependent_tables,window,market_code))
            result = cursor.fetchone()
            stg_check_query = sql.SQL("""
                select count(1) from {}
                where loadstage = %s
                and jobname like %s
                and lower(targetname) = lower(%s)
                and loadendtime >= now() - interval %s
            """).format(
                sql.SQL(AUDIT_TABLE_NAME[self.business_type])
            )
            stg_check_query_params = (
                'SOURCE to STAGE',
                f"{self.business_type}-{self.market_code.lower()}-%-{load_type}-%",
                stg_table,
                f"{window} hours"
            )
            cursor.execute(stg_check_query, stg_check_query_params)
            query_count = cursor.fetchone()

            tgt_check_query = sql.SQL("""
                select count(1) from {}
                where loadstage = %s
                and issuccess = %s
                and loadendtime is not null
                and jobname like %s
                and lower(sourcename) = lower(%s)
                and loadendtime >= now() - interval %s
            """).format(
                sql.SQL(AUDIT_TABLE_NAME[self.business_type])
            )
            tgt_check_query_params = (
                'STAGE to TARGET',
                'true',
                f"{self.business_type}-{self.market_code.lower()}-stg-to-tgt-{load_type}%",
                stg_table,
                f"{window} hours"
            )
            cursor.execute(tgt_check_query, tgt_check_query_params)
            tgt_query_count = cursor.fetchone()

            logger.info(f"Dependency check result: {result[0]}, Query count: {query_count[0]}, config: {config}, tgt_query_count: {tgt_query_count[0]}")
            if result is not None and query_count is not None and tgt_query_count is not None:
                query_count = int(query_count[0])
                tgt_query_count = int(tgt_query_count[0])
                return bool(result[0]) and query_count > 0 and tgt_query_count == 0
            else:
                return False
        except DatabaseError:
            raise RuntimeError("Error executing FUNC_CHECK_TABLE_DEPENDENCIES.")
        except Exception:
            raise RuntimeError("Unexpected error during dependency check.")
        


    def dependency_resolver(self):
        dataflow_config, window = self.get_dataflow_config()
        logger.info(f"Dataflow config: {dataflow_config}, Window: {window}")
        if not dataflow_config:
            raise RuntimeError("No Dataflow configuration found.")

        for config in dataflow_config:
            job_name = self.get_job_name(config['table'])
            logger.info(f"Job name fetched: {job_name}")
            if self.dependency_handler(config, window) and job_name:

                self.create_baton_file(
                    self.baton_file_bucket, config, f"{job_name}.json", job_name
                )
                logger.info(f"Created baton file for job: {job_name} and file_name: {job_name}.json")

    def get_job_name(self, table):
        cursor = self.conn.cursor()
        table_name = table.split('.')[-1]
        sql_query = sql.SQL(
            """
            SELECT jobname
            FROM {}
            WHERE lower(targetname) = lower(%s)
            ORDER BY loadendtime DESC
            LIMIT 1;
            """
        ).format(
            sql.SQL(AUDIT_TABLE_NAME[self.business_type])
        )
        cursor.execute(sql_query, (table_name,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None


    def finish_bundle(self):
        """Close all database connections."""
        self.conn.commit()
        self.conn.close()

    def reupload_recent_files(self, bucket_name):
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=6)
        try:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
            for blob in bucket.list_blobs():
                file = '-'.join(blob.name.split('/')[-1].split('-')[2:])
                baton_file = '-'.join(self.baton_file_path.split('/')[-1].split('-')[2:])
                if blob.time_created >= cutoff and file == baton_file:
                    data = blob.download_as_bytes()
                    blob.upload_from_string(data)
                    logger.info(f"Re-uploaded recent baton file: {blob.name}")
                    break
        except Exception as e:
            logger.error(f"Error re-uploading recent baton files: {e}")
