import os
import sys
import json
import subprocess
import pytest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from batch_orchestrator import (
    partition_slides,
    merge_slide_batches,
    run_qa_preflight_and_validate,
)


def _make_sample_raw_slides(count=15):
    slides = []
    for i in range(1, count + 1):
        slides.append({
            "slide_number": i,
            "text_lines": [f"Slide {i} Title", f"Clinical concept {i}"],
            "has_tables": (i in (4, 11)),
            "has_images": (i in (2, 4, 9, 11)),
            "needs_vision_inspection": (i in (4, 9, 11)),
            "image_path": f"slide_images/slide_{i:02d}.png",
        })
    return slides


def test_partition_slides_creates_batches_and_context_halo(tmp_path):
    raw_path = tmp_path / "raw_slides.json"
    batches_dir = tmp_path / "batches"
    chunks_manifest = tmp_path / "chunks_manifest.json"

    raw_slides = _make_sample_raw_slides(15)
    raw_path.write_text(json.dumps({"slides": raw_slides}, ensure_ascii=False), encoding="utf-8")
    chunks_manifest.write_text(
        json.dumps({
            "chunks": [
                {"index": 1, "file": "chunks/chunk_01.m4a"},
                {"index": 2, "file": "chunks/chunk_02.m4a"},
                {"index": 3, "file": "chunks/chunk_03.m4a"},
                {"index": 4, "file": "chunks/chunk_04.m4a"},
            ]
        }),
        encoding="utf-8",
    )

    manifest = partition_slides(
        raw_slides_path=str(raw_path),
        batches_dir=str(batches_dir),
        batch_size=6,
        halo_size=1,
        chunks_manifest_path=str(chunks_manifest),
    )

    assert manifest["total_slides"] == 15
    assert manifest["total_batches"] == 3
    assert manifest["multi_agent_mandatory"] is True
    assert len(manifest["audio_transcription_groups"]) == 2

    b1 = json.loads((batches_dir / "batch_01_06_raw.json").read_text(encoding="utf-8"))
    b2 = json.loads((batches_dir / "batch_07_12_raw.json").read_text(encoding="utf-8"))
    b3 = json.loads((batches_dir / "batch_13_15_raw.json").read_text(encoding="utf-8"))

    assert b1["expected_slide_numbers"] == [1, 2, 3, 4, 5, 6]
    assert b1["halo_prev"] == []
    assert len(b1["halo_next"]) == 1 and b1["halo_next"][0]["slide_number"] == 7
    assert b1["halo_next"][0]["_halo_role"] == "read_only_prev_context" or b1["halo_next"][0]["_halo_role"] == "read_only_next_context"
    assert b1["mandatory_table_slides"] == [4]

    assert b2["expected_slide_numbers"] == [7, 8, 9, 10, 11, 12]
    assert len(b2["halo_prev"]) == 1 and b2["halo_prev"][0]["slide_number"] == 6
    assert len(b2["halo_next"]) == 1 and b2["halo_next"][0]["slide_number"] == 13
    assert b2["mandatory_table_slides"] == [11]

    assert b3["expected_slide_numbers"] == [13, 14, 15]
    assert len(b3["halo_prev"]) == 1 and b3["halo_prev"][0]["slide_number"] == 12
    assert b3["halo_next"] == []


