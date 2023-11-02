"""
Main script to initialize logger and server
"""

import uvicorn
from fastapi import FastAPI, status, Response, Depends, HTTPException
from fastapi.responses import StreamingResponse
from influxdb_client import InfluxDBClient
from starlette.middleware.cors import CORSMiddleware
from app.helpers.config_helper import props
from app.routers.data import router1 as storeresponse
from app.routers.data import router2 as getdata
from app.routers.data import router3 as socketextract
from app.routers.data import router4 as sample
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from app.helpers.db_helper import init_database_connection


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



@app.on_event('startup')
def startup_event():
    init_database_connection()


@app.get('/healthcheck', status_code=status.HTTP_200_OK)
def perform_healthcheck():
    return {'healthcheck': 'Everything OK!'}


app.include_router(storeresponse)

app.include_router(getdata)

app.include_router(socketextract)

app.include_router(sample)


if __name__ == "__main__":
    # Read server connection details
    host = props.get_properties("connection", "host")
    port = props.get_properties("connection", "port")

    uvicorn.run(app, host=host, port=int(port))
