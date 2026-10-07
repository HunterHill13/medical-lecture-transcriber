#!/usr/bin/env python3
"""
text_utils.py: Centralized Text Normalization, Tokenization, and Time Utilities.
Provides single-source-of-truth normalization for Persian/Arabic text,
medical token extraction, timestamp conversion with full Arabic/Persian digit support,
and ceremonial slide detection.
"""

import re
from typing import Set, Union, List, Optional

# Pre-compiled digit translation tables
COMBINED_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ARABIC_DIGITS = COMBINED_DIGITS
PERSIAN_DIGITS = COMBINED_DIGITS

# Character replacements for display normalization (preserves correct Persian spelling and orthography)
DISPLAY_CHAR_REPLACEMENTS = {
    'ك': 'ک',
    'ي': 'ی',
    'ة': 'ه',
    '\u200c': ' ',  # Zero-width non-joiner
    '\u200b': '',   # Zero-width space
}

# Character replacements for matching / lexical comparison
MATCHING_CHAR_REPLACEMENTS = {
    'ك': 'ک',
    'ي': 'ی',
    'ة': 'ه',
    'أ': 'ا',
    'إ': 'ا',
    'آ': 'ا',
    'ؤ': 'و',
    'ئ': 'ی',
    '\u200c': ' ',
    '\u200b': '',
}

CHAR_REPLACEMENTS = MATCHING_CHAR_REPLACEMENTS

STOPWORDS = {
    # English stopwords
    "the", "and", "for", "with", "from", "that", "this", "are", "type", "page",
    "slide", "their", "have", "each", "also", "been", "into", "over", "such",
    "by", "of", "in", "to", "at", "an", "a", "or", "as", "is", "it", "its", "on", "was", "be",
    # Persian standard stopwords
    "این", "است", "های", "برای", "که", "شد", "می", "در", "با", "از", "تا", "به", "یک",
    "رو", "هم", "دارد", "دارند", "کنند", "شود", "و", "یا", "بود", "بوده", "گفتیم", "کرد",
    "کند", "شده", "باشد", "باشند", "باید", "شما", "ببینید", "خیلی", "یعنی", "اینجا", "آنها",
    "اسلاید", "صفحه", "مبحث", "درس", "جلسه", "دکتر", "استاد",
    # Persian conversational stopwords & verbal auxiliaries
    "بشه", "باشه", "بره", "برم", "بشن", "باشن", "بودن", "بشیم", "باشیم", "باشید",
    "بکنم", "بکنن", "بکنه", "بکنید", "بکنیم", "بگردید", "بیاد", "بیارید", "بیاین",
    "اینو", "اون", "اونا", "اینا", "اینم", "اینایی", "انها", "اینها",
    "میشه", "میشن", "میکنن", "میکنم", "میکنیم", "میکنه", "میکشن", "میریم", "میاد", "میره",
    "اصطلاح", "اصلا", "اصولا", "البته", "افتاده", "اومده", "اورده", "اوردید", "اولش", "بعدش", "بعدا", "بعدی", "بقیه",
    "باهاش", "بهش", "بهتون", "بهشون", "بهتره",
    "بتونن", "بتونید", "بتونیم", "بتونه",
    "بدونید", "بخونید", "بدیم", "بذاره", "بذاریم", "بذارید",
    "هست", "هستش", "هستن", "نیست", "نیستن", "نیستش", "چیز", "چیزی",
    "طوری", "ترتیب", "موقع", "داره", "دارم", "داریم", "طریق", "مربوط", "مربوطه", "سایر", "مابقی",
    "همین", "همون", "همینطور", "دوباره", "تقریبا", "مثلا", "حالا", "کلا", "اپروچش", "اپروچ", "بالاست", "بالایی",
    "بیمارتون", "توی", "تونید", "بیس", "بگم", "خوام", "دربیاریم", "دیدید", "دونیم", "فرستنش", "قضیه", "هاست",
    "دادم", "دادید", "دارن", "ندارن", "داشتن", "دیدن", "دیدم", "دیدند", "دیگه", "راحت", "رسیم", "رسیدیم",
    "رشته", "رفته", "رفتید", "روتین", "رید", "سازشون", "شرایط", "شون", "صحبت", "طور", "عملا", "عین", "غلطی",
    "غیره", "فقط", "قبل", "قدم", "قسمتی", "لازم", "لحاظ", "لیست", "مثل", "مسیری", "مشخص", "مشکل", "معاینات",
    "مقدمات", "ممکنه", "منشاش", "مهمه", "مواردی", "نام", "نداریم", "نرمال", "نهایت", "نوعی", "نگه", "هایی",
    "هستیم", "همدیگه", "همه", "وقتی", "ولی", "چرا", "چون", "کار", "کامل", "کاملی", "کرات", "کردید", "کنار",
    "کنم", "کنه", "کنید", "کنیم", "گرفتید", "گفتم", "گونه", "گیری", "تمام", "انواع", "اقسام", "خاصی", "حالی",
    "حالتی", "حتما", "حفظ", "خسته", "خصوصیتی", "خوب", "بیشترین", "دستوری", "دچار", "دیدیم", "تصمیم", "تقسیم",
    "اتفاق", "ایا", "اینکه", "باز", "بعد", "بین", "دست", "سال", "سراغ", "زندگی", "زیاد", "زیادی",
    "ارگانش", "ازمایشات", "استاندارد", "اسلایدها"
}

def normalize_for_display(text: str) -> str:
    """
    Normalizes Persian text for publication display:
    - Normalizes basic character encodings (ك -> ک, ي -> ی, ة -> ه)
    - STRICTLY PRESERVES correct orthography (does NOT alter 'آ' or 'ئ')
    - STRICTLY PRESERVES scientific notation, arrows (→, ⇌, <->), chemical formulas,
      Greek letters (α, β, γ), sub/superscripts (Ca²⁺, HCO₃⁻), inequalities, and punctuation.
    """
    if not text:
        return ""
    for src, dst in DISPLAY_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    # Strip diacritics / tashkeel / harakat
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # Collapse redundant consecutive whitespaces
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def normalize_for_matching(text: str) -> str:
    """
    Normalizes text for alignment matching and lexical recall:
    - Lowercases English tokens
    - Unifies Arabic/Persian letter variants (آ -> ا, ئ -> ی, etc.)
    - Normalizes digits via COMBINED_DIGITS
    - Strips tashkeel
    - Isolates punctuation while PRESERVING intra-word hyphens in medical compounds (IGFBP-3, TNF-α)
      and scientific notations (Ca²⁺, HCO₃⁻).
    """
    if not text:
        return ""
    for src, dst in MATCHING_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = text.translate(COMBINED_DIGITS)
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # Isolate standalone punctuation without breaking intra-word hyphens in medical compounds
    # Replace Persian & general punctuation except hyphens/slashes within alphanumeric compounds
    text = re.sub(r'[\u060C\u061B\u061F\u0640,\.;:!?()\[\]{}"\'«»—]', ' ', text)
    # Replace standalone hyphens (surrounded by space) while keeping word-internal hyphens
    text = re.sub(r'(?<=\s)-(?=\s)|^-(?=\s)|(?<=\s)-$', ' ', text)
    return text

def normalize_persian_text(text: str) -> str:
    """Standard normalization function (backward-compatible alias to normalize_for_matching)."""
    return normalize_for_matching(text)

