#!/usr/bin/env python3
"""
run_pipeline.py: Unified CLI Orchestrator for the Medical Lecture Transcriber Pipeline.
Connects all stages from raw audio & presentation files to the final verified publication-grade Word study guide.

Commands:
    status         Inspect workspace artifacts, pipeline progress, and show next steps.
    extract        Extract raw slides and images from PPTX or PDF.
    chunk          Split lecture audio into lightweight chunks.
    verify-slides  Validate slide index invariance, counts, and ref_notes.
    verify-lecture Validate audio timestamps, concept density, and track isolation.
    verify         Run both slide and lecture verification gates.
    build          Build the final publication-grade Word document.
    annotate       Inject structured RTL callout notes into existing DOCX (Mode B).
    all            Execute full deterministic pipeline (extract -> chunk -> verify -> build).

Usage:
    uv run python scripts/run_pipeline.py status
    uv run python scripts/run_pipeline.py extract --presentation slides.pdf
    uv run python scripts/run_pipeline.py chunk --audio lecture.m4a
    uv run python scripts/run_pipeline.py verify
    uv run python scripts/run_pipeline.py build --output lecture_pamphlet.docx
    uv run python scripts/run_pipeline.py annotate --docx slides.docx --annotations notes.json
"""

import os
import sys
import glob
import shutil
import argparse
import subprocess
import traceback

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def get_py_runner():
    """Returns the current Python executable for fast, deterministic, offline subprocess execution without nested uv resolution."""
    return [sys.executable]

def run_cmd(cmd_list, description="Executing command"):
    print(f"\n🚀 {description}...")
    print(f"   Command: {' '.join(cmd_list)}")
    res = subprocess.run(cmd_list)
    if res.returncode != 0:
        print(f"❌ Error: Command failed with exit code {res.returncode}")
        return False
    return True

DEFAULT_DOCX_PATTERNS = [
    "output/*.docx",
    "pamphlet/*.docx",
    "pamphlets/*.docx",
    "docs/*.docx",
    "متن جزوه/*کامل*.docx",
    "متن جزوه/*جامع*.docx",
    "متن جزوه/*.docx",
    "*pamphlet*.docx",
    "*study_guide*.docx",
    "*کامل*.docx",
    "*جامع*.docx",
    "*جزوه*.docx",
    "*.docx"
]

def find_first_match(patterns):
    for pat in patterns:
        matches = [m for m in glob.glob(pat) if not os.path.basename(m).startswith("~$")]
        if matches:
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]
    return None

