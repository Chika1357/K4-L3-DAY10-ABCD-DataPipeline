# Báo Cáo Cá Nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| Họ và tên | Nguyễn Tuấn Thành |
| MSSV | 2A202602640 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Nhóm ABCD |
| Vai trò chính | Data Foundation & Corruption Specialist |
| Repository | `https://github.com/Chika1357/K4-L3-DAY10-ABCD-DataPipeline` |
| Ngày hoàn thành | 2026-09-26 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Source Ingestion | `src/ingestion/crossref.py` | Crossref REST API / Snapshot | Danh sách `PaperRecord` chuẩn hóa | Hoàn thành 100% |
| Data Cleaning & Modeling | `src/ingestion/cleaning.py` | `list[PaperRecord]` | DataFrame 16 cột, `text_for_embedding`, `age_days` | Hoàn thành 100% |
| Synthetic Corruption | `src/ingestion/corruption.py` | Clean DataFrame | Corrupted DataFrame & `corruption_log.json` | Hoàn thành 100% |
| Idempotent Repair | `src/pipelines/corruption_flow.py` (tích hợp) | Raw Snapshot JSON | Khôi phục 100% dữ liệu sạch | Hoàn thành 100% |

### Việc hỗ trợ ngoài phạm vi chính
- Xây dựng giao diện Web Studio trực quan phục vụ demo live trên lớp và slides thuyết trình (`tuanthanh_demo`).
- Hỗ trợ Member 3 xác thực các trường hợp kiểm định chất lượng đối với dữ liệu sau khi clean và sau khi corrupt.

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Thu thập và bảo tồn dữ liệu thô | `src/ingestion/crossref.py` | `data/raw/crossref_records.json` (24 bài báo) | Kiểm tra file JSON trong `data/raw/` |
| Làm sạch và chuẩn hóa schema | `src/ingestion/cleaning.py` | `data/clean/papers_clean.csv`, `papers_clean.json` | Đạt 100% kiểm định GX 1.x |
| Thiết kế 6 kịch bản tiêm lỗi dữ liệu | `src/ingestion/corruption.py` | `data/results/corruption_log.json` ghi nhật ký 6 lỗi | Kiểm tra log JSON |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Hệ thống RAG phụ thuộc trực tiếp vào chất lượng dữ liệu đầu vào. Cần xây dựng một nền tảng dữ liệu sạch (Data Foundation), bảo toàn nguồn cội dữ liệu (Data Lineage) và mô phỏng được các sự cố dữ liệu thực tế (Data Corruption) nhằm kiểm chứng khả năng phát hiện của tầng Observability.

### Cách triển khai
1. **Thu thập có Fallback:** Hàm `fetch_source_records` gọi Crossref API với 3 lần retry; nếu mạng gặp sự cố sẽ tự động fallback đọc từ local raw snapshot đã lưu sẵn.
2. **Data Modeling:** Hàm `build_clean_dataframe` loại bỏ thẻ HTML, chuẩn hóa tác giả/chuyên mục, tính `age_days` dựa trên thời gian chạy thực tế và tổng hợp chuỗi văn bản hoàn chỉnh `text_for_embedding`.
3. **Mô phỏng 6 dạng lỗi thực tế:**
   - `drop_latest_records`: Bỏ 20% bản ghi mới nhất.
   - `blank_summary`: Xóa trắng đoạn tóm tắt abstract.
   - `inject_noise`: Chèn chuỗi vô nghĩa `0xDEADBEEF`.
   - `truncate_title`: Cắt tiêu đề còn `"Paper"`.
   - `stale_date`: Lùi ngày xuất bản 365 ngày để vi phạm Freshness SLA.
   - `duplicate_rows`: Nhân bản dòng vi phạm Uniqueness constraint.
4. **Idempotent Repair:** Tái nạp từ raw snapshot bất biến và chạy lại pure transformation function, khôi phục dữ liệu sạch hoàn hảo 100%.

---

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Lựa chọn cách thức sửa chữa dữ liệu khi xảy ra lỗi.
- **Phương án cân nhắc:**
  1. Viết các hàm vá lỗi trực tiếp trên bảng dữ liệu bị hỏng (In-place patching).
  2. Triển khai cơ chế Idempotent Repair bằng cách nạp lại từ Raw Snapshot gốc bất biến.
- **Lựa chọn:** Phương án 2.
- **Lý do:** In-place patching dễ để sót lỗi tiềm ẩn hoặc tạo ra trạng thái lai không thể kiểm soát. Việc tái tạo từ snapshot gốc đảm bảo tính toàn vẹn (Data Integrity) và độ tin cậy tuyệt đối trong môi trường Production.

---

## 6. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end của cả nhóm.
- [x] Báo cáo không chứa bất kỳ secret hay API key nào.

**Họ và tên:** Nguyễn Tuấn Thành  
**Ngày xác nhận:** 2026-09-26
