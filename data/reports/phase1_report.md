# BÁO CÁO PHA 1: BASELINE DATA PIPELINE & OBSERVABILITY

> **Thời điểm thực thi:** `2026-09-25T08:55:53.734029+00:00`  
> **Nguồn dữ liệu:** `Crossref REST API`  
> **Mô hình Embedding:** `sentence-transformers/all-MiniLM-L6-v2`  
> **ChromaDB Collection:** `papers-baseline`  

---

## 1. TỔNG QUAN DỮ LIỆU ĐẦU VÀO (INGESTION & CLEANING)

| Thông số | Giá trị |
| :--- | :--- |
| Tổng bản ghi thô (Raw Records) | `24` |
| Bản ghi sạch sau tiền xử lý (Clean Rows) | `24` |
| Số câu hỏi kiểm thử (Test Questions) | `10` |
| LLM Provider đánh giá | `openai` |

---

## 2. CHỐT KIỂM DỊCH CHẤT LƯỢNG (GREAT EXPECTATIONS 1.X)

- **Trạng thái Quality Gate:** `PASSED` (✅ Đạt chuẩn)
- **Tổng số Expectation kiểm tra:** `6`
- **Số Expectation đạt:** `6`
- **Số Expectation thất bại:** `0`

### Danh sách 4 Expectation thiết yếu:
1. `ExpectTableRowCountToBeBetween`: Số lượng bản ghi nằm trong ngưỡng 5 – 5000.
2. `ExpectColumnValuesToNotBeNull`: Các cột `paper_id`, `title`, `text_for_embedding` không rỗng.
3. `ExpectColumnValuesToBeUnique`: Khóa `paper_id` là duy nhất.
4. `ExpectColumnValueLengthsToBeBetween`: Trường `summary` có độ dài tối thiểu 30 ký tự.

---

## 3. GIÁM SÁT ĐỘ TƯƠI MỚI DỮ LIỆU (FRESHNESS SLA)

- **Trạng thái Freshness:** `FRESH`
- **Ngưỡng SLA cho phép:** `180` ngày (Tối đa 25% bài báo quá hạn)
- **Số bài báo quá hạn (Stale rows):** `1 / 24` (4.2%)
- **Bài báo mới nhất:** `2026-07-22`
- **Bài báo cũ nhất:** `2026-03-28`

---

## 4. KẾT QUẢ ĐÁNH GIÁ HIỆU NĂNG RAG (BASELINE BENCHMARK)

| Chỉ số đo lường (Metric) | Kết quả Baseline | Mục tiêu tối thiểu | Đánh giá |
| :--- | :---: | :---: | :---: |
| **Retrieval Hit Rate** | **1.000** | ≥ 0.800 | ✅ Đạt |
| **Mean Token F1** | **1.000** | ≥ 0.700 | ✅ Đạt |
| **Judge Accuracy** | **1.000** | ≥ 0.700 | ✅ Đạt |
| **Mean Judge Score** (Thang 1-5) | **5.00** | ≥ 3.50 | ✅ Đạt |

---

## 5. KẾT LUẬN PHA 1
Pipeline dữ liệu sạch hoạt động ổn định, toàn bộ dữ liệu vượt qua chốt kiểm dịch Great Expectations 1.x, đạt tiêu chuẩn độ tươi Freshness SLA và tạo lập thành công nền tảng chỉ mục ngữ nghĩa cho hệ thống RAG.
