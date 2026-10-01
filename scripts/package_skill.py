#!/usr/bin/env python3
"""
package_skill.py: Cross-platform, deterministic POSIX-compliant ZIP packager for medical-lecture-transcriber.
Guarantees:
1. 100% Forward-slash path separators ('/') for perfect Linux/macOS/Windows cross-platform compatibility.
2. Zero __pycache__, zero .pyc files, zero .venv or .pytest_cache files.
3. Strict non-empty package validation (raises RuntimeError if 0 files discovered).
4. Full portability: supports CLI arguments with smart automatic source discovery.
"""

import os
import sys
import zipfile
import shutil
import argparse

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def discover_source(provided_source: str = None) -> str:
    """Finds the skill directory deterministically across different run locations."""
    if provided_source and os.path.isdir(provided_source):
        return os.path.abspath(provided_source)
        
    candidates = [
        os.path.abspath(".agents/skills/medical-lecture-transcriber"),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        os.path.abspath("skills/medical-lecture-transcriber"),
        os.path.abspath(".")
    ]
    for cand in candidates:
        if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "SKILL.md")) and os.path.isdir(os.path.join(cand, "scripts")):
            return cand
            
    raise RuntimeError("Could not automatically locate the 'medical-lecture-transcriber' source directory. Specify with --source.")

def clean_cache(target_dir: str):
    """Removes __pycache__, .pytest_cache, and .pyc/.pyo files."""
    if not os.path.isdir(target_dir):
        return
    for root, dirs, files in os.walk(target_dir, topdown=False):
        for d in dirs:
            if d in ("__pycache__", ".pytest_cache"):
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass

