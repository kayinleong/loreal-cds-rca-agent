import psycopg2
from psycopg2 import sql
from psycopg2 import OperationalError,DatabaseError
from google.cloud import storage
from core.secret import get_secret
from core.logger import Logger
import yaml
import os
logger = Logger(name = "batch log").create_logger()


class BatchJobExecutor:
    """Class to execute batch jobs by calling stored procedures in a Postgres database."""
    
    def __init__(self,environment,country_code,db_mapping_path,table):
        self.environment = environment
        self.country_code = country_code.lower()
        self.db_mapping_path = db_mapping_path
        self.table = table
        # self.create_connection()
        


    def get_database(self):
        """
        Retrieves the database name from a YAML file stored in Google Cloud Storage.
        The YAML file is expected to have a structure like:
        environments:
          <environment>:
            databases:
              <country_code>: <database_name>
        
        where <environment> is the environment (e.g., "pd", "dev") and <country_code> is the market code (e.g., "AU").
        """
        bucket_name = self.db_mapping_path.split("gs://")[-1].split("/")[0]
        file_path = self.db_mapping_path.replace(f"gs://{bucket_name}/","")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        yaml_content = blob.download_as_text()
        data = yaml.safe_load(yaml_content)
        try:
            database = data.get("environments").get(self.environment).get("databases").get(self.country_code)
            logger.info(f"database name: {database}")
            return database
        except KeyError:
            logger.error(f"Missing key in YAML file for database configuration: 'environments', 'databases', or '{self.country_code}'.")
            raise KeyError(f"Missing key in YAML file for database configuration: 'environments', 'databases', or '{self.country_code}'.")

    def get_credentials(self):
        """
        Retrieves the database credentials from Google Cloud Secret Manager.
        """
        pswd = get_secret("space_cds-srt-cloudsql_b2c_pwd")
        user = get_secret("space_cds-srt-cloudsql_b2c_user")
        return user, pswd
        
    def get_database_config(self):
        """
        Retrieves the database configuration including host, database name, user, and password.
        """

        user,pswd = self.get_credentials()

        database = self.get_database()
        db_config = {
            "host": os.environ.get("INSTANCE_IP"),
            "database": database,
            "user": user,  
            "password": pswd,
            "port": os.environ.get("INSTANCE_PORT",)
        }


        return db_config
        

    def create_connection(self):
        """
        Creates a connection to the Postgres database.
        """
        db_config = self.get_database_config()

        try:
            self.conn = psycopg2.connect(
                host=db_config["host"],
                dbname=db_config["database"],
                user=db_config["user"],
                password=db_config["password"],
                port=db_config.get("port", 5432)  # default port fallback
            )
        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            raise RuntimeError("Failed to connect to the PostgreSQL database.")
        except Exception as e:
            logger.error(f"Unexpected error occurred while connecting to the database: {e}")
            raise RuntimeError("Unexpected error during database connection.")





    def get_params(self):
        """
        Retrieves the job_id and job_name for the specified table from the batch_audit_log table.
        """
        cursor = self.conn.cursor()
        sql = """
            SELECT id, jobname FROM batch_audit_log
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
            


    def call_stored_procedure(self, stored_proc_name):
        """
        Calls the specified stored procedure with job_id and job_name.
        """
        self.create_connection()

        job_id, job_name = self.get_params()

        try:
            cursor = self.conn.cursor()

            # query = sql.SQL("CALL {}(%s, %s)").format(sql.Identifier(stored_proc_name))
            query = sql.SQL("CALL {}(%s, %s)").format(sql.SQL(stored_proc_name))

            cursor.execute(query, (str(job_id), job_name))

            if self.conn.notices:
                logger.error("Postgres notices found during stored procedure execution.")
                for notice in self.conn.notices:
                    logger.error(f"Postgres notice: {notice.strip()}")


            self.conn.commit()
            logger.info(f"Stored procedure '{stored_proc_name}' called for table {self.table} with job_id {job_id}.")

        except (DatabaseError,OperationalError) as e:
            logger.error(f"Error executing stored procedure '{stored_proc_name}': {e}")
            raise RuntimeError(f"Error executing stored procedure '{stored_proc_name}' for table {self.table}.")
        except Exception as e:
            logger.error(f"Unexpected error during stored procedure execution: {e}")
            raise RuntimeError(f"Unexpected error during stored procedure execution for table {self.table}.")
        finally:
            self.close()
            logger.info(f"Connection closed after calling stored procedure for table {self.table}.")


    
    def close(self):
        """
        Closes the connection to the Postgres database.
        """
        self.conn.commit()
        self.conn.close()
        logger.info("Connection closed.")


