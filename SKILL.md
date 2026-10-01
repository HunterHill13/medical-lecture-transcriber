---
name: medical-lecture-transcriber
description: >-
  Publication-grade medical study guide and lecture transcription workflow (v5.1.0): enforces Anti-Clause Parentheses Gate
  (PARENTHETICAL_CLAUSE_VIOLATION strictly restricts parenthetical English to <= 4 words of concise proper/drug names and blocks full clauses),
  Substantive Medical Concept Denominator Filtering (filters routine English prose verbs and fillers from recall denominator),
  Gemini Multimodal Audio Transcription Protocol (strictly prohibits local STT/Whisper/CUDA downloads),
  Track 3 Reference Note Separation (renders ref_note in dedicated callouts strictly outside Track 2 Slide Box),
  Semantic Source Provenance Mapping (validates line citations), Unified Bilingual Medical Concept Engine (248 non-generic concepts + phrases),
  Visual-Aware OCR Triggering, Automated 103-Test Suite in tests/, and Clean Portable POSIX Packaging (100% '/' paths, 0 pycache).
---

# Medical Lecture Transcriber & Study Guide Generator (v5.1.0)

## Overview

This skill provides an end-to-end, publication-grade medical pair-programming and study-guide generation workflow. It synthesizes live class audio lectures with PowerPoint (`.pptx`) or PDF (`.pdf`) presentation slides into a beautifully styled Microsoft Word study guide (`.docx`) and structured Markdown transcripts, governed by strict page index invariance, tri-partite provenance attribution, substantive audio coverage, and visual fidelity protocols.

---

## 🎨 1. MASTER COLOR & TYPOGRAPHY SPECIFICATION (STRICT MANDATORY)

Every agent implementing this skill **MUST** strictly adhere to the following color palette and typography rules without deviation:

| Element | Font | Size | Weight | Color (HEX) | XML Specification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Document Title** | Dubai | 16pt | Bold | `#78281F` (Burgundy) | `<w:sz w:val="32"/><w:szCs w:val="32"/><w:b/><w:bCs/>` |
| **TOC Title** | Dubai | 14pt | Bold | `#78281F` (Burgundy) | `<w:sz w:val="28"/><w:szCs w:val="28"/><w:b/><w:bCs/>` |
| **TOC Table Header** | Dubai | 10.5pt | Bold | Text `#FFFFFF` on Fill `#78281F` | `<w:shd w:fill="78281F"/>` |
| **TOC Section Col (0)** | Dubai | 10pt | Bold | `#78281F` (Burgundy) | `<w:color w:val="78281F"/>` |
| **TOC Audio Time Col (2)**| Dubai | 10pt | Bold | `#D35400` (Deep Orange) | `<w:color w:val="D35400"/>` |
| **TOC Other Cols (1, 3)**| Dubai | 10pt | Regular | `#262626` (Charcoal) | `<w:color w:val="262626"/>` |
| **Section Heading (H1)** | Dubai | 14pt | Bold | `#78281F` (Burgundy) | `<w:sz w:val="28"/><w:szCs w:val="28"/><w:b/><w:bCs/>` |
| **H1 Audio Time Tag** | Dubai | 10pt | Bold | `#D35400` (Deep Orange) | `[⏱️ زمان فایل صوتی: دقیقه XX:YY]` |
| **Subheadings (H2)** | Dubai | 11pt | Bold | `#0E6251` (Forest Emerald) | Same size as body text, NOT enlarged! |
| **Body Paragraphs** | Dubai | 11pt | Regular | `#262626` (Charcoal) | Line spacing 1.15, space after 3.5pt |
| **Slide Box Outline** | - | 1pt | - | `#85C1E9` (Soft Sky Blue) | `<w:tcBorders><w:top w:sz="8" w:color="85C1E9"/>...` |
| **Slide Box Header Bar**| Dubai | 10.5pt | Bold | Fill `#EBF5FB`, Label `#1B4F72`, Title `#78281F` | `📑 اسلاید مرتبط X : [عنوان فارسی] ([English Title])` |
| **Slide Box Body** | Dubai | 10.5pt | Regular | Fill `#FFFFFF` (Pure White) | Outline `#85C1E9` on left, bottom, right |
| **Ref Note Lead (`ref_note`)**| Dubai | 10pt | Bold | `#6C3483` (Royal Purple) | `💡 شرح تکمیلی رفرنس ({ref_book_name}) جهت تفهیم مبحث: ` |
| **Ref Note Body** | Dubai | 10pt | Italic | `#333333` (Dark Charcoal) | 2–3 sentences high-yield clinical explanation |
| **Reference Table Header**| Dubai | 10.5pt | Bold | Fill `#F5EBE1` (Peach/Cream), Text `#5D4037` | Espresso brown text on cream fill |
| **Reference Banners** | Dubai | 11pt | Bold | Fill `#4A709C` (Slate Blue), Text `#FFFFFF` | Merged across all table columns |
| **Student Review Badge** | Dubai | 10.5pt | Bold | Fill `#FEF9E7`, Border `#D35400` (Amber) | `⚠️ برچسب بازبینی دانشجو (اسلاید X...): ` |
| **Classroom Q&A Box** | Dubai | 10.5pt | Bold | Fill `#FBF9FD`, Right Border `#6C3483` (36) | `❓ پرسش کلاسی:` `#6C3483`, `💡 پاسخ استاد:` `#1E8449` |

---

## 📚 2. CONTENT INTEGRITY, TRI-PARTITE PROVENANCE & PEDAGOGICAL PROTOCOLS

### A. Strict Anti-Hallucination & Tri-Partite Provenance Attribution (خاستگاه‌شناسی سه‌گانه مطالب و منع انتساب نابجا به استاد)
Medical study guides require 100% verifiable source provenance. Students must immediately know whether a sentence was spoken by the professor, extracted verbatim from a slide, or added as a textbook reference note.

1. **Tri-Partite Provenance Tiers (سطوح سه‌گانه خاستگاه مطالب):**
   - **Tier 1 — `[🎙️ تدریس کلاسی استاد]` (Track 1):**
     Faithful Clinical Content Preservation: captures all medical facts, pathophysiology reasoning, mnemonics, dosages, laboratory thresholds, diagnostic algorithms, and clinical cases spoken by the professor (Word Volume Ratio $\ge$ 50% excluding verbal fillers, with 100% material clinical content preserved).
     - **Zero Hallucination Rule:** Agents must NEVER invent remarks or attribute textbook passages to the professor.
   - **Tier 2 — `[📑 ترجمه اسلاید X]` (Track 2):**
     Literal, faithful translation of the English slide text, bullet structure, and figures in the dedicated slide box.
     - **Isolation Rule:** Slide text is never merged into the spoken lecture prose, and spoken words are never injected as fake slide bullets.
   - **Tier 3 — `[💡 شرح تکمیلی رفرنس ({ref_book_name})]` (Track 3):**
     Supplementary commentary strictly reserved for unvoiced, skipped, or under-explained slides.
     - Clearly distinguished by royal purple `#6C3483` lead and italic charcoal styling, separated from professor remarks.

2. **Strict Unvoiced & Skipped Slide Protocol:**
   - If the professor skips Page N without speaking about it:
     - The slide box for Page N **MUST STILL BE CREATED** to preserve Page Index Invariance.
     - It must be explicitly marked with an amber badge: `[⚠️ اسلاید تدریس‌نشده در کلاس]`.
     - High-yield textbook explanation is placed inside `ref_note` so students understand the content without confusing it with the lecture.
     - **NEVER generate fake spoken narrative in Track 1 for a skipped slide!**

3. **Verifiable Classroom Q&A Protocol:**
   - Classroom Q&A callouts (`add_qa_box`) are authorized **ONLY** when a genuine question was raised by a student or posed by the instructor during the recorded class session.
   - It is strictly forbidden to fabricate synthetic student questions out of the professor's normal continuous monologue.

4. **Anti-Parametric-Hallucination Protocol (منع سوگیری حافظه کتابی و جایگزینی خودسرانه متون اسلاید):**
   - در کادر اسلاید (Track 2)، مدل موظف به ترجمه لغوی و ساختاریافته سطرهای عینی اسلاید (`raw_slides.json["text_lines"]`) است.
   - به کارگیری حافظه پارامتریک و درج انشاهای کلی از رفرنس‌های پزشکی (مانند هاریسون) به جای ترجمه مستقیم اسلاید **اکیداً ممنوع** است و توسط گیت اعتبارسنجی با خطای `PARAMETRIC_HALLUCINATION_RISK` شناسایی می‌شود.
   - توضیحات دانشنامه‌ای تنها و منحصراً در بخش `ref_note` مجاز است، نه در بالت‌های ترجمه اسلاید!

5. **Parenthetical Entity Restriction & Anti-Clause Enforcement (قانون انحصاری پرانتزها و منع کپی عبارات انگلیسی):**
   - **انحصار به اسامی خاص پزشکی:** در کادر اسلاید (Track 2)، متن ترجمه باید به زبان فارسی سلیس و آکادمیک نگاشته شود. درج واژگان انگلیسی در پرانتز منحصراً و اکیداً به **اسامی خاص پزشکی، نام داروها، اختصارات استاندارد و اصطلاحات کلیدی (حداکثر ۱ تا ۴ واژه)** محدود است؛ مانند:
     - `دئودنوم (Duodenum)`
     - `کلسیم اصلاح‌شده (Corrected calcium)`
     - `استئیت فیبروزا سیستیکا (Osteitis fibrosa cystica)`
     - `تومورهای قهوه‌ای (Brown Tumors)`
     - `نئوپلازی چندگانه غدد درون‌ریز تیپ ۱ (Multiple Endocrine Neoplasia Type 1)`
     - `سیناکلست (Cinacalcet)`
     - `پاراتورمون (PTH)`
   - **منع مطلق کپی جملات یا عبارات کامل (Anti-Clause Violation):** کپی کردن جملات انگلیسی، سطرها، یا بندهای دارای فعل/حرف‌ربط (مانند `(When the calcium level is >13 mg/dL...)` یا `(cannot provide enough capacity to replace losses)`) در داخل پرانتز یا متن بالت **اکیداً ممنوع** است و توسط گیت با خطای سخت `PARENTHETICAL_CLAUSE_VIOLATION` مسدود می‌شود.
   - **فرمول مخرج کسر در گیت انطباق:** مخرج کسر گیت ریکال (Cross-Lingual Concept Recall) به صورت خودکار کلمات عمومی، افعال و قیدهای روتین زبان انگلیسی (مانند `provide`, `replace`, `cannot`, `enough`, `losses`, `under`, `circumstances`, `directed`) را فیلتر کرده و تنها مفاهیم اصیل پزشکی، فرمول‌ها، دوزها و اختصارات را ارزیابی می‌کند. بنابراین مترجم بدون نیاز به درج عبارات انگلیسی در پرانتز، با ترجمه سلیس فارسی حدنصاب ۵۰٪ را احراز می‌کند.

---

### B. Parametric Reference Architecture (معماری پارامتریک کتب مرجع - عدم هاردکد نام رفرنس)
The skill is fully decoupled from any single textbook. Agents must dynamically adapt the reference name `{ref_book_name}` to match the target medical discipline:
- **Internal Medicine / Endocrinology / Nephrology:** Harrison's Principles of Internal Medicine / Cecil Medicine
- **Cardiology:** Braunwald's Heart Disease
- **Surgery:** Schwartz's Principles of Surgery / Sabiston Textbook of Surgery
- **Pediatrics:** Nelson Textbook of Pediatrics
- **Obstetrics & Gynecology:** Williams Obstetrics / Berek & Novak's Gynecology
- **Pathology:** Robbins & Cotran Pathologic Basis of Disease
- **Pharmacology:** Katzung Basic & Clinical Pharmacology / Goodman & Gilman's
- **Physiology:** Guyton & Hall Textbook of Medical Physiology / Berne & Levy

Whenever `{ref_book_name}` is referenced in titles or notes, substitute the appropriate curriculum standard (e.g. `💡 شرح تکمیلی رفرنس (هاریسون) جهت تفهیم مبحث` or `💡 شرح تکمیلی رفرنس (برانوالد) جهت تفهیم مبحث`).

---

### C. Unified Slide-Anchored Spoken Architecture & Dual-Track Isolation (معماری ساختاریافته تدریس پیوسته موضعی)
To eliminate any conflict between classroom lecture flow and slide translation fidelity, and to **guarantee that no spoken concept, clinical anecdote, or diagnostic nuance is lost**, all content is unified inside `translated_slides.json` and segregated into two clean, non-interfering tracks:

1. **Track 1: متن تدریس کلاسی استاد (`spoken_lecture` در هر اسلاید):**
   - **Slide-Anchored Spoken Flow:** سخنان استاد دقیقاً همراه با همان اسلایدی که در آن لحظه تدریس می‌شده جانمایی می‌شود (نه به صورت کلی‌گویی‌های مبهم و کلی).
   - شامل ۱۰۰٪ گفتار استاد، الگوریتم‌های تشخیصی، هشدارهای بالینی (مثلاً عدم درخواست عجولانه MRI در اورژانس به دلیل اینسیدنتالوماهای ۷٪ آدرنال و ۱۰٪ هیپوفیز)، توجیهات فیزیولوژیک و تعاملات کلاسی است.
   - فیلد `spoken_lecture` در هر اسلاید ذخیره شده و توسط `create_slide_pamphlet.py` دقیقاً قبل از کادر اسلاید با آیکون `🎙️ تدریس و بیانات کلاسی استاد` رندر می‌شود.
   - اسلایدهای شروع فصل دارای فیلد اختیاری `section_title` هستند که تیتر H1 و ردیف جدول فهرست مطالب (TOC) را به صورت خودکار ایجاد می‌کنند.