def check_status(args):
    print("=" * 65)
    print("📋 MEDICAL LECTURE TRANSCRIBER — PIPELINE STATUS DASHBOARD")
    print("=" * 65)
    
    # 1. Inputs
    pres_file = find_first_match(["*.pptx", "*.pdf"])
    audio_file = find_first_match(["*.m4a", "*.mp3", "*.wav", "*.ogg"])
    
    # 2. Intermediate artifacts
    raw_slides = "raw_slides.json" if os.path.exists("raw_slides.json") else None
    slide_images = "slide_images" if os.path.isdir("slide_images") and os.listdir("slide_images") else None
    chunks_dir = "chunks" if os.path.isdir("chunks") and os.listdir("chunks") else ("scratch_chunks" if os.path.isdir("scratch_chunks") else None)
    
    # Transcripts
    trans_files = glob.glob("transcripts/*.txt") + glob.glob("scratch/*.txt") + glob.glob("*transcript*.txt")
    trans_dir = os.path.dirname(trans_files[0]) if trans_files else None
    
    translated_slides = "translated_slides.json" if os.path.exists("translated_slides.json") else None
    annotations_file = find_first_match(["*annotation*.json", "annotations.json"])
    
    # 3. Output
    docx_file = find_first_match(DEFAULT_DOCX_PATTERNS)
    
    def badge(found, label):
        return f"✅ READY: {label}" if found else f"⏳ MISSING: {label}"

    print("\n[Input Assets]")
    print(f"  • Presentation File : {badge(pres_file, pres_file or '*.pptx / *.pdf')}")
    print(f"  • Lecture Audio     : {badge(audio_file, audio_file or '*.m4a / *.mp3 / *.wav')}")

    print("\n[Extraction & Preprocessing]")
    print(f"  • Raw Slides JSON   : {badge(raw_slides, raw_slides or 'raw_slides.json')}")
    print(f"  • Slide Screenshots : {badge(slide_images, slide_images or 'slide_images/')}")
    print(f"  • Audio Chunks      : {badge(chunks_dir, chunks_dir or 'chunks/')}")

    print("\n[AI Pedagogical Content (LLM Tasks)]")
    print(f"  • Audio Transcripts : {badge(bool(trans_files), f'{len(trans_files)} transcript chunk files' if trans_files else 'transcripts/*.txt')}")
    print(f"  • Translated Slides : {badge(translated_slides, translated_slides or 'translated_slides.json')}")
    print(f"  • Mode B Annotations: {badge(annotations_file, annotations_file or 'annotations.json')}")

    print("\n[Final Output & Verification]")
    print(f"  • Final Study Guide : {badge(docx_file, docx_file or '*.docx')}")
    
    print("\n" + "-" * 65)
    print("👉 ACTIONABLE NEXT STEP:")
    if not pres_file and not audio_file:
        print("   Place your presentation (.pptx or .pdf) and lecture audio (.m4a/.mp3) into this directory.")
    elif not raw_slides:
        print(f"   Run extraction: uv run python scripts/run_pipeline.py extract --presentation \"{pres_file}\"")
    elif not chunks_dir:
        print(f"   Run chunking:   uv run python scripts/run_pipeline.py chunk --audio \"{audio_file}\"")
    elif not trans_files:
        print("   ⚡ MANDATORY: Transcribe audio chunks with Gemini Multimodal (view_file on chunks/chunk_XX.m4a or scripts/transcribe_chunks.py). DO NOT install Whisper/CUDA!")
    elif not translated_slides:
        print("   Translate extracted slides into 'translated_slides.json' matching raw slide count.")
    else:
        print("   Run verification and compile docx: uv run python scripts/run_pipeline.py build")
    print("-" * 65)

def cmd_extract(args):
    pres = args.presentation or find_first_match(["*.pptx", "*.pdf"])
    if not pres:
        print("❌ Error: No presentation file found. Specify with --presentation <file.pptx/.pdf>")
        return 1
    script = os.path.join(SCRIPTS_DIR, "extract_presentation.py")
    cmd = get_py_runner() + [script, "--input", pres, "--output", args.output, "--img-dir", args.img_dir]
    return 0 if run_cmd(cmd, f"Extracting presentation from {pres}") else 1

def cmd_chunk(args):
    audio = args.audio or find_first_match(["*.m4a", "*.mp3", "*.wav", "*.ogg"])
    if not audio:
        print("❌ Error: No audio file found. Specify with --audio <file.m4a>")
        return 1
    script = os.path.join(SCRIPTS_DIR, "chunk_audio.py")
    cmd = get_py_runner() + [script, audio, "--output-dir", args.output_dir, "--chunk-len", str(args.chunk_len), "--overlap", str(args.overlap), "--bitrate", args.bitrate]
    if args.duration:
        cmd.extend(["--duration", str(args.duration)])
    return 0 if run_cmd(cmd, f"Splitting lecture audio from {audio}") else 1

def cmd_transcribe(args):
    script = os.path.join(SCRIPTS_DIR, "transcribe_chunks.py")
    cmd = get_py_runner() + [script, "--manifest", args.manifest, "--chunks-dir", args.chunks_dir, "--output-dir", args.output_dir, "--model", args.model]
    if args.api_key:
        cmd.extend(["--api-key", args.api_key])
    return 0 if run_cmd(cmd, "Transcribing audio chunks via Gemini") else 1

def cmd_verify_slides(args):
    raw = args.raw or "raw_slides.json"
    trans = args.translated or "translated_slides.json"
    if not os.path.exists(raw) or not os.path.exists(trans):
        print(f"❌ Error: Required files missing. Ensure '{raw}' and '{trans}' exist.")
        return 1
    script = os.path.join(SCRIPTS_DIR, "verify_slide_alignment.py")
    cmd = get_py_runner() + [script, "--raw", raw, "--translated", trans]
    if args.auto_fix:
        cmd.append("--auto-fix")
    if getattr(args, "ref_corpus", None):
        cmd.extend(["--ref-corpus", args.ref_corpus])
    if getattr(args, "allow_review", False):
        cmd.append("--allow-review")
    return 0 if run_cmd(cmd, "Running Slide Alignment & Index Invariance Verification Gate") else 1

