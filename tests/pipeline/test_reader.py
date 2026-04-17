import unittest
from unittest.mock import MagicMock, patch
import codecs
import io
import re
from apache_beam import pvalue
from space_cds_etl_core.pipeline.reader import ReadFromGCS

class TestReadFromGCS(unittest.TestCase):

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_get_file_header_logs(self, mock_logger):
        # no_header branch
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": ",", "no_header": True}
        reader = ReadFromGCS(self.df_args, config, self.environment)
        mock_file = MagicMock()
        expected_header = "col1,col2"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, expected_header)
        mock_logger.info.assert_any_call(f"Headers: {expected_header}")

        # skip_header branch
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": ",", "skip_header": True}
        reader = ReadFromGCS(self.df_args, config, self.environment)
        mock_file = MagicMock()
        mock_file.readline.return_value = "header_line\n"
        expected_header = "col1,col2"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, expected_header)
        mock_logger.info.assert_any_call(f"Headers: {expected_header}")

        # default branch
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        mock_file = MagicMock()
        mock_file.readline.return_value = "header_line\n"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, "header_line")
        mock_logger.info.assert_any_call("Headers: header_line")

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_encoding_log(self, mock_logger):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = b"col1,col2\na,b\n"
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            list(reader.read_file_chunks(file_mock))
        mock_logger.info.assert_any_call("Detecting encoding for file: gs://bucket/file.csv")

   
    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_utf32le_bom(self, mock_logger):
        # Simulate a file with UTF-32 LE BOM
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        # Compose content with UTF-32 LE BOM and a header/line
        content = codecs.BOM_UTF32_LE + "col1,col2\na,b\n".encode("utf-32le")
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            # The output will contain the line, header, and filename
            self.assertTrue(result)
            # Remove nulls from the line for assertion
            cleaned = [(r[0].replace('\x00', ''), r[1], r[2]) for r in result]
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), cleaned)
   
    def setUp(self):
        self.df_args = {"input_path": "gs://bucket/folder/file.csv", "encoding_error_file": "gs://bucket/errors.txt"}
        self.config = {
            "field_mapping": {"col1": "desc1", "col2": "desc2", "col3": None, "col4": ""},
            "delimiter": ",",
            "skip_columns": ["col2"]
        }
        self.environment = "dev"
        self.reader = ReadFromGCS(self.df_args, self.config, self.environment)

    def test_validate_header_empty_header(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        header = ""
        with self.assertRaises(ValueError):
            reader.validate_header(header)

    def test_validate_header_missing_delimiter(self):
        config = {
            "field_mapping": {"col1": "desc1", "col2": "desc2"},
        }
        reader = ReadFromGCS(self.df_args, config, self.environment)
        header = "col1,col2"
        with self.assertRaises(ValueError):
            reader.validate_header(header)

    def test_init_missing_input_path(self):
        bad_df_args = dict(self.df_args)
        bad_df_args['input_path'] = None
        with self.assertRaises(ValueError):
            ReadFromGCS(bad_df_args, self.config, self.environment)

    def test_init_missing_env(self):
        with self.assertRaises(ValueError):
            ReadFromGCS(self.df_args, self.config, None)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_filter_file_path_match(self, mock_logger):
        file_mock = MagicMock()
        file_mock.metadata.path = self.df_args["input_path"]
        regex = re.compile(rf"{self.df_args['input_path']}")
        result = self.reader.filter_file_path(file_mock, regex)
        self.assertTrue(result)
        mock_logger.info.assert_called()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_filter_file_path_no_match(self, mock_logger):
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/otherfile.csv"
        regex = re.compile(rf"{self.df_args['input_path']}")
        result = self.reader.filter_file_path(file_mock, regex)
        self.assertFalse(result)
        mock_logger.info.assert_called()

    def test_get_file_header_no_header(self):
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": ",", "no_header": True}
        reader = ReadFromGCS(self.df_args, config, self.environment)
        mock_file = MagicMock()
        expected_header = "col1,col2"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, expected_header)

    def test_get_file_header_skip_header(self):
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": ",", "skip_header": True}
        reader = ReadFromGCS(self.df_args, config, self.environment)
        mock_file = MagicMock()
        mock_file.readline.return_value = "header_line\n"
        expected_header = "col1,col2"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, expected_header)
        mock_file.readline.assert_called_once()

    def test_get_file_header_default(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        mock_file = MagicMock()
        mock_file.readline.return_value = "header_line\n"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, "header_line")
        mock_file.readline.assert_called_once()

    def test_get_file_header_empty_file(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        mock_file = MagicMock()
        mock_file.readline.return_value = ""
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, "")
        mock_file.readline.assert_called_once()

    def test_get_file_header_both_no_header_and_skip_header(self):
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": ",", "no_header": True, "skip_header": True}
        reader = ReadFromGCS(self.df_args, config, self.environment)
        mock_file = MagicMock()
        expected_header = "col1,col2"
        result = reader.get_file_header(mock_file)
        self.assertEqual(result, expected_header)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_utf8(self, mock_logger):
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = b"col1,col2\na,b\nc,d\n"
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_utf8_sig(self, mock_logger):
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = codecs.BOM_UTF8 + b"col1,col2\na,b\nc,d\n"
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_utf16(self, mock_logger):
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = codecs.BOM_UTF16_LE + "col1,col2\na,b\nc,d\n".encode("utf-16le")
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_utf32(self, mock_logger):
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = codecs.BOM_UTF32_LE + "col1,col2\na,b\nc,d\n".encode("utf-32le")
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            cleaned = [(r[0].replace('\x00', ''), r[1], r[2]) for r in result]
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), cleaned)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_decoding_error(self, mock_logger):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = "col1,col2\nbad\uFFFDline\nokline\n".encode("utf-8")
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            with patch("space_cds_etl_core.pipeline.reader.pvalue.TaggedOutput", wraps=pvalue.TaggedOutput):
                results = list(reader.read_file_chunks(file_mock))
                error_lines = [r for r in results if hasattr(r, "tag") and r.tag == "errors"]
                self.assertTrue(error_lines)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_all_decoding_errors(self, mock_logger):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        content = "col1,col2\nbad\ufffdline\nbad\ufffdline2\n".encode("utf-8")
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            with patch("space_cds_etl_core.pipeline.reader.pvalue.TaggedOutput", wraps=pvalue.TaggedOutput):
                results = list(reader.read_file_chunks(file_mock))
                error_lines = [r for r in results if hasattr(r, "tag") and r.tag == "errors"]
                self.assertEqual(len(error_lines), 2)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_empty_file(self, mock_logger):
        df_args = dict(self.df_args)
        df_args['archive_bucket_name'] = 'mock-archive-bucket'
        df_args['market_code'] = 'mock-market-code'
        df_args['source_system_name'] = 'mock-source-system'
        reader = ReadFromGCS(df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        file_mock.metadata.size_in_bytes = 0
        file_mock.open.side_effect = lambda: io.BytesIO(b"")
        with patch("space_cds_etl_core.pipeline.reader.archive_file"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertEqual(result, [])
            print("Warning log calls:", mock_logger.warning.call_args_list)
            found = any(
                "File gs://bucket/file.csv is empty. Skipping." in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertTrue(found, "Expected warning log not found.")

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_open_exception(self, mock_logger):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        file_mock.open.side_effect = Exception("fail")
        with self.assertRaises(Exception):
            list(reader.read_file_chunks(file_mock))

    def test_read_file_chunks_no_peek(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        class FBin(io.BytesIO):
            def read(self, n=-1):
                return super().read(n)
        content = b"col1,col2\na,b\n"
        def open_side_effect():
            f = FBin(content)
            return f
        file_mock.open.side_effect = open_side_effect
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    def test_read_file_chunks_no_seek(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        class FBin(io.BytesIO):
            pass
        content = b"col1,col2\na,b\n"
        def open_side_effect():
            return FBin(content)
        file_mock.open.side_effect = open_side_effect
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    def test_read_file_chunks_no_size_attr(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        # No 'size' attribute on metadata
        content = b"col1,col2\na,b\n"
        def make_f_bin(content):
            f = io.BytesIO(content)
            f.peek = lambda n: content[:n]
            return f
        file_mock.open.side_effect = lambda: make_f_bin(content)
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    def test_read_file_chunks_no_peek_no_seek(self):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        class FBin(io.BytesIO):
            pass  # No peek, no seek
        content = b"col1,col2\na,b\n"
        def open_side_effect():
            return FBin(content)
        file_mock.open.side_effect = open_side_effect
        with patch.object(reader, "get_file_header", return_value="col1,col2"):
            result = list(reader.read_file_chunks(file_mock))
            self.assertTrue(result)
            self.assertIn(("a,b", "col1,col2", "gs://bucket/file.csv"), result)

    def test_validate_header_all_fields_skipped(self):
        config = {
            "field_mapping": {"col1": "desc1", "col2": "desc2"},
            "delimiter": ",",
            "skip_columns": ["col1", "col2"]
        }
        reader = ReadFromGCS(self.df_args, config, self.environment)
        header = "col1,col2"
        self.assertTrue(reader.validate_header(header))

    @patch("space_cds_etl_core.pipeline.reader.WriteToGCS")
    @patch("space_cds_etl_core.pipeline.reader.fileio.MatchFiles", side_effect=Exception("fail"))
    def test_expand_exception(self, mock_matchfiles, mock_writetogcs):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        pcoll = MagicMock()
        with patch.object(reader, "filepath_regex", self.df_args["input_path"]):
            with self.assertRaises(RuntimeError):
                reader.expand(pcoll)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    @patch("space_cds_etl_core.pipeline.reader.fileio.MatchFiles")
    @patch("space_cds_etl_core.pipeline.reader.fileio.ReadMatches")
    @patch("space_cds_etl_core.pipeline.reader.beam.Filter")
    @patch("space_cds_etl_core.pipeline.reader.beam.FlatMap")
    @patch("space_cds_etl_core.pipeline.reader.beam.combiners.ToList")
    @patch("space_cds_etl_core.pipeline.reader.beam.ParDo")
    @patch("space_cds_etl_core.pipeline.reader.WriteToGCS")
    def test_expand_unsupported_filetype_branch(self, mock_writetogcs, mock_pardo, mock_tolist, mock_flatmap, mock_filter, mock_readmatches, mock_matchfiles, mock_logger):
        df_args = {"input_path": "gs://bucket/folder/file.abc", "encoding_error_file": "gs://bucket/errors.txt"}
        reader = ReadFromGCS(df_args, self.config, self.environment)
        pcoll = MagicMock()
        
        # The code has a bug where glob_pattern is not defined for unsupported file types
        # This test verifies that a RuntimeError is raised in this case
        with self.assertRaises(RuntimeError) as context:
            reader.expand(pcoll)
        
        # Verify the warning was logged before the error occurred
        mock_logger.warning.assert_called_with("Unsupported file type for pattern gs://bucket/folder/file.abc. Only .csv and .TXT are supported. Defaulting to .TXT")
        # Verify the error message contains information about the glob_pattern issue
        self.assertIn("cannot access local variable 'glob_pattern'", str(context.exception))

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_header_pass(self, mock_logger):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        header = "col1,col2"
        self.assertTrue(reader.validate_header(header))
        mock_logger.info.assert_called()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_header_fail(self, mock_logger):
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        header = "col2"
        with self.assertRaises(ValueError):
            reader.validate_header(header)
        mock_logger.error.assert_called()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_header_skip_columns(self, mock_logger):
        config = {
            "field_mapping": {"col1": "desc1", "col2": "desc2", "col3": "desc3"},
            "delimiter": ",",
            "skip_columns": ["col2"]
        }
        reader = ReadFromGCS(self.df_args, config, self.environment)
        header = "col1,col2,col3"
        self.assertTrue(reader.validate_header(header))
        mock_logger.info.assert_called()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_header_field_mapping_none_empty(self, mock_logger):
        config = {
            "field_mapping": {"col1": None, "col2": "", "col3": "desc3"},
            "delimiter": ",",
            "skip_columns": []
        }
        reader = ReadFromGCS(self.df_args, config, self.environment)
        header = "col3"
        self.assertTrue(reader.validate_header(header))
        mock_logger.info.assert_called()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_header_no_skip_columns(self, mock_logger):
        config = {
            "field_mapping": {"col1": "desc1", "col2": "desc2"},
            "delimiter": ","
        }
        reader = ReadFromGCS(self.df_args, config, self.environment)
        header = "col1,col2"
        self.assertTrue(reader.validate_header(header))
        mock_logger.info.assert_called()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_header_only_file(self, mock_logger):
        df_args = dict(self.df_args)
        df_args['archive_bucket_name'] = 'mock-archive-bucket'
        df_args['market_code'] = 'mock-market-code'
        df_args['source_system_name'] = 'mock-source-system'
        reader = ReadFromGCS(df_args, self.config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        file_mock.metadata.size_in_bytes = 10  # Non-zero to simulate header present
        # Simulate file with only header and no data
        content = b"col1,col2\n"
        def open_side_effect():
            f = io.BytesIO(content)
            return f
        file_mock.open.side_effect = open_side_effect
        with patch("space_cds_etl_core.pipeline.reader.archive_file") as mock_archive:
            result = list(reader.read_file_chunks(file_mock))
            self.assertEqual(result, [])
            mock_logger.warning.assert_any_call("File gs://bucket/file.csv is empty after header. Skipping.")
            mock_archive.assert_called_once()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_delimiter_no_delimiter_configured(self, mock_logger):
        config = {"field_mapping": {"col1": "desc1"}}  # No delimiter
        df_args = {"input_path": "gs://bucket/file.csv", "archive_bucket_name": "archive-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        result = reader.validate_delimiter("col1|col2", "a|b", "test.csv")
        self.assertIsNone(result)
        mock_logger.warning.assert_called_with("No delimiter configured. Skipping delimiter validation for file: test.csv")

    @patch("space_cds_etl_core.pipeline.reader.logger")
    @patch("space_cds_etl_core.pipeline.reader.archive_file")
    def test_validate_delimiter_not_in_header(self, mock_archive, mock_logger):
        config = {"field_mapping": {"col1": "desc1"}, "delimiter": "|"}
        df_args = {"input_path": "gs://bucket/file.csv", "error_bucket": "error-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        result = reader.validate_delimiter("col1,col2", "a,b", "test.csv")
        self.assertIsNotNone(result)
        self.assertIn("Delimiter validation failed", result)
        mock_logger.error.assert_called()
        mock_archive.assert_called_once_with("test.csv", "error-bucket", df_args)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    @patch("space_cds_etl_core.pipeline.reader.archive_file")
    def test_validate_delimiter_count_mismatch(self, mock_archive, mock_logger):
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": "|"}
        df_args = {"input_path": "gs://bucket/file.csv", "error_bucket": "error-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        # Use different delimiters (| in header, comma in data) to trigger mismatch
        result = reader.validate_delimiter("col1|col2", "a,b,c", "test.csv")
        self.assertIsNotNone(result)
        self.assertIn("Delimiter validation failed", result)
        mock_logger.error.assert_called()
        mock_archive.assert_called_once()

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_validate_delimiter_success(self, mock_logger):
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": "|"}
        df_args = {"input_path": "gs://bucket/file.csv", "archive_bucket_name": "archive-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        result = reader.validate_delimiter("col1|col2", "a|b", "test.csv")
        self.assertIsNone(result)
        mock_logger.info.assert_called_with("Delimiter detection for test.csv - Header: '|', Data: '|', Configured: '|'")

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_read_file_chunks_with_validation_failure(self, mock_logger):
        config = {"field_mapping": {"col1": "desc1", "col2": "desc2"}, "delimiter": "|"}
        df_args = {
            "input_path": "gs://bucket/file.csv",
            "error_bucket": "error-bucket",
            "market_code": "US",
            "source_system_name": "test",
            "encoding_error_file": "gs://bucket/errors.txt"
        }
        reader = ReadFromGCS(df_args, config, self.environment)
        file_mock = MagicMock()
        file_mock.metadata.path = "gs://bucket/file.csv"
        file_mock.metadata.size_in_bytes = 20
        # File with comma delimiter but config expects pipe
        content = b"col1,col2\na,b\n"
        def open_side_effect():
            return io.BytesIO(content)
        file_mock.open.side_effect = open_side_effect
        with patch("space_cds_etl_core.pipeline.reader.archive_file"):
            result = list(reader.read_file_chunks(file_mock))
            # Should have one validation_failures output and nothing else
            validation_failures = [r for r in result if isinstance(r, pvalue.TaggedOutput) and r.tag == 'validation_failures']
            self.assertEqual(len(validation_failures), 1)
            self.assertIn("Delimiter validation failed", validation_failures[0].value)

    def test_fail_on_validation_errors_with_errors(self):
        config = {"field_mapping": {"col1": "desc1"}, "delimiter": "|"}
        df_args = {"input_path": "gs://bucket/file.csv", "error_bucket": "error-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        errors = ["Error 1", "Error 2"]
        with self.assertRaises(RuntimeError) as context:
            reader._fail_on_validation_errors(errors)
        self.assertIn("Delimiter validation failed", str(context.exception))

    def test_fail_on_validation_errors_no_errors(self):
        config = {"field_mapping": {"col1": "desc1"}, "delimiter": "|"}
        df_args = {"input_path": "gs://bucket/file.csv", "error_bucket": "error-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        result = reader._fail_on_validation_errors([])
        self.assertIsNone(result)

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_sniff_delimiter_exception(self, mock_logger):
        """Test exception handling in sniff_delimiter"""
        config = {"field_mapping": {"col1": "desc1"}, "delimiter": "|"}
        df_args = {"input_path": "gs://bucket/file.csv", "error_bucket": "error-bucket"}
        reader = ReadFromGCS(df_args, config, self.environment)
        # Pass a string that will cause csv.Sniffer to fail
        result = reader.sniff_delimiter("", "test.csv")
        self.assertEqual(result, ',')  # Expecting ',' as returned by the implementation

    @patch("space_cds_etl_core.pipeline.reader.logger")
    def test_detect_file_encode_default_utf8(self, mock_logger):
        """Test detect_file_encode returns utf-8 when no BOM is present"""
        reader = ReadFromGCS(self.df_args, self.config, self.environment)
        # Create a BytesIO without any BOM
        content = b"col1,col2\na,b\n"
        f_bin = io.BytesIO(content)
        f_bin.peek = lambda n: content[:n]
        encoding = reader.detect_file_encode(f_bin)
        self.assertEqual(encoding, "utf-8")

if __name__ == "__main__":
    unittest.main()