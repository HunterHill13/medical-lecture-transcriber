#!/usr/bin/env python3
"""
transcribe_chunks.py: Lightweight, Cloud-Native Audio Transcription via Gemini.
Enforces the strict Gemini Multimodal Transcription Architecture:
- Uses Gemini 2.0 Flash API (or direct in-context multimodal view_file).
- STRICTLY FORBIDS downloading or installing heavyweight local speech models (Whisper, faster-whisper, torch, CUDA).
"""

import os
import sys
import json
import base64
import time
import argparse
import urllib.request
import urllib.error

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from text_utils import format_seconds_to_time

MEDICAL_TRANSCRIPTION_PROMPT = """شما یک متخصص پیاده‌سازی و ترنسکریپت سخنرانی‌ها و کلاس‌های پزشکی دانشگاهی هستید.
وظیفه شما پیاده‌سازی کلمه به کلمه (Verbatim)، دقیق و کامل فایل صوتی ضمیمه‌شده به زبان فارسی و اصطلاحات تخصصی انگلیسی است.

دستورالعمل‌های حیاتی:
۱. تمام بیانات، شوخی‌ها، مثال‌های بالینی، نام بیماری‌ها، داروها و دوزها را بدون کم و کاست پیاده‌سازی کنید.
۲. اصطلاحات تخصصی پزشکی (مانند TSH, PTH, T3/T4, Hypothyroidism, Cushing, Adenoma, Incidentaloama) را با املای دقیق ثبت کنید.
۳. از خلاصه‌سازی، بازنویسی کلی یا حذف هرگونه جمله استاد اکیداً خودداری کنید.
۴. متن را ساختاریافته و با پاراگراف‌بندی مناسب ارائه دهید.
"""

def get_mime_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mapping = {
        ".m4a": "audio/mp4",
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".aac": "audio/aac",
        ".flac": "audio/flac"
    }
    return mapping.get(ext, "audio/mp4")

def transcribe_chunk_with_gemini_rest(chunk_path: str, api_key: str, model: str = "gemini-2.0-flash", max_retries: int = 3, retry_delay: float = 2.0) -> str:
    """
    Transcribes an audio chunk using standard library urllib with exponential backoff retry.
    Retries automatically on HTTP 429 (rate limit / quota), HTTP 503, or network connection timeouts.
    """
    if not os.path.exists(chunk_path):
        raise FileNotFoundError(f"Audio chunk not found: {chunk_path}")
        
    mime_type = get_mime_type(chunk_path)
    with open(chunk_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": MEDICAL_TRANSCRIPTION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": audio_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                candidates = res_json.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    text_result = "".join(p.get("text", "") for p in parts)
                    return text_result.strip()
                return ""
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                wait_sec = retry_delay * (2 ** (attempt - 1))
                sys.stderr.write(f"⚠️ [Retry {attempt}/{max_retries}] HTTP {e.code} received from Gemini API. Backing off {wait_sec:.1f}s...\n")
                time.sleep(wait_sec)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < max_retries:
                wait_sec = retry_delay * (2 ** (attempt - 1))
                sys.stderr.write(f"⚠️ [Retry {attempt}/{max_retries}] Network error: {e}. Retrying in {wait_sec:.1f}s...\n")
                time.sleep(wait_sec)
                continue
            raise

    if last_err:
        raise last_err
    return ""

def main():
    parser = argparse.ArgumentParser(description="Cloud-Native Gemini Audio Transcription for Lecture Chunks")
    parser.add_argument("--manifest", default="chunks_manifest.json", help="Path to chunks_manifest.json")
    parser.add_argument("--chunks-dir", default="./chunks", help="Directory containing audio chunks")
    parser.add_argument("--output-dir", default="./transcripts", help="Output directory for text transcripts")
    parser.add_argument("--model", default="gemini-2.0-flash", help="Gemini model name")
    parser.add_argument("--api-key", default=None, help="Gemini API Key (optional, defaults to GEMINI_API_KEY or GOOGLE_API_KEY env vars)")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if not api_key:
        print("=" * 75)
        print("🚫 GEMINI_API_KEY / GOOGLE_API_KEY NOT FOUND IN ENVIRONMENT")
        print("=" * 75)
        print("📌 MANDATORY ARCHITECTURAL POLICY FOR AUDIO TRANSCRIPTION:")
        print("   1. STRICTLY FORBIDDEN: NEVER install Whisper, faster-whisper, torch, or CUDA.")
        print("      Downloading multi-gigabyte wheels wastes user bandwidth and causes driver conflicts.")
        print()
        print("   2. IN-SESSION MULTIMODAL TRANSCRIPTION (Recommended for Antigravity Agents):")
        print("      - Antigravity's `view_file` tool natively supports binary audio files (.m4a, .mp3)!")
        print("      - Call `view_file(AbsolutePath=\"<chunk_path>\")` for each chunk in ./chunks.")
        print("      - Gemini natively hears the audio in-context and transcribes it with exact medical terminology.")
        print("      - Save each output to `transcripts/part01.txt`, `transcripts/part02.txt`, etc.")
        print()
        print("   3. BATCH CLOUD EXECUTION:")
        print("      - Export GEMINI_API_KEY=your_key")
        print("      - Rerun: uv run python scripts/transcribe_chunks.py")
        print("=" * 75)
        sys.exit(2)
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    manifest_path = args.manifest
    chunks = []
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
    elif os.path.isdir(args.chunks_dir):
        files = sorted(os.listdir(args.chunks_dir))
        for f in files:
            if f.endswith((".m4a", ".mp3", ".wav", ".ogg")):
                chunks.append({
                    "filename": f,
                    "path": os.path.join(args.chunks_dir, f),
                    "timestamp_start": "00:00:00"
                })
                
    if not chunks:
        print(f"❌ Error: No chunks found in manifest '{manifest_path}' or directory '{args.chunks_dir}'.")
        sys.exit(1)
        
    print(f"🎙️ Starting Gemini Cloud Transcription for {len(chunks)} audio chunks with {args.model}...")
    for idx, c in enumerate(chunks, 1):
        c_path = c.get("path") or os.path.join(args.chunks_dir, c["filename"])
        out_name = f"part{idx:02d}.txt"
        out_path = os.path.join(args.output_dir, out_name)
        
        if os.path.exists(out_path) and os.path.getsize(out_path) > 50:
            print(f"   [Skip] Chunk {idx}/{len(chunks)} already transcribed: {out_name}")
            continue
            
        t_start = c.get("timestamp_start", "00:00:00")
        t_end = format_seconds_to_time(int(c.get("end_sec", 0))) if "end_sec" in c else ""
        range_str = f"[{t_start} - {t_end}]" if t_end else f"[{t_start}]"
        
        print(f"   Transcribing Chunk {idx}/{len(chunks)}: {os.path.basename(c_path)} {range_str}...")
        try:
            transcript = transcribe_chunk_with_gemini_rest(c_path, api_key, model=args.model)
            with open(out_path, "w", encoding="utf-8") as out_f:
                header = f"{range_str} بیانات استاد - بخش {idx}\n\n"
                out_f.write(header + transcript + "\n")
            print(f"   ✅ Saved {out_name} ({len(transcript.split())} words)")
        except Exception as e:
            print(f"   ❌ Failed to transcribe chunk {idx}: {e}", file=sys.stderr)
            
    print(f"\n🎉 All chunks processed. Transcripts saved in '{args.output_dir}'.")

if __name__ == "__main__":
    main()
