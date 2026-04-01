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