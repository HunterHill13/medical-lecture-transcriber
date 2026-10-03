import os
import sys
import tempfile
import pytest
import pymupdf
from pptx import Presentation
from pptx.util import Inches

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from extract_presentation import (
    extract_pptx,
    extract_pdf,
    run_ocr_on_image
)
from verify_slide_alignment import check_slide_pair
from verify_lecture_alignment import evaluate_slide_level_grounding


def test_extract_pptx_pure_text_skips_ocr(monkeypatch):
    """Verifies that a PPTX slide with pure digital text and no visuals skips OCR execution."""
    ocr_called = False
    def fake_ocr(img_path):
        nonlocal ocr_called
        ocr_called = True
        return [], 0.0, False, False

    monkeypatch.setattr("extract_presentation.run_ocr_on_image", fake_ocr)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pptx_path = os.path.join(tmp_dir, "test_pure_text.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
        txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(5), Inches(2))
        tf = txBox.text_frame
        tf.text = "Pathophysiology of Chronic Heart Failure and Clinical Symptoms Overview"
        prs.save(pptx_path)

        slides = extract_pptx(pptx_path, img_dir=tmp_dir)
        assert len(slides) == 1
        meta = slides[0]
        assert meta["has_images"] is False
        assert meta["has_charts"] is False
        assert meta["has_smartart"] is False
        assert meta["ocr_text_lines"] == []
        assert meta["has_image_text"] is False
        assert ocr_called is False  # OCR was successfully skipped for pure text slide


