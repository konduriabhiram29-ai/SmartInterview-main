import os
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.speech_service import SpeechService
from app.dependencies.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/speech", tags=["speech"])

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not file.content_type.startswith("audio/") and not file.content_type.startswith("video/webm"):
        # WebM can sometimes be sent as video/webm by the browser
        pass

    # Read the file data
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Prevent large files to avoid resource exhaustion (e.g., limit to 5MB for short segments)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Audio file too large")

    tmp_path = ""
    try:
        # Save to a temporary file
        # Whisper/ffmpeg needs the real container extension. Browsers may send
        # WebM, Ogg, or MP4 depending on the MediaRecorder implementation.
        content_type = (file.content_type or "").lower()
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".webm", ".ogg", ".mp4", ".m4a", ".wav"}:
            suffix = ".webm" if "webm" in content_type else ".ogg" if "ogg" in content_type else ".mp4"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Transcribe
        text = SpeechService.transcribe(tmp_path)
        return {"text": text}
    
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {str(e)}")
    
    finally:
        # Always clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
