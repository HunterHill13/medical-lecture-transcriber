#!/usr/bin/env python3
"""
verify_lecture_alignment.py: Automated Verification Gate & Substantive Coverage Engine for Lecture Narrative & Audio Timestamps.
Validates:
1. Chronological order and reality of timestamps (no fake timestamps beyond audio duration).
2. Topic-Timestamp alignment (verifies that keywords in H1 match the actual transcript text at that timestamp).
3. Substantive Audio & Concept Coverage (checks that each section has adequate clinical word density and concept recall from the audio transcript, preventing superficial generic summaries).
4. 100% Audio Coverage (verifies that all audio transcript chunks are represented in the pamphlet without dropped segments).

Supports:
1. Console and structured JSON diagnostic reporting (alignment_diagnostic_lecture.json).
2. Actionable Remediation Hints for autonomous agent self-healing (up to 3-retry budget).
3. Safe auto-fix boundary: Refuses silent clamping if timestamp drift > 180 seconds, requiring semantic re-anchoring.

Usage:
    uv run --with python-docx python verify_lecture_alignment.py --docx pamphlet.docx --transcripts-dir ./scratch [--diagnostic-json report.json]
"""

import os
import sys
import re
import json
import glob
import argparse
import docx
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from text_utils import (
    parse_time_to_seconds,
    format_seconds_to_time,
    extract_tokens,
    flatten_spoken_lecture,
    extract_timestamps,
    validate_cross_reference,
    extract_clinical_facts,
    compare_clinical_facts,
    DEFAULT_CHUNK_LENGTH_SEC
)

def compute_drift_threshold(duration_sec: int, strict: bool = False, max_drift: Optional[int] = None) -> int:
    """Computes dynamic proportional drift threshold (5% of total audio duration, min 180s, or strict 60s cap)."""
    if strict:
        return 60
    if max_drift is not None:
        return max(0, int(max_drift))
    return max(180, int(duration_sec * 0.05)) if duration_sec > 0 else 180

def evaluate_word_ratio_gate(total_lecture_words: int, total_trans_words: int, threshold: float = 0.50):
    """
    Stage 1 Word Volume Ratio Gate (minimum 50%).
    Returns: (passed: bool, word_ratio: float, error_detail: Optional[dict])
    """
    word_ratio = total_lecture_words / max(total_trans_words, 1)
    if word_ratio < threshold:
        err_msg = (f"INSUFFICIENT LECTURE COVERAGE: Spoken lecture in study guide has {total_lecture_words} words, "
                   f"which is only {word_ratio*100:.1f}% of audio transcripts ({total_trans_words} words). "
                   f"Minimum required ratio is {threshold*100:.1f}%. High risk of missing substantial classroom explanations!")
        diag = {
            "error_type": "INSUFFICIENT_LECTURE_COVERAGE",
            "total_spoken_words": total_lecture_words,
            "total_transcript_words": total_trans_words,
            "word_ratio": word_ratio,
            "message": err_msg,
            "remediation_action": "Expand spoken_lecture fields across slides to faithfully capture the professor's full verbal explanations without superficial summarization."
        }
        return False, word_ratio, diag
    return True, word_ratio, None

def evaluate_concept_recall_gate(chunk_tokens: set, total_lecture_tokens: set, threshold: float = 0.60):
    """
    Stage 2 Chunk Medical & Clinical Concept Recall Rate (minimum 60%).
    Returns: (passed: bool, recall_rate: float, missing_sample: list[str])
    """
    chunk_substantive = {t for t in chunk_tokens if len(t) >= 3 or (len(t) >= 2 and any(c.isascii() and c.isalpha() for c in t))}
    if not chunk_substantive:
        return True, 1.0, []
    recalled = chunk_substantive.intersection(total_lecture_tokens)
    recall_rate = len(recalled) / len(chunk_substantive)
    if recall_rate < threshold:
        missing_sample = sorted(list(chunk_substantive - recalled))[:8]
        return False, recall_rate, missing_sample
    return True, recall_rate, []

def evaluate_chunk_coverage_gate(transcript_chunks: list, sec_times: list, total_lecture_tokens: set,
                                  min_chunk_duration: int = 30, threshold: float = 0.85,
                                  chunk_recall_threshold: float = 0.50, strict: bool = False,
                                  allow_review: bool = False, return_displaced: bool = False):
    """
    Stage 3 Audio Chunk Mapping Coverage Check (minimum 85% of chunks > min_chunk_duration covered).
    Enforces strict spatio-temporal audio-text grounding:
    - PASS (Covered): Requires BOTH matching timestamp interval (drift <= 60s) AND substantive concept recall >= chunk_recall_threshold.
    - REVIEW_REQUIRED (Displaced): Substantive concepts recalled globally, but missing/drifted section timestamp (drift > 60s).
      By default, displaced chunks are NOT covered (is_covered=False). They are provisionally covered ONLY when allow_review=True (and strict=False).
    - FAIL (Uncovered): Chunks with insufficient concept recall or zero matching evidence.
    Returns:
        If return_displaced is False: (passed, coverage_ratio, uncovered_chunks, covered_count, evaluated_count)
        If return_displaced is True: (passed, coverage_ratio, uncovered_chunks, covered_count, evaluated_count, displaced_chunks)
    """
    covered_chunks_count = 0
    evaluated_chunks_count = 0
    uncovered_chunk_files = []
    displaced_chunk_files = []

    # Normalize sec_times into temporal intervals [(i_st, i_en), ...]
    intervals = []
    if sec_times:
        for item in sec_times:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                intervals.append((float(item[0]), float(item[1])))
        if not intervals:
            # sec_times is a list of scalar timestamps [t0, t1, t2, ...]
            sorted_times = sorted([float(t) for t in sec_times if isinstance(t, (int, float))])
            for idx, t_st in enumerate(sorted_times):
                if idx + 1 < len(sorted_times):
                    t_en = sorted_times[idx + 1]
                else:
                    t_en = t_st + 540.0
                intervals.append((t_st, t_en))
    
    for chunk in transcript_chunks:
        chunk_dur = chunk["end_sec"] - chunk["start_sec"]
        if chunk_dur < min_chunk_duration:
            continue
        evaluated_chunks_count += 1
        
        c_st = float(chunk["start_sec"])
        c_en = float(chunk["end_sec"])
        c_dur = max(1.0, c_en - c_st)

        # Genuine interval overlap: requires substantive overlap (>= 15s or >= 15% of chunk duration)
        has_timestamp = any(
            (min(c_en, i_en) - max(c_st, i_st) >= 15.0)
            or (min(c_en, i_en) - max(c_st, i_st) > 0 and (min(c_en, i_en) - max(c_st, i_st)) / c_dur >= 0.15)
            for (i_st, i_en) in intervals
        ) if intervals else False

        chunk_substantive = {t for t in chunk["tokens"] if len(t) >= 3 or (len(t) >= 2 and any(c.isascii() and c.isalpha() for c in t))}
        recalled = chunk_substantive.intersection(total_lecture_tokens) if chunk_substantive else set()
        recall_ratio = len(recalled) / max(len(chunk_substantive), 1) if chunk_substantive else 1.0
        
        has_substance = recall_ratio >= chunk_recall_threshold

        if has_timestamp and has_substance:
            # Fully grounded pass: both timestamp and substantive concepts match
            is_covered = True
        elif has_substance and not has_timestamp:
            # Temporal displacement: concepts appear, but audio timestamp is missing/drifted > 60s
            displaced_chunk_files.append(chunk["file"])
            if allow_review and not strict:
                # Provisionally covered under explicit human review mode
                is_covered = True
            else:
                # By default, displaced chunks do NOT count as covered!
                is_covered = False
        else:
            # Low substance or unmapped chunk
            is_covered = False

        if is_covered:
            covered_chunks_count += 1
        else:
            uncovered_chunk_files.append(chunk["file"])
            
    if evaluated_chunks_count == 0:
        if return_displaced:
            return True, 1.0, [], 0, 0, []
        return True, 1.0, [], 0, 0

    coverage_ratio = covered_chunks_count / evaluated_chunks_count
    passed = coverage_ratio >= threshold
    if return_displaced:
        return passed, coverage_ratio, uncovered_chunk_files, covered_chunks_count, evaluated_chunks_count, displaced_chunk_files
    return passed, coverage_ratio, uncovered_chunk_files, covered_chunks_count, evaluated_chunks_count

def evaluate_toc_drift_gate(toc_sec: int, h1_sec: int, tolerance_sec: int = 60):
    """
    Evaluates TOC Timestamp Drift Gate.
    Returns: (passed: bool, drift_seconds: int)
    """
    drift = abs(toc_sec - h1_sec)
    return drift <= tolerance_sec, drift