def test_merge_slide_batches_strips_halo_sanitizes_latex_and_resolves_clusters(tmp_path):
    raw_path = tmp_path / "raw_slides.json"
    batches_dir = tmp_path / "batches"
    out_path = tmp_path / "translated_slides.json"

    raw_slides = _make_sample_raw_slides(6)
    raw_path.write_text(json.dumps(raw_slides, ensure_ascii=False), encoding="utf-8")

    manifest = partition_slides(
        raw_slides_path=str(raw_path),
        batches_dir=str(batches_dir),
        batch_size=3,
        halo_size=1,
    )
    assert manifest["total_batches"] == 2

    repeated_lecture = (
        "در این مبحث استاد به تفصیل پاتوفیزیولوژی هایپرکلسمی و نقش هورمون پاراتورمون را در افزایش بازجذب کلیوی کلسیم تشریح می‌کنند."
    )

    # Batch 1 shard (slides 1..3), plus accidental halo slide 4 included by subagent
    shard1 = [
        {
            "slide_number": 1,
            "title_fa": "اسلاید ۱",
            "title_en": "Slide 1",
            "bullets": [{"lead": "معیار:", "text": "مقدار $\\ ge   1.0 $ گرم"}],
            "spoken_lecture": "مقدمه جلسه اول.",
        },
        {
            "slide_number": 2,
            "title_fa": "اسلاید ۲",
            "title_en": "Slide 2",
            "bullets": ["سطح کلسیم $\\le 8.5$ میلی‌گرم"],
            "spoken_lecture": repeated_lecture,
        },
        {
            "slide_number": 3,
            "title_fa": "اسلاید ۳",
            "title_en": "Slide 3",
            "bullets": ["ادامه مبحث"],
            "parent_lecture_slide": 2,
            "spoken_lecture": repeated_lecture,
        },
        # Accidental halo slide 4 that should be stripped automatically
        {
            "slide_number": 4,
            "title_fa": "هاله اشتباهی",
            "bullets": [],
        },
    ]
    (batches_dir / "translated_batch_01_03.json").write_text(
        json.dumps(shard1, ensure_ascii=False), encoding="utf-8"
    )

    # Batch 2 shard (slides 4..6): slide 4 points to parent 3 (transitive to 2), slide 5 has LaTeX in table
    shard2 = [
        {
            "slide_number": 4,
            "title_fa": "اسلاید ۴",
            "title_en": "Slide 4",
            "parent_lecture_slide": 3,
            "bullets": ["جدول تشخیصی"],
            "table_data": {
                "headers": ["معیار", "مقدار ($\\ge 1.0$)"],
                "rows": [["کلسیم", "$\\ pm 0.5 $"]],
            },
        },
        {
            "slide_number": 5,
            "title_fa": "اسلاید ۵",
            "title_en": "Slide 5",
            "is_skipped": True,
            "bullets": ["نکته اسلاید ۵"],
            "ref_note": "💡 شرح تکمیلی رفرنس (هاریسون) جهت تفهیم مبحث: این اسلاید به بررسی دقیق علل نادر هایپرکلسمی در بیماران بستری می‌پردازد.",
        },
        {
            "slide_number": 6,
            "title_fa": "اسلاید ۶",
            "title_en": "Slide 6",
            "bullets": ["جمع‌بندی پایانی"],
            "spoken_lecture": "پایان جلسه.",
        },
    ]
    (batches_dir / "translated_batch_04_06.json").write_text(
        json.dumps(shard2, ensure_ascii=False), encoding="utf-8"
    )

    report = merge_slide_batches(
        batches_dir=str(batches_dir),
        raw_slides_path=str(raw_path),
        output_path=str(out_path),
        ref_book_name="هاریسون",
    )

    assert report["status"] == "PASSED"
    assert report["total_merged_slides"] == 6
    merged = json.loads(out_path.read_text(encoding="utf-8"))
    assert [s["slide_number"] for s in merged] == [1, 2, 3, 4, 5, 6]

    # Verify LaTeX math sanitization on bullets and table_data
    assert "≥ 1.0" in merged[0]["bullets"][0]["text"]
    assert "$" not in merged[0]["bullets"][0]["text"]
    assert "≤ 8.5" in merged[1]["bullets"][0]
    assert "≥ 1.0" in merged[3]["table_data"]["headers"][1]
    assert "± 0.5" in merged[3]["table_data"]["rows"][0][1]

    # Verify transitive parent_lecture_slide resolution (4 -> 3 -> 2 becomes 4 -> 2)
    assert merged[3]["parent_lecture_slide"] == 2

    # Verify ref_note dual prefix sanitization
    assert not merged[4]["ref_note"].startswith("💡")


def test_merge_slide_batches_detects_missing_slide_error(tmp_path):
    raw_path = tmp_path / "raw_slides.json"
    batches_dir = tmp_path / "batches"
    out_path = tmp_path / "translated_slides.json"

    raw_slides = _make_sample_raw_slides(4)
    raw_path.write_text(json.dumps(raw_slides, ensure_ascii=False), encoding="utf-8")

    partition_slides(raw_slides_path=str(raw_path), batches_dir=str(batches_dir), batch_size=2)

    # Write shard 1 with only slide 1 (missing slide 2)
    (batches_dir / "translated_batch_01_02.json").write_text(
        json.dumps([{"slide_number": 1, "title_fa": "۱", "bullets": []}]),
        encoding="utf-8",
    )
    (batches_dir / "translated_batch_03_04.json").write_text(
        json.dumps([
            {"slide_number": 3, "title_fa": "۳", "bullets": []},
            {"slide_number": 4, "title_fa": "۴", "bullets": []},
        ]),
        encoding="utf-8",
    )

    report = merge_slide_batches(
        batches_dir=str(batches_dir),
        raw_slides_path=str(raw_path),
        output_path=str(out_path),
        strict=True,
    )
    assert report["status"] == "FAILED"
    error_codes = {e["code"] for e in report["errors"]}
    assert "MISSING_SLIDES_IN_BATCH" in error_codes
    assert "GLOBAL_INDEX_GAP" in error_codes