# Comprehensive Bilingual Medical Concept Dictionary (English <-> Persian)
BILINGUAL_MEDICAL_CONCEPTS = {
    # Endocrine & Metabolism
    "hyperthyroidism": {"پرکاری", "تیروئید", "هایپرتیروئیدی", "هیپرتیروئیدی"},
    "hypothyroidism": {"کم‌کاری", "تیروئید", "هایپوتیروئیدی", "هیپوتیروئیدی"},
    "thyroid": {"تیروئید", "تیروئیدی"},
    "parathyroid": {"پاراتیروئید", "پاراتیروئیدی"},
    "gland": {"غده", "غدد"},
    "hormone": {"هورمون", "هورمونها", "هورمونهای", "هورمونی"},
    "hormones": {"هورمون", "هورمونها", "هورمونهای", "هورمونی"},
    "synthesis": {"سنتز", "ساخت", "تولید"},
    "secretion": {"ترشح", "ترشحی", "افراز"},
    "inhibition": {"مهار", "بازداری", "مهارکننده"},
    "stimulation": {"تحریک", "برانگیختگی"},
    "regulation": {"تنظیم", "کنترل"},
    "feedback": {"فیدبک", "پسخورد", "بازخورد"},
    "calcium": {"کلسیم"},
    "calcitriol": {"کلسی‌تریول", "کلسیتریول"},
    "phosphorus": {"فسفر"},
    "phosphate": {"فسفات"},
    "glucose": {"گلوکز", "قند"},
    "diabetes": {"دیابت", "قند"},
    "mellitus": {"ملیتوس", "شیرین"},
    "insulin": {"انسولین"},
    "glucagon": {"گلوکاگون"},
    "cortisol": {"کورتیزول"},
    "adrenal": {"آدرنال", "فوق‌کلیه", "فوق‌کلیوی"},
    "pituitary": {"هیپوفیز", "پیتویتری"},
    "hypothalamus": {"هیپوتالاموس"},
    "ulcer": {"زخم"},
    "wagner": {"واگنر"},
    "walker": {"واکر", "بریس"},
    "pneumatic": {"بادی", "پنوماتیک"},
    "aircast": {"ایرکست", "واکر", "بریس"},
    "microvascular": {"میکروواسکولار", "عروق", "ریز"},
    "macrovascular": {"ماکروواسکولار", "عروق", "بزرگ"},
    "glycemic": {"قند", "گلیسمیک", "گلایسمیک", "گلوکز"},
    "statin": {"استاتین"},

    # Cardiovascular
    "hypertension": {"پرفشاری", "فشارخون", "هایپرتانسیون", "هیپرتانسیون", "فشار"},
    "hypotension": {"کاهش", "افت", "فشارخون", "هیپوتانسیون"},
    "cardiovascular": {"قلبی", "عروقی"},
    "cardiac": {"قلب", "قلبی"},
    "heart": {"قلب", "قلبی"},
    "myocardial": {"میوکارد", "میوکاردیال", "قلبی"},
    "infarction": {"انفارکتوس", "سکته"},
    "ischemia": {"ایسکمی", "کاهش", "خونرسانی"},
    "angina": {"آنژین", "درد"},
    "atherosclerosis": {"آترواسکلروز", "آترواسکلروتیک", "تصلب", "شرایین"},
    "cholesterol": {"کلسترول", "چربی"},
    "dyslipidemia": {"دیس‌لیپیدمی", "دیسلیپیدمی", "چربی"},
    "lipid": {"لیپید", "چربی"},
    "lipids": {"لیپیدها", "چربی‌ها", "چربی"},
    "statin": {"استاتین", "استاتین‌ها"},
    "statins": {"استاتین", "استاتین‌ها"},
    "artery": {"شریان", "سرخرگ"},
    "arteries": {"شریان‌ها", "سرخرگ‌ها"},
    "arterial": {"شریانی"},
    "vein": {"ورید", "سیاهرگ"},
    "veins": {"وریدها", "سیاهرگ‌ها"},
    "venous": {"وریدی"},
    "vascular": {"عروق", "عروقی", "رگ"},
    "vessels": {"عروق", "رگ‌ها"},
    "vessel": {"رگ", "عروق"},
    "blood": {"خون", "خونی"},
    "pressure": {"فشار"},
    "systolic": {"سیستولیک", "سیستول"},
    "diastolic": {"دیاستولیک", "دیاستول"},
    "tachycardia": {"تاکی‌کاردی", "تندتپشی", "تپش"},
    "bradycardia": {"برادی‌کاردی", "کندتپشی"},
    "arrhythmia": {"آریتمی", "بی‌نظمی"},
    "thrombosis": {"ترومبوز", "لخته"},
    "thrombus": {"ترومبوز", "لخته"},
    "embolism": {"آمبولی"},
    "embolus": {"آمبولی"},
    "stroke": {"سکته", "مغزی"},

    # Renal & Urinary
    "renal": {"کلیه", "کلیوی", "رنال"},
    "kidney": {"کلیه", "کلیوی"},
    "kidneys": {"کلیه‌ها", "کلیوی"},
    "nephrotic": {"نفروتیک"},
    "nephritic": {"نفریتیک"},
    "glomerulus": {"گلومرول"},
    "glomerular": {"گلومرولی", "گلومرولار"},
    "tubule": {"توبول", "لوله‌چه"},
    "tubular": {"توبولار", "توبولی"},
    "podocyte": {"پودوسیت"},
    "proteinuria": {"پروتئینوری", "دفع", "پروتئین"},
    "hematuria": {"هماچوری", "خون", "ادرار"},
    "hypoalbuminemia": {"هیپوآلبومینمی", "کاهش", "آلبومین"},
    "hyperlipidemia": {"هیپرلیپیدمی", "چربی", "بالا"},
    "creatinine": {"کراتینین"},
    "filtration": {"فیلتراسیون", "تصفیه"},
    "reabsorption": {"بازتجذب"},
    "excretion": {"دفع"},
    "urine": {"ادرار", "ادراری"},
    "urinary": {"ادرار", "ادراری"},
    "dialysis": {"دیالیز"},

    # Pulmonary
    "pulmonary": {"ریه", "ریوی", "پولمونری"},
    "lung": {"ریه", "ریوی"},
    "lungs": {"ریه‌ها", "ریوی"},
    "respiratory": {"تنفسی", "تنفس"},
    "dyspnea": {"تنگی", "نفس", "دیسپنه"},
    "cough": {"سرفه"},
    "hypoxia": {"هیپوکسی", "کاهش", "اکسیژن"},
    "pneumonia": {"پنومونی", "ذات‌الریه", "عفونت"},
    "asthma": {"آسم"},
    "bronchial": {"برونش", "نایژه‌ای"},

    # Gastrointestinal & Hepatic
    "hepatic": {"کبد", "کبدی", "هپاتیک"},
    "liver": {"کبد", "کبدی"},
    "cirrhosis": {"سیروز"},
    "hepatitis": {"هپاتیت", "التهاب", "کبد"},
    "jaundice": {"یرقان", "زردی"},
    "biliary": {"صفراوی", "صفرا"},
    "bile": {"صفرا"},
    "gastric": {"معده", "معدی"},
    "stomach": {"معده"},
    "ulcer": {"زخم"},
    "intestinal": {"روده‌ای", "روده"},
    "bowel": {"روده"},
    "colon": {"کولون", "روده"},
    "pancreas": {"پانکراس", "لوزالمعده"},
    "pancreatitis": {"پانکراتیت"},

    # Pathology & Clinical Oncology
    "etiology": {"اتیولوژی", "علت", "سبب‌شناسی"},
    "pathogenesis": {"پاتوژنز", "بیماری‌زایی"},
    "pathophysiology": {"پاتوفیزیولوژی"},
    "pathology": {"پاتولوژی", "آسیب‌شناسی"},
    "diagnosis": {"تشخیص", "تشخیصی"},
    "treatment": {"درمان", "درمانی"},
    "therapy": {"درمان", "درمانی", "تراپی"},
    "management": {"مدیریت", "اداره"},
    "prognosis": {"پیش‌آگهی", "پروگنوز"},
    "prevention": {"پیشگیری"},
    "complication": {"عوارض", "پیامد"},
    "complications": {"عوارض", "پیامدها"},
    "symptom": {"علامت", "نشانه"},
    "symptoms": {"علائم", "نشانه‌ها"},
    "sign": {"نشانه", "علامت"},
    "signs": {"نشانه‌ها", "علائم"},
    "manifestation": {"تظاهر", "علامت"},
    "manifestations": {"تظاهرات", "علائم", "نشانه‌ها"},
    "acute": {"حاد"},
    "chronic": {"مزمن"},
    "primary": {"اولیه"},
    "secondary": {"ثانویه"},
    "benign": {"خوش‌خیم"},
    "malignant": {"بدخیم"},
    "carcinoma": {"کارسینوما", "سرطان"},
    "adenoma": {"آدنوم", "تومور"},
    "tumor": {"تومور", "توده"},
    "tumors": {"تومورها", "توده‌ها"},
    "cancer": {"سرطان"},
    "mass": {"توده", "ماس"},
    "nodule": {"ندول", "گرهک"},
    "nodules": {"ندول‌ها", "گرهک‌ها"},
    "lesion": {"ضایعه"},
    "lesions": {"ضایعات"},
    "hyperplasia": {"هیپرپلازی", "هایپرپلازی"},
    "hypertrophy": {"هیپرتروفی"},
    "atrophy": {"آتروفی", "تحلیل"},
    "necrosis": {"نکروز", "بافت‌مردگی"},
    "apoptosis": {"آپوپتوز", "مرگ"},
    "inflammation": {"التهاب", "التهابی"},
    "inflammatory": {"التهابی"},
    "infection": {"عفونت", "عفونی"},
    "infectious": {"عفونی"},
    "fever": {"تب"},
    "pain": {"درد"},
    "edema": {"ادم", "ورم"},
    "fatigue": {"خستگی"},
    "weakness": {"ضعف"},
    "loss": {"کاهش", "ازدست‌دادن"},
    "gain": {"افزایش", "اضافه"},
    "weight": {"وزن"},

    # Pharmacology & Clinical Methodology
    "monotherapy": {"تک‌دارویی", "مونوتراپی"},
    "combination": {"ترکیبی", "ترکیب"},
    "dosage": {"دوز", "مقدار", "دوزاژ"},
    "dose": {"دوز", "مقدار"},
    "daily": {"روزانه", "روزی"},
    "target": {"هدف", "تارگت"},
    "reduction": {"کاهش", "افت"},
    "increase": {"افزایش", "بالا"},
    "increased": {"افزایش", "بالا", "افزایش‌یافته"},
    "decrease": {"کاهش", "پایین"},
    "decreased": {"کاهش", "پایین", "کاهش‌یافته"},
    "associated": {"همراه", "مرتبط"},
    "receptor": {"گیرنده", "رسپتور"},
    "receptors": {"گیرنده‌ها", "رسپتورها"},
    "inhibitor": {"مهارکننده"},
    "inhibitors": {"مهارکننده‌ها"},
    "agonist": {"آگونیست"},
    "agonists": {"آگونیست‌ها"},
    "antagonist": {"آنتاگونیست"},
    "antagonists": {"آنتاگونیست‌ها"},
    "first-line": {"خط", "اول", "اولیه"},
    "second-line": {"خط", "دوم"},
    "initial": {"اولیه", "شروع"},
    "drug": {"دارو", "دارویی"},
    "drugs": {"داروها", "دارویی"},
    "medication": {"دارو", "داروها"},
    "medications": {"داروها", "دارو"},
    "adults": {"بالغین", "بزرگسالان", "افراد"},
    "older": {"مسن‌تر", "بالاتر", "بزرگتر"},
    "years": {"سال", "ساله"},
    "lifestyle": {"سبک", "زندگی"},
    "guideline": {"راهنما", "گایدلاین"},
    "guidelines": {"راهنماها", "گایدلاین"},
    "criteria": {"معیار", "معیارها", "کرایتیریا"},
    "screening": {"غربالگری"},
    "biopsy": {"بیوپسی", "نمونه‌برداری"},
    "surgery": {"جراحی"},
    "surgical": {"جراحی"},
    "resection": {"رزکسیون", "برداشتن"},
    "patient": {"بیمار"},
    "patients": {"بیماران", "بیمار"},
    "risk": {"خطر", "ریسک"},
    "factor": {"عامل", "فاکتور"},
    "factors": {"عوامل", "فاکتورها"},
    "mechanism": {"مکانیسم", "سازوکار"},
    "pathway": {"مسیر", "پات‌وی"},
    "resistance": {"مقاومت"},
    "sensitivity": {"حساسیت"},
    "level": {"سطح", "میزان"},
    "levels": {"سطوح", "میزان‌ها", "مقادیر"},
    "high": {"بالا", "شدید", "پرتوان"},
    "intensity": {"شدت", "پرتوان", "توان"},
    "low": {"پایین", "کم"},
    "moderate": {"متوسط"},
    "severe": {"شدید"},
    "mild": {"خفیف"},
    "goiter": {"گواتر"},
    "tremor": {"لرزش", "ترمور"},
    "tremors": {"لرزش", "ترمور"},
    "follicular": {"فولیکولار", "فولیکولی"},
    "follicle": {"فولیکول"},
    "cell": {"سلول", "سلولها", "سلولی"},
    "cells": {"سلول", "سلولها", "سلولی", "سلولهای"},
    "antibody": {"آنتی بادی", "پادتن"},
    "antibodies": {"آنتی بادی", "پادتن", "پادتنها"},
    "clinical": {"بالینی"},
    "manifestation": {"تظاهر", "تظاهرات", "علامت"},
    "manifestations": {"تظاهر", "تظاهرات", "علامت"},
    "dysfunction": {"اختلال", "نارسایی", "دیسفانکشن"},
    "excess": {"افزایش", "مازاد", "بیش از حد"},
    "increase": {"افزایش", "بالا رفتن"},
    "increased": {"افزایش یافته", "افزایش"},
    "decrease": {"کاهش", "پایین امدن"},
    "decreased": {"کاهش یافته", "کاهش"}
}

