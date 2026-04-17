import apache_beam as beam
from datetime import datetime
from zoneinfo import ZoneInfo
import csv
from space_cds_etl_core.utils.constants import TRUE_VALUES
import re
import copy
from space_cds_etl_core.utils.logger import CloudLogger
import uuid
from space_cds_etl_core.utils.util_gcs import archive_file

logger = CloudLogger().get_logger()

class GenericTransformer(beam.DoFn):
    """Generic transformer that applies rules based on a per-source config file."""

    def __init__(self, config, df_args, db_connector):
        
        self.config = config
        self.db_connector = db_connector 
        self.field_mapping = self.config.get("field_mapping")
        self.delimiter = self.config.get("delimiter","|")
        self.df_args = df_args
        self.data = None
        utc_now = datetime.now(ZoneInfo("UTC"))
        utc_current_timestamp = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.stage_create_timestamp = utc_current_timestamp
        self.schema_mapping = self.config.get("schema_mapping", {})
        self.is_target_load = self.config.get("isTargetLoad", False)
        self.current_utc_timestamp = utc_current_timestamp
        self.iso_country_map = {}
        self.operation = "create" if str(self.config.get("operation", "update")).lower() == "create" else "update"
        logger.info("Operation set to: %s", self.operation)
        logger.info("Initializing GenericTransformer")
            

    def process(self, element):
        """Applies all transformations to the input data."""
        self.data = {}
        transformations = self.config.get("transformations", {})
        data,header,filename = element
        self.line_to_dict(data,header,filename)
        self.validate_field_mapping(self.data, self.field_mapping)
        self.null_missing_data()
        self.apply_type_conversions(transformations.get("type_conversion", {}))
        self.format_dates(transformations.get("format", {}))
        self.convert_timezones(transformations.get("timezone_conversion", {}))
        self.apply_case_conversion(transformations.get("case_conversion", {}))
        self.remove_spaces(transformations.get("remove_spaces_columns", []))
        self.apply_uuid_conversion(transformations.get("uuid_conversion", {}))
        self.apply_value_mapping(transformations.get("value_mapping", {}))
        if not self.is_target_load:
            self.data["sourcefilename"] = filename
            self.data["stagecreatetimestamp"] = self.stage_create_timestamp
            self.data["sourcesystemid"] = f'{self.df_args.get("source_system_name")}_{self.df_args.get("market_code")}'
            self.data["operation"] = self.operation
            if not self.config.get("is_country_code_available",True):
                self.data["market"] = self.df_args.get("market_code").upper()
        else :
            self.data["sourcefilename"] = filename
            self.data["createdsourcesystemid"] = f'{self.df_args.get("source_system_name")}_{self.df_args.get("market_code")}'
            self.data["lastupdatedsourcesystemid"] =  f'{self.df_args.get("source_system_name")}_{self.df_args.get("market_code")}'
            self.data["syscreateddatetime"] = self.current_utc_timestamp
            self.data["sysupdatedatetime"] = self.current_utc_timestamp
            isocountry_val =self.data["isocountry"]
            self.data["country_iso_3166_1"] = self.iso_country_map.get(isocountry_val)
        mapped_data = self.map_schema()
        self.validate_market()
        yield self.data, mapped_data

    def null_missing_data(self):
        for key,value in self.data.items():
            if value == "":
                self.data[key] = None

    
    def line_to_dict(self, element,headers,filename):
        """Map fields from the input element to the database fields."""
        row = csv.reader([element],delimiter=self.delimiter)
        row = next(row)
        row = [r.strip() for r in row]
        headers = csv.reader([headers], delimiter=self.delimiter)
        headers = next(headers)
        headers = [h.strip() for h in headers]
        self.data =  self.zip_data(headers, row)





    def apply_type_conversions(self, type_conversion):
        """Applies type conversions to fields based on the configuration."""
        for field, field_type in type_conversion.items():
            if field in self.data and self.data[field] != "" and self.data[field] is not None:
                try:
                    if field_type == "int":
                        self.data[field] = int(self.data[field])
                    elif field_type == "float":
                        self.data[field] = float(self.data[field])
                    elif field_type in ("boolean","bool","Boolean"):
                        self.data[field] = self.data[field].lower() in TRUE_VALUES

                except (ValueError, TypeError):
                    logger.warning(f"Failed to convert field '{field}' to {field_type}")


    def format_dates(self, date_formats):
        """Formats date fields based on the provided formats."""
        for field, date_format in date_formats.items():
            if field in self.data and self.data[field] != "" and self.data[field] is not None:
                try:
                    self.data[field] = self.data[field].strip().split(' ')[0]
                    self.data[field] = datetime.strptime(self.data[field],date_format).date().strftime("%Y-%m-%d")

                except Exception as e:
                    logger.warning(f"Failed to convert date for field '{field}': {str(e)}")


    def convert_timezones(self, timezone_conversion):
        """
        Converts datetime fields from a source timezone to UTC in Zulu format.

        Args:
            data (dict): The input data record.
            timezone_conversion (dict): Configuration for timezone conversion.
                Example:
                {
                    "field_name": {
                        "source_timezone": "Asia/Singapore"
                    }
                }
        """
        for field, tz_config in timezone_conversion.items():
            if field in self.data and self.data[field] != "" and self.data[field] is not None:
                try:
                    source_tz = ZoneInfo(tz_config["source_timezone"])
                    utc_tz = ZoneInfo("UTC")
                    local_time = datetime.strptime(self.data[field], "%Y-%m-%d %H:%M:%S")
                    local_time = local_time.replace(tzinfo=source_tz)  # Localize to source timezone
                    utc_time = local_time.astimezone(utc_tz)  # Convert to UTC
                    self.data[field] = utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")  # Format to Zulu
                except Exception as e:
                    logger.warning(f"Failed to convert timezone for field '{field}': {str(e)}")

    def apply_case_conversion(self, case_conversion):
        """Applies case conversion to fields based on the configuration."""
        for field, case_type in case_conversion.items():
            if field in self.data and self.data[field] != "" and self.data[field] is not None:
                try:
                    if case_type == "upper":
                        self.data[field] = str(self.data[field]).upper()
                    elif case_type == "lower":
                        self.data[field] = str(self.data[field]).lower()
                    elif case_type == "title":
                        self.data[field] = str(self.data[field]).title()
                    else:
                        logger.warning(f"Failed to convert case for field '{field}': Unknown case type '{case_type}'")
                except Exception as e:
                    logger.warning(f"Failed to convert case for field '{field}': {str(e)}")

    def validate_field_mapping(self, row_data ,field_mapping):
        for key in list(row_data.keys()):
            if key in field_mapping and field_mapping[key] is not None:
                row_data[field_mapping[key].lower()] = row_data.pop(key)
            elif key not in field_mapping:
                del row_data[key]
            elif key in field_mapping and field_mapping[key] is None:
                del row_data[key]


    def map_schema(self):
        """
        Maps the data fields to the schema fields based on the provided schema mapping.
        """
        mapped_data = copy.deepcopy(self.data)
        for stg_field, tgt_field in self.schema_mapping.items():
            if stg_field in self.data:
                mapped_data[tgt_field] = mapped_data.pop(stg_field)
        return mapped_data
    
    def zip_data(self, keys, values):
        """
        Zips the keys and values into a dictionary if key does not already exist 
        or if the value for the key is empty string it is replaced with the new value.
        If a key already exists in the result dictionary, it will not be overwritten.
        """
        result = {}
        skip_columns = list()
        if self.config.get("skip_columns", None):
            skip_columns = self.config.get("skip_columns")
            skip_columns = [s.strip() for s in skip_columns]

        for k,v in zip(keys, values):
            if k.strip() not in skip_columns and not result.get(k):
                    result[k] = v
        return result
    
    def remove_spaces(self, columns):
        """
        Removes leading and trailing spaces from all string fields in the data.
        """
        for field in columns:
            if field in self.data and isinstance(self.data[field], str):
                self.data[field] =  re.sub(r"\s+", "", self.data[field])

    def apply_uuid_conversion(self, uuid_conversion):
        """Validates fields as UUIDs for use in Postgres UUID columns, does not change value."""
        for field, enabled in uuid_conversion.items():
            if enabled and field in self.data and self.data[field] not in (None, ""):
                try:
                    _ = uuid.UUID(str(self.data[field]))
                except Exception as e:
                    logger.warning(f"Field '{field}' value '{self.data[field]}' is not a valid UUID: {str(e)}")

    def apply_value_mapping(self, value_mappings):
        """
        Applies generic value mapping transformations to fields.
        
        Args:
            value_mappings (dict): Dictionary where keys are field names and values are 
                                   dictionaries mapping source values to target values.
        """
        if not value_mappings:
            return
        
        for field, mapping_dict in value_mappings.items():
            if field in self.data and self.data[field] not in (None, ""):
                original_value = self.data[field]
                # Look up the value in the mapping, keep original if not found
                mapped_value = mapping_dict.get(original_value, self.data[field])
                self.data[field] = mapped_value

    def setup(self):
        if self.is_target_load:
            # Fetch iso_country_iso_3166_1_map table and build mapping
            logger.info("Setting up database connection...")
            self.connection = self.db_connector.create_connection()
            cursor = self.connection.cursor()
            cursor.execute("SELECT isocountry, country_iso_3166_1 FROM iso_country_iso_3166_1_map")
            rows = cursor.fetchall()
            self.iso_country_map = {row[0].strip(): row[1] for row in rows}
            cursor.close()
        else:
            logger.info("Non-target load detected; skipping ISO country mapping fetch.")

    def validate_market(self):
        market_code = self.df_args.get("market_code","").strip()
        config_market = self.config.get("market_code_column","").strip()
        if not self.data.get(config_market):
            return
        if market_code.lower() != self.data[config_market].lower():
            logger.error(f"Market code mismatch: DF args market code '{market_code}' does not match data market code '{self.data[config_market]}' (column '{config_market}')")
            logger.error(f"Mismatch data in file:{self.data.get('sourcefilename')}")
            archive_file(self.data.get('sourcefilename'), self.df_args['error_bucket'], self.df_args)
            raise ValueError("Market code mismatch between DF args and config.")