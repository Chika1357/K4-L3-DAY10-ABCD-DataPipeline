# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `Nhóm ABCD`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-ABCD-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | Hồ Đình Tuấn Kiệt | 2A202602785 | tuankiet@vinuni.edu.vn | Trưởng nhóm / Pipeline Lead & RAG Integrator (`src/core/`, `src/retrieval/`, `src/pipelines/`) | `report/2A202602785_HoDinhTuanKiet.md` |
| 2 | Nguyễn Tuấn Thành | 2A202602640 | tuanthanh.develop@gmail.com | Data Foundation & Corruption Specialist (`src/ingestion/crossref.py`, `cleaning.py`, `corruption.py`) | `report/2A202602640_NguyenTuanThanh.md` |
| 3 | Nguyễn Trần Kiên | 2A2202602571 | trankien@vinuni.edu.vn | Data Observability & Benchmark Evaluation Lead (`src/observability/`, `src/evaluation/`) | `report/2A2202602571_NguyenTranKien.md` |

---

## # Cá nhân

### ## HoDinhTuanKiet-2A202602785
- **Vai trò:** Trưởng nhóm & Pipeline Lead, RAG Integrator.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập cấu hình hệ thống `src/core/config.py` và đường dẫn artifacts `src/core/utils.py`.
  - Kết nối luồng thực thi trong `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`.
  - Quản lý 3 ChromaDB collections (`papers-baseline`, `papers-corrupted`, `papers-repaired`) và QA Agent.
  - Quản lý Git, phân quyền nhánh và tích hợp PR của các thành viên lên nhánh `main`.
- **Điều học được / Đóng góp chính:**
  - Hiểu sâu sắc về thiết kế Idempotent Pipeline và quản lý trạng thái luồng dữ liệu đa tầng trong hệ thống RAG thực tế.

### ## NguyenTuanThanh-2A202602640
- **Vai trò:** Phụ trách Ingestion, Làm sạch & Phục hồi dữ liệu (Data Foundation).
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref API với cơ chế Fallback offline trong `src/ingestion/crossref.py`.
  - Chuẩn hóa schema, tính toán trường `age_days` và `text_for_embedding` trong `src/ingestion/cleaning.py`.
  - Thiết kế và triển khai 6 kịch bản data corruption thực tế trong `src/ingestion/corruption.py`.
  - Thực thi cơ chế Idempotent Repair phục hồi 100% dữ liệu từ raw snapshot không gây ô nhiễm.
- **Điều học được / Đóng góp chính:**
  - Kỹ thuật truy vết nguồn gốc dữ liệu (Data Lineage) và bảo toàn raw snapshot trước khi thực hiện biến đổi.

### ## NguyenTranKien-2A2202602571
- **Vai trò:** Phụ trách Data Observability & Benchmark Evaluation Lead.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Quality Gate theo chuẩn mới **Great Expectations 1.x** (Ephemeral context) và giám sát Freshness SLA trong `src/observability/quality.py`.
  - Xây dựng bộ đề thi đánh giá chuẩn 10 câu hỏi cân bằng 4 nhóm trong `src/evaluation/testset.py`.
  - Đo lường và xuất báo cáo Markdown đối chiếu 3 trạng thái vào `data/reports/corruption_report.md` và `data/reports/phase1_report.md`.
- **Điều học được / Đóng góp chính:**
  - Cách thiết lập hệ thống cảnh báo sớm chặn đứng hiện tượng Silent Failure trước khi dữ liệu độc hại xâm nhập vào Vector Store.