# Persian Clinical Pharmacology & Intervention Keywords
PERSIAN_PHARMA_INTERVENTIONS = {
    "متیمازول": "methimazole",
    "پروپیل‌تیواوراسیل": "propylthiouracil",
    "لووتیروکسین": "levothyroxine",
    "پروپرانولول": "propranolol",
    "آتنولول": "atenolol",
    "متوپرولول": "metoprolol",
    "متفورمین": "metformin",
    "گلی‌بن‌کلامید": "glibenclamide",
    "آسپرین": "aspirin",
    "کلوپیدوگرل": "clopidogrel",
    "هپارین": "heparin",
    "وارفارین": "warfarin",
    "ریواروکسابان": "rivaroxaban",
    "آپیکسابان": "apixaban",
    "کاپتوپریل": "captopril",
    "انالاپریل": "enalapril",
    "لوزارتان": "losartan",
    "والسارتان": "valsartan",
    "آملودیپین": "amlodipine",
    "دیلتیازم": "diltiazem",
    "وراپامیل": "verapamil",
    "هیدروکلروتیازید": "hydrochlorothiazide",
    "فوروزماید": "furosemide",
    "اسپیرونولاکتون": "spironolactone",
    "آتورواستاتین": "atorvastatin",
    "روزوواستاتین": "rosuvastatin",
    "سیمواستاتین": "simvastatin",
    "دگزامتازون": "dexamethasone",
    "پردنیزولون": "prednisolone",
    "هیدروکورتیزون": "hydrocortisone",
    "امپرازول": "omeprazole",
    "پانتوپرازول": "pantoprazole",
    "سفتریاکسون": "ceftriaxone",
    "وانکومایسین": "vancomycin",
    "مروپنم": "meropenem",
    "آزیترومایسین": "azithromycin",
    "سیپروفلوکساسین": "ciprofloxacin",
    "تیروئیدکتومی": "thyroidectomy",
    "پاراتیروئیدکتومی": "parathyroidectomy",
}


def parse_time_to_seconds(time_str: str) -> Optional[int]:
    """
    Parses MM:SS or HH:MM:SS into seconds, normalizing both Arabic and Persian digits.
    Enforces valid clock ranges:
    - 2 parts (MM:SS): seconds must be in range 0..59
    - 3 parts (HH:MM:SS): minutes and seconds must be in range 0..59
    Returns None if timestamp contains invalid range values (e.g. 12:99, 99:99).
    """
    if not time_str:
        return None
    time_str = str(time_str).strip()
    time_str = time_str.translate(COMBINED_DIGITS)
    
    m = re.search(r'(\d+):(\d+)(?::(\d+))?', time_str)
    if not m:
        return None
    parts = [int(p) for p in m.groups() if p is not None]
    if len(parts) == 2:
        minutes, seconds = parts[0], parts[1]
        if seconds >= 60:
            return None
        return minutes * 60 + seconds
    elif len(parts) == 3:
        hours, minutes, seconds = parts[0], parts[1], parts[2]
        if hours >= 24 or minutes >= 60 or seconds >= 60:
            return None
        return hours * 3600 + minutes * 60 + seconds
    return None


def format_seconds_to_time(seconds: int) -> str:
    """Formats seconds into MM:SS or HH:MM:SS."""
    if seconds is None:
        return "00:00"
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def flatten_spoken_lecture(val: Union[str, List[object], None]) -> str:
    """Safely flattens spoken_lecture whether it is stored as a str, list[str], or None."""
    if not val:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, (list, tuple)):
        return " ".join(str(x).strip() for x in val if x)
    return str(val)

def extract_timestamps(text: str) -> List[int]:
    """Extracts all timestamps (MM:SS or HH:MM:SS) from text in seconds, normalizing Persian/Arabic digits."""
    if not text:
        return []
    norm = text.translate(COMBINED_DIGITS)
    raw_matches = re.findall(r'(\d{1,2}:\d{2}(?::\d{2})?)', norm)
    secs = []
    for m in raw_matches:
        s = parse_time_to_seconds(m)
        if s is not None:
            secs.append(s)
    return secs

