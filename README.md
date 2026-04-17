# Dataflow Pipeline with Apache Beam & Poetry

This repository contains an **Apache Beam Dataflow pipeline** that processes JSON files from **Google Cloud Storage (GCS)**, validates and transforms them using **JSON Schema and YAML-based configurations**, and loads them into **Cloud SQL**.

## 🚀 Features

- **Configurable**: Define transformations per source using a YAML config.
- **Validation**: Enforces data rules with JSON Schema.
- **Scalable**: Easily add new sources without modifying the core code.
- **Uses Poetry**: For dependency management and packaging.

---

## 🛠️ Installation

### 1️⃣ **Install Poetry**

If you haven't installed **Poetry**, run:

```sh
curl -sSL https://install.python-poetry.org | python3 -
```

### 2️⃣ **Install Dependencies**

Run the following command to install OR update dependencies:

```sh
poetry install --no-root
```
It will update the poetry.lock file which needs to be versioned

---

## ⚙️ Configuration

The project has to have a GCS bucket to store the settings:
- config.yaml and datasets
- 
### Example Directory Structure in GCS
```
gs://your-config-bucket/
├── config.yaml
├── datasets/
│   ├── AU/
│   │   ├── MARS/
│   │   │   ├── addresses.yaml
│   ├── SG/
│       ├── SAP/
│           ├── product.yaml
```

### Required Parameters

- **`--input_path`**: The GCS path to the input data.
- **`--config_gcs_path`**: The GCS path to the `config.yaml` file containing environment-specific configurations.
- **`--market_code`**: A 2-character ISO market code (e.g., `SG`, `AU`).
- **`--source_system_name`**: The name of the source system (e.g., `SAP`, `MARS`).
- **`--db_mapping_config`**: configuration file for databases based on market_code (e.g., `AU`, `SG`).
- **`--environment`**: Environment where job will be running (e.g., `dv`, `pd`).



## `config.yaml` File configuration

The following configuration parameters are used in the project:

### Database Configuration

Databases are now defined under each environment in the `config.yaml` file. For example:

```yaml
environments:
  dv:
    databases:
      sg_db: "sg_db_dv"
      anz_db: "anz_db_dv"
```

The pipeline dynamically selects the appropriate database based on the environment and the market code provided.

#### Allowed environments
- dv
- qa
- np
- pd

## `dataset` configuration 

- **`table_name`**: Specifies the name of the target table in the database. Used in `writer.py`.
- **`transformations`**: A dictionary containing transformation rules Used in `transformer.py`.
- **`where_conditions`**: A dictionary containing transformation rules Used in `writer.py`.

For a market ISO code `AU` and source system name `MARS`, the configuration file should be located at:

```
config/datasets/AU/MARS/address.yaml
```

Each combination of `market_iso_code` and `source_system_name` can have multiple files to define the specific transformations, validation rules, and target Cloud SQL (PostgreSQL) for each table.

### Example of full Configuration

Below is an example of how these parameters might look in a configuration file:

```yaml
table_name: "target_table_name"
primary_key: "email"
operation: 'update'
where_conditions:
  - field: "status"
    operator: "="
    value: "active"
transformations:
  rename_fields:
    old_field: new_field
  uppercase_fields: ["field1", "field2"]
  lowercase_fields: ["field3"]
  type_conversion:
    field4: "int"
    field5: "float"
  format:
    date_field: "%Y-%m-%d"
  timezone_conversion:
    timestamp_field:
      source_timezone: "Asia/Singapore"
  concat_fields:
    new_field:
      fields: ["field6", "field7"]
      separator: "-"
  default_values:
    field8: "default_value"
```

Each source has a YAML file defining:

- **Table name**
- **Operation**
- **Primary key**
- **Field transformations** (rename, concatenate, uppercase, lowercase, format, etc.)
- **Where conditions**

### Configuration: operation

The `operation` field in the configuration specifies the type of database operation to perform. Supported operations are insert / upsert / update

#### 1️⃣ **Insert**
- Inserts new rows into the database.
- If a row with the same primary key already exists, the operation will fail unless handled by the database.

##### Example Configuration
```yaml
operation: "insert"
```

##### Behavior
For the following input:
```json
{
  "id": 1,
  "name": "John Doe",
  "status": "active"
}
```

The generated SQL query will be:
```sql
INSERT INTO table_name (id, name, status) VALUES (%s, %s, %s)
```

---

#### 2️⃣ **Update**
- Updates existing rows in the database.
- Requires the `primary_key` field to be specified in the configuration.
- If the row does not exist, the operation will fail.

##### Example Configuration
```yaml
operation: "update"
primary_key: "id"
```

##### Behavior
For the following input:
```json
{
  "id": 1,
  "name": "John Doe",
  "status": "inactive"
}
```

The generated SQL query will be:
```sql
UPDATE table_name SET name = %s, status = %s WHERE id = %s
```

---

#### 3️⃣ **Upsert**
- Inserts new rows or updates existing rows if they already exist.
- Requires the `primary_key` field to be specified in the configuration.

#### Example Configuration
```yaml
operation: "upsert"
primary_key: "id"
```

##### Behavior
For the following input:
```json
{
  "id": 1,
  "name": "John Doe",
  "status": "active"
}
```

The generated SQL query will be:
```sql
INSERT INTO table_name (id, name, status) VALUES (%s, %s, %s)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, status = EXCLUDED.status
```

---

