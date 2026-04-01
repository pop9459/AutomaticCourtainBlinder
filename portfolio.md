# Solo Innovator Y1 P3
- Name: Peter Kapsiar
- Student ID: 5486866
- Repository: https://github.com/pop9459/AutomaticCourtainBlinder

### Description
The project is focused on creating an automated system for opening and closing window courtains. The system uses a raspberry pi pico w microcontroller to control a stepper motor to pull strings attached to the curtains. The system can be controlled via physical buttons or remotely via API endpoints. The whole system is powered by a solar panel and a power bank. 

Components used:
- Raspberry Pi Pico W
- Neema 17 stepper motor
- A4988 stepper motor driver
- 2x buttons
- 2x 10k ohm resistors

During the project there was some accidental damage to the stepper motor driver which is why in the demo video I replaced the motor and the driver with a smaller stepper motor and a different driver. 

The project is inspired by a similar project from the youtube channel: "DIY Machines" (https://www.youtube.com/@DIYMachines) with the video "DIY - Alexa Curtain Control System - (3D Printable, Echo, Adafruit Feather Huzzah ESP8266)" (https://www.youtube.com/@DIYMachines)

### Schematic

<img src="./schematic.png" alt="schematic" style="max-height: 512px;"/>
<img src="./fallback_motor_schematic.png" alt="schematic" style="max-height: 512px;"/>

### Code
`main.py`
```python
import socket
import network
from machine import Pin

from position_db import PositionDB
from stepper_motor import make_motor
from web_server import connect_wifi, send_response

LEFT_BUTTON_PIN = 14
RIGHT_BUTTON_PIN = 15

positions_db = PositionDB()
stored_positions = positions_db.load_positions()
current_position = stored_positions["current_position"]
position_open = stored_positions["position_open"]
position_closed = stored_positions["position_closed"]

if not connect_wifi():
    raise RuntimeError("WiFi connection failed")

ip = network.WLAN(network.STA_IF).ifconfig()[0]
print("Pico IP:", ip)

motor = make_motor(pin1=10, pin2=11, pin3=12, pin4=13, delay=0.001, reverse=False)
motor.set_mode("half")

left_button = Pin(LEFT_BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)
right_button = Pin(RIGHT_BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)

addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
s = socket.socket()
try:
    # Helps after soft reboot when the previous socket is still in use briefly.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
except AttributeError:
    # Some MicroPython builds may not expose all socket constants/options.
    pass

try:
    s.bind(addr)
except OSError as exc:
    if exc.args and exc.args[0] == 98:
        s.close()
        raise RuntimeError(
            "Port 80 is already in use. Stop other web server scripts or hard-reset the Pico."
        )
    raise
s.listen(1)
s.settimeout(0.05)


def persist_positions():
    positions_db.save_positions(current_position, position_open, position_closed)


def step_with_tracking(logical_direction, steps=1):
    """Move motor and track logical position."""
    global current_position

    if steps <= 0:
        return

    if logical_direction > 0:
        motor.step_forward(steps)
    else:
        motor.step_backward(steps)

    current_position += logical_direction * steps
    motor.stop()


def move_to_position(target_position):
    delta = target_position - current_position
    moved = False

    if delta > 0:
        step_with_tracking(1, delta)
        moved = True
    elif delta < 0:
        step_with_tracking(-1, -delta)
        moved = True
    else:
        motor.stop()

    if moved:
        persist_positions()


def handle_manual_drive():
    """Step continuously while a manual button is held."""
    moved = False

    while True:
        left_pressed = left_button.value() == 1
        right_pressed = right_button.value() == 1

        if left_pressed and not right_pressed:
            step_with_tracking(-1, 1)
            moved = True
        elif right_pressed and not left_pressed:
            step_with_tracking(1, 1)
            moved = True
        else:
            motor.stop()
            if moved:
                persist_positions()
            return

while True:
    left_pressed = left_button.value() == 1
    right_pressed = right_button.value() == 1

    if left_pressed or right_pressed:
        handle_manual_drive()
        continue

    client = None
    try:
        try:
            client, client_addr = s.accept()
        except OSError:
            # No client connected within timeout; continue polling buttons.
            continue

        client.settimeout(2)
        request = client.recv(1024).decode()
        request_line = request.split("\r\n", 1)[0]
        print("Request from", client_addr, request_line)

        if request_line.startswith("GET /set/open "):
            position_open = current_position
            persist_positions()
            send_response(client, '200 OK', 'text/plain', 'OPEN_SET={}'.format(position_open))
        elif request_line.startswith("GET /set/close "):
            position_closed = current_position
            persist_positions()
            send_response(client, '200 OK', 'text/plain', 'CLOSE_SET={}'.format(position_closed))
        elif request_line.startswith("GET /move/open "):
            if position_open is None:
                send_response(client, '400 Bad Request', 'text/plain', 'Open position not set')
            else:
                move_to_position(position_open)
                send_response(client, '200 OK', 'text/plain', 'MOVED_OPEN position={}'.format(current_position))
        elif request_line.startswith("GET /move/close "):
            if position_closed is None:
                send_response(client, '400 Bad Request', 'text/plain', 'Closed position not set')
            else:
                move_to_position(position_closed)
                send_response(client, '200 OK', 'text/plain', 'MOVED_CLOSE position={}'.format(current_position))
        elif request_line.startswith("GET /reset/positions "):
            positions_db.reset_positions()
            current_position = 0
            position_open = None
            position_closed = None
            motor.stop()
            send_response(client, '200 OK', 'text/plain', 'POSITIONS_RESET current=0 open=None close=None')
        else:
            send_response(
                client,
                '404 Not Found',
                'text/plain',
                'Use /set/open, /set/close, /move/open, /move/close, /reset/positions',
            )
    except Exception as exc:
        motor.stop()
        if client is not None:
            try:
                send_response(client, '500 Internal Server Error', 'text/plain', str(exc))
            except Exception:
                pass
    finally:
        if client is not None:
            client.close()
```

`position_db.py`
```python
try:
    import ujson as json
except ImportError:
    import json


class PositionDB:
    def __init__(self, filename="positions.json"):
        self.filename = filename

    def load_json_file(self, filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_json_file(self, filename, data):
        with open(filename, "w") as f:
            json.dump(data, f)

    def load_positions(self):
        data = self.load_json_file(self.filename)
        if not isinstance(data, dict):
            data = {}

        return {
            "current_position": data.get("current_position", 0),
            "position_open": data.get("position_open", None),
            "position_closed": data.get("position_closed", None),
        }

    def save_positions(self, current_position, position_open, position_closed):
        self.save_json_file(
            self.filename,
            {
                "current_position": current_position,
                "position_open": position_open,
                "position_closed": position_closed,
            },
        )

    def reset_positions(self):
        self.save_positions(0, None, None)
```

`stepper_motor.py`
```python
"""Simple stepper motor library for ULN2003 + 28BYJ-48 style motors.

MicroPython compatible.
"""

from machine import Pin
import time


FULL_STEP_SEQUENCE = [
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
]


HALF_STEP_SEQUENCE = [
    (1, 0, 0, 0),
    (1, 1, 0, 0),
    (0, 1, 0, 0),
    (0, 1, 1, 0),
    (0, 0, 1, 0),
    (0, 0, 1, 1),
    (0, 0, 0, 1),
    (1, 0, 0, 1),
]


class StepperMotor:
    """Very small helper class to drive a 4-wire stepper via ULN2003."""

    def __init__(self, in1, in2, in3, in4, delay=0.002, reverse=False):
        self.pins = [in1, in2, in3, in4]
        self.delay = delay
        self.step_index = 0
        self.sequence = FULL_STEP_SEQUENCE
        self.reverse = bool(reverse)

    def set_mode(self, mode="full"):
        if mode == "half":
            self.sequence = HALF_STEP_SEQUENCE
        else:
            self.sequence = FULL_STEP_SEQUENCE

    def _set_pins(self, pattern):
        for pin, state in zip(self.pins, pattern):
            pin.value(state)

    def set_reverse(self, reverse=False):
        self.reverse = bool(reverse)

    def _step_actual_direction(self, actual_direction, steps=1):
        if actual_direction > 0:
            for _ in range(steps):
                self._set_pins(self.sequence[self.step_index])
                self.step_index = (self.step_index + 1) % len(self.sequence)
                time.sleep(self.delay)
        else:
            for _ in range(steps):
                self.step_index = (self.step_index - 1) % len(self.sequence)
                self._set_pins(self.sequence[self.step_index])
                time.sleep(self.delay)

    def step_forward(self, steps=1):
        actual_direction = -1 if self.reverse else 1
        self._step_actual_direction(actual_direction, steps)

    def step_backward(self, steps=1):
        actual_direction = 1 if self.reverse else -1
        self._step_actual_direction(actual_direction, steps)

    def rotate(self, degrees, steps_per_revolution=2048):
        steps = int(abs(degrees) / 360 * steps_per_revolution)
        if degrees >= 0:
            self.step_forward(steps)
        else:
            self.step_backward(steps)

    def stop(self):
        self._set_pins((0, 0, 0, 0))


def make_motor(pin1=16, pin2=17, pin3=18, pin4=19, delay=0.002, reverse=False):
    """Convenience factory using default Pico GPIO pins 16-19."""
    return StepperMotor(
        Pin(pin1, Pin.OUT),
        Pin(pin2, Pin.OUT),
        Pin(pin3, Pin.OUT),
        Pin(pin4, Pin.OUT),
        delay=delay,
        reverse=reverse,
    )
```

`web_server.py`
```python
try:
    import ujson as json
except ImportError:
    import json

import time
import network
from secrets import SSID, PASSWORD


def connect_wifi(timeout=15):
    """Connect to WiFi network. Returns True if connected, False otherwise."""
    nic = network.WLAN(network.WLAN.IF_STA)
    nic.active(True)

    if not nic.isconnected():
        print('Connecting to WiFi...')
        nic.connect(SSID, PASSWORD)
        # wait for connection (timeout after ~15 seconds)
        while not nic.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

    if nic.isconnected():
        print('Connected, network config:', nic.ifconfig())
        return True
    else:
        print('Failed to connect to WiFi. Check SSID/PASSWORD')
        return False


def send_response(conn, status, content_type, body):
    conn.send(('HTTP/1.1 {}\r\n'.format(status)).encode())
    conn.send(('Content-Type: {}\r\n'.format(content_type)).encode())
    conn.send('Connection: close\r\n\r\n'.encode())
    conn.send(body.encode())


def send_json(conn, status, payload):
    send_response(conn, status, 'application/json', json.dumps(payload))


def serve_file(conn, filepath, status='200 OK', content_type='text/html'):
    """Serve a file from the filesystem."""
    try:
        with open(filepath, 'r') as f:
            body = f.read()
        send_response(conn, status, content_type, body)
        return True
    except OSError:
        return False
```

`secrets.py`
```python
# WiFi credentials 
SSID = "YOUR_NET_SSID"
PASSWORD = "YOUR_NET_PASS"
```

### Output

overview video: https://youtu.be/afZEDE46g-k?si=IUZLnpNUe_IK7F3g