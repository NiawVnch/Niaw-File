import cv2
import numpy as np
#import pickle
#from skimage.transform import resize
import time
from datetime import datetime
import tkinter as tk
import threading
from tkinter import *
from tkinter import ttk
from PIL import Image, ImageDraw
import csv
import os
from tkinter import messagebox
import paho.mqtt.client as mqtt

import subprocess
import re

app = None

## Define model constants 
EMPTY = 0
NOT_EMPTY = 1
OTHER = 2

## Network and MQTT constants
interface_name = "wlp1s0"  # Replace with your actual WiFi interface name
#interfaces = ['wlp1s0', 'wlan0']
interfaces = ['wlp1s0']
firewall_port = 1883

## Program parameters
frame_rate = 20.0
step = 10
WiFi_Reconect_step = 1000 # will fine tune later
step_size = 5
resize_margin = 10
external_padx = 10
external_pady = 10
internal_padx = 10
internal_pady = 5

## Program Constants
File_Name = "N/A" #<= will came from code title
Device_Addr = "N/A"
#Host_Addr = "172.20.10.4"
Host_Addr = "10.84.171.108"
WiFi_SSID = "Tablet_PMFTH"
WiFi_USERNAME = "09barcode01"
WiFi_PWD = "P@ssw0rd"
Camera_Addr = 5
LstStat_Cam = "Good"
LstStat_PwdOff = "Bad"
LstStat_WiFi = "Bad" # TBC
LstStat_MQTT = "Bad"
LstStat_ExitProg = "Bad"
LstStat_LogicLoop = "Bad"

## Additional parameters
resize_shape = (100, 100, 3)  # Shape for resizing the spot
default_spot = [10, 10, 50, 50]  # Default dimensions for a new spot
first_spot_position = [0, 0, 0, 0]  # Initial position for the first spot
diff_threshold = 0.1  # Threshold for detecting significant differences

## Color codes
background_color = (0, 0, 0)
empty_color = (0, 0, 255)  # Red color for EMPTY
not_empty_color = (0, 255, 0)  # Green color for NOT_EMPTY
other_color = (255, 0, 0)  # Blue color for OTHER
selected_color = (0, 255, 255)  # Yellow color for selected spot
text_color = (255, 255, 255)  # White color for text
adjust_text_color = (50, 50, 255)

## MQTT setup section


def connect_to_wifi(ssid, username, password, iface):
    global LstStat_WiFi
    try:
        # Delete any existing connection with the same name
        subprocess.run(['nmcli', 'connection', 'delete', 'id', ssid], check=False)

        # Add a new connection with the specified parameters
        subprocess.run([
            'nmcli', 'connection', 'add',
            'type', 'wifi',
            'con-name', ssid,
            'ifname', iface,
            'ssid', ssid,
            'wifi-sec.key-mgmt', 'wpa-eap',
            '802-1x.eap', 'peap',
            '802-1x.phase2-auth', 'mschapv2',
            '802-1x.identity', username,
            '802-1x.password', password
        ], check=True)
        
        # Bring up the new connection
        subprocess.run(['nmcli', 'connection', 'up', ssid], check=True)
        
        LstStat_WiFi = "Good"
        print("Connected to WiFi.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to connect to WiFi. Error: {e}")
        LstStat_WiFi = "Bad"

def check_and_reconnect():
    global LstStat_WiFi
    while True:
        # Check WiFi connection status
        connection_status = subprocess.run(['nmcli', '-t', '-f', 'DEVICE,STATE', 'dev'], capture_output=True, text=True)
        connected = any(['connected' in line for line in connection_status.stdout.splitlines()])

        if not connected or LstStat_WiFi == "Bad":
            LstStat_WiFi = "Bad"
            connect_to_wifi(WiFi_SSID, WiFi_USERNAME, WiFi_PWD, interface_name)
        else:
            LstStat_WiFi = "Good"




def get_camera_indices():
    # Execute the command and get the output
    result = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE)
    output = result.stdout.decode('utf-8')

    # Use regular expression to find all video addresses
    matches = re.findall(r'/dev/video(\d+)', output)
    
    # Convert matches to integers
    indices = [int(match) for match in matches]

    # Ensure 5 is first if present, then sort the remaining
    if 5 in indices:
        indices.remove(5)
        indices = [5] + sorted(indices)
    else:
        indices = sorted(indices)

    return indices

def get_ip_address(interfaces):
    for interface in interfaces:
        try:
            # Execute the ip command and get the output
            result = subprocess.run(['ip', 'addr', 'show', interface], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Check if the command was successful
            if result.returncode != 0:
                print(f"Error running ip addr show on {interface}: {result.stderr}")
                continue
            
            # Use regex to find the IP address
            match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
            
            if match:
                return match.group(1)
        except Exception as e:
            print(f"An error occurred with interface {interface}: {e}")
            continue
    
    print("No IP address found for any interface")
    return None



 # Get the latest camera address
Camera_Addr = get_camera_indices()[0]

#Camera_Addr ='http://127.0.0.1/video_feed'

#Camera_Addr ='rtsp://admin:admin1234@192.168.1.44:554/cam/realmonitor?channel=1&subtype=0'

print("Found camera address:", Camera_Addr)

 # Get the latest ip address
Device_Addr = get_ip_address(interfaces)

if Device_Addr:
    print(f"IP address found: {Device_Addr}")
else:
    print(f"Failed to get IP address for any interface")


# WiFi connection initiation
#connect_to_wifi(WiFi_SSID, WiFi_PWD)
connect_to_wifi(WiFi_SSID, WiFi_USERNAME, WiFi_PWD, interface_name)

# Start the WiFi check and reconnect thread
wifi_thread = threading.Thread(target=check_and_reconnect)
wifi_thread.start()

cap = cv2.VideoCapture(Camera_Addr)
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

mask_height = frame_height
mask_width = frame_width
image_size = (frame_width, frame_height)

start_time = time.time()
t_E = t_S = t_prev_E = None
e_detected = s_detected = False

previous_frame = None
cycle_time = "N/A"
assembly_time = "N/A"

frame_nmr = 0
ret = True
cycle_counter = 1
cycle_time_start = time.time()

cv2.namedWindow(f'Real-Time Monitor', cv2.WINDOW_NORMAL)

while ret:
    ret, frame = cap.read()
    LstStat_Cam = "Good"

    copy_frame = frame.copy()
    ## Text position
    adjust_text_position = (frame.shape[1] - 170, 65)  # Position for adjust text
    time_text_position = (frame.shape[1] - 382, 32)  # Position for time text

    current_time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    cv2.putText(frame, current_time, time_text_position, cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2, cv2.LINE_AA)

    cv2.namedWindow(f'Real-Time Monitor', cv2.WINDOW_NORMAL)

    cv2.imshow(f'Real-Time Monitor', frame)

    if app is not None and app.is_recording:
        if app.video_writer is not None:
            app.video_writer.write(copy_frame)

    if cv2.waitKey(25) & 0xFF == ord('q'):
        LstStat_ExitProg = "Good"
        break


cap.release()
cv2.destroyAllWindows()
app.master.destroy()  # This will close the Tkinter window