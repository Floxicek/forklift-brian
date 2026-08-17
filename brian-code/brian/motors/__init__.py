from MotorPort import *
from Motor import *
from EV3LargeMotor import *
from EV3MediumMotor import *
from NXTMotor import *
from MovementEnd import *
from MotorWaitOptimismLevel import *
import motor_types
import motor_port_probe
import motor_limits


class MotorException(Exception):
    """Default motor Exception"""


class MotorAlreadyClosedError(MotorException):
    """Thrown when trying to access closed Motor"""


class MotorInitializationFailedError(MotorException):
    """Thrown when motor initialization fails during init"""


class MotorPortAlreadyInUse(MotorException):
    """Thrown when trying to register motor or motor probe with port mode to already used port"""


class MotorIsNotReadyError(MotorException):
    """Thrown when trying to operate on a motor that is not ready.

    This is the base class for motor readiness exceptions. Catching this
    exception will also catch MotorIncompatibleTypeError and MotorNotConnectedError.
    """


class MotorIncompatibleTypeError(MotorIsNotReadyError):
    """Thrown when a motor of a different type than expected is connected.

    Catching this exception will also catch MotorNotConnectedError.
    """


class MotorNotConnectedError(MotorIncompatibleTypeError):
    """Thrown when no motor is connected to the specified port."""


def get_wait_until_timeout_ms() -> int:
    """Get the current timeout value for waitUntilReady operations in milliseconds."""
    ...


def set_wait_until_timeout_ms(timeout_ms: int) -> None:
    """Set the default timeout value for waitUntilReady operations in milliseconds.

    This timeout is used by all motor operations that internally wait for the motor
    to be ready (e.g., current_angle, coast, rotate_by_angle, etc.).

    Args:
        timeout_ms: Timeout in milliseconds for internal wait-until-ready calls.
            - positive: wait up to that many milliseconds
            - 0 or negative: treated as no wait (immediate return from readiness waits)
    """
    ...
