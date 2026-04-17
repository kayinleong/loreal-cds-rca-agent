import requests
from jsonschema.validators import Draft202012Validator

import jsonref
from google.cloud import secretmanager
import google.auth
from requests.exceptions import RequestException
from core.logger import Logger

from datetime import datetime,timezone
logger = Logger(name = "batch log").create_logger()

class JsonValidator:
    def __init__(self,country,schema_name=None):

        self.country = country
        self.schema_name = schema_name
        self.github_validation_rules_repo_url = "https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2c-validation-rules/main"

    def get_schema_from_github(self):
        """Downloads a schema file from GitHub with process-level caching."""
        # right now we don't know which authentication technique to be used
        if not self.schema_name:
            raise ValueError("The 'schema_name' parameter must be provided to fetch the schema.")
        schema_url = f"{self.github_validation_rules_repo_url}/resources/rules/{self.country.lower()}/consumer/{self.schema_name}.json"
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
            schema_url = f"{self.github_validation_rules_repo_url}/resources/rules/default/consumer/{self.schema_name}.json"
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



    def flatten_schema(self, schema):
        self.flat_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": True,
        }
        self._recurse_schema(schema)
        return self.flat_schema

    def _handle_property(self, key, value):
        val_type = value.get("type")
        if val_type == "object":
            self._recurse_schema(value)
        elif val_type == "array":
            self._recurse_schema(value.get("items", {}))
        else:
            self.flat_schema["properties"][key] = {
                k: v for k, v in value.items() if k != "required"
            }

    def _handle_required(self, subschema):
        for r in subschema.get("required", []):
            self.flat_schema["required"].append(r)

    def _recurse_schema(self, subschema):
        if subschema.get("type") == "object" and "properties" in subschema:
            for key, value in subschema["properties"].items():
                if isinstance(value, dict):
                    self._handle_property(key, value)
            self._handle_required(subschema)

    def get_schema(self):
        """Fetches the schema from GitHub and flattens it."""
        if not self.schema_name:
            return None
        schema = self.get_schema_from_github()
        flattened_schema = self.flatten_schema(schema)
        return flattened_schema
    
    def validate_data(self,element,flattened_schema):
        """Validates data against the flattened schema."""
        validator = Draft202012Validator(flattened_schema)
        errors = list(validator.iter_errors(element))
        return errors
    
    def fetch_secret(self,secret_id):
        client = secretmanager.SecretManagerServiceClient()
        project_id = google.auth.default()[1]
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    def validate_data_quality(self,data,flattened_schema):
        """Validates data quality against the flattened schema."""
        error_data = list()

        valid_data = list()
        for row in data:
            if flattened_schema:
                errors = self.validate_data(row,flattened_schema)
            else:
                errors = list()
            if errors:
                for error in errors:
                    field_path = ".".join([str(x) for x in error.path]) or "root"
                    # logging.warning(f"Validation error in field '{field_path}': {error.message}")
                    row["validation_errors"] = f"{field_path} {error.message}"
                    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                    row["timestamp"] = f"{timestamp}"
                error_data.append(",".join("" if v is None else str(v) for v in row.values()))

                logger.warning(f"Validation error in row: {row}")
            else:
                valid_data.append(row)
        return error_data,valid_data

