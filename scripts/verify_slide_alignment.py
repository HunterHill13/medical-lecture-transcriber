#!/usr/bin/env python3
"""
verify_slide_alignment.py: Mandatory Automated Alignment Verification Gate & Auto-Remediation Engine.
Prevents off-by-N slide shifts, dropped image-only slides, and content-index drift
by comparing raw extracted presentation slides with translated slides before Word document generation.

Supports:
1. Console and structured JSON diagnostic reporting (alignment_diagnostic_slides.json).
2. Actionable Remediation Hints for autonomous agent self-healing (up to 3-retry budget).
3. --auto-fix: automatically repairs missing slide gaps by injecting Student Review badges from raw presentation data.

Usage:
    uv run python verify_slide_alignment.py --raw raw_slides.json --translated translated_slides.json [--diagnostic-json report.json] [--auto-fix]
"""

import os
import sys
import re
import json
import argparse

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
    extract_tokens,
    extract_substantive_tokens,
    is_ceremonial_slide,
    validate_cross_reference,
    normalize_for_matching,
    PERSIAN_PHARMA_INTERVENTIONS,
    evaluate_concept_overlap
)

# Clause markers that indicate full English prose/sentences inside parentheses
CLAUSE_MARKERS = {
    "is", "are", "was", "were", "be", "been", "being",
    "can", "cannot", "cant", "could", "couldnt", "will", "wont", "would", "wouldnt",
    "shall", "should", "may", "might", "must",
    "have", "has", "had", "having",
    "when", "if", "that", "which", "who", "whom", "whose", "where", "while",
    "because", "although", "though", "since", "unless",
    "with", "from", "into", "onto", "under", "over", "through",
    "provide", "provides", "provided", "replace", "replaces", "replaced",
    "direct", "directed", "cause", "caused", "causing", "lead", "leads", "leading",
    "occur", "occurs", "occurred", "due"
}