def cmd_verify_lecture(args):
    docx_file = args.docx or find_first_match(DEFAULT_DOCX_PATTERNS)
    trans_dir = args.transcripts_dir or ("transcripts" if os.path.isdir("transcripts") else "scratch")
    if not docx_file:
        print("❌ Error: No Word document found to verify. Specify with --docx <file.docx>")
        return 1
    script = os.path.join(SCRIPTS_DIR, "verify_lecture_alignment.py")
    cmd = get_py_runner() + [script, "--docx", docx_file, "--transcripts-dir", trans_dir]
    if args.raw_slides and os.path.exists(args.raw_slides):
        cmd.extend(["--raw-slides", args.raw_slides])
    if getattr(args, "min_chunk_duration", None):
        cmd.extend(["--min-chunk-duration", str(args.min_chunk_duration)])
    if getattr(args, "strict_drift", False):
        cmd.append("--strict-drift")
    if getattr(args, "max_drift", None) is not None:
        cmd.extend(["--max-drift", str(args.max_drift)])
    trans = getattr(args, "translated", None) or ("translated_slides.json" if os.path.exists("translated_slides.json") else None)
    if trans and os.path.exists(trans):
        cmd.extend(["--translated", trans])
    if getattr(args, "allow_review", False):
        cmd.append("--allow-review")
    return 0 if run_cmd(cmd, "Running Lecture Audio Alignment & Concept Recall Gate") else 1

def cmd_verify_all(args):
    res_s = cmd_verify_slides(args)
    if res_s != 0:
        return res_s
    docx_file = args.docx or find_first_match(DEFAULT_DOCX_PATTERNS)
    if not docx_file:
        print("\n✅ Pre-build Slide Alignment Gate PASSED.")
        print("ℹ️ Note: No Word document found yet to verify lecture audio alignment.")
        print("💡 Next step: Run 'python scripts/run_pipeline.py build --verify' or 'python scripts/run_pipeline.py publish' to compile and verify the Word study guide.")
        return 0
    return cmd_verify_lecture(args)

def cmd_build(args):
    if getattr(args, "verify", False):
        print("🔍 Pre-build verification requested: Validating slide alignment...")
        res_s = cmd_verify_slides(args)
        if res_s != 0:
            print("❌ Build aborted due to slide alignment errors.")
            return res_s

    trans = args.translated or "translated_slides.json"
    output = args.output or "lecture_pamphlet.docx"
    script = os.path.join(SCRIPTS_DIR, "create_slide_pamphlet.py")
    cmd = get_py_runner() + [script, "--translated", trans, "--output", output, "--img-dir", args.img_dir]
    if args.title:
        cmd.extend(["--title", args.title])
    if args.ref_book:
        cmd.extend(["--ref-book", args.ref_book])
    build_ok = run_cmd(cmd, f"Compiling publication-grade Word study guide to {output}")
    if not build_ok:
        return 1

    if getattr(args, "verify", False):
        print("🔍 Post-build verification requested: Validating lecture audio alignment...")
        # Point to the freshly built docx
        args.docx = output
        res_l = cmd_verify_lecture(args)
        if res_l != 0:
            print("❌ Build post-verification failed.")
            return res_l

    return 0

def cmd_publish(args):
    """Certified publication pipeline: strictly enforces all verification gates before and after building."""
    print("🎓 Executing Certified Publication Workflow...")
    res_s = cmd_verify_slides(args)
    if res_s != 0:
        print("❌ Publication aborted: Slide alignment gate failed.")
        return res_s
    res_b = cmd_build(args)
    if res_b != 0:
        print("❌ Publication aborted: Document build failed.")
        return res_b
    args.docx = args.output or "lecture_pamphlet.docx"
    res_l = cmd_verify_lecture(args)
    if res_l != 0:
        print("❌ Publication failed: Lecture alignment gate failed.")
        return res_l
    print("🏆 Document successfully certified and published!")
    return 0