2. **Track 2: کادر اسلاید مرتبط (Dedicated Slide Box):**
   - Serves as a 100% faithful, isolated, literal mirror of the English slide.
   - Never summarizes, never merges spoken words into slide bullets, and never alters bullet counts or hierarchies.
   - **Structured Two-Part Bullet Schema (ساختار دوبخشی بالت‌ها با سرتیتر بولد):**
     برای جلوگیری از یکنواختی متن و ارتقای خوانایی بصری بدون نقض تطابق ۱ به ۱، بالت‌ها باید دارای سرتیتر بولد باشند:
     - فرمت شیء در JSON: `{"lead": "سرتیتر کوتاه بالت:", "text": "متن تفصیلی و ترجمه بالت..."}`
     - یا تاپل در کد پایتون: `("سرتیتر کوتاه:", "متن تفصیلی...")`
     - بخش `lead` با رنگ آبی تیره `#1B4F72` و فونت بولد و بخش `text` با رنگ زغالی `#262626` رندر می‌شود.
   - For **Pure Text Slides**: Contains the clean, faithfully translated Persian bullet points (CRITICAL: NEVER embed a redundant screenshot of plain English text!).
   - For **Table Slides**: Contains the localized Persian Word table (`render_reference_table`) reproducing exact columns, headers, and rows.
   - For **Diagram / Flowchart Slides**: Contains a faithful line-by-line translation of all paths, receptors, and labels.
   - For **Unvoiced / Skipped Slides**: Appends the mandatory substantive `ref_note` (minimum 12 words) in royal purple.

---

### D. Dual-Engine Presentation Extraction Protocol (پروتکل استخراج دوگانه متون ارائه PPTX و PDF)
To prevent ad-hoc text extraction and format discrepancies, agents must use the unified extraction script:
1. **Command Execution:**
   - **For PowerPoint (.pptx):**
     ```powershell
     uv run --with python-pptx --with pymupdf python scripts/extract_presentation.py --input presentation.pptx --output raw_slides.json --img-dir ./slide_images
     ```
   - **For PDF (.pdf):**
     ```powershell
     uv run --with python-pptx --with pymupdf python scripts/extract_presentation.py --input presentation.pdf --output raw_slides.json --img-dir ./slide_images
     ```
2. **Unified Data Schema:**
   The output `raw_slides.json` contains a strictly ordered array with 1-based `slide_number` matching the exact page index of the input file.

---

### E. Strict Page Index Invariance Protocol (قانون ثبات مطلق اندیس صفحه - منع پرش و ادغام)
To permanently eliminate cascade offset shifts (Off-by-N drift):
1. **Strict 1-to-1 Mapping:**
   - **Slide Box N in the Word study guide MUST STRICTLY correspond to Page N of the presentation file.**
   - Total slide boxes in the document must equal the total number of pages in the presentation (`len(SLIDES_DB) == total_presentation_pages`).
2. **Handling Image-Only and Diagram Slides:**
   - If Page N is purely an image, atlas illustration, or diagram without typed text:
     - Slide Box N **MUST STILL EXIST**.
     - Set `title_fa` and `title_en` matching the diagram topic.
     - Insert an amber **Student Review Badge** (`add_student_review_badge(doc, N, note_text)`) explaining that the slide is a visual diagram/figure.
     - **NEVER skip, omit, or merge Page N into Page N+1!** Merging slides causes a catastrophic offset shift across the entire rest of the pamphlet.

---

### F. Mandatory Automated Slide Alignment Verification Gate (گیت اعتبارسنجی خودکار انطباق اسلایدها)
Before constructing the Word document (`.docx`), the agent **MUST** run the automated alignment validator:
```powershell
uv run python scripts/verify_slide_alignment.py --raw raw_slides.json --translated translated_slides.json
```
- **Validation Criteria:**
  1. `Total Raw Slides == Total Translated Slides`.
  2. Every integer index from `1` to `N` exists with zero gaps, zero skips, and zero duplicates.
  3. Anchor keyword verification (with 8-character medical root matching) guarantees that Page N's English terms match Slide Box N (detecting and failing on any offset shifts).
  4. **Substantive Reference Note Check (`ref_note`):** For every slide marked as skipped (`is_skipped` or `unvoiced`), `ref_note` MUST be non-empty and contain at least 12 words of substantive clinical textbook commentary. Missing or superficial notes trigger hard gate failure (`MISSING_REF_NOTE` / `SUPERFICIAL_REF_NOTE`).
- **Auto-Fix Boundary:** Auto-fix (`--auto-fix`) is strictly authorized to repair deterministic structural gaps (e.g. creating review boxes with raw images for missing page indices). It is forbidden from altering semantic slide content.

---

### G. Multimodal Vision & Anti-OCR-Blindness Protocol (پروتکل بینایی ماشین چندحالته و رفع کوری استخراج جداول)
1. **The OCR Blindness Hazard (خطر کوری استخراج متون درون عکس):**
   - کتابخانه‌های متنی (`python-pptx` و `pymupdf`) متون تایپ‌نشده‌ای که به شکل اسکرین‌شات از کتاب یا اسکن جداول در اسلاید قرار دارند را تشخیص نمی‌دهند و طول کاراکتر را صفر برمی‌گردانند.
   - هرگز نباید اسلایدی را صرفاً به دلیل خالی بودن `text_lines` در `raw_slides.json`، «فاقد متن» یا «خالی» فرض کرد!
2. **Mandatory Visual Inspection Trigger (`needs_vision_inspection`):**
   - برای هر اسلایدی که دارای پرچم `needs_vision_inspection: true` یا `is_image_only: true` است (یا طول متن تایپ‌شده آن کمتر از ۵۰ کاراکتر است اما دارای تصویر است)، ایجنت **الزاماً و قطعی** باید ابزار بینایی ماشین (`view_file`) را روی تصویر رندرشده آن اسلاید (`slide_images/slide_XX.png`) فراخوانی کند.
   - ساختار جداول، مقادیر عددی، کات‌آف‌های آزمایشگاهی و فلوچارت‌ها باید مستقیماً از روی تصویر استخراج و در JSON ترجمه درج شوند.

---

### H. Universal Visual Content Architecture (معماری بصری جامع و هدفمند)
1. **Targeted Visual Roles:**
   - **Pure Text Slides (اسلایدهای صرفاً متنی):** Do NOT include a redundant screenshot of plain English text. They are translated cleanly and completely into Persian bullet points inside the slide box.
   - **Visual Slides (جداول، دیاگرام‌ها، فلوچارت‌ها و تصاویر آناتومیک):**
     - **Dual Presentation (تصویر اصلی + جدول/متن فارسی):** برای اسلایدهای تصویری و جداول، هرگز تصویر انگلیسی اصلی نباید سرکوب شود! هم اسکرین‌شات باکیفیت انگلیسی و هم جدول/دیاگرام بازسازی‌شده فارسی در کادر اسلاید درج می‌شوند تا دانشجو بتواند مرجع انگلیسی و ساختار فارسی را در کنار هم مشاهده کند.
     - **Track 1:** Displays the original high-resolution English diagram/table image alongside the professor's lecture breakdown (`add_figure_with_caption`).
     - **Track 2 (Slide Box):** Displays the slide box. If the figure was NOT already embedded in Track 1 (`image_already_shown=False`), it MUST be embedded inside the slide box.
2. **Deterministic Code Check & Prohibition of False Flags:**
   - در کد رندر (`add_slide_box_from_json`)، وجود جدول (`table_data`) هرگز نباید مانع درج تصویر اسلاید شود.
   - ایجنت‌ها اکیداً منع شده‌اند از اینکه پرچم `image_already_shown=True` را به صورت دستی یا کورکورانه ارسال کنند، مگر آنکه تصویر واقعاً در همان بخش در ریل ۱ با `add_figure_with_caption` در خروجی Word قرار گرفته باشد.
   - پارامتر `table_data` باید به صورت خودکار از `slide_data.get("table_data")` خوانده شود تا هیچ جدولی ناپدید نگردد.

---

### I. Reference-Accurate Table Reproduction Standards
1. **Exact Column Structure:**
   - Replicate the exact column count and header semantics of the slide/reference table.
2. **Merged Category Banners (نوار سرشاخه‌های ادغام‌شده):**
   - Major categories **MUST** be rendered as full-width banner rows spanning all columns using `cell_start.merge(cell_end)`.
   - Banner fill: Slate-blue (`#4A709C`), borders `#2C3E50`, text white bold 11pt (`#FFFFFF`).
3. **Palette Standards:**
   - Header row: Peach/Cream fill (`#F5EBE1`) with espresso brown bold text (`#5D4037`) and subtle vertical dividers (`#D5D8DC`).
   - Data rows: Alternating crisp white (`#FFFFFF`) and soft ivory (`#FDFBF7`) with light gray borders (`#E2E8F0`).
   - Bold lead terms: The key disease or hormone name at the start of each cell must be bolded.

---

### J. Bidirectional (BiDi) Text Sanitization & Preservation of Scientific Notation (مسیرهای بیوشیمیایی و فرمول‌ها)
1. **Preservation of Scientific Pathways & Equations:**
   - **Biochemical pathways and cascades:** `GPCR -> Gs -> Adenylyl Cyclase -> cAMP -> PKA`
   - **Chemical & physiological equations:** `CO2 + H2O <-> H2CO3 <-> H+ + HCO3-`
   - **Receptor notation & laboratory ranges:** `D2 -> Gi -> ↓cAMP`, `TSH > 10 mIU/L`, `Ca < 8.5 mg/dL`
   - **CRITICAL RULE:** Do NOT replace scientific arrows (`->`, `<->`) or inequality signs (`<`, `>`) with Persian words in chemical/biochemical notation!
   - Every scientific pathway, formula, unit (`mg/kg/day`), or dosage **MUST** be isolated inside an explicit `<w:rtl w:val="0"/>` LTR run so Microsoft Word preserves its exact directionality without character flipping.
2. **Narrative Text Arrow Sanitization:**
   - In ordinary conversational prose (e.g. «استرس -> ترشح کورتیزول»), replace volatile symbols with Persian words («استرس منجر به ترشح کورتیزول می‌شود»).
3. **Isolate Latin Acronyms in `w:rtl="0"` Runs:**
   - Split paragraphs using regex: `re.split(r'(\([A-Za-z0-9_\-\s,\./%αβγ><=↓↑]+\))', text)`.
   - Every English parenthetical run `(GPCR)`, `(ITT/OGTT)`, `(IGFBP-3)` MUST be set with `<w:rtl w:val="0"/>`.
4. **Strict No-Footnotes Policy:**
   - All medical abbreviations and Latin terms must appear inline in parentheses: e.g. `پرولاکتینوما (Prolactinoma)`. Zero bottom-of-page footnotes!

---

### J. Gemini Multimodal Audio Transcription Protocol & Strict Local STT Prohibition (پروتکل پیاده‌سازی صوت با جمینای و منع اکید نصب لوکال Whisper/CUDA)

> ⛔ **قانون حیاتی و خط قرمز سیستم (STRICT PROHIBITION):**
> هیچ ایجنتی تحت هیچ شرایطی حق ندارد پکیج‌های سنگین لوکال نظیر `whisper`، `faster-whisper`، `torch`، `nvidia-cudnn`، `nvidia-cublas`، `ctranslate2` یا بسته‌های درایور CUDA را دانلود، نصب یا اجرا کند!
> دانلود چند گیگابایتی این پکیج‌ها حجم اینترنت و فضای دیسک کاربر را هدر می‌دهد و تخلف صریح از معماری سیستم است. تبدیل فایل صوتی به متن منحصراً و همواره توسط **هوش مصنوعی جمینای (Gemini Multimodal)** انجام می‌گیرد.

#### چرخه استاندارد پیاده‌سازی صوت با جمینای:
1. **گام اول — خرد کردن صوت به چانک‌های سبک:**
   ```powershell
   uv run python scripts/run_pipeline.py chunk --audio lecture.m4a
   ```
   این اسکریپت فایل صوتی طولانی را به چانک‌های کوچک زیر ۱۰ مگابایت با همپوشانی ۱۰ ثانیه‌ای در پوشه `chunks/` تقسیم کرده و مانیفست `chunks_manifest.json` را می‌سازد.

2. **گام دوم — پیاده‌سازی چانک‌ها با مدل جمینای (یکی از دو روش زیر):**
   * **روش الف — مستقیم درون سشن آنتی‌گرویتی با ابزار `view_file` (روش پیشنهادی و پیش‌فرض ایجنت‌ها):**
     ابزار `view_file` به صورت مادری از فایل‌های باینری صوتی (`.m4a`, `.mp3`, `.wav`) تا سقف ۱۰۰ مگابایت پشتیبانی می‌کند.
     ایجنت به سادگی چانک‌های سبک را تک‌تک با `view_file(AbsolutePath=".../chunks/chunk_01.m4a")` مشاهده می‌کند. مدل جمینای کانتکست چندرسانه‌ای را مستقیماً می‌شنود و متن پیاده‌سازی‌شده کلمه به کلمه فارسی را همراه با اصطلاحات تخصصی انگلیسی و بازه زمانی تولید می‌کند.
     سپس ایجنت خروجی هر چانک را در `transcripts/part01.txt`، `transcripts/part02.txt` و... ذخیره می‌نماید.
   * **روش ب — پیاده‌سازی خودکار ابری با کلید جمینای:**
     چنانچه متغیر محیطی `GEMINI_API_KEY` در سیستم تنظیم شده باشد:
     ```powershell
     uv run python scripts/run_pipeline.py transcribe
     ```
     اسکریپت فوق‌سبک `transcribe_chunks.py` بدون نیاز به نصب حتی ۱ مگابایت کتابخانه خارجی (با استفاده از `urllib` استاندارد پایتون)، چانک‌ها را با مدل پرسرعت `gemini-2.0-flash` یا `gemini-1.5-flash` به صورت ابری در چند ثانیه پیاده‌سازی کرده و در `transcripts/` ذخیره می‌کند.
   * **روش ج — استفاده از متن آماده کاربر:**
     اگر کاربر قبلاً متن پیاده‌شده کلاس را در اختیار دارد، کافی است فایل متنی (`.md` یا `.txt`) را در پوشه قرار دهد تا با اجرای `prepare_transcripts.py` به فایل‌های `partXX.txt` تفکیک گردد.

