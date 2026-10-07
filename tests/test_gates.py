import os
import sys
import pytest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from text_utils import is_ceremonial_slide
from verify_slide_alignment import validate_slide_schema, check_slide_pair
from verify_lecture_alignment import (
    evaluate_word_ratio_gate,
    evaluate_concept_recall_gate,
    evaluate_chunk_coverage_gate,
    check_academic_prose_quality,
    evaluate_slide_level_grounding
)


def test_validate_slide_schema_valid():
    valid_slide = {
        "slide_number": 1,
        "title_fa": "مقدمات غدد",
        "title_en": "Introduction to Endocrinology",
        "bullets": [{"lead": "تعریف", "text": "سیستم هورمونی بدن"}],
        "spoken_lecture": "استاد در این بخش توضیح دادند که سیستم اندوکرین...",
        "ref_note": "بر اساس هاریسون فصل ۳۷۰ تنظیم هورمونی با فیدبک منفی است.",
        "is_ceremonial": False,
        "is_image_heavy": False
    }
    errs = validate_slide_schema(valid_slide, 1)
    assert len(errs) == 0

def test_validate_slide_schema_invalid_types():
    invalid_slide = {
        "slide_number": "not_an_int",
        "title_fa": 12345,  # Should be string
        "bullets": "should be a list",
        "spoken_lecture": 9999,  # Should be string or list
        "is_ceremonial": "yes"  # Should be bool
    }
    errs = validate_slide_schema(invalid_slide, 1)
    assert len(errs) >= 4
    assert any("slide_number" in e for e in errs)
    assert any("title_fa" in e for e in errs)
    assert any("bullets" in e for e in errs)
    assert any("spoken_lecture" in e for e in errs)

def test_evaluate_word_ratio_gate():
    transcript_words = 1000
    lecture_words_passing = 650
    lecture_words_failing = 300
    
    passed_pass, ratio_pass, diag_pass = evaluate_word_ratio_gate(lecture_words_passing, transcript_words, threshold=0.50)
    assert passed_pass is True
    assert ratio_pass == 0.65
    assert diag_pass is None
    
    passed_fail, ratio_fail, diag_fail = evaluate_word_ratio_gate(lecture_words_failing, transcript_words, threshold=0.50)
    assert passed_fail is False
    assert ratio_fail == 0.30
    assert diag_fail is not None
    assert diag_fail["error_type"] == "INSUFFICIENT_LECTURE_COVERAGE"

def test_evaluate_concept_recall_gate():
    chunk_tokens = {"پرولاکتین", "دوپامین", "گیرنده", "d2", "هیپوفیز"}
    
    # Complete coverage (> 60%)
    lecture_tokens_pass = {"پرولاکتین", "دوپامین", "گیرنده", "d2", "آدنوم"}
    passed_pass, recall_pass, missing_pass = evaluate_concept_recall_gate(chunk_tokens, lecture_tokens_pass, threshold=0.60)
    assert passed_pass is True
    assert recall_pass == 4 / 5  # 80%
    assert len(missing_pass) == 0
    
    # Critical omission (< 60%)
    lecture_tokens_fail = {"کلسیم", "تیروئید"}
    passed_fail, recall_fail, missing_fail = evaluate_concept_recall_gate(chunk_tokens, lecture_tokens_fail, threshold=0.60)
    assert passed_fail is False
    assert recall_fail == 0.0
    assert len(missing_fail) == 5

def test_evaluate_chunk_coverage_gate():
    chunks = [
        {"file": "part01.txt", "start_sec": 0, "end_sec": 120, "tokens": {"پرولاکتین", "آدنوم"}},
        {"file": "part02.txt", "start_sec": 120, "end_sec": 240, "tokens": {"تیروئید", "لووتیروکسین"}},
        {"file": "part03.txt", "start_sec": 240, "end_sec": 255, "tokens": {"کوتاه"}},  # <= 30s, ignored
    ]
    # Coverage requires BOTH timestamp AND substantive concept recall >= 50%
    sec_times = [60, 180]  # covers part01 at 60s and part02 at 180s
    lecture_tokens = {"پرولاکتین", "آدنوم", "تیروئید", "لووتیروکسین"}
    
    passed, cov_ratio, uncovered, covered_cnt, eval_cnt = evaluate_chunk_coverage_gate(
        chunks, sec_times, lecture_tokens, min_chunk_duration=30, threshold=0.85
    )
    assert passed is True
    assert cov_ratio == 1.0
    assert len(uncovered) == 0
    assert eval_cnt == 2

def test_ceremonial_slide_detection_and_clinical_safeguards():
    bismillah_slide = {"title_fa": "بسم الله الرحمن الرحیم", "bullets": []}
    salawat_slide = {"title_fa": "اللهم صل علی محمد", "bullets": []}
    thanks_slide = {"title_fa": "با تشکر از توجه شما", "bullets": []}
    academic_slide = {"title_fa": "پاتولوژی آکرومگالی و ترشح GH", "bullets": []}
    
    assert is_ceremonial_slide(bismillah_slide) is True
    assert is_ceremonial_slide(salawat_slide) is True
    assert is_ceremonial_slide(thanks_slide) is True
    assert is_ceremonial_slide(academic_slide) is False

    # Clinical safeguard test: A long clinical slide containing "پایان" or "تقدیم" must NOT be marked ceremonial
    long_clinical_slide = {
        "title_fa": "بررسی سیر بالینی و پایان دوره درمان در بیماران کوشینگ",
        "bullets": [
            {"lead": "پروتکل", "text": "در پایان درمان جراحی، سطح کورتیزول پلاسما در ساعت ۸ صبح پایش می‌شود."},
            {"lead": "تقدیم دارو", "text": "تقدیم هیدروکورتیزون به عنوان درمان جایگزین تا زمان ریکاوری محور هیپوتالاموس-هیپوفیز الزامی است."}
        ]
    }
    assert is_ceremonial_slide(long_clinical_slide) is False

    # Q&A / Any Questions detection test
    qa_slide = {"title_en": "ANY QUESTIONS", "bullets": []}
    assert is_ceremonial_slide(qa_slide) is True

def test_phantom_content_hallucination_detection():
    # Check 3.1: Phantom Content Hallucination Check for Image-Only / Empty Raw Slides
    # If raw slide is image-only with no text, translated slide cannot have fabricated text bullets
    raw_image_only = {"slide_number": 46, "text_lines": [], "is_image_only": True}
    
    # 1. Valid: bullets is empty for image-only slide
    clean_trans = {"slide_number": 46, "bullets": [], "is_image_only": True}
    clean_issues = check_slide_pair(raw_image_only, clean_trans)
    assert not any(e.get("type") == "PHANTOM_CONTENT_HALLUCINATION" for e in clean_issues)
    
    # 2. Hallucinated: raw has zero text, but translated generated fabricated bullets
    hallucinated_trans = {
        "slide_number": 46,
        "bullets": [{"lead": "گام اول", "text": "بررسی بالینی"}],
        "is_ceremonial": False,
        "needs_student_review": False
    }
    hallucinated_issues = check_slide_pair(raw_image_only, hallucinated_trans)
    assert any(e.get("type") == "PHANTOM_CONTENT_HALLUCINATION" for e in hallucinated_issues)
    assert any(e.get("error_type") == "PHANTOM_CONTENT_HALLUCINATION" for e in hallucinated_issues)
    
    # 3. Exemption: Student Review badge explicitly permits manual student notes on image-only slides
    student_review_trans = {
        "slide_number": 46,
        "bullets": [{"lead": "نکته دانشجو", "text": "بررسی جدول توسط دانشجو"}],
        "needs_student_review": True,
        "is_ceremonial": False
    }
    student_issues = check_slide_pair(raw_image_only, student_review_trans)
    assert not any(e.get("type") == "PHANTOM_CONTENT_HALLUCINATION" for e in student_issues)

def test_table_data_schema_and_missing_gate():
    # Valid table_data list format [headers, rows]
    valid_slide = {
        "slide_number": 12,
        "title_fa": "خانواده گیرنده‌ها",
        "title_en": "Hormone Families",
        "bullets": [],
        "has_table": True,
        "table_data": [
            ["گیرنده‌ها", "افکتورها", "مسیرها"],
            [{"cols": ["GPCR", "Gs", "cAMP"]}]
        ]
    }
    errs = validate_slide_schema(valid_slide, 12)
    assert len(errs) == 0

    # Invalid table_data format (must be 2-element list or dict)
    invalid_slide = dict(valid_slide)
    invalid_slide["table_data"] = "not_a_valid_table_structure"
    errs_inv = validate_slide_schema(invalid_slide, 12)
    assert len(errs_inv) > 0

    # Missing table_data warning on table slide
    raw_tbl_slide = {"slide_number": 12, "has_tables": True, "text_lines": ["Table"]}
    trans_no_tbl = {"slide_number": 12, "title_en": "Table", "title_fa": "جدول", "bullets": [], "table_data": None}
    issues = check_slide_pair(raw_tbl_slide, trans_no_tbl)
    assert any(e.get("type") == "MISSING_TABLE_DATA" for e in issues)

def test_check_academic_prose_quality():
    # Colloquial text with broken verbs and fillers
    colloquial_sample = "ببینید این هورمون ترشح می‌شه و سلول‌ها دارن اینو اپروچ می‌کنن و نمی‌شن."
    detected = check_academic_prose_quality(colloquial_sample)
    assert len(detected) >= 3
    assert any("می‌شه" in d for d in detected)
    assert any("ببینید" in d for d in detected)
    assert any("دارن" in d for d in detected)

    # Formal academic medical text
    formal_sample = "این هورمون از سلول‌های اندوکرین ترشح می‌شود و سلول‌های هدف دارای گیرنده‌های اختصاصی به آن پاسخ می‌دهند."
    detected_formal = check_academic_prose_quality(formal_sample)
    assert len(detected_formal) == 0

