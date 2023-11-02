from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from datetime import datetime
from app.helpers.log_helper import app
from app.helpers.db_helper import init_database_connection
from dotenv import load_dotenv
import pandas as pd 
from fastapi.responses import JSONResponse
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import timedelta
from app.helpers.config_helper import props
import csv
import asyncio
import socketio

import os

router1 = APIRouter()
router2 = APIRouter()
router3 = APIRouter()
router4 = APIRouter()



app.set_logger_name(__name__)

# Load environment variables from .env file
load_dotenv()

last_selected_interval = None
class FeedbackData(BaseModel):
    feedback: str
    time: datetime

@router1.post("/submit_feedback/{timestamp}/{feedback}/{command}")
def submit_feedback(timestamp:datetime, feedback:str, command:str):
    try:
        print(timestamp)
        time = timestamp.isoformat()[:-6]
        print(time)
        ftime = datetime.fromisoformat(time).isoformat() + ".000Z"

        print("Let's get started")
        # Create an InfluxDB client
        connection = init_database_connection()
        # Retrieve the db_bucket from the connection dictionary
        con = connection["client"]
        db_bucket = connection['db_bucket']
        org = connection['db_org']
        write_api = con.write_api(write_options=SYNCHRONOUS)
        print("Query Completed")
        measurement = "cpu_usage_cmd"
        cpu = "cpu"
        print(ftime,command,feedback)


        # Write feedback data to InfluxDB
        point = (
            Point(measurement)
            .field("Feedback", command)
            .tag("response", feedback)
            .time(ftime)
        )
        write_api.write(bucket=db_bucket, record=point)
        print("Feedback stored in Influxdb")

        return JSONResponse(content={"message": "Feedback stored successfully"})
    except Exception as e:
        return {"error": f"Error occurred: {str(e)}"}
        # return HTTPException(status_code=500, detail="Internal Server Error")



#CHANGING MEASUREMENT NAME AND

