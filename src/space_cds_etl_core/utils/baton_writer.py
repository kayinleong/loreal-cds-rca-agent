import apache_beam as beam
from google.cloud import storage
import json

class BatonFileWriter(beam.DoFn):
    def __init__(self, df_args):
        self.df_args = df_args

    def process(self, element):

        bucket_name = self.df_args['baton_file_bucket']
        file_path = self.df_args['next_df_params']['job_name'] + ".json"

        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)

        blob.upload_from_string(
            json.dumps({
                "market_code": self.df_args['job_name'].split("-")[0].lower(),
                "loadtype": self.df_args['job_name'].split("-")[4].lower(),
                "frequency": self.df_args['job_name'].split("-")[-2].lower(),
                "sp_name": self.df_args['next_df_params']['sp_name'],
                "dependent_tables": self.df_args['next_df_params']['dependent_tables']
            }),
            content_type='application/json'
        )

        yield f"Baton file created: gs://{bucket_name}/{file_path}"
