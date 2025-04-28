import socket
import paho.mqtt.client as mqtt
import threading
import FindMyIP as ip
import time

from shared_variables import (
    MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEP_ALIVE_INTERVAL
)

# MQTT Configuration

MQTT_TOPIC = "DeviceStatus"
MQTT_EXPECTED_MESSAGE = "up"

# Multicast Configuration
MULTICAST_GROUP = '224.1.1.1'
MULTICAST_PORT = 10001

# Flag to control broadcasting
broadcasting = True

def on_message(client, userdata, msg):
    global broadcasting
    message_payload = msg.payload.decode("utf-8")
    print(f"Received MQTT message on topic [{msg.topic}]: {message_payload}")

    if msg.topic == MQTT_TOPIC and message_payload == MQTT_EXPECTED_MESSAGE:
        print("Received 'up' message, stopping IP broadcast.")
        broadcasting = False  # Stop broadcasting

def start_mqtt_listener():
    """Listens for MQTT messages and stops broadcasting when needed."""
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_forever()  # Keep listening

def SendMyIP():
    """Continuously sends the local IP via UDP multicast until stopped."""
    global broadcasting

    local_ip = ip.internal()
    print(f"Broadcasting local IP: {local_ip}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    while broadcasting:
        sock.sendto(local_ip.encode(), (MULTICAST_GROUP, MULTICAST_PORT))
        time.sleep(1)

    print("IP broadcasting stopped.")

# Start MQTT listener in a separate thread
mqtt_thread = threading.Thread(target=start_mqtt_listener, daemon=True)
mqtt_thread.start()

# Start broadcasting IP
SendMyIP()