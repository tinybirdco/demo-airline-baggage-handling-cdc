# cc_functions.py

from confluent_kafka.admin import AdminClient
import requests

CFLT_BASE_URL = "https://api.confluent.cloud/"

# Sensitive information in external file to avoid Git tracking
import conf

# Simple cache for discovered identities
cache = {}

def environment_list():
    print("Listing Confluent Cloud Environments...")
    resp = requests.get(
        CFLT_BASE_URL + "org/v2/environments",
        auth=(conf.CONFLUENT_CLOUD_KEY, conf.CONFLUENT_CLOUD_SECRET)
    )
    resp.raise_for_status()
    return resp.json()['data']

def environment_get(env_name):
    print(f"Getting Confluent Cloud Environment with name {env_name}...")
    envs = environment_list()
    for env in envs:
        if env['display_name'] == env_name:
            return env
    return None

def cluster_list(env_name):
    env_id = cache_cflt_env_id(env_name)
    print("Listing Confluent Cloud Clusters...")
    resp = requests.get(
        CFLT_BASE_URL + f"cmk/v2/clusters?environment={env_id}",
        auth=(conf.CONFLUENT_CLOUD_KEY, conf.CONFLUENT_CLOUD_SECRET)
    )
    resp.raise_for_status()
    return resp.json()['data']

def cluster_get(cluster_name, env_name):
    print(f"Getting Confluent Cloud Cluster with name {cluster_name}...")
    clusters = cluster_list(env_name)
    for cluster in clusters:
        if cluster['spec']['display_name'] == cluster_name:
            return cluster
    return None

def cache_cflt_env_id(env_name):
    if 'clft_env_id' in cache and cache['clft_env_id'] is not None:
        return cache['clft_env_id']
    environment = environment_get(env_name)
    if not environment:
        raise Exception(f"Environment {env_name} not found.")
    cache['clft_env_id'] = environment['id']
    return environment['id']

def cache_cflt_cluster_id(cluster_name, env_name):
    if 'clft_cluster_id' in cache and cache['clft_cluster_id'] is not None:
        return cache['clft_cluster_id']
    cluster = cflt_cluster_get(cluster_name=cluster_name, env_name=env_name)
    if not cluster:
        raise Exception(f"Cluster {cluster_name} not found.")
    cache['clft_cluster_id'] = cluster['id']
    return cluster['id']

def connector_list(cluster_name, env_name):
    print(f"Listing Confluent Cloud Connectors for Cluster {cluster_name}...")
    env_id = cache_cflt_env_id(env_name)
    cluster_id = cache_cflt_cluster_id(cluster_name=cluster_name, env_name=env_name)
    resp = requests.get(
        CFLT_BASE_URL + f"connect/v1/environments/{env_id}/clusters/{cluster_id}/connectors",
        auth=(conf.CONFLUENT_CLOUD_KEY, conf.CONFLUENT_CLOUD_SECRET)
    )
    resp.raise_for_status()
    return resp.json()

def connector_delete(name, env_name, cluster_name):
    if name not in connector_list(cluster_name=cluster_name, env_name=env_name):
        print(f"Confluent Cloud Debezium Connector with name {name} not found.")
        return
    print(f"Deleting Confluent Cloud Debezium Connector with name {name}...")
    env_id = cache_cflt_env_id(env_name)
    cluster_id = cache_cflt_cluster_id(cluster_name=cluster_name, env_name=env_name)
    resp = requests.delete(
        CFLT_BASE_URL + f"connect/v1/environments/{env_id}/clusters/{cluster_id}/connectors/{name}",
        auth=(conf.CONFLUENT_CLOUD_KEY, conf.CONFLUENT_CLOUD_SECRET)
    )
    resp.raise_for_status()
    print(f"Deleted Confluent Cloud Connector with name {name}")

