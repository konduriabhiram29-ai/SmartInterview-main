import os
from app.config import STT_MODEL_SIZE, STT_DEVICE, STT_COMPUTE_TYPE

class SpeechService:
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise RuntimeError("faster-whisper is not installed. Please install C++ build tools and run pip install faster-whisper.")
            
            print(f"Loading faster-whisper model: {STT_MODEL_SIZE} on {STT_DEVICE} with {STT_COMPUTE_TYPE}...")
            cls._model = WhisperModel(
                STT_MODEL_SIZE, 
                device=STT_DEVICE, 
                compute_type=STT_COMPUTE_TYPE
            )
        return cls._model

    @classmethod
    def transcribe(cls, audio_file_path: str) -> str:
        model = cls.get_model()
        # vad_filter ensures silence is ignored, condition_on_previous_text=False prevents hallucinations 
        # based on past state since we process utterance by utterance.
        segments, info = model.transcribe(
            audio_file_path, 
            beam_size=1,
            best_of=1,
            temperature=0,
            vad_filter=True, 
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        
        text = " ".join([segment.text for segment in segments]).strip()
        return text
