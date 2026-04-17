import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
from google.cloud import storage
from core.secret import get_secret
from core.logger import Logger
import yaml
import os
logger = Logger(name = "batch log").create_logger()


class PostgresRecordWriter:
    def __init__(self,environment,market_code,db_mapping_path):
        self.environment = environment
        self.market_code = market_code.lower()
        self.db_mapping_path = db_mapping_path


    def get_database(self):
        bucket_name = self.db_mapping_path.split("gs://")[-1].split("/")[0]
        file_path = self.db_mapping_path.replace(f"gs://{bucket_name}/","")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        yaml_content = blob.download_as_text()
        data = yaml.safe_load(yaml_content)
        try:
            database = data.get("environments").get(self.environment).get("databases").get(self.market_code)
            logger.info(f"database name: {database}")
            return database
        except KeyError:
            logger.error(f"Missing key in YAML file for database configuration: 'environments', 'databases', or '{self.market_code}'.")
            raise KeyError(f"Missing key in YAML file for database configuration: 'environments', 'databases', or '{self.market_code}'.")

        
    def get_database_config(self):
        pswd = get_secret("space_cds-srt-cloudsql_b2c_pwd")
        user = get_secret("space_cds-srt-cloudsql_b2c_user")
        database = self.get_database()
        db_config = {
            "host": os.environ.get("INSTANCE_IP"),
            "database": database,
            "user": user,  
            "password": pswd,
            "port": os.environ.get("INSTANCE_PORT")   
        }
        return db_config
        
    def create_connection(self):
        """
        Creates a connection to the Postgres database.
        """
        db_config = self.get_database_config()

        self.conn = psycopg2.connect(
                host=db_config["host"],
                dbname=db_config["database"],
                user=db_config["user"],
                password=db_config["password"],
                port=db_config.get("port")
        )
        return self.conn

    
    def write(self,data,table_name,conn):
        """
        Writes the data to a Postgres table.
        """
        if not data:
            logger.warning("No data to write.")
            return
        columns = list(data[0].keys())
        values = [[row[col] for col in columns] for row in data]
        sql_query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
            # sql.Identifier(table_name),
            sql.SQL(table_name),
            sql.SQL(', ').join(map(sql.Identifier, columns))
        )

        cursor = conn.cursor()
        try:  
            execute_values(cursor, sql_query, values)
        except Exception as e:
            logger.error(f"Error writing to Postgres table {table_name}: {e}")
            raise Exception(f"Error writing to Postgres table {table_name}: {e}") from e
    
    def close(self):
        """
        Closes the connection to the Postgres database.
        """
        self.conn.commit()
        self.conn.close()
        logger.info("Connection closed.")


