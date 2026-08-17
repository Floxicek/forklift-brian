from typing import Optional


class BTNS:
    """
    Static singleton providing access to the physical buttons and knob
    on the device via the global button state listener.

    BTNS is not instantiable — it is a pre-existing module-level object.
    Button attributes like ``is_pressed`` and ``turned_to`` reflect the
    live hardware state.
    """

    class Button:
        is_pressed: bool
        """True if the button is currently pressed by the user."""

        def wait_for_press(self, timeout_ms: Optional[int] = None) -> bool:
            """
            Waits for next button press event.
            This function is blocking.

            :param timeout_ms: Maximum number of milliseconds to wait.
                - If the timeout is not provided or is None, the function will wait indefinitely.

            :return success:
                - True: If the desired button event was caught.
                - False: If the timeout ran out.
            """

        def wait_for_release(self, timeout_ms: Optional[int] = None) -> bool:
            """
            Waits for next button release event.
            This function is blocking.

            :param timeout_ms: Maximum number of milliseconds to wait.
                - If the timeout is not provided or is None, the function will wait indefinitely.

            :return success:
                - True: If the desired button event was caught.
                - False: If the timeout ran out.
            """

        def wait_for_press_and_release(self, timeout_ms: Optional[int] = None) -> bool:
            """
            Waits for next button press and release event.
            This function is blocking.

            :param timeout_ms: Maximum number of milliseconds to wait.
                - If the timeout is not provided or is None, the function will wait indefinitely.

            :return success:
                - True: If the desired button event was caught.
                - False: If the timeout ran out.
            """

    class Knob(Button):
        turned_to: int
        """Absolute turn indent count (offset-corrected). Can be reset via reset_absolute_rotation()."""

        def wait_for_directional_turn(self, clockwise: bool = True, timeout_ms: Optional[int] = None) -> bool:
            """
            Waits for next directional turn of the knob.
            This function is blocking.

            :param clockwise: Whether to wait for clockwise or counterclockwise turn.
            :param timeout_ms: Maximum number of milliseconds to wait.
                - If the timeout is not provided or is None, the function will wait indefinitely.

            :return success:
                - True: If the desired button event was caught.
                - False: If the timeout ran out.
            """

        def wait_for_any_turn(self, timeout_ms: Optional[int] = None) -> bool:
            """
            Waits for next any turn of the knob.
            This function is blocking.

            :param timeout_ms: Maximum number of milliseconds to wait.
                - If the timeout is not provided or is None, the function will wait indefinitely.

            :return success:
                - True: If the desired button event was caught.
                - False: If the timeout ran out.
            """

        def reset_absolute_rotation(self, new_turned_to: int = 0) -> None:
            """
            Resets turned_to back to zero (or the provided value).

            :param new_turned_to: Value that turned_to should return immediately after this call. Defaults to 0.
            """

    top_left: Button
    """"""
    top_right: Button
    """"""
    bottom_left: Button
    """"""
    bottom_right: Button
    """"""
    any: Button
    """"""
    any_incl_knob: Button
    """"""
    knob: Knob
    """"""