#### Notes
- **`primary_key`**: This field is mandatory for `update` and `upsert` operations.
- **Default Operation**: If the `operation` field is not specified, the pipeline defaults to `insert`.

### Configuration: where_conditions

The `where_conditions` field in the configuration allows you to define dynamic filtering logic for database operations. This is used to build the `WHERE` clause in SQL queries.

### Where condition
```yaml
where_conditions:
  - field: "status"
    operator: "="
    value: "active"
  - field: "created_at"
    operator: ">"
    value: "2023-01-01"
```

### Explanation
- **field**: The database column to filter on.
- **operator**: The SQL operator to use (e.g., `=`, `>`, `<`, `LIKE`, etc.).
- **value**: The value to compare against.

### Generated SQL
For the above configuration, the following `WHERE` clause will be generated:
```sql
WHERE status = %s AND created_at > %s
```
The corresponding values (`"active"` and `"2023-01-01"`) will be passed as query parameters to prevent SQL injection.


### Timezone Conversion

The pipeline supports converting datetime fields from a source timezone to UTC. The output will always be in Zulu format (`YYYY-MM-DDTHH:MM:SSZ`). This is configured in the `timezone_conversion` section of the YAML file.

#### Example Configuration

```yaml
transformations:
  timezone_conversion:
    timestamp_field:
      source_timezone: "Asia/Singapore"
```

#### Behavior

- The `timestamp_field` will be converted from the `Asia/Singapore` timezone to UTC.
- The output will always be in the Zulu format `YYYY-MM-DDTHH:MM:SSZ`.


### Error Handling

- If the `config.yaml` file is missing or invalid, the pipeline will raise an error.
- If the `input_path` or `config_gcs_path` is not provided, the pipeline will raise a `ValueError`.
- If the GCS bucket or folder is incorrect, the pipeline will raise a `RuntimeError`.
- **Error Logs**: Records that fail validation or transformation will be logged into a separate GCS path for debugging purposes.

### Example Error Logs

Failed records will be written to a GCS path specified in the configuration (e.g., `gs://your-bucket/errors/`). Each log entry will include:

- The original record
- The error message
- The transformation or validation step that failed

Example log format:

```json
{
  "record": {
    "name": "John Doe",
    "email": "invalid-email"
  },
  "error": "Invalid email format",
  "step": "Validation"
}
```
---

## 🚀 Running the Pipeline

### Local Execution

```sh
poetry run python src/main.py \
  --input_path gs://your-bucket/source1/*.json \
  --market_code AU \
  --source_system_name SAP \
  --config_gcs_path gs://your-config-bucket/config.yaml \
  --datasets_gcs_path gs://your-config-bucket/datasets \
  --datasets_filename config.yaml
```

### Running on Google Dataflow

```sh
poetry run python src/main.py \
  --input_path gs://your-bucket/source1/*.json \
  --market_code AU \
  --source_system_name SAP \
  --config_gcs_path gs://your-config-bucket/config.yaml \
  --runner DataflowRunner \
  --project your-gcp-project \
  --region asia-southeast1 \
  --temp_location gs://your-temp-bucket/tmp/ \
  --error_output_path gs://your-bucket/errors/
```
---

## 📂 Folder Structure

```
├── src/
│   ├── config.yaml                # Environment-specific configurations
│   ├── main.py                    # Entry point for the pipeline
│   ├── utils/
│   │   ├── db_connector.py        # Database connection management
│   │   ├── ...other utility files...
│   ├── pipeline/
│   │   ├── reader.py              # Reads data from GCS
│   │   ├── transformer.py         # Transformation logic
│   │   ├── validator.py           # JSON Schema validation
│   │   ├── writer.py              # Writes data to Cloud SQL
│   │   ├── ...other pipeline components...
│
├── pyproject.toml                 # Poetry configuration
├── README.md                      # Documentation
├── tests/                         # Unit tests for the pipeline
│   ├── test_reader.py             # Tests for the reader module
│   ├── test_transformer.py        # Tests for the transformer module
│   ├── ...other test files...
```

---

## 🛠️ Common Commands

### Activate Poetry Virtual Environment

```sh
poetry shell
```

### Add a New Dependency

```sh
poetry add package_name
```

### Export Dependencies for Deployment

```sh
poetry export -f requirements.txt --without-hashes -o requirements.txt
```

### Run Tests

```sh
poetry run pytest
```

---

## 🧪 Running Unit Tests

Unit tests are included to validate the functionality of the pipeline. To run the tests, use the following command:

```sh
poetry run pytest tests/
```

### Test Coverage

The tests cover:

- Field renaming
- Case conversion (uppercase/lowercase)
- Type conversions (e.g., string to int/float)
- Date formatting
- Timezone conversion
- Field concatenation
- Default value assignment

---

## 📝 Notes

- Ensure **Google Cloud credentials** are configured for Dataflow:
  ```sh
  gcloud auth application-default login
  ```
- Ensure the `config.yaml` and `datasets` directory are accessible in the specified GCS bucket.
- Ensure the `--datasets_filename` allows you to specify different configuration files for different datasets.
- Ensure that the `--market_code` is exactly 2 characters (e.g., `US`, `AU`).
- The `--source_system_name` must be alphabetic (e.g., `SAP`, `MARS`).
- Failed records are logged to the path specified by `--error_output_path` for debugging.
- Modify `config/datasets/sourceX.yaml` to add **new transformations** without modifying the code.
- If adding a new source, create a new YAML config inside `config/datasets/`.

---

