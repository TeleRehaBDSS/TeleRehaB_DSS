from PyNuitrack import py_nuitrack
import cv2
from itertools import cycle
import numpy as np
import math

def euclidean_distance(Ax, Ay, Bx, By):
    distance = math.sqrt((Bx - Ax)**2 + (By - Ay)**2)
    return distance

def draw_face(image):
    if not data_instance:
        return
    for instance in data_instance["Instances"]:
        line_color = (59, 164, 225)
        text_color = (59, 255, 255)
        if 'face' in instance.keys():
            bbox = instance["face"]["rectangle"]
        else:
            return
        x1 = (round(bbox["left"]), round(bbox["top"]))
        x2 = (round(bbox["left"]) + round(bbox["width"]), round(bbox["top"]))
        x3 = (round(bbox["left"]), round(bbox["top"]) + round(bbox["height"]))
        x4 = (round(bbox["left"]) + round(bbox["width"]), round(bbox["top"]) + round(bbox["height"]))
        cv2.line(image, x1, x2, line_color, 3)
        cv2.line(image, x1, x3, line_color, 3)
        cv2.line(image, x2, x4, line_color, 3)
        cv2.line(image, x3, x4, line_color, 3)
        cv2.putText(image, "User {}".format(instance["id"]), x1, cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2, cv2.LINE_AA)
        cv2.putText(image, "{} {}".format(instance["face"]["gender"], int(instance["face"]["age"]["years"])), x3, cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2, cv2.LINE_AA)

def draw_skeleton(image, initial_hip_y, current_hip_y, posture, left_hand_count, right_hand_count):
    point_color = (59, 164, 0)
    for skel in data.skeletons:
        for el in skel[1:]:
            x = (round(el.projection[0]), round(el.projection[1]))
            cv2.circle(image, x, 8, point_color, -1)
    
    # Draw the initial hip line (yellow)
    if initial_hip_y is not None:
        initial_hip_y = int(initial_hip_y)
        cv2.line(image, (0, initial_hip_y), (image.shape[1], initial_hip_y), (0, 255, 255), 2)
    
    # Draw the current hip line (red if standing)
    if current_hip_y is not None and posture == "standing":
        current_hip_y = int(current_hip_y)
        cv2.line(image, (0, current_hip_y), (image.shape[1], current_hip_y), (0, 0, 255), 2)
    
    # Draw posture message
    cv2.putText(image, posture, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
    
    # Display hand raise counts
    cv2.putText(image, f'Left Hand Raises: {left_hand_count}', (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)
    cv2.putText(image, f'Right Hand Raises: {right_hand_count}', (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2, cv2.LINE_AA)

def detect_posture(skeleton, c, threshold):
    torso = skeleton.torso
    left_knee = skeleton.left_knee
    right_knee = skeleton.right_knee
    
    torso_x, torso_y = torso.projection[:2]
    knee_x = (left_knee.projection[0] + right_knee.projection[0]) / 2
    knee_y = (left_knee.projection[1] + right_knee.projection[1]) / 2

    distance = euclidean_distance(torso_x, torso_y, knee_x, knee_y)

    if c == 0:
        threshold = distance
        return "calibrating", threshold, torso_y
    elif c < 100:
        threshold = (threshold + distance) / 2
        return "calibrating", threshold, torso_y
    else:
        if distance > threshold * 1.2:
            return "standing", threshold, torso_y
        else:
            return "sitting", threshold, torso_y

def count_hand_raises(skeleton, head_y, left_hand_count, right_hand_count, left_hand_raised, right_hand_raised):
    left_hand = skeleton.left_hand
    right_hand = skeleton.right_hand
    
    left_hand_y = left_hand.projection[1]
    right_hand_y = right_hand.projection[1]
    
    if left_hand_y < head_y and not left_hand_raised:
        left_hand_count += 1
        left_hand_raised = True
    elif left_hand_y > head_y:
        left_hand_raised = False
    
    if right_hand_y < head_y and not right_hand_raised:
        right_hand_count += 1
        right_hand_raised = True
    elif right_hand_y > head_y:
        right_hand_raised = False
    
    return left_hand_count, right_hand_count, left_hand_raised, right_hand_raised

# Initialize Nuitrack
nuitrack = py_nuitrack.Nuitrack()
nuitrack.init()

# List available devices and activate the first one
devices = nuitrack.get_device_list()
for i, dev in enumerate(devices):
    print(dev.get_name(), dev.get_serial_number())
    if i == 0:
        dev.activate("license:48280:yH4janVDuE0tHhs9")
        print(dev.get_activation())
        nuitrack.set_device(dev)

# Print version and license info
print(nuitrack.get_version())
print(nuitrack.get_license())

# Create Nuitrack modules and start the pipeline
nuitrack.create_modules()
nuitrack.run()

# Cycle through display modes
modes = cycle(["depth", "color"])
mode = next(modes)

# Main loop
calibrating = True
calibration_frames = 100
c = 0
threshold = 0
initial_hip_y = None
current_hip_y = None
posture = "calibrating"
left_hand_count = 0
right_hand_count = 0
left_hand_raised = False
right_hand_raised = False

while True:
    key = cv2.waitKey(1)
    nuitrack.update()
    data = nuitrack.get_skeleton()
    data_instance = nuitrack.get_instance()
    img_depth = nuitrack.get_depth_data()
    
    if img_depth.size:
        cv2.normalize(img_depth, img_depth, 0, 255, cv2.NORM_MINMAX)
        img_depth = np.array(cv2.cvtColor(img_depth, cv2.COLOR_GRAY2RGB), dtype=np.uint8)
        img_color = nuitrack.get_color_data()
        
        for skeleton in data.skeletons:
            posture, threshold, current_hip_y = detect_posture(skeleton, c, threshold)
            print(posture)
            c += 1
            
            if c == calibration_frames:
                initial_hip_y = current_hip_y
            
            head_y = skeleton.head.projection[1]
            left_hand_count, right_hand_count, left_hand_raised, right_hand_raised = count_hand_raises(
                skeleton, head_y, left_hand_count, right_hand_count, left_hand_raised, right_hand_raised)

        if initial_hip_y is not None:
            draw_skeleton(img_depth, initial_hip_y, current_hip_y, posture, left_hand_count, right_hand_count)
            draw_skeleton(img_color, initial_hip_y, current_hip_y, posture, left_hand_count, right_hand_count)

        draw_face(img_depth)
        draw_face(img_color)

        if key == 32:  # Space key to toggle mode
            mode = next(modes)
        
        if mode == "depth":
            cv2.imshow('Image', img_depth)
        if mode == "color":
            if img_color.size:
                cv2.imshow('Image', img_color)
    
    if key == 27:  # ESC key to exit
        break

# Release Nuitrack resources
nuitrack.release()
