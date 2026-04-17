import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
from src.main import (
    validate_arguments, download_from_gcs, load_config_path, load_config
)
import apache_beam as beam
import warnings
# Patch sys.argv so argparse doesn't fail
sys.argv = [
    "main.py",
    "--input_path", "gs://bucket/file.csv",
    "--market_code", "AU",
    "--source_system_name", "SAP",
    "--config_gcs_path", "gs://bucket/config.yaml",
    "--environment", "dev",
    "--db_mapping_config", "gs://bucket/dbmap.yaml",
    "--table", "sometable",
    "--business_type", "b2c",
    "--error_bucket", "gs://bucket/errors",
    "--next_df_params", "{'job_name': 'job', 'sp_name': 'sp', 'dependent_tables': []}",
    "--archive_bucket_name", "gs://bucket/archive",
    "--baton_file_bucket", "gs://bucket/baton",
    "--validation_json", "schema.json",
    "--gcs_uri_log", "gs://bucket/logs",
    "--domainname", "customer"
]

# Dummy callable for Beam transforms to avoid pickling errors
class DummyDoFn:
    def __init__(self, *args, **kwargs): 
        pass
    def process(self, element, *args, **kwargs): 
        return [element]

class DummyWriter(DummyDoFn): 
    pass
class DummyInvalid(DummyDoFn): 
    pass
class DummyAuditTransform(beam.PTransform):
    def expand(self, pcoll):
        return pcoll

class DummyAudit(beam.PTransform):
    def __init__(self, *args, **kwargs):
        super().__init__()

    def expand(self, pcoll):
        return pcoll  # No-op: just return input

    def __call__(self, pcoll, *args, **kwargs):
        return self.expand(pcoll)  # Allow it to be used like a callable


# Inside your test_run_pipeline:



class TestMain(unittest.TestCase):

    @patch('src.main.upload_log_to_gcs')
    @patch('src.main.create_file_name')
    @patch('src.main.beam.Pipeline')
    @patch('src.main.JsonValidator')
    @patch('src.main.DBConnector')
    @patch('src.main.GoogleCloudOptions')
    @patch('src.main.load_config')
    @patch('src.main.parse_arguments')
    @patch('src.main.ValidateData')
    @patch('src.main.GenericWriter')
    @patch('src.main.AuditLogger')
    @patch('src.main.GenericTransformer')  # NEW PATCH
    def test_run_pipeline(self, mock_generic_transformer, mock_audit_logger, mock_generic_writer, mock_validate_data,
                          mock_parse_args, mock_load_config, mock_gcloud_opts,
                          mock_db_connector, mock_json_validator, mock_beam_pipeline,
                          mock_create_file, mock_upload_log):
        # Provide a dummy DoFn instance to avoid pickling recursion
        mock_generic_transformer.return_value = DummyDoFn

        # Setup known_args
        warnings.simplefilter("ignore")

        known_args = MagicMock()
        known_args.input_path = 'gs://bucket/file.csv'
        known_args.market_code = 'AU'
        known_args.source_system_name = 'SAP'
        known_args.config_gcs_path = 'gs://bucket/config.yaml'
        known_args.environment = 'dv'
        known_args.db_mapping_config = 'gs://bucket/db.yaml'
        known_args.table = 'table'
        known_args.business_type = 'b2b'
        known_args.error_bucket = 'gs://bucket/error'
        known_args.next_df_params = '{}'
        known_args.archive_bucket_name = 'gs://bucket/archive'
        known_args.baton_file_bucket = 'gs://bucket/baton'
        known_args.validation_json = 'schema.json'
        known_args.gcs_uri_log = 'gs://bucket/log'
        known_args.domain_name_validation = 'domain'
        mock_parse_args.return_value = (known_args, ['--foo'])
        mock_load_config.side_effect = [
            {'file_delimiter': '|', 'delimiter': '|'},
            {'environments': {'dv': {'databases': {}}}}
        ]
        mock_gcloud_opts.return_value.job_name = 'job'
        mock_gcloud_opts.return_value.template_location = 'gs://bucket/templates/some/path/jobid'
        mock_db_connector.return_value = MagicMock()
        mock_json_validator.return_value = MagicMock()
        mock_beam_pipeline.return_value.__enter__.return_value = MagicMock()
        mock_create_file.return_value = 'logfile'
        mock_validate_data.return_value = DummyDoFn
        mock_generic_writer.return_value = DummyWriter
        mock_audit_logger.return_value = DummyAudit()

        from src.main import run_pipeline
        run_pipeline()
        mock_upload_log.assert_called()

    @patch('src.main.argparse.ArgumentParser')
    def test_parse_arguments(self, mock_arg_parser):
        mock_parser_instance = MagicMock()
        mock_known_args = MagicMock()
        mock_pipeline_args = ['--runner', 'DataflowRunner']
        mock_parser_instance.parse_known_args.return_value = (mock_known_args, mock_pipeline_args)
        mock_arg_parser.return_value = mock_parser_instance

        from src.main import parse_arguments
        known_args, pipeline_args = parse_arguments()
        self.assertEqual(known_args, mock_known_args)
        self.assertEqual(pipeline_args, mock_pipeline_args)

    @patch("src.main.CloudLogger")
    @patch("builtins.exit", side_effect=SystemExit)
    @patch("sys.exit", side_effect=SystemExit)
    def test_validate_arguments(self, mock_sys_exit, mock_builtin_exit, mock_logger):
        args = MagicMock()
        # market_code too short
        args.market_code = "A"
        args.config_gcs_path = "gs://bucket/config.yaml"
        args.business_type = "b2c"
        with self.assertRaises(SystemExit):
            validate_arguments(args)
        # config_gcs_path not GCS
        args.market_code = "AU"
        args.config_gcs_path = "/notgcs/path"
        with self.assertRaises(SystemExit):
            validate_arguments(args)
        # business_type invalid
        args.config_gcs_path = "gs://bucket/config.yaml"
        args.business_type = "foo"
        with self.assertRaises(SystemExit):
            validate_arguments(args)
        # valid
        args.business_type = "b2c"
        try:
            validate_arguments(args)
        except SystemExit:
            self.fail("validate_arguments raised SystemExit unexpectedly!")

    @patch("src.main.FileSystems.open", new_callable=mock_open, read_data=b"config")
    @patch("src.main.open", new_callable=mock_open, read_data="config: true")
    @patch("src.main.os.makedirs")
    @patch("src.main.logger")
    def test_download_from_gcs(self, mock_logger, mock_makedirs, mock_open_local, mock_open_gcs):
        download_from_gcs("gs://bucket/file", "localfile")
        mock_makedirs.assert_called()
        mock_open_gcs.assert_called()
        mock_open_local.assert_called()
        mock_logger.info.assert_called()

    @patch("src.main.download_from_gcs")
    def test_load_config_path(self, mock_download):
        mock_download.return_value = None
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            mock_tmp.return_value.__enter__.return_value.name = "tmpfile"
            mock_tmp.return_value.name = "tmpfile"
            result = load_config_path("gs://bucket/config.yaml")
            self.assertEqual(result, "tmpfile")

    @patch("src.main.load_config_path", return_value="tmpfile")
    @patch("src.main.open", new_callable=mock_open, read_data="config: true")
    def test_load_config(self, mock_open_local, mock_load_config_path):
        with patch("yaml.safe_load", return_value={"foo": "bar"}):
            result = load_config("gs://bucket/config.yaml")
            self.assertEqual(result, {"foo": "bar"})

if __name__ == "__main__":
    unittest.main()