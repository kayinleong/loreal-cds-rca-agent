import unittest
from unittest.mock import MagicMock, patch
from psycopg2 import DatabaseError
from space_cds_etl_core.utils.audit_logger import AuditLogger

class TestAuditLogger(unittest.TestCase):
    def setUp(self):
        self.db_connector = MagicMock()
        self.config = {}  # Minimal config for tests
        self.df_args = {
            'table': 'public.test_table',
            'input_path': 'gs://bucket/path/to/file.csv',
            'business_type': 'b2c',
            'loadstarttime': '2025-07-24T05:56:48.975Z',
            'job_name': 'job-abc-123-xyz-456-freq',
            'source_system_name': 'SAP',
            'job_id': 'jobid',
            'domain_name_validation': 'domain',
            'archive_bucket_name': 'archive-bucket',
            'baton_file_bucket': 'baton-bucket',
            'next_df_params': {'dependent_tables': [], 'dependency_lookback_window_hours': 1, 'market_code': 'AU'},
            'input_json_path': 'gs://bucket/path/to/file.json',
            'market_code': 'AU'
        }
        self.audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)

    @patch('space_cds_etl_core.utils.audit_logger.AUDIT_TABLE_NAME', {'b2c': 'audit_table'})
    def test_init_sets_attributes(self):
        audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)
        self.assertEqual(audit_logger.table, 'public.test_table')
        self.assertEqual(audit_logger.log_table, 'audit_table')
        self.assertEqual(audit_logger.input_bucket, 'bucket')
        self.assertEqual(audit_logger.input_path, self.df_args['input_path'])

    def test_setup_calls_create_connection(self):
        self.db_connector.create_connection.return_value = 'conn'
        self.audit_logger.setup()
        self.assertEqual(self.audit_logger.connection, 'conn')
        self.db_connector.create_connection.assert_called_once()

    @patch('space_cds_etl_core.utils.audit_logger.archive_file')
    @patch('space_cds_etl_core.utils.audit_logger.execute_values')
    @patch('space_cds_etl_core.utils.audit_logger.sql')
    def test_process_inserts_audit_and_archives(self, mock_sql, mock_execute_values, mock_archive_file):
        conn = MagicMock()
        cursor = MagicMock()
        self.audit_logger.connection = conn
        conn.cursor.return_value = cursor
        element = {'file.csv': {'valid': 10, 'error': 2}}
        mock_sql.SQL.return_value = MagicMock()
        self.audit_logger.df_args['input_json_path'] = 'file.json'
        self.audit_logger.df_args['archive_bucket_name'] = 'archive-bucket'
        self.audit_logger.df_args['next_df_params'] = {'dependent_tables': [], 'dependency_lookback_window_hours': 1, 'market_code': 'AU'}
        with patch.object(self.audit_logger, 'baton_handler') as mock_baton:
            self.audit_logger.process(element)
            mock_execute_values.assert_called()
            mock_archive_file.assert_any_call('file.csv', 'archive-bucket', self.audit_logger.df_args)
            mock_archive_file.assert_any_call('file.json', 'archive-bucket', self.audit_logger.df_args)
            mock_baton.assert_called()

    def test_baton_handler_with_dependency(self):
        with patch.object(self.audit_logger, 'check_dependency', return_value=True), \
             patch.object(self.audit_logger, 'create_baton_file') as mock_create:
            self.audit_logger.df_args['next_df_params'] = {
                'dependent_tables': ['t1'],
                'dependency_lookback_window_hours': 1,
                'market_code': 'AU',
                'sp_name': 'proc_etl'
            }
            self.audit_logger.baton_handler(1)
            mock_create.assert_called()

    def test_baton_handler_without_dependency(self):
        with patch.object(self.audit_logger, 'create_baton_file') as mock_create:
            self.audit_logger.df_args['next_df_params'] = {
                'some_other_param': 'value',
                'sp_name': 'proc_generic'
            }
            self.audit_logger.baton_handler(1)
            mock_create.assert_called()

    def test_baton_handler_row_count_zero(self):
        with patch.object(self.audit_logger, 'create_baton_file') as mock_create:
            # include sp_name but row_count == 0 should still block
            self.audit_logger.df_args['next_df_params'] = {'sp_name': 'proc_zero'}
            self.audit_logger.baton_handler(0)
            mock_create.assert_not_called()

    def test_fetch_file_name_returns_result(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = ['file.csv']
        self.audit_logger.connection = conn
        self.audit_logger.table = 'public.test_table'
        result = self.audit_logger.fetch_file_name()
        self.assertEqual(result, 'file.csv')

    def test_fetch_file_name_returns_default(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None
        self.audit_logger.connection = conn
        self.audit_logger.table = 'public.test_table'
        result = self.audit_logger.fetch_file_name()
        self.assertEqual(result, 'unable to fetch file name')

    @patch('space_cds_etl_core.utils.audit_logger.storage')
    def test_create_baton_file_uploads_json(self, mock_storage):
        bucket = MagicMock()
        blob = MagicMock()
        mock_storage.Client.return_value.bucket.return_value = bucket
        bucket.blob.return_value = blob
        self.audit_logger.df_args['next_df_params'] = {'dependent_tables': [], 'market_code': 'au', 'loadtype': 'stg', 'frequency': 'freq', 'source_system_name': 'SAP'}
        self.audit_logger.df_args['job_name'] = 'au-foo-bar-stg-baz-freq'
        self.audit_logger.df_args['source_system_name'] = 'SAP'
        self.audit_logger.create_baton_file('bucket', 'file.json')
        blob.upload_from_string.assert_called()

    def test_check_dependency_true(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = [1]
        audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)
        audit_logger.connection = conn
        audit_logger.df_args['next_df_params'] = {'dependent_tables': ['t1'], 'dependency_lookback_window_hours': 1, 'market_code': 'AU'}
        result = audit_logger.check_dependency()
        self.assertTrue(result)

    def test_check_dependency_false(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = [0]
        audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)
        audit_logger.connection = conn
        audit_logger.df_args['next_df_params'] = {'dependent_tables': ['t1'], 'dependency_lookback_window_hours': 1, 'market_code': 'AU'}
        result = audit_logger.check_dependency()
        self.assertFalse(result)

    def test_check_dependency_none(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None
        audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)
        audit_logger.connection = conn
        audit_logger.df_args['next_df_params'] = {'dependent_tables': ['t1'], 'dependency_lookback_window_hours': 1, 'market_code': 'AU'}
        result = audit_logger.check_dependency()
        self.assertFalse(result)

    def test_check_dependency_no_connection(self):
        audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)
        audit_logger.connection = None
        with self.assertRaises(RuntimeError):
            audit_logger.check_dependency()

    def test_check_dependency_database_error(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.execute.side_effect = DatabaseError("fail")
        audit_logger = AuditLogger(self.db_connector, self.config, self.df_args)
        audit_logger.connection = conn
        audit_logger.df_args['next_df_params'] = {'dependent_tables': ['t1'], 'dependency_lookback_window_hours': 1, 'market_code': 'AU'}
        with self.assertRaises(RuntimeError):
            audit_logger.check_dependency()

    def test_finish_bundle_commits_and_closes(self):
        conn = MagicMock()
        self.audit_logger.connection = conn
        self.audit_logger.db_connector = MagicMock()
        self.audit_logger.finish_bundle()
        conn.commit.assert_called()
        self.audit_logger.db_connector.close.assert_called()

    @patch('space_cds_etl_core.utils.audit_logger.archive_file')
    @patch('space_cds_etl_core.utils.audit_logger.execute_values')
    @patch('space_cds_etl_core.utils.audit_logger.sql')
    def test_process_target_load_integration(self, mock_sql, mock_execute_values, mock_archive_file):
        # isTargetLoad True path
        cfg = {"isTargetLoad": True}
        audit_logger = AuditLogger(self.db_connector, cfg, self.df_args.copy())
        conn = MagicMock()
        cursor = MagicMock()
        audit_logger.connection = conn
        conn.cursor.return_value = cursor
        mock_sql.SQL.return_value = MagicMock()
        element = {'file.csv': {'valid': 5, 'error': 1}}
        with patch.object(audit_logger, 'baton_handler') as mock_baton:
            audit_logger.process(element)
            mock_execute_values.assert_called()
            self.assertEqual(audit_logger.loadtype, "Integration Load")
            mock_baton.assert_called()

    @patch('space_cds_etl_core.utils.audit_logger.archive_file')
    @patch('space_cds_etl_core.utils.audit_logger.execute_values')
    @patch('space_cds_etl_core.utils.audit_logger.sql')
    def test_process_no_input_json_path(self, mock_sql, mock_execute_values, mock_archive_file):
        # branch where optional json archive not triggered
        conn = MagicMock()
        cursor = MagicMock()
        self.audit_logger.connection = conn
        conn.cursor.return_value = cursor
        mock_sql.SQL.return_value = MagicMock()
        df_args_clone = self.df_args
        df_args_clone.pop('input_json_path', None)
        self.audit_logger.df_args = df_args_clone
        element = {'file.csv': {'valid': 2, 'error': 0}}
        with patch.object(self.audit_logger, 'baton_handler'):
            self.audit_logger.process(element)
            # only one archive (csv) called
            self.assertEqual(mock_archive_file.call_count, 1)

    def test_baton_handler_next_params_empty_row_count_positive(self):
        # next_df_params empty -> no baton file (sp_name missing)
        with patch.object(self.audit_logger, 'create_baton_file') as mock_create:
            self.audit_logger.df_args['next_df_params'] = {}
            self.audit_logger.baton_handler(3)
            mock_create.assert_not_called()

    # NEW: dependency satisfied but sp_name missing -> no baton file
    def test_baton_handler_with_dependency_missing_sp_name(self):
        with patch.object(self.audit_logger, 'check_dependency', return_value=True), \
             patch.object(self.audit_logger, 'create_baton_file') as mock_create:
            self.audit_logger.df_args['next_df_params'] = {
                'dependent_tables': ['t1'],
                'dependency_lookback_window_hours': 1,
                'market_code': 'AU'
            }
            self.audit_logger.baton_handler(2)
            mock_create.assert_not_called()

    # NEW: no dependency path but sp_name missing -> no baton file
    def test_baton_handler_without_dependency_missing_sp_name(self):
        with patch.object(self.audit_logger, 'create_baton_file') as mock_create:
            self.audit_logger.df_args['next_df_params'] = {
                'some_other_param': 'value'
            }
            self.audit_logger.baton_handler(4)
            mock_create.assert_not_called()

    def test_check_dependency_unexpected_exception(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.execute.side_effect = Exception("boom")
        self.audit_logger.connection = conn
        self.audit_logger.df_args['next_df_params'] = {
            'dependent_tables': ['t1'],
            'dependency_lookback_window_hours': 1,
            'market_code': 'AU'
        }
        with self.assertRaises(RuntimeError) as ctx:
            self.audit_logger.check_dependency()
        self.assertIn("Unexpected error", str(ctx.exception))

if __name__ == '__main__':
    unittest.main()