def test_duplicate_slide_number_detection(tmp_path):
    import json
    import subprocess
    from verify_slide_alignment import main

    raw_data = [
        {"slide_number": 1, "text_lines": ["Slide 1"], "title_raw": "Slide 1"},
        {"slide_number": 1, "text_lines": ["Slide 1 Duplicate"], "title_raw": "Slide 1 Duplicate"},
        {"slide_number": 2, "text_lines": ["Slide 2"], "title_raw": "Slide 2"}
    ]
    trans_data = [
        {"slide_number": 1, "title_fa": "اسلاید ۱", "bullets": []},
        {"slide_number": 2, "title_fa": "اسلاید ۲", "bullets": []}
    ]
    raw_file = tmp_path / "raw_dup.json"
    trans_file = tmp_path / "trans_dup.json"
    diag_file = tmp_path / "diag.json"

    raw_file.write_text(json.dumps(raw_data, ensure_ascii=False), encoding="utf-8")
    trans_file.write_text(json.dumps(trans_data, ensure_ascii=False), encoding="utf-8")

    # Run verify script via subprocess or argument interception
    script_path = os.path.abspath(os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py"))
    res = subprocess.run([
        sys.executable, script_path,
        "--raw", str(raw_file),
        "--translated", str(trans_file),
        "--diagnostic-json", str(diag_file)
    ], capture_output=True, text=True, encoding="utf-8")

    assert res.returncode != 0
    with open(diag_file, "r", encoding="utf-8") as df:
        diag = json.load(df)
    assert any(e.get("error_type") == "DUPLICATE_SLIDE_NUMBER" for e in diag.get("errors", []))

def test_malformed_slide_number_schema_protection(tmp_path):
    import json
    import subprocess

    raw_data = [
        {"slide_number": "slide twelve", "text_lines": ["Slide 12"], "title_raw": "Slide 12"}
    ]
    trans_data = [
        {"slide_number": 1, "title_fa": "اسلاید ۱", "bullets": []}
    ]
    raw_file = tmp_path / "raw_bad.json"
    trans_file = tmp_path / "trans_bad.json"
    diag_file = tmp_path / "diag_bad.json"

    raw_file.write_text(json.dumps(raw_data, ensure_ascii=False), encoding="utf-8")
    trans_file.write_text(json.dumps(trans_data, ensure_ascii=False), encoding="utf-8")

    script_path = os.path.abspath(os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py"))
    res = subprocess.run([
        sys.executable, script_path,
        "--raw", str(raw_file),
        "--translated", str(trans_file),
        "--diagnostic-json", str(diag_file)
    ], capture_output=True, text=True, encoding="utf-8")

    # Script should gracefully exit with error code, NOT crash with unhandled ValueError traceback
    assert "ValueError" not in res.stderr
    with open(diag_file, "r", encoding="utf-8") as df:
        diag = json.load(df)
    assert any(e.get("error_type") == "SCHEMA_VALIDATION_ERROR" for e in diag.get("errors", []))

def test_ref_note_12_word_gate_boundary(tmp_path):
    import json
    import subprocess

    raw_data = [{"slide_number": 1, "text_lines": ["Intro"], "title_raw": "Intro"}]
    
    # 11 words: should fail with SUPERFICIAL_REF_NOTE
    short_words = "یک دو سه چهار پنج شش هفت هشت نه ده یازده"
    trans_short = [{
        "slide_number": 1,
        "title_fa": "مقدمه",
        "bullets": [],
        "is_skipped": True,
        "ref_note": short_words
    }]
    
    raw_file = tmp_path / "raw_ref.json"
    trans_file = tmp_path / "trans_ref.json"
    diag_file = tmp_path / "diag_ref.json"

    raw_file.write_text(json.dumps(raw_data, ensure_ascii=False), encoding="utf-8")
    trans_file.write_text(json.dumps(trans_short, ensure_ascii=False), encoding="utf-8")

    script_path = os.path.abspath(os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py"))
    res = subprocess.run([
        sys.executable, script_path,
        "--raw", str(raw_file),
        "--translated", str(trans_file),
        "--diagnostic-json", str(diag_file)
    ], capture_output=True, text=True, encoding="utf-8")

    assert res.returncode != 0
    with open(diag_file, "r", encoding="utf-8") as df:
        diag = json.load(df)
    assert any(e.get("error_type") == "SUPERFICIAL_REF_NOTE" for e in diag.get("errors", []))

def test_auto_fix_gaps_reads_title_raw(tmp_path):
    import json
    from verify_slide_alignment import auto_fix_gaps

    raw_db = {
        1: {"slide_number": 1, "title_raw": "Real Raw Slide Title", "text_lines": []}
    }
    trans_db = {}
    trans_file = tmp_path / "trans_fix.json"
    trans_file.write_text("[]", encoding="utf-8")

    fixed = auto_fix_gaps(raw_db, trans_db, str(trans_file), 1)
    assert fixed is True
    assert 1 in trans_db
    assert trans_db[1]["title_en"] == "Real Raw Slide Title"

def test_slide_level_grounding_dynamic_threshold():
    from verify_lecture_alignment import evaluate_slide_level_grounding
    
    chunks = [{
        "start_sec": 0,
        "end_sec": 25,
        "text": "هورمون تیرویید ترشح می شود و کلسیم خون تنظیم می شود و گیرنده اثر می کند",
        "tokens": {"هورمون", "تیرویید", "کلسیم", "گیرنده"}
    }]
    
    # Short duration (<30s): threshold is 40%
    # Slide covers 2 out of 4 tokens (50%) -> should pass!
    slides = [{
        "slide_number": 1,
        "audio_time_range": "00:00 - 00:20",
        "spoken_lecture": "در این اسلاید هورمون و تیرویید بررسی می شوند."
    }]
    
    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["passed_slides"] == 1
    assert stats["failed_slides"] == 0

def test_slide_level_grounding_monotonicity():
    from verify_lecture_alignment import evaluate_slide_level_grounding
    
    chunks = [
        {"start_sec": 0, "end_sec": 300, "text": "مبحث اول غدد", "tokens": {"مبحث", "اول", "غدد"}},
        {"start_sec": 300, "end_sec": 600, "text": "مبحث دوم غدد", "tokens": {"مبحث", "دوم", "غدد"}}
    ]
    
    # Slide 2 starts at 01:00 (60s) while Slide 1 ended at 03:00 (180s) without cross-ref -> warning
    slides_regression = [
        {"slide_number": 1, "audio_time_range": "00:00 - 03:00", "spoken_lecture": "مبحث اول غدد"},
        {"slide_number": 2, "audio_time_range": "01:00 - 02:00", "spoken_lecture": "مبحث دوم غدد"}
    ]
    issues, stats = evaluate_slide_level_grounding(slides_regression, chunks)
    assert any(i.get("type") == "TEMPORAL_MONOTONICITY_REGRESSION" for i in issues)
    
    # With explicit structural cross-reference, regression is permitted without warning
    slides_cross_ref = [
        {"slide_number": 1, "audio_time_range": "00:00 - 03:00", "spoken_lecture": "مبحث اول غدد"},
        {"slide_number": 2, "audio_time_range": "01:00 - 02:00", "spoken_lecture": "مبحث دوم غدد", "cross_references": [{"target_slide": 1, "reason": "مرور مبحث اسلاید قبل"}]}
    ]
    issues_cr, stats_cr = evaluate_slide_level_grounding(slides_cross_ref, chunks)
    assert not any(i.get("type") == "TEMPORAL_MONOTONICITY_REGRESSION" for i in issues_cr)

def test_multi_slide_multi_topic_segment_grounding():
    """
    Validates that fine-grained segment grounding discriminates between different topics
    within the same 9-minute audio chunk, catching temporally displaced/misaligned slides.
    """
    # 9-minute chunk with 3 distinct semantic sections
    chunk_text = (
        "### ۱. فیزیولوژی غده تیروئید\n"
        "هورمون تیروئید و تیروکسین و گواتر و هاشیموتو و پرکاری تیروئید بررسی شد.\n\n"
        "### ۲. فیزیولوژی غده آدرنال\n"
        "قشر آدرنال و کورتیزول و سندرم کوشینگ و آلدوسترون ترشح می شوند.\n\n"
        "### ۳. فیزیولوژی پانکراس و انسولین\n"
        "سلول های بتا و انسولین و دیابت و گلوکاگون قند خون را تنظیم می کنند.\n"
    )
    
    chunks = [{
        "start_sec": 0,
        "end_sec": 540,
        "text": chunk_text,
        "tokens": {"تیروئید", "تیروکسین", "گواتر", "هاشیموتو", "آدرنال", "کورتیزول", "کوشینگ", "آلدوسترون", "انسولین", "دیابت", "گلوکاگون"}
    }]
    
    # Correctly aligned slides:
    # Slide 1 (00:00 - 02:30) matches Thyroid
    # Slide 2 (03:00 - 05:30) matches Adrenal
    # Slide 3 (06:00 - 08:30) matches Pancreas
    correct_slides = [
        {"slide_number": 1, "audio_time_range": "00:00 - 02:30", "spoken_lecture": "در این اسلاید هورمون تیروئید و گواتر و هاشیموتو و تیروکسین تدریس شد."},
        {"slide_number": 2, "audio_time_range": "03:00 - 05:30", "spoken_lecture": "استاد در این بخش غده آدرنال و کورتیزول و سندرم کوشینگ و آلدوسترون را بررسی فرمودند."},
        {"slide_number": 3, "audio_time_range": "06:00 - 08:30", "spoken_lecture": "در نهایت انسولین و دیابت و گلوکاگون و سلول های بتا در پانکراس تدریس گردید."}
    ]
    
    issues_ok, stats_ok = evaluate_slide_level_grounding(correct_slides, chunks)
    assert stats_ok["failed_slides"] == 0
    assert stats_ok["passed_slides"] == 3
    assert stats_ok["avg_precision"] > 0.20
    
    # Misaligned slide: Slide 1 (at 00:00 - 02:30) talks about Pancreas/Insulin (spoken at 06:00+)
    misaligned_slides = [
        {"slide_number": 1, "audio_time_range": "00:00 - 02:30", "spoken_lecture": "در این اسلاید انسولین و دیابت و گلوکاگون در پانکراس تدریس گردید."},
        {"slide_number": 2, "audio_time_range": "03:00 - 05:30", "spoken_lecture": "استاد در این بخش غده آدرنال و کورتیزول و کوشینگ را بررسی فرمودند."},
        {"slide_number": 3, "audio_time_range": "06:00 - 08:30", "spoken_lecture": "در نهایت هورمون تیروئید و گواتر و هاشیموتو تدریس شد."}
    ]
    
    issues_bad, stats_bad = evaluate_slide_level_grounding(misaligned_slides, chunks)
    assert stats_bad["failed_slides"] >= 1
    assert any(i.get("slide_number") == 1 and i.get("type") == "SLIDE_AUDIO_MISALIGNMENT" for i in issues_bad)

def test_disjoint_audio_segments_evaluation():
    """
    Validates that non-contiguous audio_segments intervals (e.g. 01:00-01:40 and 05:00-06:00)
    are evaluated independently without merging the unrelated intermediate audio.
    """
    chunks = [{
        "start_sec": 0,
        "end_sec": 400,
        "text": (
            "### ۱. مبحث اول\nتیروئید و گواتر و هاشیموتو در اینجا مطرح شد.\n\n"
            "### ۲. مبحث میانی نامرتبط\nاستخوان و کلسیم و پاراتورمون در این فاصله تدریس شد.\n\n"
            "### ۳. بازگشت به مبحث اول\nدر ادامه دوباره تیروئید و پرکاری و تیروتوکسیکوز تدریس شد.\n"
        )
    }]
    
    # Slide with disjoint segments: [60s, 100s] and [300s, 360s]
    # It deliberately omits the middle 108s-248s segment (Bone/Calcium)
    slide_disjoint = [{
        "slide_number": 5,
        "audio_segments": [
            {"start": 60, "end": 100},
            {"start": 300, "end": 360}
        ],
        "spoken_lecture": "استاد در بخش اول و بخش پایانی به بیماری های تیروئید و گواتر و هاشیموتو و پرکاری و تیروتوکسیکوز پرداختند."
    }]
    
    issues, stats = evaluate_slide_level_grounding(slide_disjoint, chunks)
    assert stats["passed_slides"] == 1
    assert stats["failed_slides"] == 0


def test_unanchored_academic_slide_fails_grounding():
    """
    Validates that an academic slide lacking audio timing anchor (no audio_time_range and no audio_segments)
    fails with NO_AUDIO_ANCHOR error instead of being silently skipped.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding
    
    chunks = [{"start_sec": 0, "end_sec": 100, "text": "تست هورمون و ترشح"}]
    slides = [
        {"slide_number": 1, "audio_time_range": "00:00 - 01:00", "spoken_lecture": "تست هورمون و ترشح"},
        {"slide_number": 2, "spoken_lecture": "اسلاید بدون لنگر زمانی"}  # No timing!
    ]
    
    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["failed_slides"] >= 1
    assert any(i.get("type") == "NO_AUDIO_ANCHOR" and i.get("slide_number") == 2 for i in issues)

def test_structural_cross_reference_validation():
    """
    Validates dual structural cross-reference parsing:
    Rejects bare emojis and non-existent slide targets, accepts valid objects and textual references.
    """
    from text_utils import validate_cross_reference
    
    available = {1, 2, 3, 5, 12}
    
    # 1. Bare emoji or string rejection
    ok, err = validate_cross_reference("🔗", 12, available)
    assert ok is False
    assert "Cross-references must be structured dictionaries" in err
    
    # 2. Structural object with valid target
    ok, err = validate_cross_reference({"target_slide": 5, "reason": "review of thyroid axis"}, 12, available)
    assert ok is True
    assert err == ""
    
    # 3. Structural object with non-existent target
    ok, err = validate_cross_reference({"target_slide": 99, "reason": "invalid target"}, 12, available)
    assert ok is False
    assert "does not exist" in err
    
    # 4. Textual explicit reference is rejected (Option 1: strict structured dictionaries)
    ok, err = validate_cross_reference("اسلاید ۱۲", 15, available)
    assert ok is False
    assert "Cross-references must be structured dictionaries" in err

def test_four_segment_granularity_within_single_chunk():
    """
    Validates fine-grained segment discrimination across 4 sub-sections inside a single 9-minute chunk.
    Confirms that Slide 2 (mapped to Segment B at 02:00-04:00) ONLY matches Segment B concepts,
    and fails if populated with Segment D concepts.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding
    
    chunk_text = (
        "### ۱. فیزیولوژی غده تیروئید\n"
        "هورمون تیروئید و تیروکسین و گواتر و هاشیموتو در این بخش اول تدریس شد.\n\n"
        "### ۲. بیولوژی غده آدرنال\n"
        "غده آدرنال و ترشح کورتیزول و ایجاد سندرم کوشینگ و آلدوسترون در این بخش دوم تدریس شد.\n\n"
        "### ۳. هموستاز کلسیم و پاراتیروئید\n"
        "غدد پاراتیروئید و ترشح PTH و تنظیم کلسیم سرم و سلامت استخوان در این بخش سوم بررسی گردید.\n\n"
        "### ۴. متابولیسم قند و جزایر لانگرهانس\n"
        "سلول‌های بتای پانکراس و سنتز انسولین و گلوکاگون و بیماری دیابت در بخش چهارم پایان یافت.\n"
    )
    chunks = [{
        "file": "chunk_01.txt",
        "start_sec": 0,
        "end_sec": 540,
        "text": chunk_text
    }]
    
    # 1. Slide correctly mapped to Segment B (02:15 - 03:45)
    slide_b_correct = [{
        "slide_number": 2,
        "audio_time_range": "02:15 - 03:45",
        "spoken_lecture": "استاد به بررسی ترشح کورتیزول از قشر غده آدرنال و عوارض سندرم کوشینگ و آلدوسترون پرداختند."
    }]
    issues_ok, stats_ok = evaluate_slide_level_grounding(slide_b_correct, chunks)
    assert stats_ok["passed_slides"] == 1
    assert stats_ok["failed_slides"] == 0
    assert stats_ok["avg_recall_rate"] > 0.40
    
    # 2. Slide incorrectly populated with Segment D (Pancreas/Insulin/Diabetes) concepts at Segment B's timing
    slide_b_displaced = [{
        "slide_number": 2,
        "audio_time_range": "02:15 - 03:45",
        "spoken_lecture": "استاد به سنتز انسولین از سلول های بتای پانکراس و ترشح گلوکاگون در بیماری دیابت پرداختند."
    }]
    issues_fail, stats_fail = evaluate_slide_level_grounding(slide_b_displaced, chunks)
    assert stats_fail["failed_slides"] == 1
    assert any(i.get("type") == "SLIDE_AUDIO_MISALIGNMENT" and i.get("slide_number") == 2 for i in issues_fail)

def test_large_slide_with_insufficient_recall_fails_grounding():
    """Verifies that large slides with low recall fail grounding even if 3 tokens overlap (closing min_overlap loophole)."""
    chunks = [{
        "file": "part01.txt",
        "start_sec": 0,
        "end_sec": 300,
        "text": ("تولید کورتیزول آلدوسترون آندروژن تستوسترون استروژن کاتکول‌آمین‌ها دوپامین اپی‌نفرین نوراپی‌نفرین "
                 "فئوکروموسیتوم آدنوما کارسینوما هیپرپلازی هیپوکالمی هیپرتانسیون رنین آنژیوتانسین کلرید سدیم منیزیم کلسیم فسفات.")
    }]
    # Slide contains only 3 matched words, but audio window has ~25 substantive medical concepts
    slide = [{
        "slide_number": 1,
        "audio_time_range": "00:00 - 04:00",
        "spoken_lecture": "استاد به موضوع کورتیزول آلدوسترون آندروژن اشاره مختصری کردند بدون هیچ توضیح دیگری."
    }]
    issues, stats = evaluate_slide_level_grounding(slide, chunks)
    # Recall will be ~3/25 = 12%, which is well below the 55% threshold for a 240s slide
    assert stats["failed_slides"] == 1
    assert any(i.get("type") == "SLIDE_AUDIO_MISALIGNMENT" for i in issues)

def test_temporal_regression_severity_thresholds():
    """Verifies that regression > 60s without cross-ref triggers error, while 15-60s triggers warning."""
    chunks = [{
        "file": "part01.txt",
        "start_sec": 0,
        "end_sec": 600,
        "text": "مبحث اول غده آدرنال و سنتز هورمون ها و سپس تیروئید و سپس پانکراس."
    }]
    # Slide 1: 00:00 - 03:00 (180s)
    # Slide 2: 01:30 - 03:00 (regression of 90 seconds > 60s without cross_ref -> ERROR)
    slides_critical = [
        {"slide_number": 1, "audio_time_range": "00:00 - 03:00", "spoken_lecture": "غده آدرنال و سنتز هورمون ها"},
        {"slide_number": 2, "audio_time_range": "01:30 - 03:30", "spoken_lecture": "بازگشت به آدرنال و هورمون ها"}
    ]
    issues_crit, _ = evaluate_slide_level_grounding(slides_critical, chunks)
    crit_issues = [i for i in issues_crit if i.get("type") == "TEMPORAL_MONOTONICITY_REGRESSION"]
    assert len(crit_issues) == 1
    assert crit_issues[0]["severity"] == "error"

    # Slide 3: regression of 30 seconds (15-60s -> WARNING)
    slides_moderate = [
        {"slide_number": 1, "audio_time_range": "00:00 - 03:00", "spoken_lecture": "غده آدرنال و سنتز هورمون ها"},
        {"slide_number": 2, "audio_time_range": "02:30 - 04:00", "spoken_lecture": "غده آدرنال و سنتز هورمون ها"}
    ]
    issues_mod, _ = evaluate_slide_level_grounding(slides_moderate, chunks)
    mod_issues = [i for i in issues_mod if i.get("type") == "TEMPORAL_MONOTONICITY_REGRESSION"]
    assert len(mod_issues) == 1
    assert mod_issues[0]["severity"] == "warning"

def test_clinical_fact_extraction_and_omission_audit():
    """Verifies extraction of dosages, percentages, BP, ranges, and omission warning generation."""
    from text_utils import extract_clinical_facts, compare_clinical_facts

    audio_text = "دوز هیدروکورتیزون 25 mg و پردنیزولون 5 mg است و فشار خون 120/80 mmHg بود و 7% افراد مبتلا بودند."
    lecture_text = "استاد درباره هیدروکورتیزون و پردنیزولون صحبت کردند و فرمودند فشار خون 120/80 mmHg بود."

    aud_facts = extract_clinical_facts(audio_text)
    assert "25 mg" in aud_facts["dosages"]
    assert "5 mg" in aud_facts["dosages"]
    assert "120/80 mmhg" in aud_facts["lab_values"]
    assert "7%" in aud_facts["percentages"]

    lec_facts = extract_clinical_facts(lecture_text)
    comp = compare_clinical_facts(aud_facts, lec_facts)
    assert comp["total_audio_facts"] >= 4
    # 25 mg, 5 mg, and 7% are missing from lecture_text
    assert any("25 mg" in item for item in comp["omissions"])
    assert any("7%" in item for item in comp["omissions"])

def test_provenance_mode_and_confidence_reporting():
    """Verifies that diagnostic metadata accurately reports exact vs estimated confidence."""
    # Mode B (heuristic chunk text)
    chunks_mode_b = [{
        "file": "part01.txt",
        "start_sec": 0,
        "end_sec": 100,
        "text": "تست هورمون رشد و فاکتور رشد شبه انسولین."
    }]
    slides_b = [{"slide_number": 1, "audio_time_range": "00:00 - 01:00", "spoken_lecture": "تست هورمون رشد و فاکتور رشد شبه انسولین."}]
    _, stats_b = evaluate_slide_level_grounding(slides_b, chunks_mode_b)
    assert stats_b["grounding_mode"] == "heuristic"
    assert stats_b["temporal_confidence"] == "estimated"

    # Mode A (exact timestamped segments)
    chunks_mode_a = [{
        "file": "part01.txt",
        "start_sec": 0,
        "end_sec": 100,
        "segments": [
            {"start": 0.0, "end": 60.0, "text": "تست هورمون رشد و فاکتور رشد شبه انسولین."}
        ]
    }]
    _, stats_a = evaluate_slide_level_grounding(slides_b, chunks_mode_a)
    assert stats_a["grounding_mode"] == "timestamped"
    assert stats_a["temporal_confidence"] == "exact"

def test_packager_empty_source_raises_runtime_error(tmp_path):
    """Verifies that package_skill raises RuntimeError if packaging source is empty."""
    from package_skill import build_posix_zip
    empty_dir = tmp_path / "empty_skill"
    empty_dir.mkdir()
    out_zip = tmp_path / "empty.zip"

    with pytest.raises(RuntimeError, match="empty or invalid"):
        build_posix_zip(str(empty_dir), str(out_zip))

def test_timestamped_slide_without_matching_audio_segment_fails():
    """
    Problem 1 Fix: Verifies that a voiced slide claiming an audio timeframe
    where no transcript segments exist fails with SLIDE_AUDIO_NO_TEMPORAL_EVIDENCE (NOT a False PASS).
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [
        {"start_sec": 0, "end_sec": 300, "text": "مبحث اول غدد هیپوفیز", "tokens": {"مبحث", "اول", "غدد", "هیپوفیز"}}
    ]
    # Slide 5 claims audio at 10:00 - 11:00 (600s - 660s), well past available transcript (300s)
    slides = [
        {"slide_number": 5, "audio_time_range": "10:00 - 11:00", "spoken_lecture": "مبحث تومورهای هیپوفیز و پرولاکتینوما"}
    ]
    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["failed_slides"] == 1
    assert stats["passed_slides"] == 0
    assert any(i.get("type") == "SLIDE_AUDIO_NO_TEMPORAL_EVIDENCE" and i.get("slide_number") == 5 for i in issues)

def test_chunk_relative_timestamp_conversion():
    """
    Problem 2 Fix: Verifies that build_transcript_segments offsets local chunk-relative Whisper segment timestamps.
    """
    from verify_lecture_alignment import build_transcript_segments

    # Chunk starting at 540s with Whisper segments local to the chunk (0..30s)
    chunks = [{
        "file": "part02.txt",
        "start_sec": 540.0,
        "end_sec": 1080.0,
        "segments": [
            {"start": 10.0, "end": 25.0, "text": "هورمون رشد ترشح می شود"}
        ]
    }]
    segments = build_transcript_segments(chunks)
    assert len(segments) == 1
    # Global seconds should be 540 + 10 = 550 and 540 + 25 = 565
    assert segments[0]["start_sec"] == 550.0
    assert segments[0]["end_sec"] == 565.0
    assert segments[0]["grounding_mode"] == "timestamped"

def test_mixed_provenance_confidence():
    """
    Problem 3 Fix: Verifies that stats reports 'mixed' when both Mode A and Mode B segments are present.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [
        {"file": "part01.txt", "start_sec": 0, "end_sec": 300, "segments": [{"start": 0, "end": 100, "text": "تیروئید و تیروکسین"}]},
        {"file": "part02.txt", "start_sec": 300, "end_sec": 600, "text": "آدرنال و کورتیزول"}
    ]
    slides = [
        {"slide_number": 1, "audio_time_range": "00:00 - 01:00", "spoken_lecture": "تیروئید و تیروکسین"},
        {"slide_number": 2, "audio_time_range": "05:00 - 06:00", "spoken_lecture": "آدرنال و کورتیزول"}
    ]
    _, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["grounding_mode"] == "mixed"
    assert stats["temporal_confidence"] == "mixed"
    assert stats["timestamped_segments_count"] >= 1
    assert stats["heuristic_segments_count"] >= 1

def test_strict_audio_segments_schema_validation():
    """
    Problem 4 Fix: Verifies that validate_slide_schema strictly rejects malformed audio_segments.
    """
    from verify_slide_alignment import validate_slide_schema

    # Non-numeric start
    slide_bad_start = {"slide_number": 1, "title_fa": "تست", "bullets": [], "audio_segments": [{"start": "ten", "end": 20}]}
    errs = validate_slide_schema(slide_bad_start, 1)
    assert any("must be numeric" in e for e in errs)

    # Negative start
    slide_neg = {"slide_number": 1, "title_fa": "تست", "bullets": [], "audio_segments": [{"start": -5, "end": 20}]}
    errs = validate_slide_schema(slide_neg, 1)
    assert any("cannot be negative" in e for e in errs)

    # End < start
    slide_rev = {"slide_number": 1, "title_fa": "تست", "bullets": [], "audio_segments": [{"start": 30, "end": 10}]}
    errs = validate_slide_schema(slide_rev, 1)
    assert any("cannot be less than 'start'" in e for e in errs)

    # Overlapping segments
    slide_overlap = {"slide_number": 1, "title_fa": "تست", "bullets": [], "audio_segments": [{"start": 10, "end": 30}, {"start": 25, "end": 40}]}
    errs = validate_slide_schema(slide_overlap, 1)
    assert any("overlaps with previous" in e for e in errs)

    # Valid segments
    slide_valid = {"slide_number": 1, "title_fa": "تست", "bullets": [], "audio_segments": [{"start": 10, "end": 30}, {"start": 35, "end": 50}]}
    errs = validate_slide_schema(slide_valid, 1)
    assert errs == []

def test_invalid_clock_ranges_rejected():
    """
    Problem 5 Fix: Verifies that parse_time_to_seconds and extract_timestamps reject minutes/seconds >= 60.
    """
    from text_utils import parse_time_to_seconds, extract_timestamps

    assert parse_time_to_seconds("12:99") is None
    assert parse_time_to_seconds("99:99") is None
    assert parse_time_to_seconds("25:00:00") is None
    assert parse_time_to_seconds("09:20") == 560
    assert parse_time_to_seconds("01:10:05") == 4205

    # In extract_timestamps, 12:99 is skipped
    ts = extract_timestamps("09:20 الی 12:99 و سپس 15:30")
    assert 560 in ts
    assert 930 in ts
    assert len(ts) == 2

def test_critical_fact_omission_triggers_error():
    """
    Problem 6 Fix: Verifies that omitting dosages or vital lab values triggers hard ERROR,
    while percentages remain WARNING.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [{
        "start_sec": 0,
        "end_sec": 120,
        "text": "درمان با هیدروکورتیزون 25 mg شروع شد و فشار خون 120/80 mmHg بود و 7% عود داشت."
    }]
    # Spoken lecture omits 25 mg and 120/80 mmHg (critical) and 7% (advisory)
    slides = [{
        "slide_number": 1,
        "audio_time_range": "00:00 - 01:30",
        "spoken_lecture": "استاد درباره درمان با هیدروکورتیزون و وضعیت فشار خون و عود بیماری صحبت کردند."
    }]
    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["slides_with_fact_omissions"] == 1
    # Critical omission must have severity == "error"
    crit_issues = [i for i in issues if i.get("type") == "CLINICAL_FACT_CRITICAL_OMISSION"]
    assert len(crit_issues) >= 1
    assert crit_issues[0]["severity"] == "error"
    assert any("25 mg" in item for item in crit_issues[0]["critical_omissions"])

def test_version_consistency_verification(tmp_path):
    """
    Verifies that package_skill detects and prevents version mismatch between plugin.json, pyproject.toml, and version.py.
    """
    from package_skill import verify_version_consistency

    # Setup matching files
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "version.py").write_text('__version__ = "4.6.0"\n', encoding="utf-8")
    (tmp_path / "plugin.json").write_text('{"name": "test", "version": "4.6.0"}', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "4.6.0"\n', encoding="utf-8")

    # Should pass without error
    verify_version_consistency(str(tmp_path))

    # Mismatch in plugin.json should raise RuntimeError
    (tmp_path / "plugin.json").write_text('{"name": "test", "version": "4.5.0"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Version mismatch in plugin.json"):
        verify_version_consistency(str(tmp_path))

def test_boundary_fallback_tolerance_advisory():
    """
    Problem 10 Fix: Verifies that when a slide matches purely through ±15s boundary tolerance,
    a GROUNDING_BOUNDARY_TOLERANCE_ADVISORY warning is recorded.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    # Segment ends at 100s
    chunks = [{
        "start_sec": 0,
        "end_sec": 100,
        "text": "مبحث هورمون تیروئید و گواتر"
    }]
    # Slide begins at 105s (within 15s boundary of segment end 100s)
    slides = [{
        "slide_number": 1,
        "audio_time_range": "01:45 - 02:30",  # 105s - 150s
        "spoken_lecture": "مبحث هورمون تیروئید و گواتر در اینجا مطرح شد."
    }]
    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    boundary_warns = [i for i in issues if i.get("type") == "GROUNDING_BOUNDARY_TOLERANCE_ADVISORY"]
    assert len(boundary_warns) == 1
    assert boundary_warns[0]["severity"] == "review_required"
    assert stats.get("boundary_fallback_slides") == 1

def test_malformed_mode_a_transcript_segments_sanitized():
    """
    Problem 11 Fix: Verifies that build_transcript_segments sanitizes negative start times
    and inverted intervals (end <= start).
    """
    from verify_lecture_alignment import build_transcript_segments

    chunks = [{
        "start_sec": 0,
        "end_sec": 300,
        "segments": [
            {"start": -5.0, "end": 20.0, "text": "bad start"},
            {"start": 50.0, "end": 30.0, "text": "end less than start"},
            {"start": 10.0, "end": 25.0, "text": "valid segment"}
        ]
    }]
    segs = build_transcript_segments(chunks)
    assert len(segs) == 1
    assert segs[0]["start_sec"] == 10.0
    assert segs[0]["text"] == "valid segment"

def test_strict_drift_chunk_coverage_conditions():
    """
    Direct unit tests for evaluate_chunk_coverage_gate under strict grounding rules:
    - Low recall is NEVER covered (even with matching timestamp).
    - Displaced chunks are NOT covered by default (require allow_review=True).
    - Strict mode rejects displaced chunks even under review.
    """
    from verify_lecture_alignment import evaluate_chunk_coverage_gate

    chunks = [
        {"file": "chunk01.txt", "start_sec": 0, "end_sec": 120, "tokens": {"پرولاکتین", "آدنوم", "دوپامین", "بروموکریپتین"}}
    ]

    # Scenario A: Correct timestamp, but LOW recall (0% recall)
    sec_times_match = [30]  # matches chunk interval
    no_tokens = {"تیروئید", "لووتیروکسین"}
    
    # By default (strict=False, allow_review=False): FAILS because concept recall is 0%
    pass_non_strict, cov_non_strict, uncov_non_strict, _, _ = evaluate_chunk_coverage_gate(
        chunks, sec_times_match, no_tokens, strict=False
    )
    assert pass_non_strict is False
    assert cov_non_strict == 0.0
    assert "chunk01.txt" in uncov_non_strict

    # Under strict=True: FAILS
    pass_strict, cov_strict, uncov_strict, _, _ = evaluate_chunk_coverage_gate(
        chunks, sec_times_match, no_tokens, strict=True
    )
    assert pass_strict is False
    assert cov_strict == 0.0
    assert "chunk01.txt" in uncov_strict

    # Scenario B: Displaced timestamp (drift > 60s), but HIGH recall (100% recall)
    sec_times_drifted = [500]  # 500s is far beyond [0 - 120]
    high_tokens = {"پرولاکتین", "آدنوم", "دوپامین", "بروموکریپتین"}

    # By default (allow_review=False): Displaced chunk does NOT count as covered!
    pass_def, cov_def, uncov_def, _, _, disp_def = evaluate_chunk_coverage_gate(
        chunks, sec_times_drifted, high_tokens, strict=False, allow_review=False, return_displaced=True
    )
    assert pass_def is False
    assert cov_def == 0.0
    assert "chunk01.txt" in disp_def
    assert "chunk01.txt" in uncov_def

    # With allow_review=True: Provisionally covered under human review
    pass_rev, cov_rev, uncov_rev, _, _, disp_rev = evaluate_chunk_coverage_gate(
        chunks, sec_times_drifted, high_tokens, strict=False, allow_review=True, return_displaced=True
    )
    assert pass_rev is True
    assert cov_rev == 1.0
    assert "chunk01.txt" in disp_rev

    # Under strict=True: FAILS even if allow_review=True
    pass_strict_b, cov_strict_b, uncov_strict_b, _, _ = evaluate_chunk_coverage_gate(
        chunks, sec_times_drifted, high_tokens, strict=True, allow_review=True
    )
    assert pass_strict_b is False
    assert "chunk01.txt" in uncov_strict_b

def test_direct_vs_boundary_evidence_separation():
    """
    Verifies that evaluate_slide_level_grounding cleanly separates direct evidence
    from boundary fallback evidence in stats and scores.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [
        {"start_sec": 0, "end_sec": 60, "text": "مبحث هورمون پرولاکتین و دوپامین"},
        {"start_sec": 60, "end_sec": 120, "text": "مبحث تیروئید و گواتر"}
    ]
    slides = [
        # Slide 1: Direct overlap with chunk 1 ([10s - 40s] directly overlaps [0s - 60s])
        {
            "slide_number": 1,
            "audio_time_range": "00:10 - 00:40",
            "spoken_lecture": "هورمون پرولاکتین تحت مهار دوپامین است."
        },
        # Slide 2: Boundary fallback with chunk 2 (Slide starts at 130s, chunk ends at 120s, within 15s boundary)
        {
            "slide_number": 2,
            "audio_time_range": "02:10 - 02:40",  # 130s - 160s
            "spoken_lecture": "تیروئید و گواتر بررسی شد."
        }
    ]

    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["voiced_slides"] == 2
    assert stats["direct_grounded_slides"] == 1
    assert stats["boundary_fallback_slides"] == 1
    assert stats["avg_direct_precision"] > 0.0
    assert stats["avg_direct_recall_rate"] > 0.0
    assert stats["avg_boundary_precision"] > 0.0
    assert stats["avg_boundary_recall_rate"] > 0.0

def test_tuple_list_bullet_validation_and_defensive_unpack(tmp_path):
    """
    Issue 2: Verify bullet tuple/list schema validation (must have length 2)
    and defensive unpacking in document generation.
    """
    from verify_slide_alignment import validate_slide_schema
    from create_slide_pamphlet import build_pamphlet_from_json

    # 1. Schema rejects 1-element or 3-element bullet tuples/lists
    bad_slide_1 = {"slide_number": 1, "bullets": [["OnlyLead"]]}
    errs_1 = validate_slide_schema(bad_slide_1, 1)
    assert any("must have exactly 2 elements" in e for e in errs_1)

    bad_slide_3 = {"slide_number": 1, "bullets": [["Lead", "Text", "ExtraElement"]]}
    errs_3 = validate_slide_schema(bad_slide_3, 1)
    assert any("must have exactly 2 elements" in e for e in errs_3)

    good_slide = {"slide_number": 1, "title_fa": "تیتر اسلاید", "bullets": [["Lead:", "Valid substantive text"]]}
    assert len(validate_slide_schema(good_slide, 1)) == 0

    # 2. Defensive rendering in build_pamphlet_from_json does NOT crash even with odd-length bullets
    odd_slides = [
        {
            "slide_number": 1,
            "title_fa": "اسلاید آزمایشی بالت",
            "bullets": [
                ["یک المان"],
                ["سرتیتر", "متن اصلی", "المان سوم اضافی"],
                {"lead": "دیکشنری:", "text": "متن معتبر"}
            ]
        }
    ]
    json_path = tmp_path / "odd_bullets.json"
    import json
    json_path.write_text(json.dumps(odd_slides, ensure_ascii=False), encoding="utf-8")
    out_docx = str(tmp_path / "odd_bullets.docx")
    build_pamphlet_from_json(str(json_path), out_docx)
    assert os.path.exists(out_docx)

def test_parametric_hallucination_risk_severity_is_error():
    """
    Issue 3: Verify that PARAMETRIC_HALLUCINATION_RISK has severity 'error'
    when raw text exists but translated bullets have zero token overlap.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 1,
        "title_raw": "Pathophysiology of Cushing Disease",
        "text_lines": [
            "ACTH-secreting pituitary microadenoma",
            "Bilateral adrenal hyperplasia",
            "Loss of normal circadian cortisol rhythm"
        ]
    }
    # Completely ungrounded slide bullets (pure parametric hallucination)
    trans_slide = {
        "slide_number": 1,
        "title_fa": "پاتوفیزیولوژی بیماری کوشینگ",
        "bullets": [
            {"lead": "نکته فارماکولوژی:", "text": "اسپیرونولاکتون در نارسایی قلبی کاربرد دارد."},
            {"lead": "دیابت:", "text": "انسولین رگولار برای DKA استفاده می‌شود."}
        ]
    }

    issues = check_slide_pair(raw_slide, trans_slide, trans_db={1: trans_slide})
    hallucination_issues = [i for i in issues if i.get("type") == "PARAMETRIC_HALLUCINATION_RISK"]
    assert len(hallucination_issues) == 1
    assert hallucination_issues[0]["severity"] == "error"

def test_annotate_docx_zero_match_raises_error(tmp_path):
    """
    Issue 6: annotate_docx must raise RuntimeError if boxes > 0 but none match docx.
    """
    import json
    import docx
    from annotate_docx import annotate_docx

    doc = docx.Document()
    doc.add_paragraph("این یک پاراگراف معمولی است بدون مارکر اسلاید.")
    doc_path = str(tmp_path / "sample.docx")
    doc.save(doc_path)

    annot_json = tmp_path / "annot.json"
    annot_data = {
        "boxes": [
            {
                "before_marker": "Page_999",
                "title": "نکته رفرنس",
                "items": [["نکته:", "توضیح"]]
            }
        ]
    }
    annot_json.write_text(json.dumps(annot_data, ensure_ascii=False), encoding="utf-8")
    out_docx = str(tmp_path / "annotated.docx")

    with pytest.raises(RuntimeError, match="None of the 1 annotation boxes matched"):
        annotate_docx(doc_path, str(annot_json), out_docx)

def test_stage3_interval_overlap_rejects_boundary_touching_sections():
    """
    Verifies that Stage 3 uses interval overlap logic instead of point-proximity.
    A chunk [600, 1140] touching the start of next section [1140, 1200] has 0s overlap
    and must NOT be counted as covered. An interval [1080, 1140] (60s overlap) MUST cover it.
    """
    from verify_lecture_alignment import evaluate_chunk_coverage_gate

    chunks = [
        {
            "file": "chunk01.txt",
            "start_sec": 600.0,
            "end_sec": 1140.0,
            "tokens": {"پرولاکتین", "آدنوم", "دوپامین"}
        }
    ]
    doc_tokens = {"پرولاکتین", "آدنوم", "دوپامین"}

    # Touching boundary: next section [1140, 1200] -> overlap is 0.0s -> NOT covered
    touching_intervals = [(1140.0, 1200.0)]
    passed, cov, uncov, _, _ = evaluate_chunk_coverage_gate(
        chunks, touching_intervals, doc_tokens, strict=True
    )
    assert passed is False
    assert cov == 0.0
    assert "chunk01.txt" in uncov

    # Real overlap: section [1080, 1140] -> overlap is 60s (>= 15s) -> Covered
    overlapping_intervals = [(1080.0, 1140.0)]
    passed_ok, cov_ok, uncov_ok, _, _ = evaluate_chunk_coverage_gate(
        chunks, overlapping_intervals, doc_tokens, strict=True
    )
    assert passed_ok is True
    assert cov_ok == 1.0
    assert len(uncov_ok) == 0

def test_coarse_segment_resolution_advisory():
    """
    Verifies that when a slide covers <25% of a long audio segment (>60s),
    Stage 4 issues a SEGMENT_TEMPORAL_RESOLUTION_ADVISORY warning.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [
        {
            "start_sec": 0.0,
            "end_sec": 120.0,  # 120s long segment (> 60s)
            "text": "مبحث هورمون پرولاکتین و ترشح شیر از پستان و مهار با دوپامین در آدنوم هیپوفیز"
        }
    ]
    slides = [
        {
            "slide_number": 1,
            "audio_time_range": "00:00 - 00:10",  # 10s slide duration -> 10/120 = 8.3% (< 25%)
            "spoken_lecture": "مبحث هورمون پرولاکتین و ترشح شیر در این اسلاید مطرح شده است."
        }
    ]

    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    assert stats["low_temporal_resolution_slides"] == 1
    res_issues = [i for i in issues if i.get("type") == "SEGMENT_TEMPORAL_RESOLUTION_ADVISORY"]
    assert len(res_issues) == 1
    assert res_issues[0]["severity"] == "review_required"
    assert res_issues[0]["slide_number"] == 1


def test_cluster_slides_grounding_inherits_parent_lecture():
    """
    Verifies that multi-slide clusters (where child slides reference parent_lecture_slide)
    properly inherit audio timing and spoken lecture for concept grounding without
    triggering NO_AUDIO_ANCHOR, SLIDE_SPOKEN_LECTURE_EMPTY, or TEMPORAL_MONOTONICITY_REGRESSION.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [
        {
            "start_sec": 600.0,
            "end_sec": 900.0,
            "text": "بررسی جامع محور هیپوتالاموس و هیپوفیز و ترشح هورمون رشد و فاکتور رشد شبه انسولین"
        }
    ]
    slides = [
        {
            "slide_number": 10,
            "audio_time_range": "10:00 - 15:00",
            "spoken_lecture": "استاد در این بخش به بررسی جامع محور هیپوتالاموس و هیپوفیز و ترشح هورمون رشد پرداختند."
        },
        {
            "slide_number": 11,
            "parent_lecture_slide": 10,
        },
        {
            "slide_number": 12,
            "parent_lecture_slide": 10,
        }
    ]

    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    errors = [i for i in issues if i.get("severity") == "error"]
    assert len(errors) == 0, f"Expected 0 errors for clustered slides, got: {errors}"
    assert stats["passed_slides"] == 3
    assert stats["failed_slides"] == 0


def test_create_slide_pamphlet_deduplicates_cluster_and_identical_lectures(tmp_path):
    """
    Verifies that create_slide_pamphlet.py does not repeat the spoken lecture banner
    when consecutive slides share identical spoken_lecture or declare parent_lecture_slide.
    """
    import json
    import docx
    from create_slide_pamphlet import build_pamphlet_from_json

    identical_lecture = "توضیحات مفصل استاد درباره تنظیم ترشح هورمون رشد در کودکان و نوجوانان."
    slides = [
        {
            "slide_number": 1,
            "title_fa": "اسلاید اول مبحث",
            "spoken_lecture": identical_lecture,
            "bullets": [{"lead": "نکته:", "text": "هورمون رشد"}]
        },
        {
            "slide_number": 2,
            "title_fa": "اسلاید دوم مبحث",
            "spoken_lecture": identical_lecture,
            "bullets": [{"lead": "نکته دوم:", "text": "گیرنده GHR"}]
        },
        {
            "slide_number": 3,
            "title_fa": "اسلاید سوم مبحث",
            "parent_lecture_slide": 1,
            "bullets": [{"lead": "نکته سوم:", "text": "سوماتواستاتین"}]
        }
    ]

    json_path = tmp_path / "test_cluster_slides.json"
    json_path.write_text(json.dumps(slides, ensure_ascii=False), encoding="utf-8")
    out_docx = tmp_path / "test_cluster_out.docx"

    build_pamphlet_from_json(str(json_path), str(out_docx))

    doc = docx.Document(str(out_docx))
    matching_paras = [p for p in doc.paragraphs if "توضیحات مفصل استاد درباره تنظیم" in p.text]
    assert len(matching_paras) == 1, f"Expected spoken lecture to be rendered exactly ONCE, but found {len(matching_paras)} times!"
    assert len(doc.tables) >= 3


def test_image_text_bearing_slide_exempt_from_phantom_hallucination():
    """
    Verifies that an image-text-bearing slide (slide with empty digital text but confirmed
    OCR labels/captions) does NOT trigger PHANTOM_CONTENT_HALLUCINATION when translated bullets
    match the OCR evidence.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 77,
        "title_raw": "Slide 77",
        "text_lines": [],  # Empty digital text
        "ocr_text_lines": [
            "Hashimoto thyroiditis with extensive lymphocytic infiltration",
            "Hurthle cell metaplasia and germinal center formation"
        ],
        "has_images": True,
        "has_image_text": True,
        "is_image_text_bearing": True,
        "is_pure_visual": False
    }

    trans_slide = {
        "slide_number": 77,
        "title_fa": "تیروئیدیت هاشیموتو و ارتشاح لنفوسیتی",
        "title_en": "Hashimoto thyroiditis",
        "bullets": [
            {"lead": "پاتولوژی:", "text": "ارتشاح گسترده سلول های لنفوسیتی (lymphocytic infiltration) در فولیکول ها"},
            {"lead": "متاپلازی:", "text": "تشکیل مراکز زایا و تغییرات سلول های هورتل (Hurthle cell metaplasia)"}
        ]
    }

    issues = check_slide_pair(raw_slide, trans_slide)
    phantom_errs = [i for i in issues if i.get("type") == "PHANTOM_CONTENT_HALLUCINATION"]
    assert len(phantom_errs) == 0, f"Expected 0 phantom hallucination errors for image-text-bearing slide, got: {phantom_errs}"


def test_pure_visual_slide_without_ocr_fails_fabricated_bullets():
    """
    Verifies that a confirmed pure visual slide (zero digital text and zero OCR text)
    correctly triggers PHANTOM_CONTENT_HALLUCINATION if an agent fabricates bullets
    without marking needs_student_review.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 88,
        "title_raw": "Slide 88",
        "text_lines": [],
        "ocr_text_lines": [],
        "has_images": True,
        "has_image_text": False,
        "is_pure_visual": True,
        "is_image_only": True
    }

    trans_slide = {
        "slide_number": 88,
        "title_fa": "اسلاید تصویری بدون متن",
        "bullets": [
            {"lead": "نکته اختراعی:", "text": "این متن از خود مدل ساخته شده و در تصویر وجود ندارد"}
        ]
    }

    issues = check_slide_pair(raw_slide, trans_slide)
    phantom_errs = [i for i in issues if i.get("type") == "PHANTOM_CONTENT_HALLUCINATION"]
    assert len(phantom_errs) == 1, "Expected 1 PHANTOM_CONTENT_HALLUCINATION error for fabricated bullets on pure visual slide"
    assert phantom_errs[0]["severity"] == "error"


def test_image_table_triggers_missing_table_data_if_table_data_absent():
    """
    Verifies that when a slide is flagged with has_image_table: true,
    omitting table_data triggers a MISSING_TABLE_DATA advisory.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 78,
        "title_raw": "Robbins Table 20.5",
        "text_lines": [],
        "ocr_text_lines": ["Table 20.5 Diagnostic Criteria for Diabetes Mellitus", "FPG >= 126 mg/dL", "2-h PG >= 200 mg/dL"],
        "has_images": True,
        "has_tables": True,
        "has_image_table": True,
        "has_image_text": True
    }

    trans_slide = {
        "slide_number": 78,
        "title_fa": "جدول معیارهای تشخیصی دیابت رابینز",
        "title_en": "Table 20.5 Diagnostic Criteria",
        "bullets": [{"lead": "معیار:", "text": "قند خون ناشتا بالای 126"}]
        # table_data is missing!
    }

    issues = check_slide_pair(raw_slide, trans_slide)
    table_issues = [i for i in issues if i.get("type") == "MISSING_TABLE_DATA"]
    assert len(table_issues) == 1, "Expected MISSING_TABLE_DATA warning when has_image_table is present without table_data"


def test_slide_with_matching_title_but_omitted_body_fails_50_percent_recall():
    """
    Exact simulation of the Slide 79 blindspot bug:
    Raw slide has 15 substantive concepts across title and 4 bullets.
    Translated slide matches the title English words (len(common) == 5),
    but omitted the 4 bullets entirely (replaced with generic sentences).
    Under v4.7.0 this passed because common > 0.
    Under v4.8.0 this must FAIL with SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY because recall < 50%.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 79,
        "title_raw": "MANAGEMENT OF CHOLESTEROL TO PREVENT CARDIOVASCULAR DISEASE",
        "text_lines": [
            "Adults 20 years or older: Lifestyle management and statin therapy",
            "High-intensity statin: Atorvastatin 40 to 80 mg daily",
            "Secondary prevention in established atherosclerotic cardiovascular disease",
            "Target LDL-C reduction of at least 50%"
        ],
        "ocr_text_lines": []
    }

    # Translated slide with matching English title but generic bullets omitting the key terms
    bad_trans_slide = {
        "slide_number": 79,
        "title_fa": "مدیریت کلسترول جهت پیشگیری از بیماری های قلبی عروقی",
        "title_en": "MANAGEMENT OF CHOLESTEROL TO PREVENT CARDIOVASCULAR DISEASE",
        "bullets": [
            {"lead": "نکته کلی:", "text": "چربی خون بسیار مهم است و پزشک باید وضعیت بیمار را پیگیری نماید."},
            {"lead": "اهمیت بالینی:", "text": "اصلاح تغذیه و تحرک در سلامت انسان نقش اساسی ایفا می کند."}
        ]
    }

    issues = check_slide_pair(raw_slide, bad_trans_slide)
    recall_issues = [i for i in issues if i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY"]
    assert len(recall_issues) == 1, f"Expected SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY for Slide 79 blindspot, got: {issues}"
    issue = recall_issues[0]
    assert issue["severity"] == "error"
    assert issue["recall_ratio"] < 0.50
    assert issue["required_threshold"] == 0.50
    assert "atorvastatin" in [t.lower() for t in issue["missing_tokens"]] or "statin" in [t.lower() for t in issue["missing_tokens"]]
    assert issue["source_category"] == "missing_from_translation"


def test_slide_with_full_translation_passes_50_percent_recall():
    """
    Verifies that a slide with faithful translation of body bullets
    easily surpasses the 50% substantive recall threshold and passes without error.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 79,
        "title_raw": "MANAGEMENT OF CHOLESTEROL TO PREVENT CARDIOVASCULAR DISEASE",
        "text_lines": [
            "Adults 20 years or older: Lifestyle management and statin therapy",
            "High-intensity statin: Atorvastatin 40 to 80 mg daily",
            "Secondary prevention in established atherosclerotic cardiovascular disease",
            "Target LDL-C reduction of at least 50%"
        ],
        "ocr_text_lines": []
    }

    good_trans_slide = {
        "slide_number": 79,
        "title_fa": "مدیریت کلسترول جهت پیشگیری از بیماری های قلبی عروقی",
        "title_en": "MANAGEMENT OF CHOLESTEROL TO PREVENT CARDIOVASCULAR DISEASE",
        "bullets": [
            {"lead": "اصلاح سبک زندگی و استاتین (Lifestyle management & Statin):", "text": "در بالغین بالای 20 سال (Adults 20 years or older) استاتین‌تراپی تجویز می‌شود."},
            {"lead": "استاتین پرتوان (High-intensity statin):", "text": "آتورواستاتین (Atorvastatin 40-80 mg) روزانه خط اول است."},
            {"lead": "پیشگیری ثانویه (Secondary prevention):", "text": "در بیماری آترواسکلروتیک قلبی عروقی جهت کاهش حداقل 50% در LDL-C هدف‌گذاری می‌گردد."}
        ]
    }

    issues = check_slide_pair(raw_slide, good_trans_slide)
    recall_issues = [i for i in issues if i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY"]
    assert len(recall_issues) == 0, f"Expected 0 recall issues for faithful translation, got: {recall_issues}"


def test_missing_tokens_distinguishes_digital_vs_ocr_source():
    """
    Verifies that when missing tokens originate predominantly from OCR diagrams,
    the diagnostic category correctly flags 'missing_from_source_extraction'.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 62,
        "title_raw": "Dyslipidemia Secondary Causes",
        "text_lines": ["Secondary causes overview"],
        "ocr_text_lines": [
            "Hypothyroidism elevated LDL",
            "Nephrotic syndrome massive proteinuria",
            "Cholestatic liver disease",
            "Cushing syndrome cortisol excess"
        ]
    }

    # Only translated the digital line
    trans_slide = {
        "slide_number": 62,
        "title_fa": "علل ثانویه دیس لیپیدمی",
        "title_en": "Dyslipidemia Secondary Causes",
        "bullets": [
            {"lead": "کلیات:", "text": "بررسی علل ثانویه (Secondary causes overview)"}
        ]
    }

    issues = check_slide_pair(raw_slide, trans_slide)
    recall_issues = [i for i in issues if i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY"]
    assert len(recall_issues) == 1
    issue = recall_issues[0]
    assert issue["source_category"] == "missing_from_source_extraction"
    assert len(issue["missing_from_ocr"]) > len(issue["missing_from_digital"])


def test_substantive_recall_with_needs_student_review_and_allow_review():
    """
    Verifies the 3-state lifecycle for recall deficiency:
    - Default (allow_review=False): severity is 'error' (FAILED_HARD).
    - With allow_review=True on a slide with needs_student_review: true: severity is downgraded to 'warning'.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 95,
        "title_raw": "Complex Microscopic Pathology",
        "text_lines": [
            "Psammoma bodies concentric calcification",
            "Ground-glass nuclei Orphan Annie eyes",
            "Nuclear pseudoinclusions"
        ]
    }

    trans_slide = {
        "slide_number": 95,
        "title_fa": "پاتولوژی میکروسکوپی پیچیده",
        "title_en": "Complex Microscopic Pathology",
        "needs_student_review": True,
        "bullets": [
            {"lead": "نمای سلولی:", "text": "مشاهده هسته باز"}
        ]
    }

    # 1. Without allow_review -> Hard error
    issues_strict = check_slide_pair(raw_slide, trans_slide, allow_review=False)
    rec_strict = [i for i in issues_strict if i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY"]
    assert len(rec_strict) == 1
    assert rec_strict[0]["severity"] == "error"

    # 2. With allow_review -> Warning (REVIEW_REQUIRED)
    issues_review = check_slide_pair(raw_slide, trans_slide, allow_review=True)
    rec_review = [i for i in issues_review if i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY"]
    assert len(rec_review) == 1
    assert rec_review[0]["severity"] == "warning"


def test_temporal_topic_displacement_advisory_emitted_without_mutating_slides():
    """
    Verifies that when audio during Slide 1's timeframe discusses Slide 2's concepts
    (e.g., Insulin, beta cells, HbA1c, pancreas) far more than Slide 1's content (Thyroid),
    TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY is emitted while keeping slide texts 100% immutable.
    """
    from verify_lecture_alignment import evaluate_slide_level_grounding

    chunks = [{
        "start_sec": 0,
        "end_sec": 120,
        "text": "استاد در این بازه انسولین، سلول های بتا، هموگلوبین ای وان سی (HbA1c) و پانکراس را با جزئیات تدریس کردند."
    }]

    slides = [
        {
            "slide_number": 1,
            "audio_time_range": "00:00 - 02:00",
            "title_fa": "هورمون های تیروئید",
            "title_en": "Thyroid Hormones",
            "bullets": [
                {"lead": "تیروئید:", "text": "تیروکسین و تری‌یدوتیرونین و گواتر"}
            ],
            "spoken_lecture": "استاد در این بازه انسولین و سلول های بتا و HbA1c و پانکراس را توضیح دادند."
        },
        {
            "slide_number": 2,
            "audio_time_range": "02:00 - 04:00",
            "title_fa": "هورمون های پانکراس و انسولین",
            "title_en": "Pancreatic Hormones & Insulin",
            "bullets": [
                {"lead": "انسولین:", "text": "سلول های بتا در پانکراس انسولین ترشح کرده و HbA1c را پایش می کنند."}
            ],
            "spoken_lecture": "در ادامه مبحث انسولین پیگیری شد."
        }
    ]

    import copy
    slides_before = copy.deepcopy(slides)

    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    disp_issues = [i for i in issues if i.get("type") == "TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY"]
    assert len(disp_issues) >= 1, f"Expected TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY, got: {issues}"
    assert disp_issues[0]["slide_number"] == 1
    assert disp_issues[0]["displaced_to_slide"] == 2
    assert stats["temporal_topic_displacement_slides"] >= 1

    # Immutability verification: Slide contents must not be mutated!
    assert slides == slides_before, "Slide texts were mutated by displacement detection! Immutability violated!"


def test_substantive_tokens_filters_english_prose_stopwords():
    """
    Verifies that extract_substantive_tokens filters routine English prose verbs and fillers
    (cannot, provide, enough, replace, losses, under, circumstances, directed) while preserving
    genuine clinical entities, chemical notations, and dosages.
    Also verifies that a pure academic Persian translation passes the 50% recall gate without
    needing to paste English clauses into parentheses.
    """
    from text_utils import extract_substantive_tokens, extract_tokens
    from verify_slide_alignment import check_slide_pair

    raw_text = (
        "When the calcium level is >13 mg/dL, calcification in kidneys, skin, vessels "
        "cannot provide enough capacity to replace losses under any circumstances directed by homeostatic control."
    )

    all_tokens = extract_tokens([raw_text])
    substantive = extract_substantive_tokens([raw_text])

    # Prose verbs and fillers must be excluded from substantive tokens
    for prose_word in ["cannot", "provide", "enough", "capacity", "replace", "losses", "under", "circumstances", "directed", "when", "level"]:
        assert prose_word not in substantive, f"Prose word '{prose_word}' should have been filtered out of substantive tokens!"

    # Genuine medical concepts, dosages, and organs must be kept
    assert "calcium" in substantive
    assert "calcification" in substantive
    assert "kidneys" in substantive
    assert "vessels" in substantive
    assert "mg/dl" in substantive

    # Verify that clean academic Persian translation passes check_slide_pair with 0 recall errors
    raw_slide = {
        "slide_number": 42,
        "title_raw": "Hypercalcemia Complications",
        "text_lines": [raw_text]
    }
    trans_slide = {
        "slide_number": 42,
        "title_fa": "عوارض هیپرکلسمی شدید",
        "title_en": "Hypercalcemia Complications",
        "bullets": [
            {
                "lead": "رسوب بافتی کلسیم:",
                "text": "سطح کلسیم (Calcium) بالای ۱۳ میلی‌گرم بر دسی‌لیتر منجر به کلسیفیکاسیون در کلیه‌ها، پوست و عروق خونی می‌شود."
            }
        ]
    }

    issues = check_slide_pair(raw_slide, trans_slide)
    recall_errors = [i for i in issues if i.get("type") in ("SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY", "PARAMETRIC_HALLUCINATION_RISK")]
    assert len(recall_errors) == 0, f"Expected clean Persian translation to pass recall, but got: {recall_errors}"


def test_adversarial_parenthetical_clause_violation_triggers_hard_error():
    """
    Verifies that when an agent attempts to cheat the recall test by copy-pasting
    full English sentences or clauses inside parentheses, the Anti-Clause Parentheses Gate
    triggers a hard error (PARENTHETICAL_CLAUSE_VIOLATION).
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 43,
        "title_raw": "Severe Hypercalcemia",
        "text_lines": ["When calcium exceeds 13 mg/dL, calcification occurs in kidneys, skin, and vessels."]
    }

    # Bullet with full English clause pasted inside parentheses
    trans_cheating = {
        "slide_number": 43,
        "title_fa": "هیپرکلسمی شدید",
        "title_en": "Severe Hypercalcemia",
        "bullets": [
            {
                "lead": "رسوب کلسیم:",
                "text": "رسوب بافتی (When calcium exceeds 13 mg/dL, calcification occurs in kidneys, skin, and vessels) رخ می‌دهد."
            }
        ]
    }

    issues = check_slide_pair(raw_slide, trans_cheating)
    clause_violations = [i for i in issues if i.get("type") == "PARENTHETICAL_CLAUSE_VIOLATION"]
    assert len(clause_violations) >= 1, f"Expected PARENTHETICAL_CLAUSE_VIOLATION, got: {issues}"
    assert clause_violations[0]["severity"] == "error"
    assert clause_violations[0]["slide_number"] == 43

    # Bullet with a 3-word clause containing a clause marker verb ("which causes pain")
    trans_clause_marker = {
        "slide_number": 43,
        "title_fa": "هیپرکلسمی شدید",
        "title_en": "Severe Hypercalcemia",
        "bullets": [
            {
                "lead": "رسوب کلسیم:",
                "text": "رسوب در پوست (which causes pain) ایجاد می‌شود."
            }
        ]
    }
    issues_marker = check_slide_pair(raw_slide, trans_clause_marker)
    clause_marker_violations = [i for i in issues_marker if i.get("type") == "PARENTHETICAL_CLAUSE_VIOLATION"]
    assert len(clause_marker_violations) >= 1, f"Expected PARENTHETICAL_CLAUSE_VIOLATION for 'which causes pain', got: {issues_marker}"


