from psycopg2 import sql, OperationalError, DatabaseError
from space_stage_target_etl.utils.db_utils import create_connection
import apache_beam as beam
from space_stage_target_etl.utils.logger import CloudLogger
import hashlib

# Setup Google Cloud Logging
logger = CloudLogger().get_logger()




class CallStoredProcedureDoFn(beam.DoFn):
    def __init__(self,job_id,job_name, environment, market_code, db_mapping_path, sp_name,business_type,baton_file_path):
        self.environment = environment
        self.market_code = market_code.lower()
        self.db_mapping_path = db_mapping_path
        self.baton_file_path = baton_file_path
        self.sp_name = sp_name
        self.business_type = business_type
        self.job_id = job_id
        self.job_name = job_name
        
        self.conn = None

    def setup(self):

        self.conn = create_connection(self.environment, self.market_code, self.db_mapping_path,self.business_type)

    def finish_bundle(self):
        if self.conn:
            try:
                self.conn.commit()
                self.conn.close()
                logger.info("Connection closed in finish_bundle.")
            except Exception as e:
                logger.error(f"Error closing connection in finish_bundle: {e}")

    def _get_advisory_lock_key(self):
        """
        Returns a consistent integer key for advisory locking based on the stored procedure name.
        """
        # Use sha256 hash and take first 8 bytes as int for advisory lock key
        hash_bytes = hashlib.sha256(self.sp_name.encode('utf-8')).digest()[:8]
        key = int.from_bytes(hash_bytes, byteorder='big', signed=False)
        # Ensure key fits in signed 64-bit integer range
        if key > 0x7FFFFFFFFFFFFFFF:
            key = key - (1 << 64)
        return key

    def _procedure_exists_in_public(self, cursor) -> bool:
        # Check if the procedure exists specifically in the public schema with the expected arity.
        cursor.execute(
            """
            SELECT 1
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.prokind = 'p'
              AND lower(p.proname) = lower(%s)
            LIMIT 1
            """,
            (self.sp_name,),  # fixed: pass a 1-element tuple
        )
        return cursor.fetchone() is not None

    def call_stored_procedure(self):
        """
        Calls the specified stored procedure with job_id and job_name.
        Ensures only one instance runs at a time using advisory lock.
        """
        if not self.conn:
            raise RuntimeError("Database connection is not initialized.")
        lock_key = self._get_advisory_lock_key()
        cursor = None
        lock_acquired = False
        try:
            cursor = self.conn.cursor()
            # fixed: actually call the existence check
            if not self._procedure_exists_in_public(cursor):
                logger.error(f"Stored procedure '{self.sp_name}' not found in public schema.")
                raise RuntimeError(f"Stored procedure '{self.sp_name}' not found in public schema.")

            # Acquire advisory lock (blocks until available)
            cursor.execute("SELECT pg_advisory_lock(%s);", (lock_key,))
            lock_acquired = True
            logger.info(f"Acquired advisory lock for key {lock_key} (SP: {self.sp_name})")
            
            # STRY0709777 story to align ANZ with 3 parameters
            # currently ANZ for b2c we are passing 2 parameters and for rest stored procedures 3 parameters
            
            if self.market_code.lower() in ('au', 'nz') and self.business_type.lower() == 'b2c':
                logger.info(f"Calling stored procedure '{self.sp_name}' with job_id {self.job_id} and job_name {self.job_name}.")
                query = sql.SQL("CALL {}(%s, %s)").format(sql.SQL(self.sp_name))
                cursor.execute(query, (self.job_id, self.job_name))
            else:
                logger.info(f"Calling stored procedure '{self.sp_name}' with job_id {self.job_id} and job_name {self.job_name}.")
                query = sql.SQL("CALL {}(%s, %s, %s)").format(sql.SQL(self.sp_name))
                cursor.execute(query, (self.job_id, self.job_name, self.market_code.upper()))

            # Check for any notices from the database
            if self.conn.notices:
                has_sqlstate_error = any("SQLSTATE" in str(notice) for notice in self.conn.notices)
                
                if has_sqlstate_error:
                    logger.error("Postgres notices found during stored procedure execution.")
                    for notice in self.conn.notices:
                        logger.error(f"Postgres notice: {notice.strip()}")
                    raise RuntimeError("Unexpected notices found during stored procedure execution.")
                else:
                    # Log non-error notices as warnings
                    for notice in self.conn.notices:
                        logger.warning(f"Postgres notice: {notice.strip()}")

            self.conn.commit()
            logger.info(
                f"Stored procedure '{self.sp_name}' called with job_id {self.job_id}."
            )
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Error executing stored procedure '{self.sp_name}': {e}")
            raise RuntimeError(f"Error executing stored procedure '{self.sp_name}'.")
        except Exception as e:
            logger.error(f"Unexpected error during stored procedure execution: {e}")
            raise RuntimeError("Unexpected error during stored procedure execution.")
        finally:
            # Release advisory lock if acquired
            if lock_acquired:
                try:
                    # If cursor is closed, create a new one to unlock
                    if cursor is None or cursor.closed:
                        cursor = self.conn.cursor()
                    cursor.execute("SELECT pg_advisory_unlock(%s);", (lock_key,))
                    logger.info(f"Released advisory lock for key {lock_key} (SP: {self.sp_name})")
                except Exception as e:
                    logger.error(f"Error releasing advisory lock for key {lock_key}: {e}")
            self.conn.commit()

    def process(self, element):
        self.call_stored_procedure()
        yield "Stored procedure executed"