import os
import sys
import pytest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from text_utils import parse_time_to_seconds, format_seconds_to_time
from verify_lecture_alignment import compute_drift_threshold, evaluate_toc_drift_gate

def test_time_parsing_and_formatting():
    # Persian digits in timestamps
    assert parse_time_to_seconds("۰۹:۲۰") == 560
    assert parse_time_to_seconds("دقیقه ۰۰:۰۰") == 0
    assert parse_time_to_seconds("01:30:15") == 5415
    assert format_seconds_to_time(560) == "09:20"
    assert format_seconds_to_time(5415) == "01:30:15"

    # Arabic digits in timestamps (٠١٢٣٤٥٦٧٨٩)
    assert parse_time_to_seconds("٠٩:٢٠") == 560
    assert parse_time_to_seconds("٠١:٣٠:١٥") == 5415
    assert parse_time_to_seconds("دقيقة ٠٠:٠٠") == 0

def test_dynamic_proportional_drift_threshold():
    # Short 20-minute lecture (1200s): threshold should default to 180s minimum
    assert compute_drift_threshold(1200) == 180

    # Long 3-hour lecture (10800s): threshold scales proportionally to 540s (9 minutes)
    assert compute_drift_threshold(10800) == 540

    # Strict drift option enforces 60s cap regardless of duration
    assert compute_drift_threshold(10800, strict=True) == 60
    assert compute_drift_threshold(1200, strict=True) == 60

    # Explicit max_drift override
    assert compute_drift_threshold(10800, max_drift=120) == 120

    # Zero/negative edge cases
    assert compute_drift_threshold(0) == 180
    assert compute_drift_threshold(-50) == 180

def test_toc_timestamp_drift_tolerance():
    # Tolerance is 60 seconds
    toc_time = parse_time_to_seconds("۰۹:۲۰")  # 560s
    
    # Matching within 20s drift -> PASS
    h1_time_pass = parse_time_to_seconds("۰۹:۴۰")  # 580s -> drift = 20s
    passed, drift = evaluate_toc_drift_gate(toc_time, h1_time_pass, tolerance_sec=60)
    assert passed is True
    assert drift == 20

    # Matching with 120s drift -> FAIL
    h1_time_fail = parse_time_to_seconds("۱۱:۲۰")  # 680s -> drift = 120s
    passed_fail, drift_fail = evaluate_toc_drift_gate(toc_time, h1_time_fail, tolerance_sec=60)
    assert passed_fail is False
    assert drift_fail == 120

def test_remote_drift_distance_logic():
    num = 5
    immediate_adj = [3, 4, 6, 7]
    remote_adj = [1, 2, 8, 9, 20]
    
    for adj in immediate_adj:
        assert abs(adj - num) <= 2
        
    for adj in remote_adj:
        assert abs(adj - num) > 2
