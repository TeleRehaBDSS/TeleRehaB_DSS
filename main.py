import logging
import json
import paho.mqtt.client as mqtt
import sys
import os
import multiprocessing as mp
import threading
import time
import requests
import configparser
from datetime import datetime
from mqtt_messages import init_mqtt_client, set_language, start_exercise_demo, send_voice_instructions,send_message_with_speech_to_text,send_message_with_speech_to_text_2,send_exit
from data_management_v05 import scheduler, receive_imu_data
from api_management import login, get_device_api_key
from configure_file_management import read_configure_file
from Polar_test import start_ble_process 
from shared_variables import (
    queueData, scheduleQueue, enableConnectionToAPI,
    MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEP_ALIVE_INTERVAL,
    mqttState
)
from UDPSERVER import start_multicast_server
from UDPClient import SendMyIP
from websocketServer import run_websocket_server
from pathlib import Path

# Get the directory where the script is located
BASE_DIR = Path(__file__).resolve().parent

# Construct the paths for config and logo
CONFIG_PATH = BASE_DIR / 'config.ini'
TOPIC_PING = "healthcheck/AREYOUALIVE"
TOPIC_PONG = "healthcheck/IAMALIVE"

def send_heartbeat():
    global received_response
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)

    while True:
        received_response.value = 0  # Reset flag
        client.publish(TOPIC_PING, "AREYOUALIVE")
        print('------------------HEALTHCHECK-----------------------')
        time.sleep(30)  # Wait for 30 seconds

        # Wait for a response for a few more seconds before logging failure
        timeout = time.time() + 5
        while time.time() < timeout:
            if received_response.value == 1:
                break
            time.sleep(1)

        if received_response.value == 0:
            print("WARNING: No response received from the mobile app!")
            os.system("pkill -f 'gnome-terminal'")
    
            sys.exit(1)  # Exit the program with error code 1

def on_message_healthcheck(client, userdata, msg):
    global received_response
    if msg.topic == TOPIC_PONG:
        received_response.value = 1  # Mark that the response was received
        print('I got msg from app')

def start_mqtt_listener():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message_healthcheck
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    client.subscribe(TOPIC_PONG)
    client.loop_forever()  # Blocking call to listen continuously

# Define file storage API endpoints
FILE_STORAGE_BASE_URL = "https://telerehab-develop.biomed.ntua.gr/filestorage"
LOGS_ENDPOINT = f"{FILE_STORAGE_BASE_URL}/Logs"
DATA_ENDPOINT = f"{FILE_STORAGE_BASE_URL}/Data"