def test_valid_concise_medical_parentheses_pass_cleanly():
    """
    Verifies that legitimate concise medical terms, drug names, and anatomical entities
    in parentheses (<= 4 words without sentence clauses) pass without triggering any violations.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide = {
        "slide_number": 44,
        "title_raw": "Parathyroid Pathology & Therapy",
        "text_lines": [
            "Duodenum absorption",
            "Corrected calcium formula",
            "Brown Tumors and Osteitis fibrosa cystica",
            "Multiple Endocrine Neoplasia Type 1",
            "Cinacalcet therapy and PTH reduction"
        ]
    }

    trans_valid = {
        "slide_number": 44,
        "title_fa": "پاتولوژی و درمان پاراتیروئید",
        "title_en": "Parathyroid Pathology & Therapy",
        "bullets": [
            {"lead": "جذب روده‌ای:", "text": "جذب فعال در دئودنوم (Duodenum) رخ می‌دهد."},
            {"lead": "محاسبه آزمایشگاهی:", "text": "محاسبه کلسیم اصلاح‌شده (Corrected calcium) الزامی است."},
            {"lead": "ضایعات استخوانی:", "text": "ایجاد تومور قهوه‌ای (Brown Tumors) و استئیت فیبروزا سیستیکا (Osteitis fibrosa cystica)."},
            {"lead": "سندرم ژنتیکی:", "text": "ارتباط با نئوپلازی چندگانه غدد درون‌ریز (Multiple Endocrine Neoplasia Type 1)."},
            {"lead": "درمان دارویی:", "text": "تجویز داروی سیناکلست (Cinacalcet) جهت مهار پاراتورمون (PTH)."}
        ]
    }

    issues = check_slide_pair(raw_slide, trans_valid)
    clause_violations = [i for i in issues if i.get("type") == "PARENTHETICAL_CLAUSE_VIOLATION"]
    assert len(clause_violations) == 0, f"Expected 0 PARENTHETICAL_CLAUSE_VIOLATION for valid medical terms, got: {clause_violations}"


def test_slide_45_table_omission_triggers_incomplete_table_transcription():
    """
    Simulation of Slide 45 Bug (Harrison Table: Classification of Causes of Hypercalcemia).
    Verifies that when a slide contains diagnostic table rows (e.g. Aluminum intoxication,
    Lithium therapy, Sarcoidosis, Multiple myeloma) and key clinical rows are omitted,
    the verifier raises an INCOMPLETE_TABLE_TRANSCRIPTION error.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide_45 = {
        "slide_number": 45,
        "title_raw": "Classification of Causes of Hypercalcemia",
        "text_lines": ["Classification of Causes of Hypercalcemia"],
        "ocr_text_lines": [
            "I. Parathyroid-related: Primary hyperparathyroidism, Lithium therapy, Familial hypocalciuric hypercalcemia",
            "II. Malignancy-related: Solid tumor metastases breast, lung, kidney; Hematologic multiple myeloma, lymphoma, leukemia",
            "III. Vitamin D-related: Vitamin D intoxication, 1,25(OH)2D sarcoidosis",
            "IV. Associated with Renal Failure: Severe secondary hyperparathyroidism, Aluminum intoxication, Milk-alkali syndrome"
        ],
        "has_images": True,
        "has_tables": True,
        "has_image_table": True,
        "has_image_text": True
    }

    # Deficient translation that omitted the renal failure rows including Aluminum intoxication
    trans_deficient_45 = {
        "slide_number": 45,
        "title_fa": "طبقه‌بندی علل هایپرکلسمی",
        "title_en": "Classification of Causes of Hypercalcemia",
        "bullets": [],
        "table_data": {
            "headers": ["دسته علل", "اتیولوژی‌های اختصاصی"],
            "rows": [
                {"cols": ["وابسته به پاراتیروئید", "هایپرپاراتیروئیدیسم اولیه و درمان با لیتیوم"]},
                {"cols": ["وابسته به بدخیمی", "تومورهای توپر پستان، ریه، کلیه"]}
                # Renal failure / Aluminum intoxication omitted!
            ]
        }
    }

    issues = check_slide_pair(raw_slide_45, trans_deficient_45)
    incomplete_errs = [i for i in issues if i.get("type") == "INCOMPLETE_TABLE_TRANSCRIPTION"]
    assert len(incomplete_errs) >= 1, f"Expected INCOMPLETE_TABLE_TRANSCRIPTION error for omitted table rows, got: {issues}"
    assert incomplete_errs[0]["severity"] == "error"
    assert "Aluminum" in str(incomplete_errs[0].get("message")) or "aluminum" in str(incomplete_errs[0].get("message")).lower() or incomplete_errs[0]["type"] == "INCOMPLETE_TABLE_TRANSCRIPTION"


