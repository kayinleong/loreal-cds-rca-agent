import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.utils import logger as logger_module

class TestLoggerUtils(unittest.TestCase):
    @patch("space_cds_etl_core.utils.logger.storage.Client")
    def test_upload_log_to_gcs(self, mock_storage_client):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        logger_module.upload_log_to_gcs("gs://my-bucket", "local.log", "logs/remote.log")
        mock_storage_client.assert_called_once()
        mock_storage_client.return_value.bucket.assert_called_with("my-bucket")
        mock_bucket.blob.assert_called_with("logs/remote.log")
        mock_blob.upload_from_filename.assert_called_with("local.log")

    @patch("space_cds_etl_core.utils.logger.datetime")
    @patch("space_cds_etl_core.utils.logger.ZoneInfo")
    def test_create_file_name(self, mock_zoneinfo, mock_datetime):
        mock_zoneinfo.return_value = "UTC"
        mock_now = MagicMock()
        mock_now.date.return_value = "2024-06-23"
        mock_now.strftime.return_value = "2024-06-23T12:00:00.123Z"
        mock_datetime.now.return_value = mock_now

        result = logger_module.create_file_name("au", "sap", "job1")
        self.assertTrue(result.startswith("au/sap/2024-06-23/2024-06-23T12:00:00"))
        self.assertTrue(result.endswith("_job1.log"))

    @patch("space_cds_etl_core.utils.logger.StructuredLogHandler")
    @patch("space_cds_etl_core.utils.logger.logging.FileHandler")
    @patch("space_cds_etl_core.utils.logger.logging.getLogger")
    def test_cloud_logger_singleton_and_get_logger(self, mock_get_logger, mock_file_handler, mock_structured_handler):
        # Reset singleton for test isolation
        logger_module.CloudLogger._instance = None

        mock_logger = MagicMock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        cloud_logger1 = logger_module.CloudLogger()
        cloud_logger2 = logger_module.CloudLogger()
        self.assertIs(cloud_logger1, cloud_logger2)

        logger = cloud_logger1.get_logger(level=42)
        mock_logger.setLevel.assert_called_with(42)
        self.assertEqual(logger, mock_logger)

if __name__ == "__main__":
    unittest.main()