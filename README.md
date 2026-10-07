# 🩺 Medical Lecture Transcriber & Study Guide Generator (v5.7.0)

[🇬🇧 English](README.md) | [🇮🇷 فارسی](README_FA.md)

[![CI](https://img.shields.io/github/actions/workflow/status/HunterHill13/medical-lecture-transcriber/ci.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI)](https://github.com/HunterHill13/medical-lecture-transcriber/actions)
[![Tests](https://img.shields.io/badge/Tests-128%20Passed-success?style=for-the-badge&logo=pytest)](tests/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Version](https://img.shields.io/badge/Version-5.7.0-orange?style=for-the-badge)](scripts/version.py)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Google%20Antigravity-Compatible-blueviolet?style=for-the-badge)](https://antigravity.google)

A publication-grade, automated pair-programming and document generation pipeline for medical academia. It converts recorded university medical lectures (audio/video) and English presentation slides (`.pptx` / `.pdf`) into beautifully formatted, tri-partite Microsoft Word study guides (`.docx`) governed by strict clinical accuracy gates, semantic provenance attribution, and visual fidelity protocols.

---

## 🌟 Key Innovations & Architectural Pillars

### 1. 🎯 Tri-Partite Source Provenance (خاستگاه‌شناسی سه‌گانه مطالب)
Students must immediately know the origin of every statement:
* **Track 1 (`[🎙️ تدریس کلاسی استاد]`):** Captures 100% of the professor's spoken clinical nuances, diagnostic mnemonics, laboratory thresholds, drug dosages, and patient case anecdotes. Zero parametric hallucination.
* **Track 2 (`[📑 ترجمه اسلاید X]`):** Dedicated light blue slide box (`#85C1E9`) featuring literal, faithful Persian translations of English slide bullets.
* **Track 3 (`[💡 شرح تکمیلی رفرنس]`):** High-yield reference commentary (Harrison, Cecil, Braunwald, etc.) in royal purple callouts (`#6C3483`) strictly outside Track 2 for unvoiced, skipped, or dense slides.

### 2. 🛡️ Anti-Clause Parentheses Gate (`PARENTHETICAL_CLAUSE_VIOLATION`)
Prevents translation shortcuts and visual pollution:
* English terms in translated slide bullets are strictly restricted to concise proper nouns, drug names, and domain acronyms (maximum 1–4 words, e.g., `(Duodenum)`, `(Corrected calcium)`, `(Cinacalcet)`, `(PTH)`).
* Copy-pasting full English clauses or sentences with verbs/conjunctions triggers an immediate hard validation error.

### 3. 🔬 Substantive Concept Denominator Filtering & Expanded Medical Thesaurus
* Filters routine English academic prose verbs and fillers (`cannot`, `provide`, `enough`, `replace`, `losses`, `under`, `circumstances`, `directed`) from recall denominators.
* Evaluates true clinical entities, formulas, chemical notations (`Ca²⁺`, `HCO₃⁻`), measurements, and acronyms, allowing fluent academic Persian translation to pass 100% cleanly without artificial English token crutches.
* Expanded bilingual dictionary covering diabetic foot, Wagner classification, orthotics (`aircast walker`), lipidology, and cardiovascular risk paradigms.

### 4. 📊 Table Completeness & Diagnostic Preservation Gate (`TABLE_COMPLETENESS_GATE`)
* Enforces zero-omission atomic line-by-line translation for textbook tables, classifications, and diagnostic criteria.
* Automatically marks table screenshots and guideline tables as `has_image_table: true` and blocks slide exemption even in the presence of OCR noise.
* Validates that all subcategories, parenthetical entities (e.g., Aluminum intoxication, Lithium therapy, Multiple myeloma), and criteria are fully translated in `table_data`, raising blocking errors (`MISSING_TABLE_DATA`, `INCOMPLETE_TABLE_TRANSCRIPTION`) if rows are dropped or summarized away.

### 5. 🛑 Table Hallucination Guard (`UNGROUNDED_TABLE_ROW_CONTENT`)
* Audits every translated table row against raw slide text and OCR tokens.
* Detects and blocks parametric memory hallucinations of non-existent rows, grades, or categories (e.g., injecting an ungrounded "Grade 0" into a slide containing Wagner grades 1 to 5).

### 6. 🛑 Unparenthesized English Clause Guard (`UNPROCESSED_ENGLISH_CLAUSE_VIOLATION`)
* Strictly inspects Persian bullet prose outside parentheses for raw, untranslated English clauses ($\ge 4$ words with clause markers or $\ge 5$ consecutive English tokens).
* Eliminates the shortcut of dumping raw English prose directly into Persian text to satisfy recall thresholds without triggering parenthetical checks.

### 7. 🔄 Raw Slides Visual & Structural Auto-Inheritance
* Master pamphlet compiler (`create_slide_pamphlet.py`) seamlessly inherits visual metadata (`has_images`, `has_charts`, `has_tables`, `has_image_table`, `is_visual`, `img_path`) directly from `raw_slides.json` (via `--raw` or automatic discovery).
* Guarantees that clinical photographs, pathology samples, devices, and curves are embedded in Word documents even if downstream translation JSON omitted visual flags.
* Injects a prominent structural deficiency advisory banner (`⚠️ تذکر ساختاری`) into the study guide if a table exists in the source slide but `table_data` was omitted.

### 8. ☁️ Gemini Multimodal Audio Transcription Protocol
* Native in-context audio comprehension leveraging Google Gemini multimodal capabilities.
* Strictly prohibits heavy local Whisper/CUDA downloads, saving gigabytes of disk space and GPU memory while preserving exact Persian medical pronunciation.

### 9. 👁️ Visual-Aware OCR & Confidence Thresholding
* Intelligently triggers OCR for slides containing images, micrographs, charts, smart art, or tables, regardless of digital text volume.
* Filters OCR noise using statistical confidence thresholds (`mean_conf >= 0.60`, substantive tokens $\ge 2$).
* Displays warning banners in Word documents if embedded image extraction fails.

### 10. 📈 Universal Vector & Chart Rasterization Engine (`convert_image_to_png`)
* Automatically detects and converts non-raster vector shapes, metafiles, and specialized formats (`.wmf`, `.emf`, `.svg`, `.webp`, `.tiff`, `.bmp`) to standard PNG during both presentation extraction and Word compilation.
* Dynamic multi-pattern candidate discovery (`find_and_prepare_slide_image`) resolves any slide chart or diagram graphic asset without hardcoded filename fragility.
* Enforces the `VISUAL_ASSET_AUDIT` gate and renders student advisory banners when graphic chart assets cannot be embedded.

### 11. 🛡️ Universal Reference Note Sanitization & Anti-Dual-Prepending Engine (`sanitize_ref_note`)
* Eliminates double-title rendering bugs (Dual Prepending) where models mistakenly inject `💡 شرح تکمیلی رفرنس...` into the JSON `ref_note` value.
* Features a robust agnostic regex parser in `text_utils.py` that strips redundant emojis, phrases, book titles, and colons while preserving pure medical commentary.
* Connects seamlessly with `verify_slide_alignment.py` to issue informative, non-blocking `DUPLICATE_REF_TITLE_PREFIX` advisories without halting pipeline execution.

### 12. 🖼️ Smart Visual Asset Classifier & Standalone Figure Engine
* **Multi-Criteria Asset Filtering:** Automatically identifies and discards tiny decorative icons, bullet graphics (< 150px or < 25,000 px²), and slide master template background wallpapers on text slides.
* **Standalone Figure Extraction (`slide_NN_fig.png`):** For mixed slides featuring both text and clinical diagrams/flowcharts, extracts the pure graphical asset directly from the PDF/PPTX container.
* **Smart Text Slide Screenshot Guard:** In the Word compiler, prioritizes standalone figures over whole-page screenshots, and strictly suppresses redundant full-page English screenshots on slides that only contain text bullets.

### 13. 🔢 Slide Numerical & Statistical Preservation Engine & Text Sanitizer (`SLIDE_NUMERICAL_DATA_OMISSION`)
* **Verbatim Quantitative Metric Preservation:** Strictly enforces that epidemiological ratios (`5 in 10,000`, `3 in 10,000`), percentages (`0.5–2%`, `2–5%`), numerical ranges, cohort ages (`40-year-olds`), and drug dosages on presentation slides are preserved verbatim in translated bullets rather than generalized into vague qualitative prose.
* **Anti-Track-Leakage Principle:** Ensures that detailed verbal explanations of statistics by the lecturer in Track 1 cannot be used to justify omitting or simplifying numbers in Track 2 slide boxes.
* **Presentation Text Encoding Recovery (`sanitize_presentation_text`):** Automatically recovers and normalizes corrupted character encodings (e.g. `\ufffd` in ranges like `2\ufffd5%` to `2-5%`), unicode en/em-dashes, and smart quotes across PowerPoint and PDF extractions.
* **Anti-Gaming Token Denominator:** Expands `ENGLISH_PROSE_STOPWORDS` with non-specific prose words (`countries`, `origin`, `frequent`, `population`, `society`) to prevent models from artificially inflating substantive recall by echoing general nouns in parentheses.

### 14. 🧪 128-Test Automated Quality Suite
* Comprehensive unit, integration, and adversarial tests ensuring page index invariance, zero content drift, chronological audio grounding, vector rasterization, table hallucination guards, unparenthesized English clause detection, reference note sanitization, standalone figure extraction, numerical & statistical data preservation, and schema integrity.

---

## 🏗️ Architecture & Pipeline Flow

```mermaid
flowchart TD
    A[Recorded Lecture Audio\n.m4a / .mp3 / .wav] -->|chunk_audio.py| B[Audio Chunks\n10-15 min]
    B -->|transcribe_chunks.py\nGemini Multimodal| C[Verbatim Persian Transcripts\ntranscript_chunk_XX.json]
    
    D[Presentation Slides\n.pptx / .pdf] -->|extract_presentation.py\nPyMuPDF / python-pptx / OCR| E[Raw Extracted Data\nraw_slides.json & slide_images/]
    
    C --> F[Agent / Translator Engine]
    E --> F
    
    F --> G[Structured Content Data\ntranslated_slides.json]
    
    G --> H{verify_slide_alignment.py\nGate 1: Slide Alignment}
    H -->|PASSED| I{verify_lecture_alignment.py\nGate 2: Spoken Grounding}
    H -->|FAILED| F
    
    I -->|PASSED| J[create_slide_pamphlet.py\nWord Compiler]
    I -->|FAILED| F
    
    J --> K[Publication-Grade Study Guide\nlecture_pamphlet.docx]
```

---

## 📂 Repository Structure

```text
medical-lecture-transcriber/
├── scripts/
│   ├── annotate_docx.py            # Word XML margin annotator & reference callouts
│   ├── chunk_audio.py              # Lossless silence-aware audio chunker
│   ├── create_slide_pamphlet.py    # Master DOCX study guide compiler
│   ├── extract_presentation.py     # Presentation extractor with visual-aware OCR
│   ├── package_skill.py            # POSIX-compliant clean packager & plugin syncer
│   ├── run_pipeline.py             # Unified CLI orchestrator
│   ├── text_utils.py               # Medical tokenization & bilingual concept engine
│   ├── transcribe_chunks.py        # Lightweight Gemini cloud STT client
│   ├── verify_lecture_alignment.py # Temporal monotonicity & audio grounding gate
│   ├── verify_slide_alignment.py   # Page index invariance & concept recall gate
│   └── version.py                  # Canonical single source of truth version
├── tests/
│   ├── conftest.py                 # Pytest fixtures and mock environments
│   ├── test_drift.py               # Slide index invariance & drift regression tests
│   ├── test_extractor_and_ocr.py   # Visual-aware OCR & presentation extractor tests
│   ├── test_gates.py               # Alignment, recall, and parenthetical clause gate tests
│   ├── test_normalization.py       # Persian digit & text normalization tests
│   └── test_pipeline_and_tools.py  # CLI and STT protocol tests
├── .gitignore
├── LICENSE                         # MIT License
├── plugin.json                     # Antigravity plugin manifest
├── pyproject.toml                  # Python packaging & dependencies
├── README.md                       # Repository documentation
└── SKILL.md                        # Master Antigravity Agent Skill specification
```

---

## 🚀 Quick Start & CLI Usage

### Prerequisites
* Python 3.11+
* [uv](https://docs.astral.sh/uv/) (recommended) or standard `pip`

```bash
# Clone the repository
git clone https://github.com/<your-username>/medical-lecture-transcriber.git
cd medical-lecture-transcriber

# Install dependencies and run tests
uv run pytest
```

### Running Pipeline Commands

The pipeline is managed via `scripts/run_pipeline.py`:

```bash
# 1. Chunk audio into manageable 10-minute segments
uv run python scripts/run_pipeline.py chunk --input lecture.m4a --output-dir chunks/

# 2. Extract presentation slides and images (with auto OCR)
uv run python scripts/run_pipeline.py extract --input presentation.pptx --output raw_slides.json --images-dir slide_images/

# 3. Transcribe audio chunks with Gemini Multimodal API
uv run python scripts/run_pipeline.py transcribe --audio-dir chunks/ --output transcripts/ --model gemini-2.0-flash

# 4. Verify slide translation alignment & concept recall
uv run python scripts/run_pipeline.py verify-slides --raw raw_slides.json --translated translated_slides.json

# 5. Verify spoken lecture coverage & chronological order
uv run python scripts/run_pipeline.py verify-lecture --translated translated_slides.json --chunks-dir chunks/

# 6. Compile the final publication Word document
uv run python scripts/run_pipeline.py build --translated translated_slides.json --output lecture_pamphlet.docx --ref-book هاریسون --verify
```

---

## 🎨 Typography & Word Styling Palette

All Microsoft Word documents (`.docx`) generated by this tool follow strict institutional medical typography:

| Component | Font | Size | Weight | Color (HEX) | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Document Title** | Dubai | 16pt | Bold | `#78281F` (Burgundy) | Title header |
| **Section Heading (H1)** | Dubai | 14pt | Bold | `#78281F` (Burgundy) | Chapter / Topic divisions |
| **Timestamp Tag** | Dubai | 10pt | Bold | `#D35400` (Deep Orange) | Audio position tag `[⏱️ زمان: XX:YY]` |
| **Subheadings (H2)** | Dubai | 11pt | Bold | `#0E6251` (Forest Emerald) | Clinical sub-topics |
| **Body Paragraphs** | Dubai | 11pt | Regular | `#262626` (Charcoal) | Professor lecture monologue |
| **Slide Box Header** | Dubai | 10.5pt | Bold | `#1B4F72` on `#EBF5FB` | Slide banner `📑 اسلاید مرتبط X` |
| **Slide Box Border** | - | 1pt | - | `#85C1E9` (Sky Blue) | Clean structural outline |
| **Ref Note Header** | Dubai | 10pt | Bold | `#6C3483` (Royal Purple) | Textbook clarification banner |
| **Student Review** | Dubai | 10.5pt | Bold | `#D35400` on `#FEF9E7` | Amber advisory badge |

---

## 🧪 Testing

To run the full suite of **103 automated tests**:

```bash
uv run pytest -v
```

All 103 tests pass in under 3 seconds with zero external network calls.

---

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.
