from brian.motors import Motor, MotorPort, MotorException, set_wait_until_timeout_ms
from brian.audio import play_tone
from brian.runtime import show_image
from brian.audio import play_file, stop_playback


faces = ["gerty_empty.jpg",
"gerty_confused_left.jpg",
"gerty_love.jpg",
"gerty_confused_right.jpg",
"gerty_happy.jpg"]

sounds = [
    "assets/honk.wav",
    "assets/engine.wav",
    "assets/start.wav"
]

MOTOR_SPEED = 600
FORK_MOTOR_SPEED = 1500

show_image("assets/" + faces[4], size='fullscreen_fill')

set_wait_until_timeout_ms(300)

def make_motor(name, port):
    try:
        return Motor(port)
    except MotorException as exc:
        print(f"{name} motor on port {port.name} not available: {exc}")
        return None


left_motor = make_motor("left", MotorPort.B)
right_motor = make_motor("right", MotorPort.C)
fork_motor = make_motor("fork", MotorPort.A)

def game_start():
    show_image("assets/" + faces[1], size='fullscreen_fill')
    play_file(sounds[1])

def game_over():
    show_image("assets/" + faces[2], size='fullscreen_fill')
    play_tone(220, 600)

def swapping_controls():
    show_image("assets/" + faces[3], size='fullscreen_fill')
    play_file(sounds[0])


def stop_all():
    for motor in (left_motor, right_motor, fork_motor):
        if motor is None:
            continue
        try:
            motor.brake()
        except MotorException:
            pass


while True:
    try:
        line = input()
        for command in line.split():
            if not command:
                continue
            if command == "LEFT_FORWARD" and left_motor:
                left_motor.run_at_speed(MOTOR_SPEED)
            elif command == "LEFT_BACKWARD" and left_motor:
                left_motor.run_at_speed(-MOTOR_SPEED)
            elif command == "LEFT_STOP" and left_motor:
                left_motor.brake()
            elif command == "RIGHT_FORWARD" and right_motor:
                right_motor.run_at_speed(MOTOR_SPEED)
            elif command == "RIGHT_BACKWARD" and right_motor:
                right_motor.run_at_speed(-MOTOR_SPEED)
            elif command == "RIGHT_STOP" and right_motor:
                right_motor.brake()
            elif command == "FORK_FORWARD" and fork_motor:
                fork_motor.run_at_speed(FORK_MOTOR_SPEED)
            elif command == "FORK_BACKWARD" and fork_motor:
                fork_motor.run_at_speed(-FORK_MOTOR_SPEED)
            elif command == "FORK_STOP" and fork_motor:
                fork_motor.brake()
            elif command == "GAME_START":
                game_start()
            elif command == "GAME_OVER":
                game_over()
            elif command == "SWAPPING_CONTROLS":
                swapping_controls()
            elif command in (
                "LEFT_FORWARD", "LEFT_BACKWARD", "LEFT_STOP",
                "RIGHT_FORWARD", "RIGHT_BACKWARD", "RIGHT_STOP",
                "FORK_FORWARD", "FORK_BACKWARD", "FORK_STOP",
            ):
                print("Motor not connected!")
            else:
                print(f"unknown command: {command}")
    except KeyboardInterrupt:
        print("interrupted, stopping motors")
        stop_all()
        break
    except MotorException as exc:
        print(f"motor error: {exc}")
