#!/usr/bin/env python3
"""
batch_orchestrator.py: Deterministic Multi-Agent Map-Reduce Partitioner, Boundary-Safe Merger,
and QA Critic Audit Engine for the Medical Lecture Transcriber Pipeline (v5.8.0).

Provides three deterministic engineering safeguards for multi-agent parallel execution:
1. `partition_slides`: Slices `raw_slides.json` into disjoint slide batches (default 10-12 slides)
   inside `batches/` with a 1-slide read-only Context Halo (`halo_prev`, `halo_next`) and explicit
   per-slide vision/table checklists so parallel subagents never suffer from boundary drift or
   file write contention.
2. `merge_slide_batches`: Collects isolated `batches/translated_batch_XX_YY.json` shard files,
   strips any accidental halo slides, normalizes LaTeX math and `ref_note` prefixes, resolves
   transitive/cross-batch `parent_lecture_slide` chains, deduplicates boundary lecture repeats,
   verifies 1-to-N index invariance, and writes the canonical `translated_slides.json`.
3. `run_qa_preflight_and_validate`: Generates a targeted inspection dossier for the independent
   QA Critic Subagent (listing all table slides, visual slides, batch boundaries, and numerical
   slides) and validates `qa_audit_report.json`.
"""

import os
import sys
import glob
import json
import math
import argparse
from typing import Dict, List, Any, Tuple, Optional

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
    sanitize_latex_math,
    sanitize_ref_note,
    normalize_for_display,
)


def _to_posix(path: str) -> str:
    return path.replace("\\", "/") if path else ""


