
import yaml
from google.cloud import storage
from datetime import datetime
from core.logger import Logger
from zoneinfo import ZoneInfo
logger = Logger(name = "batch log").create_logger()

class Transfomer:
    def __init__(self,config_path,data):
        self.config_path = config_path
        self.config = self.read_yaml_from_gcs()
        self.data = data



    def read_yaml_from_gcs(self):
        bucket_name = self.config_path.split("gs://")[-1].split("/")[0]
        file_path = self.config_path.replace(f"gs://{bucket_name}/","")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        yaml_content = blob.download_as_text()
        data = yaml.safe_load(yaml_content)
        return data.get("transformations",{})

    def apply_type_conversions(self, type_conversion,data):
        """Applies type conversions to fields based on the configuration."""
        for field, field_type in type_conversion.items():
            if field in data and data[field] != "" and data[field] is not None:
                try:
                    if field_type == "int":
                        data[field] = int(data[field])
                    elif field_type == "float":
                        data[field] = float(data[field])
                except ValueError:
                    logger.warning(f"Failed to convert field '{field}' to {field_type}")

    def format_dates(self, date_formats,data):
        """Formats date fields based on the provided formats."""
        for field, date_format in date_formats.items():
            if field in data and data[field] != "" and data[field] is not None:
                try:
                    data[field] = data[field].strip().split(' ')[0]
                    data[field] = datetime.strptime(data[field],date_format).date().strftime("%Y-%m-%d")

                except Exception as e:
                    logger.warning(f"Failed to convert date for field '{field}': {str(e)}")


    def convert_timezones(self, timezone_conversion,data):
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
            if field in data and data[field] != "" and data[field] is not None:
                try:
                    source_tz = ZoneInfo(tz_config["source_timezone"])
                    utc_tz = ZoneInfo("UTC")
                    local_time = datetime.strptime(data[field], "%Y-%m-%d %H:%M:%S")
                    local_time = local_time.replace(tzinfo=source_tz)  # Localize to source timezone
                    utc_time = local_time.astimezone(utc_tz)  # Convert to UTC
                    data[field] = utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")  # Format to Zulu
                except Exception as e:
                    logger.warning(f"Failed to convert timezone for field '{field}': {str(e)}")

    def transform(self):
        for record in self.data:
            self.nullify_fields(record)
            if self.config.get("type_conversion",False):
                self.apply_type_conversions(self.config["type_conversion"],record)
            if self.config.get("date_format",False):
                self.format_dates(self.config["date_format"],record)
            if self.config.get("timezone_conversion",False):
                self.convert_timezones(self.config["timezone_conversion"],record)
        return self.data
    
    def nullify_fields(self,data):
        for key,value in data.items():
            if value == "":
                data[key] = None
        return data

        