def load_ref_corpus(ref_path):
    """Loads reference book text and chunks it for hallucination verification."""
    if not ref_path or not os.path.exists(ref_path):
        return []
    corpus_chunks = []
    if os.path.isfile(ref_path):
        try:
            with open(ref_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                paras = [p.strip() for p in text.split("\n\n") if p.strip()]
                for p in paras:
                    corpus_chunks.append({
                        "text": p,
                        "tokens": extract_tokens([p])
                    })
        except Exception:
            pass
    elif os.path.isdir(ref_path):
        for root, _, files in os.walk(ref_path):
            for file in files:
                if file.endswith((".txt", ".md", ".json")):
                    fp = os.path.join(root, file)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read()
                            paras = [p.strip() for p in text.split("\n\n") if p.strip()]
                            for p in paras:
                                corpus_chunks.append({
                                    "text": p,
                                    "tokens": extract_tokens([p])
                                })
                    except Exception:
                        pass
    return corpus_chunks

MEDICAL_ACRONYM_COMPONENTS = {
    "pth": {"parathyroid", "hormone"},
    "tsh": {"thyroid", "stimulating", "hormone"},
    "acth": {"adrenocorticotropic", "hormone"},
    "fsh": {"follicle", "stimulating", "hormone"},
    "lh": {"luteinizing", "hormone"},
    "gh": {"growth", "hormone"},
    "prl": {"prolactin"},
    "adh": {"antidiuretic", "hormone", "vasopressin"},
    "t3": {"triiodothyronine"},
    "t4": {"thyroxine"},
    "htn": {"hypertension", "hypertensive"},
    "dm": {"diabetes", "mellitus"},
    "bp": {"blood", "pressure"},
    "hr": {"heart", "rate"},
    "rr": {"respiratory", "rate"},
    "chf": {"congestive", "heart", "failure"},
    "ckd": {"chronic", "kidney", "disease"},
    "copd": {"chronic", "obstructive", "pulmonary", "disease"},
    "mi": {"myocardial", "infarction"},
    "ecg": {"electrocardiogram", "electrocardiography"},
    "ekg": {"electrocardiogram", "electrocardiography"},
    "eeg": {"electroencephalogram"},
    "ct": {"computed", "tomography"},
    "mri": {"magnetic", "resonance", "imaging"},
    "pet": {"positron", "emission", "tomography"},
    "us": {"ultrasound", "ultrasonography"},
    "cxr": {"chest", "x-ray", "radiograph"},
    "cbc": {"complete", "blood", "count"},
    "esr": {"erythrocyte", "sedimentation", "rate"},
    "crp": {"c-reactive", "protein"},
    "ldl": {"low-density", "lipoprotein"},
    "hdl": {"high-density", "lipoprotein"},
    "vldl": {"very-low-density", "lipoprotein"},
    "tg": {"triglycerides", "triglyceride"},
    "bun": {"blood", "urea", "nitrogen"},
    "gfr": {"glomerular", "filtration", "rate"},
    "egfr": {"estimated", "glomerular", "filtration", "rate"},
    "ast": {"aspartate", "aminotransferase"},
    "alt": {"alanine", "aminotransferase"},
    "alp": {"alkaline", "phosphatase"},
    "ggt": {"gamma-glutamyl", "transferase"},
    "inr": {"international", "normalized", "ratio"},
    "pt": {"prothrombin", "time"},
    "ptt": {"partial", "thromboplastin", "time"},
    "aptt": {"activated", "partial", "thromboplastin", "time"},
    "abg": {"arterial", "blood", "gas"},
    "ards": {"acute", "respiratory", "distress", "syndrome"},
    "aki": {"acute", "kidney", "injury"},
    "uti": {"urinary", "tract", "infection"},
    "uri": {"upper", "respiratory", "infection"},
    "gerd": {"gastroesophageal", "reflux", "disease"},
    "ibd": {"inflammatory", "bowel", "disease"},
    "ibs": {"irritable", "bowel", "syndrome"},
    "sle": {"systemic", "lupus", "erythematosus"},
    "ra": {"rheumatoid", "arthritis"},
    "oa": {"osteoarthritis"},
    "ms": {"multiple", "sclerosis"},
    "als": {"amyotrophic", "lateral", "sclerosis"},
    "cva": {"cerebrovascular", "accident", "stroke"},
    "tia": {"transient", "ischemic", "attack"},
    "icp": {"intracranial", "pressure"},
    "csf": {"cerebrospinal", "fluid"},
    "dvt": {"deep", "vein", "thrombosis"},
    "pe": {"pulmonary", "embolism"},
    "pvd": {"peripheral", "vascular", "disease"},
    "pad": {"peripheral", "artery", "disease"},
    "cad": {"coronary", "artery", "disease"},
    "cabg": {"coronary", "artery", "bypass", "graft"},
    "pci": {"percutaneous", "coronary", "intervention"},
    "aed": {"automated", "external", "defibrillator"},
    "cpr": {"cardiopulmonary", "resuscitation"},
    "icu": {"intensive", "care", "unit"},
    "nicu": {"neonatal", "intensive", "care", "unit"},
    "picu": {"pediatric", "intensive", "care", "unit"},
    "er": {"emergency", "room"},
    "ed": {"emergency", "department"},
    "or": {"operating", "room"},
}

def validate_slide_schema(slide_dict, idx, available_slide_nums=None):
    """Validates structural types and required fields for a single translated slide without heavy external dependencies."""
    errs = []
    if not isinstance(slide_dict, dict):
        return [f"Slide item at index {idx} is not a valid JSON object/dict (got {type(slide_dict).__name__})"]
        
    s_num = slide_dict.get("slide_number")
    if s_num is None:
        errs.append(f"Slide item at index {idx}: missing required field 'slide_number'")
    elif not isinstance(s_num, int) or s_num <= 0:
        errs.append(f"Slide item at index {idx}: 'slide_number' must be a positive integer (got {s_num!r})")
        
    t_fa = slide_dict.get("title_fa")
    if t_fa is None:
        errs.append(f"Slide {s_num or idx}: missing required field 'title_fa'")
    elif not isinstance(t_fa, str):
        errs.append(f"Slide {s_num or idx}: 'title_fa' must be a string (got {type(t_fa).__name__})")
        
    t_en = slide_dict.get("title_en")
    if t_en is not None and not isinstance(t_en, str):
        errs.append(f"Slide {s_num or idx}: 'title_en' must be a string if provided (got {type(t_en).__name__})")
        
    bullets = slide_dict.get("bullets")
    if bullets is None:
        errs.append(f"Slide {s_num or idx}: missing required field 'bullets' (must be a list)")
    elif not isinstance(bullets, list):
        errs.append(f"Slide {s_num or idx}: 'bullets' must be a list (got {type(bullets).__name__})")
        
    spoken = slide_dict.get("spoken_lecture")
    if spoken is not None:
        if isinstance(spoken, list):
            if not all(isinstance(x, str) for x in spoken):
                errs.append(f"Slide {s_num or idx}: all items in 'spoken_lecture' list must be strings")
        elif not isinstance(spoken, str):
            errs.append(f"Slide {s_num or idx}: 'spoken_lecture' must be a string or list of strings (got {type(spoken).__name__})")
        
    if isinstance(bullets, list):
        for b_idx, b in enumerate(bullets):
            if isinstance(b, dict):
                if not isinstance(b.get("lead", ""), str) or not isinstance(b.get("text", ""), str):
                    errs.append(f"Slide {s_num or idx}, bullet {b_idx}: 'lead' and 'text' in bullet dict must be strings")
            elif isinstance(b, (tuple, list)):
                if len(b) != 2:
                    errs.append(f"Slide {s_num or idx}, bullet {b_idx}: tuple/list bullet must have exactly 2 elements [lead, text] (got {len(b)})")
                elif not all(isinstance(x, str) for x in b):
                    errs.append(f"Slide {s_num or idx}, bullet {b_idx}: tuple/list bullet items must be strings")
            elif not isinstance(b, str):
                errs.append(f"Slide {s_num or idx}, bullet {b_idx}: bullet must be a string, list/tuple of strings, or dict with 'lead' and 'text'")

    if "table_data" in slide_dict and slide_dict["table_data"] is not None:
        td = slide_dict["table_data"]
        if isinstance(td, dict):
            if "headers" not in td or not isinstance(td["headers"], list):
                errs.append(f"Slide {s_num or idx}: 'table_data.headers' must be a list of strings")
            if "rows" not in td or not isinstance(td["rows"], list):
                errs.append(f"Slide {s_num or idx}: 'table_data.rows' must be a list")
        elif isinstance(td, (list, tuple)):
            if len(td) != 2 or not isinstance(td[0], list) or not isinstance(td[1], list):
                errs.append(f"Slide {s_num or idx}: 'table_data' list format must be [headers_list, rows_list]")
        else:
            errs.append(f"Slide {s_num or idx}: 'table_data' must be a dict with 'headers' and 'rows' or a 2-element list [headers, rows]")
        
    ref_note = slide_dict.get("ref_note")
    if ref_note is not None and not isinstance(ref_note, str):
        errs.append(f"Slide {s_num or idx}: 'ref_note' must be a string (got {type(ref_note).__name__})")
        
    for bool_field in ["is_ceremonial", "is_image_heavy", "is_image_only", "needs_student_review"]:
        val = slide_dict.get(bool_field)
        if val is not None and not isinstance(val, bool):
            errs.append(f"Slide {s_num or idx}: '{bool_field}' must be a boolean (got {type(val).__name__})")
            
    for str_field in ["section_title", "audio_time", "audio_time_range", "student_review_note"]:
        val = slide_dict.get(str_field)
        if val is not None and not isinstance(val, str):
            errs.append(f"Slide {s_num or idx}: '{str_field}' must be a string (got {type(val).__name__})")
            
    asegs = slide_dict.get("audio_segments")
    if asegs is not None:
        if not isinstance(asegs, list):
            errs.append(f"Slide {s_num or idx}: 'audio_segments' must be a list of segment dicts")
        else:
            prev_end = None
            for s_idx, seg in enumerate(asegs):
                if not isinstance(seg, dict) or "start" not in seg or "end" not in seg:
                    errs.append(f"Slide {s_num or idx}, segment {s_idx}: segment must be a dict with 'start' and 'end' seconds")
                    continue
                start = seg.get("start")
                end = seg.get("end")
                if isinstance(start, bool) or not isinstance(start, (int, float)):
                    errs.append(f"Slide {s_num or idx}, segment {s_idx}: 'start' must be numeric (got {start!r})")
                    continue
                if isinstance(end, bool) or not isinstance(end, (int, float)):
                    errs.append(f"Slide {s_num or idx}, segment {s_idx}: 'end' must be numeric (got {end!r})")
                    continue
                if start < 0:
                    errs.append(f"Slide {s_num or idx}, segment {s_idx}: 'start' ({start}) cannot be negative")
                if end < start:
                    errs.append(f"Slide {s_num or idx}, segment {s_idx}: 'end' ({end}) cannot be less than 'start' ({start})")
                if prev_end is not None and start < prev_end - 0.01:
                    errs.append(f"Slide {s_num or idx}, segment {s_idx}: 'start' ({start}) overlaps with previous segment end ({prev_end})")
                prev_end = max(prev_end if prev_end is not None else 0, end)

    crefs = slide_dict.get("cross_references")
    if crefs is not None:
        if not isinstance(crefs, list):
            errs.append(f"Slide {s_num or idx}: 'cross_references' must be a list")
        else:
            for c_idx, ref in enumerate(crefs):
                is_val, msg = validate_cross_reference(ref, available_slide_nums)
                if not is_val:
                    errs.append(f"Slide {s_num or idx}, cross_reference {c_idx}: {msg}")

    qa_list = slide_dict.get("qa_list")
    if qa_list is not None and not isinstance(qa_list, list):
        errs.append(f"Slide {s_num or idx}: 'qa_list' must be a list (got {type(qa_list).__name__})")
            
    table_data = slide_dict.get("table_data")
    if table_data is not None:
        if isinstance(table_data, (list, tuple)) and len(table_data) == 2:
            headers, rows = table_data
            if not isinstance(headers, list) or not isinstance(rows, list):
                errs.append(f"Slide {s_num or idx}: 'table_data' list format must be [headers_list, rows_list]")
        elif isinstance(table_data, dict):
            if "headers" not in table_data or ("rows" not in table_data and "items" not in table_data):
                errs.append(f"Slide {s_num or idx}: 'table_data' dict format must have 'headers' and 'rows'/'items'")
        else:
            errs.append(f"Slide {s_num or idx}: 'table_data' must be a 2-element list [headers, rows] or a dict")
            
    return errs

def auto_fix_gaps(raw_db, trans_db, trans_path, total_slides):
    """Automatically repairs missing translated slide gaps by generating student review entries."""
    fixed = False
    for num in range(1, total_slides + 1):
        if num not in trans_db and num in raw_db:
            raw_item = raw_db[num]
            new_slide = {
                "slide_number": num,
                "title_fa": f"اسلاید {num}: نگاره / دیاگرام نیازمند بازبینی",
                "title_en": raw_item.get("title_raw") or raw_item.get("title") or f"Slide {num}",
                "is_image_only": True,
                "needs_student_review": True,
                "student_review_note": "این اسلاید در فایل خام ارائه صرفاً شامل نگاره، جدول یا دیاگرام بود و به طور خودکار جهت حفظ توالی صفحات به کادر اسلاید اضافه گردید.",
                "bullets": []
            }
            trans_db[num] = new_slide
            fixed = True
            
    if fixed:
        # Write back sorted
        sorted_trans = [trans_db[k] for k in sorted(trans_db.keys())]
        with open(trans_path, "w", encoding="utf-8") as f:
            json.dump(sorted_trans, f, ensure_ascii=False, indent=2)
        print(f"🔧 AUTO-FIX APPLIED: Repaired slide index gaps in '{trans_path}'.")
    return fixed

def _check_structural_extras(num: int, raw_item: dict, trans_item: dict, issues: list):
    """Checks table data presence and bullet structure across all slides, including ceremonial slides."""
    bullets = trans_item.get("bullets", [])
    if bullets and isinstance(bullets[0], str) and ":" not in bullets[0]:
        issues.append({
            "type": "FORMAT_ADVISORY",
            "error_type": "FORMAT_ADVISORY",
            "severity": "warning",
            "slide_number": num,
            "message": f"Slide {num}: Bullets are flat strings. Recommend using tuple (lead, text) or {{'lead': ..., 'text': ...}} for distinct bold headers."
        })
        
    has_tbl = bool(raw_item.get("has_tables") or raw_item.get("has_image_table") or trans_item.get("has_table"))
    td = trans_item.get("table_data")
    if has_tbl and not td:
        err_msg = f"MISSING TABLE DATA at Slide {num}: Presentation slide contains a structured or visual table, but 'table_data' is missing from translated_slides.json!"
        issues.append({
            "type": "MISSING_TABLE_DATA",
            "error_type": "MISSING_TABLE_DATA",
            "severity": "error",
            "slide_number": num,
            "message": err_msg,
            "remediation_action": "Provide complete 'table_data' with 'headers' and 'rows' for this table slide."
        })
    elif has_tbl and td:
        rows = []
        if isinstance(td, dict):
            rows = td.get("rows") or td.get("items", [])
        elif isinstance(td, (list, tuple)) and len(td) == 2:
            rows = td[1]
        if not rows:
            issues.append({
                "type": "INCOMPLETE_TABLE_TRANSCRIPTION",
                "error_type": "INCOMPLETE_TABLE_TRANSCRIPTION",
                "severity": "error",
                "slide_number": num,
                "message": f"INCOMPLETE TABLE at Slide {num}: 'table_data' has 0 rows! A structured or image table must contain all translated rows.",
                "remediation_action": "Populate 'table_data.rows' with all rows from the presentation table."
            })

def check_visual_asset_presence(num: int, raw_item: dict, trans_item: dict, img_dir: str = None) -> bool:
    """
    Checks if a visual asset (chart/diagram image) is available for the given slide.
    Checks:
    1. trans_item['img_path'] pointing to an existing file
    2. raw_item['img_path'] pointing to an existing file
    3. img_dir containing slide_{num:02d}.* or slide_{num:02d}_img.* or slide_{num}.*
    """
    for p in (trans_item.get("img_path"), raw_item.get("img_path")):
        if p and os.path.exists(p):
            return True
            
    if img_dir and os.path.isdir(img_dir):
        exts = ("png", "jpg", "jpeg", "wmf", "emf", "webp", "tiff", "tif", "bmp", "svg")
        prefixes = (f"slide_{num:02d}", f"slide_{num:03d}", f"slide_{num}_", f"slide_{num}.")
        try:
            for f in os.listdir(img_dir):
                fl = f.lower()
                if any(fl.startswith(p) for p in prefixes) and any(fl.endswith(f".{x}") for x in exts):
                    return True
        except Exception:
            pass
    return False

def check_slide_pair(raw_item: dict, trans_item: dict, trans_db: dict = None, allow_review: bool = False, img_dir: str = None) -> list[dict]:
    """
    Validates alignment, content fidelity, and hallucination bounds between a single raw slide and its translation.
    Returns a list of issue dictionaries:
    [
        {
            "type": str,
            "error_type": str,
            "severity": "error" | "warning",
            "slide_number": int,
            "message": str,
            "remediation_action": str (optional)
        }
    ]
    """
    issues = []
    try:
        raw_num = trans_item.get("slide_number") or raw_item.get("slide_number", 0)
        num = int(raw_num)
    except (ValueError, TypeError):
        num = 0

    raw_title = raw_item.get("title_raw", "") or raw_item.get("title", "")
    raw_lines = raw_item.get("text_lines", [])
    ocr_lines = raw_item.get("ocr_text_lines", [])
    raw_digital_lines = list(raw_lines)
    if raw_title and raw_title not in raw_digital_lines:
        raw_digital_lines.insert(0, raw_title)
    raw_digital_tokens = extract_substantive_tokens(raw_digital_lines)
    raw_ocr_tokens = extract_substantive_tokens(ocr_lines)
    raw_tokens = raw_digital_tokens.union(raw_ocr_tokens)
    raw_body_tokens = extract_substantive_tokens(list(raw_lines) + list(ocr_lines))
    
    trans_searchable = trans_item.get("title_en", "") + " " + trans_item.get("title_fa", "")
    trans_bullet_texts = []
    for b in trans_item.get("bullets", []):
        if isinstance(b, dict):
            b_txt = b.get("lead", "") + " " + b.get("text", "")
            trans_searchable += " " + b_txt
            trans_bullet_texts.append(b_txt)
        elif isinstance(b, (tuple, list)):
            b_txt = " ".join(str(x) for x in b)
            trans_searchable += " " + b_txt
            trans_bullet_texts.append(b_txt)
        else:
            b_txt = str(b)
            trans_searchable += " " + b_txt
            trans_bullet_texts.append(b_txt)

    trans_table_texts = []
    td = trans_item.get("table_data")
    if td:
        if isinstance(td, dict):
            headers = td.get("headers", [])
            for h in headers:
                if isinstance(h, str):
                    trans_searchable += " " + h
                    trans_table_texts.append(h)
            rows = td.get("rows") or td.get("items", [])
            for row in rows:
                if isinstance(row, dict):
                    if "text" in row and isinstance(row["text"], str):
                        trans_searchable += " " + row["text"]
                        trans_table_texts.append(row["text"])
                    if "cols" in row and isinstance(row["cols"], (list, tuple)):
                        for c in row["cols"]:
                            if isinstance(c, str):
                                trans_searchable += " " + c
                                trans_table_texts.append(c)
                elif isinstance(row, (list, tuple)):
                    for c in row:
                        if isinstance(c, str):
                            trans_searchable += " " + c
                            trans_table_texts.append(c)
                elif isinstance(row, str):
                    trans_searchable += " " + row
                    trans_table_texts.append(row)
        elif isinstance(td, (list, tuple)) and len(td) == 2:
            headers, rows = td
            if isinstance(headers, (list, tuple)):
                for h in headers:
                    if isinstance(h, str):
                        trans_searchable += " " + h
                        trans_table_texts.append(h)
            if isinstance(rows, (list, tuple)):
                for row in rows:
                    if isinstance(row, dict):
                        if "text" in row and isinstance(row["text"], str):
                            trans_searchable += " " + row["text"]
                            trans_table_texts.append(row["text"])
                        if "cols" in row and isinstance(row["cols"], (list, tuple)):
                            for c in row["cols"]:
                                if isinstance(c, str):
                                    trans_searchable += " " + c
                                    trans_table_texts.append(c)
                    elif isinstance(row, (list, tuple)):
                        for c in row:
                            if isinstance(c, str):
                                trans_searchable += " " + c
                                trans_table_texts.append(c)
                    elif isinstance(row, str):
                        trans_searchable += " " + row
                        trans_table_texts.append(row)

    trans_tokens = extract_tokens([trans_searchable])
    trans_bullet_tokens = extract_tokens(trans_bullet_texts)
    trans_table_tokens = extract_tokens(trans_table_texts)
    trans_body_tokens = trans_bullet_tokens.union(trans_table_tokens)

    body_common = evaluate_concept_overlap(raw_body_tokens, trans_body_tokens, " ".join(trans_bullet_texts + trans_table_texts))
    
    ceremonial = is_ceremonial_slide(trans_item) or is_ceremonial_slide(raw_item)
    has_tbl_content = bool(raw_item.get("has_tables") or raw_item.get("has_image_table") or trans_item.get("has_table") or trans_item.get("table_data"))
    is_image_heavy = bool(raw_item.get("is_image_heavy", False) or (raw_item.get("has_images", False) and len(raw_tokens) < 5))
    if has_tbl_content:
        is_image_heavy = False
    ocr_uncertain = bool(raw_item.get("ocr_uncertain", False))
    ocr_conf = float(raw_item.get("ocr_confidence", 0.0))
    has_image_text = bool(raw_item.get("has_image_text", False) and not ocr_uncertain and ocr_conf >= 0.60)
    if not has_image_text and len(ocr_lines) > 0 and not ocr_uncertain and ocr_conf >= 0.60:
        has_image_text = True

    has_visual_content = bool(
        raw_item.get("has_images") or 
        raw_item.get("has_charts") or 
        raw_item.get("has_smartart") or 
        raw_item.get("has_tables") or 
        raw_item.get("has_image_table") or
        raw_item.get("is_image_only")
    )
    is_pure_visual = bool(raw_item.get("is_pure_visual") or (not raw_tokens and has_visual_content and not has_image_text and not ocr_uncertain))
    
    if ceremonial:
        _check_structural_extras(num, raw_item, trans_item, issues)
        return issues
        
    # Check 3.0: Image Extraction Failure Diagnostic Warning
    if raw_item.get("image_extraction_error") or trans_item.get("image_extraction_error"):
        issues.append({
            "type": "IMAGE_EXTRACTION_FAILED",
            "error_type": "IMAGE_EXTRACTION_FAILED",
            "severity": "warning",
            "slide_number": num,
            "message": f"IMAGE EXTRACTION FAILED at Slide {num}: Embedded image extraction or rendering failed during presentation extraction. Visual inspection recommended.",
            "remediation_action": f"Inspect Slide {num} in presentation source or verify extracted slide image in image directory."
        })
        
    # Check 3.0.1: Visual Asset Presence Audit for Charts / Graphs
    if raw_item.get("has_charts") or raw_item.get("has_smartart"):
        has_asset = check_visual_asset_presence(num, raw_item, trans_item, img_dir=img_dir)
        if not has_asset:
            issues.append({
                "type": "VISUAL_ASSET_AUDIT",
                "error_type": "VISUAL_ASSET_AUDIT",
                "severity": "warning",
                "slide_number": num,
                "message": (f"VISUAL ASSET AUDIT at Slide {num}: Presentation slide contains a chart or graphical diagram (has_charts: True), "
                            f"but no resolved visual asset (img_path or slide_images file) was found! Ensure vector/WMF graphics are extracted and rasterized to PNG."),
                "remediation_action": f"Verify extraction of chart/diagram image for Slide {num} into slide_images and rasterize to PNG."
            })
        
    # Check 3.1: Phantom Content Hallucination Check for Pure Visual / Empty Raw Slides
    # Slides bearing OCR text (micrograph captions, diagram labels) are legitimate image-text slides, NOT pure visual.
    if is_pure_visual and not has_image_text:
        is_student_review = bool(trans_item.get("needs_student_review", False))
        trans_bullets = trans_item.get("bullets", [])
        if not is_student_review and len(trans_bullets) > 0:
            err_msg = (f"PHANTOM CONTENT HALLUCINATION at Slide {num}: Raw slide has ZERO text lines and ZERO OCR text (confirmed pure visual/graphic slide), "
                       f"but translated slide contains {len(trans_bullets)} fabricated bullets! "
                       f"Pure visual slides without text/captions must have bullets=[] unless marked with student review badge.")
            issues.append({
                "type": "PHANTOM_CONTENT_HALLUCINATION",
                "error_type": "PHANTOM_CONTENT_HALLUCINATION",
                "severity": "error",
                "slide_number": num,
                "message": err_msg,
                "remediation_action": f"Set bullets=[] for pure visual Slide {num} or provide needs_student_review: true."
            })
            return issues
            
    elif is_image_heavy:
        # Image-heavy slide: require title match or diagram note/explanation rather than blanket exemption
        raw_title = raw_item.get("title_raw", "")
        raw_title_tokens = extract_tokens([raw_title])
        title_overlap = raw_title_tokens.intersection(trans_tokens)
        has_desc = bool(trans_item.get("ref_note") or trans_item.get("spoken_lecture") or len(trans_tokens) >= 3)
        if not title_overlap and not has_desc:
            warn_msg = f"IMAGE-HEAVY SLIDE DEFICIENCY at Slide {num}: Visual slide with sparse text lacks both title match and diagram explanation!"
            issues.append({
                "type": "IMAGE_HEAVY_DEFICIENCY",
                "error_type": "IMAGE_HEAVY_DEFICIENCY",
                "severity": "warning",
                "slide_number": num,
                "message": warn_msg
            })
            
    elif raw_tokens:
        # Cross-Lingual Concept/Phrase Recall Evaluation (Strict Non-Generic)
        common = evaluate_concept_overlap(raw_tokens, trans_tokens, trans_searchable)

        recall_ratio = len(common) / max(1, len(raw_tokens))
        is_substantive_raw = len(raw_tokens) >= 4
        recall_failed = (recall_ratio < 0.50) if is_substantive_raw else (not common)

        if recall_failed:
            shift_detected = False
            if trans_db:
                for delta in [-2, -1, 1, 2]:
                    adj_num = num + delta
                    if adj_num in trans_db:
                        adj_trans = trans_db[adj_num]
                        adj_text = adj_trans.get("title_en", "") + " " + adj_trans.get("title_fa", "")
                        for b in adj_trans.get("bullets", []):
                            if isinstance(b, dict):
                                adj_text += " " + b.get("lead", "") + " " + b.get("text", "")
                            elif isinstance(b, (tuple, list)) and len(b) >= 2:
                                adj_text += " " + str(b[0]) + " " + str(b[1])
                            elif isinstance(b, (tuple, list)) and len(b) == 1:
                                adj_text += " " + str(b[0])
                            else:
                                adj_text += " " + str(b)
                        adj_tokens = extract_tokens([adj_text])
                        adj_common = raw_tokens.intersection(adj_tokens)
                        if len(adj_common) > len(common) and len(adj_common) >= 3:
                            err_msg = f"OFFSET SHIFT DETECTED at Slide {num}: Content from Raw Page {num} appears in Translated Slide {adj_num} (Shift: {delta:+d})! Common terms: {list(adj_common)[:4]}"
                            issues.append({
                                "type": "OFFSET_SHIFT",
                                "error_type": "OFFSET_SHIFT",
                                "severity": "error",
                                "slide_number": num,
                                "shifted_to": adj_num,
                                "offset_delta": delta,
                                "common_terms": list(adj_common)[:4],
                                "message": err_msg,
                                "remediation_action": f"Re-index translated slides starting from slide {num} with offset {-delta}."
                            })
                            shift_detected = True
                            break
            if not shift_detected:
                # Check for Remote Content Drift beyond +/- 2 window
                remote_candidates = []
                if trans_db:
                    for other_num, other_trans in trans_db.items():
                        if abs(other_num - num) > 2:
                            other_text = other_trans.get("title_en", "") + " " + other_trans.get("title_fa", "")
                            for b in other_trans.get("bullets", []):
                                if isinstance(b, dict):
                                    other_text += " " + b.get("lead", "") + " " + b.get("text", "")
                                elif isinstance(b, (tuple, list)):
                                    other_text += " " + " ".join(str(x) for x in b)
                                else:
                                    other_text += " " + str(b)
                            other_tokens = extract_tokens([other_text])
                            remote_common = raw_tokens.intersection(other_tokens)
                            if len(remote_common) > len(common) and len(remote_common) >= 3:
                                remote_candidates.append((other_num, remote_common))

                if remote_candidates:
                    r_num, r_common = remote_candidates[0]
                    err_msg = (f"REMOTE CONTENT DRIFT DETECTED at Slide {num}: Content from Raw Page {num} appears in "
                               f"Remote Translated Slide {r_num} (Distance: {r_num - num:+d})! Common terms: {list(r_common)[:4]}. "
                               f"Slide {num} only recalls {len(common)}/{len(raw_tokens)} concepts ({recall_ratio*100:.1f}%).")
                    issues.append({
                        "type": "REMOTE_CONTENT_DRIFT",
                        "error_type": "REMOTE_CONTENT_DRIFT",
                        "severity": "error",
                        "slide_number": num,
                        "remote_slide_number": r_num,
                        "distance": r_num - num,
                        "common_terms": list(r_common)[:4],
                        "message": err_msg,
                        "remediation_action": f"Re-anchor content belonging to Slide {num} back to Slide {num} instead of remote Slide {r_num}."
                    })
                elif len(common) == 0 or (not trans_item.get("title_en") and len(body_common) == 0):
                    err_msg = f"PARAMETRIC HALLUCINATION RISK at Slide {num}: Zero token overlap between Raw ({list(raw_tokens)[:5]}) and Translated ({list(trans_tokens)[:5]}). Ensure slide box contains literal translation of slide bullets, NOT ungrounded textbook prose!"
                    issues.append({
                        "type": "PARAMETRIC_HALLUCINATION_RISK",
                        "error_type": "PARAMETRIC_HALLUCINATION_RISK",
                        "severity": "error",
                        "slide_number": num,
                        "raw_tokens": list(raw_tokens)[:5],
                        "message": err_msg,
                        "remediation_action": f"Re-translate Slide {num} strictly from raw_slides.json text lines."
                    })
                else:
                    # Substantive Recall Deficiency (0 < recall_ratio < 0.50 on raw slide with >= 4 tokens)
                    missing_tokens = sorted(list(raw_tokens - common))
                    missing_digital = [t for t in missing_tokens if t in raw_digital_tokens]
                    missing_ocr = [t for t in missing_tokens if t in raw_ocr_tokens]
                    if len(missing_ocr) > len(missing_digital) and len(raw_ocr_tokens) > 0:
                        source_category = "missing_from_source_extraction"
                    else:
                        source_category = "missing_from_translation"

                    is_student_review = bool(trans_item.get("needs_student_review", False))
                    sev = "warning" if (is_student_review and allow_review) else "error"

                    err_msg = (f"SUBSTANTIVE SLIDE RECALL DEFICIENCY at Slide {num}: Raw slide contains {len(raw_tokens)} substantive concepts, "
                               f"but translated slide only recalls {len(common)} concepts ({recall_ratio*100:.1f}%), falling below the mandatory 50% threshold! "
                               f"Missing terms: {missing_tokens[:6]}. Source: {source_category}. "
                               f"Slide text must be a faithful translation of Raw Slide {num} without hallucination, audio-leakage, or enrichment.")
                    issues.append({
                        "type": "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY",
                        "error_type": "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY",
                        "severity": sev,
                        "slide_number": num,
                        "recall_ratio": round(recall_ratio, 3),
                        "required_threshold": 0.50,
                        "common_tokens": sorted(list(common)),
                        "missing_tokens": missing_tokens,
                        "source_category": source_category,
                        "missing_from_digital": missing_digital,
                        "missing_from_ocr": missing_ocr,
                        "message": err_msg,
                        "remediation_action": f"Translate missing substantive concepts {missing_tokens[:5]} directly from Raw Slide {num}."
                    })

        # Check 3.3.0: Table Completeness & Substantive Coverage Gate (Strict Diagnostic Preservation)
        if has_tbl_content and td:
            raw_table_tokens = set()
            if raw_item.get("has_image_table") or (raw_item.get("has_images") and ocr_lines):
                raw_table_tokens = raw_ocr_tokens
            elif raw_item.get("has_tables"):
                table_lines = [l for l in raw_lines if "|" in l or "\t" in l]
                if not table_lines:
                    table_lines = raw_lines
                raw_table_tokens = extract_substantive_tokens(table_lines)
            elif ocr_lines:
                raw_table_tokens = raw_ocr_tokens
            
            if len(raw_table_tokens) >= 4:
                table_common = evaluate_concept_overlap(raw_table_tokens, trans_table_tokens, " ".join(trans_table_texts))
                table_recall = len(table_common) / max(1, len(raw_table_tokens))
                if table_recall < 0.50:
                    missing_concepts = sorted(list(raw_table_tokens - table_common))[:8]
                    issues.append({
                        "type": "INCOMPLETE_TABLE_TRANSCRIPTION",
                        "error_type": "INCOMPLETE_TABLE_TRANSCRIPTION",
                        "severity": "error",
                        "slide_number": num,
                        "message": (f"INCOMPLETE TABLE TRANSCRIPTION at Slide {num}: Table substantive recall is {table_recall:.1%} "
                                    f"(threshold: 50.0%). Key table rows, subcategories, or diagnostic criteria were omitted or summarized away. "
                                    f"Uncovered table concepts: {missing_concepts}"),
                        "remediation_action": "Translate 100% of rows, subcategories, and parenthetical items in table_data without omitting clinical details."
                    })

        # Check 3.3.1: Anti-Clause Parentheses Gate (Strict Parenthetical Entity Enforcement)
        # Strictly forbids copying full English sentences, clauses, or long descriptive phrases into parentheses.
        # English in slide bullets is strictly reserved for concise proper names, drug names, and entity acronyms.
        for b_idx, b in enumerate(trans_item.get("bullets", [])):
            b_txt = ""
            if isinstance(b, dict):
                b_txt = b.get("lead", "") + " " + b.get("text", "")
            elif isinstance(b, (tuple, list)):
                b_txt = " ".join(str(x) for x in b)
            else:
                b_txt = str(b)

            parentheticals = re.findall(r'[\(（]([^)）]+)[\)）]', b_txt)
            for p_str in parentheticals:
                p_clean = p_str.strip()
                en_words = re.findall(r'[A-Za-z]+', p_clean)
                if not en_words:
                    continue
                has_clause_marker = any(w.lower() in CLAUSE_MARKERS for w in en_words)
                has_sentence_punct = bool(re.search(r'[;\.]{1,}', p_clean) and len(en_words) >= 3)

                if len(en_words) > 5 or (len(en_words) >= 3 and has_clause_marker) or has_sentence_punct:
                    issues.append({
                        "type": "PARENTHETICAL_CLAUSE_VIOLATION",
                        "error_type": "PARENTHETICAL_CLAUSE_VIOLATION",
                        "severity": "error",
                        "slide_number": num,
                        "bullet_index": b_idx,
                        "parenthetical_content": p_clean[:80],
                        "word_count": len(en_words),
                        "message": (f"PARENTHETICAL CLAUSE VIOLATION at Slide {num}, Bullet {b_idx}: Bullet contains full English clause "
                                    f"or sentence in parentheses ('{p_clean[:60]}...'). Slide boxes must contain fluent Persian "
                                    f"academic translation; English is strictly restricted to concise proper names, drug names, and medical "
                                    f"entity acronyms (maximum 4-5 words, no verbs/clauses)."),
                        "remediation_action": "Remove English clause from parentheses and express the statement cleanly in Persian prose."
                    })

            # Check 3.3.1b: Unprocessed English Clause Violation (outside parentheses)
            # Strictly forbids leaving unparenthesized, un-translated English sentences or clauses directly in Persian bullets.
            unparenthesized_txt = re.sub(r'[\(（][^)）]+[\)）]', ' ', b_txt)
            raw_en_runs = re.findall(r'[A-Za-z]+(?:\s+[A-Za-z]+){3,}', unparenthesized_txt)
            for en_run in raw_en_runs:
                run_clean = en_run.strip()
                en_run_words = re.findall(r'[A-Za-z]+', run_clean)
                has_run_clause = any(w.lower() in CLAUSE_MARKERS for w in en_run_words)
                if len(en_run_words) >= 5 or (len(en_run_words) >= 4 and has_run_clause):
                    issues.append({
                        "type": "UNPROCESSED_ENGLISH_CLAUSE_VIOLATION",
                        "error_type": "UNPROCESSED_ENGLISH_CLAUSE_VIOLATION",
                        "severity": "error",
                        "slide_number": num,
                        "bullet_index": b_idx,
                        "raw_english_content": run_clean[:80],
                        "word_count": len(en_run_words),
                        "message": (f"UNPROCESSED ENGLISH CLAUSE VIOLATION at Slide {num}, Bullet {b_idx}: Bullet contains un-translated English "
                                    f"clause or phrase ('{run_clean[:60]}...') directly in Persian prose! Slide boxes must be fluent Persian "
                                    f"academic translations; raw English clauses cannot be left un-translated outside parentheses."),
                        "remediation_action": "Translate English clause into Persian prose rather than leaving raw English words in slide text."
                    })

        # Check 3.4: Source Exclusivity & Unsupported Slide Box Content Audit
        # Ensures translated slide box does not inject extensive ungrounded external technical concepts.
        num_digital = len(raw_item.get("text_lines", []))
        num_ocr = len(raw_item.get("ocr_text_lines", []))
        total_source_lines = max(1, num_digital + num_ocr)

        bullet_texts = []
        for b_idx, b in enumerate(trans_item.get("bullets", [])):
            if isinstance(b, dict):
                bullet_texts.append(b.get("lead", "") + " " + b.get("text", ""))
                if "source_refs" in b:
                    srefs = b["source_refs"]
                    if not isinstance(srefs, list):
                        issues.append({
                            "type": "INVALID_SOURCE_REF",
                            "error_type": "INVALID_SOURCE_REF",
                            "severity": "warning",
                            "slide_number": num,
                            "message": f"Slide {num}: bullet 'source_refs' must be a list of identifiers (got {type(srefs).__name__})."
                        })
                    else:
                        for ref in srefs:
                            ref_valid = True
                            if isinstance(ref, int):
                                if ref < 0 or ref >= total_source_lines:
                                    ref_valid = False
                            elif isinstance(ref, str):
                                ref_clean = ref.strip()
                                if ":" in ref_clean:
                                    prefix, idx_str = ref_clean.split(":", 1)
                                    prefix = prefix.strip().lower()
                                    if idx_str.strip().isdigit():
                                        idx = int(idx_str.strip())
                                        if prefix in ("digital", "line") and (idx < 0 or idx >= max(1, num_digital)):
                                            ref_valid = False
                                        elif prefix == "ocr" and (idx < 0 or idx >= max(1, num_ocr)):
                                            ref_valid = False
                                elif ref_clean.isdigit():
                                    idx = int(ref_clean)
                                    if idx < 0 or idx >= total_source_lines:
                                        ref_valid = False
                            if not ref_valid:
                                issues.append({
                                    "type": "INVALID_SOURCE_REF_BOUNDS",
                                    "error_type": "INVALID_SOURCE_REF_BOUNDS",
                                    "severity": "warning",
                                    "slide_number": num,
                                    "message": f"Slide {num}: bullet {b_idx + 1} source_ref '{ref}' is out of bounds (digital lines: {num_digital}, ocr lines: {num_ocr})."
                                })
                            else:
                                # Semantic provenance verification: resolve referenced line text
                                line_text = ""
                                if isinstance(ref, int):
                                    all_lines = raw_item.get("text_lines", []) + raw_item.get("ocr_text_lines", [])
                                    if 0 <= ref < len(all_lines):
                                        line_text = all_lines[ref]
                                elif isinstance(ref, str):
                                    ref_clean = ref.strip()
                                    if ":" in ref_clean:
                                        prefix, idx_str = ref_clean.split(":", 1)
                                        prefix = prefix.strip().lower()
                                        if idx_str.strip().isdigit():
                                            idx = int(idx_str.strip())
                                            if prefix in ("digital", "line") and 0 <= idx < len(raw_item.get("text_lines", [])):
                                                line_text = raw_item.get("text_lines", [])[idx]
                                            elif prefix == "ocr" and 0 <= idx < len(raw_item.get("ocr_text_lines", [])):
                                                line_text = raw_item.get("ocr_text_lines", [])[idx]
                                    elif ref_clean.isdigit():
                                        idx = int(ref_clean)
                                        all_lines = raw_item.get("text_lines", []) + raw_item.get("ocr_text_lines", [])
                                        if 0 <= idx < len(all_lines):
                                            line_text = all_lines[idx]

                                if line_text:
                                    line_tokens = extract_tokens([line_text])
                                    b_text = b.get("lead", "") + " " + b.get("text", "")
                                    b_tokens = extract_tokens([b_text])
                                    line_expanded = set(line_tokens)
                                    for lt in line_tokens:
                                        lt_l = lt.lower()
                                        if lt_l in MEDICAL_ACRONYM_COMPONENTS:
                                            line_expanded.update(MEDICAL_ACRONYM_COMPONENTS[lt_l])
                                        for acr, words in MEDICAL_ACRONYM_COMPONENTS.items():
                                            if lt_l in words:
                                                line_expanded.add(acr)
                                    overlap = b_tokens.intersection(line_expanded)
                                    if line_tokens and not overlap:
                                        issues.append({
                                            "type": "UNGROUNDED_SOURCE_REF_MAPPING",
                                            "error_type": "UNGROUNDED_SOURCE_REF_MAPPING",
                                            "severity": "warning",
                                            "slide_number": num,
                                            "message": f"Slide {num}: bullet {b_idx + 1} cites '{ref}' ('{line_text[:40]}...'), but shares no substantive concepts with it."
                                        })
            elif isinstance(b, (tuple, list)):
                bullet_texts.append(" ".join(str(x) for x in b))
            else:
                bullet_texts.append(str(b))

        bullet_tokens = extract_tokens(bullet_texts)
        bullet_tech_tokens = {
            t for t in bullet_tokens
            if any(c.isascii() and (c.isalpha() or c.isdigit()) for c in t) or '%' in t
        }
        raw_tech_tokens = {
            t for t in raw_tokens
            if any(c.isascii() and (c.isalpha() or c.isdigit()) for c in t) or '%' in t
        }

        # Collect allowed acronym expansions from raw tokens
        allowed_acronym_expansions = set()
        for rt in raw_tokens:
            rt_lower = rt.lower()
            if rt_lower in MEDICAL_ACRONYM_COMPONENTS:
                allowed_acronym_expansions.update(MEDICAL_ACRONYM_COMPONENTS[rt_lower])
            for acr, words in MEDICAL_ACRONYM_COMPONENTS.items():
                if rt_lower in words:
                    allowed_acronym_expansions.add(acr)
                    allowed_acronym_expansions.update(words)

        unsupported_tech = bullet_tech_tokens - raw_tech_tokens - allowed_acronym_expansions
        
        # Persian Clinical Pharmacology & Intervention Intrusion Audit
        raw_full_corpus = " ".join(raw_item.get("text_lines", []) + raw_item.get("ocr_text_lines", [])).lower()
        unsupported_persian_pharma = set()
        for bt in bullet_tokens:
            if bt in PERSIAN_PHARMA_INTERVENTIONS:
                en_drug = PERSIAN_PHARMA_INTERVENTIONS[bt].lower()
                if bt not in raw_full_corpus and en_drug not in raw_full_corpus and en_drug not in raw_tech_tokens:
                    unsupported_persian_pharma.add(bt)

        # Source Quote Verification
        all_raw_lines = raw_item.get("text_lines", []) + raw_item.get("ocr_text_lines", [])
        for b_idx, b in enumerate(trans_item.get("bullets", [])):
            if isinstance(b, dict) and "source_quote" in b:
                sq = str(b.get("source_quote", "")).strip()
                if sq:
                    sq_norm = normalize_for_matching(sq).lower()
                    if len(sq_norm) >= 6 and sq_norm not in raw_full_corpus and not any(sq_norm in normalize_for_matching(l).lower() for l in all_raw_lines):
                        issues.append({
                            "type": "UNVERIFIED_SOURCE_QUOTE",
                            "error_type": "UNVERIFIED_SOURCE_QUOTE",
                            "severity": "warning",
                            "slide_number": num,
                            "message": f"Slide {num}: bullet {b_idx + 1} source_quote '{sq[:40]}...' was not found in Raw Slide {num}."
                        })

        is_student_review = bool(trans_item.get("needs_student_review", False))
        all_unsupported = set()
        if is_substantive_raw and len(unsupported_tech) >= 4:
            all_unsupported.update(unsupported_tech)
        if unsupported_persian_pharma:
            all_unsupported.update(unsupported_persian_pharma)

        if all_unsupported and not is_student_review:
            err_msg = (
                f"UNSUPPORTED SLIDE BOX CONTENT at Slide {num}: Translated slide box introduces "
                f"ungrounded concepts {sorted(list(all_unsupported))[:6]} not found anywhere in Raw Slide {num}! "
                f"Track 2 (slide box) must strictly reflect slide content. "
                f"Supplementary reference notes belong in ref_note (Track 3) and spoken lecture belongs in spoken_lecture (Track 1)."
            )
            issues.append({
                "type": "UNSUPPORTED_SLIDE_BOX_CONTENT",
                "error_type": "UNSUPPORTED_SLIDE_BOX_CONTENT",
                "severity": "error",
                "slide_number": num,
                "unsupported_tokens": sorted(list(all_unsupported)),
                "message": err_msg,
                "remediation_action": f"Remove ungrounded external concepts {sorted(list(all_unsupported))[:4]} from Slide {num} bullets or move them to ref_note."
            })

        # Check 3.4b: Table Row Ungrounded Content Audit (Table Hallucination Gate)
        # Prevents parametric memory leakage into table_data (e.g. injecting Grade 0 into Wagner classification when raw slide only has 1-5)
        if td and not is_student_review:
            raw_full_table_text = " ".join(raw_item.get("text_lines", []) + raw_item.get("ocr_text_lines", [])).lower()
            raw_full_tokens = extract_tokens([raw_full_table_text])
            raw_norm = normalize_for_matching(raw_full_table_text)
            
            rows = []
            if isinstance(td, dict):
                rows = td.get("rows") or td.get("items", [])
            elif isinstance(td, (list, tuple)) and len(td) == 2:
                rows = td[1]
                
            for r_idx, r in enumerate(rows):
                row_str = ""
                if isinstance(r, dict):
                    row_str = r.get("text", "") + " " + " ".join(str(c) for c in r.get("cols", []))
                elif isinstance(r, (list, tuple)):
                    row_str = " ".join(str(c) for c in r)
                elif isinstance(r, str):
                    row_str = r
                
                # Check for numerical / grade classification hallucination:
                # E.g. Grade 0 / گرید ۰ when '0' or 'zero' or '۰' does not exist anywhere in raw slide
                grade_match = re.search(r'(?:گرید|درجه|grade|stage|گروه|تیپ)\s*([0-9\u06F0-\u06F9IVXLCDM]+)', row_str, re.IGNORECASE)
                if grade_match:
                    found_grade = grade_match.group(1).lower()
                    grade_norm = normalize_for_matching(found_grade)
                    if grade_norm not in raw_norm and found_grade not in raw_full_table_text:
                        issues.append({
                            "type": "UNGROUNDED_TABLE_ROW_CONTENT",
                            "error_type": "UNGROUNDED_TABLE_ROW_CONTENT",
                            "severity": "error",
                            "slide_number": num,
                            "row_index": r_idx,
                            "hallucinated_item": grade_match.group(0),
                            "message": (f"UNGROUNDED TABLE ROW CONTENT at Slide {num}, Row {r_idx + 1}: Table introduces fabricated category "
                                        f"'{grade_match.group(0)}' not found anywhere in Raw Slide {num}! Table data must strictly reflect "
                                        f"the slide content without parametric memory hallucination."),
                            "remediation_action": f"Remove ungrounded item '{grade_match.group(0)}' from Slide {num} table_data."
                        })

    elif not ceremonial:
        # Check for silent bypass on text slides
        raw_text_len = sum(len(l.strip()) for l in raw_lines)
        is_visual_or_img = bool(raw_item.get("is_image_only", False) or raw_item.get("has_images", False) or trans_item.get("is_image_only", False))
        if raw_text_len >= 30 and not is_visual_or_img:
            warn_msg = f"UNVERIFIED SLIDE CONTENT at Slide {num}: Raw slide has {raw_text_len} characters of text, but 0 substantive tokens were extracted for alignment matching!"
            issues.append({
                "type": "UNVERIFIED_SLIDE_CONTENT",
                "error_type": "UNVERIFIED_SLIDE_CONTENT",
                "severity": "warning",
                "slide_number": num,
                "message": warn_msg
            })
            
    _check_structural_extras(num, raw_item, trans_item, issues)
    return issues

def main():
    parser = argparse.ArgumentParser(description="Mandatory Automated Alignment Verification Gate & Auto-Remediation")
    parser.add_argument("--raw", "-r", required=True, help="Path to raw_slides.json")
    parser.add_argument("--translated", "-t", required=True, help="Path to translated_slides.json")
    parser.add_argument("--diagnostic-json", "-j", default="alignment_diagnostic_slides.json", help="Path to write JSON diagnostic report")
    parser.add_argument("--auto-fix", action="store_true", help="Automatically repair missing slide gaps")
    parser.add_argument("--ref-corpus", help="Optional path to reference book corpus (file/folder) for ref_note grounding verification")
    parser.add_argument("--allow-review", action="store_true", help="Allow REVIEW_REQUIRED state for slides with needs_student_review: true")
    parser.add_argument("--img-dir", default=None, help="Optional slide images directory to audit visual assets (e.g. ./slide_images)")
    args = parser.parse_args()
    
    if not os.path.exists(args.raw):
        print(f"Error: Raw slides file '{args.raw}' does not exist!", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.translated):
        print(f"Error: Translated slides file '{args.translated}' does not exist!", file=sys.stderr)
        sys.exit(1)
        
    with open(args.raw, "r", encoding="utf-8") as f:
        raw_list = json.load(f)
    with open(args.translated, "r", encoding="utf-8") as f:
        trans_list = json.load(f)
        
    errors = []
    warnings = []
    diagnostics = {
        "gate_status": "PENDING",
        "total_raw": 0,
        "total_translated": 0,
        "errors": [],
        "warnings": [],
        "remediation_hints": []
    }

    from collections import Counter

    # 1. Parse raw slide numbers and check for duplicates & invalid values
    raw_numbers = []
    raw_db = {}
    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            err_msg = f"MALFORMED RAW SLIDE: Item at index {idx} in raw_slides.json is not a valid JSON dict!"
            errors.append(err_msg)
            diagnostics["errors"].append({"error_type": "SCHEMA_VALIDATION_ERROR", "message": err_msg})
            continue
        val = item.get("slide_number")
        try:
            num = int(val)
        except (ValueError, TypeError):
            err_msg = f"MALFORMED SLIDE NUMBER in raw_slides.json at index {idx}: expected integer, got {val!r}"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "SCHEMA_VALIDATION_ERROR",
                "message": err_msg,
                "remediation_action": "Ensure all slide_number values are positive integers."
            })
            continue
        raw_numbers.append(num)
        raw_db[num] = item

    raw_counts = Counter(raw_numbers)
    for num, count in raw_counts.items():
        if count > 1:
            err_msg = f"DUPLICATE SLIDE NUMBER in raw_slides.json: Slide index {num} appears {count} times!"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "DUPLICATE_SLIDE_NUMBER",
                "slide_number": num,
                "count": count,
                "message": err_msg,
                "remediation_action": f"Remove duplicate slide entries for slide {num}."
            })

    # 2. Parse translated slide numbers and check for duplicates & invalid values
    trans_numbers = []
    trans_db = {}
    for idx, item in enumerate(trans_list):
        if not isinstance(item, dict):
            err_msg = f"MALFORMED TRANSLATED SLIDE: Item at index {idx} in translated_slides.json is not a valid JSON dict!"
            errors.append(err_msg)
            diagnostics["errors"].append({"error_type": "SCHEMA_VALIDATION_ERROR", "message": err_msg})
            continue
        val = item.get("slide_number")
        try:
            num = int(val)
        except (ValueError, TypeError):
            err_msg = f"MALFORMED SLIDE NUMBER in translated_slides.json at index {idx}: expected integer, got {val!r}"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "SCHEMA_VALIDATION_ERROR",
                "message": err_msg,
                "remediation_action": "Ensure all slide_number values are positive integers."
            })
            continue
        trans_numbers.append(num)
        trans_db[num] = item

    trans_counts = Counter(trans_numbers)
    for num, count in trans_counts.items():
        if count > 1:
            err_msg = f"DUPLICATE SLIDE NUMBER in translated_slides.json: Slide index {num} appears {count} times!"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "DUPLICATE_SLIDE_NUMBER",
                "slide_number": num,
                "count": count,
                "message": err_msg,
                "remediation_action": f"Remove duplicate slide entries for slide {num}."
            })

    total_raw = len(raw_db)
    total_trans = len(trans_db)
    total_slides = max(total_raw, total_trans)
    diagnostics["total_raw"] = total_raw
    diagnostics["total_translated"] = total_trans

    if args.auto_fix:
        if auto_fix_gaps(raw_db, trans_db, args.translated, total_slides):
            total_trans = len(trans_db)
            total_slides = max(total_raw, total_trans)

    print("=" * 65)
    print("🔍 MANDATORY AUTOMATED ALIGNMENT VERIFICATION GATE")
    print("=" * 65)
    print(f"• Total Raw Slides: {total_raw}")
    print(f"• Total Translated Slides: {total_trans}")

    # Check 0: Structural Schema Validation for translated_slides.json
    available_nums = set(trans_db.keys())
    for idx, item in enumerate(trans_list):
        schema_errs = validate_slide_schema(item, idx + 1, available_slide_nums=available_nums)
        for serr in schema_errs:
            err_msg = f"SCHEMA VALIDATION ERROR: {serr}"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "SCHEMA_VALIDATION_ERROR",
                "slide_index": idx + 1,
                "message": err_msg,
                "remediation_action": "Fix field type or missing required key in translated_slides.json."
            })
            
    # Check 1: Slide Count Match
    if total_raw != total_trans:
        err_msg = f"COUNT MISMATCH: Raw presentation has {total_raw} slides, but translated database has {total_trans} slides!"
        errors.append(err_msg)
        diagnostics["errors"].append({
            "error_type": "COUNT_MISMATCH",
            "message": err_msg,
            "remediation_action": "Run with --auto-fix or ensure every presentation page from 1 to N is defined in translated_slides.json."
        })
        
    # Check 2: Strict Consecutive Indexing (1 to N, zero gap, zero drop)
    for num in range(1, total_slides + 1):
        if num not in raw_db:
            err_msg = f"MISSING RAW SLIDE: Slide index {num} is missing from raw_slides.json!"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "MISSING_RAW_SLIDE",
                "slide_number": num,
                "message": err_msg,
                "remediation_action": f"Check extraction script for slide {num}."
            })
        if num not in trans_db:
            err_msg = f"MISSING TRANSLATED SLIDE: Slide index {num} is missing from translated_slides.json (Page Index Invariance violated)!"
            errors.append(err_msg)
            diagnostics["errors"].append({
                "error_type": "INDEX_GAP",
                "slide_number": num,
                "message": err_msg,
                "remediation_action": f"Auto-remediation available: Insert Student Review slide at index {num} or rerun verify_slide_alignment.py with --auto-fix."
            })
            
    # Check 3: Anchor Word Alignment and Shift Detection
    img_dir_audit = args.img_dir or ("./slide_images" if os.path.isdir("./slide_images") else None)
    for num in range(1, min(total_raw, total_trans) + 1):
        raw_item = raw_db[num]
        trans_item = trans_db[num]
        slide_issues = check_slide_pair(raw_item, trans_item, trans_db, allow_review=getattr(args, "allow_review", False), img_dir=img_dir_audit)
        for issue in slide_issues:
            if issue.get("severity") == "error":
                errors.append(issue["message"])
                diagnostics["errors"].append(issue)
            else:
                warnings.append(issue["message"])
                diagnostics["warnings"].append(issue)

    # Check 4: Mandatory ref_note verification and Grounding/Hallucination Check
    ref_corpus_chunks = load_ref_corpus(args.ref_corpus) if args.ref_corpus else []
    if args.ref_corpus:
        print(f"• Reference Corpus Loaded: {len(ref_corpus_chunks)} text chunks for ref_note grounding check.")

    for num in range(1, min(total_raw, total_trans) + 1):
        trans_item = trans_db[num]
        raw_item = raw_db.get(num, {})
        if is_ceremonial_slide(trans_item) or is_ceremonial_slide(raw_item):
            # Exempt ceremonial / non-academic slides from ref_note checks
            continue
            
        ref_note = trans_item.get("ref_note", "").strip()
        is_skipped = bool(trans_item.get("is_skipped") or trans_item.get("unvoiced") or trans_item.get("skipped_by_professor"))
        if is_skipped:
            ref_words = len(ref_note.split())
            if not ref_note:
                err_msg = f"MISSING REF NOTE: Slide {num} is marked as skipped/unvoiced by professor, but lacks mandatory 'ref_note' supplementary commentary!"
                errors.append(err_msg)
                diagnostics["errors"].append({
                    "error_type": "MISSING_REF_NOTE",
                    "slide_number": num,
                    "message": err_msg,
                    "remediation_action": f"Provide substantive 15-30 word clinical explanation in 'ref_note' for unvoiced Slide {num}."
                })
            elif ref_words < 12:
                err_msg = f"SUPERFICIAL REF NOTE: Slide {num} 'ref_note' contains only {ref_words} words (minimum 12 words required for clinical comprehension)."
                errors.append(err_msg)
                diagnostics["errors"].append({
                    "error_type": "SUPERFICIAL_REF_NOTE",
                    "slide_number": num,
                    "word_count": ref_words,
                    "message": err_msg,
                    "remediation_action": f"Expand 'ref_note' for Slide {num} with high-yield clinical context from curriculum textbook."
                })

        if ref_note:
            ref_tokens = extract_tokens([ref_note])
            substantive_ref_tokens = {t for t in ref_tokens if len(t) >= 3 or (len(t) >= 2 and any(c.isupper() for c in t))}
            
            if ref_corpus_chunks:
                # Mode A: Grounding check against provided reference corpus
                max_overlap = 0.0
                for chunk in ref_corpus_chunks:
                    c_overlap = len(substantive_ref_tokens.intersection(chunk["tokens"])) / max(len(substantive_ref_tokens), 1)
                    if c_overlap > max_overlap:
                        max_overlap = c_overlap
                if max_overlap < 0.25:
                    warn_msg = f"REF NOTE GROUNDING ADVISORY at Slide {num}: 'ref_note' has low overlap ({max_overlap*100:.1f}%) with provided reference corpus. Verify source citation."
                    warnings.append(warn_msg)
                    diagnostics["warnings"].append({
                        "warning_type": "REF_NOTE_UNGROUNDED",
                        "slide_number": num,
                        "overlap": max_overlap,
                        "message": warn_msg
                    })
            else:
                # Mode B: Semantic topic coherence & medical terminology density check
                if len(substantive_ref_tokens) < 2:
                    warn_msg = f"REF NOTE DENSITY WARNING at Slide {num}: 'ref_note' contains fewer than 2 substantive clinical/scientific terms ({list(substantive_ref_tokens)}). Avoid generic filler prose."
                    warnings.append(warn_msg)
                    diagnostics["warnings"].append({
                        "warning_type": "REF_NOTE_LOW_DENSITY",
                        "slide_number": num,
                        "substantive_tokens": list(substantive_ref_tokens),
                        "message": warn_msg
                    })
                slide_topic_text = (trans_item.get("title_en", "") + " " + trans_item.get("title_fa", "") + " " +
                                    raw_item.get("title", "") + " " + " ".join(raw_item.get("text_lines", [])))
                slide_topic_tokens = extract_tokens([slide_topic_text])
                coherence_overlap = substantive_ref_tokens.intersection(slide_topic_tokens)
                if not coherence_overlap and len(slide_topic_tokens) >= 3:
                    warn_msg = f"REF NOTE TOPIC COHERENCE ADVISORY at Slide {num}: 'ref_note' does not share direct terminology with Slide {num}'s title or bullets. Ensure it directly clarifies this slide's mechanism."
                    warnings.append(warn_msg)
                    diagnostics["warnings"].append({
                        "warning_type": "REF_NOTE_LOW_COHERENCE",
                        "slide_number": num,
                        "message": warn_msg
                    })

    print("-" * 65)
    if warnings:
        print(f"⚠️  {len(warnings)} Advisory Warnings:")
        for w in warnings[:5]:
            print(f"   - {w}")
        if len(warnings) > 5:
            print(f"   ... and {len(warnings) - 5} more warnings.")
            
    if errors:
        diagnostics["gate_status"] = "FAILED"
        print(f"\n❌ GATE FAILED: {len(errors)} Critical Alignment Errors detected!")
        for e in errors:
            print(f"   [FAIL] {e}")
            
        print("\n💡 ACTIONABLE REMEDIATION HINTS:")
        for diag in diagnostics["errors"]:
            print(f"   • [{diag['error_type']}] Slide {diag.get('slide_number', 'N/A')}: {diag['remediation_action']}")
            diagnostics["remediation_hints"].append(diag['remediation_action'])
            
        # Write JSON diagnostic
        try:
            with open(args.diagnostic_json, "w", encoding="utf-8") as f:
                json.dump(diagnostics, f, ensure_ascii=False, indent=2)
            print(f"\n📁 Structured diagnostic written to: '{args.diagnostic_json}'")
        except Exception as ex:
            print(f"Could not write diagnostic JSON: {ex}", file=sys.stderr)
            
        print("\nDocument generation ABORTED. Fix translated_slides.json using the hints above before proceeding.")
        sys.exit(1)
        
    diagnostics["gate_status"] = "PASSED"
    try:
        with open(args.diagnostic_json, "w", encoding="utf-8") as f:
            json.dump(diagnostics, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
        
    print("\n✅ GATE PASSED: 100% Page Index Invariance and Content Alignment Verified!")
    print(f"All {total_slides} slides are strictly consecutive with zero offset drift.")
    print("=" * 65)
    sys.exit(0)

if __name__ == "__main__":
    main()