def test_slide_45_complete_table_transcription_passes():
    """
    Verifies that when all subcategories from Harrison Table 45 (including Aluminum intoxication,
    Lithium therapy, Sarcoidosis, Multiple myeloma) are fully translated in table_data,
    the slide passes with 0 errors.
    """
    from verify_slide_alignment import check_slide_pair

    raw_slide_45 = {
        "slide_number": 45,
        "title_raw": "Classification of Causes of Hypercalcemia",
        "text_lines": ["Classification of Causes of Hypercalcemia"],
        "ocr_text_lines": [
            "I. Parathyroid-related: Primary hyperparathyroidism, Lithium therapy, Familial hypocalciuric hypercalcemia",
            "II. Malignancy-related: Solid tumor metastases breast, lung, kidney; Hematologic multiple myeloma, lymphoma, leukemia",
            "III. Vitamin D-related: Vitamin D intoxication, 1,25(OH)2D sarcoidosis",
            "IV. Associated with Renal Failure: Severe secondary hyperparathyroidism, Aluminum intoxication, Milk-alkali syndrome"
        ],
        "has_images": True,
        "has_tables": True,
        "has_image_table": True,
        "has_image_text": True
    }

    trans_complete_45 = {
        "slide_number": 45,
        "title_fa": "طبقه‌بندی علل هایپرکلسمی",
        "title_en": "Classification of Causes of Hypercalcemia",
        "bullets": [],
        "table_data": {
            "headers": ["دسته‌بندی اصلی", "علل و بیماری‌های اختصاصی"],
            "rows": [
                {"merged": True, "text": "I. علل وابسته به پاراتیروئید (Parathyroid-related)"},
                {"cols": ["هایپرپاراتیروئیدیسم اولیه", "آدنوم منفرد، هایپرپلازی و کارسینوما"]},
                {"cols": ["درمان با لیتیوم", "کاهش حساسیت گیرنده‌های کلسیم"]},
                {"cols": ["هایپرکلسمی هایپوکلسیمیک فامیلیال", "جهش در گیرنده سنجش کلسیم (FHH)"]},
                {"merged": True, "text": "II. علل وابسته به بدخیمی (Malignancy-related)"},
                {"cols": ["متاستاز تومورهای توپر به استخوان", "سرطان پستان (Breast cancer) و ریه"]},
                {"cols": ["ترشح هورمونی پپتید وابسته به PTH", "تومورهای بدخیم ریه و کلیه (Kidney)"]},
                {"cols": ["بدخیمی‌های خونی", "مولتیپل میلوما (Multiple myeloma)، لنفوم و لوسمی"]},
                {"merged": True, "text": "III. علل مرتبط با ویتامین دی (Vitamin D-related)"},
                {"cols": ["مسمومیت با ویتامین D", "مصرف بیش از حد و هایپرویتامینوز"]},
                {"cols": ["افزایش سنتز متابولیت فعال", "بیماری سارکوئیدوز (Sarcoidosis) و گرانولوماتوز"]},
                {"merged": True, "text": "IV. همراه با نارسایی کلیوی (Associated with Renal Failure)"},
                {"cols": ["هایپرپاراتیروئیدیسم ثانویه شدید", "نارسایی مزمن کلیوی"]},
                {"cols": ["مسمومیت با آلومینیوم", "تجویز آلومینیوم در بیماران دیالیزی (Aluminum intoxication)"]},
                {"cols": ["سندرم شیر-قلیا", "مصرف همزمان مقادیر زیاد کلسیم و آنتی‌اسیدهای قابل جذب"]}
            ]
        }
    }

    issues = check_slide_pair(raw_slide_45, trans_complete_45)
    errors = [i for i in issues if i.get("severity") == "error"]
    assert len(errors) == 0, f"Expected 0 errors for complete slide 45 table, got: {errors}"


