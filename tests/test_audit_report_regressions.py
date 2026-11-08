import pytest
from text_utils import clean_pamphlet_voice, prune_redundant_slide_reading
from verify_slide_alignment import check_slide_pair
from verify_lecture_alignment import check_redundant_slide_spoken_overlap
from batch_orchestrator import _sanitize_slide_object, merge_slide_batches
import tempfile
import json
import os


def test_clean_pamphlet_voice_transforms_third_person_leads_to_direct_leads():
    """
    Audit Report Regression Test: Direct Pamphlet Voice Law
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


def test_subtractive_synthesis_prunes_paraphrased_bullet_definitions():
    """
    Subtractive Synthesis Report Case 1 (Slide 2):
    Verifies that prune_redundant_slide_reading prunes paraphrased definitions
    where the core clinical concept is already listed in slide bullets,
    even when written in elevated literary Persian or with numbered leads.
    """
    slide2 = {
        "slide_number": 2,
        "title_fa": "دیسفاژی انتقالی و فاگوفوبیا",
        "bullets": [
            {
                "lead": "دیسفاژی انتقالی (Transfer Dysphagia):",
                "text": "اغلب به پس‌زدن مواد از بینی و آسپیراسیون ریوی حین بلع منجر می‌شود و ویژگی بارز دیسفاژی اوروفارنژیال است."
            },
            {
                "lead": "فاگوفوبیا (Phagophobia):",
                "text": "ترس از بلع و امتناع از بلعیدن ممکن است منشأ سایکوژنیک داشته باشد یا به اضطراب پیش‌بینانه ناشی از انسداد با لقمه غذا، اودینوفاژی یا آسپیراسیون مربوط باشد."
            }
        ],
        "spoken_lecture": (
            "۱. دیسفاژی انتقالی: به اختلال در فاز دهانی-حلقی (اوروفارنژیال) اطلاق می‌شود که در آن بیمار در انتقال لقمه غذا ناتوان است. این حالت معمولاً با پس‌زدن مایعات از بینی و آسپیراسیون ریوی تظاهر پیدا می‌کند.\n\n"
            "۲. فاگوفوبیا (Phagophobia): ترس شدید و امتناع از بلع غذا است که ممکن است ریشه سایکوژنیک داشته باشد یا به دنبال یک تجربه تروماتیک پیشین نظیر گیر کردن دردناک لقمه غذا ایجاد شود.\n\n"
            "🚨 نکته بالینی مهم: در بیمار مشکوک به دیسفاژی انتقالی، بررسی بلع با باریم ویدئوفلوروسکوپی (MBS) خط اول ارزیابی است."
        )
    }

    pruned = prune_redundant_slide_reading(slide2)
    assert "🚨 نکته بالینی مهم:" in pruned, "Unique off-slide clinical pearl MUST be preserved"
    assert "باریم ویدئوفلوروسکوپی" in pruned, "Unique diagnostic procedure MUST be preserved"
    assert "۱. دیسفاژی انتقالی: به اختلال در فاز دهانی-حلقی" not in pruned, "Paraphrased definition of Transfer Dysphagia MUST be pruned"
    assert "۲. فاگوفوبیا (Phagophobia): ترس شدید" not in pruned, "Paraphrased definition of Phagophobia MUST be pruned"


def test_subtractive_synthesis_silent_suppression_on_full_slide_paraphrase():
    """
    Subtractive Synthesis Report Case 2 (Slide 3):
    Verifies that when 100% of spoken commentary merely paraphrases the 3 swallowing phases
    on the slide without adding novel clinical facts or pearls, the entire spoken_lecture is
    pruned to empty string ("") for Silent Suppression.
    """
    slide3 = {
        "slide_number": 3,
        "title_fa": "مراحل سه‌گانه بلع",
        "bullets": [
            {"lead": "فاز دهانی (Oral phase):", "text": "مرحله ارادی بلع"},
            {"lead": "فاز حلقی (Pharyngeal phase):", "text": "مرحله غیرارادی بلع"},
            {"lead": "فاز مروی (Esophageal phase):", "text": "مرحله غیرارادی بلع"}
        ],
        "spoken_lecture": (
            "کنترل ارادی منحصراً به فاز دهانی محدود می‌شود. انتقال به فاز غیرارادی به محض عبور لقمه غذا "
            "از قوس‌های کامی قدامی آغاز شده و فازهای حلقی و مروی به طور کاملاً غیرارادی و بازتابی اداره می‌گردند."
        )
    }

    pruned = prune_redundant_slide_reading(slide3)
    assert pruned == "", f"Expected empty string (Silent Suppression) for full paraphrase, got: {pruned!r}"


def test_redundant_slide_spoken_overlap_gate_detects_unpruned_paraphrase():
    """
    Subtractive Synthesis Report Pillar 3 Gate:
    Verifies that check_redundant_slide_spoken_overlap flags REDUNDANT_SLIDE_SPOKEN_OVERLAP
    when a slide has non-empty spoken_lecture that merely re-explains slide bullets with 0 novel facts.
    """
    slide = {
        "slide_number": 6,
        "title_fa": "فاز حلقی بلع",
        "bullets": [
            {"lead": "بسته شدن نازوفارنکس:", "text": "جلوگیری از پس‌زدن مواد به بینی"},
            {"lead": "بسته شدن حنجره:", "text": "محافظت از مجاری تنفسی در برابر آسپیراسیون"},
            {"lead": "باز شدن اسفنکتر فوقانی مری (UES):", "text": "ورود لقمه به مری"}
        ],
        "spoken_lecture": (
            "۱. بسته شدن نازوفارنکس: مانع از برگشت مواد به بینی می‌شود.\n\n"
            "۲. بسته شدن حنجره: از ورود محتویات غذا به راه هوایی و آسپیراسیون جلوگیری می‌کند.\n\n"
            "۳. باز شدن UES: امکان انتقال لقمه به داخل مری را فراهم می‌سازد."
        )
    }
    issue = check_redundant_slide_spoken_overlap(slide)
    assert issue is not None, "Expected REDUNDANT_SLIDE_SPOKEN_OVERLAP warning/error"
    assert issue.get("type") == "REDUNDANT_SLIDE_SPOKEN_OVERLAP"
