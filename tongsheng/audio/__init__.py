"""Audio primitives: WAV helpers, microphone capture, streaming playback."""

from . import wav
from .capture import (AudioInput, InputDevice, MicMonitor, Recorder,
                      list_input_devices, parse_device)
from .player import StreamingPlayer, list_output_devices, play_file

__all__ = [
    "wav", "Recorder", "AudioInput", "MicMonitor", "InputDevice",
    "list_input_devices", "parse_device", "StreamingPlayer",
    "list_output_devices", "play_file",
]
