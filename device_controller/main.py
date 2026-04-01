import socket
import network
from machine import Pin

from stepper_motor import make_motor
from web_server import connect_wifi, send_response

LEFT_BUTTON_PIN = 14
RIGHT_BUTTON_PIN = 15

STEPS_PER_ACTION = 2048

# Set to -1 to flip motor direction globally, or 1 for normal direction.
DIRECTION_FLIP = 1

setting_mode_active = False
current_position = 0
position_open = None
position_closed = None

if not connect_wifi():
    raise RuntimeError("WiFi connection failed")

ip = network.WLAN(network.STA_IF).ifconfig()[0]
print("Pico IP:", ip)

motor = make_motor(pin1=10, pin2=11, pin3=12, pin4=13, delay=0.001)
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


def step_with_tracking(logical_direction, steps=1):
    """Move motor and track logical position independent of DIRECTION_FLIP."""
    global current_position

    if steps <= 0:
        return

    actual_direction = logical_direction * DIRECTION_FLIP
    if actual_direction > 0:
        motor.step_forward(steps)
    else:
        motor.step_backward(steps)

    current_position += logical_direction * steps
    motor.stop()


def move_to_position(target_position):
    delta = target_position - current_position
    if delta > 0:
        step_with_tracking(1, delta)
    elif delta < 0:
        step_with_tracking(-1, -delta)
    else:
        motor.stop()


def handle_manual_drive():
    """In setting mode, step continuously while a manual button is held."""
    while True:
        left_pressed = left_button.value() == 1
        right_pressed = right_button.value() == 1

        if left_pressed and not right_pressed:
            step_with_tracking(-1, 1)
        elif right_pressed and not left_pressed:
            step_with_tracking(1, 1)
        else:
            motor.stop()
            return

while True:
    left_pressed = left_button.value() == 1
    right_pressed = right_button.value() == 1

    if setting_mode_active and (left_pressed or right_pressed):
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

        if request_line.startswith("GET /setting/enter "):
            setting_mode_active = True
            send_response(
                client,
                '200 OK',
                'text/plain',
                'SETTING_MODE=ON position={} open={} closed={}'.format(
                    current_position,
                    position_open,
                    position_closed,
                ),
            )
        elif request_line.startswith("GET /setting/save/open "):
            if not setting_mode_active:
                send_response(client, '400 Bad Request', 'text/plain', 'Enter setting mode first')
            else:
                position_open = current_position
                send_response(client, '200 OK', 'text/plain', 'OPEN_SAVED={}'.format(position_open))
        elif request_line.startswith("GET /setting/save/close "):
            if not setting_mode_active:
                send_response(client, '400 Bad Request', 'text/plain', 'Enter setting mode first')
            else:
                position_closed = current_position
                send_response(client, '200 OK', 'text/plain', 'CLOSED_SAVED={}'.format(position_closed))
        elif request_line.startswith("GET /setting/exit "):
            setting_mode_active = False
            motor.stop()
            send_response(client, '200 OK', 'text/plain', 'SETTING_MODE=OFF')
        elif request_line.startswith("GET /setting/status "):
            send_response(
                client,
                '200 OK',
                'text/plain',
                'SETTING_MODE={} position={} open={} closed={}'.format(
                    'ON' if setting_mode_active else 'OFF',
                    current_position,
                    position_open,
                    position_closed,
                ),
            )
        elif request_line.startswith("GET /open "):
            if setting_mode_active:
                send_response(client, '409 Conflict', 'text/plain', 'Exit setting mode first')
            elif position_open is None:
                send_response(client, '400 Bad Request', 'text/plain', 'Open position not set')
            else:
                move_to_position(position_open)
                send_response(client, '200 OK', 'text/plain', 'OPEN')
        elif request_line.startswith("GET /close ") or request_line.startswith("GET /closed "):
            if setting_mode_active:
                send_response(client, '409 Conflict', 'text/plain', 'Exit setting mode first')
            elif position_closed is None:
                send_response(client, '400 Bad Request', 'text/plain', 'Closed position not set')
            else:
                move_to_position(position_closed)
                send_response(client, '200 OK', 'text/plain', 'CLOSED')
        elif request_line.startswith("GET /move/default/open "):
            # Compatibility helper: moves fixed distance without calibration.
            step_with_tracking(1, STEPS_PER_ACTION)
            send_response(client, '200 OK', 'text/plain', 'OPEN_DEFAULT')
        elif request_line.startswith("GET /move/default/close "):
            # Compatibility helper: moves fixed distance without calibration.
            step_with_tracking(-1, STEPS_PER_ACTION)
            send_response(client, '200 OK', 'text/plain', 'CLOSED_DEFAULT')
        else:
            send_response(
                client,
                '404 Not Found',
                'text/plain',
                'Use /setting/enter, /setting/save/open, /setting/save/close, /setting/exit, /open, /close',
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