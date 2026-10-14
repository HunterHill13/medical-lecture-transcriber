import os
import sys
import json
import pytest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from create_slide_pamphlet import build_pamphlet_from_json
from batch_orchestrator import partition_slides, merge_slide_batches
import docx


def test_toc_initial_slide_coverage_in_pamphlet(tmp_path):
    """
    Factor 3 Regression Test:
    When Slide 1 has no 'section_title', but a subsequent slide (e.g. Slide 3)
    has 'section_title', build_pamphlet_from_json must automatically synthesize an
    opening section entry for Slide 1 so that slides 1..(M-1) are not omitted from the TOC.
    """
    slides = [
        {
            "slide_number": 1,
            "title_fa": "فیزیولوژی تخمدان",
            "title_en": "Ovarian Physiology",
            "bullets": [["تعریف", "نمو جنینی تخمدان"]],
            "spoken_lecture": "استاد مبحث نمو تخمدان را توضیح دادند.",
        },
        {
            "slide_number": 2,
            "title_fa": "فولیکولوژنز",
            "title_en": "Folliculogenesis",
            "bullets": [["مراحل", "فولیکول پرایموردیال"]],
            "spoken_lecture": "مراحل نمو فولیکولی تشریح شد.",
        },
        {
            "slide_number": 3,
            "section_title": "آناتومی تخمدان",
            "title_fa": "آناتومی ماکروسکوپیک",
            "title_en": "Macroscopic Anatomy",
            "bullets": [["خونرسانی", "عروق اووارین"]],
            "spoken_lecture": "آناتومی و خونرسانی تخمدان بیان شد.",
        },
    ]

    trans_json = tmp_path / "translated_slides.json"
    out_docx = tmp_path / "output.docx"
    trans_json.write_text(json.dumps(slides, ensure_ascii=False), encoding="utf-8")

    build_pamphlet_from_json(str(trans_json), str(out_docx), title="جزوه فیزیولوژی و آناتومی")
    doc = docx.Document(str(out_docx))
    # Inspect tables in doc: the first table should be TOC
    assert len(doc.tables) >= 1, "Pamphlet must contain a table (TOC)"
    toc_table = doc.tables[0]
    
    # Check rows: header + 2 section rows
    # Row 1 (header): شماره بخش | عنوان مبحث | زمان فایل صوتی | محدوده اسلایدها
    # Row 2 (Section 1): بخش ۱ | فیزیولوژی تخمدان (or مقدمه) | ... | اسلایدهای ۱ الی ۲
    # Row 3 (Section 2): بخش ۲ | آناتومی تخمدان | ... | اسلاید ۳
    table_text = " ".join(cell.text for row in toc_table.rows for cell in row.cells)
    
    assert "فیزیولوژی تخمدان" in table_text or "مقدمه" in table_text, (
        f"TOC table must cover initial slides (1-2), found: {table_text}"
    )
    assert "آناتومی تخمدان" in table_text, f"TOC table must cover section 2, found: {table_text}"
    assert "اسلایدهای ۱ الی ۲" in table_text or "اسلاید ۱ الی ۲" in table_text or "اسلایدهای 1 الی 2" in table_text


