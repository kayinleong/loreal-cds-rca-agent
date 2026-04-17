B2B_GITHUB_REPO = "https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2b-validation-rules/main"
B2C_GITHUB_REPO = "https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2c-validation-rules/main"
GITHUB_TOKEN_SECRET_NAME = "space_cds-srt-github_token"
B2B_DB_USERNAME_SECRET_NAME = "space_cds-srt-cloudsql_b2b_user"
B2B_DB_PASSWORD_SECRET_NAME = "space_cds-srt-cloudsql_b2b_pwd"
B2C_DB_USERNAME_SECRET_NAME = "space_cds-srt-cloudsql_b2c_user"
B2C_DB_PASSWORD_SECRET_NAME = "space_cds-srt-cloudsql_b2c_pwd"
INSTANCE_IP_SECRET_NAME = "space_cds-srt-cloudsql_instance_ip"

market_type_constants = {
    'INSTANCE_IP_SECRET_NAME': INSTANCE_IP_SECRET_NAME,
    'b2b': {
        'GITHUB_REPO': B2B_GITHUB_REPO,
        'DB_USERNAME_SECRET_NAME': B2B_DB_USERNAME_SECRET_NAME,
        'DB_PASSWORD_SECRET_NAME': B2B_DB_PASSWORD_SECRET_NAME
    },
    'b2c': {
        'GITHUB_REPO': B2C_GITHUB_REPO,
        'DB_USERNAME_SECRET_NAME': B2C_DB_USERNAME_SECRET_NAME,
        'DB_PASSWORD_SECRET_NAME': B2C_DB_PASSWORD_SECRET_NAME
    }
}

AUDIT_TABLE_NAME = {
    "b2b": "cds_stg.batch_audit_log",
    "b2c": "batch_audit_log"
}

STG_TO_TARGET_LOAD_FLAG = {
    "b2b": "stgtargetloadflag",
    "b2c": "stgtotargetloadflag"
}

GSUTIL_URI_PREFIX = "gs://"

TRUE_VALUES = ("true", "1", "yes", "True", "Yes", "TRUE", "YES", "Y")


schema_urls = {
'migr' : {
    'b2b': [
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2b-validation-rules/main/resources/rules/default/{domain}/{schema_name}',
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2b-validation-rules/main/resources/rules/{country}/{domain}/{schema_name}'
    ],

    'b2c': [
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2c-validation-rules/main/resources/rules/default/{domain}/{schema_name}',
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2c-validation-rules/main/resources/rules/{country}/{domain}/{schema_name}'
    ]
},

'int' : {
    'b2b': [
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2b-validation-rules/main/resources/rules/default/{domain}/{schema_name}',
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2b-validation-rules/main/resources/rules/{country}/{domain}/{schema_name}'
    ],

    'b2c': [
        'https://raw.githubusercontent.com/oa-nasapmena-crm/space-cds-b2c-validation-rules/main/resources/rules/integration/{country}/{source}/{schema_name}'
    ]

}
}

GENERIC_MOBILE_COUNTRY_CODE = "+611"