def test_extract_pptx_with_visual_triggers_ocr(monkeypatch):
    """Verifies that a PPTX slide containing visual shapes/tables triggers OCR even when text is >= 20 words."""
    ocr_called = False
    def fake_ocr(img_path):
        nonlocal ocr_called
        ocr_called = True
        return ["Glomerulus", "Podocyte"], 0.88, True, False

    monkeypatch.setattr("extract_presentation.run_ocr_on_image", fake_ocr)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pptx_path = os.path.join(tmp_dir, "test_visual.pptx")
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        # Add visual table
        slide.shapes.add_table(2, 2, Inches(1), Inches(1), Inches(4), Inches(2))
        # Add textbox with >= 20 words so total_words >= 20 (guaranteeing OCR is triggered by has_visuals, not total_words < 5)
        txBox = slide.shapes.add_textbox(Inches(1), Inches(3.5), Inches(5), Inches(2))
        txBox.text_frame.text = (
            "Clinical presentation of renal nephrotic syndrome manifests with massive proteinuria, "
            "hypoalbuminemia, generalized edema, and hyperlipidemia requiring immediate therapeutic intervention."
        )
        prs.save(pptx_path)

        # Create mock candidate image
        cand_img = os.path.join(tmp_dir, "slide_01.png")
        with open(cand_img, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nfake")

        slides = extract_pptx(pptx_path, img_dir=tmp_dir)
        assert len(slides) == 1
        meta = slides[0]
        assert meta["has_tables"] is True
        assert meta["has_image_text"] is True
        assert "Glomerulus" in meta["ocr_text_lines"]
        assert ocr_called is True


def test_extract_pdf_pure_text_skips_ocr(monkeypatch):
    """Verifies that a PDF page with pure digital text and no images skips OCR."""
    ocr_called = False
    def fake_ocr(img_path):
        nonlocal ocr_called
        ocr_called = True
        return [], 0.0, False, False

    monkeypatch.setattr("extract_presentation.run_ocr_on_image", fake_ocr)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = os.path.join(tmp_dir, "test_pure_text.pdf")
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Clinical Manifestations of Diabetes Mellitus with detailed polyuria and polydipsia explanations.")
        doc.save(pdf_path)
        doc.close()

        slides = extract_pdf(pdf_path, img_dir=tmp_dir)
        assert len(slides) == 1
        meta = slides[0]
        assert meta["has_images"] is False
        assert meta["has_tables"] is False
        assert meta["ocr_text_lines"] == []
        assert meta["has_image_text"] is False
        assert ocr_called is False  # Skipped because no visuals and text >= 5 words


def test_extract_pdf_native_table_vs_scanned_table():
    """Verifies that native text tables have has_tables=True and has_image_table=False."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = os.path.join(tmp_dir, "test_native_table.pdf")
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Col1 | Col2\nValA | ValB\nValC | ValD")
        doc.save(pdf_path)
        doc.close()

        slides = extract_pdf(pdf_path, img_dir=tmp_dir)
        assert len(slides) == 1
        meta = slides[0]
        assert meta["has_tables"] is True
        assert meta["has_image_table"] is False  # Native table, not a scanned raster table


def test_ocr_confidence_threshold_and_uncertain_flag(monkeypatch):
    """Verifies that low-confidence or borderline OCR flags ocr_uncertain and needs_student_review."""
    class MockEngineUncertain:
        def __call__(self, img_path):
            # 1 token with borderline confidence 0.42
            return [[[[0,0],[10,0],[10,10],[0,10]], "artifact", 0.42]], None

    monkeypatch.setattr("extract_presentation.get_ocr_engine", lambda: MockEngineUncertain())
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(b"mock")
        tf_name = tf.name

    try:
        lines, conf, confident, uncertain = run_ocr_on_image(tf_name)
        assert len(lines) == 1
        assert confident is False
        assert uncertain is True
    finally:
        if os.path.exists(tf_name):
            os.remove(tf_name)


def test_unsupported_slide_box_content_gate():
    """Verifies that injecting extraneous external clinical content into slide box triggers UNSUPPORTED_SLIDE_BOX_CONTENT."""
    raw_slide = {
        "slide_number": 15,
        "title_raw": "Hypertension Classification",
        "text_lines": [
            "Normal BP: < 120/80 mmHg",
            "Elevated BP: 120-129 / < 80 mmHg",
            "Stage 1 HTN: 130-139 / 80-89 mmHg"
        ],
        "ocr_text_lines": []
    }
    # Translator translated the 3 lines, BUT ALSO injected 4 extraneous drug regimens from Robbins into the slide box!
    translated_slide = {
        "slide_number": 15,
        "title_en": "Hypertension Classification",
        "title_fa": "طبقه‌بندی پرفشاری خون",
        "bullets": [
            {"lead": "نرمال", "text": "فشار خون زیر 120/80 mmHg"},
            {"lead": "افزایش یافته", "text": "فشار بین 120-129 و کمتر از 80"},
            {"lead": "مرحله یک", "text": "فشار بین 130-139 یا 80-89 mmHg"},
            # Injected ungrounded clinical regimen into slide box:
            {"lead": "درمان دارویی رابینز", "text": "تجویز آملودیپین (Amlodipine 5mg)، لوزارتان (Losartan 50mg)، هیدروکلروتیازید (Hydrochlorothiazide 25mg) و اسپیرونولاکتون (Spironolactone 25mg)"}
        ]
    }

    issues = check_slide_pair(raw_slide, translated_slide)
    unsupported_errs = [iss for iss in issues if iss["error_type"] == "UNSUPPORTED_SLIDE_BOX_CONTENT"]
    assert len(unsupported_errs) == 1
    assert unsupported_errs[0]["severity"] == "error"
    assert any("amlodipine" in str(tok).lower() for tok in unsupported_errs[0]["unsupported_tokens"])


def test_source_refs_validation():
    """Verifies that invalid source_refs format in bullets is flagged."""
    raw_slide = {
        "slide_number": 20,
        "title_raw": "Diabetes Diagnosis",
        "text_lines": ["Fasting plasma glucose >= 126 mg/dL"],
        "ocr_text_lines": []
    }
    translated_slide = {
        "slide_number": 20,
        "title_en": "Diabetes Diagnosis",
        "title_fa": "تشخیص دیابت",
        "bullets": [
            {"lead": "قند ناشتا", "text": "گلوکز مساوی یا بیشتر از 126 mg/dL", "source_refs": "invalid_should_be_list"}
        ]
    }

    issues = check_slide_pair(raw_slide, translated_slide)
    ref_issues = [iss for iss in issues if iss["error_type"] == "INVALID_SOURCE_REF"]
    assert len(ref_issues) == 1
    assert ref_issues[0]["severity"] == "warning"


def test_topic_displacement_avoids_false_positive_on_high_current_overlap():
    """Verifies that TEMPORAL_TOPIC_DISPLACEMENT is NOT emitted when audio has strong (>30%) overlap with current slide."""
    chunks = [{
        "start_sec": 0,
        "end_sec": 120,
        "text": "استاد درباره هورمون‌های تیروئید، سنتز T3 و T4، گیرنده‌های هورمونی و فیدبک منفی صحبت کردند."
    }]
    slides = [
        {
            "slide_number": 1,
            "title_fa": "هورمون‌های تیروئید",
            "title_en": "Thyroid Hormones",
            "audio_time_range": "00:00 - 02:00",
            "bullets": [
                {"lead": "سنتز هورمون", "text": "سنتز هورمون‌های T3 و T4 در فولیکول‌های تیروئید"}
            ],
            "spoken_lecture": "استاد درباره هورمون‌های تیروئید و سنتز هورمونی T3 و T4 در فولیکول صحبت کردند."
        },
        {
            "slide_number": 2,
            "title_fa": "سنتز و تنظیم تیروئید",
            "title_en": "Thyroid Synthesis and Regulation",
            "audio_time_range": "02:00 - 04:00",
            "bullets": [
                {"lead": "تنظیم", "text": "گیرنده‌های هورمونی و فیدبک منفی با T3 و T4"}
            ],
            "spoken_lecture": "تنظیم ترشح تیروئید از طریق محور هیپوتالاموس و فیدبک منفی انجام می‌شود."
        }
    ]

    issues, stats = evaluate_slide_level_grounding(slides, chunks)
    # Since Slide 1 audio has strong overlap with Slide 1 itself (> 30%), displacement to Slide 2 MUST NOT be emitted!
    disp_issues = [i for i in issues if i.get("type") == "TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY"]
    assert len(disp_issues) == 0


def test_allow_review_cannot_bypass_hard_fail():
    """Verifies that --allow-review strictly CANNOT downgrade non-bypassable hard failures (e.g. duplicate slide numbers)."""
    import subprocess
    import json
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create valid raw slides
        raw_slides = [
            {"slide_number": 1, "title_raw": "Slide 1", "text_lines": ["Line 1", "Line 2"]},
            {"slide_number": 2, "title_raw": "Slide 2", "text_lines": ["Line 3", "Line 4"]}
        ]
        raw_path = os.path.join(tmp_dir, "raw_slides.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_slides, f, ensure_ascii=False)

        # Create invalid translated slides with DUPLICATE slide numbers
        invalid_slides = [
            {"slide_number": 1, "title_fa": "اسلاید ۱", "title_en": "Slide 1", "bullets": [{"lead": "۱", "text": "Line 1"}]},
            {"slide_number": 1, "title_fa": "اسلاید ۱ تکراری", "title_en": "Slide 1 Dup", "bullets": [{"lead": "۲", "text": "Line 2"}]}
        ]
        slides_path = os.path.join(tmp_dir, "translated_slides.json")
        with open(slides_path, "w", encoding="utf-8") as f:
            json.dump(invalid_slides, f, ensure_ascii=False)

        diag_path = os.path.join(tmp_dir, "diag.json")
        script_path = os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py")
        cmd = [
            sys.executable, script_path,
            "--raw", raw_path,
            "--translated", slides_path,
            "--diagnostic-json", diag_path,
            "--allow-review"  # User attempts to bypass with --allow-review
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        assert res.returncode == 1  # MUST fail hard (exit code 1)!
        assert "GATE FAILED" in res.stdout or "DUPLICATE" in res.stdout


def test_pipeline_allow_review_cannot_bypass_hard_fail():
    """Verifies that run_pipeline.py build/publish commands CANNOT bypass hard verification failures with --allow-review."""
    import subprocess
    import json
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        raw_slides = [
            {"slide_number": 1, "title_raw": "Slide 1", "text_lines": ["Line 1", "Line 2"]},
            {"slide_number": 2, "title_raw": "Slide 2", "text_lines": ["Line 3", "Line 4"]}
        ]
        raw_path = os.path.join(tmp_dir, "raw_slides.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_slides, f, ensure_ascii=False)

        # Duplicate slide 1 creates a non-bypassable hard structural failure
        invalid_slides = [
            {"slide_number": 1, "title_fa": "اسلاید ۱", "title_en": "Slide 1", "bullets": [{"lead": "۱", "text": "Line 1"}]},
            {"slide_number": 1, "title_fa": "اسلاید ۱ تکراری", "title_en": "Slide 1 Dup", "bullets": [{"lead": "۲", "text": "Line 2"}]}
        ]
        slides_path = os.path.join(tmp_dir, "translated_slides.json")
        with open(slides_path, "w", encoding="utf-8") as f:
            json.dump(invalid_slides, f, ensure_ascii=False)

        pipeline_path = os.path.join(SCRIPTS_DIR, "run_pipeline.py")
        cmd = [
            sys.executable, pipeline_path,
            "publish",
            "--raw", raw_path,
            "--translated", slides_path,
            "--output", os.path.join(tmp_dir, "out.docx"),
            "--allow-review"  # Pipeline must NOT bypass hard failure
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        assert res.returncode == 1, f"Pipeline bypassed hard fail! stdout: {res.stdout}\nstderr: {res.stderr}"


def test_source_refs_bounds_and_acronym_expansions():
    """Verifies source_refs bounds checking and medical acronym expansion immunity in Check 3.4."""
    # 1. Test source_refs out-of-bounds warning
    raw_item = {
        "slide_number": 10,
        "title_raw": "Parathyroid Gland Physiology",
        "text_lines": [
            "PTH regulates serum calcium concentration",
            "PTH acts directly on bone and kidney",
            "PTH increases tubular calcium reabsorption",
            "PTH stimulates calcitriol synthesis"
        ],
        "ocr_text_lines": []
    }
    trans_with_bad_ref = {
        "slide_number": 10,
        "title_fa": "فیزیولوژی پاراتیروئید",
        "title_en": "Parathyroid Gland Physiology",
        "bullets": [
            {"lead": "تنظیم کلسیم", "text": "تنظیم غلظت کلسیم توسط PTH و عملکرد کلیوی", "source_refs": ["digital:99"]}
        ]
    }
    issues = check_slide_pair(raw_item, trans_with_bad_ref)
    assert any(i.get("type") == "INVALID_SOURCE_REF_BOUNDS" for i in issues)

    # 2. Test legitimate acronym expansion (PTH -> Parathyroid hormone) is NOT flagged as unsupported content
    # Note: 'parathyroid', 'hormone' are not in raw text_lines (which only had PTH), but are allowed by MEDICAL_ACRONYM_COMPONENTS
    trans_with_expansion = {
        "slide_number": 10,
        "title_fa": "فیزیولوژی پاراتیروئید",
        "title_en": "Parathyroid Gland Physiology",
        "bullets": [
            {"lead": "هورمون پاراتیروئید", "text": "هورمون پاراتیروئید (Parathyroid hormone; PTH) ترشح کلسیم را تنظیم می‌کند", "source_refs": ["digital:0"]},
            {"lead": "اثر استخوانی", "text": "PTH اثر مستقیم بر استخوان و کلیه دارد", "source_refs": ["digital:1"]},
            {"lead": "بازتجذب", "text": "افزایش بازجذب کلسیم در توبول کلیوی", "source_refs": ["digital:2"]},
            {"lead": "کلسی‌تریول", "text": "تحریک ساخت کلسی‌تریول در کلیه", "source_refs": ["digital:3"]}
        ]
    }
    issues_expansion = check_slide_pair(raw_item, trans_with_expansion)
    assert not any(i.get("type") == "UNSUPPORTED_SLIDE_BOX_CONTENT" for i in issues_expansion)


def test_ref_note_is_rendered_outside_slide_box_table():
    """Verifies that Track 3 ref_note is rendered in a separate dedicated table OUTSIDE the Slide Box table."""
    import docx
    from create_slide_pamphlet import add_slide_box_from_json
    
    doc = docx.Document()
    slide_data = {
        "slide_number": 5,
        "title_fa": "فیزیولوژی پاراتیروئید",
        "title_en": "Parathyroid Physiology",
        "bullets": [
            {"lead": "ترشح هورمون", "text": "هورمون PTH تنظیم‌کننده کلسیم سرم است."}
        ],
        "ref_note": "بر اساس رفرنس هاریسون، هیپرپاراتیروئیدی اولیه شایع‌ترین علت هیپرکلسمی در بیماران سرپایی است."
    }
    add_slide_box_from_json(doc, slide_data, ref_book_name="هاریسون")
    
    # Document should have two tables: table[0] is Slide Box, table[1] is Reference Note Box
    assert len(doc.tables) >= 2, f"Expected at least 2 tables (Slide Box + Ref Note), got {len(doc.tables)}"
    
    slide_box = doc.tables[0]
    slide_box_text = "\n".join(c.text for row in slide_box.rows for c in row.cells)
    
    # Slide Box must ONLY contain slide translation content
    assert "هیپرپاراتیروئیدی اولیه شایع‌ترین علت" not in slide_box_text, "ref_note was found inside the Slide Box table!"
    assert "PTH" in slide_box_text
    assert "تنظیم‌کننده کلسیم سرم است." in slide_box_text
    
    # The dedicated Reference Note table must contain ref_note
    ref_box = doc.tables[1]
    ref_box_text = "\n".join(c.text for row in ref_box.rows for c in row.cells)
    assert "هیپرپاراتیروئیدی اولیه شایع‌ترین علت" in ref_box_text
    assert "شرح تکمیلی رفرنس" in ref_box_text


def test_source_ref_semantic_provenance():
    """Verifies that citing a source line that does not ground the bullet triggers UNGROUNDED_SOURCE_REF_MAPPING."""
    raw_item = {
        "slide_number": 20,
        "title_raw": "Hypertension Guidelines",
        "text_lines": [
            "Definition: SBP >= 140 or DBP >= 90 mmHg",
            "Initial monotherapy: Thiazide, CCB, ACEi or ARB",
            "Target BP: < 130/80 mmHg in high-risk patients"
        ],
        "ocr_text_lines": []
    }
    # Bullet cites digital:0 (Definition), but actually translates monotherapy (digital:1)
    trans_mismatched_cite = {
        "slide_number": 20,
        "title_fa": "راهنمای پرفشاری خون",
        "title_en": "Hypertension Guidelines",
        "bullets": [
            {"lead": "درمان اولیه", "text": "شروع درمان دارویی با تیازید یا مهارکننده ACEi یا ARB", "source_refs": ["digital:0"]}
        ]
    }
    issues = check_slide_pair(raw_item, trans_mismatched_cite)
    assert any(i.get("type") == "UNGROUNDED_SOURCE_REF_MAPPING" for i in issues)

    # Correct citation to digital:1 should pass cleanly without UNGROUNDED_SOURCE_REF_MAPPING
    trans_correct_cite = {
        "slide_number": 20,
        "title_fa": "راهنمای پرفشاری خون",
        "title_en": "Hypertension Guidelines",
        "bullets": [
            {"lead": "درمان اولیه", "text": "شروع درمان دارویی با تیازید یا مهارکننده ACEi یا ARB", "source_refs": ["digital:1"]}
        ]
    }
    clean_issues = check_slide_pair(raw_item, trans_correct_cite)
    assert not any(i.get("type") == "UNGROUNDED_SOURCE_REF_MAPPING" for i in clean_issues)


def test_pure_persian_translation_passes_bilingual_recall():
    """Verifies that a pure Persian translation (without Latin English words) passes 50% recall via Bilingual Concept Engine."""
    raw_slide = {
        "slide_number": 30,
        "title_raw": "Pathogenesis of Hyperthyroidism and Goiter",
        "text_lines": [
            "Hyperthyroidism involves excess thyroid hormone synthesis",
            "Stimulation of thyroid follicular cells by antibodies",
            "Clinical manifestations include tachycardia, weight loss, and tremors"
        ],
        "ocr_text_lines": []
    }
    # Pure Persian translation with zero English/ASCII tokens in the bullets
    trans_pure_persian = {
        "slide_number": 30,
        "title_fa": "پاتوژنز پرکاری تیروئید و گواتر",
        "title_en": "Pathogenesis of Hyperthyroidism and Goiter",
        "bullets": [
            {"lead": "تولید هورمون", "text": "پرکاری تیروئید ناشی از افزایش سنتز هورمون تیروئیدی است."},
            {"lead": "تحریک سلولی", "text": "تحریک سلول‌های تیروئید رخ می‌دهد."},
            {"lead": "تظاهرات بالینی", "text": "علائم بالینی شامل تاکی‌کاردی، کاهش وزن و لرزش اندام‌ها می‌باشد."}
        ]
    }
    issues = check_slide_pair(raw_slide, trans_pure_persian)
    assert not any(i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY" for i in issues)
    assert not any(i.get("type") == "PARAMETRIC_HALLUCINATION_RISK" for i in issues)


def test_persian_pharma_addition_detected_as_unsupported():
    """Verifies that injecting Persian drug treatments not present in raw slide triggers UNSUPPORTED_SLIDE_BOX_CONTENT."""
    raw_slide = {
        "slide_number": 31,
        "title_raw": "Etiology of Thyroid Hormone Excess",
        "text_lines": [
            "Primary thyroid dysfunction and autonomous adenoma",
            "Increased thyroid hormone release into circulation"
        ],
        "ocr_text_lines": []
    }
    # Translation injects Persian pharmacological treatment 'متیمازول' which was nowhere in the raw slide
    trans_with_persian_drug = {
        "slide_number": 31,
        "title_fa": "اتیولوژی افزایش هورمون تیروئید",
        "title_en": "Etiology of Thyroid Hormone Excess",
        "bullets": [
            {"lead": "علت اولیه", "text": "اختلال اولیه غده تیروئید و ترشح هورمون به گردش خون."},
            {"lead": "درمان دارویی", "text": "درمان این بیماران معمولاً با داروی متیمازول انجام می‌شود."}
        ]
    }
    issues = check_slide_pair(raw_slide, trans_with_persian_drug)
    pharma_issues = [i for i in issues if i.get("type") == "UNSUPPORTED_SLIDE_BOX_CONTENT"]
    assert len(pharma_issues) == 1
    assert "متیمازول" in pharma_issues[0]["unsupported_tokens"]


def test_source_quote_validation():
    """Verifies that source_quote is validated against raw slide content."""
    raw_slide = {
        "slide_number": 32,
        "title_raw": "Diabetes Mellitus Diagnostic Criteria",
        "text_lines": [
            "Fasting plasma glucose >= 126 mg/dL",
            "HbA1c >= 6.5% using standardized NGSP assay"
        ],
        "ocr_text_lines": []
    }
    # 1. Valid source_quote matching raw line
    trans_valid_quote = {
        "slide_number": 32,
        "title_fa": "معیارهای تشخیصی دیابت ملیتوس",
        "title_en": "Diabetes Mellitus Diagnostic Criteria",
        "bullets": [
            {
                "lead": "قند ناشتا",
                "text": "قند خون پلاسما ناشتا مساوی یا بیشتر از 126 میلی‌گرم در دسی‌لیتر",
                "source_refs": ["digital:0"],
                "source_quote": "Fasting plasma glucose >= 126 mg/dL"
            }
        ]
    }
    issues_valid = check_slide_pair(raw_slide, trans_valid_quote)
    assert not any(i.get("type") == "UNVERIFIED_SOURCE_QUOTE" for i in issues_valid)

    # 2. Fabricated source_quote not found in raw slide
    trans_fake_quote = {
        "slide_number": 32,
        "title_fa": "معیارهای تشخیصی دیابت ملیتوس",
        "title_en": "Diabetes Mellitus Diagnostic Criteria",
        "bullets": [
            {
                "lead": "درمان انسولین",
                "text": "شروع انسولین گلارژین شبانه در بیماران با قند بالای 300",
                "source_refs": ["digital:0"],
                "source_quote": "Insulin glargine administered at bedtime for severe hyperglycemia"
            }
        ]
    }
    issues_fake = check_slide_pair(raw_slide, trans_fake_quote)
    assert any(i.get("type") == "UNVERIFIED_SOURCE_QUOTE" for i in issues_fake)


def test_adversarial_generic_persian_words_cannot_pass_recall():
    """
    Adversarial Test 1: Verifies that generic Persian words (کاهش, افزایش, فشار, قلب, کبد, تیروئید)
    cannot by themselves count as sufficient evidence for medical concepts, preventing false passes.
    """
    raw_slide = {
        "slide_number": 40,
        "title_raw": "Pathogenesis of Hyperthyroidism and Goiter",
        "text_lines": [
            "Hyperthyroidism involves excess thyroid hormone synthesis",
            "Stimulation of thyroid follicular cells by antibodies",
            "Clinical manifestations include tachycardia, weight loss, and tremors"
        ],
        "ocr_text_lines": []
    }
    # Adversarial translation composed entirely of generic chatter and isolated generic words
    trans_adversarial = {
        "slide_number": 40,
        "title_fa": "بررسی اجمالی بیماری ها",
        "title_en": "General Medical Review",
        "bullets": [
            {"lead": "نکته عمومی ۱:", "text": "در بدن انسان تیروئید و قلب و کبد وجود دارند."},
            {"lead": "نکته عمومی ۲:", "text": "کاهش و افزایش مواد مختلف فشار زیادی وارد می کند و درد ایجاد می شود."}
        ]
    }
    issues = check_slide_pair(raw_slide, trans_adversarial)
    # Generic word overlap must NOT pass the 50% substantive recall threshold!
    assert any(i.get("type") in ("SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY", "PARAMETRIC_HALLUCINATION_RISK") for i in issues)
    rec_issue = [i for i in issues if i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY"]
    if rec_issue:
        assert rec_issue[0]["recall_ratio"] < 0.50
        assert rec_issue[0]["recall_ratio"] == 0.0  # Zero legitimate concepts matched


def test_adversarial_cardiovascular_generic_word_fails():
    """
    Adversarial Test 2: Verifies that isolated generic organ words ('قلب') or direction words ('کاهش')
    do NOT match 'heart failure' or 'ejection fraction' without multi-word phrases or specific terms.
    """
    raw_slide = {
        "slide_number": 41,
        "title_raw": "Management of Heart Failure and Reduced Ejection Fraction",
        "text_lines": [
            "Secondary prevention in heart failure with reduced ejection fraction (HFrEF)",
            "Initiation of beta-blocker therapy and ACE inhibitors",
            "Target systemic vascular resistance reduction"
        ],
        "ocr_text_lines": []
    }
    # Adversarial translation using generic words 'قلب' and 'کاهش' without medical concept phrases
    trans_adversarial = {
        "slide_number": 41,
        "title_fa": "مدیریت بیماری",
        "title_en": "Disease Management",
        "bullets": [
            {"lead": "توصیه عمومی:", "text": "بیمار باید به قلب خود توجه کند و نمک کم مصرف نماید تا فشار کاهش یابد."}
        ]
    }
    issues = check_slide_pair(raw_slide, trans_adversarial)
    assert any(i.get("type") in ("SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY", "PARAMETRIC_HALLUCINATION_RISK") for i in issues)


def test_valid_source_quote_with_unsupported_addition_still_fails():
    """
    Verifies that source_quote proves ONLY source existence, not complete bullet grounding.
    A bullet containing a 100% valid source_quote from the raw slide plus ungrounded
    additional clinical pharmacology (e.g. injected Persian drug) must STILL fail with UNSUPPORTED_SLIDE_BOX_CONTENT.
    """
    raw_slide = {
        "slide_number": 42,
        "title_raw": "Hypertension Diagnostic Criteria",
        "text_lines": [
            "Systolic BP >= 140 mmHg or Diastolic BP >= 90 mmHg",
            "Essential hypertension evaluation"
        ],
        "ocr_text_lines": []
    }
    # Bullet has valid source_quote, BUT text injects ungrounded pharmacology ('آملودیپین')
    trans_bullet_with_pharma = {
        "slide_number": 42,
        "title_fa": "معیارهای تشخیصی پرفشاری خون",
        "title_en": "Hypertension Diagnostic Criteria",
        "bullets": [
            {
                "lead": "معیار فشار خون",
                "text": "فشار خون سیستولیک بالای 140 یا دیاستولیک بالای 90 است و بیمار باید فوراً داروی آملودیپین دریافت کند.",
                "source_refs": ["digital:0"],
                "source_quote": "Systolic BP >= 140 mmHg or Diastolic BP >= 90 mmHg"
            }
        ]
    }
    issues = check_slide_pair(raw_slide, trans_bullet_with_pharma)
    # 1. source_quote is valid so UNVERIFIED_SOURCE_QUOTE must NOT be emitted
    assert not any(i.get("type") == "UNVERIFIED_SOURCE_QUOTE" for i in issues)
    # 2. BUT the injected drug MUST trigger UNSUPPORTED_SLIDE_BOX_CONTENT
    unsupported = [i for i in issues if i.get("type") == "UNSUPPORTED_SLIDE_BOX_CONTENT"]
    assert any("amlodipine" in str(tok).lower() or "املودیپین" in str(tok) or "آملودیپین" in str(tok) for tok in unsupported[0]["unsupported_tokens"])


def test_valid_source_quote_does_not_artificially_credit_untranslated_slide():
    """
    Verifies that source_quote does NOT artificially inflate recall.
    A slide citing source_quotes but omitting literal translation of the slide concepts
    must still fail the substantive recall threshold.
    """
    raw_slide = {
        "slide_number": 43,
        "title_raw": "Pathogenesis of Hyperthyroidism and Goiter",
        "text_lines": [
            "Hyperthyroidism involves excess thyroid hormone synthesis",
            "Stimulation of thyroid follicular cells by antibodies",
            "Clinical manifestations include tachycardia, weight loss, and tremors"
        ],
        "ocr_text_lines": []
    }
    # Quotes valid source lines, but the actual bullet text is generic filler
    trans_with_quotes_but_no_translation = {
        "slide_number": 43,
        "title_fa": "پاتوژنز پرکاری تیروئید و گواتر",
        "title_en": "Pathogenesis of Hyperthyroidism and Goiter",
        "bullets": [
            {
                "lead": "نکته عمومی",
                "text": "این یک اسلاید است که در کلاس بحث شد.",
                "source_refs": ["digital:0"],
                "source_quote": "Hyperthyroidism involves excess thyroid hormone synthesis"
            }
        ]
    }
    issues = check_slide_pair(raw_slide, trans_with_quotes_but_no_translation)
    # Must fail 50% substantive recall because the bullet text didn't translate the concepts!
    assert any(i.get("type") == "SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY" for i in issues)


def test_unified_bilingual_concepts_active():
    """Verifies that BILINGUAL_MEDICAL_CONCEPTS (~150+ terms) are unified and active in evaluate_concept_overlap."""
    from text_utils import UNIFIED_SPECIFIC_MEDICAL_TERMS, evaluate_concept_overlap, extract_tokens
    
    # Check that specialized terms from BILINGUAL_MEDICAL_CONCEPTS are present
    assert "podocyte" in UNIFIED_SPECIFIC_MEDICAL_TERMS
    assert "creatinine" in UNIFIED_SPECIFIC_MEDICAL_TERMS
    assert "pneumonia" in UNIFIED_SPECIFIC_MEDICAL_TERMS
    assert "cirrhosis" in UNIFIED_SPECIFIC_MEDICAL_TERMS
    
    # Test recall evaluation with unified concepts
    raw_tokens = extract_tokens("Podocyte effacement and elevated creatinine")
    trans_text = "تغییرات پودوسیت و افزایش کراتینین سرم در بیماران کلیوی"
    trans_tokens = extract_tokens(trans_text)
    
    overlap = evaluate_concept_overlap(raw_tokens, trans_tokens, trans_text)
    assert "podocyte" in overlap
    assert "creatinine" in overlap


def test_generic_persian_words_cannot_pass_concept_recall():
    """Adversarial test: Generic Persian words alone CANNOT make an ungrounded translation pass recall."""
    from text_utils import evaluate_concept_overlap, extract_tokens, NORMALIZED_GENERIC_PERSIAN_WORDS
    
    # Raw slide has specific concepts
    raw_tokens = extract_tokens("Thyroid hormone excess causing tachycardia and weight loss")
    
    # Adversarial translation consisting purely of generic words (کاهش, افزایش, فشار, قلب, کبد, تیروئید)
    # without specific phrases or specific medical terms
    generic_text = "کاهش و افزایش و فشار و قلب و کبد و تیروئید در بیماران"
    generic_tokens = extract_tokens(generic_text)
    
    # Generic tokens must all be recognized in NORMALIZED_GENERIC_PERSIAN_WORDS
    assert len(generic_tokens.intersection(NORMALIZED_GENERIC_PERSIAN_WORDS)) > 0
    
    # evaluate_concept_overlap must return EMPTY overlap for thyroid/tachycardia/weight/loss against this generic text
    overlap = evaluate_concept_overlap(raw_tokens, generic_tokens, generic_text)
    assert "tachycardia" not in overlap
    assert "thyroid" not in overlap
    assert "loss" not in overlap


def test_image_extraction_error_diagnostic_flag():
    """Verifies that PPTX slide extractor includes image_extraction_error flag in slide metadata."""
    from extract_presentation import extract_pptx
    import pptx
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
        tmp_pptx = f.name
        
    try:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = "Diagnostic Test Slide"
        prs.save(tmp_pptx)
        
        slides = extract_pptx(tmp_pptx)
        assert len(slides) == 1
        assert "image_extraction_error" in slides[0]
        assert slides[0]["image_extraction_error"] is False
    finally:
        if os.path.exists(tmp_pptx):
            os.remove(tmp_pptx)


def test_image_extraction_error_verification_warning():
    """Verifies that verify_slide_alignment issues an IMAGE_EXTRACTION_FAILED warning when image_extraction_error is True."""
    from verify_slide_alignment import check_slide_pair
    
    raw_item = {
        "slide_number": 12,
        "title_raw": "Pathology Micrograph",
        "text_lines": ["Biopsy specimen of thyroid gland"],
        "ocr_text_lines": [],
        "image_extraction_error": True
    }
    trans_item = {
        "slide_number": 12,
        "title_fa": "میکروگراف پاتولوژی",
        "title_en": "Pathology Micrograph",
        "bullets": [
            {"lead": "نمونه بیوپسی", "text": "بیوپسی غده تیروئید"}
        ]
    }
    
    issues = check_slide_pair(raw_item, trans_item)
    assert any(i.get("type") == "IMAGE_EXTRACTION_FAILED" and i.get("severity") == "warning" for i in issues)


def test_detect_image_table_recognizes_harrison_table_screenshot():
    """Verifies that detect_image_table detects table screenshots with classification keywords and enumeration."""
    from extract_presentation import detect_image_table

    title = "Classification of Causes of Hypercalcemia"
    text_lines = ["Classification of Causes of Hypercalcemia"]
    ocr_lines = [
        "I. Parathyroid-related: Primary hyperparathyroidism, Lithium therapy",
        "II. Malignancy-related: Solid tumor metastases breast, lung, kidney",
        "III. Vitamin D-related: Vitamin D intoxication, Sarcoidosis",
        "IV. Associated with Renal Failure: Severe secondary hyperparathyroidism, Aluminum intoxication"
    ]
    is_table = detect_image_table(title, text_lines, ocr_lines, has_images=True)
    assert is_table is True, "Expected detect_image_table to identify Harrison classification screenshot as image table"


def test_detect_image_table_negative_for_plain_diagram():
    """Verifies that detect_image_table does not misclassify simple anatomical diagrams as tables."""
    from extract_presentation import detect_image_table

    title = "Thyroid Anatomy"
    text_lines = ["Thyroid Anatomy"]
    ocr_lines = ["Left lobe", "Right lobe", "Isthmus"]
    is_table = detect_image_table(title, text_lines, ocr_lines, has_images=True)
    assert is_table is False, "Expected plain anatomical diagram not to be flagged as image table"







