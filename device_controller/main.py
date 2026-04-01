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