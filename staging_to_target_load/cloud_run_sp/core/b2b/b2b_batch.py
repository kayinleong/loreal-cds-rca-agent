from core.batch import BatchJobExecutor
from core.secret import get_secret
from core.logger import Logger

logger = Logger(name="b2b batch").create_logger()



class B2BBatchJobExecutor(BatchJobExecutor):
    """Class to execute B2B batch jobs by calling stored procedures in a Postgres database."""
    
    def __init__(self, environment, market_code, db_mapping_path, table):
        super().__init__(environment, market_code, db_mapping_path, table)


    def get_database(self):
        return super().get_database().replace("b2c", "b2b")
    
    def get_credentials(self):
        """
        Retrieves the database credentials for B2B from Google Cloud Secret Manager.
        """
        pswd = get_secret("space_cds-srt-cloudsql_b2b_pwd")
        user = get_secret("space_cds-srt-cloudsql_b2b_user")
        return user, pswd
    
    def get_params(self):
        """
        Retrieves the job_id and job_name for the specified table from the batch_audit_log table.
        """
        cursor = self.conn.cursor()
        sql = """
            SELECT id, jobname FROM cds_stg.batch_audit_log
            WHERE LOWER(targetname) = LOWER(%s)
            ORDER BY loadendtime DESC
            LIMIT 1
        """
        cursor.execute(sql,(self.table,))
        result = cursor.fetchone()
        if result:
            job_id,job_name = result
            return job_id,job_name
        else:
            logger.error(f"No job_id and job_name found for table {self.table}.")
            raise ValueError(f"No job_id and job_name found for table {self.table}.")
    
    

    