def get_api_key():
    """Fetch API key from config file."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config['API'].get('key_edge', '')

def convert_log_to_txt(log_file):
    """Converts .log file to .txt format."""
    txt_file = log_file.replace(".log", ".txt")
    with open(log_file, 'r') as lf, open(txt_file, 'w') as tf:
        tf.write(lf.read())
    return txt_file

def upload_file(file_path, file_type="Logs"):
    """Uploads a file to the file storage API."""
    if file_path.endswith(".log"):
        file_path = convert_log_to_txt(file_path)
    
    url = f"{FILE_STORAGE_BASE_URL}/{file_type}"
    headers = {
        'Authorization': get_api_key()
    }
    files = {'files': open(file_path, 'rb')}
    response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        logging.info(f"File {file_path} uploaded successfully to {file_type}.")
    else:
        logging.error(f"Failed to upload {file_path}. Status: {response.status_code}, Response: {response.text}")

def get_file_list(file_type="Logs"):
    """Retrieves the list of files from the file storage API."""
    url = f"{FILE_STORAGE_BASE_URL}/{file_type}/list"
    headers = {
        'Authorization': get_api_key()
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Failed to retrieve file list. Status: {response.status_code}, Response: {response.text}")
        return None

def download_file(file_id, save_path, file_type="Logs"):
    """Downloads a file from the file storage API."""
    url = f"{FILE_STORAGE_BASE_URL}/{file_type}/list/{file_id}"
    headers = {
        'Authorization': get_api_key()
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        logging.info(f"File {file_id} downloaded successfully to {save_path}.")
    else:
        logging.error(f"Failed to download file {file_id}. Status: {response.status_code}, Response: {response.text}")


# Set up logger
timestamp = time.time()
current_time = datetime.now().strftime("%Y-%m-%d")
logger = logging.getLogger()
#logger.setLevel(logging.DEBUG)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(message)s')
#file_handler = logging.FileHandler(f'{current_time}/app.log', mode='a') 
file_handler = logging.FileHandler('app.log', mode='a')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Redirect stdout and stderr to logger
class StreamToLogger:
    def __init__(self, log_level):
        self.log_level = log_level

    def write(self, message):
        if message.strip():
            self.log_level(message.strip())

    def flush(self):
        pass

sys.stdout = StreamToLogger(logger.info)
sys.stderr = StreamToLogger(logger.error)

def get_devices():
    """Fetch the daily schedule from the API."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    api_key_edge = config['API'].get('key_edge', '')
    
    url = 'http://telerehab-develop.biomed.ntua.gr/api/PatientDeviceSet'
    headers = {
        'accept': '*/*',
        'Authorization': api_key_edge
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()
# Helper functions for API interaction
def get_daily_schedule():
    """Fetch the daily schedule from the API."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    api_key_edge = config['API'].get('key_edge', '')
    
    url = 'http://telerehab-develop.biomed.ntua.gr/api/PatientSchedule/daily'
    headers = {
        'accept': '*/*',
        'Authorization': api_key_edge
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

def post_results(score, exercise_id):
    """Fetch the daily schedule from the API."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    api_key_edge = config['API'].get('key_edge', '')
    """Post metrics to the PerformanceScore API."""
    try:
        url = "https://telerehab-develop.biomed.ntua.gr/api/PerformanceScore"
        date_posted = datetime.now().isoformat()
        post_data = {
            "score": score,
            "exerciseId": exercise_id,
            "datePosted": date_posted
        }
        headers = {
            "Authorization": api_key_edge,  
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=post_data, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"Metrics successfully posted for exercise ID {exercise_id}")
        else:
            logger.error(f"Failed to post metrics for exercise ID {exercise_id}. Status code: {response.status_code}")
            logger.error("Response: " + response.text)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error posting results: {e}")

# Main logic to run scenario
def runScenario(queueData):

    init_mqtt_client()

    logging.basicConfig(level=logging.INFO)
    # test_log_file = "/home/uoi/Documents/GitHub/Telerehab_UOI/WP3_v1/imu_mqtt/2024-12-13/app.log"  # Existing log file to test the upload
    # if os.path.exists(test_log_file):
    #     upload_file(test_log_file, "Logs")
    # else:
    #     logging.error(f"Test log file {test_log_file} not found.")
    
    client.publish('STARTVC', 'STARTVC')
    time.sleep(4)
    
    # Stop recording after data collection is done
    client.publish('StopRecording', 'StopRecording')
    time.sleep(2)

    try:
        set_language("EN")
    except Exception as e:
        print(f"Language selection failed{e}")
        return

    try:
        metrics_queue = mp.Queue()
        #polar_queue = mp.Queue()
        logger.info('Running scenario...')
        
        while True:
            devices = get_devices() #Get the device set from the endpoint
            # Initialize variables for IMU serial numbers
            imu_serials = {}

            # Extract serial numbers based on IMU names
            for device in devices[0]['devices']:
                name = device['name']
                serial_number = device['serialNumber']
                imu_serials[name] = serial_number

            # Assign each to a variable if needed
            imu_head = imu_serials.get('imu-one')
            imu_pelvis = imu_serials.get('imu-two')
            imu_left = imu_serials.get('imu-three')
            imu_right = imu_serials.get('imu-four')

            # Fetch the daily schedule
            exercises = get_daily_schedule()
            print("Get list",exercises)
            if not exercises:
                logger.info("No exercises found. Exiting.")
                break                    

            # Process each exercise in the schedule
            for exercise in exercises:
                logger.info(f"Processing Exercise ID: {exercise['exerciseId']}")
                
                try:
                    start_exercise_demo(exercise)
                except Exception as e:
                    logger.error(f"Demonstration failed for Exercise ID {exercise['exerciseId']}: {e}")
                    continue

                
                # Determine the config message based on exercise ID
                if exercise['exerciseId'] == 1:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-OFF,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_01"
                elif exercise['exerciseId'] == 2:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-OFF,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_02"
                elif exercise['exerciseId'] == 3:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_03"
                elif exercise['exerciseId'] == 14:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_04"
                elif exercise['exerciseId'] == 15:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-OFF,LEFTFOOT={imu_left}-QUATERNIONS,RIGHTFOOT={imu_right}-QUATERNIONS,exer_05"
                elif exercise['exerciseId'] == 16:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-OFF,LEFTFOOT={imu_left}-QUATERNIONS,RIGHTFOOT={imu_right}-QUATERNIONS,exer_06"
                elif exercise['exerciseId'] == 17:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-QUATERNIONS,RIGHTFOOT={imu_right}-QUATERNIONS,exer_07"
                elif exercise['exerciseId'] == 18:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_08"
                elif exercise['exerciseId'] == 4:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_09"
                elif exercise['exerciseId'] == 5:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_10"
                elif exercise['exerciseId'] == 6:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_11"
                elif exercise['exerciseId'] == 7:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-QUATERNIONS,RIGHTFOOT={imu_right}-QUATERNIONS,exer_12"
                elif exercise['exerciseId'] == 19:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-QUATERNIONS,RIGHTFOOT={imu_right}-QUATERNIONS,exer_13"
                elif exercise['exerciseId'] == 20:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-OFF,RIGHTFOOT={imu_right}-OFF,exer_14"
                elif exercise['exerciseId'] == 21:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-QUATERNIONS,RIGHTFOOT={imu_right}-QUATERNIONS,exer_15"
                elif exercise['exerciseId'] == 8:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-LINEARACCELERATION,RIGHTFOOT={imu_right}-LINEARACCELERATION,exer_16"
                elif exercise['exerciseId'] == 9:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-LINEARACCELERATION,RIGHTFOOT={imu_right}-LINEARACCELERATION,exer_17"
                elif exercise['exerciseId'] == 10:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-LINEARACCELERATION,RIGHTFOOT={imu_right}-LINEARACCELERATION,exer_18"
                elif exercise['exerciseId'] == 22:
                    config_message = f"HEAD={imu_head}-OFF,PELVIS={imu_pelvis}-OFF,LEFTFOOT={imu_left}-LINEARACCELERATION,RIGHTFOOT={imu_right}-LINEARACCELERATION,exer_19"
                elif exercise['exerciseId'] == 23:
                    config_message = f"HEAD={imu_head}-QUATERNIONS,PELVIS={imu_pelvis}-QUATERNIONS,LEFTFOOT={imu_left}-LINEARACCELERATION,RIGHTFOOT={imu_right}-LINEARACCELERATION,exer_20"
                else:
                    logger.warning(f"No config message found for Exercise ID: {exercise['exerciseId']}")
                    continue
                
                # Publish configuration and start the exercise
                topic = "IMUsettings"

                # Publish the configuration message to start the exercise
                print('--- Starting the exercise ---')
                client.publish("IMUsettings", config_message)
                time.sleep(2)
                client.publish('StartRecording', 'start')
                # Start the scheduler process
                scheduler_process = mp.Process(target=scheduler, args=(scheduleQueue,))
                scheduler_process.start()

                #Start the process to receive Polar data
                # polar_proc = mp.Process(target=start_ble_process, args=(0, polar_queue))  # Adjust adapter index if needed
                # polar_proc.start()

                # Wait for Polar connection or failure
                time.sleep(5)  # Give some time to attempt connection

                # Start the process to receive IMU data
                imu_process = mp.Process(
                    target=receive_imu_data,
                    args=(queueData, scheduleQueue, config_message, exercise,metrics_queue,)
                )

                imu_process.start()

                # Wait for the IMU process to finish
                imu_process.join()

                # Terminate the scheduler process
                scheduler_process.terminate()
                scheduler_process.join()

                # Stop recording after data collection is done
                client.publish('StopRecording', 'StopRecording')
                time.sleep(2)

                # Check if Polar connection failed early
                # if not polar_proc.is_alive() or (not polar_queue.empty() and polar_queue.get() is None):
                #     logging.warning("Polar H10 is not connected. Proceeding without heart rate data.")
                #     polar_proc.terminate()
                #     polar_proc.join()
                
                # polar_data = []
                # while not polar_queue.empty():
                #     polar_data.append(polar_queue.get())
                
                # Post metrics after the exercise ends

                if not metrics_queue.empty():
                    metrics = metrics_queue.get()
                    print(metrics)
                    try:
                        metrics = json.loads(metrics) if isinstance(metrics, str) else metrics
                    except json.JSONDecodeError:
                        print("Metrics could not be parsed as JSON.")
                        return
                    print(f"Metrics for Exercise {exercise['exerciseId']}: {metrics}")

                    #Post the results
                    #metrics["polar_data"] = polar_data
                    post_results(json.dumps(metrics), exercise['exerciseId'])
                   
                else:
                    try:
                        metrics = {"metrics": ["ERROR IN METRICS", "ERROR IN METRICS", "ERROR IN METRICS"]}
                    except json.JSONDecodeError:
                        print("Metrics_2 could not be parsed as JSON.")
                        return
                    
                

                # Mark the exercise as completed
                print(f"Exercise {exercise['exerciseName']} completed.")
                
                #Ask the patient if feels any symptoms
                try:
                # Combine sending voice instruction and waiting for response
                    symptomps_response = send_message_with_speech_to_text("bph0101")
                except Exception as e:
                    logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                    return
                
                #If the answer is no ask the patient to move in another exercise
                if symptomps_response == "no":
                    # Ask if wanna to move to another exercise
                    try:
                        time.sleep(2)
                        response = send_message_with_speech_to_text("bph0088")
                    except Exception as e:
                        logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                        return

                    if response == "no":
                        print("User chose to stop. Exiting scenario.")
                        send_voice_instructions("bph0222")
                        send_voice_instructions("bph0108")
                        client.publish('EXIT','EXIT')
                        send_exit()
                        return
                    elif response == "yes":
                        print("User chose to continue. Proceeding with next exercise.")
                        send_voice_instructions("bph0045")
                        continue
                else:
                    #Ask for specific symptoms one after another!!!
                    #Headache
                    try:
                    # Combine sending oral instruction and waiting for response
                        headache_response = send_message_with_speech_to_text("bph0077")
                    except Exception as e:
                        logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                        return
                    if headache_response == "yes":
                        try:
                            rate_headache = send_message_with_speech_to_text_2("bph0110")
                        except Exception as e:
                            logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                            return
                    #Disorientated
                    try:
                    # Combine sending voice instruction and waiting for response
                        disorientated_response = send_message_with_speech_to_text("bph0087")
                    except Exception as e:
                        logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                        return
                    if disorientated_response == "yes":
                        try:
                            rate_disorientated = send_message_with_speech_to_text_2("bph0110")
                        except Exception as e:
                            logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                            return
                    #Blurry Vision
                    try:
                    # Combine sending voice instruction and waiting for response
                        blurry_vision_response = send_message_with_speech_to_text("bph0089")
                    except Exception as e:
                        logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                        return
                    if blurry_vision_response == "yes":
                        try:
                            rate_blurry_vision = send_message_with_speech_to_text_2("bph0110")
                        except Exception as e:
                            logger.error(f"Failed to send voice instruction or get response for Exercise ID {exercise['exerciseId']}: {e}")
                            return
                    send_voice_instructions("bph0222")
                    send_voice_instructions("bph0223")
                    break;
            
            # Fetch updated schedule after processing current exercises
            exercises = get_daily_schedule()
            ###If there are no exercises then end the 
            if not exercises :
                send_voice_instructions("bph0222")
                send_voice_instructions("bph0108")
                client.publish('EXIT','EXIT')
                send_exit()
                break;

    except requests.exceptions.RequestException as e:
        logger.error(f"Error: {e}")


# def checkIAMALIVE(iamalive_queue):
#     client2 = mqtt.Client()

#     client2.on_connect = on_connect2
#     client2.on_message = on_message2(iamalive_queue)
#     client2.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEP_ALIVE_INTERVAL)
#     client2.loop_start()


# def on_connect2(client, userdata, flags, rc):
#     print(f"Connected with result code {rc}")
#     client.subscribe([("iamalive_topic", 0)])


# def on_message2(client, userdata, msg, iamalive_queue):
#     payload = json.loads(msg.payload.decode())
#     print(f"Received message on {msg.topic}: {payload}")

#     if msg.topic == "iamalive_topic":
#         iamalive_queue.put('OK')


# MQTT setup
def on_connect(client, userdata, flags, rc):
    logger.info("Connected to MQTT broker with result code " + str(rc))
    client.subscribe("IMUsettings")
    client.subscribe("DeviceStatus")
    client.subscribe("StopRecording")
    client.subscribe("TerminationTopic")
    client.subscribe("STARTVC")
    client.subscribe("EXIT")

def on_message(client, userdata, msg):
    logger.info(f"Message Received -> {msg.payload.decode()}")

# Start MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEP_ALIVE_INTERVAL)

client_process = mp.Process(target=SendMyIP, args=())
client_process.start()

# Publish loop
def publish_loop():
    topic = "IMUsettings"
    while True:
        time.sleep(1)

# Start necessary processes
if enableConnectionToAPI:
    login()
    get_device_api_key()

server_process = mp.Process(target=start_multicast_server, args=(queueData,))
server_process.start()

# iamalive_process = mp.Process(target=checkIAMALIVE, args=(iamalive_queue,))
# iamalive_process.start()

thread = threading.Thread(target=publish_loop)
# thread.start()

received_response = mp.Value('b', 0)  # Shared flag to track responses
listener_process = mp.Process(target=start_mqtt_listener)
listener_process.start()


threadscenario = threading.Thread(target=runScenario, args=(queueData,))
threadscenario.start()

send_heartbeat()

client.loop_forever()
threadscenario.join()
