import apache_beam as beam
from apache_beam.io.filesystems import FileSystems
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()

class WriteToGCS(beam.DoFn):
    def __init__(self, output_path):
        self.output_path = output_path

    def process(self, elements):
        # elements is a list of (line, header, filename)
        logger.info(f"Processing {len(elements) if elements else 0} error records to {self.output_path}")
        logger.info(f"elements type is {type(elements)}")
        if not elements:
            yield f"No errors to write to {self.output_path}"
            return
        lines = [line for line, _, _ in elements]
        content = "\n".join(lines)
        if content:
            with FileSystems.create(self.output_path) as f:
                f.write(content.encode('utf-8'))
            logger.info(f"Wrote {len(lines)} error records to {self.output_path}")
            yield f"Wrote errors to {self.output_path}"