def cmd_annotate(args):
    docx_file = args.docx or find_first_match(["*.docx"])
    annotations = args.annotations or find_first_match(["*annotation*.json", "annotations.json"])
    output = args.output or "annotated_pamphlet.docx"
    if not docx_file or not os.path.exists(docx_file):
        print(f"❌ Error: Input DOCX file '{docx_file}' not found. Specify with --docx <file.docx>")
        return 1
    if not annotations or not os.path.exists(annotations):
        print(f"❌ Error: Annotations JSON file '{annotations}' not found. Specify with --annotations <file.json>")
        return 1
    script = os.path.join(SCRIPTS_DIR, "annotate_docx.py")
    cmd = get_py_runner() + [script, docx_file, annotations, "--output-docx", output]
    return 0 if run_cmd(cmd, f"Injecting structured RTL callout notes into {docx_file}") else 1

def cmd_test(args):
    tests_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), "tests")
    if not os.path.exists(tests_dir):
        print(f"❌ Error: Tests directory not found at '{tests_dir}'")
        return 1
    if shutil.which("uv"):
        cmd = ["uv", "run", "--with", "pytest", "--with", "python-docx", "pytest", tests_dir]
    else:
        cmd = [sys.executable, "-m", "pytest", tests_dir]
    return 0 if run_cmd(cmd, "Running Automated Unit Test Suite (pytest)") else 1