@router2.get("/newmethod/{time}/{selected_interval}")
def newmethod(time: str, selected_interval: str):
    try:
        # Initialize the InfluxDB client using the database connection function
        connection = init_database_connection()
        print(f"Received request: time={time} interval={selected_interval}")

        if selected_interval == "1 Min":
            aggregation = "1m"
            interval = "One_min"
        elif selected_interval == "5 Min":
            aggregation = "5m"
            interval = "Five_min"
        elif selected_interval == "15 Min":
            aggregation = "15m"
            interval = "Fifteen_min"
        else:
            aggregation = "1m"
            interval = "One_min"

         # Calculate start_time and end_time based on the time parameter
        if time == "Past 1 hour":
            end_time = datetime.now() - timedelta(minutes=2)
            start_time = end_time - timedelta(hours=1)
        elif time == "Past 3 hour":
            end_time = datetime.now() - timedelta(minutes=2)
            start_time = end_time - timedelta(hours=3)
        elif time == "Past 6 hour":
            end_time = datetime.now() - timedelta(minutes=2)
            start_time = end_time - timedelta(hours=6)
        else:
            return {"error": "Invalid time parameter"}

        start_time_rfc3339 = start_time.isoformat() + "Z"
        end_time_rfc3339 = end_time.isoformat() + "Z"

        # Retrieve the db_bucket from the connection dictionary
        # con = connection["client"]
        # db_bucket = connection['db_bucket']
        # org = connection['db_org']

        db_bucket = props.get_database_bucket()
        org = props.get_influx_org()
        measurement = props.get_database_measurement()
        measurement1 = props.get_database_measurement1()
        print(measurement, measurement1)

        # Remove milliseconds and add ".000Z" to match InfluxDB timestamp format
        start_time_rfc3339 = start_time.replace(microsecond=0).isoformat() + ".000Z"
        end_time_rfc3339 = end_time.replace(microsecond=0).isoformat() + ".000Z"

        # print(f"Received request: timeSchedule={time}, interval={selected_interval}")
        print("Process Started for whole data")
        print(start_time_rfc3339,end_time_rfc3339)

        # Construct the InfluxDB query
        query = (
            f'from(bucket: "{db_bucket}") '
            f'|> range(start: {start_time_rfc3339}, stop: {end_time_rfc3339}) '
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement}") '
            f'|> filter(fn: (r) => r["interval"] == "{interval}") '
            f'|> filter(fn: (r) => r["_field"] == "original" or r["_field"] == "outlier") '  # Filter for both original and outlier fields
            f'|> yield()'
        )

        # Execute the InfluxDB query
        result = connection.query_api().query(org=org, query=query)

        # Construct the InfluxDB query
        raw_query = (
            f'from(bucket: "{db_bucket}")'
            f'|> range(start: {start_time_rfc3339}, stop: {end_time_rfc3339})'
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement1}")'
            f'|> filter(fn: (r) => r["_field"] == "cpu")'
            f'|> yield()'
        )

        # Execute the InfluxDB query
        rawdata_result = connection.query_api().query(org=org, query=raw_query)
        print("Query executed for whole data")

        if not result:
            return {"error": "No data found for the query: " + query}

   
        data = {}
        i = 1
        # Process the result and merge data with the same timestamp
        for table in result:
            for record in table.records:
                timestamp = record["_time"]
                if timestamp not in data:
                    data[timestamp] = {"id": i, "_time": timestamp, "_value": None, "outlier": None, "outlier_point": None}
                    i += 1
                
                if record["_field"] == "original":
                    data[timestamp]["_value"] = record["_value"]
                elif record["_field"] == "outlier":
                    data[timestamp]["outlier"] = record["_value"]
                    if record["_value"] > 0:
                        data[timestamp]["outlier_point"] = data[timestamp]['_value']
                    else:
                        data[timestamp]["outlier_point"] = 0

        merged_data = list(data.values())        
        sorted_data = sorted(merged_data, key=lambda x: x["_time"])
        #print(sorted_data)


        answer = []
        top_processes_by_minute = {}

        for table in rawdata_result:
            for record in table.records:
                command_parts = record['command'].split('_')
                process_name = "_".join(command_parts[1:])
                data_point = {
                    'value': record['_value'],
                    'time': record['_time'],
                    'command': record['command'],
                    'process_name': process_name,
                    'process_id': command_parts[0]
                }
                answer.append(data_point)

        
    
        # Process data to find the top 5 processes for each minute
        for data_point in answer:
            timestamp = data_point['time']
            
            # Calculate the forward timestamp (round up to the next minute)
            minute = timestamp.replace(second=0).strftime('%Y-%m-%d %H:%M:%S+00:00')
            minute_key = minute.replace(" ","T")

            if minute_key not in top_processes_by_minute:
                top_processes_by_minute[minute_key] = []

            # Check if the process is already in the top processes list for this minute
            process_exists = False
            for existing_process in top_processes_by_minute[minute_key]:
                if existing_process['process_name'] == data_point['process_name']:
                    process_exists = True
                    if data_point['value'] > existing_process['value']:
                        existing_process.update(data_point)
                    break

            # If the process is not in the list or has a higher value, add it
            if not process_exists:
                top_processes_by_minute[minute_key].append(data_point)

            # Sort the top processes by value and keep only the top 5
            top_processes_by_minute[minute_key] = sorted(top_processes_by_minute[minute_key], key=lambda x: x['value'], reverse=True)[:5]

        # Sort the keys in chronological order
        top_data = dict(sorted(top_processes_by_minute.items()))

        for entry in sorted_data:
            time_ = entry["_time"]  
            time_key = datetime.isoformat(time_)
            if time_key in top_data:
                entry["top_5"] = top_data[time_key]
            else:
                print(f"No matching top_5 data for timestamp: {time_key}")

        response_data = {"data": sorted_data}
        print("Process Done for whole data")       
        return response_data
        
    except Exception as e:
        return {"error": f"Error occurred on Whole Data retrieval process: {str(e)}"}




current_websocket = None
current_task = None
current_sleepfor = 60  

@router3.websocket("/time/{time}/{option}")
async def websocket_endpoint(websocket: WebSocket, time: str, option: str):
    global current_websocket, current_task, current_sleepfor

    async def send_data():
        try:
            while True:
                # Sleep for the current_sleepfor value
                await asyncio.sleep(current_sleepfor)

                response_data = get_data_from_database(time, option)
                data = response_data['data']
                print(data)

                # Send the data to the WebSocket client
                await websocket.send_json(data)
                print(current_sleepfor, "Data sent to frontend")

                
        except WebSocketDisconnect:
            # Handle disconnect initiated by the client
            print("WebSocket connection closed by the client")
        except asyncio.CancelledError:
            # Task was canceled, likely due to a new connection
            pass
        except Exception as e:
            print("An error occurred:", e)
        finally:
            # Reset the current WebSocket and task
            if current_websocket == websocket:
                current_websocket = None
                current_task = None
            await websocket.close()

    # Accept the new WebSocket connection
    await websocket.accept()

    #await asyncio.sleep(30)

    # Determine the new sleep interval based on the option
    if option == "1 Min":
        new_sleepfor = 60
    elif option == "5 Min":
        new_sleepfor = 60 * 5
    elif option == "15 Min":
        new_sleepfor = 60 * 15
    

    # Check if a task is already running, and if the sleep interval has changed
    if current_task and current_sleepfor != new_sleepfor:
        # Cancel the existing task
        current_task.cancel()
        current_task = None

    # Update the current WebSocket and sleep interval
    current_websocket = websocket
    current_sleepfor = new_sleepfor

    # Start sending data with the updated sleep interval
    current_task = asyncio.create_task(send_data())









