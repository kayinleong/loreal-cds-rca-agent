
import re
import csv
import yaml
from google.cloud import storage
from .logger import Logger
from datetime import datetime
from zoneinfo import ZoneInfo

logger = Logger(name = "batch log").create_logger()


class ReadFromGCS:
    
    def __init__(self, input_path, config_path, environment):
        if not input_path:
            raise ValueError("Input path must be provided.")
        if not config_path:
            raise ValueError("Config path must be provided.")
        if not environment:
            raise ValueError("Environment must be provided.")
        self.input_path = input_path
        self.file_mapping = {}
        self.config_path = config_path
        self.config = self.get_config()
        try:
            self.delimiter = self.config["file_delimiter"]
        except KeyError:
            try:
                self.delimiter =  self.config["delimiter"]
            except KeyError:
                logger.warning("Delimiter not found in config file. Using default '|' delimiter.")
                self.delimiter = "|"


        self.delimiter = self.delimiter.strip()
        self.environment = environment
        self.blob_name = None


    def find_matching_blob_from_gcs_uri(self):
        """
        Finds the first blob that matches the given GCS URI pattern.
        
        Example: 'gs://my-bucket/path/to/file-.*\\.txt'
        """
        match = re.match(r'gs://([^/]+)/(.*)', self.input_path)
        if not match:
            raise ValueError("Invalid GCS URI pattern")

        bucket_name = match.group(1)
        object_pattern = match.group(2)

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        logger.info(f"bucket:{bucket}")
        # Reduce scope of listing by extracting prefix
        split = object_pattern.rsplit('/', 1)
        prefix = split[0] + '/' if len(split) == 2 else ''
        logger.info(f"prefix:{prefix}")
        regex = re.compile(object_pattern)
        blobs = bucket.list_blobs(prefix=prefix)
        logger.info(f"blobs:{blobs}")
        for blob in blobs:
            if regex.fullmatch(blob.name):
                logger.info("Matched blob: %s",blob.name)
                self.blob_name = blob.name
                return blob,blob.name
        logger.warning("No matching blob found for pattern: %s", object_pattern)
        return None,"No file found"

    def get_field_mapping(self):
        bucket_name = self.config_path.split("gs://")[-1].split("/")[0]
        file_path = self.config_path.replace(f"gs://{bucket_name}/","")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        yaml_content = blob.download_as_text()
        data = yaml.safe_load(yaml_content)
        try:
            field_mapping = data.get("field_mapping")
            return field_mapping
        except KeyError:
            logger.error("Key 'field_mapping' not found in YAML file.")
            raise KeyError("Key 'field_mapping' not found in YAML file.")

    
    def create_file_stream(self):
        blob,blob_name = self.find_matching_blob_from_gcs_uri()
        if blob is None:
            return None,"No file found"
        logger.info("Reading blob: %s",blob.name)
        fstream = blob.open("r",encoding = "utf-8")
        return fstream,blob_name
    
    def create_reader(self,obj):
        reader = csv.reader(obj, delimiter=self.delimiter)
        if not reader:
            logger.error("Reader should not be empty. unable to create the reader iterator.")
            raise ValueError("Reader object is none.")
        return reader
    
    def get_file_header(self,reader):
        if not reader:
            logger.error("Reader is empty.")
            raise ValueError("reader object is not iterable.")
        header = [h.strip() for h in next(reader)]
        return header

    def get_file_data(
        self,
        reader,
        header,
        field_mapping,
        batch_size  = 1000
        ):

        data = list()
        for _ in range(batch_size):
            try:
                row = next(reader)
                stripped_row = [value.strip() for value in row]
                row_data = self.zip_data(header, stripped_row)
                self.validate_field_mapping(row_data, field_mapping)
                row_data["sourcefilename"] = self.blob_name.split("/")[-1]
                row_data["sourcesystemid"] = self.get_source_sys_name()
                utc_now = datetime.now(ZoneInfo("UTC"))
                zulu_time = utc_now.strftime("%Y-%m-%dT%H:%M:%SZ")
                row_data["stagecreatetimestamp"] = zulu_time
                data.append(row_data)
            except StopIteration:
                logger.info("processing the last batch")
                break
        return data

    def validate_field_mapping(self, row_data ,field_mapping):
        for key in list(row_data.keys()):
            if key in field_mapping and field_mapping[key] is not None:
                row_data[field_mapping[key].lower()] = row_data.pop(key)
            elif key not in field_mapping:
                del row_data[key]
            elif key in field_mapping and field_mapping[key] is None:
                del row_data[key]
            
    
    def get_source_sys_name(self):
        """
        Extracts the source system name from the input path.
        """
        if not self.input_path:
            raise ValueError("Input path must be provided.")
        market_code = self.input_path.replace("gs://","").split("/")[1]
        source_sys_name = self.input_path.split("/")[-2]
        return f"{source_sys_name}_{market_code}"


    def get_config(self):
        """
        Reads the configuration file from GCS and returns the field mapping.
        """
        if not self.config_path:
            logger.error("Config path is empty.")
            raise ValueError("Config path must be provided.")
        bucket_name = self.config_path.split("gs://")[-1].split("/")[0]
        file_path = self.config_path.replace(f"gs://{bucket_name}/","")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        yaml_content = blob.download_as_text()
        data = yaml.safe_load(yaml_content)
        return data
    
    def zip_data(self, keys, values):
        """
        Zips the keys and values into a dictionary.
        """
        result = {}
        for k,v in zip(keys, values):
            if k not in result:
                result[k] = v
            elif k in result and result[k] == "":
                result[k] = v
        return result