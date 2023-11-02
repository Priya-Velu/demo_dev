"""
Helper class to initialize DB connection
"""
from influxdb_client import InfluxDBClient
from app.helpers.config_helper import props



def init_database_connection():
    try:
        db_host = props.get_properties("database", "host")
        db_port = props.get_properties("database", "port")
        db_org = props.get_properties("database", "org")
        db_bucket = props.get_properties("database", "bucket")
        db_token = props.get_properties("database", "token")
        client = InfluxDBClient(
            url=f"http://{db_host}:{db_port}",
            token=db_token,
            org = db_org
        )
        connection = {
            "client": client,
            "db_bucket": db_bucket,
            "db_org": db_org
        }
        return client
    except Exception:
        raise Exception("Database connection error")



