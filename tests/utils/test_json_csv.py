import unittest
from unittest.mock import patch, MagicMock, mock_open
from space_cds_etl_core.utils import json_csv

class TestJsonCsv(unittest.TestCase):
    def test_sanitize_data_valid(self):
        self.assertEqual(json_csv.sanitize_data('{"a":1}'), {"a": 1})

    def test_sanitize_data_invalid(self):
        with patch('space_cds_etl_core.utils.json_csv.logger') as mock_logger:
            s = '{"a":1'
            self.assertEqual(json_csv.sanitize_data(s), s)
            mock_logger.info.assert_called()

    def test_sanitize_data_not_str(self):
        self.assertEqual(json_csv.sanitize_data(123), 123)

    def test_get_values_for_key(self):
        data = [{'Content': '{"a": 1}'}, {'Content': '{"b": 2}'}]
        result = json_csv.get_values_for_key(data)
        self.assertEqual(result[0]['Content'], {'a': 1})
        self.assertEqual(result[1]['Content'], {'b': 2})

    def test_flatten_dict_primitives(self):
        d = {'a': 1, 'b': 2}
        self.assertEqual(json_csv.flatten_dict(d), d)

    def test_flatten_dict_nested(self):
        d = {'a': {'b': 2, 'c': {'d': 3}}, 'e': 4}
        self.assertEqual(json_csv.flatten_dict(d), {'a_b': 2, 'a_c_d': 3, 'e': 4})

    def test_flatten_dict_list(self):
        d = {'a': [{'b': 1}, {'c': 2}], 'd': 3}
        self.assertEqual(json_csv.flatten_dict(d), {'a_0_b': 1, 'a_1_c': 2, 'd': 3})

    def test_get_files_non_gs(self):
        fs = MagicMock()
        files = json_csv.get_files(fs, 'notgs://foo')
        self.assertEqual(files, [])

    def test_get_files_gs(self):
        fs = MagicMock()
        fs.glob.return_value = ['bucket/prefix/file1.json', 'bucket/prefix/file2.json']
        pattern = 'gs://bucket/prefix/file1.json'
        with patch('re.compile') as mock_re:
            mock_regex = MagicMock()
            mock_regex.search.side_effect = lambda f: 'file1' in f
            mock_re.return_value = mock_regex
            files = json_csv.get_files(fs, pattern)
            self.assertEqual(files, ['gs://bucket/prefix/file1.json'])

    def test_load_json_success(self):
        fs = MagicMock()
        m = mock_open(read_data='{"a": 1}')
        with patch('builtins.open', m):
            fs.open = m
            result = json_csv.load_json(fs, 'gs://bucket/file.json')
            self.assertEqual(result, {"a": 1})

    def test_load_json_failure(self):
        fs = MagicMock()
        m = mock_open(read_data='bad json')
        with patch('builtins.open', m):
            fs.open = m
            with patch('space_cds_etl_core.utils.json_csv.logger') as mock_logger:
                result = json_csv.load_json(fs, 'gs://bucket/file.json')
                self.assertIsNone(result)
                mock_logger.error.assert_called()

    def test_write_csv(self):
        fs = MagicMock()
        records = [{'a': 1, 'Content_b': 2}]
        output_dir = 'dir'
        country = 'IN'
        date = '01012025'
        written = {}
        class F:
            def write(self, data): written['data'] = data
            def __enter__(self): return self
            def __exit__(self, *a): pass
        fs.open = lambda fname, mode: F()
        with patch('pandas.DataFrame') as mock_df:
            mock_df_inst = MagicMock()
            mock_df.return_value = mock_df_inst
            mock_df_inst.columns = ['Content_b']
            mock_df_inst.to_csv.return_value = None
            with patch('io.StringIO') as mock_buf:
                mock_buffer = MagicMock()
                mock_buf.return_value.__enter__.return_value = mock_buffer
                mock_buffer.read.return_value = 'csvdata'
                fname = json_csv.write_csv(fs, output_dir, country, records, date)
                self.assertEqual(fname, f"{output_dir}/access_{country}_{date}.csv")

    def test_group_by_country_basic(self):
        records = [{'Content': {'headers': {'X-Country': 'IN'}}}]
        grouped = json_csv.group_by_country(records)
        self.assertIn('IN', grouped)

    def test_group_by_country_with_code(self):
        records = [{'Content': {'headers': {'X-Country': 'IN'}}}]
        grouped = json_csv.group_by_country(records, country_code='IN')
        self.assertIn('IN', grouped)
        grouped = json_csv.group_by_country(records, country_code='US')
        self.assertEqual(grouped, {})

    def test_group_by_country_missing(self):
        records = [{'Content': {}}]
        with patch('space_cds_etl_core.utils.json_csv.logger') as mock_logger:
            grouped = json_csv.group_by_country(records)
            self.assertEqual(grouped, {})
            mock_logger.error.assert_called()

    @patch('space_cds_etl_core.utils.json_csv.gcsfs.GCSFileSystem')
    def test_process_json_to_csv_no_files(self, mock_gcsfs):
        fs = MagicMock()
        mock_gcsfs.return_value = fs
        fs.glob.return_value = []
        with patch('space_cds_etl_core.utils.json_csv.logger') as mock_logger:
            result = json_csv.process_json_to_csv('gs://bucket/folder/*.json')
            self.assertIsNone(result)
            mock_logger.info.assert_called()

    @patch('space_cds_etl_core.utils.json_csv.gcsfs.GCSFileSystem')
    @patch('space_cds_etl_core.utils.json_csv.write_csv')
    @patch('space_cds_etl_core.utils.json_csv.group_by_country')
    @patch('space_cds_etl_core.utils.json_csv.get_values_for_key')
    @patch('space_cds_etl_core.utils.json_csv.load_json')
    @patch('space_cds_etl_core.utils.json_csv.get_files')
    def test_process_json_to_csv_success(
        self, mock_get_files, mock_load_json, mock_get_values, mock_group, mock_write, mock_gcsfs
    ):
        mock_get_files.return_value = ['gs://bucket/file1.json']
        mock_load_json.return_value = [{'Content': '{"headers": {"X-Country": "IN"}}'}]
        mock_get_values.return_value = [{'Content': {'headers': {'X-Country': 'IN'}}}]
        mock_group.return_value = {'IN': [{'a': 1}]}
        mock_write.return_value = 'out/access_IN_01012025.csv'
        result = json_csv.process_json_to_csv('gs://bucket/file1.json')
        self.assertIsInstance(result, tuple)
        self.assertIn('.csv', result[0])
        self.assertIn('file1.json', result[1])

if __name__ == '__main__':
    unittest.main()