def extract_tokens(text_or_lines: Union[str, List[str]], max_stem_len: Optional[int] = None) -> Set[str]:
    """
    Extracts medical tokens, clinical terms, dosages, formulas, and acronyms.
    Features specialized preservation for:
    - Hyphenated/slashed compounds: IGFBP-3, TNF-α, IL-6, T3/T4, Na+/K+, Gs-α
    - Chemical formulas and ion notations: Ca²⁺, Na⁺, HCO₃⁻, H₂CO₃, CO2
    - Clinical measurements, percentages, dosages: 7%, 10%, 25mg, 120mmHg
    - Persian clinical words >= 3 chars

    Stem length parameter `max_stem_len`:
    Default is None (unabridged full tokens). In medical terminology processing, unabridged
    tokens are strictly necessary to prevent catastrophic prefix collisions (e.g. 'hypo-' vs 'hyper-',
    'hypocalcemia' vs 'hypercalcemia', 'hypoglycemia' vs 'hyperglycemia'). Callers may explicitly
    provide max_stem_len only when intentionally bounding token length for fuzzy index hashing.
    """
    if isinstance(text_or_lines, str):
        lines = [text_or_lines]
    elif isinstance(text_or_lines, (list, tuple, set)):
        lines = list(text_or_lines)
    else:
        lines = [str(text_or_lines)]

    tokens = set()
    for line in lines:
        if not line:
            continue
        line_norm = normalize_for_matching(str(line))
        
        # 1. Specialized Medical Compounds (hyphenated, slashed, or dotted acronyms/chemicals)
        # Matches: IGFBP-3, TNF-α, IL-6, T3/T4, Gs-α, etc.
        compounds = re.findall(r'(?:(?<=[\s\(\[\{,\.;:!?])|^)[A-Za-z0-9α-ωΑ-Ω²³⁺⁻₀-₉]+(?:[-/][A-Za-z0-9α-ωΑ-Ω²³⁺⁻₀-₉]+)+(?=(?:[\s\(\[\{,\.;:!?\)\]\}]|$))', line_norm)
        for comp in compounds:
            cl = comp.lower()
            if cl not in STOPWORDS:
                tokens.add(cl)
                
        # 2. Medical acronyms, receptor notations, and chemical ion formulas
        # Matches: Ca²⁺, Na⁺, HCO₃⁻, T3, T4, PTH, GH, CrCl, D2, β1, etc.
        chem_ions = re.findall(r'(?:(?<=[\s\(\[\{,\.;:!?])|^)[A-Za-zα-ωΑ-Ω][A-Za-z0-9α-ωΑ-Ω²³⁺⁻₀-₉]{1,}(?=(?:[\s\(\[\{,\.;:!?\)\]\}]|$))', line_norm)
        for ci in chem_ions:
            cil = ci.lower()
            if cil not in STOPWORDS and not cil.isdigit():
                tok = cil[:max_stem_len] if max_stem_len else cil
                tokens.add(tok)

        # 3. Clinical measurements, percentages, and dosages
        # Matches: 7%, 10%, 25mg, 120mmHg, 5ug, etc.
        dosages = re.findall(r'(?:(?<=[\s\(\[\{,\.;:!?])|^)\d+(?:\.\d+)?(?:%|mg|mcg|μg|g|kg|ml|l|mmhg|mmol|meq|iu|u|bpm)(?=(?:[\s\(\[\{,\.;:!?\)\]\}]|$))', line_norm)
        for ds in dosages:
            tokens.add(ds.lower())

        # 4. Persian clinical and general words of length >= 3
        fa_words = re.findall(r'[\u0600-\u06FF]{3,}', line_norm)
        for w in fa_words:
            if w not in STOPWORDS:
                tokens.add(w)
                
    return tokens

# Populate normalized forms of Persian pharma interventions
_norm_pharma = {}
for fa_drug, en_drug in PERSIAN_PHARMA_INTERVENTIONS.items():
    _norm_pharma[fa_drug] = en_drug
    for t in extract_tokens([fa_drug]):
        _norm_pharma[t] = en_drug
PERSIAN_PHARMA_INTERVENTIONS.update(_norm_pharma)

# Generic Persian words that CANNOT by themselves count as sufficient evidence for medical concepts
GENERIC_PERSIAN_WORDS = {
    "کاهش", "افزایش", "فشار", "قلب", "کبد", "تیروئید", "کلیه", "معده", "ریه",
    "خون", "مغز", "بالا", "پایین", "زیاد", "کم", "درد", "بیماری", "بیمار",
    "سطح", "سطوح", "میزان", "علامت", "عامل", "خطر", "شدید", "خفیف", "متوسط"
}

# Pre-normalized tokens for generic Persian words to guarantee bulletproof filtering across orthographic variants
NORMALIZED_GENERIC_PERSIAN_WORDS = {
    t for w in GENERIC_PERSIAN_WORDS for t in extract_tokens([w])
}

# Multi-word Concept Phrases for concepts requiring multi-word grounding
BILINGUAL_CONCEPT_PHRASES = {
    # Weight
    ("weight", "loss"): ["کاهش وزن", "افت وزن", "لاغری"],
    ("weight", "gain"): ["افزایش وزن", "چاقی"],
    # Thyroid
    ("hyperthyroidism",): ["پرکاری تیروئید", "هیپرتیروئیدی", "تیروتوکسیکوز"],
    ("hypothyroidism",): ["کم کاری تیروئید", "هیپوتیروئیدی"],
    ("thyroid", "hormone"): ["هورمون تیروئید", "هورمون تیروئیدی", "هورمونهای تیروئید"],
    ("thyroid", "gland"): ["غده تیروئید"],
    ("thyroid", "follicular"): ["فولیکول تیروئید", "سلول های تیروئید", "فولیکولار تیروئید"],
    ("follicular", "cells"): ["سلول های فولیکولار", "سلولهای فولیکولار", "سلول های تیروئید", "سلولهای تیروئید"],
    ("thyroid", "nodule"): ["ندول تیروئید", "گره تیروئید"],
    # Cardiovascular
    ("heart", "failure"): ["نارسایی قلبی", "نارسایی قلب", "افت کارکرد قلب"],
    ("cardiovascular", "disease"): ["بیماری قلبی عروقی", "بیماریهای قلبی عروقی", "حوادث قلبی عروقی"],
    ("cardiovascular",): ["قلبی عروقی", "قلبی-عروقی", "کاردیوواسکولار"],
    ("blood", "pressure"): ["فشار خون", "پرفشاری خون"],
    ("hypertension",): ["فشار خون", "پرفشاری خون", "هایپرتانسیون"],
    ("hypotension",): ["افت فشار خون", "کاهش فشار خون", "هیپوتانسیون"],
    ("myocardial", "infarction"): ["سکته قلبی", "انفارکتوس میوکارد", "حمله قلبی"],
    # Liver / Hepatic
    ("liver", "cirrhosis"): ["سیروز کبدی", "سیروز کبد"],
    ("hepatic", "failure"): ["نارسایی کبدی", "نارسایی کبد"],
    ("liver", "failure"): ["نارسایی کبدی", "نارسایی کبد"],
    ("fatty", "liver"): ["کبد چرب", "استئاتوز کبدی"],
    ("portal", "hypertension"): ["فشار ورید باب", "پرفشاری پورت", "فشار پورت"],
    ("hepatic", "encephalopathy"): ["انسفالوپاتی کبدی", "آنسفالوپاتی کبدی"],
    # Metabolic & Endocrine
    ("fasting", "glucose"): ["قند ناشتا", "قند خون ناشتا", "گلوکز ناشتا"],
    ("plasma", "glucose"): ["قند پلاسما", "گلوکز پلاسما"],
    ("fasting", "plasma", "glucose"): ["قند خون ناشتا", "قند ناشتای پلاسما", "گلوکز پلاسما ناشتا", "قند ناشتا"],
    ("hormone", "synthesis"): ["سنتز هورمون", "تولید هورمون", "ساخت هورمون"],
    ("increased", "synthesis"): ["افزایش سنتز", "افزایش تولید", "سنتز بیش از حد"],
    ("decreased", "synthesis"): ["کاهش سنتز", "کاهش تولید"],
    ("adrenal", "hyperplasia"): ["هایپرپلازی آدرنال", "هیپرپلازی ادرنال", "بزرگی آدرنال"],
    ("pituitary", "microadenoma"): ["میکروآدنوم هیپوفیز", "میکروادنوم هیپوفیز", "ادنوم هیپوفیز"],
    ("circadian", "rhythm"): ["ریتم شبانه روزی", "ریتم سیرکادین", "ریتم روزانه"],
    ("cushing", "disease"): ["بیماری کوشینگ", "سندرم کوشینگ"],
    # Clinical Signs & Management
    ("clinical", "manifestations"): ["علائم بالینی", "تظاهرات بالینی", "نشانه های بالینی"],
    ("clinical", "features"): ["ویژگی های بالینی", "یافته های بالینی", "تظاهرات بالینی"],
    ("physical", "examination"): ["معاینه بالینی", "معاینات فیزیکی", "معاینه فیزیکی"],
    ("lifestyle", "management"): ["اصلاح سبک زندگی", "تغییر سبک زندگی", "مدیریت سبک زندگی"],
    ("statin", "therapy"): ["درمان با استاتین", "استاتین تراپی", "مصرف استاتین"],
    ("risk", "factor"): ["عامل خطر", "فاکتور خطر", "عوامل خطر"],
    ("risk", "reduction"): ["کاهش خطر", "کاهش ریسک"],
    ("secondary", "prevention"): ["پیشگیری ثانویه", "پیشگیری درجه دو"],
    ("primary", "prevention"): ["پیشگیری اولیه", "پیشگیری درجه یک"],
    # Renal
    ("renal", "failure"): ["نارسایی کلیه", "نارسایی کلیوی"],
    ("kidney", "failure"): ["نارسایی کلیه", "نارسایی کلیوی"],
    # Diabetic Complications & Orthotics
    ("aircast", "walker"): ["واکر بادی", "واکر ایرکست", "بریس ایرکست", "واکر پنوماتیک"],
    ("pneumatic", "walker"): ["واکر بادی", "واکر پنوماتیک"],
    ("diabetic", "foot"): ["پای دیابتی", "زخم پای دیابتی", "پای دیابتیک"],
    ("conversion", "kit"): ["کیت تبدیل", "کیت مبدل"],
    ("glycemic", "control"): ["کنترل قند", "کنترل گلوکز", "کنترل گلایسمیک"],
    ("organ", "protection"): ["محافظت از اعضا", "حفاظت از ارگان", "حفاظت ارگانها", "حفاظت کلیوی و قلبی"],
    ("paradigm", "shift"): ["تغییر پارادایم", "تغییر رویکرد", "چرخش رویکرد", "تحول بنیادین"],
    ("microvascular", "complications"): ["عوارض میکروواسکولار", "عوارض عروق ریز"],
    ("macrovascular", "complications"): ["عوارض ماکروواسکولار", "عوارض عروق بزرگ"],
    ("wagner", "classification"): ["طبقه بندی واگنر", "درجه بندی واگنر", "سیستم واگنر"],
    ("ulcer", "classification"): ["طبقه بندی زخم", "درجه بندی زخم"],
    ("statin", "intensity"): ["شدت استاتین", "دوز استاتین"],
    ("comprehensive", "care"): ["مراقبت جامع", "مراقبت های جامع", "پایش جامع"],
}