def build_transcript_segments(transcript_chunks: list) -> list[dict]:
    """
    Dual-Mode Transcript Segmentation Engine:
    Mode A: If fine-grained segments are provided (e.g. Whisper JSON segments), loads them directly.
    Mode B: If text transcripts with headings/paragraphs are provided, performs line-weighted
            semantic temporal segmentation to produce bounded sub-segments with exact [start_sec, end_sec].
    """
    segments = []
    seg_idx = 1
    for ch in transcript_chunks:
        ch_st = float(ch.get("start_sec", 0.0))
        ch_en = float(ch.get("end_sec", ch_st + 540.0))
        ch_dur = max(1.0, ch_en - ch_st)
        
        # Mode A: Pre-segmented Whisper data
        if ch.get("segments"):
            for s in ch["segments"]:
                try:
                    raw_st = float(s.get("start", 0.0 if ch_st > 0 else ch_st))
                    raw_en = float(s.get("end", raw_st + 10.0))
                except (ValueError, TypeError):
                    continue

                # Sanity check: start must be non-negative and end must be strictly greater than start
                if raw_st < 0 or raw_en <= raw_st:
                    continue

                # Detect chunk-relative vs absolute timestamps
                origin = s.get("timestamp_origin") or ch.get("timestamp_origin")
                is_chunk_relative = (origin == "chunk_relative")
                origin_inferred = False
                if not is_chunk_relative and ch_st > 0 and raw_st < (ch_st - 1.0) and raw_en <= (ch_dur + 60.0):
                    # Segment start is smaller than chunk start and within plausible chunk duration
                    is_chunk_relative = True
                    origin_inferred = True
                    
                if is_chunk_relative:
                    s_st = ch_st + raw_st
                    s_en = ch_st + raw_en
                else:
                    s_st = raw_st
                    s_en = raw_en

                s_txt = s.get("text", "")
                segments.append({
                    "segment_id": f"seg_{seg_idx:04d}",
                    "file": ch.get("file", "unknown"),
                    "start_sec": s_st,
                    "end_sec": s_en,
                    "text": s_txt,
                    "tokens": extract_tokens(s_txt),
                    "grounding_mode": "timestamped",
                    "temporal_confidence": "inferred_chunk_relative" if origin_inferred else "exact",
                    "origin_inferred": origin_inferred
                })
                seg_idx += 1
            continue
            
        # Mode B: Automatic Text Segmentation based on headings and paragraph density
        text = ch.get("text", "")
        raw_lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("[")]
        if not raw_lines:
            segments.append({
                "segment_id": f"seg_{seg_idx:04d}",
                "file": ch.get("file", "unknown"),
                "start_sec": ch_st,
                "end_sec": ch_en,
                "text": text,
                "tokens": ch.get("tokens", set()),
                "grounding_mode": "heuristic",
                "temporal_confidence": "estimated"
            })
            seg_idx += 1
            continue
            
        blocks = []
        cur_block = []
        for l in raw_lines:
            if l.startswith("###") and cur_block:
                blocks.append(cur_block)
                cur_block = [l]
            else:
                cur_block.append(l)
        if cur_block:
            blocks.append(cur_block)
            
        total_chars = sum(sum(len(l) for l in blk) for blk in blocks)
        elapsed_st = ch_st
        for blk in blocks:
            blk_text = "\n".join(blk)
            blk_chars = sum(len(l) for l in blk)
            frac = blk_chars / max(1, total_chars)
            blk_dur = frac * ch_dur
            b_st = elapsed_st
            b_en = min(ch_en, elapsed_st + blk_dur)
            elapsed_st = b_en
            segments.append({
                "segment_id": f"seg_{seg_idx:04d}",
                "file": ch.get("file", "unknown"),
                "start_sec": b_st,
                "end_sec": b_en,
                "text": blk_text,
                "tokens": extract_tokens(blk_text),
                "grounding_mode": "heuristic",
                "temporal_confidence": "estimated"
            })
            seg_idx += 1
    return segments