def cmd_all(args):
    print("🚀 Running complete pipeline workflow...")
    if cmd_extract(args) != 0:
        return 1
    if cmd_chunk(args) != 0:
        return 1
    if os.path.exists("translated_slides.json"):
        if cmd_verify_slides(args) != 0:
            return 1
        if cmd_build(args) != 0:
            return 1
        res_l = cmd_verify_lecture(args)
        if res_l != 0:
            print("❌ Error: Lecture alignment verification failed. Terminating pipeline.")
            return res_l
    else:
        print("\n⏳ Note: 'translated_slides.json' not yet generated. Complete LLM translation before build.")
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Unified Orchestrator for the Medical Lecture Transcriber Pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Pipeline Stage Command")

    # status
    p_status = subparsers.add_parser("status", help="Inspect workspace and pipeline artifacts")

    # extract
    p_extract = subparsers.add_parser("extract", help="Extract raw slides from PPTX/PDF")
    p_extract.add_argument("--presentation", "-p", help="Path to input presentation (.pptx/.pdf)")
    p_extract.add_argument("--output", "-o", default="raw_slides.json", help="Output JSON path")
    p_extract.add_argument("--img-dir", default="./slide_images", help="Output directory for slide images")

    # chunk
    p_chunk = subparsers.add_parser("chunk", help="Split lecture audio into lightweight chunks")
    p_chunk.add_argument("--audio", "-a", help="Path to input audio file")
    p_chunk.add_argument("--output-dir", default="./chunks", help="Output chunks directory")
    p_chunk.add_argument("--chunk-len", type=int, default=540, help="Chunk length in seconds (default 540)")
    p_chunk.add_argument("--overlap", type=int, default=10, help="Chunk overlap in seconds (default 10)")
    p_chunk.add_argument("--bitrate", default="48k", help="Audio bitrate")
    p_chunk.add_argument("--duration", type=float, default=None, help="Explicit total duration")

    # transcribe
    p_transcribe = subparsers.add_parser("transcribe", help="Transcribe audio chunks with Gemini Multimodal (Cloud REST or guidance for view_file)")
    p_transcribe.add_argument("--manifest", default="chunks_manifest.json", help="Path to chunks manifest JSON")
    p_transcribe.add_argument("--chunks-dir", default="./chunks", help="Directory with audio chunks")
    p_transcribe.add_argument("--output-dir", default="./transcripts", help="Output directory for transcript text files")
    p_transcribe.add_argument("--model", default="gemini-2.0-flash", help="Gemini model name")
    p_transcribe.add_argument("--api-key", default=None, help="Gemini API Key")

    # verify-slides
    p_vslides = subparsers.add_parser("verify-slides", help="Validate slide alignment and index invariance")
    p_vslides.add_argument("--raw", default="raw_slides.json", help="Path to raw_slides.json")
    p_vslides.add_argument("--translated", default="translated_slides.json", help="Path to translated_slides.json")
    p_vslides.add_argument("--auto-fix", action="store_true", help="Auto-fix missing slide gaps")
    p_vslides.add_argument("--ref-corpus", help="Optional path to reference book corpus for ref_note grounding verification")

    # verify-lecture
    p_vlecture = subparsers.add_parser("verify-lecture", help="Validate audio timestamps and substantive density")
    p_vlecture.add_argument("--docx", help="Path to generated .docx file")
    p_vlecture.add_argument("--transcripts-dir", default="transcripts", help="Directory with transcript chunks")
    p_vlecture.add_argument("--raw-slides", default="raw_slides.json", help="Optional path to raw_slides.json for track isolation check")
    p_vlecture.add_argument("--translated", default="translated_slides.json", help="Path to translated_slides.json")
    p_vlecture.add_argument("--min-chunk-duration", type=int, default=30, help="Minimum chunk duration in seconds to evaluate in Stage 3 coverage (default 30)")
    p_vlecture.add_argument("--strict-drift", action="store_true", help="Enforce strict 60-second drift cap regardless of lecture length")
    p_vlecture.add_argument("--max-drift", type=int, default=None, help="Explicit maximum allowed drift seconds")
    p_vlecture.add_argument("--allow-review", action="store_true", help="Permit pipeline to complete with status REVIEW_REQUIRED (generating document with warning badges) instead of hard exit 1")

    # verify
    p_verify = subparsers.add_parser("verify", help="Run both slide and lecture verification gates")
    p_verify.add_argument("--raw", default="raw_slides.json")
    p_verify.add_argument("--translated", default="translated_slides.json")
    p_verify.add_argument("--auto-fix", action="store_true")
    p_verify.add_argument("--docx")
    p_verify.add_argument("--transcripts-dir", default="transcripts")
    p_verify.add_argument("--raw-slides", default="raw_slides.json")
    p_verify.add_argument("--ref-corpus", help="Optional path to reference book corpus")
    p_verify.add_argument("--min-chunk-duration", type=int, default=30)
    p_verify.add_argument("--strict-drift", action="store_true", help="Enforce strict 60-second drift cap regardless of lecture length")
    p_verify.add_argument("--max-drift", type=int, default=None, help="Explicit maximum allowed drift seconds")
    p_verify.add_argument("--allow-review", action="store_true", help="Permit pipeline to complete with status REVIEW_REQUIRED (generating document with warning badges) instead of hard exit 1")

    # build
    p_build = subparsers.add_parser("build", help="Compile final Word pamphlet")
    p_build.add_argument("--translated", default="translated_slides.json")
    p_build.add_argument("--output", default="lecture_pamphlet.docx")
    p_build.add_argument("--title", default="جزوه جامع پزشکی")
    p_build.add_argument("--ref-book", choices=["هاریسون", "برانوالد", "شوارتز", "نلسون", "ویلیامز", "رابینز", "کاتزونگ", "گایتون"])
    p_build.add_argument("--img-dir", default="./slide_images")
    p_build.add_argument("--verify", action="store_true", help="Run alignment gates before and after building")
    p_build.add_argument("--raw", default="raw_slides.json", help="Path to raw_slides.json for verification")
    p_build.add_argument("--raw-slides", default="raw_slides.json", help="Path to raw_slides.json for track isolation")
    p_build.add_argument("--transcripts-dir", default="transcripts", help="Directory with transcript chunks")
    p_build.add_argument("--ref-corpus", help="Optional path to reference book corpus")
    p_build.add_argument("--min-chunk-duration", type=int, default=30)
    p_build.add_argument("--strict-drift", action="store_true")
    p_build.add_argument("--max-drift", type=int, default=None)
    p_build.add_argument("--allow-review", action="store_true")
    p_build.add_argument("--auto-fix", action="store_true")

    # publish
    p_publish = subparsers.add_parser("publish", help="Certified publication pipeline: verify -> build -> post-verify")
    p_publish.add_argument("--translated", default="translated_slides.json")
    p_publish.add_argument("--output", default="lecture_pamphlet.docx")
    p_publish.add_argument("--title", default="جزوه جامع پزشکی")
    p_publish.add_argument("--ref-book", choices=["هاریسون", "برانوالد", "شوارتز", "نلسون", "ویلیامز", "رابینز", "کاتزونگ", "گایتون"])
    p_publish.add_argument("--img-dir", default="./slide_images")
    p_publish.add_argument("--raw", default="raw_slides.json")
    p_publish.add_argument("--raw-slides", default="raw_slides.json")
    p_publish.add_argument("--transcripts-dir", default="transcripts")
    p_publish.add_argument("--ref-corpus", help="Optional path to reference book corpus")
    p_publish.add_argument("--min-chunk-duration", type=int, default=30)
    p_publish.add_argument("--strict-drift", action="store_true")
    p_publish.add_argument("--max-drift", type=int, default=None)
    p_publish.add_argument("--allow-review", action="store_true")
    p_publish.add_argument("--auto-fix", action="store_true")

    # annotate
    p_annotate = subparsers.add_parser("annotate", help="Inject structured RTL callout notes into existing DOCX (Mode B)")
    p_annotate.add_argument("--docx", "-d", help="Path to original docx file")
    p_annotate.add_argument("--annotations", "-a", help="Path to JSON file with annotations")
    p_annotate.add_argument("--output", "-o", default="annotated_pamphlet.docx", help="Path to save annotated docx file")

    # test
    p_test = subparsers.add_parser("test", help="Run automated test suite (pytest) for gates, schema, and normalization")

    # all
    p_all = subparsers.add_parser("all", help="Execute complete deterministic flow")
    p_all.add_argument("--presentation", "-p")
    p_all.add_argument("--audio", "-a")
    p_all.add_argument("--output", "-o", default="raw_slides.json")
    p_all.add_argument("--img-dir", default="./slide_images")
    p_all.add_argument("--output-dir", default="./chunks")
    p_all.add_argument("--chunk-len", type=int, default=540)
    p_all.add_argument("--overlap", type=int, default=10)
    p_all.add_argument("--bitrate", default="48k")
    p_all.add_argument("--duration", type=float, default=None)
    p_all.add_argument("--raw", default="raw_slides.json")
    p_all.add_argument("--translated", default="translated_slides.json")
    p_all.add_argument("--auto-fix", action="store_true")
    p_all.add_argument("--docx")
    p_all.add_argument("--transcripts-dir", default="transcripts")
    p_all.add_argument("--raw-slides", default="raw_slides.json")
    p_all.add_argument("--title", default="جزوه جامع پزشکی")
    p_all.add_argument("--ref-book", choices=["هاریسون", "برانوالد", "شوارتز", "نلسون", "ویلیامز", "رابینز", "کاتزونگ", "گایتون"])
    p_all.add_argument("--strict-drift", action="store_true", help="Enforce strict 60-second drift cap regardless of lecture length")
    p_all.add_argument("--max-drift", type=int, default=None, help="Explicit maximum allowed drift seconds")
    p_all.add_argument("--allow-review", action="store_true", help="Permit pipeline to complete with status REVIEW_REQUIRED (generating document with warning badges) instead of hard exit 1")


    args = parser.parse_args()
    try:
        if not args.command or args.command == "status":
            check_status(args)
        elif args.command == "extract":
            sys.exit(cmd_extract(args))
        elif args.command == "chunk":
            sys.exit(cmd_chunk(args))
        elif args.command == "transcribe":
            sys.exit(cmd_transcribe(args))
        elif args.command == "verify-slides":
            sys.exit(cmd_verify_slides(args))
        elif args.command == "verify-lecture":
            sys.exit(cmd_verify_lecture(args))
        elif args.command == "verify":
            sys.exit(cmd_verify_all(args))
        elif args.command == "build":
            sys.exit(cmd_build(args))
        elif args.command == "publish":
            sys.exit(cmd_publish(args))
        elif args.command == "annotate":
            sys.exit(cmd_annotate(args))
        elif args.command == "test":
            sys.exit(cmd_test(args))
        elif args.command == "all":
            sys.exit(cmd_all(args))
    except KeyboardInterrupt:
        print("\n[interrupted] Pipeline stopped by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"[pipeline error] {type(e).__name__}: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
