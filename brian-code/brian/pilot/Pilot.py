from typing import Optional
from brian.motors import Motor, MovementEnd, MotorWaitOptimismLevel


class Pilot:
    """
    Differential-drive pilot for controlling a robot with left and right wheels.

    Supports brake/hold/coast, forward/backward with optional distance,
    turn (small pivots), arc (large pivots), and travel (curved path).
    Movement methods wait for completion by default and return ``MovementEnd``; ``timeout_ms`` semantics match
    ``wait_for_movement()`` (``None`` = wait until done, ``0`` or negative = return from the wait immediately,
    often ``MovementEnd.TIMED_OUT`` if still moving).
    Speed and acceleration can be set once and used as defaults in movement commands.
    Odometry (distance and angle) is available with optional zeroing.
    """

    def __init__(
        self,
        left_motor: Motor,
        right_motor: Motor,
        # NOTE: Pilot (UI/type hints) shows ints; the underlying MicroPython binding still accepts floats.
        wheelbase_mm: int,
        wheel_circumference_mm: int,
        gear_ratio: Optional[int] = None,
        aux_left_motor: Optional[Motor] = None,
        aux_right_motor: Optional[Motor] = None,
        left_motor_reversed: bool = False,
        right_motor_reversed: bool = False,
        aux_left_motor_reversed: bool = False,
        aux_right_motor_reversed: bool = False,
    ) -> None:
        """
        Create a pilot for a differential-drive chassis.

        :param left_motor: Primary left motor.
        :param right_motor: Primary right motor.
        :param aux_left_motor: Optional secondary left motor.
        :param aux_right_motor: Optional secondary right motor.
        :param wheelbase_mm: Distance between left and right wheel (centre to centre), in mm.
        :param wheel_circumference_mm: Effective mm per revolution (circumference * gear ratio).
        :param gear_ratio: Optional gear ratio used by the drivetrain model.
        :param left_motor_reversed: Reverse primary left motor direction.
        :param right_motor_reversed: Reverse primary right motor direction.
        :param aux_left_motor_reversed: Reverse auxiliary left motor direction.
        :param aux_right_motor_reversed: Reverse auxiliary right motor direction.
        :raises ValueError: If numeric or topology arguments are invalid.
        :raises brian.pilot.PilotAlreadyReservedError: If another active pilot already reserves PilotSync control.
        :raises brian.pilot.PilotConfigurationError: If pilot creation fails for non-argument reasons.
        """
        ...

    def set_speed(self, speed_mm_per_sec: int) -> None:
        """
        Set the default linear speed used when a movement method is called without the optional speed argument.

        :param speed_mm_per_sec: Default speed in mm/s.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def get_default_speed(self) -> int:
        """
        Get the current default linear speed used when movement methods are called without ``speed``.

        :return: Default speed in mm/s.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def set_acceleration(self, acceleration_mm_per_sec_sq: int) -> None:
        """
        Set acceleration so callers do not pass it in every command.

        :param acceleration_mm_per_sec_sq: Acceleration in mm/s².
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def get_default_acceleration(self) -> int:
        """
        Get the current default acceleration used by movement commands.

        :return: Default acceleration in mm/s².
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def brake(self) -> None:
        """
        Apply passive braking on all registered motors (short the windings).
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def hold(self) -> None:
        """
        Actively hold all registered motors at their current positions.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def coast(self) -> None:
        """
        Let all motors spin freely (float the windings).
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def wait_for_movement(self, timeout_ms: Optional[int] = None) -> MovementEnd:
        """
        Block until the current movement completes or the timeout expires.

        :param timeout_ms: Max wait in milliseconds. If ``None``, wait until the move completes; if ``0`` or negative,
                           return immediately.
        :return: A value of ``brian.motors.MovementEnd`` (e.g. FINISHED, TIMED_OUT).

        Movement commands (``forward``, ``backward``, ``turn``, ``arc``, ``travel``) use the same ``timeout_ms``
        rules for their internal wait and return the same kind of ``MovementEnd`` value.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def movement_done(self) -> bool:
        """
        Check whether the last movement has completed.

        :return: True if no movement is in progress, False if still moving.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def forward(
        self,
        speed: Optional[int] = None,
        distance_mm: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> MovementEnd:
        """
        Drive forward and wait up to ``timeout_ms`` for the commanded move to finish.

        :param speed: Speed in mm/s. If None, uses default from set_speed(). Negative values reverse travel
                      along the same circle.
        :param distance_mm: If None or 0, no limit (open-loop speed; returns quickly with FINISHED). Negative values flip direction
                            by reversing speed; negative speed + negative distance becomes forward.
        :param timeout_ms: Same as :meth:`wait_for_movement`.
        :return: ``MovementEnd.FINISHED`` or ``MovementEnd.TIMED_OUT`` (script abort also surfaces as TIMED_OUT if incomplete).
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def backward(
        self,
        speed: Optional[int] = None,
        distance_mm: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> MovementEnd:
        """
        Drive backward and wait up to ``timeout_ms`` for the commanded move to finish.

        :param speed: Speed in mm/s. If None, uses default from set_speed(). Negative values reverse travel
                      along the same circle.
        :param distance_mm: If None or 0, no limit (open-loop speed; returns quickly with FINISHED). Negative values flip direction
                            by reversing speed; negative speed + negative distance becomes backward.
        :param timeout_ms: Same as :meth:`wait_for_movement`.
        :return: ``MovementEnd`` value for how the wait ended.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def turn(
        self,
        turn_rate: int,
        turn_radius_mm: Optional[int] = None,
        max_angle_deg: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> MovementEnd:
        """
        Turn and wait for completion (or timeout).

        :param turn_rate: Turn rate in degrees per second. Must be non-zero; positive and negative values select
                          direction.
        :param turn_radius_mm: Turning radius in mm; 0 or None means turn on the spot (pivot).
        :param max_angle_deg: Optional cap in degrees; 0 or None means no limit. Negative values flip direction by
                              reversing ``turn_rate``; negative ``turn_rate`` + negative ``max_angle_deg`` becomes
                              a positive turn.
        :param timeout_ms: Same as :meth:`wait_for_movement`.
        :return: ``MovementEnd`` value for how the wait ended.
        :raises ValueError: If ``turn_rate`` is zero.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def arc(
        self,
        radius_mm: int,
        max_distance_mm: Optional[int] = None,
        speed: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> MovementEnd:
        """
        Drive along an arc and wait for completion (or timeout).

        :param radius_mm: Turning radius in mm (from turn centre to robot centreline).
                        - ``0`` means turn around the robot centre,
                        - ``-wheelbase_mm/2`` means the left wheel is stationary,
                        - ``+wheelbase_mm/2`` means the right wheel is stationary.
                        - Negative values turn left, positive values turn right.
        :param max_distance_mm: Optional path length limit in mm; 0 or None means no limit. Negative values reverse travel
                                along the same circle (equivalent to negating speed).
        :param speed: Speed in mm/s. If None, uses default from set_speed().
        :param timeout_ms: Same as :meth:`wait_for_movement`.
        :return: ``MovementEnd`` value for how the wait ended.
        :raises ValueError: If called with values that make an internal turn invalid (for example zero turn rate).
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def travel(
        self,
        turn_rate: int,
        max_distance_mm: Optional[int] = None,
        speed: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> MovementEnd:
        """
        Drive along a curved path and wait for completion (or timeout).

        :param turn_rate: Turn rate in degrees per second.
        :param max_distance_mm: Optional path length limit in mm; 0 or None means no limit. Negative values reverse travel
                                along the same circle (equivalent to negating speed).
        :param speed: Speed in mm/s. If None, uses default from set_speed().
        :param timeout_ms: Same as :meth:`wait_for_movement`.
        :return: ``MovementEnd`` value for how the wait ended.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        :raises brian.pilot.PilotNotReadyError: If one of the controlled motors is not ready.
        """
        ...

    def wait_until_ready(
        self,
        timeout_ms: Optional[int] = None,
        optimism_level: Optional[MotorWaitOptimismLevel] = None,
    ) -> bool:
        """
        Block until all configured pilot motors are ready or the timeout expires.

        :param timeout_ms: Max wait in milliseconds. If ``None``, no per-call wall-clock limit; if ``0`` or negative,
                           return immediately (same as ``brian.motors.Motor.wait_until_ready``).
        :param optimism_level: Readiness strictness (same enum as brian.motors.Motor.wait_until_ready()).
        :return: True if all motors became ready before timeout, False otherwise.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def distance_travelled_mm(self) -> int:
        """
        Signed integrated robot path distance (odometry), in mm, relative to the last
        ``reset_distance_travelled()`` call (or pilot start heading angle if never reset).

        :return: Signed distance in mm.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def heading_angle_deg(self) -> int:
        """
        Signed integrated heading change (odometry), in degrees, relative to the last
        ``reset_heading_angle()`` call (or pilot creation if never reset).

        :return: Signed heading angle in degrees.
        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def reset_distance_travelled(self, new_value_mm: int = 0) -> None:
        """Set current integrated distance travelled to the provided value (in mm).

        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...

    def reset_heading_angle(self, new_value_deg: int = 0) -> None:
        """Set current integrated heading angle (in degrees) to the provided value.

        :raises brian.pilot.PilotAlreadyClosedError: If the pilot instance is already closed.
        """
        ...