def test_qa_preflight_and_validate_detects_unformatted_table_and_checks_report(tmp_path):
    raw_path = tmp_path / "raw_slides.json"
    trans_path = tmp_path / "translated_slides.json"
    batches_dir = tmp_path / "batches"
    qa_report_path = tmp_path / "qa_audit_report.json"

    raw_slides = [
        {"slide_number": 1, "text_lines": ["Intro"], "has_tables": False},
        {"slide_number": 2, "text_lines": ["Table Slide"], "has_tables": True},
    ]
    raw_path.write_text(json.dumps(raw_slides), encoding="utf-8")

    # Case 1: Slide 2 is missing table_data
    trans_missing_tbl = [
        {"slide_number": 1, "title_fa": "مقدمه", "bullets": ["بالت ۱"]},
        {"slide_number": 2, "title_fa": "جدول", "bullets": ["فقط بالت بدون جدول"]},
    ]
    trans_path.write_text(json.dumps(trans_missing_tbl, ensure_ascii=False), encoding="utf-8")

    res1 = run_qa_preflight_and_validate(
        raw_slides_path=str(raw_path),
        translated_path=str(trans_path),
        batches_dir=str(batches_dir),
        qa_report_path=str(qa_report_path),
        require_report=False,
    )
    assert res1["passed"] is False
    assert res1["preflight_issues_count"] == 1
    assert res1["preflight_issues"][0]["issue"] == "RAW_TABLE_NOT_FORMATTED_AS_TABLE"

    # Case 2: Slide 2 has proper table_data and QA Critic writes PASSED report
    trans_with_tbl = [
        {"slide_number": 1, "title_fa": "مقدمه", "bullets": ["بالت ۱"]},
        {
            "slide_number": 2,
            "title_fa": "جدول",
            "bullets": [],
            "table_data": {"headers": ["ستون ۱", "ستون ۲"], "rows": [["الف", "ب"]]},
        },
    ]
    trans_path.write_text(json.dumps(trans_with_tbl, ensure_ascii=False), encoding="utf-8")
    qa_report_path.write_text(
        json.dumps({
            "status": "PASSED",
            "total_slides_audited": 2,
            "table_slides_verified": [2],
            "defects": [],
        }),
        encoding="utf-8",
    )

    res2 = run_qa_preflight_and_validate(
        raw_slides_path=str(raw_path),
        translated_path=str(trans_path),
        batches_dir=str(batches_dir),
        qa_report_path=str(qa_report_path),
        require_report=True,
    )
    assert res2["passed"] is True
    assert res2["qa_report_valid"] is True


def test_run_pipeline_cli_partition_merge_and_qa_check(tmp_path):
    raw_path = tmp_path / "raw_slides.json"
    batches_dir = tmp_path / "batches"
    out_path = tmp_path / "translated_slides.json"
    qa_report_path = tmp_path / "qa_audit_report.json"

    raw_slides = [
        {"slide_number": 1, "text_lines": ["Slide 1"], "has_tables": False},
        {"slide_number": 2, "text_lines": ["Slide 2"], "has_tables": True},
    ]
    raw_path.write_text(json.dumps(raw_slides), encoding="utf-8")

    pipeline_script = os.path.join(SCRIPTS_DIR, "run_pipeline.py")

    # 1. CLI partition
    p1 = subprocess.run(
        [sys.executable, pipeline_script, "partition", "--raw", str(raw_path), "--batches-dir", str(batches_dir), "--batch-size", "2"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p1.returncode == 0
    assert (batches_dir / "batches_manifest.json").exists()

    # Write shard
    shard = [
        {"slide_number": 1, "title_fa": "اسلاید ۱", "bullets": ["نکته ۱"]},
        {
            "slide_number": 2,
            "title_fa": "اسلاید ۲",
            "bullets": [],
            "table_data": {"headers": ["A", "B"], "rows": [["1", "2"]]},
        },
    ]
    (batches_dir / "translated_batch_01_02.json").write_text(json.dumps(shard, ensure_ascii=False), encoding="utf-8")

    # 2. CLI merge-batches
    p2 = subprocess.run(
        [sys.executable, pipeline_script, "merge-batches", "--batches-dir", str(batches_dir), "--raw", str(raw_path), "--output", str(out_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p2.returncode == 0
    assert out_path.exists()

    # 3. CLI qa-check with PASSED report
    qa_report_path.write_text(
        json.dumps({"status": "PASSED", "total_slides_audited": 2, "table_slides_verified": [2], "defects": []}),
        encoding="utf-8",
    )
    p3 = subprocess.run(
        [
            sys.executable,
            pipeline_script,
            "qa-check",
            "--raw",
            str(raw_path),
            "--translated",
            str(out_path),
            "--batches-dir",
            str(batches_dir),
            "--qa-report",
            str(qa_report_path),
            "--require-report",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert p3.returncode == 0
