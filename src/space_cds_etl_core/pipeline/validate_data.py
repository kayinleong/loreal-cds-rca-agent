from apache_beam import DoFn, pvalue
from space_cds_etl_core.utils.logger import CloudLogger
logger = CloudLogger().get_logger()

class ValidateData(DoFn):
    def __init__(self, country, schema_name, jsonvalidators):
        super().__init__()
        self.default_country = "default"
        self.country = country
        self.schema_name = schema_name
        self.jsonvalidators = jsonvalidators
        self.validators = []  # Will hold compiled validator objects

    def setup(self):
        logger.info("Setting up JsonValidator for country: %s, schema: %s", self.country, self.schema_name)
        if self.schema_name:
            logger.info(f"Setting up validators for schema: {self.schema_name}")
            for jsonvalidator in self.jsonvalidators:
                validator = jsonvalidator.validate_data()
                self.validators.append(validator)

    def process(self, element):
        errors = []
        stg_element, mapped_element = element
        # logger.info(f"mapped data: {mapped_element}")
        if self.schema_name:
            for validator in self.validators:
                errors.extend(list(validator.iter_errors(mapped_element)))
        stg_element.pop('operation', None)
        if errors:
            error_messages = []
            for error in errors:
                field = list(error.path)[-1] if error.path else ''
                error_messages.append(f'{field} {error.message}')
            stg_element["reason"] = " ".join(error_messages)
            yield pvalue.TaggedOutput("error", stg_element)
        else:
            yield stg_element