---

### K. Mandatory Lecture Narrative & Two-Stage Anti-Omission Verification Gate (گیت دومرحله‌ای اعتبارسنجی پوشش ماهوی صوت)
In addition to slide alignment, Track 1 narrative text and audio timestamps must pass the strict, non-bypassable two-stage audio gate:
1. **Strict Audio Chronological Anchoring:**
   - H1 section headings and TOC table entries **MUST** carry timestamps that reflect the true start time of each topic / audio segment (e.g. `دقیقه ۰۰:۰۰`, `دقیقه ۰۹:۲۰`).
   - Timestamps must be formatted in Persian numeral text with deep orange font color (`#D35400`) and bold styling.
2. **Zero Timestamp Hallucination & Total Audio Duration Bound:**
   - Under no circumstances may an agent invent arbitrary timestamps exceeding the total recording length.
3. **The Three-Stage Anti-Omission Gate (گیت سخت‌گیرانه سه‌مرحله‌ای منع حذف مطالب):**
    - **مرحله اول — سنجش نسبت حجم کلمات گفتار (Word Volume Ratio $\ge$ 50% به عنوان Sanity Check):**
      استاندارد اصلی جزوه‌نویسی پزشکی، **حفظ ۱۰۰٪ تمامی مفاهیم و فکت‌های کلینیکی استاد** در کنار حذف کامل زوائد بیانی و پالایش زبان محاوره‌ای است. نسبت حجم کلمات (Word Volume Ratio >= 50%) به عنوان یک *گاردریل احتیاطی (Sanity Check)* عمل می‌کند تا از تلخیص‌های افراطی جلوگیری نماید، در حالی که گیت اصلی سنجش ماهوی، Stage 2 و Stage 4 است.
   - **مرحله دوم — نرخ بازیابی کلیدواژه‌های بالینی هر چانک (Strict Clinical Concept Recall Rate $\ge$ 60%):**
     الگوریتم به صورت خودکار واژگان تخصصی، اصطلاحات کلینیکی، اعداد مهم (مانند ۷٪ و ۱۰٪ اینسیدنتالوما، دوزها، مقادیر آزمایشگاهی) و داروهای هر چانک صوتی را استخراج کرده و الزام به بازیابی حداقل ۶۰٪ آنها در متن جزوه دارد (`recall_rate >= 0.60`). در صورت افت بازیابی به زیر ۶۰٪، گیت با ارور بحرانی `CRITICAL_CONCEPT_OMISSION` و نمایش لیست دقیق مفاهیمِ از قلم‌افتاده متوقف می‌شود.
   - **مرحله سوم — پوشش نگاشت چانک‌های صوتی (Audio Chunk Mapping Coverage $\ge$ 85%):**
     حداقل ۸۵٪ از چانک‌های صوتی با مدت زمان بیش از ۳۰ ثانیه (`--min-chunk-duration 30`) باید به بخش‌های جزوه نگاشت شده باشند.
     یک چانک **منحصراً زمانی نگاشت‌شده (Covered = PASS)** محسوب می‌شود که **هم** دارای تطابق زمانی مستقیم ($\pm 60$s) با تیتر بخش‌ها باشد و **هم** حداقل ۵۰٪ واژگان تخصصی آن چانک در متن منعکس شده باشد (`recall_ratio >= 0.50`).
     > **پروتکل مهار جابجایی زمانی (Temporal Concept Displacement Guard):**
     > اگر مفاهیم یک چانک در متن جزوه وجود داشته باشد اما فاقد تایم‌استمپ متناظر در بخش‌ها باشد (انحراف زمانی > ۶۰ ثانیه)، چانک به عنوان `TEMPORAL_CONCEPT_DISPLACEMENT` ثبت شده و در حالت پیش‌فرض Covered محسوب **نمی‌شود**؛ در نتیجه وضعیت به `REVIEW_REQUIRED` تبدیل شده و انتشار سند بدون بازبینی یا فلگ صریح `--allow-review` متوقف می‌گردد. همچنین تایم‌استمپ‌های صوری بدون انتقال مفاهیم چانک نیز به هیچ وجه مورد پذیرش گیت نخواهند بود.
   - **مرحله چهارم — گیت تطبیق مکانی-زمانی اسلاید و صوت (Slide-Level Spatio-Temporal Grounding & Fact Retention Gate):**
     این گیت به طور مستقیم مفاهیم ماهوی صوت متناظر با بازه زمانی هر اسلاید را با متن ریل ۱ (`spoken_lecture`) مقایسه می‌کند:      - **رهگیری خاستگاه زمانی (Dual Provenance Modes & Publication Standard):**
        - **Mode A (Timestamped Exact Grounding):** استاندارد الزامی برای چاپ و انتشار نهایی جزوه (`Certified Publication`). مبتنی بر سگمنت‌های دقیق زمانی استخراج‌شده از Gemini Multimodal یا فایل صوتی است (`temporal_confidence: "exact"`). از تبدیل خودکار تایم‌استمپ‌های محلی چانک به زمان جهانی پشتیبانی می‌کند.
        - **Mode B (Heuristic Estimated Grounding):** حالت جایگزین (Fallback) زمانی که صرفاً ترنسکریپت متنی بدون تایم‌استمپ‌های زیرثانیه‌ای در دسترس است. تقسیم زمانی را بر اساس دانسیته کاراکتر و پاراگراف‌ها تخمین می‌زند (`temporal_confidence: "estimated"`). این حالت در گزارش نهایی وضعیت `REVIEW_REQUIRED` ایجاد می‌کند تا کاربر بداند مرزبندی زمانی تخمینی است مگر آنکه با فلگ `--allow-review` تأیید شود.
        - **Mode Mixed:** در صورت ترکیب سگمنت‌های Mode A و Mode B در یک سند، خاستگاه به عنوان `mixed` ثبت می‌شود.
      - **آستانه‌های انطباقی پویا (Adaptive Lexical Thresholds):**
        - مدت زمان < ۳۰ ثانیه: حداقل ۳۵٪ بازیابی مفاهیم یا دقت لغوی ۱۵٪ همراه با حداقل ۲ مفهوم مشترک.
        - مدت زمان ۳۰ الی ۱۲۰ ثانیه: حداقل ۴۵٪ بازیابی مفاهیم و دقت لغوی ۲۰٪ با حداقل ۳ مفهوم مشترک.
        - مدت زمان > ۱۲۰ ثانیه: حداقل ۵۵٪ بازیابی مفاهیم و دقت لغوی ۲۵٪ با حداقل ۴ مفهوم مشترک.
        - *قانون منع عبور با همپوشانی حداقلی:* تعداد همپوشانی‌ها (`min_overlap`) به تنهایی نمی‌تواند اسلایدهای پرمفهوم را قبول کند؛ همپوشانی ماهوی شرط لازم است و باید با Recall یا Precision متناسب همراه باشد.
        - *قانون رد قطعی عدم تطابق صوتی:* اگر اسلایدی در بازه زمانی اعلام‌شده فاقد شواهد صوتی یا متن تدریس باشد، فوراً ارور بحرانی `SLIDE_AUDIO_NO_TEMPORAL_EVIDENCE` یا `SLIDE_SPOKEN_LECTURE_EMPTY` صادر می‌گردد (رفع خطای False PASS).
      - **ممیزی دومرحله‌ای فکت‌های بالینی (Two-Tier Clinical Fact Recall Audit):**
        - **سطح ۱ — حیاتی (Critical ERROR):** دوزهای دارویی (`25 mg`) و مقادیر حیاتی آزمایشگاهی/فشار خون (`120/80 mmHg`) در صورت حذف از متن اسلاید، خطای سخت `CLINICAL_FACT_CRITICAL_OMISSION` صادر کرده و مانع از قبولی گیت می‌شوند.
        - **سطح ۲ — مشورتی (Advisory WARNING):** درصدها، بازه‌های عددی و اعداد آماری در صورت جا افتادن، هشدار اولویت‌دار `CLINICAL_FACT_OMISSION` صادر می‌کنند.
      - **کنترل یکنواختی زمانی و ارجاعات ساختاری معتبر (Temporal Monotonicity & Structural Cross-References):**
        - پسرفت زمانی < ۱۵ ثانیه: نادیده گرفته می‌شود (همپوشانی طبیعی گفتار).
        - پسرفت ۱۵ الی ۶۰ ثانیه: هشدار (`warning`).
        - پسرفت > ۶۰ ثانیه: خطای سخت (`error`) مگر آنکه دارای ارجاع ساختاری معتبر باشد.
        - *فرمت اجباری ارجاع ساختاری:* تمامی ارجاعات در `cross_references[]` باید حتماً به صورت آبجکت ساختاریافته `[{"target_slide": N, "reason": "..."}]` باشند. متن‌های ساده یا عبارات غیرساختاریافته مردود شمرده می‌شوند و اسلاید مقصد باید در دامنه اسلایدهای ارائه موجود باشد.
4. **Mandatory Automated Gate Execution:**
   Before finalizing the document, run:
   ```powershell
   uv run --with python-docx python scripts/verify_lecture_alignment.py --docx <path_to_docx> --transcripts-dir <path_to_transcripts> [--translated translated_slides.json] [--strict-drift] [--max-drift 60] [--allow-review]
   ```
   - **`--strict-drift`**: سقف انحراف زمانی را در کل سخنرانی به ۶۰ ثانیه محدود می‌کند (ایده‌آل برای کلاس‌های طولانی با نیاز به سینک لحظه‌ای).
   - **`--max-drift <seconds>`**: مقدار حداکثر تلورانس مجاز انحراف زمانی را به صورت عددی دستی تنظیم می‌کند.
   - **`--allow-review`**: در صورت بروز خطای عدم تطابق، بیلد را متوقف نمی‌کند و سند Word را همراه با برچسب‌های هشدار کهربایی برای بازبینی دانشجو صادر می‌نماید.

5. **Certified Publication vs Rendering (تفاوت build و publish):**
   - **`run_pipeline.py build`:** صرفاً جهت رندر و تولید فایل اولیه ورد (`.docx`) از روی اسلایدهای ترجمه‌شده (با فلگ اختیاری `--verify`).
   - **`run_pipeline.py publish`:** **مسیر اجباری و استاندارد انتشار نهایی و معتبر جزوه (Certified Publication)** است که چرخه تضمین کیفیت کامل (اعتبارسنجی اسلاید -> ساخت ورد -> اعتبارسنجی صوت) را الزامی می‌کند:
   ```powershell
   uv run python scripts/run_pipeline.py publish --output lecture_pamphlet.docx
   ```

---

### L. Academic Prose Formalization & Spoken Lecture Editorial Protocol (پروتکل ویراستاری آکادمیک و تبدیل صوت به نثر روان و فاخر دانشگاهی)
هدف ریل ۱ (`spoken_lecture`) ارائه یک متن مطالعه دانشگاهی روان، منسجم، شیوا و خواندنی برای دانشجویان پزشکی است؛ بنابراین تحت هیچ شرایطی نباید گفتار صوتی به صورت خام، محاوره‌ای و تکراری پیاده شود.
1. **قانون تبدیل افعال شکسته به نوشتاری معیار (Colloquial Verb Elimination):**
   - تمامی افعال شکسته محاوره‌ای اکیداً ممنوع بوده و باید به افعال رسمی معیار تبدیل شوند:
     - «می‌شه / نمی‌شه» $\rightarrow$ «می‌شود / نمی‌شود / می‌گردد»
     - «می‌شن / نمی‌شن» $\rightarrow$ «می‌شوند / نمی‌شوند»
     - «دارن / ندارن» $\rightarrow$ «دارند / ندارند»
     - «می‌کنن» $\rightarrow$ «می‌کنند / می‌نمایند»
     - «می‌خوایم / می‌خواد» $\rightarrow$ «می‌خواهیم / درصدد است»
     - «می‌ریم / می‌دم» $\rightarrow$ «می‌رویم / می‌پردازیم / ارائه می‌دهیم»
2. **پالایش زوائد بیانی و تپق‌های محاوره‌ای (Verbal Filler Elimination):**
   - حذف کامل واژگان پرکننده کلامی نظیر: «ببینید»، «خب»، «در واقع»، «به اصطلاح»، «عرضم به حضورتون»، «یعنی اینکه می‌دونیم»، «اینا/اونا».
3. **اصل بقای مفاهیم و اعداد بالینی (Medical Concept Invariance):**
   - ویراستاری ادبی نباید هیچ‌گونه آسیبی به اصطلاحات پزشکی، دوزها، درصدها، نام داروها و مفاهیم ترنسکریپت صوتی بزند.
   - تمامی اصطلاحات انگلیسی/لاتین، نام گیرنده‌ها (مانند $G_s\alpha$، PKA، cAMP، JAK/STAT)، مقادیر آماری (نظیر ۷٪ و ۱۰٪ اینسیدنتالوما) و اسامی بیماری‌ها باید عیناً در بطن متن روان گنجانده شوند تا نمره گیت Concept Recall و Word Ratio در بالاترین سطح باقی بماند.
