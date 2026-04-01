from machine import Pin
import time

# Update these pins to match your wiring
STEP_PIN = 15
DIR_PIN = 14
EN_PIN = None  # Set to None if EN is not connected

# Motion settings
STEP_DELAY_US = 800      # Lower value = faster speed
STEPS_PER_TEST = 200     # 200 steps is 1 full rev for most NEMA17 motors
PAUSE_BETWEEN = 1.0


step = Pin(STEP_PIN, Pin.OUT, value=0)
direction = Pin(DIR_PIN, Pin.OUT, value=0)
enable = Pin(EN_PIN, Pin.OUT, value=1) if EN_PIN is not None else None


def motor_enable(on=True):
	# A4988 EN is active-low: 0 enables outputs, 1 disables
	if enable is not None:
		enable.value(0 if on else 1)


def do_steps(count, forward=True, step_delay_us=STEP_DELAY_US):
	direction.value(1 if forward else 0)

	for _ in range(count):
		step.value(1)
		time.sleep_us(step_delay_us)
		step.value(0)
		time.sleep_us(step_delay_us)


def main():
	print("A4988 stepper test starting")
	motor_enable(True)

	try:
		while True:
			print("Forward...")
			do_steps(STEPS_PER_TEST, forward=True)
			time.sleep(PAUSE_BETWEEN)

			print("Backward...")
			do_steps(STEPS_PER_TEST, forward=False)
			time.sleep(PAUSE_BETWEEN)
	except KeyboardInterrupt:
		print("Stopping test")
	finally:
		motor_enable(False)
		print("Driver disabled")


if __name__ == "__main__":
	main()
