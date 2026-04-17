import apache_beam as beam
from apache_beam.io import fileio
from space_cds_etl_core.utils.logger import CloudLogger
import codecs
import io
import re
from apache_beam import pvalue
from space_cds_etl_core.utils.encoding_error_records import WriteToGCS
from space_cds_etl_core.utils.util_gcs import archive_file
logger = CloudLogger().get_logger()

class ReadFromGCS(beam.PTransform):
    """
    Apache Beam PTransform for reading and processing files from Google Cloud Storage (GCS).

    This class matches files using glob patterns and regex, detects encoding, reads file contents in chunks,
    validates headers, and logs processing steps. Supports CSV and TXT files with or without headers.
    """
    def __init__(self, df_args, config, environment):
        """
        Initialize the ReadFromGCS transform.

        Args:
            filepath_regex (str): Regex or glob pattern for input files in GCS.
            config (dict): Configuration dictionary (field mapping, delimiter, etc.).
            environment (str): Environment identifier (e.g., 'dev', 'prod').
        Raises:
            ValueError: If filepath_regex or environment is not provided.
        """
        if not df_args['input_path']:
            raise ValueError("Input path must be provided.")
        if not environment:
            raise ValueError("Environment must be provided.")
        self.filepath_regex = df_args['input_path']
        self.file_mapping = {}
        self.environment = environment
        self.config = config
        self.df_args = df_args

    def expand(self, pcoll):
        """
        Expands the transform in a Beam pipeline.
        Matches files, filters by regex, and reads file chunks.

        Args:
            pcoll: Input PCollection.
        Returns:
            PCollection of (line, header, filename) tuples.
        """
        filepath_regex = re.compile(rf"{self.filepath_regex}")        
        file_pattern = self.filepath_regex.split("/")[-1]
        prefix = self.filepath_regex.replace(file_pattern, "")


        if file_pattern.endswith(".csv$") or file_pattern.endswith(".csv"):
            glob_pattern = f"{prefix}*.csv"
        elif file_pattern.endswith(".TXT$") or file_pattern.endswith(".TXT"):
            glob_pattern = f"{prefix}*.TXT"
        else:
            logger.warning(f"Unsupported file type for pattern {self.filepath_regex}. Only .csv and .TXT are supported. Defaulting to .TXT")
        
        try:
            results = (
                    pcoll
                    | "Match Files" >> fileio.MatchFiles(glob_pattern)
                    | "Read Matches" >> fileio.ReadMatches()
                    | "apply regex file path" >> beam.Filter(lambda f: self.filter_file_path(f, filepath_regex))
                    | "Read File Chunks" >> beam.FlatMap(self.read_file_chunks).with_outputs('errors', 'validation_failures', main='main')
            )
            main_pcoll = results.main
            errors_pcoll = results.errors
            validation_failures = results.validation_failures
            
            (
                errors_pcoll
                | "Gather errors" >> beam.combiners.ToList()
                | "write encode error records" >> beam.ParDo(WriteToGCS(self.df_args['encoding_error_file']))
            )
            
            # Check validation failures and fail if any exist
            (
                validation_failures
                | "Collect validation failures" >> beam.combiners.ToList()
                | "Fail on validation errors" >> beam.Map(self._fail_on_validation_errors)
            )   

            combined = (main_pcoll, errors_pcoll) | "Flatten all" >> beam.Flatten()
            return combined
        except Exception as e:
            raise RuntimeError(f"Error processing GCS bucket or pipeline: {e}")

    def _fail_on_validation_errors(self, errors):
        """
        Raises RuntimeError if validation errors exist.
        Args:
            errors (list): List of validation error messages.
        Raises:
            RuntimeError: If errors list is not empty.
        """
        if errors:
            error_msg = f"Delimiter validation failed: {errors}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        return None

    def sniff_delimiter(self, line, filename):
        """
        Sniff the delimiter from a line using csv.Sniffer.
        Args:
            line (str): The line to analyze.
            filename (str): The name of the file being analyzed.
        Returns:
            str or None: Detected delimiter or None if detection fails.
        """
        try:
            possible_delimiters = [',', '\t', ';', '|']
            delimiter_counts = {delim: line.count(delim) for delim in possible_delimiters}
            detected_delimiter = max(delimiter_counts, key=delimiter_counts.get)
            return detected_delimiter
        except Exception as e:
            logger.warning(f"Could not detect delimiter for file {filename}: {e}")
            return None

    def validate_delimiter(self, header_line, second_line, filename):
        """
        Validates that the delimiter in the file matches the configured delimiter.
        Sniffs delimiters from header and data lines for comparison.
        Args:
            header_line (str): The raw header line from the file.
            second_line (str): The second line from the file.
            filename (str): The name of the file being validated.
        Returns:
            str or None: Error message if validation fails, None otherwise.
        """
        configured_delimiter = self.config.get("delimiter")
        if not configured_delimiter:
            logger.warning(f"No delimiter configured. Skipping delimiter validation for file: {filename}")
            return None
        
        # Check if the configured delimiter exists in the header line
        if configured_delimiter not in header_line:
            error_msg = f"Delimiter validation failed for file: {filename}. Configured delimiter '{configured_delimiter}' not found in header."
            logger.error(error_msg)
            archive_file(filename, self.df_args['error_bucket'], self.df_args)
            return error_msg
        
        header_detected_delimiter = self.sniff_delimiter(header_line, filename)
        data_detected_delimiter = self.sniff_delimiter(second_line, filename)

        logger.info(f"Delimiter detection for {filename} - Header: '{header_detected_delimiter}', Data: '{data_detected_delimiter}', Configured: '{configured_delimiter}'")
        
        # Get expected number of delimiters based on field mapping
        expected_field_count = len(self.config.get("field_mapping", {}))
        if expected_field_count > 0 and header_detected_delimiter and data_detected_delimiter:
            if header_detected_delimiter != data_detected_delimiter or header_detected_delimiter != configured_delimiter:
                error_msg = f"Delimiter validation failed for file: {filename}."
                logger.error(error_msg)
                archive_file(filename, self.df_args['error_bucket'], self.df_args)
                return error_msg
        return None

    def get_file_header(self, f):
        """
        Reads and returns the file header, handling no-header and skip-header options.
        Args:
            f: File object opened in text mode.
        Returns:
            str: The header line.
        """
        if self.config.get("no_header", False):
            header = list(self.config.get("field_mapping").keys())
            header = f'{self.config["delimiter"]}'.join(header)
            logger.info(f"Headers: {header}")
            return header
        if self.config.get("skip_header", False):
            _ = f.readline().strip()
            header = list(self.config.get("field_mapping").keys())
            header = f'{self.config["delimiter"]}'.join(header)
            logger.info(f"Headers: {header}")
            return header
        header = f.readline().strip()
        logger.info(f"Headers: {header}")
        return header

    def read_file_chunks(self, file):
        """
        Read large files in chunks, skipping the first line, with encoding detection.
        Args:
            file: File-like object from Beam fileio.
        Yields:
            tuple: (line, header, filename)
        """
        filename = file.metadata.path
        logger.info(f"Reading file: {filename}")
        logger.info(f"File size: {file.metadata.size_in_bytes} bytes")
        # Check if file is empty
        if getattr(file.metadata, 'size_in_bytes', None) == 0:
            logger.warning(f"File {filename} is empty. Skipping.")
            archive_file(filename, self.df_args['archive_bucket_name'], self.df_args)
            return
        # Detect encoding by reading a few bytes in binary mode
        logger.info(f"Detecting encoding for file: {filename}")
        with file.open() as f_bin:
            encoding = self.detect_file_encode(f_bin)
            logger.info(f"encoding set as {encoding}")
        # Now open in text mode with detected encoding
        with file.open() as f_bin:
            f = io.TextIOWrapper(f_bin, encoding=encoding, errors='replace')
            header = self.get_file_header(f)    
            
            pos = f.tell()
            second_line = f.readline()
            stripped_line = second_line.strip()
            if not stripped_line:
                logger.warning(f"File {filename} is empty after header. Skipping.")
                archive_file(filename, self.df_args['archive_bucket_name'], self.df_args)
                return
            
            # Validate delimiter
            validation_error = self.validate_delimiter(header, stripped_line, filename)
            if validation_error:
                yield pvalue.TaggedOutput('validation_failures', validation_error)
                return  # Stop processing this file
            
            f.seek(pos)  # Reset to the position after the header

            for line_num, line in enumerate(f,start=1):
                stripped_line = line.strip()
                if '\ufffd' in stripped_line or '\uFFFD' in stripped_line or '�' in stripped_line:
                    logger.warning(f"Decoding issue - Special char in source file replaced by � in {filename} at line {line_num}.")
                    yield pvalue.TaggedOutput('errors', (stripped_line, header, filename))
                else:
                    yield stripped_line, header, filename

    def validate_header(self, header):
        """
        Validate the header against the expected field mapping.
        Args:
            header (str): The header line from the file.
        Returns:
            bool: True if header is valid, raises ValueError otherwise.
        """
        expected_fields = set(self.config.get("field_mapping").keys())
        for key, value in self.config.get("field_mapping").items():
            if value is None or value == "":
                expected_fields.remove(key)
        try:
            skip_columns = self.config["skip_columns"]
        except KeyError:
            skip_columns = []
        for skip_column in skip_columns:
            if skip_column in expected_fields:
                expected_fields.remove(skip_column)
        actual_fields = set(header.split(self.config.get("delimiter")))
        if expected_fields.issubset(actual_fields):
            logger.info(f"Header validation passed. Expected fields: {expected_fields}, Actual fields: {actual_fields}")
            return True
        logger.error(f"Header validation failed. Expected fields: {expected_fields}, Actual fields: {actual_fields}")
        raise ValueError(f"Header validation failed. Expected fields: {expected_fields}, Actual fields: {actual_fields}")

    def filter_file_path(self, file_obj, filepath_regex):
        """
        Log the file path and filter files by filepath_regex match.
        Args:
            f: File metadata object.
            filepath_regex: Compiled filepath_regex pattern.
        Returns:
            bool: True if file path matches filepath_regex, False otherwise.
        """
        path = file_obj.metadata.path
        matched = bool(filepath_regex.match(path))
        logger.info(f"filepath_regex filter: path={path}, matched={matched}")
        return matched
    
    def detect_file_encode(self, f_bin):
        start = f_bin.peek(4) if hasattr(f_bin, "peek") else f_bin.read(4)
        if hasattr(f_bin, "seek"):
            f_bin.seek(0)
        if start.startswith(codecs.BOM_UTF8):
            encoding = "utf-8-sig"
        elif start.startswith(codecs.BOM_UTF16_LE) or start.startswith(codecs.BOM_UTF16_BE):
            encoding = "utf-16"
        elif start.startswith(codecs.BOM_UTF32_LE) or start.startswith(codecs.BOM_UTF32_BE):
            encoding = "utf-32"
        else:
            encoding = "utf-8"
        return encoding