4. **ساختاربندی پیوسته و یکپارچگی نحوی (Syntactic Flow & Cohesion):**
   - جملات مقطع و بریده‌بریده به پاراگراف‌های منسجم، مستدل و ساختاریافته پزشکی با حروف ربط مناسب («از منظر پاتوفیزیولوژی...»، «در رویکرد بالینی...»، «نکته حائز اهمیت آنکه...») تبدیل می‌شوند.
5. **گیت خودکار کنترل نثر آکادمیک (Automated Academic Prose Advisory):**
   - اسکریپت `verify_lecture_alignment.py` به صورت خودکار افعال شکسته و زوائد محاوره‌ای را رصد کرده و در صورت وجود، اخطار `COLLOQUIAL_PROSE_ADVISORY` صادر می‌کند.

---

### M. Autonomous Auto-Remediation Loop & Safe Fallback Boundaries (حلقه خودترمیمی هوشمند و مرزبندی اصلاحات)
1. **Dual Diagnostic Reporting:**
   - Both verification scripts generate machine-readable JSON reports:
     - `alignment_diagnostic_slides.json`
     - `alignment_diagnostic_lecture.json`
   - Each error entry includes an explicit `remediation_action` and human-readable hints in the console.
2. **The 3-Attempt Self-Healing Budget (حداکثر ۳ تلاش اصلاح خودکار):**
   - The agent reads the diagnostic JSON and applies the corresponding repair autonomously (up to 3 iterations):
     - **Slide Gap (`INDEX_GAP`):** Run `verify_slide_alignment.py --auto-fix` or inject missing page review boxes from `raw_slides.json`.
     - **Slide Shift (`OFFSET_SHIFT`):** Adjust slide numbers starting at the shift origin by the calculated offset delta.
     - **Topic-Audio Mismatch:** Re-anchor the section's H1 timestamp to the transcript chunk file where the topic was actually detected.
3. **Safe Auto-Fix Boundaries (منع کلمپ کورکورانه و پنهان‌سازی خطا):**
   - **Deterministic fixes ONLY:** Auto-fix is permitted for missing page indexes and timestamp formatting.
   - **NO SILENT CLAMPING:** If a timestamp drift exceeds 3 minutes (`180s`), the script will **NOT** silently clamp it to the end of the audio. It must be semantically re-anchored to the correct audio chunk or marked with an Amber Review Badge.
4. **Three-State Execution Lifecycle & Controlled Fallback Badging (چرخه ۳ وضعیتی اجرای پایپ‌لاین):**
   - **State 1: `PASSED` (تایید نهایی انتشار):**
     تمامی ۴ گیت با موفقیت و بدون خطای سخت تایید می‌شوند. جزوه برای انتشار دانشگاهی ۱۰۰٪ معتبر است.
   - **State 2: `REVIEW_REQUIRED` (حالت بازبینی انسانی با `--allow-review`):**
     اگر پس از ۳ تلاش خودکار همچنان ناسازگاری حل‌نشده باقی بماند، اجرای پایپ‌لاین با پرچم صریح `--allow-review` متوقف نمی‌شود و خروجی Word را با برچسب‌های هشدار کهربایی دانشجو (`add_student_review_badge`) روی اسلایدهای مشکل‌دار تولید می‌کند.
   - **State 3: `FAILED_HARD` (توقف سخت بیلد به صورت پیش‌فرض):**
     به صورت پیش‌فرض (بدون `--allow-review`)، بروز هرگونه خطای تطابق زمانی، اسلایدی یا صوتی باعث خروج با کد خطای ۱ (`Document generation ABORTED`) می‌شود تا از انتشار خاموش متون اعتبارسنجی‌نشده جلوگیری شود.


---

### M. Pipeline Operation Modes (تفکیک مودهای عملیاتی پایپ‌لاین و جایگاه اسکریپت‌ها)
این اسکیل دارای دو حالت کاری کاملاً تفکیک‌شده است:
1. **Mode A — Native Complete Study Guide Pipeline (حالت پیش‌فرض و استاندارد):**
   - اسکریپت‌های `extract_presentation.py` -> `chunk_audio.py` -> `verify_slide_alignment.py` -> `verify_lecture_alignment.py` -> `create_slide_pamphlet.py` به صورت یکپارچه اجرا می‌شوند.
   - خروجی این مود، یک سند کامل Word با ریل‌های دوگانه (تدریس کلاسی استاد + کادرهای تفکیک‌شده ترجمه اسلاید) است.
2. **Mode B — Post-hoc Slide Annotation Mode (`annotate_docx.py`):**
   - این حالت **صرفاً و منحصراً** برای سناریوهایی است که دانشجو از قبل یک فایل Word حاوی اسلایدهای ارائه دارد و مایل است بدون بازنویسی کل سند، صرفاً کادرهای حاشیه‌ایِ حاوی نکات تدریس یا ترجمه را به صورت تزریقی (Injection) در بالا یا پایین هر اسلاید درج کند.
   - در حالت استاندارد Mode A، هرگز نباید از `annotate_docx.py` استفاده شود زیرا `create_slide_pamphlet.py` خود سند نهایی را به صورت کامل می‌سازد.

---

### N. Central Pipeline Orchestrator (`run_pipeline.py`)
برای جلوگیری از خطای ترتیب اجرای اسکریپت‌ها و نظارت بر چرخه کامل، از ارکستریتور مرکزی استفاده کنید:
```powershell
# 1. مشاهده داشبورد وضعیت و گام بعدی پیشنهادی
uv run python scripts/run_pipeline.py status

# 2. استخراج اسلایدها و تصاویر
uv run python scripts/run_pipeline.py extract --presentation slides.pdf

# 3. قطعه‌بندی هوشمند صوت با همپوشانی ایمن
uv run python scripts/run_pipeline.py chunk --audio lecture.m4a

# 4. پیاده‌سازی هوشمند صوت با جمینای (یا مشاهده تک‌تک چانک‌ها با view_file در سشن چت)
# ⛔ اکیداً ممنوع: هرگز Whisper یا بسته‌های CUDA لوکال را نصب نکنید!
uv run python scripts/run_pipeline.py transcribe

# 5. اعتبارسنجی انطباق اسلایدها قبل از ساخت سند
uv run python scripts/run_pipeline.py verify-slides

# 6. ساخت سند نهایی با تشخیص خودکار کتاب مرجع رشته
uv run python scripts/run_pipeline.py build --output lecture_pamphlet.docx

# 7. اعتبارسنجی جامع انطباق صوت و گفتار روی سند ساخته‌شده
uv run python scripts/run_pipeline.py verify-lecture --docx lecture_pamphlet.docx

# 💡 یا اجرای یکجای کل چرخه گواهی‌شده (Verify Slides -> Build -> Verify Lecture):
uv run python scripts/run_pipeline.py publish --output lecture_pamphlet.docx

# 7. (حالت Mode B) تزریق ساختاریافته نکات به سند موجود
uv run python scripts/run_pipeline.py annotate --docx slides.docx --annotations notes.json --output annotated_pamphlet.docx
```

---

### O. Strict Batch Size Limit & Semantic Drift Prevention Protocol (سقف اندازه دسته‌های ترجمه و منع انحراف معنایی)
1. **The Semantic Drift Trap in Large Batches (انحراف معنایی در دسته‌های حجیم):**
   - هنگامی که ایجنت در یک پرامپت منفرد اقدام به ترجمه ۳۰ تا ۵۰ اسلاید به صورت یکجا می‌کند، مدل پس از اسلاید ۲۰ دچار خستگی توجه (Attention Fatigue) شده و به جای وفاداری به متن اسلاید خام، شروع به انحراف معنایی (Semantic Drift) و جایگزین کردن متون اصلی با تئوری‌های کلی کتاب مرجع می‌کند.
   - این پدیده علت اصلی خطاهای عدم تطابق (`OFFSET_SHIFT` و صفر شدن همپوشانی توکن‌ها) در گیت اعتبارسنجی است.
2. **Mandatory Batch Size Limit (سقف قطعی حداکثر ۱۰ تا ۱۵ اسلاید در هر نوبت):**
   - ایجنت‌ها **موظفند** اسلایدها را در دسته‌های کوچک حداکثر ۱۰ تا ۱۵تایی ترجمه کرده و در فایل JSON ذخیره نمایند (مثلاً اسلایدهای ۱ تا ۱۵، سپس ۱۶ تا ۳۰ و...).
3. **Strict Lexical Grounding to `raw_slides.json`:**
   - هر بالت فارسی در `translated_slides.json` باید دقیقاً ترجمه وفادارانه یکی از سطرهای `text_lines` در `raw_slides.json` (یا استخراج چشمی تصویر برای اسلایدهای تصویری) باشد. تغییر خودسرانه ساختار و متون اسلایدها اکیداً ممنوع است.

---

### P. Ceremonial & Non-Academic Slide Protocol & Anti-Cascade Guard (پروتکل اسلایدهای تشریفاتی و محافظ ضد جابجایی زنجیره‌ای)
1. **The Ceremonial Slide Failure Mode (ریشه‌یابی خطای اسلایدهای غیردرسی):**
   - اسلایدهای ابتدایی یا انتهایی شامل «بسم الله الرحمن الرحیم»، «صلوات»، «ادای احترام به شهدا»، «صفحه خوش‌آمدگویی»، «اسلاید تشکر پایانی» یا «عنوان صرف درس بدون متن آموزشی»، ماهیت تشریفاتی/غیردرسی دارند و استاد معمولاً روی آنها صحبت تخصصی نمی‌کند.
   - **خطای فاجعه‌بار جابجایی زنجیره‌ای (Cascade Displacement):** اگر ایجنت تصور کند این اسلایدها نیز باید حتماً بالت درسی داشته باشند، شروع به «پیش‌خور کردن» مباحث اسلایدهای بعدی (مثلاً تعاریف بیماری، تاریخچه کشف یا اهداف آموزشی) روی اسلاید ۱ یا ۲ می‌کند. در نتیجه، وقتی به اسلاید ۳ می‌رسد، متن اسلاید ۴ را می‌زند و کل اسلایدهای جزوه دچار شیفت زنجیره‌ای (`OFFSET_SHIFT`) نسبت به پاورپوینت اصلی می‌شوند!
2. **Mandatory Ceremonial Flag (`is_ceremonial: true`):**
   - برای هر اسلاید تشریفاتی یا مقدماتی، ایجنت **موظف است** در `translated_slides.json` خصوصیت `"is_ceremonial": true` را درج کند.
   - گیت اعتبارسنجی (`verify_slide_alignment.py`) اسلایدهای دارای `"is_ceremonial": true` یا حاوی کلیدواژه‌های تشریفاتی (بسم الله، صلوات، شهدا، تشکر، welcome و...) را به طور کامل از الزام `ref_note` در Check 4 و خطاهای توهم پارامتریک در Check 3 معاف می‌دارد.
3. **Strict Prohibition of Pedagogical Hallucination on Ceremonial Slides:**
   - **اکیداً ممنوع:** درج هرگونه مفهوم پزشکی، فیزیولوژی، پاتولوژی، اهداف آموزشی، یا تاریخچه اختراعات/اکتشافات روی اسلایدهای تشریفاتی اکیداً ممنوع است.
   - محتوای بالت‌های اسلاید تشریفاتی باید خالی `[]` یا صرفاً شامل همان متن عینی احترام/تشریفات باشد.
4. **Ceremonial Slide JSON Specification:**
   ```json
   {
     "slide_number": 1,
     "title_fa": "بسم الله الرحمن الرحیم",
     "title_en": "In the Name of God",
     "is_ceremonial": true,
     "is_skipped": true,
     "bullets": []
   }
   ```
5. **Word Document Rendering Protocol:**
   - اسلایدهای تشریفاتی در خروجی Word با یک کادر سبک، شکیل و نشان آرام `[اسلاید تشریفاتی / مقدماتی]` رندر می‌شوند. برچسب هشداردهنده نارنجی `[⚠️ تدریس‌نشده در کلاس]` برای آنها درج نخواهد شد.

### Q. Markdown Sanitization, Continuous Prose Reflow & Word Justification Protocol (پروتکل پالایش مارکداون و تراز دوطرفه زیبا)

1. **علت ریشه‌ای شکستگی خطوط و به‌هم‌ریختگی جاستیفای در Word:**
   - مدل‌های پیاده‌ساز صوت (Transcribers) خروجی را با مارکداون (`###`, `####`, `**نکته:**`, `- `) و اینترهای تک‌خطی (`\n`) میان جملات تولید می‌کنند.
   - ورود کاراکتر `\n` به درون ران‌های متنی Word (`<w:t>`) باعث ایجاد شکستگی نرم (Soft Break / Shift+Enter) می‌شود.
   - هنگامی که کاربر در نرم‌افزار Word متن را جاستیفای (Justify / تراز دوطرفه) می‌کند، سطر منتهی به `\n` توسط موتور Word به شکلی ناهنجار در سراسر عرض صفحه کشیده شده و فواصل غول‌آسا میان کلمات ایجاد می‌شود!
2. **پروتکل بازچیدمان پیوسته نثر (Continuous Prose Reflow):**
   - خطوط متوالی متن گفتار کلاسی استاد که با یک اینتر معمولی (`\n`) از یکدیگر جدا شده‌اند، باید به یک پاراگراف پیوسته و روان تبدیل شوند و با یک فاصله معمولی (`" ".join(lines)`) به هم متصل گردند.
   - **قانون تخطی‌ناپذیر:** هیچ ران متنی درون فایل Word نباید حاوی کاراکتر `\n` یا `\r` باشد (`0 Soft Breaks in Runs`).
