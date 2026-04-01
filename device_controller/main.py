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


def handle_manual_drive():
    """Step continuously while a manual button is held, then return."""
    while True:
        left_pressed = left_button.value() == 1
        right_pressed = right_button.value() == 1

        if left_pressed and not right_pressed:
            if DIRECTION_FLIP == 1:
                motor.step_backward(1)
            else:
                motor.step_forward(1)
        elif right_pressed and not left_pressed:
            if DIRECTION_FLIP == 1:
                motor.step_forward(1)
            else:
                motor.step_backward(1)
        else:
            motor.stop()
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

        if request_line.startswith("GET /open "):
            if DIRECTION_FLIP == 1:
                motor.step_forward(STEPS_PER_ACTION)
            else:
                motor.step_backward(STEPS_PER_ACTION)
            motor.stop()
            send_response(client, '200 OK', 'text/plain', 'OPEN')
        elif request_line.startswith("GET /close "):
            if DIRECTION_FLIP == 1:
                motor.step_backward(STEPS_PER_ACTION)
            else:
                motor.step_forward(STEPS_PER_ACTION)
            motor.stop()
            send_response(client, '200 OK', 'text/plain', 'CLOSED')
        else:
            send_response(client, '404 Not Found', 'text/plain', 'Use /open or /close')
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