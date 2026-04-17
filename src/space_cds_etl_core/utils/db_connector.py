import google.auth
import psycopg2
from space_cds_etl_core.utils.constants import market_type_constants
from space_cds_etl_core.config import CONFIG
from space_cds_etl_core.utils.secret import get_secret
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()

class DBConnector:
    """Manages connection to PostgreSQL databases."""
    def __init__(self, db_mapping, market_code, market_type, environment):

        _, project_id = google.auth.default()
        if not project_id:
            raise ValueError("GCP project ID must be provided.")
        self.market_code = market_code
        self.db_mapping = db_mapping
        self.project_id = project_id
        self.connection = {}
        self.secret_client = None 
        self.market_type = market_type.lower()
        self.environment = environment.lower()


    def get_database_config(self):
        pswd = get_secret(market_type_constants[self.market_type]['DB_PASSWORD_SECRET_NAME'])
        user = get_secret(market_type_constants[self.market_type]['DB_USERNAME_SECRET_NAME'])
        db_config = {
            "host": CONFIG.get(self.environment).get('SQL_INSTANCE_IP').get(self.market_code.lower()),
            "database": self.get_database(),
            "user": user,  
            "password": pswd,   
        }
        return db_config



    def get_database(self):
        """Get the database name for the given market code."""
        if self.db_mapping:
            return self.db_mapping.get(self.market_code.lower())
        else:
            raise ValueError("Database mapping is not provided.")
    
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
                port=db_config.get("port", 5432)
        )
        return self.conn
    
    def close(self):
        """
        Closes the connection to the Postgres database.
        """
        self.conn.commit()
        self.conn.close()
        logger.info("Connection closed.")
