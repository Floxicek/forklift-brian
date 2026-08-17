from enum import Enum
from typing import Optional


class PlaybackMode(Enum):
    """Mirrors AudioDriver::PlaybackMode (values match firmware)."""

    IDLE = 0
    TONE = 1
    FILE_STREAM = 2


class AudioFileMetadata:
    """
    Read-only snapshot of file metadata (attrtuple at runtime).
    Use attribute access: ``channels``, ``bits_per_sample``, ``sample_rate_hz``, ``total_samples``, ``is_supported_format``.
    """

    channels: int
    bits_per_sample: int
    sample_rate_hz: int
    total_samples: int
    is_supported_format: bool


class PlaybackStatus:
    """
    Read-only playback snapshot (attrtuple at runtime).
    Use attribute access: ``mode``, ``has_ended``, ``current_sample``, ``metadata``.
    """

    mode: PlaybackMode
    has_ended: bool
    current_sample: int
    metadata: AudioFileMetadata


def play_tone(tone: int, duration_ms: int):
    """
    Play a sine tone to the audio output.
    This method returns instantly and the tone is played in the background.

    :param tone: Frequency in Hz to play.
    :param duration_ms: How long should the tone last

    """
    ...


def stop_tone():
    """
    If tone is playing because of previous call to `play_tone`, it is stopped early.
    """
    ...


def play_file(
    path: str,
    *,
    skip_samples: Optional[int] = None,
    adaptive_loudness: Optional[bool] = None,
) -> bool:
    """
    Stream and play an audio file from SD card.
    The file is decoded and pushed in chunks and is not loaded fully to memory.

    :param path: Absolute VFS path to file (for example ``/recording.wav``).
    :param skip_samples: If ``None``, start from the beginning of the file. If set, number of source
        sample frames to skip before playback (per-channel frames in the WAV; same meaning as
        ``AudioDriver::playAudioFile``). Must be non-negative. Very large integers may
        raise ``OverflowError`` on the firmware port.
    :param adaptive_loudness: If ``True``, apply slow AGC, gentle compression, and limiting.
        If ``None``, the firmware default (enabled) is used.
    :return: ``True`` if playback request was accepted, ``False`` otherwise.
    """
    ...


def stop_playback():
    """
    Stop currently active tone or file playback.
    """
    ...


def get_playback_status() -> Optional[PlaybackStatus]:
    """
    Return a snapshot of current playback state, or ``None`` if status is unavailable.

    The returned object supports attribute access like ``PlaybackStatus`` / ``AudioFileMetadata``
    (implementation uses compact read-only attrtuples).
    """
    ...


def wait_until_done_playing(timeout_ms: Optional[float] = None) -> bool:
    """
    Block until no tone or file stream is active, ``timeout_ms`` elapses, or the program is stopped/interrupted.

    :param timeout_ms: Maximum wait in milliseconds; ``None`` means wait until idle or abort.
    :return: ``True`` if playback became idle; ``False`` on timeout or abort.
    """
    ...
