import pytest
from text_utils import clean_pamphlet_voice, prune_redundant_slide_reading
from verify_slide_alignment import check_slide_pair
from batch_orchestrator import _sanitize_slide_object, merge_slide_batches
import tempfile
import json
import os


def test_clean_pamphlet_voice_transforms_third_person_leads_to_direct_leads():
    """
    Audit Report Regression Test: Direct Pamphlet Voice Law
    Verifies that third-person reporting phrases ('استاد در تبیین...', 'استاد توضیح دادند...',
    'بر اساس توضیحات استاد...') are converted into direct, authoritative medical pamphlet voice
    with bold clinical leads, and that word count of 'استاد' drops to 0.
    """
    raw_lecture = (
        "استاد در تبیین میزان مصرف الکل و آستانه آسیب کبدی اشاره می‌کنند که مصرف مقادیر اندک در کوتاه‌مدت "
        "(حدود ۸۰ گرم در روز) با تغییرات چربی همراه است.\n\n"
        "استاد توضیح دادند که نسبت AST به ALT بالای ۲ نشانه اختصاصی هپاتیت الکلی است.\n\n"
        "بر اساس توضیحات استاد، ترانسفرین مانند اتوبوسی است که ظرفیت صندلی‌های آن را TIBC نشان می‌دهد."
    )
    cleaned = clean_pamphlet_voice(raw_lecture)
    
    assert "استاد" not in cleaned, f"Word 'استاد' must be completely eliminated, got: {cleaned}"
    assert "**میزان مصرف الکل و آستانه آسیب کبدی:**" in cleaned, "Topic must be converted to bold clinical lead"
    assert "نسبت AST به ALT بالای ۲ نشانه اختصاصی هپاتیت الکلی است." in cleaned
    assert "ترانسفرین مانند اتوبوسی است" in cleaned


def test_synthetic_table_inflation_gate_blocks_fabricated_tables():
    """
    Audit Report Regression Test: Table Authenticity Law
    Verifies that check_slide_pair flags SYNTHETIC_TABLE_INFLATION when a subagent
    converts a normal non-table slide into a synthetic table.
    """
    raw_slide = {
        "slide_number": 15,
        "title": "Alcohol Metabolism",
        "text_lines": ["Ethanol is metabolized by ADH into acetaldehyde."],
        "has_tables": False,
        "has_image_table": False,
        "tables": []
    }
    trans_slide = {
        "slide_number": 15,
        "title": "متابولیسم الکل",
        "bullets": ["اتانول توسط الکل دهیدروژناز به استالدهید تبدیل می‌شود."],
        "table_data": {
            "headers": ["مرحله", "آنزیم", "فرآورده"],
            "rows": [["۱", "ADH", "استالدهید"]]
        }
    }
    
    issues = check_slide_pair(raw_slide, trans_slide)
    synthetic_errors = [i for i in issues if i.get("type") == "SYNTHETIC_TABLE_INFLATION" or i.get("error_type") == "SYNTHETIC_TABLE_INFLATION"]
    assert len(synthetic_errors) > 0, f"Expected SYNTHETIC_TABLE_INFLATION for ungrounded table, got: {issues}"


def test_visual_schematic_series_slide_preserves_audio_commentary():
    """
    Audit Report Regression Test: Visual Slide Protocol
    Verifies that visual/schematic slides (without text bullets) preserve the professor's
    spoken explanation of the image/mechanism and are not silently suppressed to empty string.
    """
    visual_slide = {
        "slide_number": 52,
        "title": "Fat Droplets in Liver",
        "title_fa": "تفسیر میکروسکوپی دایره‌های سفید چربی",
        "bullets": [],
        "is_visual": True,
        "spoken_lecture": (
            "تفسیر میکروسکوپی دایره‌های سفید: حفره‌های گرد و شفاف در سیتوپلاسم هپاتوسیت‌ها، "
            "قطرات چربی هستند که حین مراحل آماده‌سازی بافت حل شده و به صورت فضاهای خالی باقی مانده‌اند."
        )
    }
    raw_slide = {
        "slide_number": 52,
        "title": "White circles in liver",
        "is_visual": True,
        "bullets": []
    }
    
    pruned = prune_redundant_slide_reading(visual_slide, raw_slide=raw_slide)
    assert pruned != "", "Visual slide explanation must NOT be suppressed to empty string"
    assert "تفسیر میکروسکوپی دایره‌های سفید:" in pruned


def test_sanitize_slide_object_applies_pamphlet_voice():
    """
    Verifies that _sanitize_slide_object automatically strips third-person reporting voice.
    """
    slide = {
        "slide_number": 20,
        "spoken_lecture": "استاد بیان کردند که شرب سنگین در یک نوبت آسیب حاد ایجاد می‌کند."
    }
    sanitized = _sanitize_slide_object(slide)
    assert "استاد" not in sanitized["spoken_lecture"]
    assert "شرب سنگین در یک نوبت آسیب حاد ایجاد می‌کند." in sanitized["spoken_lecture"]


def test_merge_slide_batches_auto_converts_synthetic_tables_to_bullets(tmp_path):
    """
    Verifies that merge_slide_batches detects unauthorized synthetic tables on slides
    without raw tables, and converts the rows into standard structured bullets.
    """
    batches_dir = tmp_path / "batches"
    batches_dir.mkdir()
    
    raw_slides = [
        {
            "slide_number": 1,
            "title": "Alcohol Effects",
            "text_lines": ["Binge drinking causes acute injury."],
            "has_tables": False,
            "has_image_table": False,
            "tables": []
        }
    ]
    raw_slides_path = tmp_path / "raw_slides.json"
    with open(raw_slides_path, "w", encoding="utf-8") as f:
        json.dump(raw_slides, f)
        
    manifest = {
        "schema_version": "5.8.0",
        "raw_slides_source": str(raw_slides_path),
        "total_slides": 1,
        "batch_size": 1,
        "halo_size": 0,
        "total_batches": 1,
        "batches": [
            {
                "batch_id": "batch_001",
                "start_slide": 1,
                "end_slide": 1,
                "slide_count": 1,
                "expected_slide_numbers": [1],
                "output_shard_file": str(batches_dir / "batch_001.translated.json")
            }
        ]
    }
    manifest_path = batches_dir / "batches_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)
        
    batch_trans = {
        "batch_id": "batch_001",
        "slides": [
            {
                "slide_number": 1,
                "title_fa": "اثرات الکل",
                "bullets": ["مصرف سنگین موجب آسیب حاد می‌گردد."],
                "table_data": {
                    "headers": ["نوع", "عارضه"],
                    "rows": [["حاد", "هپاتیت برق‌آسا"]]
                }
            }
        ]
    }
    with open(batches_dir / "batch_001.translated.json", "w", encoding="utf-8") as f:
        json.dump(batch_trans, f)
        
    out_file = tmp_path / "translated_slides.json"
    report = merge_slide_batches(
        batches_dir=str(batches_dir),
        raw_slides_path=str(raw_slides_path),
        output_path=str(out_file)
    )
    
    with open(out_file, "r", encoding="utf-8") as f:
        merged = json.load(f)
        
    # Slide 1 must NOT have table_data because raw slide had no table!
    s1 = merged[0]
    assert "table_data" not in s1, "Synthetic table_data MUST be stripped"
    assert any("هپاتیت برق‌آسا" in b for b in s1["bullets"]), "Table row must be converted to bullet"