3. **پالایش کامل کاراکترهای مارکداون (Zero Markdown Artifacts):**
   - تمامی کاراکترهای مارکداون خام نظیر `*`, `**`, `###`, `####` و سربرگ‌های قالبی ترنسکریپت (مانند `#### بیانات استاد:`) باید پیش از رندر در Word کاملاً پالایش شوند.
   - عناوین فرعی معنادار با `add_h2` (رنگ سبز یشمی `#0E6251` بولد)، بالت‌ها با `add_bullet_p` و متون برجسته با ران‌های واقعاً بولد (`bold=True`) بدون نشانه‌های `**` رندر می‌شوند.
4. **تراز دوطرفه استاندارد (Flawless Word Justification):**
   - تمامی پاراگراف‌های بدنه، متن گفتار استاد، بالت‌های اسلاید و شرح رفرنس‌ها با `p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.JUSTIFY` تنسیق می‌شوند.
   - به دلیل حذف کامل Soft Breakها، جاستیفای در Word با فواصل متوازن، ظریف و بدون کشیدگی ناهنجار نمایش داده می‌شود.

### R. Multi-Slide Lecture Cluster Architecture & Deduplication Protocol (پروتکل کلاستربندی تدریس چنداسلایدی و حذف هوشمند تکرارها)

1. **ریشه‌یابی و مفهوم کلاستر چنداسلایدی (Multi-Slide Vignette):**
   - در کلاس‌های پزشکی، استاد غالباً یک مبحث بالینی یا الگوریتم درمانی پیوسته را در طول چندین اسلاید متوالی (مثلاً اسلایدهای ۷ تا ۱۰) تشریح می‌کند.
   - اجبار ناصحیح به درج گفتار مجزا روی تک‌تک اسلایدها در نسخه‌های اولیه باعث دو عارضه ناخواسته می‌شد:
     - الف) کپی-پیست بیهوده متن یکسان در چند اسلاید متوالی توسط مدل‌ها جهت فرار از ارور `SLIDE_SPOKEN_LECTURE_EMPTY`.
     - ب) رندر نابینا و ۴ باره همان متن بلند گفتار استاد قبل از هر کادر اسلاید در فایل مایکروسافت ورد!
2. **پشتیبانی رسمی گیت اعتبارسنجی از کلاسترها (`parent_lecture_slide`):**
   - برای اسلایدهایی که ادامه‌دهنده تدریس یک مبحث مشترک هستند، کافی است در `translated_slides.json` فیلد `"parent_lecture_slide": N` (که N شماره اسلاید سرگروه کلاستر است) قید شود.
   - گیت `verify_lecture_alignment.py` به طور خودکار بازه زمانی (`audio_time_range`) و متن تدریس (`spoken_lecture`) را از اسلاید سرگروه به ارث می‌برد.
   - اسلایدهای کلاستر مشمول معافیت از پسرفت زمانی (`is_cluster_continuation`) بوده و هرگز دچار خطای کاذب `TEMPORAL_MONOTONICITY_REGRESSION` نمی‌شوند.
3. **دفاع هوشمند و خودکار موتور رندر Word در برابر تکرار (Smart Deduplication):**
   - موتور رندر در `create_slide_pamphlet.py` به صورت پویا متن گفتار هر اسلاید را مانیتور می‌کند:
     - چنانچه متنی دقیقاً با گفتار اسلاید قبلی یکسان باشد یا اسلاید دارای `parent_lecture_slide` باشد، از رندر مجدد بنر `🎙️ تدریس و بیانات کلاسی استاد` خودداری می‌کند.
     - کادر اسلایدهای بعدی مستقیماً و با چیدمانی آکادمیک زیر همان متن جامع تدریس قرار می‌گیرند (دقیقاً مشابه ساختار طبیعی تدریس کلاسی دانشگاهی).

### S. Format-Agnostic Image-Text Extraction, Multimodal Evidence Grounding & Scanned Table Detection Protocol (پروتکل استخراج متن از تصاویر اسلاید، اعتبارسنجی شواهد چندوجهی و کشف جداول اسکن‌شده)

1. **ریشه‌یابی و آسیب‌شناسی اسلایدهای تصویری و کلاسترهای فاقد متن لایه دیجیتال:**
   - در اسلایدهای بالینی و پاتولوژی (مانند اسلایدهای عکس میکروسکوپی، دیاگرام‌ها یا جداول اسکن‌شده کتاب رابینز)، فایل‌های ورودی PDF یا PPTX فاقد لایه متن دیجیتال (`text_lines: []`) هستند، در حالی که اسلاید دارای کپشن، لیبل‌های بالینی، یا جداول تشخیصی اسکن‌شده به زبان انگلیسی است.
   - اعمال کورکورانه گیت ضدتوهم (`PHANTOM_CONTENT_HALLUCINATION`) در نسخه‌های قبلی باعث می‌شد که اگر مدلی کپشن‌های درون عکس را ترجمه می‌کرد، گیت به دلیل خالی بودن متن دیجیتال کل بالت‌ها را پاک کند!
   - همچنین اگر اسلاید در یک کلاستر قرار داشت (`parent_lecture_slide`)، گفتار استاد بیرون کادر نمی‌آمد و بالت‌ها هم درون کادر حذف می‌شدند و کادر اسلاید کاملاً خالی (سفید) باقی می‌ماند.
   - علاوه بر این، جداول تصویری اسکن‌شده (مانند جدول ۲-۲۰ معیارهای دیابت رابینز) به دلیل برداری نبودن، شناسایی نمی‌شدند (`has_tables: false`).

2. **معماری استخراج دورگه چندوجهی مبتنی بر محتوای بصری (Visual-Aware Hybrid Extraction):**
   - **اسلایدهای صرفاً متنی (Pure Text Slides):** اگر اسلاید کاملاً فاقد المان‌های بصری (بدون تصویر، بدون چارت، بدون SmartArt و بدون جدول) باشد، برای بهینه‌سازی سرعت، پردازش سریع متنی انجام شده و OCR اجرا نمی‌شود.
   - **اسلایدهای حامل المان‌های دیداری (Visual-Bearing Slides):** هر اسلایدی که حامل هرگونه المان بصری (تصویر، نمودار، چارت، SmartArt یا جدول) باشد، فارغ از تعداد کلمات لایه دیجیتال، الزاماً مشمول استخراج OCR می‌گردد تا هیچ لیبل پاتولوژی یا متنی درون تصاویر نادیده گرفته نشود.
   - **اسلایدهای با متن دیجیتال اندک (< 5 کلمه یا خالی):** جهت پوشش تصاویر اسکن‌شده، خودکار وارد موتور OCR می‌شوند.
   - **آستانه اطمینان آماری OCR:** در صورتی که میانگین اطمینان OCR حداقل ۰.۶۰ و شامل حداقل ۲ توکن باشد، اسلاید با برچسب‌های `has_image_text: true` و `is_image_text_bearing: true` ثبت می‌گردد. در صورت عدم قطعیت، پرچم `ocr_uncertain: true` و `needs_student_review: true` صادر می‌شود.

3. **پروتکل کشف جداول اسکن‌شده و برداری (`page.find_tables()` & Scanned Table Detection):**
   - در فایل‌های PDF و PPTX، ساختارهای جدولی با استفاده از قابلیت تحلیل ساختاری (`page.find_tables()` در PyMuPDF) و شناسایی ردیف‌ها بررسی می‌شوند.
   - در صورت کشف جدول ساختاری یا اسکن‌شده، فیلد `has_image_table: true` تنظیم می‌شود.
   - گیت `verify_slide_alignment.py` وجود جدول را بررسی کرده و در صورت نبود آرایه `table_data` در `translated_slides.json`، خطای هشداردهنده `MISSING_TABLE_DATA` صادر می‌کند تا مانع از قلم افتادن جداول کلیدی رفرنس در جزوه شود.

4. **اعتبارسنجی متوازن ترجمه بالت‌ها در گیت ۳.۱ (`verify_slide_alignment.py`):**
   - واژگان مرجع اسلاید (`raw_tokens`) از تجمیع متن لایه دیجیتال (`raw_lines`) به همراه متن استخراج‌شده توسط OCR (`ocr_text_lines`) با ریشه ۸ کاراکتری زبان پزشکی اعتبارسنجی می‌شوند.
   - خطای `PHANTOM_CONTENT_HALLUCINATION` برای اسلایدهای حامل متن تصویری (`is_image_text_bearing`) غیرفعال بوده و منحصراً بر روی اسلایدهای صددرصد فاقد متن دیجیتال و OCR (`pure_visual`) که بالت‌های خودساخته دارند اعمال می‌شود.
   - **قانون اسلایدهای تصویری فاقد متن (Pure Visual):** برای تصاویر و لام‌های میکروسکوپی خالص که هیچ متنی در اسلاید یا عکس ندارند، مدل نباید متن یا بالتی از خود اختراع کند؛ شرح بیانات کلاسی استاد (`spoken_lecture`) و تصویر اسلاید برای تفهیم مبحث کفایت می‌کند.

### T. Substantive Slide Recall Gate, Temporal Topic Displacement & Slide Text Immutability Protocol (پروتکل گیت پوشش ماهوی اسلاید، انحراف زمانی موضوعی و عدم‌دستکاری متن اسلاید)

1. **انسداد قطعی نقطه کور تطابق عنوان (Closing Title-Match Blindspots):**
   - در نسخه‌های اولیه، اگر عنوان انگلیسی اسلاید دارای چند واژه مشترک با سرعنوان اسلاید استاد بود (`common = raw_tokens.intersection(trans_tokens)` و `len(common) > 0`)، گیت اعتبارسنجی اسلاید را تایید می‌کرد؛ حتی اگر ۴ بالت اصلی اسلاید کاملاً از قلم افتاده یا با جملات کلی جایگزین شده بودند (مانند باگ اسلاید ۷۹)!
   - **قانون پوشش ماهوی ۵۰٪ (The 50% Substantive Recall Mandate):** برای تمامی اسلایدهایی که دارای حداقل ۴ توکن ماهوی در متن یا OCR هستند (`len(raw_tokens) >= 4`)، نسبت اشتراک واژگان باید حداقل ۵۰٪ باشد:
     $$\text{Slide Recall Ratio} = \frac{|\text{raw\_tokens} \cap \text{trans\_tokens}|}{|\text{raw\_tokens}|} \ge 0.50$$
   - در صورت عدم احراز این آستانه، خطای سخت‌گیرانه `SLIDE_SUBSTANTIVE_RECALL_DEFICIENCY` صادر شده و پایپ‌لاین را متوقف می‌سازد.

2. **تفکیک منشأ توکن‌های مفقوده در گزارش تشخیصی (Source-Aware Diagnostics):**
   - سیستم دقیقاً مشخص می‌کند که چه کلمات کلیدی پزشکی از قلم افتاده‌اند (`missing_tokens`).
   - منشأ کمبود بین دو دسته تفکیک می‌شود:
     - `missing_from_translation`: کلمات در متن لایه دیجیتال اسلاید وجود داشته‌اند اما مترجم آنها را نادیده گرفته است.
     - `missing_from_source_extraction`: کلمات از لایه OCR استخراج شده‌اند و اسلاید نیازمند دقت بیشتری در خواندن علائم تصویری است.

3. **پروتکل تخطی‌ناپذیر عدم‌دستکاری متن اسلاید (Slide Text Immutability):**
   - **قانون بنیادین:** کادر اسلاید منحصراً باید ترجمه مستقیم، وفادارانه و کلمه‌به‌کلمه همان اسلاید استاد باشد.
   - هیچ ابزار یا مدلی حق ندارد برای جبران کسری پوشش یا پر کردن کادر، اطلاعاتی از بیانات استاد (`audio`)، کتاب‌های رفرنس (`textbook`)، اسلایدهای دیگر، یا دانش پیش‌فرض خود به درون کادر اسلاید تزریق کند (`Zero In-Slide Hallucination / Enrichment`).
   - بیانات و نکات شفاهی استاد منحصراً در ریل ۱ (`spoken_lecture`) و بیرون کادر اسلاید قرار می‌گیرند. متن ترجمه اسلاید کاملاً غیرقابل‌تغییر خودکار (`Immutable`) است.

4. **ممیزی انحراف زمانی موضوعی مبتنی بر صوت (Audio-Grounded Temporal Topic Displacement):**
   - در Stage 4، سیستم با استفاده از نگاشت زمانی واقعی صوت، مفاهیم کلاسی تدریس‌شده در بازه زمانی اسلاید N (`candidate_substantive`) را با مباحث اسلایدهای مجاور (پنجره N±1 و N±2) مقایسه می‌کند.
   - چنانچه مفاهیم صوتی در زمان اسلاید N با اسلاید مجاور M حداقل ۲ برابر بیشتر از خود اسلاید N همپوشانی داشته باشند و همپوشانی با خود اسلاید N ضعیف باشد (کمتر از ۳۰٪)، هشدار تشخیصی `TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY` صادر می‌شود تا تنظیم زمان‌بندی یا تقدم و تاخر گفتار استاد بررسی گردد، بدون آنکه تغییری در متن اسلایدها داده شود.

### U. Visual-Aware OCR, Statistical Confidence Thresholding, Bilingual Concept Recall & Strict Hard-Fail Enforcement (v4.9.1)

