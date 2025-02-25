import sys, json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QLineEdit,
    QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
)
import paho.mqtt.client as mqtt

MQTT_PORT = 1883
MQTT_TOPIC = "exercise/demo"

class MQTTExerciseApp(QWidget):
    def __init__(self):
        super().__init__()
        self.client = mqtt.Client()
        self.connected = False
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Telerehab Demo Exercise")

        layout = QVBoxLayout()

        # MQTT Broker Connection
        broker_layout = QHBoxLayout()
        self.broker_ip = QLineEdit()
        self.broker_ip.setPlaceholderText("MQTT Broker IP")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_mqtt)
        broker_layout.addWidget(self.broker_ip)
        broker_layout.addWidget(self.connect_btn)
        layout.addLayout(broker_layout)

        # Connection Status
        self.status_label = QLabel("Not Connected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.status_label)

        # Language Selection
        lang_layout = QHBoxLayout()
        for lang in ['EN', 'GR', 'DE', 'PT', 'TH']:
            btn = QPushButton(lang)
            btn.clicked.connect(lambda _, l=lang: self.send_language(l))
            lang_layout.addWidget(btn)
        layout.addLayout(lang_layout)

        # Exercise Category ComboBox
        self.category_cb = QComboBox()
        self.category_cb.addItems(['Sitting', 'Standing', 'Walking', 'Stretching'])
        self.category_cb.currentTextChanged.connect(self.update_exercises)
        layout.addWidget(QLabel("Category"))
        layout.addWidget(self.category_cb)

        # Exercise ComboBox
        self.exercise_cb = QComboBox()
        layout.addWidget(QLabel("Exercise"))
        layout.addWidget(self.exercise_cb)

        # Progression ComboBox
        self.progression_cb = QComboBox()
        layout.addWidget(QLabel("Progression"))
        layout.addWidget(self.progression_cb)

        self.update_exercises()

        # Start Exercise Button
        start_btn = QPushButton("Start Exercise")
        start_btn.clicked.connect(self.send_exercise)
        layout.addWidget(start_btn)

        self.setLayout(layout)
        self.show()

    def connect_mqtt(self):
        try:
            self.client.connect(self.broker_ip.text().strip(), MQTT_PORT, 60)
            self.connected = True
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", str(e))
            self.status_label.setText("Not Connected")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")

    def send_language(self, lang):
        if not self.connected:
            QMessageBox.warning(self, "Error", "MQTT broker not connected.")
            return

        payload = {
            "action": "LANGUAGE",
            "exercise": "/",
            "timestamp": datetime.now().isoformat(),
            "code": "",
            "message": "",
            "language": lang
        }
        self.publish(payload)

    def send_exercise(self):
        if not self.connected:
            QMessageBox.warning(self, "Error", "MQTT broker not connected.")
            return

        exercise_str = self.progression_cb.currentData()
        payload = {
            "action": "START",
            "exercise": exercise_str,
            "timestamp": datetime.now().isoformat(),
            "code": "",
            "message": "",
            "language": "/"
        }
        self.publish(payload)


    def publish(self, payload):
        msg = json.dumps(payload)
        self.client.publish(MQTT_TOPIC, msg)
        print(f"Sent: {msg}")

    def update_exercises(self):
        exercises = {
            'Sitting': {
                'Sit – Yaw': ['P0', 'P1', 'P2', 'P3'],
                'Sit - Pitch': ['P0', 'P1', 'P2', 'P3'],
                'Sit - Bend': ['P0', 'P1', 'P2', 'P3'],
                'Seated trunk rotation': ['P0', 'P1', 'P2'],
                'Assisted toe raises': ['P0', 'P1'],
                'Heel raises': ['P0', 'P1'],
                'Seated marching': ['P0', 'P1', 'P2'],
                'Sit to Stand': ['P0', 'P1', 'P2', 'P3']
            },
            'Standing': {
                'Maintain Balance': ['P0', 'P1', 'P2', 'P3'],
                'Maintain Balance Foam': ['P0', 'P1', 'P2', 'P3'],
                'Bend and Reach': ['P0', 'P1'],
                'Overhead Reach': ['P0', 'P1'],
                'Turn': ['P0', 'P1'],
                'Lateral weight shifts': ['P0', 'P1', 'P2', 'P3'],
                'Limits of stability': ['P0', 'P1', 'P2', 'P3'],
                'Forward reach': ['P0', 'P1']
            },
            'Walking': {
                'Horizon': ['P0', 'P1'],
                'Yaw': ['P0', 'P1', 'P2', 'P3'],
                'Pitch': ['P0', 'P1', 'P2', 'P3'],
                'Side stepping': ['P0', 'P1', 'P2']
            },
            'Stretching': {
                'Hip external rotator': ['P0'],
                'Lateral trunk flexion': ['P0'],
                'Calf stretch': ['P0']
            }
        }

        category = self.category_cb.currentText()
        self.exercise_cb.clear()
        for ex, progs in exercises[category].items():
            self.exercise_cb.addItem(ex, ex)

        self.update_progressions()

        self.exercise_cb.currentTextChanged.connect(self.update_progressions)

    def update_progressions(self):
        exercises = {
            'Sitting': {
                'Sit – Yaw': ['P0', 'P1', 'P2', 'P3'],
                'Sit - Pitch': ['P0', 'P1', 'P2', 'P3'],
                'Sit - Bend': ['P0', 'P1', 'P2', 'P3'],
                'Seated trunk rotation': ['P0', 'P1', 'P2'],
                'Assisted toe raises': ['P0', 'P1'],
                'Heel raises': ['P0', 'P1'],
                'Seated marching': ['P0', 'P1', 'P2'],
                'Sit to Stand': ['P0', 'P1', 'P2', 'P3']
            },
            'Standing': {
                'Maintain Balance': ['P0', 'P1', 'P2', 'P3'],
                'Maintain Balance Foam': ['P0', 'P1', 'P2', 'P3'],
                'Bend and Reach': ['P0', 'P1'],
                'Overhead Reach': ['P0', 'P1'],
                'Turn': ['P0', 'P1'],
                'Lateral weight shifts': ['P0', 'P1', 'P2', 'P3'],
                'Limits of stability': ['P0', 'P1', 'P2', 'P3'],
                'Forward reach': ['P0', 'P1']
            },
            'Walking': {
                'Horizon': ['P0', 'P1'],
                'Yaw': ['P0', 'P1', 'P2', 'P3'],
                'Pitch': ['P0', 'P1', 'P2', 'P3'],
                'Side stepping': ['P0', 'P1', 'P2']
            },
            'Stretching': {
                'Hip external rotator': ['P0'],
                'Lateral trunk flexion': ['P0'],
                'Calf stretch': ['P0']
            }
        }
        category = self.category_cb.currentText()
        exercise = self.exercise_cb.currentText()

        # Avoid the KeyError
        if exercise == '':
            return

        progressions = exercises[category][exercise]

        self.progression_cb.clear()
        category_key = category.lower()
        exercise_number = list(exercises[category]).index(exercise) + 1

        for prog in progressions:
            ex_str = f"VC holobalance_{category_key}_{exercise_number} {prog}"
            self.progression_cb.addItem(prog, ex_str)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = MQTTExerciseApp()
    sys.exit(app.exec_())