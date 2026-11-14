"""Clone voices (import, train) and speak translated text in them."""

from .engine import SovitsEngine, TTSError
from .manager import SpeechResult, TTSRuntime
from .trainer import CloneTrainer, TrainError, TrainProgress
from .voices import VoiceProfile, VoiceStore

__all__ = ["SovitsEngine", "TTSError", "TTSRuntime", "SpeechResult",
           "VoiceProfile", "VoiceStore", "CloneTrainer", "TrainProgress", "TrainError"]
