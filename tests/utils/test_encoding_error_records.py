import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.utils.encoding_error_records import WriteToGCS

class TestWriteToGCS(unittest.TestCase):

    @patch('space_cds_etl_core.utils.encoding_error_records.logger')
    def test_process_type_logging(self, mock_logger):
        elements = [('err1', 'header', 'filename')]
        with patch('space_cds_etl_core.utils.encoding_error_records.FileSystems.create') as mock_create:
            mock_file = MagicMock()
            mock_create.return_value.__enter__.return_value = mock_file
            result = list(self.dofn.process(elements))
            # The logger.info should be called for all log lines
            calls = [
                unittest.mock.call(f"Processing 1 error records to {self.output_path}"),
                unittest.mock.call(f"elements type is {type(elements)}"),
                unittest.mock.call(f"Wrote 1 error records to {self.output_path}")
            ]
            mock_logger.info.assert_has_calls(calls, any_order=False)
            self.assertEqual(result, [f'Wrote errors to {self.output_path}'])

    def setUp(self):
        self.output_path = 'gs://bucket/errors.txt'
        self.dofn = WriteToGCS(self.output_path)


    @patch('space_cds_etl_core.utils.encoding_error_records.FileSystems.create')
    def test_process_with_content(self, mock_create):
        mock_file = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_file
        elements = [('err1', 'header', 'filename'), ('err2', 'header', 'filename')]
        result = list(self.dofn.process(elements))
        mock_create.assert_called_once_with(self.output_path)
        mock_file.write.assert_called_once_with(b'err1\nerr2')
        self.assertEqual(result, [f'Wrote errors to {self.output_path}'])

    @patch('space_cds_etl_core.utils.encoding_error_records.FileSystems.create')
    def test_process_no_content(self, mock_create):
        elements = []
        result = list(self.dofn.process(elements))
        mock_create.assert_not_called()
        self.assertEqual(result, [f'No errors to write to {self.output_path}'])

    @patch('space_cds_etl_core.utils.encoding_error_records.FileSystems.create')
    def test_process_with_all_empty_lines(self, mock_create):
        mock_file = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_file
        elements = [('', 'header', 'filename'), ('', 'header', 'filename')]
        result = list(self.dofn.process(elements))
        mock_create.assert_called_once_with(self.output_path)
        mock_file.write.assert_called_once_with(b'\n')
        self.assertEqual(result, [f'Wrote errors to {self.output_path}'])

    @patch('space_cds_etl_core.utils.encoding_error_records.FileSystems.create')
    def test_process_with_some_empty_lines(self, mock_create):
        mock_file = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_file
        elements = [('err1', 'header', 'filename'), ('', 'header', 'filename')]
        result = list(self.dofn.process(elements))
        mock_create.assert_called_once_with(self.output_path)
        mock_file.write.assert_called_once_with(b'err1\n')
        self.assertEqual(result, [f'Wrote errors to {self.output_path}'])

    def test_process_with_wrong_type(self):
        result = list(self.dofn.process(None))
        self.assertEqual(result, [f'No errors to write to {self.output_path}'])

    @patch('space_cds_etl_core.utils.encoding_error_records.FileSystems.create')
    def test_process_file_write_exception(self, mock_create):
        mock_create.side_effect = Exception("fail to write")
        elements = [('err1', 'header', 'filename')]
        with self.assertRaises(Exception):
            list(self.dofn.process(elements))

if __name__ == '__main__':
    unittest.main()
