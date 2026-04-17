import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.utils.baton_writer import BatonFileWriter

class TestBatonFileWriter(unittest.TestCase):
    @patch("space_cds_etl_core.utils.baton_writer.storage.Client")
    def test_process(self, mock_storage_client):
        df_args = {
            "baton_file_bucket": "my-bucket",
            "job_name": "au-job-foo-bar-loadtype-daily-xyz",
            "next_df_params": {
                "job_name": "au-job-foo-bar-loadtype-daily-xyz",
                "sp_name": "sp_test",
                "dependent_tables": ["t1", "t2"]
            }
        }
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        writer = BatonFileWriter(df_args)
        element = {"dummy": "data"}
        result = list(writer.process(element))

        mock_storage_client.assert_called_once()
        mock_storage_client.return_value.bucket.assert_called_with("my-bucket")
        mock_bucket.blob.assert_called_with("au-job-foo-bar-loadtype-daily-xyz.json")
        mock_blob.upload_from_string.assert_called_once()
        self.assertEqual(
            result[0],
            "Baton file created: gs://my-bucket/au-job-foo-bar-loadtype-daily-xyz.json"
        )

if __name__ == "__main__":
    unittest.main()