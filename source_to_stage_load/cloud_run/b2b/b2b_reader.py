from core.reader import ReadFromGCS
from core.logger import Logger

logger = Logger(name="b2b batch").create_logger()

class B2BReader(ReadFromGCS):
    
    def get_file_header(self, reader):
        if not reader:
            logger.error("Reader is empty.")
            raise ValueError("reader object is not iterable.")
        if self.config.get("skip_header", False):
            _ = next(reader)  
        if self.config.get("no_header", True):
            header = list(self.config.get("field_mapping").keys())
            header = [h.strip() for h in header]
            return header
        header = [h.strip() for h in next(reader)]
        return header
    
    def zip_data(self, keys, values):

        skip_columns = list()
        if self.config.get("skip_columns", None):
            skip_columns = self.config.get("skip_columns")
            skip_columns = [s.strip() for s in skip_columns]
        result = {}
        for k,v in zip(keys, values):
            if k.strip() not in skip_columns:
                result[k] = v
        return result
    

    
        

