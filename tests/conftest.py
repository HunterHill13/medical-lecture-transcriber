import sys
import pathlib

# Ensure scripts directory is on sys.path regardless of where pytest is invoked from
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