# Specific, unambiguous Persian medical synonyms (strictly non-generic)
SPECIFIC_MEDICAL_TERMS = {
    "tachycardia": {"تاکی کاردی", "تندتپشی"},
    "bradycardia": {"برادی کاردی", "کندتپشی"},
    "hyperthyroidism": {"تیروتوکسیکوز", "هیپرتیروئیدی"},
    "hypothyroidism": {"هیپوتیروئیدی"},
    "goiter": {"گواتر"},
    "tremor": {"ترمور", "لرزش"},
    "tremors": {"ترمور", "لرزش"},
    "synthesis": {"سنتز"},
    "follicular": {"فولیکولار", "فولیکولی"},
    "pathogenesis": {"پاتوژنز"},
    "pathophysiology": {"پاتوفیزیولوژی"},
    "cirrhosis": {"سیروز"},
    "fibrosis": {"فیبروز"},
    "ascites": {"اسیت", "آسیت"},
    "varices": {"واریس"},
    "encephalopathy": {"انسفالوپاتی", "آنسفالوپاتی"},
    "hyperammonemia": {"هیپرامونمی", "هایپرآمونمی"},
    "calcification": {"کلسیفیکاسیون"},
    "psammoma": {"ساموما", "پساموما"},
    "hyperplasia": {"هایپرپلازی", "هیپرپلازی"},
    "microadenoma": {"میکروادنوم", "میکروآدنوم"},
    "adenoma": {"ادنوم", "آدنوم"},
    "cortisol": {"کورتیزول"},
    "atorvastatin": {"اتورواستاتین", "آتورواستاتین"},
    "statin": {"استاتین"},
    "cholesterol": {"کلسترول"},
    "atherosclerotic": {"اترواسکلروتیک", "آترواسکلروتیک"},
    "biopsy": {"بیوپسی"},
    "resection": {"رزکسیون"},
    "carcinoma": {"کارسینوم"},
    "neoplasm": {"نئوپلاسم"},
    "metastasis": {"متاستاز"},
    "microscopic": {"میکروسکوپی"},
    "parathyroid": {"پاراتیروئید"},
    "insulin": {"انسولین"},
    "thyroxine": {"تیروکسین"},
    "antibody": {"پادتن", "انتی بادی", "آنتی بادی"},
    "antibodies": {"پادتنها", "پادتن", "انتی بادی", "آنتی بادی"},
    "thyroiditis": {"تیروئیدیت"},
    "thrombosis": {"ترومبوز"},
    "ischemia": {"ایسکمی"},
    "infarction": {"انفارکتوس"},
    "arrhythmia": {"اریتمی", "آریتمی"},
    "hypertension": {"هایپرتانسیون", "پرفشاری"},
    "hypotension": {"هیپوتانسیون"},
    "hypoglycemia": {"هیپوگلیسمی"},
    "hyperglycemia": {"هیپرگلیسمی"},
    "ketoacidosis": {"کتواسیدوز"},
    "dka": {"dka"},
    "hba1c": {"hba1c"},
    "ldl": {"ldl"},
    "ldl-c": {"ldl-c", "ldl"},
    "hdl": {"hdl"},
    "crcl": {"crcl"},
    "pth": {"pth"},
    "acth": {"acth"},
    "tsh": {"tsh"},
    "t3": {"t3"},
    "t4": {"t4"},
    "stimulation": {"تحریک"},
    "manifestations": {"تظاهرات"},
    "manifestation": {"تظاهر"},
    "clinical": {"بالینی"},
    "concentric": {"هم مرکز", "هم‌مرکز"}
}

# Unify SPECIFIC_MEDICAL_TERMS with BILINGUAL_MEDICAL_CONCEPTS:
# Strictly filters out any generic Persian words, ensuring all ~240+ medical terms are actively evaluated
UNIFIED_SPECIFIC_MEDICAL_TERMS = {}
for en_term, fa_set in SPECIFIC_MEDICAL_TERMS.items():
    en_norm = en_term.lower().strip()
    clean_fa = set()
    for fa_item in fa_set:
        for t in extract_tokens([fa_item]):
            if t not in NORMALIZED_GENERIC_PERSIAN_WORDS:
                clean_fa.add(t)
    if clean_fa:
        UNIFIED_SPECIFIC_MEDICAL_TERMS[en_norm] = clean_fa

for en_k, fa_set in BILINGUAL_MEDICAL_CONCEPTS.items():
    en_norm = en_k.lower().strip()
    clean_fa = set()
    for fa_item in fa_set:
        for t in extract_tokens([fa_item]):
            if t not in NORMALIZED_GENERIC_PERSIAN_WORDS:
                clean_fa.add(t)
    if clean_fa:
        UNIFIED_SPECIFIC_MEDICAL_TERMS.setdefault(en_norm, set()).update(clean_fa)