def test_visual_asset_audit_triggers_when_chart_image_missing():
    """Verifies VISUAL_ASSET_AUDIT emits a warning when a slide has has_charts: True but no image asset exists."""
    raw_item = {
        "slide_number": 39,
        "title_raw": "Microvascular and Macrovascular Risk Curve",
        "text_lines": ["HbA1c risk correlation curve"],
        "has_charts": True,
        "has_images": True
    }
    trans_item = {
        "slide_number": 39,
        "title_fa": "نمودار مقایسه شیب بروز عوارض",
        "title_en": "Microvascular and Macrovascular Risk Curve",
        "bullets": [
            {"lead": "نمودار بالینی", "text": "همبستگی مستقیم میزان قند و عوارض میکروواسکولار"}
        ]
    }
    issues = check_slide_pair(raw_item, trans_item, img_dir=None)
    assert any(i.get("type") == "VISUAL_ASSET_AUDIT" and i.get("severity") == "warning" for i in issues)


def test_visual_asset_audit_passes_when_image_resolved(tmp_path):
    """Verifies VISUAL_ASSET_AUDIT passes when img_path points to an existing file."""
    fake_img = str(tmp_path / "slide_39_img.png")
    with open(fake_img, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\nfake")

    raw_item = {
        "slide_number": 39,
        "title_raw": "Microvascular and Macrovascular Risk Curve",
        "text_lines": ["HbA1c risk correlation curve"],
        "has_charts": True,
        "img_path": fake_img
    }
    trans_item = {
        "slide_number": 39,
        "title_fa": "نمودار مقایسه شیب بروز عوارض",
        "title_en": "Microvascular and Macrovascular Risk Curve",
        "img_path": fake_img,
        "bullets": [
            {"lead": "نمودار بالینی", "text": "همبستگی مستقیم میزان قند و عوارض میکروواسکولار"}
        ]
    }
    issues = check_slide_pair(raw_item, trans_item)
    assert not any(i.get("type") == "VISUAL_ASSET_AUDIT" for i in issues)










