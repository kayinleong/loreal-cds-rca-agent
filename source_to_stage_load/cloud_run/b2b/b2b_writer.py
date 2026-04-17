from core.writer import PostgresRecordWriter
from core.logger import Logger
from core.secret import get_secret
import os

logger = Logger(name="b2b batch").create_logger()


class PostgresRecordWriterB2B(PostgresRecordWriter):

    def get_database_config(self):
        pswd = get_secret("space_cds-srt-cloudsql_b2b_pwd")
        user = get_secret("space_cds-srt-cloudsql_b2b_user")
        database = self.get_database().replace("b2c", "b2b")
        db_config = {
            "host": os.environ.get("INSTANCE_IP"),
            "database": database,
            "user": user,  
            "password": pswd,
            "port": os.environ.get("INSTANCE_PORT")   
        }
        return db_config
    
    
