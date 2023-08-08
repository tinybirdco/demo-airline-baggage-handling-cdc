import importlib
import sys
import os

# Add the parent directory to the path so that we can import the conf module without fuss
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            conf_module = importlib.import_module("conf")
            for attr_name in dir(conf_module):
                if not attr_name.startswith("__"):  # Filter out built-in attributes
                    setattr(cls._instance, attr_name, getattr(conf_module, attr_name))
        
        # Set any derived attributes
        cls._instance.TB_BASE_URL = f"https://{cls._instance.TINYBIRD_API_URI}.tinybird.co/v0/"
        cls._instance.CFLT_BASE_URL = "https://api.confluent.cloud/"
        # The Kafka Topic Name is generated by the Debezium connector using a fixed structure.
        # See https://docs.confluent.io/cloud/current/connectors/cc-postgresql-cdc-source-debezium.html
        cls._instance.PG_KAFKA_CDC_TOPIC = f"{cls._instance.PG_DATABASE}.public.{cls._instance.USERS_TABLE_NAME}"
        # The Kafka Topic Name is generated by the Debezium connector using a fixed structure.
        # See https://docs.confluent.io/cloud/current/connectors/cc-mysql-source-cdc-debezium.html
        # Note that the documentation says 'schemaName' but that is actually just the database name in these configurations.
        cls._instance.MYSQL_KAFKA_CDC_TOPIC = f"{cls._instance.MYSQL_DB_NAME}.{cls._instance.MYSQL_DB_NAME}.{cls._instance.USERS_TABLE_NAME}"

        # Set any static values
        cls._instance.SLEEP_WAIT = 1
        cls._instance.TIMEOUT_WAIT = 15

        return cls._instance

def bool_to_int(row):
    """Converts boolean values in a row to integers."""
    return {k: int(v) if isinstance(v, bool) else v for k, v in row.items()}
