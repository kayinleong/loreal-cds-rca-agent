import apache_beam as beam
from apache_beam.io.filesystems import FileSystems
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()

def get_values(data, delimiter="|"):
    """
    Convert a dictionary to a delimited string.
    
    Args:
        data (dict): The input dictionary.
        delimiter (str): The delimiter to use for joining values.
        
    Returns:
        str: A string with values joined by the specified delimiter.
    """
    return f'{delimiter}'.join(str(value) for value in data.values())

class WriteInvalidData(beam.PTransform):
    def __init__(self, error_file,delimiter):
        super().__init__()
        self.error_file = error_file
        self.delimiter = delimiter
    
    def expand(self, pcoll):
        return (
            pcoll
            | "changing to csv" >> beam.Map(lambda data: get_values(data, delimiter=self.delimiter))
            | 'Gather All Elements' >> beam.combiners.ToList()
            | "Write data to GCS" >> beam.Map(self._write_file)
        )
    
    def _write_file(self, element):

        content = "\n".join(e for e in element if len(e) > 0)

        if content == "":
            return f"No content to write for {self.error_file}"

        with FileSystems.create(self.error_file) as f:
            f.write(content.encode('utf-8'))
        logger.info(f"Error Files written to {self.error_file}")
        return f"files written to {self.error_file}"