def test_batch_orchestrator_synthesizes_slide_one_section_title(tmp_path):
    """
    Factor 3 Regression Test:
    When merging shards where Slide 1 has no section_title but later slides do,
    merge_slide_batches must synthesize an introductory section_title on Slide 1.
    """
    raw_path = tmp_path / "raw_slides.json"
    batches_dir = tmp_path / "batches"
    out_path = tmp_path / "translated_slides.json"

    raw_slides = [
        {"slide_number": 1, "text_lines": ["Slide 1 Title"]},
        {"slide_number": 2, "text_lines": ["Slide 2 Title"]},
        {"slide_number": 3, "text_lines": ["Slide 3 Title"]},
    ]
    raw_path.write_text(json.dumps(raw_slides), encoding="utf-8")

    manifest = partition_slides(str(raw_path), str(batches_dir), batch_size=3, halo_size=0)
    
    shard_file = batches_dir / manifest["batches"][0]["output_shard_file"]
    shard_slides = [
        {
            "slide_number": 1,
            "title_fa": "مبحث آغازین",
            "bullets": [],
            "spoken_lecture": "توضیح مقدماتی",
        },
        {
            "slide_number": 2,
            "title_fa": "مبحث ادامه",
            "bullets": [],
            "spoken_lecture": "توضیح ادامه",
        },
        {
            "slide_number": 3,
            "section_title": "مبحث تخصصی دوم",
            "title_fa": "مبحث تخصصی",
            "bullets": [],
            "spoken_lecture": "توضیح تخصصی",
        },
    ]
    shard_file.write_text(json.dumps(shard_slides), encoding="utf-8")

    report = merge_slide_batches(
        batches_dir=str(batches_dir),
        raw_slides_path=str(raw_path),
        output_path=str(out_path),
    )

    merged = json.loads(out_path.read_text(encoding="utf-8"))
    assert merged[0].get("section_title") is not None, "Slide 1 must have section_title synthesized"
    assert "مبحث آغازین" in merged[0]["section_title"] or "مقدمه" in merged[0]["section_title"]


def test_partition_slides_includes_rules_6_7_8(tmp_path):
    """
    Factor 1, 2, 4 Regression Test:
    Ensures partition_slides instructs subagents regarding lecture termination,
    unvoiced trailing slides, continuous global timestamps, and Slide 1 section title.
    """
    raw_path = tmp_path / "raw_slides.json"
    batches_dir = tmp_path / "batches"

    raw_slides = [{"slide_number": 1, "text_lines": ["Slide 1"]}]
    raw_path.write_text(json.dumps(raw_slides), encoding="utf-8")

    partition_slides(str(raw_path), str(batches_dir), batch_size=1)
    b_raw = json.loads((batches_dir / "batch_01_01_raw.json").read_text(encoding="utf-8"))
    instructions = b_raw.get("instructions", {})

    assert "rule_6_lecture_termination_and_unvoiced_trailing_slides" in instructions
    assert "rule_7_continuous_global_timestamps" in instructions
    assert "rule_8_section_title_on_slide_one" in instructions


