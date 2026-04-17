import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.utils import secret

class TestGetSecret(unittest.TestCase):
    @patch('space_cds_etl_core.utils.secret.logger')
    @patch('space_cds_etl_core.utils.secret.google.auth.default', return_value=(None, 'test-project'))
    @patch('space_cds_etl_core.utils.secret.secretmanager.SecretManagerServiceClient')
    def test_get_secret_success(self, mock_secret_client, mock_auth, mock_logger):
        mock_instance = MagicMock()
        mock_secret_client.return_value = mock_instance
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = 'my-secret-value'
        mock_instance.access_secret_version.return_value = mock_response
        result = secret.get_secret('my-secret')
        self.assertEqual(result, 'my-secret-value')
        mock_logger.info.assert_called_with('Fetching secret: %s', 'my-secret')
        mock_instance.access_secret_version.assert_called_once()

    @patch('space_cds_etl_core.utils.secret.logger')
    @patch('space_cds_etl_core.utils.secret.google.auth.default', return_value=(None, 'test-project'))
    @patch('space_cds_etl_core.utils.secret.secretmanager.SecretManagerServiceClient')
    def test_get_secret_failure(self, mock_secret_client, mock_auth, mock_logger):
        mock_instance = MagicMock()
        mock_secret_client.return_value = mock_instance
        mock_instance.access_secret_version.side_effect = Exception('fail')
        with self.assertRaises(Exception):
            secret.get_secret('bad-secret')
        mock_logger.error.assert_called_with('Failed to fetch secret %s: %s', 'bad-secret', 'fail')

if __name__ == '__main__':
    unittest.main()
