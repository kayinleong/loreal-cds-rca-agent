import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.utils.db_connector import DBConnector

class TestDBConnector(unittest.TestCase):
    def setUp(self):
        self.db_mapping = {"au": "audb"}
        self.market_code = "au"
        self.market_type = "b2b"
        self.environment = "dev"

    @patch("space_cds_etl_core.utils.db_connector.google.auth.default", return_value=(None, "test-project"))
    @patch("space_cds_etl_core.utils.db_connector.CONFIG", {"dev": {"SQL_INSTANCE_IP": {"au": "10.148.1.3"}}})
    @patch("space_cds_etl_core.utils.db_connector.market_type_constants", {"b2b": {"DB_PASSWORD_SECRET_NAME": "pwd_secret", "DB_USERNAME_SECRET_NAME": "user_secret"}})
    @patch("space_cds_etl_core.utils.db_connector.get_secret")
    def test_get_database_config(self, mock_get_secret, mock_market_type_constants):
        mock_get_secret.side_effect = ["pwd", "user"]  # password, then user
        connector = DBConnector(self.db_mapping, self.market_code, self.market_type, self.environment)
        config = connector.get_database_config()
        self.assertEqual(config["host"], "10.148.1.3")
        self.assertEqual(config["database"], "audb")
        self.assertEqual(config["user"], "user")
        self.assertEqual(config["password"], "pwd")

    @patch("space_cds_etl_core.utils.db_connector.google.auth.default", return_value=(None, "test-project"))
    def test_get_database_success(self, mock_auth):
        connector = DBConnector(self.db_mapping, self.market_code, self.market_type, self.environment)
        self.assertEqual(connector.get_database(), "audb")

    @patch("space_cds_etl_core.utils.db_connector.google.auth.default", return_value=(None, "test-project"))
    def test_get_database_no_mapping(self, mock_auth):
        connector = DBConnector(None, self.market_code, self.market_type, self.environment)
        with self.assertRaises(ValueError):
            connector.get_database()

    @patch("space_cds_etl_core.utils.db_connector.google.auth.default", return_value=(None, "test-project"))
    @patch.object(DBConnector, "get_database_config")
    @patch("space_cds_etl_core.utils.db_connector.psycopg2.connect")
    def test_create_connection(self, mock_connect, mock_get_db_config, mock_auth):
        mock_get_db_config.return_value = {
            "host": "host",
            "database": "db",
            "user": "user",
            "password": "pwd",
            "port": 5432
        }
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        connector = DBConnector(self.db_mapping, self.market_code, self.market_type, self.environment)
        conn = connector.create_connection()
        self.assertEqual(conn, mock_conn)
        mock_connect.assert_called_once()

    @patch("space_cds_etl_core.utils.db_connector.google.auth.default", return_value=(None, "test-project"))
    def test_close(self, mock_auth):
        connector = DBConnector(self.db_mapping, self.market_code, self.market_type, self.environment)
        mock_conn = MagicMock()
        connector.conn = mock_conn
        connector.close()
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch("space_cds_etl_core.utils.db_connector.google.auth.default", return_value=(None, None))
    def test_init_no_project(self, mock_auth):
        with self.assertRaises(ValueError):
            DBConnector(self.db_mapping, self.market_code, self.market_type, self.environment)

if __name__ == "__main__":
    unittest.main()