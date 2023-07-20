"""
Main script to initialize logger and server
"""
import minio
import os
from minio import Minio
import uvicorn
import subprocess
from fastapi import FastAPI, status, Response, Depends, HTTPException
from fastapi.responses import StreamingResponse
from influxdb_client import InfluxDBClient
from starlette.middleware.cors import CORSMiddleware
import influxdb_client
from app.helpers.config_helper import props
from app.routers.user import router as user_router


__author__ = "Dinesh Sinnarasse"
__copyright__ = "Copyright 2023, Enterprise Minds"
__license__ = ""
__version__ = "1.0"
__maintainer__ = "Enterprise Minds"
__status__ = "Development"


def get_application() -> FastAPI:
    """
    Initialize the application server with logger
    :return: fastApi app
    """
    application = FastAPI(title="Anomaly-detection", debug=True)
    return application


app = get_application()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)

# Initialize MinIO client during startup and return it


minio_client = Minio('play.min.io',
                     'minioadmin', 'minioadmin', secure=Talse)  # Assuming you are using HTTP (non-secure) connection


def get_minio_client():
    print("ok")
    return minio_client


@app.on_event('startup')
def init_database_connection():
    """
    Mehtod to initiate DBConnection
    :return: database_object
    """
    try:
        connection_url = props.get_properties("database", "connection_url")
        db_name = props.get_properties("database", "db_name")
        client = InfluxDBClient(connection_url)
        return {"msg": "connected"}

    except Exception:
        raise Exception("Database connection error")
    return client


@app.get('/healthcheck', status_code=status.HTTP_200_OK)
def perform_healthcheck():
    return {'healthcheck': 'Everything OK!'}


@app.get('/insert', status_code=status.HTTP_200_OK)
def perform_insertdata():
    header1 = '#constant measurement,crow'
    header2 = '#datatype dateTime:2006-01-02,long,tag'
    command = f'D:/influxdb2-client-2.7.3-windows-amd64/influx write -b sample -o 51210a7db2211551 -t sQY1wYw3yDcRg35YExT3GD9PCn_EPZOBW5hlNIdq5vVbK4VG4mGdv4sEqU6PtPfiQwBa2AIt6cin0VlrX4jNxQ== -f D:\\Anomaly\\anomaly-detection\\example.csv --host http://localhost:8086 --header "{header1}" --header "{header2}"'
    subprocess.run(command, shell=True)
    return {'db': 'Everything OK!'}


@app.get("/start/{bucket_name}/{object_name}")
async def get_csv_from_minio(bucket_name: str, object_name: str, minio_client: Minio = Depends(get_minio_client)):
    # Save the file in the same name as the object with '.csv' extension
    local_file_path = f"{object_name}.csv"

    try:
        # Use the MinIO client to get the object
        chunk_size = 512 * 1024  # 512 KB chunk size
        with open(local_file_path, 'wb') as csvfile:
            data = minio_client.get_object(bucket_name, object_name)
            for line in data.stream(chunk_size):
                csvfile.write(line)

        return {"message": "CSV file retrieved successfully and saved locally."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Read server connection details
    host = props.get_properties("connection", "host")
    port = props.get_properties("connection", "port")

    uvicorn.run(app, host=host, port=int(port))
