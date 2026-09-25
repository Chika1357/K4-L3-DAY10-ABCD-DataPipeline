import sys
import warnings
from pathlib import Path
from datetime import datetime, timezone

# Tránh lỗi font Unicode trên Windows console
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Bỏ qua cảnh báo phụ của requests/urllib3
warnings.filterwarnings("ignore", category=UserWarning)

# Đảm bảo src/ luôn nằm trong sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe

print("=== BAT DAU KIEM TRA CHO THANH VIEN 2 ===")

# Test 1: Ingestion (CP0)
s = load_settings()
records = fetch_source_records(s)
print(f"1. Ingestion Test (CP0): Da tai {len(records)} bai bao.")
assert len(records) == 24, f"Ky vong 24 bai bao, nhan {len(records)}"

# Test 2: Cleaning (CP1)
raw_records = load_raw_records(s.paths.raw_records_json)
df = build_clean_dataframe(raw_records, datetime.now(timezone.utc))
print(f"2. Cleaning Test (CP1): Clean thanh cong {len(df)} dong.")
assert len(df) == 24, f"Ky vong 24 dong sach, nhan {len(df)}"
assert "text_for_embedding" in df.columns, "Thieu cot text_for_embedding"
assert "age_days" in df.columns, "Thieu cot age_days"

# Test 3: Corruption (CP4)
corrupted_df = corrupt_clean_dataframe(df, s.paths.corruption_log)
print(f"3. Corruption Test (CP4): Corrupted {len(corrupted_df)} dong.")
assert len(corrupted_df) > 0, "Corrupted dataframe khong duoc rong"
assert s.paths.corruption_log.exists(), "File corruption_log.json phai ton tai"

print("=== TAT CA CAC TEST CUA THANH VIEN 2 DA PASS 100%! ===")
