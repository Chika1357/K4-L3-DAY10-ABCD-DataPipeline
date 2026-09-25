# Báo Cáo Cá Nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| Họ và tên | Hồ Đình Tuấn Kiệt |
| MSSV | 2A202602785 |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Nhóm ABCD |
| Vai trò chính | Trưởng nhóm / Pipeline Lead & RAG Integrator |
| Repository | `https://github.com/Chika1357/K4-L3-DAY10-ABCD-DataPipeline` |
| Ngày hoàn thành | 2026-09-26 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Pipeline Orchestration | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` | `Settings`, raw records, clean dataframe | Toàn bộ luồng thực thi Phase 1 & 2 | Hoàn thành 100% |
| CLI Scripts | `script/run_phase1.py`, `script/run_corruption_flow.py` | CLI execution | Kích hoạt pipeline và xuất log tóm tắt | Hoàn thành 100% |
| System Configuration | `src/core/config.py`, `src/core/utils.py` | Environment vars | `Settings`, `Paths`, text & file utilities | Hoàn thành 100% |
| Vector Store & Retrieval | `src/retrieval/index.py`, `src/retrieval/qa.py`, `agent.py` | Clean Dataframe, câu hỏi truy vấn | 3 ChromaDB collections, câu trả lời RAG | Hoàn thành 100% |

### Việc hỗ trợ ngoài phạm vi chính
- Điều phối Git, quy hoạch nhánh cho 3 thành viên (`feature/member1-pipeline-lead`, `tuanthanh_dev`, `feature/member3-observability-eval`).
- Review và merge PR #1, PR #2, PR #3 đảm bảo không có merge conflict.
- Kiểm tra bảo mật loại bỏ `.env` khỏi git tracking.

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Xây dựng Baseline Pipeline | `src/pipelines/phase1.py` | Thực thi end-to-end từ raw data đến ChromaDB | `python script/run_phase1.py` |
| Xây dựng Corruption & Repair Flow | `src/pipelines/corruption_flow.py` | Chạy 3 trạng thái Baseline -> Corrupted -> Repaired | `python script/run_corruption_flow.py` |
| Thiết lập ChromaDB HNSW Index | `src/retrieval/index.py` | Quản lý 3 collection: `papers-baseline`, `papers-corrupted`, `papers-repaired` | Kiểm tra thư mục `data/chroma/` |

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Hệ thống cần một nhạc trưởng điều phối (Orchestrator) kết nối các mắt xích độc lập: thu thập dữ liệu (Member 2), kiểm định chất lượng & đánh giá (Member 3), và lưu trữ vector ngữ nghĩa (Member 1). Nếu không có orchestration chuẩn, các trạng thái dữ liệu sẽ bị ghi đè, làm mất tính khách quan khi so sánh hiệu năng.

### Cách triển khai
- Sử dụng mô hình Functional Pipeline: dữ liệu di chuyển qua các bước biến đổi thuần túy không gây hiệu ứng phụ.
- Tách biệt 3 không gian vector trong ChromaDB bằng `PersistentClient`, mỗi trạng thái tương ứng với một collection riêng biệt có cấu hình Cosine distance:
  - `papers-baseline`: Nạp từ dữ liệu sạch sau cleaning.
  - `papers-corrupted`: Nạp từ dữ liệu đã tiêm 6 loại lỗi.
  - `papers-repaired`: Nạp từ dữ liệu được làm sạch lại từ raw snapshot ban đầu.

---

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Lựa chọn phương pháp lưu trữ và cô lập vector index cho 3 trạng thái dữ liệu.
- **Phương án cân nhắc:**
  1. Dùng chung 1 collection và update/overwrite documents.
  2. Tạo 3 collections độc lập trong cùng một Persistent ChromaDB directory.
- **Lựa chọn:** Phương án 2.
- **Lý do:** Giúp việc đối chiếu các truy vấn giữa dữ liệu sạch và dữ liệu lỗi diễn ra song song và tức thì mà không cần rebuild lại cơ sở dữ liệu mỗi lần test.

---

## 6. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end của cả nhóm.
- [x] Báo cáo không chứa bất kỳ secret hay API key nào.

**Họ và tên:** Hồ Đình Tuấn Kiệt  
**Ngày xác nhận:** 2026-09-26
