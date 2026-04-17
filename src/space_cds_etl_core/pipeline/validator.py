import requests
from jsonschema.validators import Draft202012Validator
from space_cds_etl_core.utils.constants import market_type_constants,GITHUB_TOKEN_SECRET_NAME
import jsonref
from space_cds_etl_core.utils.secret import get_secret
from collections import defaultdict
from space_cds_etl_core.utils.constants import schema_urls
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()

class JsonValidator:
    def __init__(
    self,
    country,
    market_type,
    df_args=None,
    schema_name=None,
    domain=None,
    config=None
    ):
        """
        Initialize the JsonValidator.

        Args:
            country (str): The country code.
            market_type (str): The market type (e.g., 'b2b', 'b2c').
            schema_name (str, optional): The name of the schema file. Defaults to None.
            domain (str, optional): The domain name. Defaults to None.
        """

        self.country = country
        self.df_args = df_args if df_args else {}
        self.market_type = market_type.lower()
        self.schema_name = schema_name if schema_name else None
        self.github_validation_rules_repo_url = market_type_constants[self.market_type]['GITHUB_REPO']
        self.domain = domain.lower() if domain else None
        if config is None:
            config = {}
        self.schema_mapping = config.get("schema_mapping", {})
        self.flat_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": True,
        }
        self.job_type = self.df_args.get('job_type','int').lower()


    def get_github_headers(self):
        """
        Retrieve the GitHub API headers with authentication token.

        Returns:
            dict: Headers for GitHub API requests.
        """
        token = get_secret(GITHUB_TOKEN_SECRET_NAME)
        headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3.raw"
        }
        return headers
    
    def resolve_schema(self, schema_url):
        """
        Resolve and dereference a JSON schema from a GitHub URL, including $ref references.

        Args:
            schema_url (str): The URL to the JSON schema on GitHub.

        Returns:
            dict: The dereferenced JSON schema.
        """
        headers = self.get_github_headers()
        def github_loader(uri):
            logger.debug(f"Resolving $ref: {uri}")
            resp = requests.get(uri, headers=headers)
            resp.raise_for_status()
            return resp.json()
        
        response = requests.get(schema_url, headers=headers)
        response.raise_for_status()
        schema = response.json()
        return jsonref.replace_refs(schema, base_uri=schema_url, loader=github_loader)
    
    def get_schema_from_github(self, country, schema_url):
        """
        Fetch the JSON schema from GitHub for the specified country, domain, and schema name.
        Falls back to the default schema if the country-specific schema is not found.

        Returns:
            dict: The dereferenced JSON schema.
        Raises:
            ValueError: If schema_name is not provided.
            HTTPError: If the schema cannot be fetched due to HTTP errors.
            RequestException: For other request-related errors.
        """
        if not self.schema_name:
            raise ValueError("The 'schema_name' parameter must be provided to fetch the schema.")
        try:
            source = self.df_args.get('source_system_name').lower()
            schema_url = self.format_string(schema_url, country=country, domain=self.domain, schema_name=self.schema_name, source=source)
            logger.info(f"Fetching schema from URL: {schema_url}")
            return self.resolve_schema(schema_url)
        except Exception:
            logger.warning("No DQ json defined for this file")
            return None



    def flatten_schema(self, schema):
        """
        Flatten a nested JSON schema into a single-level schema with all properties and required fields.

        Args:
            schema (dict): The original (possibly nested) JSON schema.

        Returns:
            dict: The flattened JSON schema.
        """
        if not schema:
            return self.flat_schema
        self._recurse_schema(schema)
        return self.flat_schema

    def _handle_property(self, key, value):
        """
        Handle a property in the schema, adding it to the flat schema.

        Args:
            key (str): The property name.
            value (dict): The property schema definition.
        """
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
        """
        Add required fields from a subschema to the flat schema's required list.

        Args:
            subschema (dict): The subschema containing 'required' fields.
        """
        for r in subschema.get("required", []):
            self.flat_schema["required"].append(r)

    def _recurse_schema(self, subschema):
        """
        Recursively process a subschema to flatten its properties and required fields.

        Args:
            subschema (dict): The subschema to process.
        """
        if subschema.get("type") == "object" and "properties" in subschema:
            for key, value in subschema["properties"].items():
                if isinstance(value, dict):
                    self._handle_property(key, value)
            self._handle_required(subschema)
        for keyword in ("allOf", "oneOf", "anyOf"):
            if keyword in subschema:
                self.flat_schema[keyword] = self.flat_schema.get(keyword, [])
                self.flat_schema[keyword].extend(subschema[keyword])
    
    def merge_schemas(self):
        """
        Merges the default schema with the country-specific schema, giving precedence to the country-specific schema.

        Returns:
            dict: The merged flattened schema.
        """
        
        urls = schema_urls.get(self.job_type).get(self.market_type)
        merged_flattened_schema = {}
        for url in urls:
            schema = self.get_schema_from_github(self.country.lower(), url)
            flattened_schema = self.flatten_schema(schema)
            logger.info(f"Fetched schema from URL {url}: {flattened_schema}")
        
        merged_flattened_schema = self.flat_schema
        return merged_flattened_schema

    
    def validate_data(self):
        """
        Validates data against the flattened schema by returning a Draft202012Validator instance.

        Returns:
            Draft202012Validator: Validator for the flattened schema.
        """
        merged_flattened_schema = self.merge_schemas()
        validator = Draft202012Validator(merged_flattened_schema)
        return validator

    def format_string(self, template, **kwargs):
        return template.format_map(defaultdict(lambda: '', **kwargs))
    