def test_verify_slide_alignment_detects_chunk_relative_timestamp_reset(tmp_path):
    """
    Factor 4 Regression Test:
    Detects when a mid-presentation slide resets to near 00:00 (chunk-relative timestamp)
    without an intentional cross-reference.
    """
    import subprocess
    raw_slides = []
    trans_slides = []

    for i in range(1, 15):
        raw_slides.append({
            "slide_number": i,
            "title_raw": f"Topic {i}",
            "text_lines": [f"Content {i}"],
            "has_tables": False
        })
        # Slide 1-10 advance from 01:00 to 18:00
        # Slide 11 resets to 00:15
        if i <= 10:
            time_str = f"{(i*100)//60:02d}:{(i*100)%60:02d}"
        elif i == 11:
            time_str = "00:15"
        else:
            time_str = f"{((i-10)*100)//60:02d}:{((i-10)*100)%60:02d}"

        trans_slides.append({
            "slide_number": i,
            "title_fa": f"مبحث {i}",
            "title_en": f"Topic {i}",
            "audio_time": time_str,
            "audio_time_range": f"{time_str} - {time_str}",
            "bullets": [{"lead": "نکته", "text": f"مفهوم شماره {i} برای دانشجو"}],
            "spoken_lecture": f"استاد در اسلاید {i} توضیحات کامل دادند.",
        })

    raw_path = tmp_path / "raw.json"
    trans_path = tmp_path / "trans.json"
    diag_file = tmp_path / "report.json"
    raw_path.write_text(json.dumps(raw_slides), encoding="utf-8")
    trans_path.write_text(json.dumps(trans_slides), encoding="utf-8")

    script = os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py")
    subprocess.run(
        [
            sys.executable,
            script,
            "--raw",
            str(raw_path),
            "--translated",
            str(trans_path),
            "--diagnostic-json",
            str(diag_file),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    assert diag_file.exists()
    diag = json.loads(diag_file.read_text(encoding="utf-8"))
    warn_or_err = [w.get("error_type") or w.get("warning_type") or w.get("type") for w in diag.get("warnings", []) + diag.get("errors", [])]
    assert "CHUNK_RELATIVE_TIMESTAMP_RESET" in warn_or_err


def test_verify_slide_alignment_detects_hallucinated_trailing_lecture_displacement(tmp_path):
    """
    Factor 1 & 2 Regression Test:
    Lecture terminates at slide 10 (farewell remarks).
    Slide 14 hallucinates and copies earlier spoken lecture from slide 2 instead of being unvoiced/skipped.
    verify_slide_alignment must flag HALLUCINATED_TRAILING_LECTURE_DISPLACEMENT.
    """
    import subprocess
    raw_slides = []
    trans_slides = []

    earlier_lecture = "مبحث سندروم تخمدان پلی کیستیک و معیارهای روتردام به تفصیل تشریح گردید."

    for i in range(1, 16):
        raw_slides.append({
            "slide_number": i,
            "title_raw": f"Slide {i}",
            "text_lines": [f"Medical concept {i}"],
            "has_tables": False
        })
        if i < 10:
            spk = earlier_lecture if i == 2 else f"توضیحات مربوط به اسلاید {i} توسط استاد"
            trans_slides.append({
                "slide_number": i,
                "title_fa": f"اسلاید {i}",
                "title_en": f"Slide {i}",
                "bullets": [{"lead": "نکته", "text": f"مفهوم پزشکی {i}"}],
                "spoken_lecture": spk,
            })
        elif i == 10:
            trans_slides.append({
                "slide_number": i,
                "title_fa": "اسلاید پایانی و جمع‌بندی",
                "title_en": "Conclusion",
                "bullets": [{"lead": "جمع‌بندی", "text": "پایان مبحث آمنوره"}],
                "spoken_lecture": "این الگوریتم آخرین اسلایدم هستش و برای همه شما در دوره استاژری آرزوی موفقیت دارم و خسته نباشید.",
            })
        elif i == 14:
            # Hallucinated displacement of earlier lecture (slide 2) onto unvoiced slide 14!
            trans_slides.append({
                "slide_number": i,
                "title_fa": f"اسلاید تدریس نشده {i}",
                "title_en": f"Slide {i}",
                "bullets": [{"lead": "نکته", "text": f"مفهوم پزشکی {i}"}],
                "spoken_lecture": earlier_lecture,  # Hallucinated repetition of slide 2
            })
        else:
            trans_slides.append({
                "slide_number": i,
                "title_fa": f"اسلاید تدریس نشده {i}",
                "title_en": f"Slide {i}",
                "bullets": [{"lead": "نکته", "text": f"مفهوم پزشکی {i}"}],
                "is_skipped": True,
                "spoken_lecture": "",
                "ref_note": "شرح تکمیلی بر اساس رفرنس جهت درک مبحث درمانی که توسط استاد در کلاس تدریس نشد.",
            })

    raw_path = tmp_path / "raw.json"
    trans_path = tmp_path / "trans.json"
    diag_file = tmp_path / "report.json"
    raw_path.write_text(json.dumps(raw_slides), encoding="utf-8")
    trans_path.write_text(json.dumps(trans_slides), encoding="utf-8")

    script = os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py")
    subprocess.run(
        [
            sys.executable,
            script,
            "--raw",
            str(raw_path),
            "--translated",
            str(trans_path),
            "--diagnostic-json",
            str(diag_file),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )

    assert diag_file.exists()
    diag = json.loads(diag_file.read_text(encoding="utf-8"))
    warn_or_err = [w.get("error_type") or w.get("warning_type") or w.get("type") for w in diag.get("warnings", []) + diag.get("errors", [])]
    assert "HALLUCINATED_TRAILING_LECTURE_DISPLACEMENT" in warn_or_err