def verify_version_consistency(source_dir: str):
    """Ensures version.py, plugin.json, and pyproject.toml all match the exact same version."""
    v_file = os.path.join(source_dir, "scripts", "version.py")
    if not os.path.isfile(v_file):
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("version", v_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected_version = getattr(mod, "__version__", None)
    if not expected_version:
        return

    # Check plugin.json
    pj = os.path.join(source_dir, "plugin.json")
    if os.path.isfile(pj):
        import json
        with open(pj, "r", encoding="utf-8") as f:
            pdata = json.load(f)
            if pdata.get("version") != expected_version:
                raise RuntimeError(f"Version mismatch in plugin.json: expected {expected_version}, got {pdata.get('version')}")

    # Check pyproject.toml
    pp = os.path.join(source_dir, "pyproject.toml")
    if os.path.isfile(pp):
        import re
        with open(pp, "r", encoding="utf-8") as f:
            txt = f.read()
            m = re.search(r'version\s*=\s*["\']([^"\']+)["\']', txt)
            if m and m.group(1) != expected_version:
                raise RuntimeError(f"Version mismatch in pyproject.toml: expected {expected_version}, got {m.group(1)}")

def build_posix_zip(source_dir: str, output_zip: str) -> int:
    """Creates a deterministic ZIP from source_dir with 100% POSIX forward slashes."""
    if not os.path.isdir(source_dir):
        raise RuntimeError(f"Source directory does not exist: {source_dir}")
        
    verify_version_consistency(source_dir)
    clean_cache(source_dir)
    abs_out = os.path.abspath(output_zip)
    os.makedirs(os.path.dirname(abs_out), exist_ok=True)
    if os.path.exists(abs_out):
        os.remove(abs_out)

    total_files = 0
    with zipfile.ZipFile(abs_out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache", ".git", ".venv")]
            parts = os.path.relpath(root, source_dir).split(os.sep)
            if any(p in ("__pycache__", ".pytest_cache", ".git", ".venv") for p in parts):
                continue
                
            for file in sorted(files):
                if file.endswith((".pyc", ".pyo", ".DS_Store", ".zip")):
                    continue
                file_abs = os.path.join(root, file)
                rel_path = os.path.relpath(file_abs, source_dir)
                posix_arcname = rel_path.replace("\\", "/")
                zf.write(file_abs, arcname=posix_arcname)
                total_files += 1

    if total_files == 0:
        if os.path.exists(abs_out):
            os.remove(abs_out)
        raise RuntimeError(f"Packaging source directory is empty or invalid (0 files discovered in: {source_dir})")

    # Verification
    with zipfile.ZipFile(abs_out, "r") as zf:
        names = zf.namelist()
        has_backslash = any("\\" in n for n in names)
        has_pycache = any("__pycache__" in n or n.endswith(".pyc") for n in names)
        has_venv = any(".venv" in n for n in names)

    print(f"📦 Successfully created ZIP: {abs_out} ({total_files} files)")
    print(f"   • Path format: {'❌ FAIL (found backslashes)' if has_backslash else '✅ 100% POSIX /'}")
    print(f"   • Cache files: {'❌ FAIL (found pycache)' if has_pycache else '✅ ZERO (Clean)'}")
    print(f"   • Venv files:  {'❌ FAIL (found venv)' if has_venv else '✅ ZERO (Clean)'}")

    if has_backslash or has_pycache or has_venv:
        raise RuntimeError(f"ZIP package {abs_out} failed quality verification!")

    return total_files


def main():
    parser = argparse.ArgumentParser(description="Deterministic POSIX-compliant ZIP packager")
    parser.add_argument("--source", "-s", help="Source directory containing skill files (default: auto-detected)")
    parser.add_argument("--output", "-o", help="Output ZIP path (default: medical-lecture-transcriber.zip)")
    parser.add_argument("--sync-global", action="store_true", help="Also sync and package to ~/.gemini/config/plugins/medical-lecture-transcriber if present")
    parser.add_argument("--plugin-root", help="Global plugin root directory to sync before packaging")
    args = parser.parse_args()

    source_dir = discover_source(args.source)
    clean_cache(source_dir)

    # Determine global plugin root (optional, if on Windows with .gemini plugin structure)
    plugin_root = args.plugin_root
    if not plugin_root and args.sync_global:
        default_plugin_dir = os.path.expanduser("~/.gemini/config/plugins/medical-lecture-transcriber")
        if os.path.isdir(default_plugin_dir):
            plugin_root = default_plugin_dir

    if plugin_root and os.path.isdir(plugin_root):
        subskill_dir = os.path.join(plugin_root, "skills", "medical-lecture-transcriber")
        os.makedirs(subskill_dir, exist_ok=True)
        # Sync scripts & tests
        shutil.copytree(os.path.join(source_dir, "scripts"), os.path.join(subskill_dir, "scripts"), dirs_exist_ok=True)
        shutil.copytree(os.path.join(source_dir, "tests"), os.path.join(subskill_dir, "tests"), dirs_exist_ok=True)
        for cfg in ("SKILL.md", "pyproject.toml"):
            src_cfg = os.path.join(source_dir, cfg)
            if os.path.exists(src_cfg):
                shutil.copy2(src_cfg, os.path.join(subskill_dir, cfg))
        # Sync root pyproject.toml and plugin.json to plugin root
        src_pp = os.path.join(source_dir, "pyproject.toml")
        if os.path.exists(src_pp):
            shutil.copy2(src_pp, os.path.join(plugin_root, "pyproject.toml"))
        # Sync plugin.json if present
        src_pj = os.path.join(source_dir, "plugin.json")
        if os.path.exists(src_pj):
            shutil.copy2(src_pj, os.path.join(plugin_root, "plugin.json"))
        clean_cache(plugin_root)
        
        # Package global plugin
        global_zip = os.path.join(os.path.dirname(plugin_root), "medical-lecture-transcriber.zip")
        build_posix_zip(plugin_root, global_zip)

    # Also synchronize other known global skill directories if they exist (excluding redundant config/skills)
    if args.sync_global:
        additional_global_dirs = [
            os.path.expanduser("~/.gemini/antigravity/builtin/skills/medical-lecture-transcriber")
        ]
        for gdir in additional_global_dirs:
            if os.path.isdir(gdir):
                shutil.copytree(os.path.join(source_dir, "scripts"), os.path.join(gdir, "scripts"), dirs_exist_ok=True)
                shutil.copytree(os.path.join(source_dir, "tests"), os.path.join(gdir, "tests"), dirs_exist_ok=True)
                for cfg in ("SKILL.md", "pyproject.toml"):
                    src_cfg = os.path.join(source_dir, cfg)
                    if os.path.exists(src_cfg):
                        shutil.copy2(src_cfg, os.path.join(gdir, cfg))
                src_pj = os.path.join(source_dir, "plugin.json")
                if os.path.exists(src_pj):
                    shutil.copy2(src_pj, os.path.join(gdir, "plugin.json"))
                clean_cache(gdir)
                print(f"🔄 Synchronized global skill path: {gdir}")

    # Package local workspace ZIP
    workspace_zip = args.output or "medical-lecture-transcriber.zip"
    build_posix_zip(source_dir, workspace_zip)

if __name__ == "__main__":
    main()
