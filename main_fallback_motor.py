"""
Stepper Motor Driver with ULN2003APG Module
RPi Pico W - MicroPython Example

ULN2003APG is a Darlington transistor array that drives the stepper motor coils.
Requires 4 GPIO pins for control (IN1, IN2, IN3, IN4)
"""

from machine import Pin
import time

# GPIO Pin Configuration
# Connect these pins from Pico W to ULN2003APG inputs
IN1 = Pin(16, Pin.OUT)  # GPIO16 -> IN1
IN2 = Pin(17, Pin.OUT)  # GPIO17 -> IN2
IN3 = Pin(18, Pin.OUT)  # GPIO18 -> IN3
IN4 = Pin(19, Pin.OUT)  # GPIO19 -> IN4

# Full step sequence for stepper motor (4-phase)
# Each tuple represents coil activation pattern (IN1, IN2, IN3, IN4)
FULL_STEP_SEQUENCE = [
    (1, 0, 0, 0),  # Step 1
    (1, 1, 0, 0),  # Step 2
    (0, 1, 0, 0),  # Step 3
    (0, 1, 1, 0),  # Step 4
    (0, 0, 1, 0),  # Step 5
    (0, 0, 1, 1),  # Step 6
    (0, 0, 0, 1),  # Step 7
    (1, 0, 0, 1),  # Step 8
]

# Half step sequence (smoother, more precise control)
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
    """Control a stepper motor via ULN2003APG driver"""
    
    def __init__(self, in1, in2, in3, in4, delay=0.002):
        """
        Initialize stepper motor controller
        
        Args:
            in1, in2, in3, in4: Pin objects for motor control
            delay: Delay between steps (seconds). Lower = faster rotation
        """
        self.pins = [in1, in2, in3, in4]
        self.delay = delay
        self.step_index = 0
        self.sequence = FULL_STEP_SEQUENCE
    
    def set_sequence(self, sequence_type="full"):
        """Set stepping sequence: 'full' or 'half'"""
        if sequence_type == "half":
            self.sequence = HALF_STEP_SEQUENCE
        else:
            self.sequence = FULL_STEP_SEQUENCE
    
    def _set_pins(self, step_pattern):
        """Set GPIO pins according to step pattern"""
        for pin, state in zip(self.pins, step_pattern):
            pin.value(state)
    
    def step_forward(self, steps=1):
        """Rotate motor forward by specified number of steps"""
        for _ in range(steps):
            self._set_pins(self.sequence[self.step_index])
            self.step_index = (self.step_index + 1) % len(self.sequence)
            time.sleep(self.delay)
    
    def step_backward(self, steps=1):
        """Rotate motor backward by specified number of steps"""
        for _ in range(steps):
            self.step_index = (self.step_index - 1) % len(self.sequence)
            self._set_pins(self.sequence[self.step_index])
            time.sleep(self.delay)
    
    def rotate(self, degrees, steps_per_revolution=2048):
        """
        Rotate motor by specified degrees
        
        Args:
            degrees: Angle to rotate (positive = forward, negative = backward)
            steps_per_revolution: Steps needed for 360° rotation (typical: 2048)
        """
        steps = int(abs(degrees) / 360 * steps_per_revolution)
        if degrees > 0:
            self.step_forward(steps)
        else:
            self.step_backward(steps)
    
    def stop(self):
        """De-energize motor coils"""
        self._set_pins((0, 0, 0, 0))


# ===== EXAMPLE USAGE =====
if __name__ == "__main__":
    print("Stepper Motor Control Example - RPi Pico W")
    
    # Create motor instance (adjust delay for speed: higher = slower)
    motor = StepperMotor(IN1, IN2, IN3, IN4, delay=0.002)
    
    # Test 1: Rotate forward 180 degrees
    print("Rotating forward 180°...")
    motor.rotate(180)
    motor.stop()
    time.sleep(1)
    
    # Test 2: Rotate backward 180 degrees
    print("Rotating backward 180°...")
    motor.rotate(-180)
    motor.stop()
    time.sleep(1)
    
    # Test 3: Continuous rotation with pauses
    print("Continuous rotation...")
    for i in range(3):
        motor.step_forward(256)  # ~45° (2048 steps = 360°)
        motor.stop()
        time.sleep(0.5)
    
    # Test 4: Using half-step mode (smoother)
    print("Testing half-step mode...")
    motor.set_sequence("half")
    motor.step_forward(128)
    motor.stop()
    
    print("Done!")
