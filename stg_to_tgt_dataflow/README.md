# stg_to_tgt_dataflow

This folder contains a Dataflow pipeline built with Apache Beam for ingesting data from stage to a database. The pipeline is designed to support flexible configuration and mapping for different markets and business types.

## Features

- Loads data from staging to target tables.
- Supports configurable database mapping and stored procedure execution.
- Handles multiple business types (`b2c`, `b2b`).
- Environment-aware configuration.

## Parameters

| Name            | Required | Default | Description                        | Options         |
|-----------------|----------|---------|------------------------------------|-----------------|
| `market_code`   | Yes      |         | Market code                        |                 |
| `db_mapping_path` | Yes    |         | Path to the DB mapping config file |                 |
| `table`         | Yes      |         | Target table name                  |                 |
| `sp_name`       | No       |         | Stored procedure name              |                 |
| `business_type` | No       | `b2c`   | Business type                      | `b2c`, `b2b`    |
| `env`           | No       | `dev`   | Environment                        |                 |

## Example Usage

```bash
python main.py \
  --market_code=US \
  --db_mapping_path=gs://bucket/config/db_mapping.json \
  --table=target_table \
  --sp_name=optional_sp \
  --business_type=b2c \
  --env=prod
```

## Deployment

This pipeline is packaged as a Dataflow Flex Template and can be deployed using Google Cloud Dataflow.

## License

See repository for license details.
