import unittest
from unittest.mock import patch, MagicMock
import apache_beam as beam
from apache_beam.testing.test_pipeline import TestPipeline as BeamTestPipeline
from apache_beam.testing.util import assert_that, equal_to
from space_cds_etl_core.utils.writeinvalid import get_values, WriteInvalidData
import warnings

class TestWriteInvalidData(unittest.TestCase):
    def test_get_values(self):
        data = {"a": 1, "b": 2}
        result = get_values(data, delimiter=",")
        self.assertEqual(result, "1,2")
        result2 = get_values(data)
        self.assertEqual(result2, "1|2")

    @patch("space_cds_etl_core.utils.writeinvalid.FileSystems.create")
    def test_write_file_with_content(self, mock_create):
        mock_file = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_file
        wid = WriteInvalidData("gs://bucket/error.csv", "|")
        result = wid._write_file(["a|b", "c|d"])
        mock_create.assert_called_once_with("gs://bucket/error.csv")
        mock_file.write.assert_called_once_with(b"a|b\nc|d")
        self.assertEqual(result, "files written to gs://bucket/error.csv")

    @patch("space_cds_etl_core.utils.writeinvalid.FileSystems.create")
    def test_write_file_no_content(self, mock_create):
        wid = WriteInvalidData("gs://bucket/error.csv", "|")
        result = wid._write_file(["", ""])
        mock_create.assert_not_called()
        self.assertEqual(result, "No content to write for gs://bucket/error.csv")

    @patch.object(WriteInvalidData, "_write_file", new=lambda self, x: "files written to test.csv")
    def test_expand(self):
        warnings.simplefilter("ignore")
        with BeamTestPipeline() as p:
            pcoll = p | beam.Create([{"a": 1, "b": 2}, {"a": 3, "b": 4}])
            result = pcoll | WriteInvalidData("test.csv", ",")
            assert_that(result, equal_to(["files written to test.csv"]))



if __name__ == "__main__":
    unittest.main()