import random

config = {
  "STOPWATCH": 10,
  "VID_PID": "16C0:0483",
  "REQUEST_NEW_MAP": "R",
  "ROWS": 48,
  "COLS": 48,
  "BAUDRATE": 115200,
  "TIMEOUT": 0.1,
  "type": ["Sitting","Standing","Walking","Stretching","Optokinetic"]
}

exercise_type_map = {
    "Sitting": ["VOR Horizontal (yaw)", "VOR Vertical (pitch)","Seated bending over","Seated trunk rotation","Toe Raises","Heel Raises","Seated marching on the spot","Sit to stand"],
    "Standing": ["Standing balance","Standing balance on foam","Standing bending over","Standing Turn","Lateral Weight Shifts","Stability training limits: heel-toe sway","Forward reach"],
    "Walking": ["Forward Walking","Forward walking with yaw rotation head turns","Forward walking pitch rotation head tilts","Side Stepping","Walking saccades with horizontal head movements scanning the room"],
    "Stretching": ["Seated hip external rotator stretch", "Seated lateral trunk flexion","Standing calf stretch"],
    "Optokinetic": ["Static optokinetic screen gaze stabilisation and head turns"]
}

metrics_type_map ={
    "Sitting": {
            'Number of movements': random.randint(3, 7),
            'Pace movements per second': round(random.uniform(0.1, 0.3), 3),
            'Mean movements range degrees': round(random.uniform(40 , 75),3),
            'Std movements range degrees' : round(random.uniform(40 , 75),3),
            'Mean duration seconds' : round(random.uniform(0 , 1),3),
            'Std duration seconds ' : round(random.uniform(0 , 1),3)
        },
    "Standing": {
            'Number of movements': random.randint(3, 7),
            'Pace movements per second': round(random.uniform(0.1, 0.3), 3),
            'Mean movements range degrees': round(random.uniform(40 , 75),3),
            'Std movements range degrees' : round(random.uniform(40 , 75),3),
            'Mean duration seconds' : round(random.uniform(0 , 1),3),
            'Std duration seconds ' : round(random.uniform(0 , 1),3)
        },
    "Walking": {
            'Number of steps': 9,
            'Mean speed (m/s)': 0.97 ,
            'Std speed ': 0.02
        },
    "Stretching": {
            'Number of movements': random.randint(3, 7),
            'Pace movements per second': round(random.uniform(0.1, 0.3), 3),
            'Mean combined range degrees': round(random.uniform(40 , 80),3),
            'Std combined range degrees' : round(random.uniform(40 , 80),3),
            'Mean duration seconds' : round(random.uniform(0 , 1),3),
            'Std duration seconds ' : round(random.uniform(0 , 1),3)
        },
    "Optokinetic": {
        'Number of movements': random.randint(3, 7)
    }
}