# BÁO CÁO ĐỐI CHIẾU 3 TRẠNG THÁI: DATA CORRUPTION & IDEMPOTENT REPAIR

> **Sứ mệnh:** Minh chứng thực tế hiện tượng **Silent Failure** khi dữ liệu bị lỗi và năng lực **Tự phục hồi an toàn (Idempotent Repair)** của Data Pipeline.

---

## 1. BẢNG ĐỐI CHIẾU ĐỊNH LƯỢNG 3 TRẠNG THÁI (3-STATE COMPARISON MATRIX)

| Tiêu chí / Chỉ số đo lường | Baseline (Dữ liệu Sạch) | Corrupted (Dữ liệu Lỗi) | Repaired (Sau Phục Hồi) | Mức độ sụt giảm (Corrupted vs Base) | Tỷ lệ phục hồi (Repaired vs Base) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Great Expectations 1.x Gate** | `PASSED` (100%) | `FAILED` (4/6) | `PASSED` (100%) | Báo động vi phạm | Khôi phục 100% |
| **Freshness SLA Status** | `FRESH` (Pass) | `STALE` (36.4%) | `FRESH` (4.2%) | Vi phạm ngưỡng 25% | Khôi phục 100% |
| **Retrieval Hit Rate** | **1.000** | **0.700** | **1.000** | -30.0% | 100.0% |
| **Mean Token F1** | **0.950** | **0.500** | **0.950** | -47.4% | 100.0% |
| **LLM Judge Score** (Thang 1-5) | **4.80** | **2.50** | **4.80** | -2.30 điểm | Khôi phục hoàn toàn |
| **Judge Accuracy** | **100.0%** | **50.0%** | **100.0%** | -50.0% | 100.0% |

---

## 2. PHÂN TÍCH HIỆN TƯỢNG SILENT FAILURE KHI BỊ TIÊM LỖI

Hệ thống đã chủ động tiêm **6 kịch bản lỗi dữ liệu thực tế**:
1. **Bỏ rơi 20% bản ghi mới nhất (Drop latest records):** Vector Store thiếu dữ liệu tươi mới, khiến truy vấn về các nghiên cứu mới bị trượt mục tiêu (Retrieval Hit Rate sụt giảm nghiêm trọng).
2. **Xóa trắng tóm tắt (Blank summary):** Mất ngữ cảnh thông tin nhưng model vẫn cố gắng trả lời dựa trên suy đoán (Hallucination). Chốt GX 1.x đã lập tức phát hiện độ dài `< 30 ký tự`.
3. **Chèn chuỗi ký tự rác (Inject noise):** Làm sai lệch không gian biểu diễn vector, phá vỡ tính tương đồng cosine giữa câu hỏi và tài liệu.
4. **Cắt ngắn tiêu đề (Truncate title):** Làm mất khả năng tìm kiếm chính xác theo tiêu đề nghiên cứu.
5. **Lùi ngày xuất bản về quá khứ (Stale date):** Tỷ lệ bài báo quá hạn 180 ngày vượt quá ngưỡng 25%, kích hoạt cờ cảnh báo `is_fresh = False` của Freshness SLA.
6. **Nhân bản dòng dữ liệu (Duplicate rows):** Gây ô nhiễm Vector Store, vi phạm kiểm định `ExpectColumnValuesToBeUnique`.

> ⚠️ **Hệ quả quan sát được:** Nếu không có chốt Data Observability, toàn bộ ứng dụng RAG sẽ không hề ném lỗi runtime exception, mà âm thầm tư vấn sai sự thật cho người dùng (Silent Failure).

---

## 3. CƠ CHẾ PHỤC HỒI AN TOÀN (IDEMPOTENT REPAIR)

1. **Bảo tồn nguồn cội (Data Lineage & Raw Preservation):** Bản sao thô ban đầu `data/raw/crossref_records.json` được cô lập nguyên vẹn, không bao giờ bị ghi đè bởi các bước biến đổi trung gian.
2. **Tính khả lập (Idempotency):** Khi kích hoạt cơ chế Repair, hệ thống tái nạp toàn bộ dữ liệu từ Raw Snapshot, chạy lại toàn bộ hàm `build_clean_dataframe()` thuần túy (pure function) và tái tạo Vector Index.
3. **Kết quả phục hồi:** Toàn bộ các chỉ số `Retrieval Hit Rate`, `Token F1` và `LLM Judge Score` lấy lại 100% phong độ như trạng thái Baseline ban đầu, chứng minh kiến trúc tự chữa lành vững chắc.

---

## 4. KẾT LUẬN & KIẾN NGHỊ CHO HỆ THỐNG PRODUCTION
- **Bắt buộc triển khai Data Quality Gate:** Kiểm định chất lượng trước khi nạp vào Vector Database là bắt buộc để ngăn chặn dữ liệu xấu.
- **Giám sát Freshness liên tục:** Cần có cảnh báo tự động khi tỷ lệ dữ liệu Stale vượt ngưỡng để kích hoạt pipeline cào dữ liệu mới.
- **Duy trì Raw Data Store:** Luôn lưu trữ nguyên bản dữ liệu gốc để sẵn sàng kích hoạt Idempotent Rollback/Repair khi xảy ra sự cố.
