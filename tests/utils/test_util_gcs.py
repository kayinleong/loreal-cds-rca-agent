import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.utils import util_gcs
from datetime import datetime

class TestUtilGCS(unittest.TestCase):
    @patch('space_cds_etl_core.utils.util_gcs.storage.Client')
    def test_copy_file_success(self, mock_storage_client):
        mock_client = MagicMock()
        mock_storage_client.return_value = mock_client
        src_bucket = MagicMock()
        dest_bucket = MagicMock()
        src_blob = MagicMock()
        mock_client.bucket.side_effect = [src_bucket, dest_bucket]
        src_bucket.blob.return_value = src_blob
        src_blob.exists.return_value = True
        result = util_gcs.copy_file('gs://src-bucket/folder/file.csv', 'gs://dest-bucket', 'dest_blob')
        src_bucket.blob.assert_called_once_with('folder/file.csv')
        dest_bucket.blob.assert_not_called()  # Not used in copy_file
        src_blob.exists.assert_called_once()
        src_bucket.copy_blob.assert_called_once_with(src_blob, dest_bucket, 'dest_blob')
        self.assertEqual(result, src_blob)

    @patch('space_cds_etl_core.utils.util_gcs.storage.Client')
    def test_copy_file_file_not_found(self, mock_storage_client):
        mock_client = MagicMock()
        mock_storage_client.return_value = mock_client
        src_bucket = MagicMock()
        dest_bucket = MagicMock()
        src_blob = MagicMock()
        mock_client.bucket.side_effect = [src_bucket, dest_bucket]
        src_bucket.blob.return_value = src_blob
        src_blob.exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            util_gcs.copy_file('gs://src-bucket/folder/file.csv', 'gs://dest-bucket', 'dest_blob')

    def test_copy_file_invalid_uri(self):
        with self.assertRaises(ValueError):
            util_gcs.copy_file('invalid-uri', 'dest-bucket', 'dest_blob')

    @patch('space_cds_etl_core.utils.util_gcs.copy_file')
    @patch('space_cds_etl_core.utils.util_gcs.get_file_path')
    def test_archive_file(self, mock_get_file_path, mock_copy_file):
        mock_get_file_path.return_value = 'dest_blob'
        mock_source_blob = MagicMock()
        mock_copy_file.return_value = mock_source_blob
        mock_source_blob.delete.return_value = None
        util_gcs.archive_file('gs://src-bucket/folder/file.csv', 'gs://dest-bucket', {'market_code': 'mc', 'source_system_name': 'sys'})
        mock_get_file_path.assert_called_once()
        mock_copy_file.assert_called_once()
        mock_source_blob.delete.assert_called_once()

    @patch('space_cds_etl_core.utils.util_gcs.datetime')
    def test_get_file_path(self, mock_datetime):
        mock_now = MagicMock()
        mock_now.date.return_value = datetime(2025, 7, 9).date()
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *a, **kw: datetime
        df_args = {'market_code': 'mc', 'source_system_name': 'sys'}
        result = util_gcs.get_file_path('gs://src-bucket/folder/file.csv', df_args)
        self.assertIn('mc/sys/inbound/2025-07-09/file.csv', result)

if __name__ == '__main__':
    unittest.main()
