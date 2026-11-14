"""Audio primitives: WAV helpers, microphone capture, streaming playback."""

from . import wav
from .capture import InputDevice, Recorder, list_input_devices, parse_device
from .player import StreamingPlayer, list_output_devices, play_file

__all__ = [
    "wav", "Recorder", "InputDevice", "list_input_devices", "parse_device",
    "StreamingPlayer", "list_output_devices", "play_file",
]