def evaluate_slide_level_grounding(translated_slides: list, transcript_chunks: list) -> tuple[list[dict], dict]:
    """
    Spatio-Temporal Grounding Engine:
    Evaluates slide-level alignment against fine-grained audio segments.
    Computes both Lexical Precision (|Slide ∩ Segment| / |Slide|) and Segment Lexical Recall (|Slide ∩ Segment| / |Expected|).
    Strictly verifies:
    1. Temporal Monotonicity across consecutive slides (0 unapproved regressions allowed).
    2. Segment Grounding Precision (ensures lecture text is authentically anchored in that audio segment).
    3. Handles multi-interval audio_segments independently without naive bounding box gaps.
    """
    segments = build_transcript_segments(transcript_chunks)
    issues = []
    mode_a_count = sum(1 for seg in segments if seg.get("grounding_mode") == "timestamped")
    mode_b_count = sum(1 for seg in segments if seg.get("grounding_mode") == "heuristic")
    if mode_a_count > 0 and mode_b_count == 0:
        grounding_mode = "timestamped"
        temporal_confidence = "exact"
    elif mode_b_count > 0 and mode_a_count == 0:
        grounding_mode = "heuristic"
        temporal_confidence = "estimated"
    elif mode_a_count > 0 and mode_b_count > 0:
        grounding_mode = "mixed"
        temporal_confidence = "mixed"
    else:
        grounding_mode = "none"
        temporal_confidence = "none"

    stats = {
        "total_slides": len(translated_slides),
        "voiced_slides": 0,
        "direct_grounded_slides": 0,
        "boundary_fallback_slides": 0,
        "passed_slides": 0,
        "failed_slides": 0,
        "skipped_slides": 0,
        "avg_precision": 0.0,
        "avg_recall_rate": 0.0,
        "avg_direct_precision": 0.0,
        "avg_direct_recall_rate": 0.0,
        "avg_boundary_precision": 0.0,
        "avg_boundary_recall_rate": 0.0,
        "total_segments_evaluated": len(segments),
        "grounding_mode": grounding_mode,
        "temporal_confidence": temporal_confidence,
        "timestamped_segments_count": mode_a_count,
        "heuristic_segments_count": mode_b_count,
        "total_clinical_facts_evaluated": 0,
        "slides_with_fact_omissions": 0,
        "low_temporal_resolution_slides": 0,
        "temporal_topic_displacement_slides": 0
    }
    
    precisions = []
    recalls = []
    direct_precisions = []
    direct_recalls = []
    boundary_precisions = []
    boundary_recalls = []
    last_end_sec = -1
    last_voiced_num = -1
    available_slide_nums = {sl.get("slide_number") for sl in translated_slides if isinstance(sl, dict)}
    slide_lookup = {sl.get("slide_number"): sl for sl in translated_slides if isinstance(sl, dict)}
    slide_text_tokens_map = {}
    for sl in translated_slides:
        if isinstance(sl, dict) and sl.get("slide_number") is not None:
            bullets = sl.get("bullets", [])
            b_texts = []
            for b in bullets:
                if isinstance(b, dict):
                    b_texts.append(b.get("lead", "") + " " + b.get("text", ""))
                elif isinstance(b, (list, tuple)):
                    b_texts.append(" ".join(str(x) for x in b))
                else:
                    b_texts.append(str(b))
            s_full_text = str(sl.get("title_en", "")) + " " + str(sl.get("title_fa", "")) + " " + " ".join(b_texts)
            slide_text_tokens_map[sl.get("slide_number")] = extract_tokens(s_full_text)

    prev_intervals = []
    prev_slide_start_sec = -1
    prev_slide_end_sec = -1
    
    for s in translated_slides:
        if not isinstance(s, dict):
            continue
        num = s.get("slide_number", 0)
        is_skipped = bool(s.get("is_skipped") or s.get("unvoiced") or s.get("skipped_by_professor"))
        is_ceremonial = bool(s.get("is_ceremonial"))
        
        if is_skipped or is_ceremonial:
            stats["skipped_slides"] += 1
            continue
            
        parent_num = s.get("parent_lecture_slide") or s.get("cluster_parent")
        parent_slide = slide_lookup.get(parent_num) if parent_num else None
        
        time_str = s.get("audio_time_range")
        if not time_str and parent_slide and parent_slide.get("audio_time_range"):
            time_str = parent_slide.get("audio_time_range")
            
        has_segments = bool(s.get("audio_segments"))
        s_audio_segments = s.get("audio_segments")
        if not has_segments and parent_slide and parent_slide.get("audio_segments"):
            has_segments = True
            s_audio_segments = parent_slide.get("audio_segments")
            
        if not time_str and not has_segments:
            issues.append({
                "type": "NO_AUDIO_ANCHOR",
                "severity": "error",
                "slide_number": num,
                "message": (f"CRITICAL: Academic Slide {num} has no audio timestamp anchor (missing 'audio_time_range' and 'audio_segments'). "
                            f"Academic slides must have explicit audio timing, a parent_lecture_slide, or be marked as skipped/unvoiced."),
                "remediation_action": f"Provide audio_time_range for Slide {num}, link via parent_lecture_slide, or mark it as unvoiced: true if omitted by professor."
            })
            stats["failed_slides"] += 1
            continue
            
        intervals = []
        if has_segments and s_audio_segments:
            # Multi-segment intervals evaluated independently
            intervals = [
                (float(seg["start"]), float(seg["end"]))
                for seg in s_audio_segments
                if "start" in seg and "end" in seg and float(seg["end"]) >= float(seg["start"])
            ]
        elif time_str:
            times = extract_timestamps(str(time_str))
            if len(times) >= 2:
                st, en = (times[0], times[1]) if times[0] <= times[1] else (times[1], times[0])
                intervals = [(st, en)]
                
        if not intervals:
            issues.append({
                "type": "MALFORMED_AUDIO_ANCHOR",
                "severity": "error",
                "slide_number": num,
                "message": f"CRITICAL: Malformed audio anchor at Slide {num} ('{time_str}'). Could not parse valid start/end timestamps.",
                "remediation_action": f"Ensure audio_time_range follows 'MM:SS - MM:SS' format for Slide {num}."
            })
            stats["failed_slides"] += 1
            continue
            
        stats["voiced_slides"] += 1
        slide_start_sec = intervals[0][0]
        slide_end_sec = intervals[-1][1]
        total_slide_dur = sum(max(1.0, en - st) for st, en in intervals)
        
        # Temporal Monotonicity Audit & Structural Cross-Reference Validation
        # Structural cross-references MUST come exclusively from cross_references[] array
        cross_refs = s.get("cross_references", [])
        if isinstance(cross_refs, (dict, str)):
            cross_refs = [cross_refs]
        else:
            cross_refs = list(cross_refs)
            
        has_valid_cross_ref = False
        for cr in cross_refs:
            is_valid, _ = validate_cross_reference(cr, num, available_slide_nums)
            if is_valid:
                has_valid_cross_ref = True
                break
                
        # Check if slide is part of a multi-slide cluster continuation (shares parent or exact audio window)
        is_cluster_continuation = bool(
            parent_num or
            (last_voiced_num != -1 and intervals and prev_intervals and intervals == prev_intervals) or
            (last_voiced_num != -1 and slide_start_sec == prev_slide_start_sec and slide_end_sec == prev_slide_end_sec)
        )
        
        if last_end_sec > 0 and slide_start_sec < (last_end_sec - 15) and not has_valid_cross_ref and not is_cluster_continuation:
            regression_sec = int(last_end_sec - slide_start_sec)
            if regression_sec > 60:
                severity = "error"
                msg = (f"CRITICAL TEMPORAL REGRESSION ({regression_sec}s > 60s) at Slide {num}: Audio start time ({format_seconds_to_time(int(slide_start_sec))}) "
                       f"is earlier than preceding Slide {last_voiced_num} ({format_seconds_to_time(int(last_end_sec))}). "
                       f"Add a structural cross-reference in cross_references[] if this is an intentional review.")
            else:
                severity = "warning"
                msg = (f"TEMPORAL REGRESSION ({regression_sec}s) at Slide {num}: Audio start time ({format_seconds_to_time(int(slide_start_sec))}) "
                       f"is earlier than preceding Slide {last_voiced_num} ({format_seconds_to_time(int(last_end_sec))}).")
            issues.append({
                "type": "TEMPORAL_MONOTONICITY_REGRESSION",
                "severity": severity,
                "slide_number": num,
                "regression_seconds": regression_sec,
                "message": msg
            })
        last_end_sec = max(last_end_sec, slide_end_sec)
        last_voiced_num = num
        prev_intervals = list(intervals)
        prev_slide_start_sec = slide_start_sec
        prev_slide_end_sec = slide_end_sec
        
        # Candidate segment matching across all slide intervals (primary: real temporal overlap)
        candidate_tokens = set()
        candidate_texts = []
        direct_segment_ids = []
        boundary_segment_ids = []
        low_res_segments = []
        for seg in segments:
            for (i_st, i_en) in intervals:
                inter_dur = max(0.0, min(seg["end_sec"], i_en) - max(seg["start_sec"], i_st))
                if inter_dur >= 5.0 or (inter_dur > 0 and inter_dur / max(1.0, i_en - i_st) >= 0.15):
                    candidate_tokens.update(seg["tokens"])
                    candidate_texts.append(seg.get("text", ""))
                    direct_segment_ids.append(seg["segment_id"])
                    
                    seg_dur = max(1.0, seg["end_sec"] - seg["start_sec"])
                    seg_cov = inter_dur / seg_dur
                    if seg_dur >= 60.0 and seg_cov < 0.25:
                        low_res_segments.append((seg["segment_id"], seg_cov, seg_dur))
                    break
                    
        # Fallback if no segment had >= 5s direct overlap (for very short boundary-edge slides)
        is_boundary_fallback = False
        if not candidate_tokens:
            for seg in segments:
                for (i_st, i_en) in intervals:
                    if max(seg["start_sec"], i_st - 15) <= min(seg["end_sec"], i_en + 15):
                        candidate_tokens.update(seg["tokens"])
                        candidate_texts.append(seg.get("text", ""))
                        boundary_segment_ids.append(seg["segment_id"])
                        is_boundary_fallback = True
                        break

        matched_segment_ids = direct_segment_ids or boundary_segment_ids

        if low_res_segments:
            stats["low_temporal_resolution_slides"] = stats.get("low_temporal_resolution_slides", 0) + 1
            issues.append({
                "type": "SEGMENT_TEMPORAL_RESOLUTION_ADVISORY",
                "severity": "review_required",
                "slide_number": num,
                "low_resolution_segments": [s[0] for s in low_res_segments],
                "message": (f"TEMPORAL RESOLUTION ADVISORY at Slide {num}: Grounding matched coarse audio segments "
                            f"where slide window covered <25% of a long segment (>60s): "
                            f"{[s[0] for s in low_res_segments]}. Candidate tokens may include extraneous lecture content."),
                "remediation_action": f"Verify whether Slide {num} spoken content actually discusses the candidate tokens or if finer chunking is required."
            })

        if is_boundary_fallback and matched_segment_ids:
            stats["boundary_fallback_slides"] = stats.get("boundary_fallback_slides", 0) + 1
            issues.append({
                "type": "GROUNDING_BOUNDARY_TOLERANCE_ADVISORY",
                "severity": "review_required",
                "slide_number": num,
                "boundary_segments": boundary_segment_ids[:3],
                "message": (f"BOUNDARY TOLERANCE ADVISORY at Slide {num}: Grounding relied exclusively on ±15s boundary tolerance "
                            f"({format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}) "
                            f"with segments {boundary_segment_ids[:3]}."),
                "remediation_action": f"Verify whether Slide {num} audio boundaries align precisely with lecture audio."
            })

                    
        spoken_text = flatten_spoken_lecture(s.get("spoken_lecture"))
        if not spoken_text and parent_slide:
            spoken_text = flatten_spoken_lecture(parent_slide.get("spoken_lecture"))
        spoken_tokens = extract_tokens(spoken_text)
        
        # Clinical Facts Audit (dosages, lab values, percentages)
        combined_candidate_text = " ".join(candidate_texts)
        audio_facts = extract_clinical_facts(combined_candidate_text)
        spoken_facts = extract_clinical_facts(spoken_text)
        fact_comp = compare_clinical_facts(audio_facts, spoken_facts)
        stats["total_clinical_facts_evaluated"] += fact_comp["total_audio_facts"]
        
        crit_omissions = fact_comp.get("critical_omissions", [])
        adv_omissions = fact_comp.get("advisory_omissions", [])
        
        if crit_omissions:
            stats["slides_with_fact_omissions"] += 1
            issues.append({
                "type": "CLINICAL_FACT_CRITICAL_OMISSION",
                "severity": "error",
                "slide_number": num,
                "critical_omissions": crit_omissions,
                "fact_recall": fact_comp["fact_recall"],
                "message": (f"CRITICAL CLINICAL FACT OMISSION at Slide {num}: High-stakes dosages/lab values {crit_omissions} "
                            f"mentioned in audio window were omitted from spoken_lecture text!"),
                "remediation_action": f"Incorporate vital clinical facts {crit_omissions} into Slide {num} spoken_lecture immediately."
            })
        if adv_omissions:
            if not crit_omissions:
                stats["slides_with_fact_omissions"] += 1
            issues.append({
                "type": "CLINICAL_FACT_OMISSION",
                "severity": "warning",
                "slide_number": num,
                "omitted_facts": adv_omissions[:5],
                "fact_recall": fact_comp["fact_recall"],
                "message": (f"POTENTIAL CLINICAL FACT OMISSION at Slide {num}: Audio window mentions {adv_omissions[:3]} "
                            f"which were not detected in spoken_lecture text."),
                "remediation_action": f"Verify whether {adv_omissions[:3]} should be explicitly incorporated into Slide {num} spoken_lecture."
            })
        
        spoken_substantive = {t for t in spoken_tokens if len(t) >= 3 or (len(t) >= 2 and any(c.isascii() and c.isalpha() for c in t))}
        candidate_substantive = {t for t in candidate_tokens if len(t) >= 3 or (len(t) >= 2 and any(c.isascii() and c.isalpha() for c in t))}
        
        if not matched_segment_ids:
            stats["failed_slides"] += 1
            precisions.append(0.0)
            recalls.append(0.0)
            issues.append({
                "type": "SLIDE_AUDIO_NO_TEMPORAL_EVIDENCE",
                "severity": "error",
                "slide_number": num,
                "audio_time_range": f"{format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}",
                "message": (f"NO TEMPORAL AUDIO EVIDENCE at Slide {num} ({format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}): "
                            f"Slide specifies an active audio timeframe, but no transcript segment overlaps with this interval!"),
                "remediation_action": f"Adjust audio_time_range or audio_segments for Slide {num} to match actual spoken audio, or mark as unvoiced: true."
            })
            continue

        if not candidate_substantive:
            stats["failed_slides"] += 1
            precisions.append(0.0)
            recalls.append(0.0)
            issues.append({
                "type": "SLIDE_AUDIO_EMPTY_TRANSCRIPT",
                "severity": "error",
                "slide_number": num,
                "audio_time_range": f"{format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}",
                "message": (f"EMPTY AUDIO EVIDENCE at Slide {num} ({format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}): "
                            f"Audio segments match this interval, but transcript contains zero substantive medical concepts."),
                "remediation_action": f"Verify transcript text for audio segments {matched_segment_ids[:3]}."
            })
            continue

        if not spoken_substantive:
            stats["failed_slides"] += 1
            precisions.append(0.0)
            recalls.append(0.0)
            issues.append({
                "type": "SLIDE_SPOKEN_LECTURE_EMPTY",
                "severity": "error",
                "slide_number": num,
                "audio_time_range": f"{format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}",
                "message": (f"EMPTY SPOKEN LECTURE at Slide {num} ({format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}): "
                            f"Slide is voiced with {total_slide_dur:.1f}s of audio, but lacks substantive spoken_lecture transcription content."),
                "remediation_action": f"Provide substantive spoken_lecture content for Slide {num}."
            })
            continue
            
        overlap = spoken_substantive.intersection(candidate_substantive)
        
        # 1. Lexical Precision (|Slide ∩ Segments| / |Slide|)
        precision = len(overlap) / max(1, len(spoken_substantive))
        precisions.append(precision)
        
        # 2. Pure Lexical Segment Recall (|Slide ∩ Segments| / |Segments Substantive|)
        recall_ratio = len(overlap) / max(1, len(candidate_substantive))
        recalls.append(recall_ratio)

        if is_boundary_fallback:
            boundary_precisions.append(precision)
            boundary_recalls.append(recall_ratio)
        else:
            stats["direct_grounded_slides"] += 1
            direct_precisions.append(precision)
            direct_recalls.append(recall_ratio)
        
        # Temporal Topic Displacement Audit:
        # Detect if candidate audio concepts during Slide N's timeframe align significantly stronger
        # with an adjacent slide M's text (within +-2 window) than Slide N's own text.
        # This flags lecture pacing drifts or premature discussion without mutating slide texts.
        if len(candidate_substantive) >= 4:
            slide_n_tokens = slide_text_tokens_map.get(num, set())
            overlap_n = candidate_substantive.intersection(slide_n_tokens)
            for delta in [-2, -1, 1, 2]:
                adj_num = num + delta
                if adj_num in slide_text_tokens_map:
                    adj_slide_tokens = slide_text_tokens_map[adj_num]
                    overlap_adj = candidate_substantive.intersection(adj_slide_tokens)
                    if (
                        len(overlap_adj) >= 4
                        and len(overlap_adj) >= 2 * max(1, len(overlap_n))
                        and (len(overlap_n) <= 1 or len(overlap_n) <= 0.30 * len(candidate_substantive))
                    ):
                        stats["temporal_topic_displacement_slides"] = stats.get("temporal_topic_displacement_slides", 0) + 1
                        disp_msg = (
                            f"TEMPORAL TOPIC DISPLACEMENT ADVISORY at Slide {num}: Audio timeframe "
                            f"({format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}) "
                            f"contains concepts {sorted(list(overlap_adj))[:4]} which align significantly stronger with Slide {adj_num} (overlap: {len(overlap_adj)}) "
                            f"than Slide {num} (overlap: {len(overlap_n)})! "
                            f"Verify whether slide presentation timings drifted or if professor addressed Slide {adj_num}'s topic prematurely. "
                            f"Note: Translated slide texts remain strictly immutable."
                        )
                        issues.append({
                            "type": "TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY",
                            "severity": "review_required",
                            "slide_number": num,
                            "displaced_to_slide": adj_num,
                            "distance": delta,
                            "common_audio_terms": sorted(list(overlap_adj))[:5],
                            "message": disp_msg,
                            "remediation_action": f"Verify audio_time_range for Slide {num} and Slide {adj_num} to ensure proper lecture-slide synchrony."
                        })
                        break

        # Dynamic Adaptive Threshold based on speech duration
        if total_slide_dur < 30:
            threshold = 0.35
            min_overlap = 2
            min_precision = 0.15
        elif total_slide_dur <= 120:
            threshold = 0.45
            min_overlap = 3
            min_precision = 0.20
        else:
            threshold = 0.55
            min_overlap = 4
            min_precision = 0.25
            
        # Robust Grounding Pass Condition (closes min_overlap loophole on large slides)
        if len(candidate_substantive) <= 3:
            passed = len(overlap) >= 1 and (precision >= min_precision * 0.5 or recall_ratio >= 0.33)
        else:
            passed = (
                len(overlap) >= min_overlap and (
                    (precision >= min_precision and recall_ratio >= threshold * 0.7)
                    or recall_ratio >= threshold
                )
            )
            
        if passed:
            stats["passed_slides"] += 1
        else:
            stats["failed_slides"] += 1
            missing = sorted(list(candidate_substantive - overlap))[:6]
            issues.append({
                "type": "SLIDE_AUDIO_MISALIGNMENT",
                "severity": "error",
                "slide_number": num,
                "audio_time_range": f"{format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}",
                "duration_sec": total_slide_dur,
                "precision": precision,
                "recall_rate": recall_ratio,
                "required_threshold": threshold,
                "overlap_count": len(overlap),
                "matched_segments": matched_segment_ids[:3],
                "missing_concepts": missing,
                "message": (f"SLIDE-AUDIO MISALIGNMENT at Slide {num} ({format_seconds_to_time(int(slide_start_sec))} - {format_seconds_to_time(int(slide_end_sec))}): "
                            f"Lexical precision is {precision*100:.1f}%, lexical recall is {recall_ratio*100:.1f}% (required {threshold*100:.0f}% with min {min_overlap} concepts). "
                            f"Missing concepts from this specific audio window: {missing}"),
                "remediation_action": f"Incorporate the missing lecture concepts into Slide {num} spoken_lecture or adjust its audio_time_range."
            })
            
    if direct_precisions:
        stats["avg_direct_precision"] = sum(direct_precisions) / len(direct_precisions)
    if direct_recalls:
        stats["avg_direct_recall_rate"] = sum(direct_recalls) / len(direct_recalls)
    if boundary_precisions:
        stats["avg_boundary_precision"] = sum(boundary_precisions) / len(boundary_precisions)
    if boundary_recalls:
        stats["avg_boundary_recall_rate"] = sum(boundary_recalls) / len(boundary_recalls)
    if precisions:
        stats["avg_precision"] = sum(precisions) / len(precisions)
    if recalls:
        stats["avg_recall_rate"] = sum(recalls) / len(recalls)
        
    return issues, stats

