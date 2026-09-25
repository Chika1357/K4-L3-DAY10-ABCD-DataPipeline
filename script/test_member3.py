import sys
import warnings
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

# Tranh loi font Unicode tren Windows console
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

warnings.filterwarnings("ignore")

# Dam bao src/ va .venv site-packages luon nam trong sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
venv_site = project_root / ".venv" / "Lib" / "site-packages"
if venv_site.exists() and str(venv_site) not in sys.path:
    sys.path.insert(0, str(venv_site))

from core.config import load_settings
from ingestion.crossref import load_raw_records
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from observability.quality import run_data_quality_checks, build_freshness_report
from evaluation.testset import build_test_set
from observability.reporting import generate_phase1_report, generate_corruption_report

print("=== BAT DAU KIEM TRA CHO THANH VIEN 3 ===")

s = load_settings()

# 1. Clean data chuan bi test
raw_records = load_raw_records(s.paths.raw_records_json)
clean_df = build_clean_dataframe(raw_records, datetime.now(timezone.utc))

# 2. Test Great Expectations 1.x tren du lieu sach (Ky vong: True)
gx_clean = run_data_quality_checks(clean_df, s, "baseline_test")
print(f"1. Quality Gate tren Clean Data: status={gx_clean['success']} (passed={gx_clean['passed_expectations']})")
assert gx_clean["success"] is True, "Clean data phai vuot qua Quality Gate"

# 3. Test Freshness SLA tren du lieu sach (Ky vong: is_fresh = True)
fresh_clean = build_freshness_report(clean_df, s, s.paths.quality_dir / "test_freshness.json")
print(f"2. Freshness SLA tren Clean Data: is_fresh={fresh_clean['is_fresh']} (stale_ratio={fresh_clean['stale_ratio']})")
assert fresh_clean["is_fresh"] is True, "Clean data phai dat chuan do tuoi Freshness SLA"

# 4. Test sinh bo de thi 10 cau hoi
test_set = build_test_set(clean_df, s.paths.eval_testset)
print(f"3. Test Set Generator: Da tao {len(test_set)} cau hoi.")
assert len(test_set) == 10, f"Ky vong dung 10 cau hoi, nhan {len(test_set)}"

# 5. Test Quality Gate tren Corrupted Data (Ky vong: False de chung minh phat hien duoc loi)
corrupted_df = corrupt_clean_dataframe(clean_df, s.paths.corruption_log)
gx_corrupted = run_data_quality_checks(corrupted_df, s, "corrupted_test")
print(f"4. Quality Gate tren Corrupted Data: status={gx_corrupted['success']} (failed={gx_corrupted['failed_expectations']})")
assert gx_corrupted["success"] is False, "Quality Gate phai phat hien du lieu bi loi va bao False"

# 6. Test Freshness SLA tren Corrupted Data (Ky vong: is_fresh = False vi bi lui ngay)
fresh_corrupted = build_freshness_report(corrupted_df, s, s.paths.quality_dir / "test_freshness_corrupted.json")
print(f"5. Freshness SLA tren Corrupted Data: is_fresh={fresh_corrupted['is_fresh']} (stale_ratio={fresh_corrupted['stale_ratio']})")
assert fresh_corrupted["is_fresh"] is False, "Freshness SLA phai bao dong du lieu bi stale"

# 7. Test sinh bao cao Markdown
mock_metrics = {"retrieval_hit_rate": 1.0, "mean_token_f1": 0.95, "judge_accuracy": 1.0, "mean_judge_score": 4.8}
mock_corr_metrics = {"retrieval_hit_rate": 0.7, "mean_token_f1": 0.5, "judge_accuracy": 0.5, "mean_judge_score": 2.5}
generate_phase1_report(s.paths.baseline_report, {"raw_records": 24, "clean_rows": 24, "test_questions": 10}, mock_metrics, gx_clean, fresh_clean)
generate_corruption_report(s.paths.comparison_report, mock_metrics, mock_corr_metrics, mock_metrics, gx_corrupted, gx_clean, fresh_corrupted, fresh_clean)
assert s.paths.baseline_report.exists(), "phase1_report.md phai ton tai"
assert s.paths.comparison_report.exists(), "corruption_report.md phai ton tai"
print("6. Bao cao Markdown: Da sinh thanh cong phase1_report.md va corruption_report.md")

print("=== TAT CA CAC TEST CUA THANH VIEN 3 DA PASS 100%! ===")
