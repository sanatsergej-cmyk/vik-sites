import os
import tempfile
from pathlib import Path

_model = None


class SttUnavailable(RuntimeError):
    pass


def transcribe(audio: bytes) -> str:
    """Локальное распознавание речи (faster-whisper). Ставится только на сервере: pip install -r requirements-stt.txt."""
    global _model
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise SttUnavailable("faster-whisper не установлен") from e
    if _model is None:
        _model = WhisperModel(
            os.getenv("STT_MODEL", "small"),
            device="cpu",
            compute_type="int8",
            download_root=os.getenv("STT_MODEL_DIR") or None,
        )
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio)
        path = Path(f.name)
    try:
        segments, _ = _model.transcribe(str(path), language="ru", vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        path.unlink(missing_ok=True)
