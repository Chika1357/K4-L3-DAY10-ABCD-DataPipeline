# Báo Cáo Cá Nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| Họ và tên | Nguyễn Trần Kiên |
| MSSV | 2A2202602571 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Nhóm ABCD |
| Vai trò chính | Data Observability & Benchmark Evaluation Lead |
| Repository | `https://github.com/Chika1357/K4-L3-DAY10-ABCD-DataPipeline` |
| Ngày hoàn thành | 2026-09-26 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Data Quality Gate | `src/observability/quality.py` | DataFrame (Clean / Corrupted) | Báo cáo kiểm định Great Expectations 1.x | Hoàn thành 100% |
| Freshness SLA Monitoring | `src/observability/quality.py` | DataFrame, threshold 180d | Báo cáo độ tươi Freshness SLA | Hoàn thành 100% |
| Evaluation Testset | `src/evaluation/testset.py` | Clean DataFrame | Bộ đề thi 10 câu hỏi cân bằng `data/eval/test_set.json` | Hoàn thành 100% |
| Reporting & Metrics | `src/observability/reporting.py`, `metrics.py` | Kết quả kiểm định & đo lường | `phase1_report.md`, `corruption_report.md` | Hoàn thành 100% |

### Việc hỗ trợ ngoài phạm vi chính
- Tạo test suite độc lập `script/test_member3.py` để cả nhóm có thể xác thực nhanh toàn bộ tầng Observability và Evaluation mà không cần chạy các mô hình embedding nặng.
- Cùng Trưởng nhóm rà soát ma trận so sánh 3 trạng thái trong báo cáo tổng kết nhóm.

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Thiết lập chốt kiểm dịch Great Expectations 1.x | `src/observability/quality.py` | 4 expectations kiểm soát Completeness, Validity, Uniqueness | Chạy `python script/test_member3.py` |
| Giám sát Freshness SLA | `src/observability/quality.py` | Đo tỷ lệ stale rows theo ngưỡng 180 ngày (tối đa 25%) | Báo cáo `data/quality/test_freshness.json` |
| Sinh bộ câu hỏi đánh giá chuẩn | `src/evaluation/testset.py` | 10 câu hỏi chia đều 4 dạng (summary, authors, date, categories) | Kiểm tra `data/eval/test_set.json` |
| Xuất ma trận đối chiếu 3 trạng thái | `src/observability/reporting.py` | Báo cáo Markdown 3 cột: Baseline vs Corrupted vs Repaired | Đọc `data/reports/corruption_report.md` |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Nếu không có hệ thống Data Observability, hiện tượng **Silent Failure** sẽ xảy ra: dữ liệu bị lỗi, thiếu hoặc sai lệch vẫn được nạp vào Vector Database, khiến hệ thống RAG âm thầm tư vấn sai thông tin cho người dùng mà không hề ném lỗi kỹ thuật.

### Cách triển khai
1. **Great Expectations 1.x Ephemeral Context:** Sử dụng cú pháp mới nhất của GX 1.x `gx.get_context(mode="ephemeral")` khởi tạo kiểm định trên Data Asset bộ nhớ tạm. Bao gồm 4 Expectations thiết yếu:
   - `ExpectTableRowCountToBeBetween` [5, 5000].
   - `ExpectColumnValuesToNotBeNull` (`paper_id`, `title`, `text_for_embedding`).
   - `ExpectColumnValuesToBeUnique` (`paper_id`).
   - `ExpectColumnValueLengthsToBeBetween` (`summary` ≥ 30 ký tự).
2. **Freshness SLA:** Kiểm tra khoảng cách ngày giữa thời điểm thực thi và ngày xuất bản (`age_days`). Nếu tỷ lệ bài báo quá hạn 180 ngày vượt quá 25%, hệ thống lập tức gắn cờ `is_fresh = False`.
3. **Cố định bộ đề thi (Testset Freezing):** Tạo 10 câu hỏi mẫu đại diện cho 4 tác vụ truy vấn thực tế, liên kết chặt chẽ với Ground Truth DOI để đo lường định lượng sự sụt giảm của Retrieval Hit Rate và Token F1 khi bị tiêm lỗi.

---

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Lựa chọn phiên bản và cách cấu hình Great Expectations.
- **Phương án cân nhắc:**
  1. Sử dụng Great Expectations 0.18 legacy với cấu hình thư mục `great_expectations/` cồng kềnh trên ổ đĩa.
  2. Sử dụng chuẩn mới Great Expectations 1.x với chế độ `ephemeral` hoàn toàn trong bộ nhớ.
- **Lựa chọn:** Phương án 2.
- **Lý do:** Chế độ `ephemeral` loại bỏ các file cấu hình YAML dư thừa, tương thích hoàn hảo với môi trường CI/CD và không gây xung đột Git giữa các thành viên.

---

## 6. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end của cả nhóm.
- [x] Báo cáo không chứa bất kỳ secret hay API key nào.

**Họ và tên:** Nguyễn Trần Kiên  
**Ngày xác nhận:** 2026-09-26