def get_data_from_database(time, selected_interval):
    try:
        connection = init_database_connection()
        print(f"Received request: time={time} interval={selected_interval}")

        if selected_interval == "1 Min":
            interval = "One_min"
        elif selected_interval == "5 Min":
            interval = "Five_min"
        elif selected_interval == "15 Min":
            interval = "Fifteen_min"
        else:
            interval = "One_min"

        
        # Calculate the start and end times for the past minute
        # Get the current time
        current_time = datetime.now()
        current_time_rounded = current_time.replace(second=0, microsecond=0)
        # start_time = current_time_rounded - timedelta(minutes=2)
        # end_time = current_time_rounded - timedelta(minutes=1)


        if selected_interval == "1 Min":
            start_time = current_time_rounded - timedelta(minutes=2)
            end_time = current_time_rounded - timedelta(minutes=1)
        elif selected_interval == "5 Min":
            start_time = current_time_rounded - timedelta(minutes=6)
            end_time = current_time_rounded - timedelta(minutes=1)
        elif selected_interval == "15 Min":
            start_time = current_time_rounded - timedelta(minutes=16)
            end_time = current_time_rounded - timedelta(minutes=1)



        start_time_rfc3339 = start_time.isoformat() + "Z"
        end_time_rfc3339 = end_time.isoformat() + "Z"

        db_bucket = props.get_database_bucket()
        org = props.get_influx_org()
        measurement = props.get_database_measurement()
        measurement1 = props.get_database_measurement1()

        start_time_rfc3339 = start_time.replace(microsecond=0).isoformat() + ".000Z"
        end_time_rfc3339 = end_time.replace(microsecond=0).isoformat() + ".000Z"

        print("Process Started for Socketdata")
        print(start_time_rfc3339, end_time_rfc3339)

        query = (
            f'from(bucket: "{db_bucket}") '
            f'|> range(start: {start_time_rfc3339}, stop: {end_time_rfc3339}) '
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement}") '
            f'|> filter(fn: (r) => r["interval"] == "{interval}") '
            f'|> filter(fn: (r) => r["_field"] == "original" or r["_field"] == "outlier") '
            f'|> yield()'
        )

        result = connection.query_api().query(org=org, query=query)

        raw_query = (
            f'from(bucket: "{db_bucket}")'
            f'|> range(start: {start_time_rfc3339}, stop: {end_time_rfc3339})'
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement1}")'
            f'|> filter(fn: (r) => r["_field"] == "cpu")'
            f'|> yield()'
        )

        rawdata_result = connection.query_api().query(org=org, query=raw_query)
        print("Query executed for Socketdata")
        # print(result)
        # print(rawdata_result)
        # if not result:
        #     return {"error": "No data found for the query: " + query}
        
        # if not rawdata_result:
        #     return {"error": "No data found for the query: " + raw_query}
        

        data = {}
        i = 1

        for table in result:
            for record in table.records:
                timestamp = record["_time"]
                if timestamp not in data:
                    data[timestamp] = {"id": i,"_time": timestamp, "_value": None, "outlier": None, "outlier_point": None}
                    i += 1

                if record["_field"] == "original":
                    data[timestamp]["_value"] = record["_value"]
                elif record["_field"] == "outlier":
                    data[timestamp]["outlier"] = record["_value"]
                    if record["_value"] > 0:
                        data[timestamp]["outlier_point"] = data[timestamp]['_value']
                    else:
                        data[timestamp]["outlier_point"] = 0

        merged_data = list(data.values())
        sorted_data = sorted(merged_data, key=lambda x: x["_time"])

        answer = []
        top_processes_by_minute = {}

        for table in rawdata_result:
            for record in table.records:
                command_parts = record['command'].split('_')
                process_name = "_".join(command_parts[1:])
                data_point = {
                    'value': record['_value'],
                    'time': record['_time'],
                    'command': record['command'],
                    'process_name': process_name,
                    'process_id': command_parts[0]
                }
                answer.append(data_point)

        # Process data to find the top 5 processes for each minute
        for data_point in answer:
            timestamp = data_point['time']

            minute = timestamp.replace(second=0).strftime('%Y-%m-%d %H:%M:%S+00:00')
            minute_key = minute.replace(" ", "T")

            if minute_key not in top_processes_by_minute:
                top_processes_by_minute[minute_key] = []

            process_exists = False
            for existing_process in top_processes_by_minute[minute_key]:
                if existing_process['process_name'] == data_point['process_name']:
                    process_exists = True
                    if data_point['value'] > existing_process['value']:
                        existing_process.update(data_point)
                    break

            if not process_exists:
                top_processes_by_minute[minute_key].append(data_point)

            top_processes_by_minute[minute_key] = sorted(top_processes_by_minute[minute_key], key=lambda x: x['value'], reverse=True)[:5]

        top_data = dict(sorted(top_processes_by_minute.items()))

        for entry in sorted_data:
            time_ = entry["_time"]
            time_key = datetime.isoformat(time_)
            if time_key in top_data:
                entry["top_5"] = top_data[time_key]
            else:
                print(f"No matching top_5 data for timestamp: {time_key}")
        
        for item in sorted_data:
            item['_time'] = item['_time'].strftime('%Y-%m-%dT%H:%M:%S%z')  # Convert the main timestamp

            if 'top_5' in item:
                for top_item in item['top_5']:
                    top_item['time'] = top_item['time'].strftime('%Y-%m-%dT%H:%M:%S%z')  # Convert the timestamp in top_5 list


        response_data = {"data": sorted_data}
        print("Process Done for Socketdata")
        return response_data

    except Exception as e:
        return {"error": f"Error occurred on getting SocketData: {str(e)}"}




