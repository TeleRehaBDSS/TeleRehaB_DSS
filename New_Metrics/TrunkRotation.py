import pandas as pd
import numpy as np
import os
from datetime import datetime
import statistics 
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.signal import argrelextrema
from scipy.spatial.transform import Rotation as R
from scipy.signal import butter, filtfilt
import json
from scipy.signal import savgol_filter

def reformat_sensor_data(sensor_data_list):
    if not sensor_data_list:
        return []

    # Get the reference timestamp
    reference_timestamp = sensor_data_list[0].timestamp

    reformatted_data = []

    # Iterate through the sensor data list
    for data in sensor_data_list:
        timestamp = data.timestamp
        elapsed_time = timestamp - reference_timestamp
        reformatted_entry = [timestamp, elapsed_time, data.w, data.x, data.y, data.z]
        reformatted_data.append(reformatted_entry)

    return reformatted_data

def plotIMUDATA(Limu, x, filename):

    time = [row[0] for row in Limu]
    w = [row[x] for row in Limu]

    plt.figure(figsize=(10, 6))  
    plt.plot(time, w, marker='o', linestyle='-', color='b')  
    plt.title('Time vs W Component')
    plt.xlabel('Time (sec)')
    plt.ylabel('W component of quaternion')
    plt.grid(True)  


def interpolate_imu_data(imu_data, starttime, endtime, N):
    """
    Interpolate IMU data (w, x, y, z) between starttime and endtime into N samples.

    Parameters:
    imu_data (list of lists): The IMU data in format [time, w, x, y, z, _, _].
    starttime (float): The start time for interpolation.
    endtime (float): The end time for interpolation.
    N (int): Number of samples to interpolate.

    Returns:
    list of lists: Interpolated IMU data with N entries.
    """
    
# def butter_lowpass_filter(data, cutoff, fs, order=5):
#     nyq = 0.5 * fs  
#     normal_cutoff = cutoff / nyq
#     b, a = butter(order, normal_cutoff, btype='low', analog=False)
#     y = filtfilt(b, a, data)
#     return y
def butter_lowpass_filter(data, cutoff, fs, order=5):
    nyq = 0.5 * fs  
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)

    # Check if data length is greater than default padlen, adjust if necessary
    default_padlen = 2 * max(len(b), len(a)) - 1
    if len(data) <= default_padlen:
        padlen = len(data) - 1
    else:
        padlen = default_padlen

    y = filtfilt(b, a, data, padlen=padlen)
    return y


def striplist(L):
    A = []
    for item in L:
        t = item[1:-1]
        if ',' in t:
            t = t.split(',')
        else:
            t = t.split(' ')
        if "(number" not in t:
            A.append([t[-7],t[-5],t[-4],t[-3],t[-2],t[-1]])
    return A

def get_metrics(imu1,imu2,imu3,imu4, counter):
    
    Limu1 = reformat_sensor_data(imu1)
    Limu2 = reformat_sensor_data(imu2)
    Limu3 = reformat_sensor_data(imu3)   
    Limu4 = reformat_sensor_data(imu4)
    imu_data_lists = [Limu1, Limu2, Limu3, Limu4]
    


    dt1 = 0 
    dt2 = 0
    dt3 = 0
    dt4 = 0
    
    if(len(Limu1) > 0 ):
        dt1 = float(Limu1[-1][0]) - float(Limu1[0][0]);
    if(len(Limu2) > 0 ):
        dt2 = float(Limu2[-1][0]) - float(Limu2[0][0]);
    if(len(Limu3) > 0 ):
        dt3 = float(Limu3[-1][0]) - float(Limu3[0][0]);
    if(len(Limu4) > 0 ):
        dt4 = float(Limu4[-1][0]) - float(Limu4[0][0]);

    mean = statistics.mean([dt1, dt2, dt3, dt4])
    std = statistics.stdev([dt1, dt2, dt3, dt4])

    Limu1 = [[float(item) for item in sublist] for sublist in Limu1]

    Limu2 = [[float(item) for item in sublist] for sublist in Limu2]
    Limu3 = [[float(item) for item in sublist] for sublist in Limu3]
    Limu4 = [[float(item) for item in sublist] for sublist in Limu4]

    if(len(Limu2) > 0):
        returnedJson = getMetricsSittingNew01(Limu2, False) 
        return returnedJson