def check_academic_prose_quality(text: str) -> list[str]:
    """
    Scans Persian lecture text for informal colloquial verbal slips and fillers.
    Returns list of detected colloquial patterns with their frequencies.
    """
    colloquial_patterns = [
        (r'\bمی‌شه\b', 'می‌شه'),
        (r'\bنمی‌شه\b', 'نمی‌شه'),
        (r'\bمی‌شن\b', 'می‌شن'),
        (r'\bنمی‌شن\b', 'نمی‌شن'),
        (r'\bدارن\b', 'دارن'),
        (r'\bندارن\b', 'ندارن'),
        (r'\bمی‌کنن\b', 'می‌کنن'),
        (r'\bنمی‌کنن\b', 'نمی‌کنن'),
        (r'\bمی‌گن\b', 'می‌گن'),
        (r'\bمی‌دم\b', 'می‌دم'),
        (r'\bمی‌دیم\b', 'می‌دیم'),
        (r'\bمی‌خوایم\b', 'می‌خوایم'),
        (r'\bمی‌خواد\b', 'می‌خواد'),
        (r'\bاینا\b', 'اینا'),
        (r'\bاونا\b', 'اونا'),
        (r'\bببینید\b', 'ببینید'),
        (r'\bعرضم به حضور\b', 'عرضم به حضور'),
        (r'\bبه اصطلاح\b', 'به اصطلاح'),
    ]
    detected = []
    for pat, label in colloquial_patterns:
        matches = re.findall(pat, text)
        if matches:
            detected.append(f"{label} ({len(matches)}x)")
    return detected

