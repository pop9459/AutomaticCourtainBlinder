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
