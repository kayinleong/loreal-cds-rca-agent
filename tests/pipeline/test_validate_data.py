import unittest
from unittest.mock import MagicMock
from space_cds_etl_core.pipeline.validate_data import ValidateData

class TestValidateData(unittest.TestCase):
    def setUp(self):
        self.mock_jsonvalidator = MagicMock()
        self.mock_validator = MagicMock()
        self.mock_jsonvalidator.validate_data.return_value = self.mock_validator

    def test_setup_with_schema_name(self):
        v = ValidateData("IN", "myschema", [self.mock_jsonvalidator])
        v.setup()
        self.assertEqual(v.validators, [self.mock_validator])
        self.mock_jsonvalidator.validate_data.assert_called_once()

    def test_setup_without_schema_name(self):
        v = ValidateData("IN", None, self.mock_jsonvalidator)
        v.setup()
        self.assertEqual(v.validators, [])
        self.mock_jsonvalidator.validate_data.assert_not_called()

    def test_process_with_errors(self):
        v = ValidateData("IN", "myschema", self.mock_jsonvalidator)
        v.validators = [MagicMock()]
        mock_error1 = MagicMock()
        mock_error1.message = "error1"
        mock_error1.path = ["foo"]
        mock_error2 = MagicMock()
        mock_error2.message = "error2"
        mock_error2.path = ["bar"]
        v.validators[0].iter_errors.return_value = [mock_error1, mock_error2]
        element = ({"foo": "bar"}, {"foo": "bar"})
        results = list(v.process(element))
        self.assertEqual(len(results), 1)
        tagged = results[0]
        self.assertEqual(tagged.tag, "error")
        self.assertEqual(tagged.value["reason"], "foo error1 bar error2")

    def test_process_without_errors(self):
        v = ValidateData("IN", "myschema", self.mock_jsonvalidator)
        v.validators = [MagicMock()]
        v.validators[0].iter_errors.return_value = []
        element = ({"foo": "bar"}, {"foo": "bar"})
        results = list(v.process(element))
        self.assertEqual(results, [element[0]])

    def test_process_with_error_objects(self):
        v = ValidateData("IN", "myschema", self.mock_jsonvalidator)
        v.validators = [MagicMock()]
        mock_error1 = MagicMock()
        mock_error1.message = "missing field"
        mock_error1.path = ["foo"]
        mock_error2 = MagicMock()
        mock_error2.message = "invalid value"
        mock_error2.path = ["bar"]
        v.validators[0].iter_errors.return_value = [mock_error1, mock_error2]
        element = ({"foo": "bar"}, {"foo": "bar"})
        results = list(v.process(element))
        self.assertEqual(len(results), 1)
        tagged = results[0]
        self.assertEqual(tagged.tag, "error")
        self.assertEqual(tagged.value["reason"], "foo missing field bar invalid value")
        self.assertIn("reason", tagged.value)

    def test_process_with_one_error_object(self):
        v = ValidateData("IN", "myschema", self.mock_jsonvalidator)
        v.validators = [MagicMock()]
        mock_error = MagicMock()
        mock_error.message = "only one error"
        mock_error.path = ["foo"]
        v.validators[0].iter_errors.return_value = [mock_error]
        element = ({"foo": "bar"}, {"foo": "bar"})
        results = list(v.process(element))
        self.assertEqual(len(results), 1)
        tagged = results[0]
        self.assertEqual(tagged.tag, "error")
        self.assertEqual(tagged.value["reason"], "foo only one error")

    def test_process_does_not_mutate_input_on_success(self):
        v = ValidateData("IN", "myschema", self.mock_jsonvalidator)
        v.validators = [MagicMock()]
        v.validators[0].iter_errors.return_value = []
        element = ({"foo": "bar"}, {"foo": "bar"})
        orig = element[0].copy()
        list(v.process(element))
        self.assertEqual(element[0], orig)

    def test_process_with_none_schema_name_and_error(self):
        v = ValidateData("IN", None, self.mock_jsonvalidator)
        element = ({"foo": "bar"}, {"foo": "bar"})
        results = list(v.process(element))
        self.assertEqual(results, [element[0]])

    def test_process_error_message_is_string(self):
        v = ValidateData("IN", "myschema", self.mock_jsonvalidator)
        v.validators = [MagicMock()]
        mock_error1 = MagicMock()
        mock_error1.message = "error1"
        mock_error1.path = ["foo"]
        mock_error2 = MagicMock()
        mock_error2.message = "error2"
        mock_error2.path = ["bar"]
        v.validators[0].iter_errors.return_value = [mock_error1, mock_error2]
        element = ({"foo": "bar"}, {"foo": "bar"})
        results = list(v.process(element))
        tagged = results[0]
        self.assertIsInstance(tagged.value["reason"], str)
        self.assertEqual(tagged.value["reason"], "foo error1 bar error2")

if __name__ == '__main__':
    unittest.main()