# Routine academic and conversational English prose stopwords (verbs, adverbs, connectors, fillers)
# These words MUST NOT inflate the denominator of the Cross-Lingual Concept Recall Gate.
ENGLISH_PROSE_STOPWORDS = {
    # Auxiliary & Modal Verbs
    "can", "cannot", "cant", "could", "couldnt", "will", "wont", "would", "wouldnt",
    "shall", "should", "shouldnt", "may", "might", "must", "ought",
    "have", "has", "had", "having", "were", "being",
    # Routine Academic Prose Verbs & Inflections
    "provide", "provides", "provided", "providing",
    "replace", "replaces", "replaced", "replacing",
    "direct", "directs", "directed", "directing",
    "require", "requires", "required", "requiring",
    "occur", "occurs", "occurred", "occurring",
    "include", "includes", "included", "including",
    "contain", "contains", "contained", "containing",
    "involve", "involves", "involved", "involving",
    "show", "shows", "showed", "shown", "showing",
    "demonstrate", "demonstrates", "demonstrated", "demonstrating",
    "indicate", "indicates", "indicated", "indicating",
    "suggest", "suggests", "suggested", "suggesting",
    "lead", "leads", "led", "leading",
    "cause", "causes", "caused", "causing",
    "result", "results", "resulted", "resulting",
    "allow", "allows", "allowed", "allowing",
    "follow", "follows", "followed", "following",
    "perform", "performs", "performed", "performing",
    "present", "presents", "presented", "presenting",
    "determine", "determines", "determined", "determining",
    "evaluate", "evaluates", "evaluated", "evaluating",
    "maintain", "maintains", "maintained", "maintaining",
    "produce", "produces", "produced", "producing",
    "develop", "develops", "developed", "developing",
    "affect", "affects", "affected", "affecting",
    "remain", "remains", "remained", "remaining",
    "exist", "exists", "existed", "existing",
    "need", "needs", "needed", "needing",
    "use", "uses", "used", "using",
    "give", "gives", "given", "giving",
    "take", "takes", "took", "taken", "taking",
    "make", "makes", "made", "making",
    "become", "becomes", "became", "becoming",
    "appear", "appears", "appeared", "appearing",
    "carry", "carries", "carried", "carrying",
    "bring", "brings", "brought", "bringing",
    "see", "sees", "saw", "seen", "seeing",
    "ensure", "ensures", "ensured", "ensuring",
    "achieve", "achieves", "achieved", "achieving",
    "consider", "considers", "considered", "considering",
    "identify", "identifies", "identified", "identifying",
    "describe", "describes", "described", "describing",
    "refer", "refers", "referred", "referring",
    "depend", "depends", "depended", "depending",
    "relate", "relates", "related", "relating",
    "act", "acts", "acted", "acting",
    "help", "helps", "helped", "helping",
    "serve", "serves", "served", "serving",
    "apply", "applies", "applied", "applying",
    "start", "starts", "started", "starting",
    "stop", "stops", "stopped", "stopping",
    "begin", "begins", "began", "beginning",
    "end", "ends", "ended", "ending",
    "continue", "continues", "continued", "continuing",
    "increase", "increases", "increased", "increasing",
    "decrease", "decreases", "decreased", "decreasing",
    "elevate", "elevates", "elevated", "elevating",
    "reduce", "reduces", "reduced", "reducing",
    "alter", "alters", "altered", "altering",
    "change", "changes", "changed", "changing",
    # Connectors, Adverbs, Prepositions & Fillers
    "when", "where", "while", "whereas", "whether", "which", "what", "whatever",
    "whose", "who", "whom", "why", "how", "however",
    "because", "since", "although", "though", "despite", "unless",
    "under", "above", "below", "behind", "beyond", "between", "among", "across",
    "during", "before", "after", "through", "throughout", "toward", "towards",
    "within", "without", "upon", "onto", "against",
    "enough", "capacity", "losses", "loss", "circumstances", "manner", "way",
    "almost", "nearly", "approximately", "about", "around",
    "often", "frequently", "usually", "rarely", "seldom", "never", "always",
    "mostly", "largely", "mainly", "primarily", "secondarily",
    "partially", "completely", "entirely", "totally",
    "very", "quite", "rather", "extremely", "fairly",
    "more", "most", "less", "least", "fewer", "few", "many", "much", "several",
    "all", "any", "some", "each", "every", "both", "either", "neither", "none",
    "other", "others", "another", "such", "same", "different", "similar",
    "first", "second", "third", "last", "next", "previous", "former", "latter",
    "early", "late", "initial", "subsequent", "eventual",
    "high", "low", "higher", "lower", "highest", "lowest",
    "large", "small", "larger", "smaller", "great", "greater",
    "general", "common", "typical", "atypical", "various", "certain",
    "specific", "particular", "overall", "total", "average",
    "due", "owing", "thanks", "according", "based",
    "further", "furthermore", "moreover", "additionally", "besides",
    "therefore", "thus", "hence", "consequently", "accordingly",
    "instead", "otherwise", "indeed", "namely",
    "true", "false", "yes", "no", "not", "non",
    "well", "better", "best", "worse", "worst",
    "likely", "unlikely", "probable", "possible", "impossible",
    "level", "levels", "status", "condition", "conditions", "state", "states",
    "type", "types", "form", "forms", "group", "groups", "class", "classes",
    "case", "cases", "example", "examples", "note", "notes", "point", "points",
    "summary", "overview", "introduction", "conclusion", "review", "discussion",
    "definition", "feature", "features", "aspect", "aspects",
    "step", "steps", "stage", "stages", "phase", "phases",
    "rate", "rates", "ratio", "ratios", "amount", "amounts", "number", "numbers",
    "source", "sources", "target", "targets", "area", "areas", "part", "parts",
    "time", "times", "period", "periods", "day", "days", "week", "weeks", "month", "months", "year", "years"
}

def extract_substantive_tokens(text_or_lines: Union[str, List[str]], max_stem_len: Optional[int] = None) -> Set[str]:
    """
    Extracts substantive medical concepts, scientific entities, formulas, dosages,
    and acronyms, while strictly filtering out routine English prose words, verbs,
    adverbs, and connectors.
    Ensures that general English prose translated into fluent Persian does not
    artificially inflate the denominator of the Cross-Lingual Concept Recall Gate.
    """
    raw_toks = extract_tokens(text_or_lines, max_stem_len=max_stem_len)
    substantive = set()
    for tok in raw_toks:
        tok_lower = tok.lower()
        # Always preserve if it is in unified specific medical terms or pharma interventions
        if tok_lower in UNIFIED_SPECIFIC_MEDICAL_TERMS or tok_lower in PERSIAN_PHARMA_INTERVENTIONS:
            substantive.add(tok)
            continue
        # Always preserve dosages, percentages, measurements
        if re.search(r'\d+(?:\.\d+)?(?:%|mg|mcg|μg|g|kg|ml|l|mmhg|mmol|meq|iu|u|bpm)', tok_lower):
            substantive.add(tok)
            continue
        # Always preserve chemical formulas with sub/superscript or Greek/ion notations
        if re.search(r'[α-ωΑ-Ω²³⁺⁻₀-₉]', tok):
            substantive.add(tok)
            continue
        # Always preserve hyphenated/slashed compounds (IGFBP-3, TNF-α, T3/T4, Gs-α)
        if '-' in tok or '/' in tok:
            substantive.add(tok)
            continue
        # Filter out routine English prose stopwords
        if tok_lower in ENGLISH_PROSE_STOPWORDS or tok_lower in STOPWORDS:
            continue
        # Preserve clinical/medical entities or domain acronyms
        substantive.add(tok)
    return substantive


def evaluate_concept_overlap(raw_tokens: Set[str], trans_tokens: Set[str], trans_text: str) -> Set[str]:
    """
    Evaluates semantic and cross-lingual concept recall from raw slide tokens into translated text.
    Enforces Concept/Phrase-level Equivalence:
    - Direct English/ASCII token match is accepted.
    - Specific Persian medical synonyms (strictly non-generic) are accepted.
    - Multi-word concept phrases are accepted if the multi-word phrase occurs in trans_text.
    - GENERIC Persian words (کاهش, افزایش, فشار, قلب, کبد, تیروئید, etc.) CANNOT by themselves
      constitute evidence for any medical concept!
    """
    common = set()
    norm_text = " " + normalize_persian_text(trans_text) + " "

    # 1. Multi-word phrase matching
    for en_tuple, fa_phrases in BILINGUAL_CONCEPT_PHRASES.items():
        intersecting = set(en_tuple).intersection(raw_tokens)
        if intersecting:
            for phrase in fa_phrases:
                p_norm = normalize_persian_text(phrase)
                if p_norm and p_norm in norm_text:
                    common.update(intersecting)
                    break

    # 2. Specific medical terms (strictly non-generic, unified across BILINGUAL_MEDICAL_CONCEPTS)
    for rt in raw_tokens:
        if rt in common:
            continue
        # Direct ASCII / token intersection
        if rt in trans_tokens:
            common.add(rt)
            continue
        # Check unified specific medical terms (strictly excluding GENERIC_PERSIAN_WORDS)
        syns = UNIFIED_SPECIFIC_MEDICAL_TERMS.get(rt, set())
        if syns and syns.intersection(trans_tokens):
            common.add(rt)

    return common

EXPANDED_BILINGUAL_EN_TO_FA = {}
EXPANDED_BILINGUAL_FA_TO_EN = {}

