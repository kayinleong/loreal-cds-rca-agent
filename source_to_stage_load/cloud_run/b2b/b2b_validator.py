from core.validator import JsonValidator
from core.logger import Logger
import jsonref
import requests
from requests.exceptions import RequestException

logger = Logger(name="b2b validator").create_logger()

class B2BValidator(JsonValidator):
    def __init__(self,country,schema_name=None,domain='customer'):

        super().__init__(country,schema_name)
        self.github_validation_rules_repo_url = "https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2b-validation-rules/main"
        self.domain = domain.lower()

    def get_schema_from_github(self):
        """Downloads a schema file from GitHub with process-level caching."""
        if not self.schema_name:
            raise ValueError("The 'schema_name' parameter must be provided to fetch the schema.")
        schema_url = f"{self.github_validation_rules_repo_url}/resources/rules/{self.country.lower()}/{self.domain}/{self.schema_name}.json"
        token = self.fetch_secret("space_cds-srt-github_token")
        headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3.raw"
        }
        try:
            response = requests.get(schema_url,headers=headers)
            response.raise_for_status()
            schema = response.json()
            resolved_schema = jsonref.replace_refs(schema, base_uri=schema_url)
            return resolved_schema
        except Exception as e:
            schema_url = f"{self.github_validation_rules_repo_url}/resources/rules/default/{self.domain}/{self.schema_name}.json"
            logger.warning(f"Failed to fetch schema from GitHub: {e}. Trying default schema.")
            try:
                response = requests.get(schema_url,headers=headers)
                response.raise_for_status()
                schema = response.json()
                resolved_schema = jsonref.replace_refs(schema, base_uri=schema_url)
                return resolved_schema
            except RequestException as e:
                logger.error(f"Failed to fetch schema from GitHub: {e}")
                raise RequestException(f"Failed to fetch schema from GitHub: {e}") from e