def getMetricsSittingNew01(Limu2, plotdiagrams):
    
    columns = ['Timestamp', 'elapsed(time)',  'W(number)', 'X(number)', 'Y (number)', 'Z (number)']
    df_Limu2 = pd.DataFrame(Limu2, columns=columns)
    df_Limu2['Timestamp'] = pd.to_datetime(df_Limu2['Timestamp'])
    df_Limu2 = df_Limu2.sort_values(by='Timestamp')
    df_Limu2.set_index('Timestamp', inplace=True)


    # Step 1: Preprocess the z-axis data by smoothing
    df_Limu2['z_smooth'] = savgol_filter(df_Limu2['Z (number)'], window_length=51, polyorder=3)

    # Step 2: Set thresholds for rotation detection
    middle_threshold = 0.05  # Middle range around zero
    min_threshold = -0.05     # Threshold for right rotation (minimum)
    max_threshold = 0.05      # Threshold for left rotation (maximum)

    # Step 3: Initialize variables for detecting rotations
    rotation_counts = {"right": 0, "left": 0}
    current_rotation = None
    rotation_timestamps = {"right": [], "left": []}  # Store timestamps for detected rotations

    # Step 4: Detect right and left rotations
    for i in range(1, len(df_Limu2)):
        z_prev = df_Limu2['z_smooth'].iloc[i - 1]
        z_curr = df_Limu2['z_smooth'].iloc[i]
        timestamp = df_Limu2.index[i]
        
        # Detect right rotation: from middle to min and back to middle
        if z_prev >= -middle_threshold and z_curr < min_threshold:
            current_rotation = "right"
        elif current_rotation == "right" and z_curr >= -middle_threshold:
            rotation_counts["right"] += 1
            rotation_timestamps["right"].append(timestamp)
            current_rotation = None

        # Detect left rotation: from middle to max and back to middle
        elif z_prev <= middle_threshold and z_curr > max_threshold:
            current_rotation = "left"
        elif current_rotation == "left" and z_curr <= middle_threshold:
            rotation_counts["left"] += 1
            rotation_timestamps["left"].append(timestamp)
            current_rotation = None

    # Step 5: Calculate metrics based on detected rotations
    number_of_movements = len(rotation_timestamps["right"]) + len(rotation_timestamps["left"])

    # Calculate duration between each detected rotation for right and left
    durations = []
    for side in ["right", "left"]:
        timestamps = rotation_timestamps[side]
        durations += [timestamps[i] - timestamps[i - 1] for i in range(1, len(timestamps))]
    durations = np.array([d.total_seconds() for d in durations])  # Convert durations to seconds
    
    # Pace of movements (movements per second)
    if len(df_Limu2) > 1:
        total_time = (df_Limu2.index[-1] - df_Limu2.index[0]).total_seconds()
        pace_movements_per_second = number_of_movements / total_time if total_time > 0 else 0
    else:
        pace_movements_per_second = 0

    # Calculate range degrees (approximate rotation angle) based on max and min z values for each rotation
    ranges_degrees = []
    for side in ["right", "left"]:
        for ts in rotation_timestamps[side]:
            idx = df_Limu2.index.get_loc(ts)
            z_values_window = df_Limu2['z_smooth'].iloc[max(0, idx - 5): min(len(df_Limu2), idx + 5)]
            range_degrees = np.degrees(np.max(z_values_window) - np.min(z_values_window))
            ranges_degrees.append(range_degrees)
    
    mean_combined_range_degrees = np.mean(ranges_degrees) if ranges_degrees else 0
    std_combined_range_degrees = np.std(ranges_degrees) if ranges_degrees else 0
    mean_duration_seconds = np.mean(durations) if len(durations) > 0 else 0
    std_duration_seconds = np.std(durations) if len(durations) > 0 else 0
    
    # Compile metrics data
    metrics_data = {
        "total_metrics": {
            "number_of_movements": number_of_movements,
            "pace_movements_per_second": pace_movements_per_second,
            "mean_combined_range_degrees": mean_combined_range_degrees,
            "std_combined_range_degrees": std_combined_range_degrees,
            "mean_duration_seconds": mean_duration_seconds,
            "std_duration_seconds": std_duration_seconds
        }
    }

    print (metrics_data)
    datetime_string = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{datetime_string}_AnteroposteriorDirection_metrics.txt"

    # Save the metrics to a file
    save_metrics_to_txt(metrics_data, filename)

    # Plot the smoothed data and mark detected rotations if plotdiagrams is True
    if plotdiagrams:
        plt.figure(figsize=(12, 6))
        plt.plot(df_Limu2.index, df_Limu2['z_smooth'], label='Smoothed z-axis data', color='blue')
        
        # Mark right rotations
        for ts in rotation_timestamps["right"]:
            plt.axvline(x=ts, color='red', linestyle='--', label='Right Rotation' if ts == rotation_timestamps["right"][0] else "")
        
        # Mark left rotations
        for ts in rotation_timestamps["left"]:
            plt.axvline(x=ts, color='green', linestyle='--', label='Left Rotation' if ts == rotation_timestamps["left"][0] else "")
        
        plt.xlabel('Timestamp')
        plt.ylabel('Smoothed z-axis')
        plt.title('Detected Trunk Rotations (Right and Left) on z-axis')
        plt.legend()
        plt.show()

    return json.dumps(metrics_data, indent=4)

def save_metrics_to_txt(metrics, file_path):
    main_directory = "Sitting Metrics Data"
    sub_directory = "Trunk Rotation Metrics Data"

    directory = os.path.join(main_directory, sub_directory)
    
    if not os.path.exists(directory):
        os.makedirs(directory)
    
   
    full_path = os.path.join(directory, file_path)

   
    with open(full_path, 'w') as file:
        for key, value in metrics.items():
            if isinstance(value, dict):  
                file.write(f"{key}:\n")
                for sub_key, sub_value in value.items():
                    file.write(f"  {sub_key}: {sub_value}\n")
            else:
                file.write(f"{key}: {value}\n")
            file.write("\n")