for en_term, fa_tokens in UNIFIED_SPECIFIC_MEDICAL_TERMS.items():
    en_toks = extract_tokens([en_term])
    val_fa_toks = {f for f in fa_tokens if f not in NORMALIZED_GENERIC_PERSIAN_WORDS}
    for et in en_toks:
        if et not in EXPANDED_BILINGUAL_EN_TO_FA:
            EXPANDED_BILINGUAL_EN_TO_FA[et] = set()
        EXPANDED_BILINGUAL_EN_TO_FA[et].update(val_fa_toks)
    for ft in val_fa_toks:
        if ft not in EXPANDED_BILINGUAL_FA_TO_EN:
            EXPANDED_BILINGUAL_FA_TO_EN[ft] = set()
        EXPANDED_BILINGUAL_FA_TO_EN[ft].update(en_toks)

REVERSE_BILINGUAL_CONCEPTS = EXPANDED_BILINGUAL_FA_TO_EN

def expand_bilingual_concepts(tokens: Set[str]) -> Set[str]:
    """Expands a set of tokens strictly with specific, non-generic bilingual equivalents."""
    expanded = set(tokens)
    for tok in tokens:
        tl = tok.lower()
        if tl in EXPANDED_BILINGUAL_EN_TO_FA:
            expanded.update(EXPANDED_BILINGUAL_EN_TO_FA[tl])
        if tl in EXPANDED_BILINGUAL_FA_TO_EN:
            expanded.update(EXPANDED_BILINGUAL_FA_TO_EN[tl])
    return expanded

def is_ceremonial_slide(slide_item: dict) -> bool:
    """
    Robust detection of ceremonial/non-academic slides (Bismillah, salawat, thanks, welcome)
    with contextual safeguards against false positives in clinical texts.
    """
    if not slide_item or not isinstance(slide_item, dict):
        return False
    if slide_item.get("is_ceremonial"):
        return True
    
    corpus = ""
    if "title_fa" in slide_item:
        corpus += " " + str(slide_item.get("title_fa", ""))
    if "title_en" in slide_item:
        corpus += " " + str(slide_item.get("title_en", ""))
    if "text_lines" in slide_item:
        corpus += " " + " ".join(str(l) for l in slide_item.get("text_lines", []))
    if "bullets" in slide_item:
        for b in slide_item.get("bullets", []):
            if isinstance(b, dict):
                corpus += " " + str(b.get("lead", "")) + " " + str(b.get("text", ""))
            elif isinstance(b, (tuple, list)):
                corpus += " " + " ".join(str(x) for x in b)
            else:
                corpus += " " + str(b)
                
    norm_corpus = normalize_persian_text(corpus).lower().strip()
    if not norm_corpus:
        return False

    # Distinct ceremonial phrases with low clinical ambiguity
    ceremonial_phrases = [
        "بسم الله", "بسم‌الله", "صلوات", "اللهم صل", "صل علی", "صلوا", "ادای احترام",
        "شهدای", "تشکر و قدردانی", "با تشکر", "سپاسگزاری", "پایان جلسه", "پایان ارائه",
        "پایان اسلاید", "خوش آمدید", "خوش‌آمدید", "پرسش و پاسخ", "سوال و جواب",
        "welcome", "thank you", "thanks for", "any questions", "any question", "q&a"
    ]
    if any(phrase in norm_corpus for phrase in ceremonial_phrases):
        return True

    # High-ambiguity single words only trigger if the slide is very short (< 10 words)
    words = norm_corpus.split()
    if len(words) < 10:
        short_markers = ["تشکر", "تقدیم", "پایان", "thanks"]
        if any(marker in words or marker in norm_corpus for marker in short_markers):
            return True

    return False

DEFAULT_CHUNK_LENGTH_SEC = 540

def validate_cross_reference(cross_ref_entry: Union[dict, str], current_slide_num: Optional[int] = None, available_slide_nums: Optional[Set[int]] = None) -> tuple[bool, str]:
    """
    Canonical structural cross-reference validator:
    Strictly requires structured dictionary objects: {"target_slide": int, "reason": str}.
    Rejects text strings, bare emojis, or references to non-existent slides.
    Returns: (is_valid: bool, error_reason: str)
    """
    if isinstance(current_slide_num, (set, list, tuple)) and available_slide_nums is None:
        available_slide_nums = set(current_slide_num)
        current_slide_num = None

    if isinstance(cross_ref_entry, dict):
        tgt = cross_ref_entry.get("target_slide")
        reason = cross_ref_entry.get("reason") or cross_ref_entry.get("note", "")
        if tgt is None:
            return False, "Structural cross-reference dictionary missing required 'target_slide' key."
        try:
            tgt_int = int(tgt)
        except (ValueError, TypeError):
            return False, f"Invalid 'target_slide' format (must be integer): {tgt}"
        if available_slide_nums is not None:
            if tgt_int not in available_slide_nums:
                return False, f"Referenced target slide {tgt_int} does not exist in presentation."
        elif tgt_int < 1:
            return False, f"Referenced target slide {tgt_int} must be positive."
        if not isinstance(reason, str) or not reason.strip():
            return False, f"Structural cross-reference to Slide {tgt_int} must include a non-empty 'reason' or 'note'."
        return True, ""
        
    elif isinstance(cross_ref_entry, str):
        return False, (f"Text string cross-reference rejected: '{cross_ref_entry}'. "
                       "Cross-references must be structured dictionaries: {'target_slide': int, 'reason': str}.")
        
    return False, f"Unsupported cross-reference type: {type(cross_ref_entry).__name__}"

def extract_clinical_facts(text: str) -> dict:
    """
    Extracts structured clinical facts:
    - percentages (e.g. 7%, 10%, ۱۰٪, ۷ درصد)
    - dosages & medical quantities (e.g. 25 mg, 500mg, 10 mcg, 2 gr)
    - lab values & vitals (e.g. 120/80 mmHg, 120 mmHg, 37 C, 5.5 mmol/L)
    - numeric ranges (e.g. 5-10, 5 الی 10, 2 تا 4)
    - significant clinical numbers (>= 2 digits)
    """
    if not text:
        return {
            "percentages": set(),
            "dosages": set(),
            "lab_values": set(),
            "ranges": set(),
            "numbers": set()
        }
        
    norm_text = text.translate(COMBINED_DIGITS).lower()
    
    # 1. Percentages
    pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:%|٪|درصد)', norm_text)
    percentages = {f"{m}%" for m in pct_matches}
    
    # 2. Dosages & medical quantities
    dosage_pattern = r'(\d+(?:\.\d+)?)\s*(mg|mcg|μg|ug|g|gr|ml|cc|iu|meq|میلی[\s‌]گرم|میکروگرم|گرم|سی[\s‌]سی|واحد)'
    dosages = set()
    for val, unit in re.findall(dosage_pattern, norm_text):
        unit_clean = unit.replace(" ", "").replace("\u200c", "")
        if unit_clean in ("میلیگرم", "mg"):
            norm_unit = "mg"
        elif unit_clean in ("میکروگرم", "mcg", "μg", "ug"):
            norm_unit = "mcg"
        elif unit_clean in ("گرم", "g", "gr"):
            norm_unit = "g"
        elif unit_clean in ("سیسی", "ml", "cc"):
            norm_unit = "ml"
        elif unit_clean in ("واحد", "iu"):
            norm_unit = "iu"
        elif unit_clean in ("meq",):
            norm_unit = "meq"
        else:
            norm_unit = unit_clean
        dosages.add(f"{val} {norm_unit}")
        
    # 3. Lab values & vitals (Blood pressure, temps, standard lab units)
    lab_values = set()
    # Blood pressure: 120/80 or 120 روی 80
    bp_matches = re.findall(r'(\d{2,3})\s*(?:/|روی)\s*(\d{2,3})(?:\s*mmhg|\s*میلی[\s‌]متر[\s‌]جیوه)?', norm_text)
    for sys_bp, dia_bp in bp_matches:
        lab_values.add(f"{sys_bp}/{dia_bp} mmhg")
        
    # Single lab units
    lab_unit_pat = r'(\d+(?:\.\d+)?)\s*(mmhg|mmol/l|meq/l|mg/dl|c|درجه|سانتی[\s‌]گراد)'
    for val, unit in re.findall(lab_unit_pat, norm_text):
        if "c" in unit or "درجه" in unit or "سانتی" in unit:
            lab_values.add(f"{val} c")
        else:
            lab_values.add(f"{val} {unit}")
            
    # 4. Numeric clinical ranges (e.g. 5-10, 5 الی 10, 2 تا 4)
    range_matches = re.findall(r'(?<!\w)(\d+(?:\.\d+)?)\s*(?:-|الی|تا)\s*(\d+(?:\.\d+)?)(?!\w)', norm_text)
    ranges = {f"{r1}-{r2}" for r1, r2 in range_matches if r1 != r2}
    
    # 5. Significant clinical numbers (two or more digits)
    num_matches = re.findall(r'(?<![\w\.\-])(\d{2,5})(?![\w\.\-])', norm_text)
    numbers = set(num_matches)
    
    return {
        "percentages": percentages,
        "dosages": dosages,
        "lab_values": lab_values,
        "ranges": ranges,
        "numbers": numbers
    }

