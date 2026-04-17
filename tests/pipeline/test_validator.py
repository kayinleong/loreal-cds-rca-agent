import unittest
from unittest.mock import patch, MagicMock
from space_cds_etl_core.pipeline.validator import JsonValidator
from requests.exceptions import RequestException, HTTPError

class TestJsonValidator(unittest.TestCase):
    def setUp(self):
        self.country = "AU"
        self.market_type = "b2b"
        self.schema_name = "myschema.json"
        self.domain = "retail"
        self.df_args = {'job_type': 'int', 'source_system_name': 'test_source'}
        self.validator = JsonValidator(
            self.country, 
            self.market_type, 
            df_args=self.df_args,
            schema_name=self.schema_name, 
            domain=self.domain
        )

    def test_init(self):
        v = JsonValidator("IN", "b2b", schema_name="schema.json", domain="retail")
        self.assertEqual(v.country, "IN")
        self.assertEqual(v.schema_name, "schema.json")
        self.assertIn("http", v.github_validation_rules_repo_url)

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    def test_get_github_headers(self, mock_get_secret):
        v = JsonValidator("IN", "b2b", schema_name="schema.json", domain="retail")
        headers = v.get_github_headers()
        self.assertIn("Authorization", headers)
        self.assertIn("Accept", headers)
        mock_get_secret.assert_called_once()

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    @patch("space_cds_etl_core.pipeline.validator.requests.get")
    def test_resolve_schema_success(self, mock_requests_get, mock_get_secret):
        v = JsonValidator("IN", "b2b", schema_name="schema.json", domain="retail")
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"type": "object", "properties": {}}
        mock_requests_get.return_value = mock_response
        with patch("space_cds_etl_core.pipeline.validator.jsonref.replace_refs", side_effect=lambda s, base_uri=None, loader=None: s):
            schema = v.resolve_schema("http://example.com/schema.json")
            self.assertEqual(schema, {"type": "object", "properties": {}})

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    @patch("space_cds_etl_core.pipeline.validator.requests.get")
    def test_resolve_schema_loader(self, mock_requests_get, mock_get_secret):
        v = JsonValidator("IN", "b2b", schema_name="schema.json", domain="retail")
        # Simulate loader call
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"type": "object"}
        mock_requests_get.return_value = mock_response
        with patch("space_cds_etl_core.pipeline.validator.jsonref.replace_refs", side_effect=lambda s, base_uri=None, loader=None: loader("http://example.com/other.json")):
            schema = v.resolve_schema("http://example.com/schema.json")
            self.assertEqual(schema, {"type": "object"})

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    @patch("space_cds_etl_core.pipeline.validator.requests.get")
    @patch("space_cds_etl_core.pipeline.validator.jsonref.replace_refs", side_effect=lambda s, base_uri=None, loader=None: s)
    @patch("space_cds_etl_core.pipeline.validator.logger")
    def test_get_schema_from_github_success(self, mock_logger, mock_jsonref, mock_requests_get, mock_get_secret):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"type": "object", "properties": {}}
        mock_requests_get.return_value = mock_response

        schema = self.validator.get_schema_from_github(self.country.lower(), "http://example.com/schema.json")
        self.assertEqual(schema, {"type": "object", "properties": {}})

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    @patch("space_cds_etl_core.pipeline.validator.requests.get")
    @patch("space_cds_etl_core.pipeline.validator.jsonref.replace_refs", side_effect=lambda s, base_uri=None, loader=None: s)
    def test_get_schema_from_github_fallback(self, mock_jsonref, mock_requests_get, mock_get_secret):
        # First request fails, fallback also fails, should return None
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = RequestException("fail")
        mock_response_success = MagicMock()
        mock_response_success.raise_for_status.side_effect = RequestException("fail")
        mock_requests_get.side_effect = [mock_response_fail, mock_response_success]

        schema = self.validator.get_schema_from_github(self.country.lower(), "http://example.com/schema.json")
        self.assertIsNone(schema)

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    @patch("space_cds_etl_core.pipeline.validator.requests.get")
    def test_get_schema_from_github_fail_httperror(self, mock_requests_get, mock_get_secret):
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = HTTPError("fail")
        mock_requests_get.side_effect = [mock_response_fail, mock_response_fail]
        result = self.validator.get_schema_from_github(self.country.lower(), "http://example.com/schema.json")
        self.assertIsNone(result)

    @patch("space_cds_etl_core.pipeline.validator.get_secret", return_value="token")
    @patch("space_cds_etl_core.pipeline.validator.requests.get")
    def test_get_schema_from_github_fail_requestexception(self, mock_requests_get, mock_get_secret):
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = RequestException("fail")
        mock_requests_get.side_effect = [mock_response_fail, mock_response_fail]
        with patch("space_cds_etl_core.pipeline.validator.JsonValidator.resolve_schema", side_effect=RequestException("fail")):
            result = self.validator.get_schema_from_github(self.country.lower(), "http://example.com/schema.json")
            self.assertIsNone(result)

    def test_get_schema_from_github_no_schema_name(self):
        v = JsonValidator("AU", "b2b")
        with self.assertRaises(ValueError):
            v.get_schema_from_github("au", "http://example.com/schema.json")

    def test_flatten_schema_and_recurse(self):
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "object", "properties": {"c": {"type": "integer"}}, "required": ["c"]},
                "d": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["a"]
        }
        flat = self.validator.flatten_schema(schema)
        self.assertIn("a", flat["properties"])
        self.assertIn("c", flat["properties"])
        self.assertIn("a", flat["required"])
        self.assertIn("c", flat["required"])

    def test_handle_property_and_required(self):
        # Test _handle_property and _handle_required for all types
        v = self.validator
        v.flat_schema = {"properties": {}, "required": []}
        v._handle_property("x", {"type": "string", "required": True})
        v._handle_property("y", {"type": "object", "properties": {"z": {"type": "integer"}}, "required": ["z"]})
        v._handle_property("arr", {"type": "array", "items": {"type": "string"}})
        v._handle_required({"required": ["x", "y"]})
        self.assertIn("x", v.flat_schema["properties"])
        self.assertIn("z", v.flat_schema["properties"])
        self.assertIn("x", v.flat_schema["required"])
        self.assertIn("y", v.flat_schema["required"])

    @patch.object(JsonValidator, "merge_schemas")
    @patch("space_cds_etl_core.pipeline.validator.Draft202012Validator")
    def test_validate_data(self, mock_validator_class, mock_merge_schemas):
        mock_merge_schemas.return_value = {"type": "object", "properties": {}}
        mock_validator_instance = MagicMock()
        mock_validator_class.return_value = mock_validator_instance
        result = self.validator.validate_data()
        mock_merge_schemas.assert_called_once()
        mock_validator_class.assert_called_once_with({"type": "object", "properties": {}})
        self.assertEqual(result, mock_validator_instance)

    def test_flatten_schema_empty(self):
        # Test that flatten_schema returns flat_schema when schema is None or empty
        result = self.validator.flatten_schema(None)
        self.assertEqual(result, self.validator.flat_schema)
        
        result = self.validator.flatten_schema({})
        self.assertEqual(result, self.validator.flat_schema)

    def test_flatten_schema_with_allOf_oneOf_anyOf(self):
        # Test flattening schema with allOf, oneOf, anyOf keywords
        schema = {
            "type": "object",
            "allOf": [{"type": "object", "properties": {"a": {"type": "string"}}}],
            "oneOf": [{"type": "object", "properties": {"b": {"type": "integer"}}}],
            "anyOf": [{"type": "object", "properties": {"c": {"type": "boolean"}}}]
        }
        flat = self.validator.flatten_schema(schema)
        self.assertIn("allOf", flat)
        self.assertIn("oneOf", flat)
        self.assertIn("anyOf", flat)
        self.assertEqual(len(flat["allOf"]), 1)
        self.assertEqual(len(flat["oneOf"]), 1)
        self.assertEqual(len(flat["anyOf"]), 1)

    @patch("space_cds_etl_core.pipeline.validator.schema_urls")
    @patch.object(JsonValidator, "get_schema_from_github")
    @patch.object(JsonValidator, "flatten_schema")
    @patch("space_cds_etl_core.pipeline.validator.logger")
    def test_merge_schemas(self, mock_logger, mock_flatten, mock_get_schema, mock_schema_urls):
        # Mock schema_urls to return a list of URLs
        mock_schema_urls.get.return_value.get.return_value = [
            "http://example.com/schema1.json",
            "http://example.com/schema2.json"
        ]
        
        # Mock get_schema_from_github to return schemas
        mock_get_schema.side_effect = [
            {"type": "object", "properties": {"field1": {"type": "string"}}},
            {"type": "object", "properties": {"field2": {"type": "integer"}}}
        ]
        
        # Mock flatten_schema to return flattened schemas
        mock_flatten.side_effect = [
            {"type": "object", "properties": {"field1": {"type": "string"}}},
            {"type": "object", "properties": {"field2": {"type": "integer"}}}
        ]
        
        result = self.validator.merge_schemas()
        
        # Verify get_schema_from_github was called twice with correct parameters
        self.assertEqual(mock_get_schema.call_count, 2)
        mock_get_schema.assert_any_call(self.country.lower(), "http://example.com/schema1.json")
        mock_get_schema.assert_any_call(self.country.lower(), "http://example.com/schema2.json")
        
        # Verify flatten_schema was called twice
        self.assertEqual(mock_flatten.call_count, 2)
        
        # Verify logger was called
        self.assertEqual(mock_logger.info.call_count, 2)
        
        # Result should be the flat_schema
        self.assertEqual(result, self.validator.flat_schema)

    def test_format_string(self):
        # Test the format_string method
        template = "http://example.com/{country}/{domain}/{schema_name}"
        result = self.validator.format_string(
            template, 
            country="us", 
            domain="retail", 
            schema_name="test.json"
        )
        self.assertEqual(result, "http://example.com/us/retail/test.json")
        
        # Test with missing keys (should use empty string)
        template = "http://example.com/{country}/{missing}/{schema_name}"
        result = self.validator.format_string(
            template, 
            country="us", 
            schema_name="test.json"
        )
        self.assertEqual(result, "http://example.com/us//test.json")

if __name__ == "__main__":
    unittest.main()