1. **معماری هوشمند فراخوانی OCR مبتنی بر المان‌های بصری (Visual-Aware OCR Triggering):**
   - شرط قدیمی `total_words < 5` به طور کامل اصلاح گردید. اسلایدهایی که دارای عنوان یا متن متراکم همراه با تصویر پاتولوژی، نمودار، چارت، دیاگرام، یا جدول هستند (مانند اسلایدی با ۲۰ کلمه عنوان و ۱۵ لیبل داخل تصویر)، از اجرای OCR محروم نمی‌شوند.
   - **قانون فعال‌سازی OCR:** برای هر اسلاید دارای محتوای بصری (`has_images` یا `has_charts` یا `has_smartart` یا `has_tables`) یا متن دیجیتال کم (`total_words < 5` یا `text_empty`)، موتور OCR به صورت خودکار فراخوانی می‌شود.
   - **صرفه‌جویی محاسباتی:** OCR صرفاً برای اسلایدهای کاملاً متنی بدون کوچک‌ترین المان تصویری/جدولی خاموش می‌شود.

2. **سقف آماری قطعیت OCR و پرچم عدم قطعیت (Statistical OCR Confidence Thresholding):**
   - شناسایی تصادفی یک نویز یا کاراکتر با اطمینان پایین (مثلاً ۰.۴۱) دیگر باعث معافیت کورکورانه اسلاید از گیت ضدتوهم (`PHANTOM_CONTENT_HALLUCINATION`) نمی‌شود.
   - وضعیت `has_image_text: true` و `is_image_text_bearing: true` صرفاً در صورتی صادر می‌شود که:
     $$\text{mean\_confidence} \ge 0.60 \quad \text{AND} \quad \text{substantive\_tokens} \ge 2 \quad (\text{یا حداقل یک توکن قطعی با } \text{conf} \ge 0.70)$$
   - در موارد بینابینی و مشکوک، پرچم `ocr_uncertain: true` و `needs_student_review: true` ثبت شده و اسلاید نیازمند بازبینی چشمی دانشجو اعلام می‌گردد.

3. **تفکیک جداول برداری دیجیتال از جداول اسکن‌شده تصویری (Native vs. Scanned Table Separation):**
   - تابع `page.find_tables()` در PyMuPDF برای تمامی صفحات دارای ساختار جدولی مقدار `has_tables: true` ثبت می‌کند.
   - اما مقدار `has_image_table: true` منحصراً برای صفحاتی ثبت می‌شود که متن دیجیتال ندارند (`len(raw_lines) == 0`) یا تصویر اسکن‌شده هستند؛ جداول برداری دیجیتال دارای `has_image_table: false` خواهند بود.

4. **گیت انحصار منبع و منع محتوای فاقد پشتوانه در کادر اسلاید (Source Exclusivity & Unsupported Slide Box Content Gate):**
   - گیت بازخوانی ۵۰٪ (Recall Gate) بررسی می‌کند که حداقل نیمی از واژگان اسلاید ترجمه شده باشند (جهت Source $\to$ Translation).
   - اما گیت جدید انحصار منبع (Source Exclusivity Gate) جهت معکوس را ممیزی می‌کند (Translation $\to$ Source):
     آیا مترجم مفاهیم تکنیکال، رژیم‌های دارویی، دوزاژها، یا ادعاهای بالینی اضافه از رفرنس یا حدسیات خود به درون کادر اسلاید تزریق کرده است؟
   - اگر کادر اسلاید (Track 2) حاوی ۴ مفهوم تکنیکال یا بیشتر باشد که در هیچ کجای اسلاید خام (دیجیتال یا OCR) وجود نداشته‌اند، خطای قطعی `UNSUPPORTED_SLIDE_BOX_CONTENT` صادر شده و پایپ‌لاین متوقف می‌شود.
   - **قانون:** نکات و اضافات کتاب مرجع باید در `ref_note` (ریل ۳) و توضیحات کلاسی در `spoken_lecture` (ریل ۱) درج شوند؛ کادر اسلاید ۱۰۰٪ اختصاصی و تغییرناپذیر است. همچنین فیلد اختیاری `source_refs` برای نگاشت دقیق سطرها در صورت استفاده اعتبارسنجی ساختاری می‌شود.

5. **سپر ضد هشدار کاذب برای جابه‌جایی زمانی سرفصل‌ها (Lexical Guard for Temporal Topic Displacement):**
   - در موضوعات بسیار نزدیک (مثلاً اسلاید ۷: هورمون‌های تیروئید و اسلاید ۸: سنتز هورمون‌های تیروئید)، اشتراک کلمات بالا است.
   - شرط جابه‌جایی زمانی ارتقا یافت: هشدار `TEMPORAL_TOPIC_DISPLACEMENT_ADVISORY` فقط در صورتی صادر می‌شود که همپوشانی با اسلاید مجاور $\ge 4$ و $\ge 2\times$ اسلاید جاری باشد **و** همپوشانی بازه صوتی با خود اسلاید جاری ضعیف باشد ($\le 30\%$ مفاهیم صوتی). اگر صوت به خوبی با اسلاید جاری تطابق داشته باشد، هشدار کاذب داده نخواهد شد.

6. **خط‌مشی سرسختانه خطاهای غیرقابل‌ردکردن (Non-Bypassable Hard-Fail Policy for `--allow-review`):**
   - فلگ `--allow-review` به هیچ عنوان نمی‌تواند خطاهای ساختاری فاجعه‌بار را دور بزند.
   - خطاهای زیر همواره خروج قطعی با کد ۱ (`FAILED_HARD`) ایجاد می‌کنند و امکان تنزل به هشدار را ندارند:
     - شماره اسلاید تکراری (`DUPLICATE_SLIDE_NUMBER`)
     - شکستگی اسکیما و JSON نامعتبر (`SCHEMA_VALIDATION_ERROR`)
     - پسرفت زمانی غیرمجاز بیش از ۶۰ ثانیه (`TEMPORAL_MONOTONICITY_REGRESSION` > 60s)
     - فقدان مطلق شواهد صوتی (`SLIDE_AUDIO_NO_TEMPORAL_EVIDENCE`)
     - تزریق محتوای فاقد پشتوانه به کادر اسلاید (`UNSUPPORTED_SLIDE_BOX_CONTENT`)
   - فلگ `--allow-review` منحصراً موارد مشمول بازبینی (نظیر بازخوانی ۳۵٪ تا ۵۰٪ با تگ `needs_student_review`، عدم قطعیت OCR، و هشدارهای مشورتی) را به `REVIEW_REQUIRED` (کد خروج ۰) تبدیل می‌کند.

6. **موتور مفهوم‌محور و عبارت‌محور دوزبانه پزشکی (Phrase/Concept-Level Bilingual Engine):**
   - اسلایدهای مرجع دانشگاهی به زبان انگلیسی و ترجمه نهایی جزوه به زبان فارسی روان است. گیت بازخوانی ماهوی (`Substantive Recall`) مجهز به موتور تطبیق عبارت‌محور و مفهوم‌محور (`Phrase/Concept-Level Equivalence`) است.
   - **قانون کلمات عمومی (Generic Persian Words Rule):** کلمات عمومی تک‌واژه‌ای نظیر «کاهش»، «افزایش»، «فشار»، «قلب»، «کبد»، «تیروئید»، «خون»، «درد» و... به تنهایی به هیچ عنوان شواهد کافی برای تطابق یک مفهوم پزشکی شمرده نمی‌شوند (`GENERIC_PERSIAN_WORDS`). همپوشانی واژگان عمومی مانع از رد شدن ترجمه‌های نامربوط یا ساختگی نمی‌گردد.
   - **الزام مترادف تخصصی یا عبارت چندکلمه‌ای:** برای احراز پوشش هر مفهوم پزشکی، الزامی است که یا مترادف تک‌کلمه‌ای صریح و غیرعمومی پزشکی (`SPECIFIC_MEDICAL_TERMS` مانند تاکی‌کاردی، سنتز، فولیکولار، گواتر، لرزش، پاتوژنز، کلسیفیکاسیون و...) در متن باشد، یا عبارت ترکیبی چندکلمه‌ای مستند (`BILINGUAL_CONCEPT_PHRASES` مانند «کاهش وزن»، «پرکاری تیروئید»، «فشار خون»، «نارسایی قلبی»، «افزایش سنتز»، «قند ناشتا» و...).
   - **قانون مرزهای استناد مستقیم (`source_quote` Proves Source Existence Only):** فیلد `source_quote` منحصراً اثبات می‌کند که متن نقل‌شده در اسلاید خام منبع وجود داشته است (جلوگیری از ارجاعات جعلی). وجود `source_quote` هرگز نباید امتیاز پوشش کاذب به کل اسلاید ببخشد؛ بالتی که حاوی `source_quote` معتبر است اما متن آن شامل مداخلات دارویی تالیفی یا مفاهیم فاقد پشتوانه باشد، بدون استثنا با خطای سخت `UNSUPPORTED_SLIDE_BOX_CONTENT` مردود می‌گردد.

7. **گیت ممیزی نفوذ داروها و مداخلات در زبان فارسی (Persian Pharma Intrusion Audit):**
   - برای جلوگیری از تزریق رژیم‌های دارویی یا اقدامات درمانی تألیفی مدل به کادر اسلاید (Track 2) در متن فارسی، سیستم واژگان تخصصی فارماکولوژی بالینی فارسی (`PERSIAN_PHARMA_INTERVENTIONS` نظیر متیمازول، آتورواستاتین، وارفارین، جراحی، تیروئیدکتومی و...) را در هر دو فرم استاندارد و نرمال‌شده املایی پایش می‌کند. در صورتی که دارویی در ترجمه فارسی کادر اسلاید ذکر شود که اصل آن در اسلاید خام منبع وجود نداشته است، خطای قطعی `UNSUPPORTED_SLIDE_BOX_CONTENT` صادر شده و مدل ملزم می‌شود آن را به بخش شرح رفرنس (`ref_note`) منتقل کند.

---

## 💻 3. COMPLETE REFERENCE PYTHON IMPLEMENTATION (COPY-PASTE READY)

When generating the `.docx` document, agents **MUST** use these exact functions:

