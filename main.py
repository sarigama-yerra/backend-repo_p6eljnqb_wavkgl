import os
import re
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import create_document, get_documents, db
from schemas import Clip
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

app = FastAPI(title="Potongin Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

YOUTUBE_ID_REGEX = re.compile(r"(?:v=|be/|embed/)([A-Za-z0-9_-]{11})")


def extract_youtube_id(url: str) -> Optional[str]:
    match = YOUTUBE_ID_REGEX.search(url)
    return match.group(1) if match else None


class FetchRequest(BaseModel):
    url: str
    language: Optional[str] = None


class TranscriptSegmentOut(BaseModel):
    start: float
    end: float
    text: str
    index: int


class FetchResponse(BaseModel):
    video_id: str
    segments: List[TranscriptSegmentOut]


class CreateClipRequest(BaseModel):
    video_id: str
    start: float
    end: float
    title: Optional[str] = None
    transcript_snippet: Optional[str] = None
    user_id: Optional[str] = None


@app.get("/")
def read_root():
    return {"message": "Potongin Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, "name", None) or "✅ Connected"
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"⚠️ Error: {str(e)[:80]}"
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.post("/api/fetch", response_model=FetchResponse)
def fetch_transcript(payload: FetchRequest):
    vid = extract_youtube_id(payload.url)
    if not vid:
        raise HTTPException(status_code=400, detail="URL YouTube tidak valid.")

    try:
        # Try desired language or auto
        transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
        transcript = None
        if payload.language:
            try:
                transcript = transcript_list.find_manually_created_transcript([payload.language])
            except Exception:
                try:
                    transcript = transcript_list.find_transcript([payload.language])
                except Exception:
                    transcript = None
        if transcript is None:
            # Prefer manually created, then auto-generated English/ID, then any
            preferred = ["id", "en"]
            for code in preferred:
                try:
                    transcript = transcript_list.find_manually_created_transcript([code])
                    break
                except Exception:
                    try:
                        transcript = transcript_list.find_transcript([code])
                        break
                    except Exception:
                        continue
            if transcript is None:
                # fallback to first available
                transcript = transcript_list.find_transcript([t.language_code for t in transcript_list])
        raw = transcript.fetch()
        segments: List[TranscriptSegmentOut] = []
        for i, item in enumerate(raw):
            start = float(item.get("start", 0.0))
            dur = float(item.get("duration", 0.0))
            end = start + dur
            text = item.get("text", "").replace("\n", " ").strip()
            segments.append(TranscriptSegmentOut(start=start, end=end, text=text, index=i))
        return FetchResponse(video_id=vid, segments=segments)
    except (TranscriptsDisabled, NoTranscriptFound):
        raise HTTPException(status_code=404, detail="Transkrip tidak tersedia untuk video ini.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil transkrip: {str(e)[:120]}")


@app.post("/api/clips")
def create_clip(req: CreateClipRequest):
    if req.end <= req.start:
        raise HTTPException(status_code=400, detail="Rentang waktu tidak valid.")
    clip = Clip(
        video_id=req.video_id,
        user_id=req.user_id,
        start=req.start,
        end=req.end,
        title=req.title,
        transcript_snippet=req.transcript_snippet,
        export_status="ready",
        share_url=f"https://youtu.be/{req.video_id}?t={int(req.start)}"
    )
    clip_id = create_document("clip", clip)
    return {"id": clip_id, "share_url": clip.share_url}


@app.get("/api/clips")
def list_clips(video_id: str):
    results = get_documents("clip", {"video_id": video_id})
    # Normalize ObjectId to string
    for r in results:
        r["_id"] = str(r.get("_id"))
    return {"items": results}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