def _load_json_slides(path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Loads a JSON file that is either a list of slide dicts or a dict with a 'slides' key."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        slides = data.get("slides", [])
        meta = {k: v for k, v in data.items() if k != "slides"}
        return slides, meta
    elif isinstance(data, list):
        return data, {}
    else:
        raise ValueError(f"Invalid JSON structure in {path}: expected list or dict with 'slides'.")


def _slide_needs_vision(raw_slide: Dict[str, Any]) -> bool:
    if raw_slide.get("needs_vision_inspection") or raw_slide.get("is_image_only") or raw_slide.get("is_pure_visual"):
        return True
    if raw_slide.get("has_tables") or raw_slide.get("has_image_table") or raw_slide.get("tables"):
        return True
    if (
        raw_slide.get("has_images")
        or raw_slide.get("has_charts")
        or raw_slide.get("has_smartart")
        or raw_slide.get("has_standalone_figure")
    ):
        return True
    if raw_slide.get("extracted_images") or raw_slide.get("fig_path") or raw_slide.get("image_path"):
        return True
    return False


def _resolve_slide_image_path(raw_slide: Dict[str, Any], s_num: int) -> str:
    return _to_posix(
        raw_slide.get("fig_path")
        or raw_slide.get("img_path")
        or raw_slide.get("image_path")
        or f"slide_images/slide_{s_num:02d}.png"
    )


def _slide_has_table(raw_slide: Dict[str, Any]) -> bool:
    return bool(
        raw_slide.get("has_tables")
        or raw_slide.get("has_image_table")
        or raw_slide.get("has_table")
        or (isinstance(raw_slide.get("tables"), list) and len(raw_slide["tables"]) > 0)
    )


def _sanitize_table_rows(rows: List[Any]) -> List[Any]:
    new_rows = []
    for r in rows:
        if isinstance(r, dict):
            nr = dict(r)
            if isinstance(nr.get("text"), str):
                nr["text"] = sanitize_latex_math(nr["text"])
            if isinstance(nr.get("cols"), list):
                nr["cols"] = [sanitize_latex_math(str(c)) for c in nr["cols"]]
            new_rows.append(nr)
        elif isinstance(r, list):
            new_rows.append([sanitize_latex_math(str(c)) for c in r])
        elif isinstance(r, str):
            new_rows.append(sanitize_latex_math(r))
        else:
            new_rows.append(r)
    return new_rows


def _sanitize_slide_object(slide: Dict[str, Any], ref_book_name: str = "رفرنس") -> Dict[str, Any]:
    """Applies deterministic LaTeX math, table canonicalization, and ref_note sanitization across all fields of a slide dict."""
    s = dict(slide)
    s.pop("_halo_role", None)

    # Normalize cluster_parent alias -> parent_lecture_slide
    if "cluster_parent" in s:
        cp_val = s.pop("cluster_parent")
        if s.get("parent_lecture_slide") is None and cp_val is not None:
            s["parent_lecture_slide"] = cp_val

    for str_key in ("title_fa", "title_en", "section_title", "spoken_lecture", "audio_time_range"):
        if isinstance(s.get(str_key), str):
            s[str_key] = sanitize_latex_math(s[str_key])

    if isinstance(s.get("ref_note"), str) and s["ref_note"].strip():
        s["ref_note"] = sanitize_ref_note(sanitize_latex_math(s["ref_note"]))
        
        # Anti-proliferation check: suppress ref_note if professor gave full lecture (>= 60 words)
        # unless explicitly flagged for reference expansion or skipped/unvoiced.
        spoken_txt = s.get("spoken_lecture", "") or ""
        spoken_wcnt = len(spoken_txt.split())
        is_skip = bool(s.get("is_skipped") or s.get("unvoiced") or s.get("skipped_by_professor"))
        needs_exp = bool(s.get("needs_reference_expansion"))
        if spoken_wcnt >= 60 and not is_skip and not needs_exp:
            s["ref_note"] = ""

    if isinstance(s.get("bullets"), list):
        clean_bullets = []
        for b in s["bullets"]:
            if isinstance(b, dict):
                cb = dict(b)
                if isinstance(cb.get("lead"), str):
                    cb["lead"] = sanitize_latex_math(cb["lead"])
                if isinstance(cb.get("text"), str):
                    cb["text"] = sanitize_latex_math(cb["text"])
                clean_bullets.append(cb)
            elif isinstance(b, list):
                clean_bullets.append([sanitize_latex_math(str(x)) for x in b])
            elif isinstance(b, str):
                clean_bullets.append(sanitize_latex_math(b))
            else:
                clean_bullets.append(b)
        s["bullets"] = clean_bullets

    # Sanitize and canonicalize table_data / structured_tables / reference_tables
    for tbl_key in ("table_data", "structured_tables", "reference_tables"):
        tbl_val = s.get(tbl_key)
        if isinstance(tbl_val, dict):
            ct = dict(tbl_val)
            if isinstance(ct.get("headers"), list):
                ct["headers"] = [sanitize_latex_math(str(h)) for h in ct["headers"]]
            raw_rows = ct.get("rows") if isinstance(ct.get("rows"), list) else ct.get("items")
            if isinstance(raw_rows, list):
                ct["rows"] = _sanitize_table_rows(raw_rows)
                if "items" in ct:
                    ct.pop("items", None)
            s[tbl_key] = ct
        elif isinstance(tbl_val, list):
            # Could be [headers, rows] or list of table dicts
            if len(tbl_val) == 2 and isinstance(tbl_val[0], list) and isinstance(tbl_val[1], list) and (
                not tbl_val[0] or isinstance(tbl_val[0][0], str)
            ):
                headers = [sanitize_latex_math(str(h)) for h in tbl_val[0]]
                rows = _sanitize_table_rows(tbl_val[1])
                s[tbl_key] = [headers, rows]
            else:
                new_list = []
                for item in tbl_val:
                    if isinstance(item, dict):
                        ct = dict(item)
                        if isinstance(ct.get("headers"), list):
                            ct["headers"] = [sanitize_latex_math(str(h)) for h in ct["headers"]]
                        raw_rows = ct.get("rows") if isinstance(ct.get("rows"), list) else ct.get("items")
                        if isinstance(raw_rows, list):
                            ct["rows"] = _sanitize_table_rows(raw_rows)
                            if "items" in ct:
                                ct.pop("items", None)
                        new_list.append(ct)
                    else:
                        new_list.append(item)
                s[tbl_key] = new_list[0] if len(new_list) == 1 and isinstance(new_list[0], dict) else new_list

    # Canonicalize structured_tables / reference_tables into table_data if table_data is absent
    if not s.get("table_data"):
        for alias_key in ("structured_tables", "reference_tables"):
            alias_val = s.get(alias_key)
            if alias_val:
                if isinstance(alias_val, list) and len(alias_val) >= 1 and isinstance(alias_val[0], dict):
                    s["table_data"] = alias_val[0]
                else:
                    s["table_data"] = alias_val
                break

    return s


def _slide_has_valid_translated_table(slide: Dict[str, Any]) -> bool:
    """Checks whether a translated slide has a non-empty structured table."""
    for key in ("table_data", "structured_tables", "reference_tables"):
        val = slide.get(key)
        if not val:
            continue
        if isinstance(val, dict):
            headers = val.get("headers", [])
            rows = val.get("rows") or val.get("items", [])
            if headers and rows:
                return True
        elif isinstance(val, list):
            if len(val) == 2 and isinstance(val[0], list) and isinstance(val[1], list) and val[0] and val[1]:
                return True
            for item in val:
                if isinstance(item, dict) and item.get("headers") and (item.get("rows") or item.get("items")):
                    return True
    return False


def partition_slides(
    raw_slides_path: str = "raw_slides.json",
    batches_dir: str = "batches",
    batch_size: int = 12,
    halo_size: int = 1,
    img_dir: str = "slide_images",
    chunks_manifest_path: str = "chunks_manifest.json",
) -> Dict[str, Any]:
    """
    Slices `raw_slides.json` into disjoint slide batches of size `batch_size` (default 12),
    attaching a `halo_size` (default 1) read-only context halo before and after each batch.
    Also partitions audio chunks into parallel transcription groups if `chunks_manifest.json` exists.
    """
    if not os.path.exists(raw_slides_path):
        raise FileNotFoundError(f"Raw slides file not found: {raw_slides_path}")

    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    raw_slides, raw_meta = _load_json_slides(raw_slides_path)
    raw_slides_sorted = sorted(raw_slides, key=lambda x: int(x.get("slide_number", 0)))
    total_slides = len(raw_slides_sorted)

    os.makedirs(batches_dir, exist_ok=True)

    batch_entries = []
    num_batches = math.ceil(total_slides / batch_size) if total_slides > 0 else 0

    for b_idx in range(num_batches):
        start_idx = b_idx * batch_size
        end_idx = min(start_idx + batch_size, total_slides)
        target_slice = raw_slides_sorted[start_idx:end_idx]

        start_num = int(target_slice[0]["slide_number"])
        end_num = int(target_slice[-1]["slide_number"])
        batch_id = f"batch_{start_num:02d}_{end_num:02d}"

        # Read-only context halo (previous and next slides)
        halo_prev = []
        if halo_size > 0 and start_idx > 0:
            for hs in raw_slides_sorted[max(0, start_idx - halo_size):start_idx]:
                h_copy = dict(hs)
                h_copy["_halo_role"] = "read_only_prev_context"
                halo_prev.append(h_copy)

        halo_next = []
        if halo_size > 0 and end_idx < total_slides:
            for hs in raw_slides_sorted[end_idx:min(total_slides, end_idx + halo_size)]:
                h_copy = dict(hs)
                h_copy["_halo_role"] = "read_only_next_context"
                halo_next.append(h_copy)

        expected_nums = [int(s["slide_number"]) for s in target_slice]
        vision_slides = [int(s["slide_number"]) for s in target_slice if _slide_needs_vision(s)]
        table_slides = [int(s["slide_number"]) for s in target_slice if _slide_has_table(s)]

        raw_batch_filename = f"{batch_id}_raw.json"
        raw_batch_path = _to_posix(os.path.join(batches_dir, raw_batch_filename))
        output_shard_filename = f"translated_{batch_id}.json"
        output_shard_path = _to_posix(os.path.join(batches_dir, output_shard_filename))

        batch_payload = {
            "batch_id": batch_id,
            "batch_index": b_idx + 1,
            "total_batches": num_batches,
            "start_slide": start_num,
            "end_slide": end_num,
            "expected_slide_numbers": expected_nums,
            "output_shard_file": output_shard_path,
            "mandatory_vision_slides": vision_slides,
            "mandatory_table_slides": table_slides,
            "instructions": {
                "rule_1_isolation": (
                    f"ONLY translate and synthesize slides {start_num} to {end_num} "
                    f"(expected_slide_numbers={expected_nums}). Write output ONLY to '{output_shard_path}'. "
                    "NEVER write to 'translated_slides.json' directly."
                ),
                "rule_2_halo": (
                    "'halo_prev' and 'halo_next' are READ-ONLY context slides so you can detect multi-slide "
                    "lecture clusters (parent_lecture_slide) across batch boundaries and avoid duplicating "
                    "spoken lecture text. Do NOT include halo slides in your output JSON."
                ),
                "rule_3_vision_and_tables": (
                    f"You MUST call view_file on slide images for mandatory_vision_slides={vision_slides}. "
                    f"For mandatory_table_slides={table_slides}, you MUST populate 'table_data' with exact "
                    "{'headers': [...], 'rows': [...]} cell-by-cell without summarizing."
                ),
                "rule_4_unicode_math": (
                    "Strictly use direct Unicode symbols (≥, ≤, ±, ×, °, µ, →). NEVER use LaTeX math ($...$, \\ge, \\le)."
                ),
                "rule_5_ref_note_discipline": (
                    "'ref_note' is strictly reserved for slides where the professor gave NO explanation or very brief/sparse explanation (< 30-40 words), or skipped the slide entirely ('is_skipped': true). "
                    "If the professor gave a full, comprehensive explanation, you MUST leave 'ref_note': \"\" (empty string). Do NOT add supplementary reference notes indiscriminately."
                ),
                "rule_6_lecture_termination_and_unvoiced_trailing_slides": (
                    "If the professor concludes the lecture early (e.g. says goodbye, concludes session, states 'این آخرین اسلایدم هستش') at slide K, "
                    "or explicitly omits trailing slides, you MUST NOT hallucinate, repeat, or displace earlier lecture audio into slides K+1..N. "
                    "All trailing unvoiced slides MUST have 'is_skipped': true (or 'unvoiced': true), 'spoken_lecture': \"\", and a mandatory "
                    "substantive 'ref_note' (15-30 words) explaining the slide's clinical concepts from the textbook."
                ),
                "rule_7_continuous_global_timestamps": (
                    "Timestamps ('audio_time', 'audio_time_range') MUST ALWAYS be continuous global presentation timestamps relative to the start of "
                    "the full lecture (e.g. 18:20 - 21:45). NEVER use chunk-relative timestamps resetting to 00:00! If working from an audio chunk "
                    "(e.g. chunk 3 starting at 15:00), add the chunk's start offset to each timestamp so timestamps monotonically advance across all batches."
                ),
                "rule_8_section_title_on_slide_one": (
                    "Ensure Slide 1 has a descriptive 'section_title' (e.g. 'مقدمه و کلیات مبحث' or the main lecture title) so that the Table of Contents "
                    "(TOC) covers the opening section from Slide 1."
                ),
            },
            "halo_prev": halo_prev,
            "slides": target_slice,
            "halo_next": halo_next,
        }

        with open(os.path.join(batches_dir, raw_batch_filename), "w", encoding="utf-8") as bf:
            json.dump(batch_payload, bf, ensure_ascii=False, indent=2)

        batch_entries.append({
            "batch_id": batch_id,
            "batch_index": b_idx + 1,
            "start_slide": start_num,
            "end_slide": end_num,
            "slide_count": len(expected_nums),
            "expected_slide_numbers": expected_nums,
            "raw_batch_file": raw_batch_path,
            "output_shard_file": output_shard_path,
            "mandatory_vision_slides": vision_slides,
            "mandatory_table_slides": table_slides,
        })

    # Also check audio chunks for Level-1 parallel audio transcription grouping
    audio_groups = []
    total_audio_chunks = 0
    if os.path.exists(chunks_manifest_path):
        try:
            with open(chunks_manifest_path, "r", encoding="utf-8") as mf:
                c_manifest = json.load(mf)
            chunks_list = c_manifest.get("chunks", []) if isinstance(c_manifest, dict) else c_manifest
            if isinstance(chunks_list, list) and chunks_list:
                total_audio_chunks = len(chunks_list)
                audio_batch_size = 3
                for a_idx in range(0, total_audio_chunks, audio_batch_size):
                    sub_chunks = chunks_list[a_idx:a_idx + audio_batch_size]
                    audio_groups.append({
                        "audio_worker_index": (a_idx // audio_batch_size) + 1,
                        "chunk_indices": [c.get("index", i + 1) for i, c in enumerate(sub_chunks, start=a_idx)],
                        "chunk_files": [
                            _to_posix(c.get("file") or c.get("path") or c.get("filename") or "")
                            for c in sub_chunks
                        ],
                        "target_transcript_files": [
                            f"transcripts/part{int(c.get('index', i + 1)):02d}.txt"
                            for i, c in enumerate(sub_chunks, start=a_idx)
                        ],
                    })
        except Exception:
            pass

    multi_agent_mandatory = bool(total_slides > 12 or total_audio_chunks > 2)

    manifest = {
        "schema_version": "5.8.0",
        "raw_slides_source": _to_posix(raw_slides_path),
        "total_slides": total_slides,
        "batch_size": batch_size,
        "halo_size": halo_size,
        "total_batches": num_batches,
        "total_audio_chunks": total_audio_chunks,
        "multi_agent_mandatory": multi_agent_mandatory,
        "audio_transcription_groups": audio_groups,
        "batches": batch_entries,
    }

    manifest_path = os.path.join(batches_dir, "batches_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, ensure_ascii=False, indent=2)

    return manifest


def merge_slide_batches(
    batches_dir: str = "batches",
    raw_slides_path: str = "raw_slides.json",
    output_path: str = "translated_slides.json",
    ref_book_name: str = "رفرنس",
    strict: bool = True,
) -> Dict[str, Any]:
    """
    Validates and merges all `batches/translated_batch_XX_YY.json` shard files into
    `translated_slides.json` with deterministic boundary checks, halo stripping,
    cross-batch `parent_lecture_slide` resolution, and LaTeX math sanitization.
    """
    manifest_path = os.path.join(batches_dir, "batches_manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(
            f"Batches manifest not found at '{manifest_path}'. Run 'run_pipeline.py partition' first."
        )

    with open(manifest_path, "r", encoding="utf-8") as mf:
        manifest = json.load(mf)

    raw_slides = []
    raw_by_num: Dict[int, Dict[str, Any]] = {}
    if os.path.exists(raw_slides_path):
        raw_slides, _ = _load_json_slides(raw_slides_path)
        for rs in raw_slides:
            if "slide_number" in rs:
                raw_by_num[int(rs["slide_number"])] = rs

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    merged_by_num: Dict[int, Dict[str, Any]] = {}
    batch_boundaries: List[Tuple[int, int]] = []

    for b_entry in manifest.get("batches", []):
        batch_id = b_entry["batch_id"]
        shard_file = b_entry["output_shard_file"]
        expected_nums = [int(n) for n in b_entry["expected_slide_numbers"]]
        expected_set = set(expected_nums)

        if len(expected_nums) >= 1:
            batch_boundaries.append((expected_nums[0], expected_nums[-1]))

        if not os.path.exists(shard_file):
            errors.append({
                "code": "MISSING_BATCH_SHARD",
                "batch_id": batch_id,
                "shard_file": shard_file,
                "message": f"Batch output file '{shard_file}' for slides {expected_nums[0]}..{expected_nums[-1]} is missing.",
            })
            continue

        try:
            shard_slides, _ = _load_json_slides(shard_file)
        except Exception as e:
            errors.append({
                "code": "CORRUPT_BATCH_SHARD_JSON",
                "batch_id": batch_id,
                "shard_file": shard_file,
                "message": f"Failed to parse JSON in '{shard_file}': {e}",
            })
            continue

        found_in_batch = set()
        for s_obj in shard_slides:
            if not isinstance(s_obj, dict) or "slide_number" not in s_obj:
                errors.append({
                    "code": "INVALID_SLIDE_OBJECT",
                    "batch_id": batch_id,
                    "message": "Slide entry is missing 'slide_number'.",
                })
                continue

            s_num = int(s_obj["slide_number"])
            if s_num not in expected_set:
                # Strip accidental halo slide inclusion with a warning
                warnings.append({
                    "code": "STRIPPED_OUT_OF_RANGE_HALO_SLIDE",
                    "batch_id": batch_id,
                    "slide_number": s_num,
                    "message": f"Slide {s_num} was outside batch {batch_id} range {expected_nums[0]}..{expected_nums[-1]} (likely a halo slide) and was automatically stripped.",
                })
                continue

            if s_num in found_in_batch or s_num in merged_by_num:
                errors.append({
                    "code": "DUPLICATE_SLIDE_IN_BATCH",
                    "batch_id": batch_id,
                    "slide_number": s_num,
                    "message": f"Duplicate slide_number {s_num} detected in batch {batch_id}.",
                })
                continue

            found_in_batch.add(s_num)
            cleaned_slide = _sanitize_slide_object(s_obj, ref_book_name=ref_book_name)

            # Inherit structural flags from raw_slide if available
            raw_s = raw_by_num.get(s_num)
            if raw_s:
                if _slide_has_table(raw_s) and not _slide_has_valid_translated_table(cleaned_slide):
                    warnings.append({
                        "code": "BATCH_SLIDE_MISSING_TABLE_DATA",
                        "batch_id": batch_id,
                        "slide_number": s_num,
                        "message": f"Slide {s_num} has a table in raw_slides.json but 'table_data' is missing or empty in {shard_file}.",
                    })

            merged_by_num[s_num] = cleaned_slide

        missing_in_batch = sorted(expected_set - found_in_batch)
        if missing_in_batch:
            errors.append({
                "code": "MISSING_SLIDES_IN_BATCH",
                "batch_id": batch_id,
                "missing_slide_numbers": missing_in_batch,
                "message": f"Batch {batch_id} ({shard_file}) is missing expected slides: {missing_in_batch}.",
            })

    # Global 1..N check
    total_expected = int(manifest.get("total_slides", len(raw_by_num)))
    all_expected_nums = list(range(1, total_expected + 1))
    globally_missing = [n for n in all_expected_nums if n not in merged_by_num]
    if globally_missing:
        errors.append({
            "code": "GLOBAL_INDEX_GAP",
            "missing_slides": globally_missing,
            "message": f"Merged slides are missing slide numbers: {globally_missing}",
        })

    merged_slides_sorted = [merged_by_num[n] for n in sorted(merged_by_num.keys())]

    # Auto-synthesize Slide 1 section_title if later slides define sections but Slide 1 lacks it
    if merged_slides_sorted and any(bool(s.get("section_title")) for s in merged_slides_sorted) and not merged_slides_sorted[0].get("section_title"):
        intro_title = merged_slides_sorted[0].get("title_fa") or "مقدمه و کلیات مبحث"
        merged_slides_sorted[0]["section_title"] = intro_title
        warnings.append({
            "code": "TOC_INITIAL_SLIDES_COVERAGE_SYNTHESIZED",
            "slide_number": merged_slides_sorted[0].get("slide_number", 1),
            "synthesized_section_title": intro_title,
            "message": f"Slide 1 lacked 'section_title' while later slides defined sections. Auto-synthesized '{intro_title}' to ensure opening slides 1..M are covered in TOC."
        })

    # Cross-batch boundary & parent_lecture_slide resolution
    for s_obj in merged_slides_sorted:
        s_num = int(s_obj["slide_number"])
        parent_num = s_obj.get("parent_lecture_slide")
        if parent_num is not None:
            try:
                p_int = int(parent_num)
            except (ValueError, TypeError):
                errors.append({
                    "code": "INVALID_PARENT_LECTURE_SLIDE",
                    "slide_number": s_num,
                    "message": f"Slide {s_num} has non-integer parent_lecture_slide={parent_num}.",
                })
                continue

            if p_int >= s_num or p_int < 1 or p_int not in merged_by_num:
                errors.append({
                    "code": "OUT_OF_BOUNDS_PARENT_LECTURE_SLIDE",
                    "slide_number": s_num,
                    "parent_lecture_slide": p_int,
                    "message": f"Slide {s_num} points to invalid parent_lecture_slide {p_int} (must be 1 <= parent < {s_num}).",
                })
                continue

            # Resolve transitive parent chain (e.g., 13 -> 12 -> 11 resolves to root 11)
            visited = {s_num}
            curr_p = p_int
            while curr_p in merged_by_num and merged_by_num[curr_p].get("parent_lecture_slide") is not None:
                next_p = int(merged_by_num[curr_p]["parent_lecture_slide"])
                if next_p in visited or next_p >= curr_p or next_p < 1:
                    break
                visited.add(curr_p)
                curr_p = next_p
            if curr_p != p_int:
                s_obj["parent_lecture_slide"] = curr_p
                warnings.append({
                    "code": "RESOLVED_TRANSITIVE_CLUSTER_PARENT",
                    "slide_number": s_num,
                    "original_parent": p_int,
                    "resolved_root_parent": curr_p,
                    "message": f"Normalized transitive parent_lecture_slide on slide {s_num}: {p_int} -> {curr_p}.",
                })

    # Check adjacent batch boundaries for accidental duplicate spoken_lecture text
    for i in range(len(batch_boundaries) - 1):
        prev_end = batch_boundaries[i][1]
        next_start = batch_boundaries[i + 1][0]
        if prev_end in merged_by_num and next_start in merged_by_num:
            s_prev = merged_by_num[prev_end]
            s_next = merged_by_num[next_start]
            lec_prev = (s_prev.get("spoken_lecture") or "").strip()
            lec_next = (s_next.get("spoken_lecture") or "").strip()
            if len(lec_prev) > 80 and lec_prev == lec_next and not s_next.get("parent_lecture_slide"):
                root_parent = s_prev.get("parent_lecture_slide") or prev_end
                s_next["parent_lecture_slide"] = root_parent
                warnings.append({
                    "code": "DEDUPLICATED_BOUNDARY_SPOKEN_LECTURE",
                    "boundary": [prev_end, next_start],
                    "message": (
                        f"Slide {next_start} (start of batch {i+2}) had identical spoken_lecture to slide {prev_end} "
                        f"(end of batch {i+1}); linked parent_lecture_slide={root_parent} to prevent duplicate rendering."
                    ),
                })

    # Check for chunk-relative timestamp resets (e.g. 00:00 on slide 25)
    from text_utils import extract_timestamps, format_seconds_to_time
    max_time_sec = 0
    for s_obj in merged_slides_sorted:
        s_num = int(s_obj.get("slide_number", 0))
        time_str = s_obj.get("audio_time_range") or s_obj.get("audio_time")
        if time_str:
            ts_list = extract_timestamps(str(time_str))
            if ts_list:
                s_st = ts_list[0]
                has_xref = bool(s_obj.get("cross_references"))
                if s_num >= 5 and s_st < 180 and max_time_sec >= 480 and not has_xref:
                    warnings.append({
                        "code": "CHUNK_RELATIVE_TIMESTAMP_RESET",
                        "slide_number": s_num,
                        "timestamp": str(time_str),
                        "max_preceding_time": format_seconds_to_time(max_time_sec),
                        "message": (
                            f"Slide {s_num} timestamp ('{time_str}') resets to near 00:00 while preceding slides reached "
                            f"{format_seconds_to_time(max_time_sec)}. Likely chunk-relative timing. Convert to global continuous time."
                        )
                    })
                max_time_sec = max(max_time_sec, s_st)

    # Detect lecture termination and hallucinated trailing lecture displacement
    termination_phrases = ["خسته نباشید", "پایان جلسه", "آخرین اسلاید", "آخرین اسلایدم", "موفق باشید", "خداحافظ", "اتمام درس", "اتمام این جلسه"]
    term_slide_num = None
    for s_obj in merged_slides_sorted:
        spk = s_obj.get("spoken_lecture", "") or ""
        if any(tp in spk for tp in termination_phrases):
            term_slide_num = int(s_obj.get("slide_number", 0))
            break

    if term_slide_num is not None:
        earlier_lectures = {}
        for s_obj in merged_slides_sorted:
            s_num = int(s_obj.get("slide_number", 0))
            if s_num < term_slide_num:
                spk = (s_obj.get("spoken_lecture") or "").strip()
                if len(spk) >= 30:
                    earlier_lectures[s_num] = spk

        for s_obj in merged_slides_sorted:
            s_num = int(s_obj.get("slide_number", 0))
            if s_num > term_slide_num:
                spk = (s_obj.get("spoken_lecture") or "").strip()
                if spk:
                    for prev_n, prev_spk in earlier_lectures.items():
                        if spk == prev_spk or (len(spk) > 40 and spk in prev_spk) or (len(prev_spk) > 40 and prev_spk in spk):
                            errors.append({
                                "code": "HALLUCINATED_TRAILING_LECTURE_DISPLACEMENT",
                                "slide_number": s_num,
                                "source_slide": prev_n,
                                "message": (
                                    f"Slide {s_num} occurs after lecture termination at Slide {term_slide_num}, but hallucinates/copies "
                                    f"earlier spoken lecture from Slide {prev_n}! Unvoiced trailing slides must have 'is_skipped': true and 'spoken_lecture': \"\"."
                                )
                            })
                            break

    status = "PASSED" if not errors else "FAILED"
    report = {
        "status": status,
        "total_expected_slides": total_expected,
        "total_merged_slides": len(merged_slides_sorted),
        "output_path": _to_posix(output_path),
        "errors": errors,
        "warnings": warnings,
    }

    report_path = os.path.join(batches_dir, "merge_report.json")
    with open(report_path, "w", encoding="utf-8") as rf:
        json.dump(report, rf, ensure_ascii=False, indent=2)

    if not errors or not strict:
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(merged_slides_sorted, out_f, ensure_ascii=False, indent=2)

    return report


def run_qa_preflight_and_validate(
    raw_slides_path: str = "raw_slides.json",
    translated_path: str = "translated_slides.json",
    batches_dir: str = "batches",
    qa_report_path: str = "qa_audit_report.json",
    require_report: bool = False,
) -> Dict[str, Any]:
    """
    Builds the QA Critic Subagent Target Checklist (`batches/qa_target_dossier.json`)
    by cross-checking `raw_slides.json` and `translated_slides.json`, and validates
    `qa_audit_report.json` if `require_report=True` or if the report file exists.
    """
    if not os.path.exists(raw_slides_path):
        raise FileNotFoundError(f"Raw slides not found: {raw_slides_path}")
    if not os.path.exists(translated_path):
        raise FileNotFoundError(f"Translated slides not found: {translated_path}")

    raw_slides, _ = _load_json_slides(raw_slides_path)
    trans_slides, _ = _load_json_slides(translated_path)

    raw_by_num = {int(s["slide_number"]): s for s in raw_slides if "slide_number" in s}
    trans_by_num = {int(s["slide_number"]): s for s in trans_slides if "slide_number" in s}

    table_audit_targets = []
    visual_audit_targets = []
    structural_issues = []

    for s_num in sorted(raw_by_num.keys()):
        r_s = raw_by_num[s_num]
        t_s = trans_by_num.get(s_num)
        if not t_s:
            structural_issues.append({
                "slide_number": s_num,
                "issue": "MISSING_TRANSLATED_SLIDE",
                "detail": f"Slide {s_num} is missing from {translated_path}.",
            })
            continue

        has_raw_tbl = _slide_has_table(r_s)
        has_trans_tbl = _slide_has_valid_translated_table(t_s)
        if has_raw_tbl or has_trans_tbl:
            table_audit_targets.append({
                "slide_number": s_num,
                "raw_has_table": has_raw_tbl,
                "translated_has_table_data": has_trans_tbl,
                "image_path": _resolve_slide_image_path(r_s, s_num),
            })
            if has_raw_tbl and not has_trans_tbl:
                structural_issues.append({
                    "slide_number": s_num,
                    "issue": "RAW_TABLE_NOT_FORMATTED_AS_TABLE",
                    "detail": f"Slide {s_num} contains a table in the presentation, but 'table_data' is missing or empty in translated_slides.json.",
                })

        if _slide_needs_vision(r_s):
            visual_audit_targets.append({
                "slide_number": s_num,
                "image_path": _resolve_slide_image_path(r_s, s_num),
                "is_image_only": bool(r_s.get("is_image_only")),
                "has_tables": has_raw_tbl,
            })

    # Identify batch boundary pairs if batches_manifest.json exists
    boundary_pairs = []
    manifest_path = os.path.join(batches_dir, "batches_manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                m_data = json.load(mf)
            b_list = m_data.get("batches", [])
            for i in range(len(b_list) - 1):
                boundary_pairs.append([b_list[i]["end_slide"], b_list[i + 1]["start_slide"]])
        except Exception:
            pass

    # Audit ref_note density on lectured slides
    lectured_with_ref = []
    total_lectured_count = 0
    for s_num, t_s in trans_by_num.items():
        is_skip = bool(t_s.get("is_skipped") or t_s.get("unvoiced") or t_s.get("skipped_by_professor"))
        spk_words = len(t_s.get("spoken_lecture", "").split())
        needs_exp = bool(t_s.get("needs_reference_expansion"))
        if not is_skip and spk_words >= 40:
            total_lectured_count += 1
            if t_s.get("ref_note", "").strip() and not needs_exp:
                lectured_with_ref.append(s_num)

    ref_note_proliferation_flag = (
        total_lectured_count >= 4 and (len(lectured_with_ref) / total_lectured_count) > 0.25
    )
    if ref_note_proliferation_flag:
        structural_issues.append({
            "slide_number": lectured_with_ref[0] if lectured_with_ref else 0,
            "issue": "EXCESSIVE_REF_NOTE_PROLIFERATION",
            "detail": f"{len(lectured_with_ref)} of {total_lectured_count} lectured slides have 'ref_note'. 'ref_note' is strictly reserved for skipped or sparse-lecture slides (<30-40 words). Affected: {lectured_with_ref}",
        })

    os.makedirs(batches_dir, exist_ok=True)
    dossier = {
        "total_raw_slides": len(raw_by_num),
        "total_translated_slides": len(trans_by_num),
        "table_audit_targets": table_audit_targets,
        "visual_audit_targets": visual_audit_targets,
        "ref_note_audit": {
            "total_lectured_slides": total_lectured_count,
            "lectured_slides_with_ref_note": lectured_with_ref,
            "proliferation_ratio": (len(lectured_with_ref) / total_lectured_count) if total_lectured_count else 0.0,
            "excessive_proliferation_flag": ref_note_proliferation_flag,
        },
        "batch_boundary_pairs": boundary_pairs,
        "preflight_structural_issues": structural_issues,
        "qa_report_expected_path": _to_posix(qa_report_path),
        "qa_report_schema": {
            "status": "PASSED or NEEDS_FIXES",
            "total_slides_audited": len(raw_by_num),
            "table_slides_verified": [t["slide_number"] for t in table_audit_targets],
            "defects": [
                {
                    "slide_number": 0,
                    "category": "TABLE_FORMAT | SLIDE_ALIGNMENT | NUMERICAL_OMISSION | LECTURE_FIDELITY | BOUNDARY_DRIFT | REF_NOTE_PROLIFERATION",
                    "severity": "ERROR | WARNING",
                    "description": "Exact explanation of defect",
                    "remediation": "Exact fix required in translated_slides.json",
                }
            ],
        },
    }

    dossier_path = os.path.join(batches_dir, "qa_target_dossier.json")
    with open(dossier_path, "w", encoding="utf-8") as df:
        json.dump(dossier, df, ensure_ascii=False, indent=2)

    qa_report_valid = False
    qa_report_status = "MISSING"
    qa_defects = []

    if os.path.exists(qa_report_path):
        try:
            with open(qa_report_path, "r", encoding="utf-8") as qf:
                q_data = json.load(qf)
            qa_report_status = str(q_data.get("status", "UNKNOWN")).upper()
            qa_defects = q_data.get("defects", [])
            error_defects = [d for d in qa_defects if str(d.get("severity", "ERROR")).upper() == "ERROR"]
            if qa_report_status == "PASSED" and not error_defects and not structural_issues:
                qa_report_valid = True
        except Exception as e:
            qa_report_status = f"INVALID_JSON: {e}"

    return {
        "dossier_path": _to_posix(dossier_path),
        "preflight_issues_count": len(structural_issues),
        "preflight_issues": structural_issues,
        "table_targets_count": len(table_audit_targets),
        "visual_targets_count": len(visual_audit_targets),
        "qa_report_exists": os.path.exists(qa_report_path),
        "qa_report_status": qa_report_status,
        "qa_report_valid": qa_report_valid,
        "qa_defects": qa_defects,
        "passed": (len(structural_issues) == 0) and (qa_report_valid if require_report else True),
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Batch Partitioner, Merger, and QA Orchestrator")
    sub = parser.add_subparsers(dest="subcommand")

    p_part = sub.add_parser("partition", help="Partition raw_slides.json into isolated batches with Context Halo")
    p_part.add_argument("--raw", default="raw_slides.json", help="Path to raw_slides.json")
    p_part.add_argument("--batches-dir", default="batches", help="Directory for batch specs and shards")
    p_part.add_argument("--batch-size", type=int, default=12, help="Number of slides per batch (default: 12)")
    p_part.add_argument("--halo-size", type=int, default=1, help="Number of read-only context halo slides (default: 1)")
    p_part.add_argument("--img-dir", default="slide_images", help="Slide images directory")
    p_part.add_argument("--chunks-manifest", default="chunks_manifest.json", help="Audio chunks manifest path")

    p_merge = sub.add_parser("merge-batches", help="Validate and merge translated batch shards into translated_slides.json")
    p_merge.add_argument("--batches-dir", default="batches", help="Directory containing batch shards")
    p_merge.add_argument("--raw", default="raw_slides.json", help="Path to raw_slides.json")
    p_merge.add_argument("--output", default="translated_slides.json", help="Output path for merged translated_slides.json")
    p_merge.add_argument("--ref-book", default="رفرنس", help="Reference book name for ref_note sanitization")
    p_merge.add_argument("--no-strict", action="store_true", help="Write output even if non-fatal batch errors exist")

    p_qa = sub.add_parser("qa-check", help="Generate QA target dossier and validate qa_audit_report.json")
    p_qa.add_argument("--raw", default="raw_slides.json", help="Path to raw_slides.json")
    p_qa.add_argument("--translated", default="translated_slides.json", help="Path to translated_slides.json")
    p_qa.add_argument("--batches-dir", default="batches", help="Directory for QA target dossier")
    p_qa.add_argument("--qa-report", default="qa_audit_report.json", help="Path to QA Critic Subagent JSON report")
    p_qa.add_argument("--require-report", action="store_true", help="Fail with exit code 1 if qa_audit_report.json is missing or not PASSED")

    args = parser.parse_args()
    if args.subcommand == "partition":
        manifest = partition_slides(
            raw_slides_path=args.raw,
            batches_dir=args.batches_dir,
            batch_size=args.batch_size,
            halo_size=args.halo_size,
            img_dir=args.img_dir,
            chunks_manifest_path=args.chunks_manifest,
        )
        print(f"✅ Partitioned {manifest['total_slides']} slides into {manifest['total_batches']} isolated batches (batch_size={manifest['batch_size']}, halo={manifest['halo_size']}).")
        print(f"   Manifest written to: {_to_posix(os.path.join(args.batches_dir, 'batches_manifest.json'))}")
        for b in manifest["batches"]:
            print(
                f"   • {b['batch_id']} (Slides {b['start_slide']}..{b['end_slide']}) -> "
                f"Input: {b['raw_batch_file']} | Target Output: {b['output_shard_file']} "
                f"[Vision: {b['mandatory_vision_slides']}, Tables: {b['mandatory_table_slides']}]"
            )
        if manifest["audio_transcription_groups"]:
            print(f"   🎙️ Audio Parallel Groups ({manifest['total_audio_chunks']} chunks -> {len(manifest['audio_transcription_groups'])} subagent groups):")
            for ag in manifest["audio_transcription_groups"]:
                print(f"     - Audio Subagent {ag['audio_worker_index']}: chunks {ag['chunk_indices']} -> {ag['target_transcript_files']}")
        sys.exit(0)

    elif args.subcommand == "merge-batches":
        report = merge_slide_batches(
            batches_dir=args.batches_dir,
            raw_slides_path=args.raw,
            output_path=args.output,
            ref_book_name=args.ref_book,
            strict=not args.no_strict,
        )
        if report["warnings"]:
            print(f"⚠️ Merge completed with {len(report['warnings'])} warning(s):")
            for w in report["warnings"]:
                print(f"   - [{w['code']}] {w['message']}")
        if report["status"] == "PASSED":
            print(f"✅ Successfully merged {report['total_merged_slides']}/{report['total_expected_slides']} slides into '{report['output_path']}'.")
            sys.exit(0)
        else:
            print(f"❌ Merge FAILED with {len(report['errors'])} error(s):")
            for err in report["errors"]:
                print(f"   - [{err['code']}] {err['message']}")
            sys.exit(1)

    elif args.subcommand == "qa-check":
        res = run_qa_preflight_and_validate(
            raw_slides_path=args.raw,
            translated_path=args.translated,
            batches_dir=args.batches_dir,
            qa_report_path=args.qa_report,
            require_report=args.require_report,
        )
        print(f"🔎 QA Target Dossier generated at: {res['dossier_path']}")
        print(f"   • Table Slides to Audit : {res['table_targets_count']}")
        print(f"   • Visual Slides to Audit: {res['visual_targets_count']}")
        if res["preflight_issues"]:
            print(f"❌ Preflight Structural Issues Found ({res['preflight_issues_count']}):")
            for iss in res["preflight_issues"]:
                print(f"   - Slide {iss['slide_number']} [{iss['issue']}]: {iss['detail']}")
        if res["qa_report_exists"]:
            print(f"📋 QA Critic Report ('{args.qa_report}'): status={res['qa_report_status']}, valid={res['qa_report_valid']}")
            for d in res["qa_defects"]:
                print(f"   - Slide {d.get('slide_number')} [{d.get('severity', 'ERROR')}/{d.get('category', 'QA')}]: {d.get('description')}")
        elif args.require_report:
            print(f"❌ Required QA Critic Report '{args.qa_report}' is missing! Invoke the QA Critic Subagent first.")
        sys.exit(0 if res["passed"] else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