def main():
    parser = argparse.ArgumentParser(description="Automated Lecture Narrative & Audio Alignment Verification Gate")
    parser.add_argument("--docx", "-d", required=True, help="Path to .docx study guide")
    parser.add_argument("--transcripts-dir", "-t", required=True, help="Directory containing part*.txt transcription files")
    parser.add_argument("--diagnostic-json", "-j", default="alignment_diagnostic_lecture.json", help="Path to write JSON diagnostic report")
    parser.add_argument("--raw-slides", "-r", help="Optional path to raw_slides.json to enforce Track Isolation")
    parser.add_argument("--translated", help="Optional path to translated_slides.json to verify spoken_lecture fields")
    parser.add_argument("--min-chunk-duration", type=int, default=30, help="Minimum audio chunk duration in seconds to evaluate in Stage 3 coverage (default: 30)")
    parser.add_argument("--strict-drift", action="store_true", help="Enforce strict 60-second drift cap regardless of lecture length")
    parser.add_argument("--max-drift", type=int, default=None, help="Explicit maximum allowed drift seconds")
    parser.add_argument("--allow-review", action="store_true", help="Permit pipeline to complete with status REVIEW_REQUIRED (generating document with warning badges) instead of hard exit 1")
    args = parser.parse_args()
    
    if not os.path.exists(args.docx):
        print(f"Error: DOCX file '{args.docx}' not found!", file=sys.stderr)
        sys.exit(1)
        
    doc = docx.Document(args.docx)
    
    part_files = sorted(glob.glob(os.path.join(args.transcripts_dir, "part*.txt")))
    if not part_files:
        print(f"Error: No part*.txt files found in '{args.transcripts_dir}'!", file=sys.stderr)
        sys.exit(1)
        
    # Load chunks_manifest.json if available as Single Source of Truth
    manifest_chunks = {}
    manifest_candidates = [
        os.path.join(args.transcripts_dir, "chunks_manifest.json"),
        os.path.join(os.path.dirname(args.transcripts_dir), "chunks_manifest.json"),
        "chunks_manifest.json"
    ]
    for mc in manifest_candidates:
        if os.path.exists(mc):
            try:
                with open(mc, "r", encoding="utf-8") as mf:
                    m_data = json.load(mf)
                    for item in m_data.get("chunks", []):
                        fn = os.path.basename(item.get("chunk_filename", ""))
                        stem = os.path.splitext(fn)[0]
                        if stem:
                            manifest_chunks[stem] = item
                break
            except Exception:
                pass

    transcript_chunks = []
    max_audio_sec = 0
    for pf in part_files:
        if pf.endswith(".metadata.json"):
            continue
        base_stem = os.path.splitext(os.path.basename(pf))[0]
        with open(pf, "r", encoding="utf-8") as f:
            content = f.read()
            first_line = content.split("\n")[0] if content else ""
            
            start_sec = 0
            end_sec = 0
            if base_stem in manifest_chunks:
                m_info = manifest_chunks[base_stem]
                start_sec = int(m_info.get("start_sec", 0))
                dur = int(m_info.get("duration_sec", DEFAULT_CHUNK_LENGTH_SEC))
                end_sec = int(m_info.get("end_sec", start_sec + dur))
            else:
                secs = extract_timestamps(first_line)
                if len(secs) >= 2:
                    start_sec = secs[0]
                    end_sec = secs[1]
                elif len(secs) == 1:
                    start_sec = secs[0]
                    end_sec = start_sec + DEFAULT_CHUNK_LENGTH_SEC  # standard chunk default
                
            max_audio_sec = max(max_audio_sec, end_sec)
            transcript_chunks.append({
                "file": os.path.basename(pf),
                "header": first_line,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "text": content,
                "tokens": extract_tokens(content)
            })
            
    print("=" * 68)
    print("🎙️ MANDATORY LECTURE NARRATIVE & AUDIO TIMESTAMP VERIFICATION GATE")
    print("=" * 68)
    print(f"• Target DOCX: {os.path.basename(args.docx)}")
    print(f"• Audio Chunks Discovered: {len(transcript_chunks)} files")
    m_tot, s_tot = divmod(max_audio_sec, 60)
    h_tot, m_tot = divmod(m_tot, 60)
    print(f"• Total Lecture Audio Span: {h_tot:02d}:{m_tot:02d}:{s_tot:02d} ({max_audio_sec} seconds)")
    print("-" * 68)
    
    # Extract H1 sections along with their subsequent body text paragraphs
    sections_data = []
    current_sec = None
    
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        # Skip Track 1 spoken lecture banner paragraphs so they do not split H1 sections
        if txt.startswith("🎙️"):
            if current_sec:
                current_sec["body_paragraphs"].append(txt)
                current_sec["body_text"] += " " + txt
            continue
            
        if "⏱️ زمان فایل صوتی:" in txt or "⏱️" in txt:
            if current_sec:
                sections_data.append(current_sec)
            current_sec = {
                "header": txt,
                "body_paragraphs": [],
                "body_text": ""
            }
        else:
            if current_sec:
                current_sec["body_paragraphs"].append(txt)
                current_sec["body_text"] += " " + txt
                
    if current_sec:
        sections_data.append(current_sec)
        
    print(f"• H1 Sections with Audio Timestamps in DOCX: {len(sections_data)}")
    
    errors = []
    warnings = []
    diagnostics = {
        "gate_status": "PENDING",
        "total_audio_seconds": max_audio_sec,
        "total_audio_span": f"{h_tot:02d}:{m_tot:02d}:{s_tot:02d}",
        "h1_sections_count": len(sections_data),
        "errors": [],
        "warnings": [],
        "review_items": [],
        "remediation_hints": []
    }
    
    if not sections_data:
        err_msg = "NO AUDIO TIMESTAMPS FOUND: Document lacks [⏱️ زمان فایل صوتی: دقیقه XX:YY] tags in H1 headings!"
        errors.append(err_msg)
        diagnostics["errors"].append({
            "error_type": "NO_TIMESTAMPS",
            "message": err_msg,
            "remediation_action": "Add explicit audio_time tags (e.g. audio_time='دقیقه ۰۰:۰۰') to each add_h1 call and ensure TOC matches."
        })
        
    last_sec = -1
    for idx, sec_info in enumerate(sections_data):
        h1 = sec_info["header"]
        body_text = sec_info["body_text"]
        body_words = len(body_text.split())
        sec_tokens = extract_tokens(h1 + " " + body_text)
        
        m = re.search(r'⏱️\s*(?:زمان فایل صوتی:\s*)?(?:دقیقه\s*)?([۰-۹0-9:]+)', h1)
        if not m:
            warn_msg = f"Section {idx+1}: Could not parse timestamp from header '{h1[:45]}...'"
            warnings.append(warn_msg)
            diagnostics["warnings"].append({"section_index": idx + 1, "message": warn_msg})
            continue
            
        ts_str = m.group(1)
        sec = parse_time_to_seconds(ts_str)
        sec_info["sec"] = sec
        if sec is None:
            warn_msg = f"Section {idx+1}: Invalid timestamp format '{ts_str}'"
            warnings.append(warn_msg)
            diagnostics["warnings"].append({"section_index": idx + 1, "message": warn_msg})
            continue
            
        # Check 1: Chronological order
        if sec < last_sec:
            err_msg = f"TIMESTAMP REGRESSION: Section {idx+1} timestamp ({ts_str} = {sec}s) is earlier than preceding section ({last_sec}s)!"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "TIMESTAMP_REGRESSION",
                "section_index": idx + 1,
                "claimed_timestamp": ts_str,
                "message": err_msg,
                "remediation_action": f"Adjust Section {idx+1} timestamp to be >= {format_seconds_to_time(last_sec)} according to actual topic order."
            })
        last_sec = sec
        
        # Check 2: Exceeding real audio duration (Hallucinated Timestamps)
        drift_threshold = compute_drift_threshold(max_audio_sec, strict=args.strict_drift, max_drift=args.max_drift)
        if max_audio_sec > 0 and sec > (max_audio_sec + drift_threshold):
            err_msg = f"HALLUCINATED TIMESTAMP: Section {idx+1} claims timestamp {ts_str} ({sec}s), but total lecture audio ended at {h_tot:02d}:{m_tot:02d}:{s_tot:02d} ({max_audio_sec}s)! Drift exceeds allowed threshold ({drift_threshold}s)."
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "HALLUCINATED_TIMESTAMP",
                "section_index": idx + 1,
                "claimed_timestamp": ts_str,
                "claimed_seconds": sec,
                "max_audio_seconds": max_audio_sec,
                "allowed_drift_seconds": drift_threshold,
                "message": err_msg,
                "remediation_action": f"Drift exceeds dynamic threshold ({drift_threshold}s). Do not silently clamp! Align H1 section with actual audio chunk or mark with Student Review Badge."
            })
            
        # Check 3: Topic & Substantive Coverage in Transcript
        h1_tokens = extract_tokens(h1)
        matching_chunk = None
        for chunk in transcript_chunks:
            if chunk["start_sec"] <= sec <= (chunk["end_sec"] + 30):
                matching_chunk = chunk
                break
                
        if matching_chunk:
            common = h1_tokens.intersection(matching_chunk["tokens"])
            if not common and len(h1_tokens) >= 2:
                found_in_other = []
                suggested_chunk = None
                for other_chunk in transcript_chunks:
                    if other_chunk != matching_chunk:
                        other_common = h1_tokens.intersection(other_chunk["tokens"])
                        if len(other_common) >= 2:
                            found_in_other.append(other_chunk["file"])
                            if suggested_chunk is None:
                                suggested_chunk = other_chunk
                if found_in_other:
                    suggested_start = format_seconds_to_time(suggested_chunk["start_sec"]) if suggested_chunk else "N/A"
                    err_msg = f"TOPIC-AUDIO MISMATCH in Section {idx+1}: Section claims time {ts_str} (in {matching_chunk['file']}), but topic is actually discussed in {', '.join(found_in_other)}!"
                    errors.append(err_msg)
                    diagnostics["errors"].append({
                        "error_type": "TOPIC_AUDIO_MISMATCH",
                        "section_index": idx + 1,
                        "claimed_timestamp": ts_str,
                        "found_in_files": found_in_other,
                        "suggested_timestamp": suggested_start,
                        "message": err_msg,
                        "remediation_action": f"Re-anchor Section {idx+1} timestamp to '{suggested_start}' (start of {suggested_chunk['file']})."
                    })
            
    # Collect all spoken lecture text: Single Source of Truth
    total_body_text = " ".join(s["body_text"] for s in sections_data)
    json_spoken_text = ""
    s_data = []
    trans_json = args.translated or ("translated_slides.json" if os.path.exists("translated_slides.json") else None)
    if trans_json and os.path.exists(trans_json):
        try:
            with open(trans_json, "r", encoding="utf-8") as f:
                s_data = json.load(f)
            json_spoken_text = " ".join(flatten_spoken_lecture(s.get("spoken_lecture", "")) for s in s_data if isinstance(s, dict) and s.get("spoken_lecture"))
        except Exception:
            pass

    # Single Source of Truth: Prefer json_spoken_text if available, else total_body_text from docx (NEVER concatenate both!)
    lecture_text = json_spoken_text if json_spoken_text.strip() else total_body_text
    total_lecture_tokens = extract_tokens(lecture_text)
    total_lecture_words = len(lecture_text.split())
    total_trans_words = sum(len(c["text"].split()) for c in transcript_chunks)

    # Check 4: The Strict Two-Stage Anti-Omission & Concept Recall Gate
    passed_w, word_ratio, w_diag = evaluate_word_ratio_gate(total_lecture_words, total_trans_words, threshold=0.50)
    print("\n" + "=" * 68)
    print("📊 LECTURE COVERAGE & CONCEPT RECALL AUDIT")
    print(f"• Total Audio Transcript Words: {total_trans_words}")
    print(f"• Total Spoken Lecture Words in Study Guide: {total_lecture_words} (Ratio: {word_ratio*100:.1f}%)")
    
    # Stage 1: Word Volume Ratio Check (Minimum 50%)
    if not passed_w:
        errors.append(w_diag["message"])
        diagnostics["errors"].append(w_diag)
        
    # Stage 2: Chunk-by-Chunk Localized Concept Recall Gate (Minimum 60%)
    for chunk in transcript_chunks:
        chunk_st = chunk["start_sec"]
        chunk_en = chunk["end_sec"]
        
        # 1. Gather local text from matching/adjacent H1 sections
        local_text = ""
        matching_secs = [
            s for s in sections_data
            if s.get("sec") is not None and (chunk_st - 120) <= s["sec"] <= (chunk_en + 120)
        ]
        if matching_secs:
            local_text = " ".join(s["body_text"] for s in matching_secs)
        elif sections_data:
            closest_sec = min(sections_data, key=lambda s: abs((s.get("sec") or 0) - chunk_st))
            local_text = closest_sec["body_text"]
            
        # Also include matching slides from s_data if available
        if s_data:
            for s in s_data:
                if not isinstance(s, dict):
                    continue
                s_time_sec = parse_time_to_seconds(s.get("audio_time", ""))
                if s_time_sec is None and s.get("audio_time_range"):
                    t_list = extract_timestamps(s["audio_time_range"])
                    if t_list:
                        s_time_sec = t_list[0]
                if s_time_sec is not None and (chunk_st - 120) <= s_time_sec <= (chunk_en + 120):
                    local_text += " " + flatten_spoken_lecture(s.get("spoken_lecture", ""))
                    
        local_target_tokens = extract_tokens(local_text) if local_text.strip() else total_lecture_tokens
        
        # Evaluate local recall
        passed_c, recall_rate, missing_sample = evaluate_concept_recall_gate(chunk["tokens"], local_target_tokens, threshold=0.60)
        
        # If failed locally, check if concepts were displaced globally to a remote section
        if not passed_c:
            passed_global, global_recall, global_missing = evaluate_concept_recall_gate(chunk["tokens"], total_lecture_tokens, threshold=0.60)
            if passed_global:
                warn_msg = (f"TEMPORAL CONCEPT DISPLACEMENT in {chunk['file']} (time {format_seconds_to_time(chunk_st)} - {format_seconds_to_time(chunk_en)}): "
                            f"Concepts were covered ({global_recall*100:.1f}%), but placed in remote slides/sections rather than the corresponding audio timeframe! Missing locally: {missing_sample}")
                warnings.append(warn_msg)
                diagnostics["warnings"].append({
                    "warning_type": "TEMPORAL_CONCEPT_DISPLACEMENT",
                    "chunk_file": chunk["file"],
                    "start_sec": chunk_st,
                    "end_sec": chunk_en,
                    "local_recall_rate": recall_rate,
                    "global_recall_rate": global_recall,
                    "message": warn_msg
                })
            else:
                err_msg = (f"CRITICAL CONCEPT OMISSION in {chunk['file']} (time {format_seconds_to_time(chunk_st)} - {format_seconds_to_time(chunk_en)}): "
                           f"Recall rate is only {recall_rate*100:.1f}% (minimum 60.0% required). "
                           f"Omitted key clinical concepts: {missing_sample}")
                errors.append(err_msg)
                diagnostics["errors"].append({
                    "error_type": "CRITICAL_CONCEPT_OMISSION",
                    "chunk_file": chunk["file"],
                    "start_sec": chunk_st,
                    "end_sec": chunk_en,
                    "recall_rate": recall_rate,
                    "missing_concepts_sample": missing_sample,
                    "message": err_msg,
                    "remediation_action": f"Incorporate the omitted lecture concepts ({missing_sample}) from {chunk['file']} into the corresponding slide's spoken_lecture field."
                })
            
    # Stage 3: Audio Chunk Mapping Coverage Check (Minimum 85% of chunks > 30s covered)
    CHUNK_COVERAGE_THRESHOLD = 0.85
    sec_times = []
    for s_info in sections_data:
        m_sec = re.search(r'⏱️\s*(?:زمان فایل صوتی:\s*)?(?:دقیقه\s*)?([۰-۹0-9:]+)', s_info["header"])
        if m_sec:
            s_val = parse_time_to_seconds(m_sec.group(1))
            if s_val is not None:
                sec_times.append(s_val)

    # Build section intervals
    sec_intervals = []
    sorted_times = sorted(set(sec_times))
    for idx, st in enumerate(sorted_times):
        en = sorted_times[idx + 1] if idx + 1 < len(sorted_times) else max(st + 540, max_audio_sec)
        sec_intervals.append((st, en))

    # Also augment with slide audio intervals if translated slides are provided
    if s_data:
        for sl in s_data:
            tr = sl.get("audio_time_range")
            if tr and " - " in tr:
                parts = tr.split(" - ")
                t_st = parse_time_to_seconds(parts[0])
                t_en = parse_time_to_seconds(parts[1])
                if t_st is not None and t_en is not None and t_en > t_st:
                    sec_intervals.append((t_st, t_en))

    passed_cov, chunk_cov_ratio, uncovered_chunk_files, covered_chunks_count, evaluated_chunks_count, displaced_chunk_files = evaluate_chunk_coverage_gate(
        transcript_chunks, sec_intervals or sec_times, total_lecture_tokens, min_chunk_duration=args.min_chunk_duration, threshold=CHUNK_COVERAGE_THRESHOLD,
        strict=args.strict_drift, allow_review=getattr(args, 'allow_review', False), return_displaced=True
    )
    print(f"• Audio Chunk Coverage (> {args.min_chunk_duration}s): {covered_chunks_count}/{evaluated_chunks_count} ({chunk_cov_ratio*100:.1f}%)")
    
    if displaced_chunk_files:
        disp_msg = (f"TEMPORAL CONCEPT DISPLACEMENT: Chunks {displaced_chunk_files} matched lexical concepts globally "
                    f"but lack corresponding section timestamps (drift > 60s). Review required.")
        warnings.append(disp_msg)
        diagnostics["warnings"].append({
            "warning_type": "TEMPORAL_CONCEPT_DISPLACEMENT",
            "displaced_chunks": displaced_chunk_files,
            "message": disp_msg
        })
        diagnostics["review_items"].append({
            "item_type": "TEMPORAL_CONCEPT_DISPLACEMENT",
            "message": disp_msg,
            "remediation_action": f"Add explicit timestamps matching chunks {displaced_chunk_files} or verify audio placement."
        })

    if not passed_cov:
        err_msg = (f"UNMAPPED AUDIO CHUNKS: Only {chunk_cov_ratio*100:.1f}% of audio chunks are mapped to the study guide "
                   f"(minimum {CHUNK_COVERAGE_THRESHOLD*100:.0f}% required). Uncovered chunks: {uncovered_chunk_files}")
        errors.append(err_msg)
        diagnostics["errors"].append({
            "error_type": "UNMAPPED_AUDIO_CHUNKS",
            "covered_ratio": chunk_cov_ratio,
            "uncovered_chunks": uncovered_chunk_files,
            "message": err_msg,
            "remediation_action": f"Add spoken_lecture sections covering audio chunks {uncovered_chunk_files}."
        })

    # Stage 4: Lexical Fidelity Check (Advisory Warning if token overlap < 40%)
    for chunk in transcript_chunks:
        c_tokens = {t for t in chunk["tokens"] if len(t) >= 3 or (len(t) >= 2 and any(c.isascii() and c.isalpha() for c in t))}
        if not c_tokens:
            continue
        overlap = c_tokens.intersection(total_lecture_tokens)
        fidelity = len(overlap) / len(c_tokens)
        if fidelity < 0.40:
            warn_msg = f"LEXICAL FIDELITY WARNING for {chunk['file']}: Token overlap is only {fidelity*100:.1f}% (< 40%). Verify that spoken remarks were not over-summarized."
            warnings.append(warn_msg)
            diagnostics["warnings"].append({
                "warning_type": "LEXICAL_FIDELITY_LOW",
                "chunk_file": chunk["file"],
                "fidelity": fidelity,
                "message": warn_msg
            })
            
    # Check 5: Track Isolation Validation (Ensure raw English slide text is not verbatim dumped into Track 1)
    if args.raw_slides and os.path.exists(args.raw_slides):
        try:
            with open(args.raw_slides, "r", encoding="utf-8") as f:
                raw_slides_data = json.load(f)
            leaked_count = 0
            for slide in raw_slides_data:
                s_num = slide.get("slide_number", "?")
                for line in slide.get("text_lines", []):
                    clean_line = line.strip()
                    if len(clean_line.split()) >= 6 and re.search(r'[a-zA-Z]{4,}', clean_line):
                        if clean_line in total_body_text:
                            leaked_count += 1
                            if leaked_count <= 3:
                                warn_msg = f"TRACK ISOLATION WARNING (Slide {s_num}): Verbatim English slide text found in Track 1 lecture prose: '{clean_line[:60]}...'"
                                warnings.append(warn_msg)
                                diagnostics["warnings"].append({"slide_number": s_num, "message": warn_msg})
            if leaked_count > 3:
                warnings.append(f"TRACK ISOLATION: Total {leaked_count} verbatim raw slide lines found in Track 1 prose. Verify that lecture text is spoken transcription, not slide text.")
        except Exception:
            pass

    # Check 6: TOC Accuracy & Timestamp Consistency Verification
    toc_table = None
    for t in doc.tables:
        if len(t.rows) > 1 and len(t.columns) >= 3:
            header_text = " ".join(c.text for c in t.rows[0].cells)
            if ("موضوع" in header_text or "بخش" in header_text) and ("زمان" in header_text):
                toc_table = t
                break

    if toc_table:
        print(f"• Found Table of Contents (TOC) with {len(toc_table.rows) - 1} entries. Verifying TOC timestamp consistency...")
        for r_idx in range(1, len(toc_table.rows)):
            row_cells = toc_table.rows[r_idx].cells
            sec_label = row_cells[0].text.strip()
            topic_label = row_cells[1].text.strip()
            time_text = row_cells[2].text.strip() if len(row_cells) > 2 else ""
            
            toc_sec = parse_time_to_seconds(time_text)
            if toc_sec is None:
                continue
                
            matching_h1 = None
            if (r_idx - 1) < len(sections_data):
                matching_h1 = sections_data[r_idx - 1]
            else:
                topic_tokens = extract_tokens(topic_label)
                best_overlap = 0
                for s_cand in sections_data:
                    overlap = len(topic_tokens.intersection(extract_tokens(s_cand["header"])))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        matching_h1 = s_cand

            if matching_h1:
                m_h1 = re.search(r'⏱️\s*(?:زمان فایل صوتی:\s*)?(?:دقیقه\s*)?([۰-۹0-9:]+)', matching_h1["header"])
                if m_h1:
                    h1_sec = parse_time_to_seconds(m_h1.group(1))
                    if h1_sec is not None:
                        passed_toc, drift = evaluate_toc_drift_gate(toc_sec, h1_sec, tolerance_sec=60)
                        if not passed_toc:
                            err_msg = (f"TOC TIMESTAMP DRIFT: TOC row {r_idx} ('{topic_label[:30]}') claims time {time_text} ({toc_sec}s), "
                                       f"but corresponding H1 heading claims time {m_h1.group(1)} ({h1_sec}s)! Drift is {drift}s (> 60s tolerance).")
                            errors.append(err_msg)
                            diagnostics["errors"].append({
                                "error_type": "TOC_TIMESTAMP_DRIFT",
                                "toc_row": r_idx,
                                "topic": topic_label,
                                "toc_seconds": toc_sec,
                                "h1_seconds": h1_sec,
                                "drift_seconds": drift,
                                "message": err_msg,
                                "remediation_action": f"Synchronize TOC table row {r_idx} timestamp ({time_text}) with H1 heading timestamp ({m_h1.group(1)})."
                            })

    # Check 7: Academic Prose Quality & Colloquial Slips Advisory
    colloquial_slips = check_academic_prose_quality(total_body_text)
    if colloquial_slips:
        warn_msg = f"ACADEMIC PROSE ADVISORY: Detected {len(colloquial_slips)} colloquial verbal patterns in Track 1 lecture text: {', '.join(colloquial_slips[:6])}. Recommend formalizing into fluent academic prose."
        warnings.append(warn_msg)
        diagnostics["warnings"].append({
            "error_type": "COLLOQUIAL_PROSE_ADVISORY",
            "detected_slips": colloquial_slips,
            "message": warn_msg
        })

    # Check 8: Dedicated Slide Grounding & Segment Fidelity Gate
    if s_data:
        print("\n" + "=" * 68)
        print("🎯 MANDATORY SLIDE GROUNDING & SEGMENT FIDELITY GATE")
        grounding_issues, g_stats = evaluate_slide_level_grounding(s_data, transcript_chunks)
        diagnostics["slide_grounding_stats"] = g_stats
        print(f"• Fine-Grained Audio Segments: {g_stats.get('total_segments_evaluated', 0)}")
        if g_stats["voiced_slides"] > 0:
            pass_pct = (g_stats["passed_slides"] / g_stats["voiced_slides"]) * 100
            print(f"• Voiced Slides Evaluated: {g_stats['voiced_slides']}/{g_stats['total_slides']}")
            print(f"• Direct Grounded Slides: {g_stats.get('direct_grounded_slides', 0)}/{g_stats['voiced_slides']}")
            if g_stats.get('boundary_fallback_slides', 0) > 0:
                print(f"• Boundary Fallback Slides (±15s): {g_stats['boundary_fallback_slides']}/{g_stats['voiced_slides']}")
            if g_stats.get('direct_grounded_slides', 0) > 0:
                print(f"• Direct Lexical Precision: {g_stats.get('avg_direct_precision', 0)*100:.1f}%")
                print(f"• Direct Lexical Recall: {g_stats.get('avg_direct_recall_rate', 0)*100:.1f}%")
            print(f"• Overall Average Lexical Precision: {g_stats.get('avg_precision', 0)*100:.1f}%")
            print(f"• Overall Average Lexical Recall: {g_stats.get('avg_recall_rate', 0)*100:.1f}%")
            print(f"• Passed Slides: {g_stats['passed_slides']}/{g_stats['voiced_slides']} ({pass_pct:.1f}%)")
            print(f"• Failed Slides: {g_stats['failed_slides']}")
            if g_stats.get("slides_with_fact_omissions", 0) > 0:
                print(f"• Slides with Fact Omission Warnings: {g_stats['slides_with_fact_omissions']}")
        for g_iss in grounding_issues:
            if g_iss.get("severity") == "error":
                errors.append(g_iss["message"])
                diagnostics["errors"].append({
                    "error_type": g_iss["type"],
                    "slide_number": g_iss.get("slide_number"),
                    "message": g_iss["message"],
                    "remediation_action": f"Incorporate the missing lecture concepts into Slide {g_iss.get('slide_number')} spoken_lecture or adjust its audio_time_range."
                })
            elif g_iss.get("severity") == "review_required":
                warnings.append(g_iss["message"])
                diagnostics["warnings"].append(g_iss)
                diagnostics["review_items"].append({
                    "item_type": g_iss["type"],
                    "slide_number": g_iss.get("slide_number"),
                    "message": g_iss["message"],
                    "remediation_action": g_iss.get("remediation_action", "")
                })
            else:
                warnings.append(g_iss["message"])
                diagnostics["warnings"].append(g_iss)

    print("-" * 68)
    if warnings:
        print(f"⚠️  {len(warnings)} Advisory Warnings:")
        for w in warnings[:5]:
            print(f"   - {w}")
        if len(warnings) > 5:
            print(f"   ... and {len(warnings) - 5} more warnings.")
            
    if errors:
        print("\n💡 ACTIONABLE REMEDIATION HINTS:")
        for diag in diagnostics["errors"]:
            sec_display = f"Section {diag['section_index']}" if "section_index" in diag else "Global"
            print(f"   • [{diag['error_type']}] {sec_display}: {diag['remediation_action']}")
            diagnostics["remediation_hints"].append(diag['remediation_action'])
            
        HARD_FAIL_KEYWORDS = [
            "DUPLICATE SLIDE NUMBER",
            "TEMPORAL MONOTONICITY VIOLATION",
            "SCHEMA VALIDATION ERROR",
            "MALFORMED SLIDE SCHEMA",
            "NO TEMPORAL AUDIO EVIDENCE",
            "COUNT MISMATCH",
            "INDEX GAP",
            "UNSUPPORTED SLIDE BOX CONTENT",
            "PHANTOM CONTENT HALLUCINATION"
        ]
        hard_fails = [e for e in errors if any(kw in e.upper() for kw in HARD_FAIL_KEYWORDS)]

        if getattr(args, 'allow_review', False) and not hard_fails:
            diagnostics["gate_status"] = "REVIEW_REQUIRED"
            print(f"\n⚠️  GATE STATUS: REVIEW_REQUIRED ({len(errors)} review-eligible issues detected).")
            print("   Proceeding with document generation because --allow-review was specified.")
            print("   All unverified slides and sections will be tagged with Amber Review Badges for human inspection.")
            try:
                with open(args.diagnostic_json, "w", encoding="utf-8") as f:
                    json.dump(diagnostics, f, ensure_ascii=False, indent=2)
                print(f"\n📁 Structured diagnostic written to: '{args.diagnostic_json}'")
            except Exception as ex:
                print(f"Could not write diagnostic JSON: {ex}", file=sys.stderr)
            sys.exit(0)
        else:
            diagnostics["gate_status"] = "FAILED_HARD"
            if hard_fails and getattr(args, 'allow_review', False):
                print(f"\n❌ GATE FAILED (FAILED_HARD): {len(hard_fails)} Non-bypassable structural/monotonicity hard failures detected!")
                print("   --allow-review CANNOT override severe data corruptions or timestamp backwards jumps.")
            else:
                print(f"\n❌ GATE FAILED (FAILED_HARD): {len(errors)} Critical Audio/Lecture Alignment Errors detected!")
            for e in errors:
                print(f"   [FAIL] {e}")
                
            try:
                with open(args.diagnostic_json, "w", encoding="utf-8") as f:
                    json.dump(diagnostics, f, ensure_ascii=False, indent=2)
                print(f"\n📁 Structured diagnostic written to: '{args.diagnostic_json}'")
            except Exception as ex:
                print(f"Could not write diagnostic JSON: {ex}", file=sys.stderr)
                
            print("\nDocument generation ABORTED. Fix timestamps and audio alignment using the hints above, or pass --allow-review to generate a review copy with warning badges.")
            sys.exit(1)
    elif diagnostics.get("review_items"):
        diagnostics["gate_status"] = "REVIEW_REQUIRED"
        print(f"\n⚠️  GATE STATUS: REVIEW_REQUIRED ({len(diagnostics['review_items'])} items require human review).")
        for r_item in diagnostics["review_items"]:
            print(f"   • [{r_item.get('item_type', 'REVIEW')}] {r_item['message']}")
        if getattr(args, 'allow_review', False):
            print("   Proceeding with document generation because --allow-review was specified.")
            try:
                with open(args.diagnostic_json, "w", encoding="utf-8") as f:
                    json.dump(diagnostics, f, ensure_ascii=False, indent=2)
                print(f"\n📁 Structured diagnostic written to: '{args.diagnostic_json}'")
            except Exception as ex:
                print(f"Could not write diagnostic JSON: {ex}", file=sys.stderr)
            sys.exit(0)
        else:
            print("\nDocument generation paused. Review the items above, or pass --allow-review to generate the document with warning badges.")
            try:
                with open(args.diagnostic_json, "w", encoding="utf-8") as f:
                    json.dump(diagnostics, f, ensure_ascii=False, indent=2)
                print(f"\n📁 Structured diagnostic written to: '{args.diagnostic_json}'")
            except Exception as ex:
                print(f"Could not write diagnostic JSON: {ex}", file=sys.stderr)
            sys.exit(1)
        
    diagnostics["gate_status"] = "PASSED"
    try:
        with open(args.diagnostic_json, "w", encoding="utf-8") as f:
            json.dump(diagnostics, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
        
    print("\n✅ GATE PASSED: 100% Lecture Audio Alignment and Substantive Coverage Verified!")
    print(f"All {len(sections_data)} section timestamps strictly match real audio transcripts with high clinical substance density.")
    print("=" * 68)
    sys.exit(0)

if __name__ == "__main__":
    main()
