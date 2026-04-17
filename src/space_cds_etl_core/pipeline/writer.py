import apache_beam as beam
from psycopg2.extras import execute_values
from psycopg2 import sql
import psycopg2
from datetime import datetime
from zoneinfo import ZoneInfo
from space_cds_etl_core.config import DEFAULT_BATCH_SIZE
from apache_beam.io import filesystems
from space_cds_etl_core.utils.logger import CloudLogger
from space_cds_etl_core.utils.constants import GENERIC_MOBILE_COUNTRY_CODE
from apache_beam import pvalue
logger = CloudLogger().get_logger()


class GenericWriter(beam.DoFn):
    """Generic writer that writes to a Cloud SQL PostgreSQL database dynamically."""

    def __init__(self, config, df_args, db_connector):
        self.config = config
        self.db_connector = db_connector 
        self.field_mapping = self.config.get("field_mapping", {})
        self.operation = self.config.get("operation", "insert").lower()  # Default to "insert"
        self.delimiter = self.config.get("delimiter","|")
        self.connection = None
        self.batch = []
        self.batch_size = self.config.get("batch_size", DEFAULT_BATCH_SIZE)
        self.is_target_load = self.config.get("isTargetLoad", False)
        self.df_args = df_args
        self.is_success_records = True
        self.files_with_errors = []
        self.invalid_record_count = 0
        self.error_row = []

    def _run_preload_scripts(self, cursor):
        preload_scripts = self.config.get("run_preload_script")
        market_code = self.df_args.get('market_code').upper()
        
        if preload_scripts:
            if isinstance(preload_scripts, list):
                for script in preload_scripts:
                    try:
                        script = script.replace('{{market_code}}', f"'{market_code}'")
                        logger.info(f"Running preload script: {script}")
                        cursor.execute(script)
                        self.connection.commit()
                    except Exception as e:
                        logger.error(f"Error running preload script '{script}': {e}")
                        self.connection.rollback()
                        raise
            elif isinstance(preload_scripts, str):
                try:
                    preload_scripts = preload_scripts.replace('{{market_code}}', f"'{market_code}'")
                    logger.info(f"Running preload script: {preload_scripts}")
                    cursor.execute(preload_scripts)
                    self.connection.commit()
                except Exception as e:
                    logger.error(f"Error running preload script '{preload_scripts}': {e}")
                    self.connection.rollback()
                    raise

    def normalize_mobile_number(self,element):
        """Sanitizes mobile number by removing non-numeric characters."""
        if not hasattr(self, 'mobile_column') or not hasattr(self, 'mobile_code'):
            return element
        
        if self.mobile_column is None or self.mobile_code is None:
            return element
        

            
        if self.mobile_column in element and element[self.mobile_column] not in (None, ""):
            if element[self.mobile_column].startswith(GENERIC_MOBILE_COUNTRY_CODE) or element[self.mobile_column].startswith(self.mobile_code):
                return element
            elif element[self.mobile_column].startswith(GENERIC_MOBILE_COUNTRY_CODE.lstrip('+')) or element[self.mobile_column].startswith(self.mobile_code.lstrip('+')):
                element[self.mobile_column] = '+' + element[self.mobile_column]
                return element
            elif element[self.mobile_column].startswith('0'):
                element[self.mobile_column] = self.mobile_code + element[self.mobile_column][1:]
            elif not element[self.mobile_column].startswith(('+')):
                element[self.mobile_column] = self.mobile_code + element[self.mobile_column]
        return element


    def get_mobile_config(self, mobile_config):
        if not mobile_config:
            logger.info("No mobile number mapping configuration found.")
            return None, None
        mobile_column = list(mobile_config.keys())[0]
        market_code = self.df_args.get("market_code").upper()
        mobile_code = str(mobile_config.get(mobile_column).get(market_code))
        if not mobile_code.startswith('+'):
            mobile_code = '+' + mobile_code
        return mobile_column, mobile_code

    def setup(self):
        logger.info("Setting up database connection...")
        self.connection = self.db_connector.create_connection()
        cursor = self.connection.cursor()
        self.mobile_column, self.mobile_code = self.get_mobile_config(self.config.get("transformations", {}).get("mobile_code_mapping", {}))

        # Run preload scripts if available 
        self._run_preload_scripts(cursor)

        if self.config.get("truncate",True):
            table = self.df_args['table']
            partition_table = f"{table}_processed"
            cursor.execute("SELECT to_regclass(%s)", (partition_table,))
            exists = cursor.fetchone()[0] is not None
            truncate_target = partition_table if exists else table
            logger.info(f"Truncating table: {truncate_target} (exists={exists})")
            query = f"TRUNCATE TABLE {truncate_target}"
            try:
                cursor.execute(query)
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise


    def process(self, batch):
        """Process a batch of elements (list). BatchElements transform provides the batch."""
        # Normalize mobile numbers for all elements in batch
        normalized_batch = [self.normalize_mobile_number(element) for element in batch]

        # Flush this batch and yield all outputs
        for output in self.flush_batch(normalized_batch):
            yield output


    
    def flush_batch(self, batch):
        """Flush the batch of rows to the database."""
        if not batch:
            return
        cursor = self.connection.cursor()
        table = self.df_args.get('table')
        if not table:
            raise ValueError("Table name is not specified in the configuration.")

        # Convert column names to a comma-separated string

        columns = list(batch[0].keys())
        file_name_idx = columns.index('sourcefilename') if 'sourcefilename' in columns else -1
        # Simplified removal logic
        columns = [c for c in columns if not (self.is_target_load and c == 'sourcefilename')]
        logger.info(f"Flushing batch to table {table} with columns: {columns}")
        values = []
        for row in batch:
            try:
                values.append([row[col] for col in columns])
            except KeyError as e:
                logger.error(f"problem with processing for {row} in {row['sourcefilename']}: {e}")
                self.is_success_records = False
                self.files_with_errors.append(row['sourcefilename'])
                self.record_error_row(list(row.values()) + [str(e)])
            except Exception as e:
                logger.error(f"problem with processing for {row} in {row['sourcefilename']}: {e}")
                self.is_success_records = False
                self.files_with_errors.append(row['sourcefilename'])
                self.record_error_row(list(row.values()) + [str(e)])
        sql_query = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
            sql.SQL(table),
            sql.SQL(', ').join(map(sql.Identifier, columns))
        )

        row_sql_query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.SQL(table),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() for _ in columns)  
        )

        try:
            execute_values(cursor, sql_query, values)
            self.connection.commit()
            # Yield success for each row in the batch
            success_count = 0
            for row in batch:
                yield {'sourcefilename': row.get('sourcefilename', 'unknown')}
                success_count += 1
            logger.info(f"Successfully inserted {success_count} rows to {table}")
        except psycopg2.Error as e:
            logger.error(f"Failed to insert batch into {table}: {e}")
            self.connection.rollback()
            for output in self.insert_rows(values, cursor, row_sql_query, file_name_idx, batch):
                yield output

    def record_error_row(self, row):
        """Format a row as a delimited string for error logging."""
        error_row = self.delimiter.join([f'"{str(col) if col is not None else ""}"' for col in row]).replace('\n', '').replace('\r', '')
        self.error_row.append(error_row)

    def insert_rows(self, values, cursor, row_sql_query, file_name_idx, batch):
        """
        Insert rows individually when batch insert fails.
        
        This method is called as a fallback when the batch insert using execute_values fails.
        It attempts to insert each row individually to identify and handle problematic rows
        while allowing successful rows to be processed.
        
        Args:
            values (list): List of row tuples to insert
            cursor: Database cursor for executing SQL commands
            row_sql_query: Prepared SQL query for individual row insertion
            file_name_idx (int): Index of the source filename column in the row data
            batch (list): Original batch of row dictionaries
        """
        for i, row in enumerate(values):
            try:
                cursor.execute(row_sql_query, tuple(row))
                self.connection.commit()
                # Yield success for this row
                yield {'sourcefilename': batch[i].get('sourcefilename', 'unknown')}
            except psycopg2.Error as row_err:
                self.connection.rollback()
                self.invalid_record_count += 1
                logger.error(f"Failed to insert row from {batch[i].get('sourcefilename')}: {row_err}")
                self.is_success_records = False
                row = list(row)
                row.append(str(row_err))
                self.record_error_row(row)
                self.files_with_errors.append(batch[i].get('sourcefilename'))
                yield pvalue.TaggedOutput('database_error', {'sourcefilename': batch[i].get('sourcefilename')})  

        

    def finish_bundle(self):
        """Close all database connections."""
        self.files_with_errors = set(self.files_with_errors)
        if not self.is_success_records:
            logger.info(f"Files with errors: {self.files_with_errors}")
            logger.error(f'Total invalid rows - {self.invalid_record_count}')
            today_date = datetime.now(ZoneInfo("UTC")).date()
            destination_blob = (
                f"gs://{self.df_args['error_bucket']}/"
                f"{self.df_args['market_code']}/"
                f"{self.df_args['source_system_name']}/"
                f"inbound/{today_date}/"
                f"{self.df_args['job_name']}_"
                f"{datetime.now(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]}Z.csv"
            )
            error_rows = "\n".join(self.error_row)
            with filesystems.FileSystems.create(destination_blob) as f:
                f.write(error_rows.encode('utf-8'))
        self.connection.commit()
        self.db_connector.close()