```python
import os
import sys
import json
import re
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_p_rtl(p, space_before=2, space_after=3, line_spacing=1.15, align_justify=False):
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    if align_justify:
        p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.JUSTIFY
    pPr = p._p.get_or_add_pPr()
    if pPr.find(docx.oxml.ns.qn('w:bidi')) is None:
        pPr.append(parse_xml(r'<w:bidi {}/>'.format(nsdecls('w'))))

def add_r(p, text, font_name="Dubai", size_pt=11, bold=False, italic=False, color_rgb=(0x26, 0x26, 0x26), is_rtl=True):
    # Strip any soft breaks/newlines to prevent grotesque justification spacing in Word
    sanitized_text = str(text).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    run = p.add_run(sanitized_text)
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor(*color_rgb)
    rPr = run._r.get_or_add_rPr()
    
    rFonts = rPr.find(docx.oxml.ns.qn('w:rFonts'))
    if rFonts is None:
        rFonts = parse_xml(r'<w:rFonts {} w:ascii="{}" w:hAnsi="{}" w:cs="{}"/>'.format(nsdecls('w'), font_name, font_name, font_name))
        rPr.append(rFonts)
    else:
        rFonts.set(docx.oxml.ns.qn('w:cs'), font_name)
        rFonts.set(docx.oxml.ns.qn('w:ascii'), font_name)
        rFonts.set(docx.oxml.ns.qn('w:hAnsi'), font_name)
        
    rtl_elem = rPr.find(docx.oxml.ns.qn('w:rtl'))
    if is_rtl:
        if rtl_elem is None:
            rPr.append(parse_xml(r'<w:rtl {} w:val="1"/>'.format(nsdecls('w'))))
        else:
            rtl_elem.set(docx.oxml.ns.qn('w:val'), '1')
    else:
        if rtl_elem is not None:
            rPr.remove(rtl_elem)
            
    # Set explicit Complex Script font size (w:szCs) matching w:sz
    sz_half_pts = str(int(round(size_pt * 2)))
    sz_elem = rPr.find(docx.oxml.ns.qn('w:sz'))
    if sz_elem is None:
        rPr.append(parse_xml(r'<w:sz {} w:val="{}"/>'.format(nsdecls('w'), sz_half_pts)))
    else:
        sz_elem.set(docx.oxml.ns.qn('w:val'), sz_half_pts)
        
    szCs_elem = rPr.find(docx.oxml.ns.qn('w:szCs'))
    if szCs_elem is None:
        rPr.append(parse_xml(r'<w:szCs {} w:val="{}"/>'.format(nsdecls('w'), sz_half_pts)))
    else:
        szCs_elem.set(docx.oxml.ns.qn('w:szCs'), sz_half_pts)
        
    # Set explicit Complex Script bold (w:bCs) and italic (w:iCs)
    bCs_elem = rPr.find(docx.oxml.ns.qn('w:bCs'))
    if bold:
        if bCs_elem is None:
            rPr.append(parse_xml(r'<w:bCs {}/>'.format(nsdecls('w'))))
    else:
        if bCs_elem is not None:
            rPr.remove(bCs_elem)
            
    iCs_elem = rPr.find(docx.oxml.ns.qn('w:iCs'))
    if italic:
        if iCs_elem is None:
            rPr.append(parse_xml(r'<w:iCs {}/>'.format(nsdecls('w'))))
    else:
        if iCs_elem is not None:
            rPr.remove(iCs_elem)
            
    return run

def add_bidi_text(p, text, font_name="Dubai", size_pt=11, bold=False, italic=False, color_rgb=(0x26, 0x26, 0x26)):
    if not text:
        return
    text = str(text).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
    tokens = re.split(r'(\([A-Za-z0-9_\-\s,\./%αβγ]+\))', text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith('(') and tok.endswith(')'):
            add_r(p, tok, font_name=font_name, size_pt=size_pt, bold=bold, italic=italic, color_rgb=color_rgb, is_rtl=False)
        else:
            add_r(p, tok, font_name=font_name, size_pt=size_pt, bold=bold, italic=italic, color_rgb=color_rgb, is_rtl=True)

def add_formatted_bidi_text(p, text_or_runs, font_name="Dubai", size_pt=11, default_bold=False, default_italic=False, color_rgb=(0x26, 0x26, 0x26)):
    if not text_or_runs:
        return
    runs = text_or_runs if isinstance(text_or_runs, list) else parse_inline_spans(str(text_or_runs), default_bold=default_bold, default_italic=default_italic)
    for r in runs:
        r_text = r.get("text", "")
        if not r_text:
            continue
        add_bidi_text(p, r_text, font_name=font_name, size_pt=size_pt, bold=r.get("bold", default_bold), italic=r.get("italic", default_italic), color_rgb=color_rgb)

def add_numbered_p(doc, num, body):
    p = doc.add_paragraph()
    set_p_rtl(p, space_before=2, space_after=2, align_justify=True)
    add_r(p, f"{num}. ", font_name="Dubai", size_pt=11, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    add_formatted_bidi_text(p, body, font_name="Dubai", size_pt=11, color_rgb=(0x26, 0x26, 0x26))
    return p

def add_title(doc, text):
    p = doc.add_paragraph()
    set_p_rtl(p, space_before=10, space_after=12)
    p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
    add_r(p, text, font_name="Dubai", size_pt=16, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    return p

def add_toc(doc, rows_data):
    p_toc = doc.add_paragraph()
    set_p_rtl(p_toc, space_before=8, space_after=6)
    add_r(p_toc, "📑 فهرست عناوین، زمان فایل صوتی و اسلایدهای مرتبط", font_name="Dubai", size_pt=14, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    
    headers = ["بخش", "موضوع و مبحث تدریس کلاسی استاد", "زمان فایل صوتی", "اسلایدهای مرتبط"]
    t = doc.add_table(rows=len(rows_data) + 1, cols=4)
    tPr = t._tbl.tblPr
    tPr.append(parse_xml(r'<w:tblW {} w:w="5000" w:type="pct"/>'.format(nsdecls('w'))))
    tPr.append(parse_xml(r'<w:bidiVisual {}/>'.format(nsdecls('w'))))
    
    for c_idx, h in enumerate(headers):
        c = t.cell(0, c_idx)
        tcPr = c._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(r'<w:shd {} w:fill="78281F"/>'.format(nsdecls('w'))))
        p = c.paragraphs[0]
        set_p_rtl(p, space_before=3.5, space_after=3.5)
        add_r(p, h, font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0xFF, 0xFF, 0xFF))
        
    for r_idx, rdata in enumerate(rows_data):
        bg = "FAF7F5" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(rdata):
            c = t.cell(r_idx + 1, c_idx)
            tcPr = c._tc.get_or_add_tcPr()
            tcPr.append(parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), bg)))
            p = c.paragraphs[0]
            set_p_rtl(p, space_before=2.5, space_after=2.5)
            c_rgb = (0x78, 0x28, 0x1F) if c_idx == 0 else ((0xD3, 0x54, 0x00) if c_idx == 2 else (0x26, 0x26, 0x26))
            add_r(p, val, font_name="Dubai", size_pt=10, bold=(c_idx == 0 or c_idx == 2), color_rgb=c_rgb)
            
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(4)
    sp.paragraph_format.space_after = Pt(12)

def add_h1(doc, text, audio_time=None):
    p = doc.add_paragraph()
    set_p_rtl(p, space_before=18, space_after=5)
    add_r(p, text, font_name="Dubai", size_pt=14, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    if audio_time:
        add_r(p, f"   [⏱️ زمان فایل صوتی: {audio_time}]", font_name="Dubai", size_pt=10, bold=True, color_rgb=(0xD3, 0x54, 0x00))
    return p

def add_h2(doc, text, audio_time=None):
    p = doc.add_paragraph()
    set_p_rtl(p, space_before=11, space_after=3)
    add_r(p, text, font_name="Dubai", size_pt=11, bold=True, color_rgb=(0x0E, 0x62, 0x51))
    if audio_time:
        add_r(p, f"   [⏱️ {audio_time}]", font_name="Dubai", size_pt=9.5, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    return p

def add_body_p(doc, text, bold_prefix=""):
    p = doc.add_paragraph()
    set_p_rtl(p, space_before=2.5, space_after=3.5, align_justify=True)
    if bold_prefix:
        clean_prefix = clean_markdown_text(bold_prefix).strip()
        add_r(p, clean_prefix + " ", font_name="Dubai", size_pt=11, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    add_formatted_bidi_text(p, text, font_name="Dubai", size_pt=11, color_rgb=(0x26, 0x26, 0x26))
    return p

def add_bullet_p(doc, lead, body):
    p = doc.add_paragraph()
    set_p_rtl(p, space_before=2, space_after=2, align_justify=True)
    clean_lead = clean_markdown_text(lead).strip() if lead else ""
    if clean_lead:
        if not clean_lead.endswith(":"):
            clean_lead += ":"
        add_r(p, "• " + clean_lead + " ", font_name="Dubai", size_pt=11, bold=True, color_rgb=(0x0E, 0x62, 0x51))
    else:
        add_r(p, "• ", font_name="Dubai", size_pt=11, bold=True, color_rgb=(0x0E, 0x62, 0x51))
    add_formatted_bidi_text(p, body, font_name="Dubai", size_pt=11, color_rgb=(0x26, 0x26, 0x26))
    return p

def add_figure_with_caption(doc, img_path, caption_title, caption_text="", max_width_in=5.2):
    """Embeds an educational figure or English slide table/diagram in Track 1 alongside spoken lecture."""
    if os.path.exists(img_path):
        p = doc.add_paragraph()
        p.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run()
        run.add_picture(img_path, width=Inches(max_width_in))
        
        cp = doc.add_paragraph()
        set_p_rtl(cp, space_before=2, space_after=8)
        cp.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        add_r(cp, f"🖼️ {caption_title} ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x78, 0x28, 0x1F))
        if caption_text:
            add_r(cp, f"— {caption_text}", font_name="Dubai", size_pt=10, italic=True, color_rgb=(0x55, 0x55, 0x55))
        return True
    return False

def add_qa_box(doc, question, answer):
    tbl = doc.add_table(rows=1, cols=1)
    tblPr = tbl._tbl.tblPr
    tblPr.append(parse_xml(r'<w:tblW {} w:w="5000" w:type="pct"/>'.format(nsdecls('w'))))
    tblPr.append(parse_xml(r'<w:bidiVisual {}/>'.format(nsdecls('w'))))
    
    cell = tbl.cell(0, 0)
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(r'<w:shd {} w:fill="FBF9FD"/>'.format(nsdecls('w'))))
    tcPr.append(parse_xml(r'''
        <w:tcBorders {} >
            <w:top w:val="single" w:sz="6" w:space="0" w:color="E8DAEF"/>
            <w:left w:val="single" w:sz="6" w:space="0" w:color="E8DAEF"/>
            <w:bottom w:val="single" w:sz="6" w:space="0" w:color="E8DAEF"/>
            <w:right w:val="single" w:sz="36" w:space="0" w:color="6C3483"/>
        </w:tcBorders>
    '''.format(nsdecls('w'))))
    tcPr.append(parse_xml(r'''
        <w:tcMar {} >
            <w:top w:w="120" w:type="dxa"/>
            <w:bottom w:w="120" w:type="dxa"/>
            <w:left w:w="160" w:type="dxa"/>
            <w:right w:w="200" w:type="dxa"/>
        </w:tcMar>
    '''.format(nsdecls('w'))))
    
    p0 = cell.paragraphs[0]
    set_p_rtl(p0, space_before=2, space_after=2)
    add_r(p0, "❓ پرسش دانشجو در کلاس: ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x6C, 0x34, 0x83))
    add_r(p0, question, font_name="Dubai", size_pt=10.5, italic=True, color_rgb=(0x33, 0x33, 0x33))
    
    p1 = cell.add_paragraph()
    set_p_rtl(p1, space_before=2, space_after=2)
    add_r(p1, "💡 پاسخ استاد: ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1E, 0x84, 0x49))
    add_bidi_text(p1, answer, font_name="Dubai", size_pt=10.5, color_rgb=(0x26, 0x26, 0x26))
    
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)

def add_student_review_badge(doc, slide_num, note_text=""):
    tbl = doc.add_table(rows=1, cols=1)
    tblPr = tbl._tbl.tblPr
    tblPr.append(parse_xml(r'<w:tblW {} w:w="5000" w:type="pct"/>'.format(nsdecls('w'))))
    tblPr.append(parse_xml(r'<w:bidiVisual {}/>'.format(nsdecls('w'))))
    
    cell = tbl.cell(0, 0)
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(r'<w:shd {} w:fill="FEF9E7"/>'.format(nsdecls('w'))))
    tcPr.append(parse_xml(r'''
        <w:tcBorders {} >
            <w:top w:val="single" w:sz="8" w:space="0" w:color="FAD7A0"/>
            <w:left w:val="single" w:sz="8" w:space="0" w:color="FAD7A0"/>
            <w:bottom w:val="single" w:sz="8" w:space="0" w:color="FAD7A0"/>
            <w:right w:val="single" w:sz="36" w:space="0" w:color="D35400"/>
        </w:tcBorders>
    '''.format(nsdecls('w'))))
    tcPr.append(parse_xml(r'''
        <w:tcMar {} >
            <w:top w:w="120" w:type="dxa"/>
            <w:bottom w:w="120" w:type="dxa"/>
            <w:left w:w="160" w:type="dxa"/>
            <w:right w:w="200" w:type="dxa"/>
        </w:tcMar>
    '''.format(nsdecls('w'))))
    
    p = cell.paragraphs[0]
    set_p_rtl(p, space_before=2, space_after=2)
    add_r(p, f"⚠️ برچسب بازبینی دانشجو (اسلاید {slide_num} - نگاره یا دیاگرام تصویری): ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0xD3, 0x54, 0x00))
    desc = note_text or "این صفحه از فایل ارائه حاوی دیاگرام یا نگاره اطلسی بود؛ جهت حفظ ثبات ۱ به ۱ اندیس صفحات، کادر این اسلاید حفظ شده است."
    add_r(p, desc, font_name="Dubai", size_pt=10, italic=True, color_rgb=(0x55, 0x55, 0x55))
    
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(4)

def add_slide_box_from_json(doc, slide_data, img_path=None, table_data=None, ref_book_name="هاریسون", image_already_shown=False):
    """Renders a 2-row slide box strictly from JSON data with soft sky blue border and white body.
    Supports pure text slides, localized tables, and optional diagrams.
    Auto-detects table_data from slide_data if omitted.
    CRITICAL: Never embeds English screenshots for pure-text slides! Only visual slides (tables/diagrams/figures)."""
    slide_num = slide_data.get('slide_number', '?')
    title_fa = slide_data.get('title_fa', f'اسلاید {slide_num}')
    title_en = slide_data.get('title_en', '')
    bullets = slide_data.get('bullets', [])
    ref_note = slide_data.get('ref_note', '')
    is_visual = bool(slide_data.get('has_table') or slide_data.get('has_diagram') or slide_data.get('is_image_only') or slide_data.get('has_figure') or slide_data.get('is_visual'))
    is_ceremonial = bool(slide_data.get('is_ceremonial') or any(term in (slide_data.get('title_fa', '') + ' ' + slide_data.get('title_en', '')).lower() for term in ['بسم الله', 'بسم‌الله', 'صلوات', 'ادای احترام', 'شهدا', 'تشکر', 'تقدیم', 'پایان', 'welcome', 'thank you']))
    is_skipped = bool(slide_data.get('is_skipped') or slide_data.get('unvoiced') or slide_data.get('skipped_by_professor'))
    
    # Auto-fallback to table_data inside slide_data if not explicitly passed
    if table_data is None:
        table_data = slide_data.get('table_data')
    
    tbl = doc.add_table(rows=2, cols=1)
    tblPr = tbl._tbl.tblPr
    tblPr.append(parse_xml(r'<w:tblW {} w:w="5000" w:type="pct"/>'.format(nsdecls('w'))))
    tblPr.append(parse_xml(r'<w:bidiVisual {}/>'.format(nsdecls('w'))))
    
    # Row 0: Slim Header Bar (Fill #EBF5FB, Border #85C1E9)
    cell0 = tbl.cell(0, 0)
    tcPr0 = cell0._tc.get_or_add_tcPr()
    tcPr0.append(parse_xml(r'<w:shd {} w:fill="EBF5FB"/>'.format(nsdecls('w'))))
    tcPr0.append(parse_xml(r'''
        <w:tcBorders {} >
            <w:top w:val="single" w:sz="8" w:space="0" w:color="85C1E9"/>
            <w:left w:val="single" w:sz="8" w:space="0" w:color="85C1E9"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="D4E6F1"/>
            <w:right w:val="single" w:sz="8" w:space="0" w:color="85C1E9"/>
        </w:tcBorders>
    '''.format(nsdecls('w'))))
    tcPr0.append(parse_xml(r'''
        <w:tcMar {} >
            <w:top w:w="80" w:type="dxa"/>
            <w:bottom w:w="80" w:type="dxa"/>
            <w:left w:w="160" w:type="dxa"/>
            <w:right w:w="160" w:type="dxa"/>
        </w:tcMar>
    '''.format(nsdecls('w'))))
    
    p0 = cell0.paragraphs[0]
    set_p_rtl(p0, space_before=1.5, space_after=2)
    prefix_label = "📑 اسلاید مقدماتی " if is_ceremonial else "📑 اسلاید مرتبط "
    add_r(p0, f"{prefix_label}{slide_num}: ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
    add_r(p0, title_fa, font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    if title_en:
        add_r(p0, f" ({title_en})", font_name="Dubai", size_pt=9.5, italic=True, color_rgb=(0x55, 0x55, 0x55), is_rtl=False)
    if is_ceremonial:
        add_r(p0, " [اسلاید تشریفاتی / مقدماتی]", font_name="Dubai", size_pt=9.5, bold=True, color_rgb=(0x2E, 0x86, 0xC1))
    elif is_skipped:
        add_r(p0, " [⚠️ تدریس‌نشده در کلاس]", font_name="Dubai", size_pt=9.5, bold=True, color_rgb=(0xD3, 0x54, 0x00))
        
    # Row 1: Content Area (White background, 1pt Border #85C1E9)
    cell1 = tbl.cell(1, 0)
    tcPr1 = cell1._tc.get_or_add_tcPr()
    tcPr1.append(parse_xml(r'<w:shd {} w:fill="FFFFFF"/>'.format(nsdecls('w'))))
    tcPr1.append(parse_xml(r'''
        <w:tcBorders {} >
            <w:top w:val="none"/>
            <w:left w:val="single" w:sz="8" w:space="0" w:color="85C1E9"/>
            <w:bottom w:val="single" w:sz="8" w:space="0" w:color="85C1E9"/>
            <w:right w:val="single" w:sz="8" w:space="0" w:color="85C1E9"/>
        </w:tcBorders>
    '''.format(nsdecls('w'))))
    tcPr1.append(parse_xml(r'''
        <w:tcMar {} >
            <w:top w:w="100" w:type="dxa"/>
            <w:bottom w:w="120" w:type="dxa"/>
            <w:left w:w="160" w:type="dxa"/>
            <w:right w:w="200" w:type="dxa"/>
        </w:tcMar>
    '''.format(nsdecls('w'))))
    
    first_item = True
    # Embed screenshot for visual slides (diagram, table, or image-only) unless already placed in Track 1
    if is_visual and img_path and os.path.exists(img_path) and not image_already_shown:
        ip = cell1.paragraphs[0] if first_item else cell1.add_paragraph()
        first_item = False
        ip.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER
        ip.paragraph_format.space_before = Pt(4)
        ip.paragraph_format.space_after = Pt(6)
        run = ip.add_run()
        run.add_picture(img_path, width=Inches(4.8))
        
    for b in bullets:
        bp = cell1.paragraphs[0] if first_item else cell1.add_paragraph()
        first_item = False
        set_p_rtl(bp, space_before=1.5, space_after=2, align_justify=True)
        if isinstance(b, dict):
            lead = clean_markdown_text(b.get('lead', '')).strip()
            text = b.get('text', '')
            if lead:
                if not lead.endswith(":"):
                    lead += ":"
                add_r(bp, "• " + lead + " ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
            else:
                add_r(bp, "• ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
            add_formatted_bidi_text(bp, text, font_name="Dubai", size_pt=10.5, color_rgb=(0x26, 0x26, 0x26))
        elif isinstance(b, (tuple, list)) and len(b) >= 2:
            lead, text = clean_markdown_text(str(b[0])).strip(), b[1]
            if not lead.endswith(":"):
                lead += ":"
            add_r(bp, "• " + lead + " ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
            add_formatted_bidi_text(bp, text, font_name="Dubai", size_pt=10.5, color_rgb=(0x26, 0x26, 0x26))
        else:
            raw_str = str(b).strip()
            # If string starts with bold-like pattern e.g. "عنوان: متن"
            if ":" in raw_str and not raw_str.startswith("http"):
                parts = raw_str.split(":", 1)
                lead_cand = clean_markdown_text(parts[0]).strip()
                if len(lead_cand.split()) <= 6:
                    add_r(bp, "• " + lead_cand + ": ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
                    add_formatted_bidi_text(bp, parts[1].strip(), font_name="Dubai", size_pt=10.5, color_rgb=(0x26, 0x26, 0x26))
                else:
                    add_r(bp, "• ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
                    add_formatted_bidi_text(bp, raw_str, font_name="Dubai", size_pt=10.5, color_rgb=(0x26, 0x26, 0x26))
            else:
                add_r(bp, "• ", font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x1B, 0x4F, 0x72))
                add_formatted_bidi_text(bp, raw_str, font_name="Dubai", size_pt=10.5, color_rgb=(0x26, 0x26, 0x26))
                
    if is_ceremonial and not bullets and not table_data and not (img_path and os.path.exists(img_path)):
        cp = cell1.paragraphs[0]
        set_p_rtl(cp, space_before=2, space_after=2)
        add_r(cp, title_fa or "اسلاید تشریفاتی / مقدماتی جلسه", font_name="Dubai", size_pt=10.5, italic=True, color_rgb=(0x55, 0x55, 0x55))

    if table_data:
        headers, items_data = table_data
        render_harrison_table(cell1, headers, items_data)
        
    # Supplementary reference note for skipped/unexplained slides (EXEMPT for ceremonial slides)
    if ref_note and not is_ceremonial:
        rp = cell1.add_paragraph()
        set_p_rtl(rp, space_before=5, space_after=2, align_justify=True)
        add_r(rp, f"💡 شرح تکمیلی رفرنس ({ref_book_name}) جهت تفهیم مبحث: ", font_name="Dubai", size_pt=10, bold=True, color_rgb=(0x6C, 0x34, 0x83))
        add_formatted_bidi_text(rp, ref_note, font_name="Dubai", size_pt=10, default_italic=True, color_rgb=(0x33, 0x33, 0x33))
        
    sp = doc.add_paragraph()
    sp.paragraph_format.space_before = Pt(0)
    sp.paragraph_format.space_after = Pt(5)

def render_harrison_table(parent_cell, headers, items):
    tp = parent_cell.add_paragraph()
    set_p_rtl(tp, space_before=4, space_after=3)
    add_r(tp, "📊 جدول تفصیلی ترجمه‌شده فارسی (منطبق دقیق بر ساختار و رفرنس هاریسون):", font_name="Dubai", size_pt=11, bold=True, color_rgb=(0x78, 0x28, 0x1F))
    
    t = parent_cell.add_table(rows=len(items) + 1, cols=len(headers))
    tPr = t._tbl.tblPr
    tPr.append(parse_xml(r'<w:tblW {} w:w="5000" w:type="pct"/>'.format(nsdecls('w'))))
    tPr.append(parse_xml(r'<w:bidiVisual {}/>'.format(nsdecls('w'))))
    
    # Header Row (Peach / Cream #F5EBE1, Text #5D4037)
    for c_idx, h in enumerate(headers):
        c = t.cell(0, c_idx)
        tcPr_t = c._tc.get_or_add_tcPr()
        tcPr_t.append(parse_xml(r'<w:shd {} w:fill="F5EBE1"/>'.format(nsdecls('w'))))
        tcPr_t.append(parse_xml(r'''
            <w:tcBorders {} >
                <w:top w:val="single" w:sz="8" w:space="0" w:color="5D4037"/>
                <w:left w:val="single" w:sz="4" w:space="0" w:color="D5D8DC"/>
                <w:bottom w:val="single" w:sz="8" w:space="0" w:color="5D4037"/>
                <w:right w:val="single" w:sz="4" w:space="0" w:color="D5D8DC"/>
            </w:tcBorders>
        '''.format(nsdecls('w'))))
        tcPr_t.append(parse_xml(r'''
            <w:tcMar {} >
                <w:top w:w="90" w:type="dxa"/>
                <w:bottom w:w="90" w:type="dxa"/>
                <w:left w:w="110" w:type="dxa"/>
                <w:right w:w="110" w:type="dxa"/>
            </w:tcMar>
        '''.format(nsdecls('w'))))
        p_t = c.paragraphs[0]
        set_p_rtl(p_t, space_before=2.5, space_after=2.5)
        add_r(p_t, h, font_name="Dubai", size_pt=10.5, bold=True, color_rgb=(0x5D, 0x40, 0x37))
        
    for r_idx, item in enumerate(items):
        row_num = r_idx + 1
        if item.get("type") == "banner":
            cell_start = t.cell(row_num, 0)
            cell_end = t.cell(row_num, len(headers) - 1)
            cell_merged = cell_start.merge(cell_end)
            
            tcPr_t = cell_merged._tc.get_or_add_tcPr()
            tcPr_t.append(parse_xml(r'<w:shd {} w:fill="4A709C"/>'.format(nsdecls('w'))))
            tcPr_t.append(parse_xml(r'''
                <w:tcBorders {} >
                    <w:top w:val="single" w:sz="6" w:space="0" w:color="2C3E50"/>
                    <w:left w:val="none"/>
                    <w:bottom w:val="single" w:sz="6" w:space="0" w:color="2C3E50"/>
                    <w:right w:val="none"/>
                </w:tcBorders>
            '''.format(nsdecls('w'))))
            tcPr_t.append(parse_xml(r'''
                <w:tcMar {} >
                    <w:top w:w="80" w:type="dxa"/>
                    <w:bottom w:w="80" w:type="dxa"/>
                    <w:left w:w="120" w:type="dxa"/>
                    <w:right w:w="120" w:type="dxa"/>
                </w:tcMar>
            '''.format(nsdecls('w'))))
            p_m = cell_merged.paragraphs[0]
            set_p_rtl(p_m, space_before=2.5, space_after=2.5)
            add_r(p_m, item["text"], font_name="Dubai", size_pt=11, bold=True, color_rgb=(0xFF, 0xFF, 0xFF))
        else:
            cols_val = item["cols"]
            bg = item.get("bg", "FFFFFF" if r_idx % 2 == 0 else "FDFBF7")
            for c_idx, val in enumerate(cols_val):
                c = t.cell(row_num, c_idx)
                tcPr_t = c._tc.get_or_add_tcPr()
                tcPr_t.append(parse_xml(r'<w:shd {} w:fill="{}"/>'.format(nsdecls('w'), bg)))
                tcPr_t.append(parse_xml(r'''
                    <w:tcBorders {} >
                        <w:top w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                        <w:left w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                        <w:bottom w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                        <w:right w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
                    </w:tcBorders>
                '''.format(nsdecls('w'))))
                tcPr_t.append(parse_xml(r'''
                    <w:tcMar {} >
                        <w:top w:w="80" w:type="dxa"/>
                        <w:bottom w:w="80" w:type="dxa"/>
                        <w:left w:w="100" w:type="dxa"/>
                        <w:right w:w="100" w:type="dxa"/>
                    </w:tcMar>
                '''.format(nsdecls('w'))))
                p_c = c.paragraphs[0]
                set_p_rtl(p_c, space_before=2, space_after=2)
                is_bold = (c_idx == 0) and not val.startswith("   ")
                add_bidi_text(p_c, val, font_name="Dubai", size_pt=10, bold=is_bold, color_rgb=(0x26, 0x26, 0x26))
```