def connector_create(name, source_db, env_name, cluster_name):
    # The API response for this call can be obtuse, sending 500 for minor misconfigurations.
    # Therefore change carefully and test thoroughly.
    if name in connector_list(cluster_name=cluster_name, env_name=env_name):
        print(f"Confluent Cloud Debezium Connector with name {name} already exists.")
        return
    print(f"Creating Confluent Cloud Debezium Connector with name {name}...")
    env_id = cache_cflt_env_id(env_name)
    cluster_id = cache_cflt_cluster_id(cluster_name=cluster_name, env_name=env_name)

    base_config = {
        "name": name,
        "kafka.auth.mode": "KAFKA_API_KEY",
        "kafka.api.key": conf.CONFLUENT_UNAME,
        "kafka.api.secret": conf.CONFLUENT_SECRET,
        "tasks.max": "1",
        "output.data.format": "JSON",
        "output.key.format": "JSON",
        "cleanup.policy": "delete"
    }
    mysql_config = {
        "connector.class": "MySqlCdcSource",
        "database.hostname": conf.MYSQL_HOST_URL,
        "database.port": str(conf.MYSQL_PORT),
        "database.user": conf.MYSQL_USERNAME,
        "database.password": conf.MYSQL_PASSWORD,
        "database.server.name": conf.MYSQL_DB_NAME,
        "database.whitelist": conf.MYSQL_DB_NAME,
        "table.include.list": '.'.join([conf.MYSQL_DB_NAME, conf.USERS_TABLE_NAME]),
        "database.include.list": "mysql_cdc_demo",
        "snapshot.mode": "when_needed",
        "database.ssl.mode": "preferred"
    }
    pg_config = {
        "connector.class": "PostgresCdcSource",
        "database.hostname": conf.PG_HOST_URL,  # This is the RDS endpoint
        "database.port": str(conf.PG_PORT),
        "database.user": conf.PG_USERNAME,
        "database.password": conf.PG_PASSWORD,
        "database.dbname": conf.PG_DATABASE,
        "database.server.name": conf.PG_DATABASE,  # This is a logical name used for Confluent topics
        "database.sslmode": "require",
        "table.include.list":f"public.{conf.USERS_TABLE_NAME}", 
        "plugin.name": "pgoutput",
        "snapshot.mode": "exported"
    }
    if source_db == 'MYSQL':
        config_sub = {**base_config, **mysql_config}
    elif source_db == 'PG':
        config_sub = {**base_config, **pg_config}
    else:
        raise Exception(f"Invalid source_db: {source_db}")
    json_sub = {
            "name": name,
            "config": config_sub
        }
    # print(f"Using config: {json_sub}")  # Prints full config for debugging. Contains security info.
    resp = requests.post(
        CFLT_BASE_URL + f"connect/v1/environments/{env_id}/clusters/{cluster_id}/connectors",
        headers={'Content-Type': 'application/json'},
        auth=(conf.CONFLUENT_CLOUD_KEY, conf.CONFLUENT_CLOUD_SECRET),
        json=json_sub
    )
    resp.raise_for_status()
    print(f"Created Confluent Cloud Connector with name {name}")


def k_connect_kadmin():
    print("Connecting to Confluent Cloud Kafka with Admin Client...")
    return AdminClient({
        'bootstrap.servers': conf.CONFLUENT_BOOTSTRAP_SERVERS,
        'sasl.mechanisms': 'PLAIN',
        'security.protocol': 'SASL_SSL',
        'sasl.username': conf.CONFLUENT_UNAME,
        'sasl.password': conf.CONFLUENT_SECRET
    })

def k_topic_list():
    kadmin = k_connect_kadmin()
    topics_metadata = kadmin.list_topics(timeout=5)
    if not topics_metadata:
        raise Exception("No topics found.")
    print(f"Found {len(topics_metadata.topics)} Kafka topics.")
    return topics_metadata.topics

def k_topic_delete(topic_name):
    if topic_name not in k_topic_list():
        print(f"Kafka topic {topic_name} not found.")
        return
    print(f"Deleting Kafka topic {topic_name}...")
    kadmin = k_connect_kadmin()
    kadmin.delete_topics([topic_name])
    print(f"Deleted Kafka topic {topic_name}.")