def compare_clinical_facts(audio_facts: dict, slide_facts: dict) -> dict:
    """
    Compares clinical facts extracted from audio segments against slide spoken lecture.
    Distinguishes two tiers of omissions:
    1. Critical omissions: drug dosages and vital lab values (triggers hard ERROR in verifier)
    2. Advisory omissions: percentages, numeric ranges, clinical numbers (triggers WARNING in verifier)
    Returns comparison metrics and partitioned omission lists.
    """
    critical_omissions = []
    advisory_omissions = []
    
    # 1. Critical categories (Drug dosages, vital lab values)
    for cat in ("dosages", "lab_values"):
        aud_set = audio_facts.get(cat, set())
        sld_set = slide_facts.get(cat, set())
        missing = aud_set - sld_set
        for item in sorted(missing):
            critical_omissions.append(f"{cat.rstrip('s')}: {item}")
            
    # 2. Advisory categories (Percentages, ranges, numbers)
    for cat in ("percentages", "ranges", "numbers"):
        aud_set = audio_facts.get(cat, set())
        sld_set = slide_facts.get(cat, set())
        missing = aud_set - sld_set
        for item in sorted(missing):
            advisory_omissions.append(f"{cat.rstrip('s')}: {item}")
            
    all_omissions = critical_omissions + advisory_omissions
    
    total_audio_facts = sum(len(audio_facts.get(k, set())) for k in ("dosages", "lab_values", "percentages", "ranges", "numbers"))
    total_slide_facts = sum(len(slide_facts.get(k, set())) for k in ("dosages", "lab_values", "percentages", "ranges", "numbers"))
    
    fact_recall = 1.0
    if total_audio_facts > 0:
        matched = total_audio_facts - len(all_omissions)
        fact_recall = max(0.0, matched / total_audio_facts)
        
    return {
        "total_audio_facts": total_audio_facts,
        "total_slide_facts": total_slide_facts,
        "critical_omissions": critical_omissions,
        "advisory_omissions": advisory_omissions,
        "omissions": all_omissions,
        "fact_recall": fact_recall
    }

def clean_markdown_text(text: str) -> str:
    """
    Cleans raw markdown artifacts (*, #, __) and template headings from text,
    reflowing soft-breaks into clean prose without internal newlines.
    """
    if not text:
        return ""
    text = str(text)
    # Strip template headers
    generic_header_re = re.compile(
        r'(?m)^#{1,6}\s*(?:بیانات استاد|تدریس استاد|تدریس کلاسی|بیانات کلاسی|متن پیاده\s*سازی|'
        r'پیاده\s*سازی صوت|قطعه\s*(?:\d+|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم)|'
        r'بخش\s*\d+|پارت\s*\d+|ترنسکریپت|جلسه\s*\d+|اسلاید\s*\d+)[\s:]*$', re.I
    )
    text = generic_header_re.sub('', text)
    # Strip header markers (#)
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)
    # Strip bullet markers at line starts
    text = re.sub(r'(?m)^\s*[-*+•–—]\s+', '', text)
    # Strip bold / italic asterisks
    text = re.sub(r'[*#]', '', text)
    # Reflow newlines into single spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_inline_spans(text: str, default_bold: bool = False, default_italic: bool = False) -> List[dict]:
    """
    Parses a single line of text into inline text runs, extracting markdown bold (**...**)
    and italic (*...*), stripping markdown symbols, and ensuring zero newlines in runs.
    """
    if not text:
        return []
    # Replace internal newlines with space
    text = str(text).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'  +', ' ', text).strip()
    if not text:
        return []
        
    pattern = r'(\*\*.*?\*\*|__.*?__|\*[^\*\s][^\*]*?\*|(?<![\w/])_[^_\s][^_]*?_(?![\w/]))'
    raw_spans = re.split(pattern, text)
    runs = []
    for span in raw_spans:
        if not span:
            continue
        if (span.startswith('**') and span.endswith('**') and len(span) >= 4) or \
           (span.startswith('__') and span.endswith('__') and len(span) >= 4):
            content = span[2:-2]
            b, it = True, False
        elif (span.startswith('*') and span.endswith('*') and len(span) >= 2) or \
             (span.startswith('_') and span.endswith('_') and len(span) >= 2):
            content = span[1:-1]
            b, it = False, True
        else:
            content = span
            b, it = default_bold, default_italic
            
        # Strip any stray unparsed * or #
        clean_content = re.sub(r'[*#]', '', content)
        if clean_content:
            runs.append({'text': clean_content, 'bold': b, 'italic': it})
            
    return runs

def parse_markdown_blocks(text: Union[str, list, None]) -> List[dict]:
    """
    Parses raw spoken lecture or study text into structured semantic blocks:
    - Eliminates transcript template artifacts (e.g. '#### بیانات استاد:')
    - Identifies substantive markdown headings (level, text)
    - Groups consecutive single-newline lines into continuous prose paragraphs (no internal \\n)
    - Identifies bullet points with optional lead/body separation
    - Identifies numbered list items
    Returns list of dicts:
      {'type': 'heading', 'level': int, 'text': str}
      {'type': 'paragraph', 'text': str}
      {'type': 'bullet', 'lead': str, 'text': str}
      {'type': 'numbered', 'num': str, 'text': str}
    """
    if not text:
        return []
    if isinstance(text, (list, tuple)):
        raw_text = '\n\n'.join(str(x) for x in text if x)
    else:
        raw_text = str(text)

    raw_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    lines = raw_text.split('\n')
    
    blocks = []
    current_para_lines = []
    
    def flush_para():
        if current_para_lines:
            joined = ' '.join(l.strip() for l in current_para_lines if l.strip())
            joined = re.sub(r'  +', ' ', joined).strip()
            if joined:
                blocks.append({'type': 'paragraph', 'text': joined})
            current_para_lines.clear()

    generic_header_re = re.compile(
        r'^#{1,6}\s*(?:بیانات استاد|تدریس استاد|تدریس کلاسی|بیانات کلاسی|متن پیاده\s*سازی|'
        r'پیاده\s*سازی صوت|قطعه\s*(?:\d+|اول|دوم|سوم|چهارم|پنجم|ششم|هفتم|هشتم|نهم|دهم)|'
        r'بخش\s*\d+|پارت\s*\d+|ترنسکریپت|جلسه\s*\d+|اسلاید\s*\d+)[\s:]*$', re.I
    )
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_para()
            continue
            
        # 1. Filter out generic template headers
        if generic_header_re.match(line):
            flush_para()
            continue
            
        # 2. Check substantive markdown heading
        m_head = re.match(r'^(#{1,6})\s+(.+)$', line)
        if m_head:
            flush_para()
            h_level = len(m_head.group(1))
            h_text = m_head.group(2).strip()
            h_text = re.sub(r'[*#_]', '', h_text).strip()
            if h_text:
                blocks.append({'type': 'heading', 'level': h_level, 'text': h_text})
            continue
            
        # 3. Check bullet point
        m_bullet = re.match(r'^\s*[-*+•–—]\s+(.+)$', line)
        if m_bullet:
            flush_para()
            b_text = m_bullet.group(1).strip()
            lead = ''
            body = b_text
            m_lead = re.match(r'^\*\*(.*?)\*\*[:\s]*(.*)$', b_text)
            if m_lead:
                lead = m_lead.group(1).strip()
                if not lead.endswith(':'):
                    lead += ':'
                body = m_lead.group(2).strip()
            elif ':' in b_text and not b_text.startswith('http'):
                parts = b_text.split(':', 1)
                if len(parts[0].split()) <= 6:
                    lead = parts[0].strip() + ':'
                    body = parts[1].strip()
            blocks.append({'type': 'bullet', 'lead': lead, 'text': body})
            continue

        # 4. Check numbered list item
        m_num = re.match(r'^\s*(\d+)[\.\)]\s+(.+)$', line)
        if m_num:
            flush_para()
            num = m_num.group(1)
            n_text = m_num.group(2).strip()
            blocks.append({'type': 'numbered', 'num': num, 'text': n_text})
            continue
            
        # 5. Continuous prose line
        current_para_lines.append(line)
        
    flush_para()
    return blocks