# Changing 
@router4.get("/trailerror")
def trialerror():
    try:
        # Initialize the InfluxDB client using the database connection function
        connection = init_database_connection()

        # Retrieve the db_bucket from the connection dictionary
        db_bucket = props.get_database_bucket()
        org = props.get_influx_org()
        measurement = props.get_database_measurement1()

        print("Process Started")

        # Construct the InfluxDB query
        raw_query = (
            f'from(bucket: "{db_bucket}")'
            f'|> range(start: 2023-10-16T21:11:00Z, stop: 2023-10-16T22:11:00Z)'
            f'|> filter(fn: (r) => r["_measurement"] == "{measurement}")'
            f'|> filter(fn: (r) => r["_field"] == "cpu")'
            f'|> yield()'
        )

        # Execute the InfluxDB query
        rawdata_result = connection.query_api().query(org=org, query=raw_query)
        print("Query executed")

        answer = []
        # Initialize a dictionary to store the top 5 processes for each minute
        top_processes_by_minute = {}

        for table in rawdata_result:
            for record in table.records:
                command_parts = record['command'].split('_')
                process_name = "_".join(command_parts[1:])
                data_point = {
                    'value': record['_value'],
                    'time': record['_time'],
                    'command': record['command'],
                    'process_name': process_name,
                    'process_id': command_parts[0]
                }
                answer.append(data_point)
                
        sorted_answer = sorted(answer, key=lambda x: x['time'])


        # Process data to find the top 5 processes for each minute
        for data_point in answer:
            timestamp = data_point['time']
            
            # Calculate the forward timestamp (round up to the next minute)
            minute = timestamp.replace(second=0).strftime('%Y-%m-%d %H:%M:%S+00:00')
            minute_key = minute.replace(" ","T")

            if minute_key not in top_processes_by_minute:
                top_processes_by_minute[minute_key] = []

            # Check if the process is already in the top processes list for this minute
            process_exists = False
            for existing_process in top_processes_by_minute[minute_key]:
                if existing_process['process_name'] == data_point['process_name']:
                    process_exists = True
                    if data_point['value'] > existing_process['value']:
                        existing_process.update(data_point)
                    break

            # If the process is not in the list or has a higher value, add it
            if not process_exists:
                top_processes_by_minute[minute_key].append(data_point)

            # Sort the top processes by value and keep only the top 5
            top_processes_by_minute[minute_key] = sorted(top_processes_by_minute[minute_key], key=lambda x: x['value'], reverse=True)[:5]

        # Sort the keys in chronological order
        top_data = dict(sorted(top_processes_by_minute.items()))

        print("Done")
        response1_data = {"data": top_data}
        return response1_data


    except Exception as e:
        return {"error": f"Error occurred: {str(e)}"}







    #started changing here