---

## 📋 4. MANDATORY AUDIT & VERIFICATION CHECKLIST

Before concluding any study guide generation task, the agent **MUST** verify each item:

- [ ] **Dual-Engine Presentation Extraction Executed:** Extracted all slides from PPTX or PDF into `raw_slides.json` using `scripts/extract_presentation.py` (with visual-aware ONNX OCR triggered on any slide bearing visual images, charts, smartart, or PDF tables, robust confidence thresholding >= 0.60, and native vs. scanned table differentiation).
- [ ] **Strict Page Index Invariance Verified:** Slide Box N strictly corresponds to Presentation Page N across all 1 to total_pages. Zero dropped or merged slides.
- [ ] **Automated Slide Alignment Gate Passed:** `scripts/verify_slide_alignment.py` executed and passed with exit code 0 (mandatory >= 50% substantive recall rate on raw tokens >= 4, Source Exclusivity gate preventing ungrounded textbook/drug injections into Track 2, zero false phantom hallucination, and strict slide text immutability without audio/reference leakage).
- [ ] **Substantive Audio & Concept Coverage Gate Passed:** `scripts/verify_lecture_alignment.py` executed and passed with exit code 0, verifying chronology, duration bounds, keyword matching, and clinical substance density.
- [ ] **Safe Auto-Remediation & Fallback Badging Verified:** Auto-fix restricted to deterministic structural issues (no silent clamping for drifts > 3 min); unresolved cases flagged with amber Student Review Badges.
- [ ] **Tri-Partite Provenance Attribution Verified:** Strict separation between spoken lecture (Track 1), literal slide translation (Track 2), and unvoiced reference commentary (Track 3).
- [ ] **Parametric Reference Architecture Configured:** Standard textbook `{ref_book_name}` matched to discipline without hardcoding.
- [ ] **Strict Unvoiced Slide Labeling Verified:** Any slide skipped by professor explicitly labeled `[اسلاید تدریس‌نشده در کلاس]`, preventing false attribution.
- [ ] **Verifiable Classroom Q&A Verified:** Q&A boxes used only for genuine recorded classroom questions, never synthetic monologue conversions.
- [ ] **Multimodal Table Verification:** Every table slide image inspected with `view_file` to confirm exact columns, headers, banners, and rows.
- [ ] **Universal Visual Architecture:** Pure text slides translated without plain screenshots; visual slides embed English figure in Track 1 and localized Word table in Track 2.
- [ ] **Preserved BiDi Scientific Notation Verified:** Biochemical pathways (`->`), chemical formulas (`<->`), inequalities (`<, >`), and Latin acronyms protected in explicit `<w:rtl w:val="0"/>` LTR runs.
- [ ] **Font & XML Size Compliance:** Dubai font throughout, with explicit `<w:szCs>` and `<w:bCs/>` on every run. H1 is 14pt `#78281F` bold, audio time is `#D35400` bold, H2 is 11pt `#0E6251` bold. Zero footnotes.
