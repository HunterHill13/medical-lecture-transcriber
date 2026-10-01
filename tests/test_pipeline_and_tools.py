import os
import sys
import pytest
import docx
from docx.oxml.ns import qn

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from chunk_audio import compute_chunk_ranges
from annotate_docx import (
    style_p,
    add_run,
    extract_page_number,
    annotate_docx
)

def test_compute_chunk_ranges_basic():
    # 1800s (30 min) audio, chunk_len=540, overlap=10
    ranges = compute_chunk_ranges(1800, chunk_len=540, overlap=10)
    assert len(ranges) == 4
    
    # Check first chunk
    assert ranges[0]["index"] == 1
    assert ranges[0]["start_sec"] == 0.0
    assert ranges[0]["duration_sec"] == 550.0  # 540 + 10 overlap
    assert ranges[0]["overlap_sec"] == 0
    
    # Check second chunk
    assert ranges[1]["index"] == 2
    assert ranges[1]["start_sec"] == 540.0
    assert ranges[1]["duration_sec"] == 550.0
    assert ranges[1]["overlap_sec"] == 10

def test_compute_chunk_ranges_ghost_chunk_prevention():
    # Audio with remaining trailing duration <= overlap should not spawn ghost chunk
    ranges = compute_chunk_ranges(545, chunk_len=540, overlap=10)
    # Remaining duration after first chunk starts at 0 is 545. Next chunk would start at 540, remaining 5s <= 10s overlap
    assert len(ranges) == 1
    assert ranges[0]["duration_sec"] == 545.0

def test_style_p_idempotent_xml_tags():
    doc = docx.Document()
    p = doc.add_paragraph("Test Paragraph")
    
    # Call style_p twice
    style_p(p)
    style_p(p)
    
    pPr = p._p.get_or_add_pPr()
    bidi_nodes = pPr.findall(qn('w:bidi'))
    jc_nodes = pPr.findall(qn('w:jc'))
    
    # Exactly one bidi and one jc tag should exist
    assert len(bidi_nodes) == 1
    assert len(jc_nodes) == 1

def test_add_run_font_xml_escaping():
    doc = docx.Document()
    p = doc.add_paragraph()
    
    # Font name containing quotes or angle brackets (XML injection test)
    malicious_font = 'Dubai" <script>evil</script>'
    run = add_run(p, "Sample Text", font_name=malicious_font)
    
    # Check run font name
    assert run.font.name == malicious_font
    # If XML parsing didn't throw and run was successfully added, escaping succeeded
    assert len(p.runs) == 1

def test_extract_page_number_variants():
    assert extract_page_number("Page_1") == 1
    assert extract_page_number("Page 12") == 12
    assert extract_page_number("اسلاید مرتبط ۳") == 3
    assert extract_page_number("اسلاید ۴۵") == 45
    assert extract_page_number("صفحه ۶") == 6
    assert extract_page_number("متن عمومی بدون شماره") is None
    assert extract_page_number("") is None

def test_annotate_docx_input_validation(tmp_path):
    missing_docx = str(tmp_path / "missing.docx")
    missing_json = str(tmp_path / "missing.json")
    out_docx = str(tmp_path / "out.docx")
    
    with pytest.raises(FileNotFoundError, match="Input docx not found"):
        annotate_docx(missing_docx, missing_json, out_docx)
        
    # Create empty docx
    real_docx = str(tmp_path / "real.docx")
    doc = docx.Document()
    doc.save(real_docx)
    
    with pytest.raises(FileNotFoundError, match="Annotations JSON not found"):
        annotate_docx(real_docx, missing_json, out_docx)

def test_annotate_docx_marker_matching(tmp_path):
    import json
    doc_path = str(tmp_path / "test_doc.docx")
    json_path = str(tmp_path / "annotations.json")
    out_path = str(tmp_path / "annotated.docx")
    
    # Document with a regular heading, a numbered slide page, and a body paragraph
    doc = docx.Document()
    doc.add_paragraph("Introduction Heading")
    doc.add_paragraph("Slide Page 1")
    doc.add_paragraph("Unrelated Body Paragraph without numbers")
    doc.save(doc_path)
    
    # Annotations: one numeric marker (Page 1) and one non-numeric heading marker ("Introduction Heading")
    # Also an unmatched marker ("NonExistent Marker") that should NOT falsely match paragraphs with None p_num
    annotations_data = {
        "boxes": [
            {
                "before_marker": "اسلاید ۱",
                "header": "Box 1 - Numeric Match",
                "sections": [{"title": "Note 1", "items": ["Item A"]}]
            },
            {
                "before_marker": "Introduction Heading",
                "header": "Box 2 - Non-Numeric Match",
                "sections": [{"title": "Note 2", "items": ["Item B"]}]
            },
            {
                "before_marker": "NonExistent Marker",
                "header": "Box 3 - Should Not Match",
                "sections": [{"title": "Note 3", "items": ["Item C"]}]
            }
        ]
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(annotations_data, f, ensure_ascii=False)
        
    annotate_docx(doc_path, json_path, out_path)
    
    # Verify the output document has exactly 2 callout tables inserted (Box 1 and Box 2), NOT 3
    annotated_doc = docx.Document(out_path)
    assert len(annotated_doc.tables) == 2

def test_build_pamphlet_json_validation(tmp_path):
    from create_slide_pamphlet import build_pamphlet_from_json
    
    missing_file = str(tmp_path / "does_not_exist.json")
    out_docx = str(tmp_path / "out.docx")
    
    # 1. Non-existent file
    with pytest.raises(FileNotFoundError, match="not found"):
        build_pamphlet_from_json(missing_file, out_docx)
        
    # 2. Malformed JSON
    corrupt_json = tmp_path / "corrupt.json"
    corrupt_json.write_text("{ unclosed json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON"):
        build_pamphlet_from_json(str(corrupt_json), out_docx)
        
    # 3. Non-list JSON root
    dict_json = tmp_path / "dict.json"
    dict_json.write_text('{"slides": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="Expected a JSON list"):
        build_pamphlet_from_json(str(dict_json), out_docx)

def test_add_cross_reference_box_execution():
    from create_slide_pamphlet import add_cross_reference_box
    
    doc = docx.Document()
    # Test forward reference
    add_cross_reference_box(doc, target_slide=5, note="مراجعه به اسلاید ۵ جهت مقایسه", direction="forward")
    # Test backward reference
    add_cross_reference_box(doc, target_slide=2, note="همان‌طور که در اسلاید ۲ دیدیم", direction="backward")
    
    # Both calls should succeed and create table boxes
    assert len(doc.tables) == 2


def test_transcribe_chunks_mime_type_and_policy():
    from transcribe_chunks import get_mime_type
    assert get_mime_type("chunk_01.m4a") == "audio/mp4"
    assert get_mime_type("audio.mp3") == "audio/mp3"
    assert get_mime_type("speech.wav") == "audio/wav"
    assert get_mime_type("recording.ogg") == "audio/ogg"

