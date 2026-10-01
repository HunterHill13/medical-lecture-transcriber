#!/usr/bin/env python3
"""
chunk_audio.py: Splits a long lecture audio file into lightweight chunks (under 10 MB each)
with overlapping boundaries for seamless, high-accuracy multimodal transcription with Gemini.
"""

import os
import sys
import json
import subprocess
import argparse

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from text_utils import format_seconds_to_time, DEFAULT_CHUNK_LENGTH_SEC

def get_audio_duration(file_path, explicit_duration=None):
    if explicit_duration is not None and explicit_duration > 0:
        return float(explicit_duration)
        
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        # Fallback probe via ffmpeg
        res = subprocess.run(["ffmpeg", "-i", file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in res.stderr.splitlines():
            if "Duration:" in line:
                dur_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
                
        raise RuntimeError(
            f"Could not determine audio duration for '{file_path}'. "
            "Please ensure ffmpeg or ffprobe is installed and on PATH, or pass --duration explicitly."
        )

def compute_chunk_ranges(total_sec: float, chunk_len: int = DEFAULT_CHUNK_LENGTH_SEC, overlap: int = 10) -> list[dict]:
    """
    Deterministically computes chunk start, duration, and overlap boundaries.
    Prevents redundant ghost chunks if trailing duration <= overlap.
    """
    ranges = []
    start = 0.0
    idx = 1
    while start < total_sec:
        # Prevent redundant ghost chunk if remaining audio was already covered by previous chunk's overlap
        if idx > 1 and (total_sec - start) <= overlap:
            break
            
        duration = min(float(chunk_len + overlap), total_sec - start)
        time_str = format_seconds_to_time(int(start))
        out_name = f"chunk_{idx:02d}.m4a"
        
        ranges.append({
            "index": idx,
            "filename": out_name,
            "start_sec": start,
            "duration_sec": duration,
            "end_sec": start + duration,
            "timestamp_start": time_str,
            "overlap_sec": overlap if idx > 1 else 0
        })
        
        start += chunk_len
        idx += 1
        
    return ranges

def chunk_audio(input_file, output_dir, chunk_len=540, overlap=10, bitrate="48k", explicit_duration=None):
    os.makedirs(output_dir, exist_ok=True)
    total_sec = get_audio_duration(input_file, explicit_duration=explicit_duration)
    chunk_specs = compute_chunk_ranges(total_sec, chunk_len=chunk_len, overlap=overlap)
    total_chunks = len(chunk_specs)
    print(f"📦 Splitting audio into {total_chunks} chunks ({chunk_len}s + {overlap}s overlap, bitrate: {bitrate})...")
    
    chunks = []
    for idx, spec in enumerate(chunk_specs, 1):
        out_path = os.path.join(output_dir, spec["filename"])
        cmd = [
            "ffmpeg", "-y", "-ss", str(spec["start_sec"]), "-i", input_file,
            "-t", str(spec["duration_sec"]), "-ac", "1", "-c:a", "aac", "-b:a", bitrate,
            out_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        except subprocess.CalledProcessError as e:
            err_output = e.stderr.strip() if e.stderr else "Unknown error"
            raise RuntimeError(f"FFmpeg error on chunk {idx}/{total_chunks} ({spec['filename']}): {err_output}") from e
            
        chunk_entry = dict(spec)
        chunk_entry["path"] = os.path.abspath(out_path)
        chunks.append(chunk_entry)
        
    print(f"✅ Successfully generated {len(chunks)} chunks in '{output_dir}'.")
    return chunks

def main():
    parser = argparse.ArgumentParser(description="Split lecture audio into lightweight chunks for Gemini.")
    parser.add_argument("input_audio", help="Path to input audio file")
    parser.add_argument("--output-dir", default="./scratch_chunks", help="Output directory for chunks")
    parser.add_argument("--chunk-len", type=int, default=DEFAULT_CHUNK_LENGTH_SEC, help=f"Chunk length in seconds (default {DEFAULT_CHUNK_LENGTH_SEC} = {DEFAULT_CHUNK_LENGTH_SEC//60} min)")
    parser.add_argument("--overlap", type=int, default=10, help="Overlap between chunks in seconds (default 10s)")
    parser.add_argument("--bitrate", default="48k", help="Audio bitrate (default 48k, use 32k for ultra-lightweight)")
    parser.add_argument("--duration", type=float, default=None, help="Explicit total duration in seconds (overrides auto-probing)")
    parser.add_argument("--output-json", default="chunks_manifest.json", help="Path to output manifest JSON")
    
    args = parser.parse_args()
    chunks = chunk_audio(
        args.input_audio, args.output_dir, args.chunk_len, args.overlap,
        bitrate=args.bitrate, explicit_duration=args.duration
    )
    
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
        
    print(f"Success! {len(chunks)} chunks created in '{args.output_dir}'. Manifest saved to '{args.output_json}'.")

if __name__ == "__main__":
    main()
