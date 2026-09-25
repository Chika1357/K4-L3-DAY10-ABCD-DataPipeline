# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| :--- | :--- |
| Khóa/Lớp | K4-L3-DAY10 |
| Tên nhóm | Nhóm ABCD |
| Repository | `https://github.com/Chika1357/K4-L3-DAY10-ABCD-DataPipeline` |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | :--- | :--- | :--- | :--- |
| 1 | Hồ Đình Tuấn Kiệt | 2A202602785 | Pipeline Lead & RAG Integrator | `src/core/`, `src/retrieval/`, `src/pipelines/`, `script/run_phase1.py`, `script/run_corruption_flow.py` |
| 2 | Nguyễn Tuấn Thành | 2A202602640 | Data Foundation & Corruption Specialist | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, `data/raw/`, `data/clean/` |
| 3 | Nguyễn Trần Kiên | 2A2202602571 | Observability & Evaluation Lead | `src/observability/quality.py`, `src/observability/reporting.py`, `src/evaluation/testset.py`, `src/evaluation/metrics.py`, `data/quality/`, `data/reports/` |

---

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành trọn vẹn 100% mục tiêu của Day 10: Xây dựng hoàn chỉnh đường ống dữ liệu (Data Pipeline) từ thu thập Crossref API đến lưu trữ Vector Database (ChromaDB) phục vụ RAG Agent, tích hợp hệ thống giám sát chất lượng dữ liệu (Data Observability) với chuẩn **Great Expectations 1.x (Ephemeral)** và giám sát độ tươi (Freshness SLA 180 ngày).

Pipeline Baseline tạo ra các artifact: `data/raw/crossref_records.json`, `data/clean/papers_clean.csv`, `papers_clean.json`, index ChromaDB `papers-baseline`, bộ đề thi 10 câu hỏi `data/eval/test_set.json`, cùng các báo cáo chất lượng và hiệu năng.

Khi tiêm 6 kịch bản data corruption, kịch bản **Drop latest records (20%)** và **Blank summary** gây ảnh hưởng nặng nề nhất: Retrieval Hit Rate giảm từ **1.000 xuống 0.700 (-30%)**, Mean Token F1 giảm từ **0.950 xuống 0.500 (-47.4%)**, LLM Judge Score sụt giảm từ **4.80 xuống 2.50**, đồng thời làm xuất hiện hiện tượng **Silent Failure / Hallucination** (RAG trả lời trúng bài báo mở rộng nhưng sai bài gốc).

Hệ thống Idempotent Repair tái tạo dữ liệu từ snapshot nguyên bản `crossref_records.json`, đưa toàn bộ chỉ số Retrieval Hit Rate, Token F1 và Judge Score hồi phục hoàn toàn **100%** về mức Baseline ban đầu.

---

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API (hoặc Offline Snapshot fallback)
    │
    ▼
Raw Records Extraction (src/ingestion/crossref.py -> data/raw/)
    │
    ▼
Data Cleaning & Feature Engineering (src/ingestion/cleaning.py -> data/clean/)
    │
    ├────────► Quality Gate Great Expectations 1.x & Freshness SLA (src/observability/quality.py)
    │
    ├────────► 10-Question Testset Generator (src/evaluation/testset.py -> data/eval/)
    │
    ├────────► ChromaDB Vector Indexing (src/retrieval/index.py -> data/chroma/)
    │             │
    │             ▼
    │          Extractive Grounding QA & Benchmark Evaluation (src/evaluation/metrics.py)
    │
    ▼
Synthetic Corruption Engine (src/ingestion/corruption.py -> 6 lỗi thực tế)
    │
    ▼
Corrupted Flow: GX Gate Fail -> Retrieval Hit Drops -> Silent Failure Analysis
    │
    ▼
Idempotent Repair Flow (Pure functional replay từ data/raw/ snapshot)
    │
    ▼
3-State Comparison Matrix (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| :--- | :--- | :--- | :--- | :--- |
| Ingestion | Crossref REST API / Snapshot | Fetch HTTP với timeout/retry, offline fallback, trích xuất metadata | `data/raw/crossref_records.json` | Nguyễn Tuấn Thành |
| Cleaning | Raw records list | Khử HTML tag, chuẩn hóa chuỗi, tính `age_days`, tạo `text_for_embedding` | `data/clean/papers_clean.csv`, `.json` | Nguyễn Tuấn Thành |
| Embedding/Index | Clean DataFrame | Dense embeddings `all-MiniLM-L6-v2` (384d), nạp HNSW Cosine ChromaDB | `data/chroma/`, `data/embeddings/` | Hồ Đình Tuấn Kiệt |
| Evaluation | Test set + Index | Dense vector search, metadata extractive grounding, Token F1, LLM Judge | `data/results/baseline_metrics.json` | Nguyễn Trần Kiên |
| Observability | Clean / Corrupted DataFrame | Great Expectations 1.x Ephemeral (4 expectations), Freshness SLA 180d | `data/quality/*.json` | Nguyễn Trần Kiên |
| Corruption/Repair | Clean DataFrame / Raw Snapshot | Tiêm 6 lỗi (Drop, Blank, Noise, Truncate, Stale, Dup); Idempotent replay | `data/results/corruption_log.json`, `data/clean/*repaired*` | Nguyễn Tuấn Thành |
| Orchestration | Cấu hình Settings | Điều phối Phase 1, Corruption flow, xuất Markdown reports | `script/run_phase1.py`, `script/run_corruption_flow.py` | Hồ Đình Tuấn Kiệt |

---

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| :--- | :--- |
| `LLM_PROVIDER` | `gemini` (hoặc heuristic fallback offline) |
| `LLM_MODEL` | `gemini-2.5-flash` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | `24` |
| Retrieval `top_k` | `4` |
| Freshness threshold | `180` ngày (Tối đa 25% stale ratio) |

### Lệnh chạy tái hiện

Với môi trường virtual environment:

```powershell
# 1. Chạy Baseline Pipeline (Pha 1)
.\.venv\Scripts\python.exe script/run_phase1.py

# 2. Chạy Corruption Flow & Idempotent Repair (Pha 2)
.\.venv\Scripts\python.exe script/run_corruption_flow.py

# 3. Chạy Suite kiểm thử độc lập cho Observability
.\.venv\Scripts\python.exe script/test_member3.py
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy | Bằng chứng |
| :--- | :--- | :--- | :--- |
| `run_phase1.py` | Thành công 100% | 2026-09-26 | `data/reports/phase1_report.md`, `baseline_metrics.json` |
| `run_corruption_flow.py` | Thành công 100% | 2026-09-26 | `data/reports/corruption_report.md`, `corruption_log.json` |
| `test_member3.py` | Thành công 100% | 2026-09-26 | Terminal output: 6 checks passed, exit code 0 |

---

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| :--- | :--- |
| Source | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter | `query=agentic retrieval augmented generation large language model`, `filter=from-pub-date:2026-03-30,has-abstract:true` |
| Thời điểm lấy | 2026-09-25T14:18:00Z (Lưu snapshot tại `data/raw/crossref_records.json`) |
| Số record | 24 bản ghi nghiên cứu khoa học |
| Retry/Backoff | 3 lần thử với backoff 1s, tự động fallback về local snapshot nếu mất kết nối |

### Data Contract: Clean Schema (16 trường)

| Tên trường | Kiểu | Bắt buộc? | Ý nghĩa & Xử lý |
| :--- | :--- | :---: | :--- |
| `paper_id` | String | Có | DOI định danh duy nhất bài báo. Khử trùng lặp theo trường này. |
| `title` | String | Có | Tiêu đề bài báo đã xóa thẻ HTML và chuẩn hóa khoảng trắng thừa. |
| `summary` | String | Có | Đoạn tóm tắt abstract đã làm sạch. Tối thiểu 30 ký tự. |
| `authors` | List[String] | Có | Danh sách tên tác giả. Điền `Unknown Author` nếu thiếu. |
| `categories` | List[String] | Có | Danh sách chủ đề nghiên cứu. Điền `General` nếu thiếu. |
| `primary_category` | String | Có | Chủ đề chính (phần tử đầu tiên của categories). |
| `published` | String | Có | Ngày xuất bản chuẩn `YYYY-MM-DD`. |
| `updated` | String | Có | Ngày cập nhật gần nhất. |
| `abs_url` | String | Có | Đường link bài báo tại Crossref/DOI. |
| `pdf_url` | String | Có | Đường link tới file PDF bài báo (nếu có). |
| `comment` | String | Không | Ghi chú nguồn gốc dữ liệu. |
| `authors_joined` | String | Có | Chuỗi tác giả nối bằng dấu phẩy phục vụ hiển thị. |
| `categories_joined` | String | Có | Chuỗi chuyên mục nối bằng dấu phẩy. |
| `summary_chars` | Integer | Có | Độ dài ký tự của tóm tắt phục vụ kiểm định GX. |
| `age_days` | Integer | Có | Số ngày tuổi so với ngày chạy phục vụ Freshness SLA. |
| `text_for_embedding` | String | Có | Văn bản ghép đa trường chuẩn hóa để nạp vào mô hình Embedding. |

---

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| :--- | :--- |
| Số câu hỏi | `10` câu hỏi |
| Các `question_type` | `summary` (3 câu), `authors` (3 câu), `date` (2 câu), `categories` (2 câu) |
| Ground-truth doc ID | DOI bài báo tương ứng được trích xuất tự động tại thời điểm sinh test set |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) |
| Vector Store | ChromaDB `PersistentClient` với khoảng cách cosine (`hnsw:space: cosine`) |
| Retrieval `top_k` | `4` tài liệu gần nhất |
| Test set dùng chung | `data/eval/test_set.json` (Cố định tuyệt đối qua cả 3 trạng thái) |

> **Giải thích tính khách quan của Test Set:** Bộ đề thi được cố định nguyên vẹn (frozen) cho cả Baseline, Corrupted và Repaired. Việc giữ nguyên câu hỏi và Ground Truth DOI cho phép đo lường chính xác tác động tiêu cực của Data Corruption và chứng minh năng lực khôi phục định lượng của Idempotent Repair.

---

## 7. Kết quả Baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái |
| :--- | :--- | :---: |
| Raw records | `data/raw/crossref_records.json` | Đầy đủ |
| Cleaned dataset | `data/clean/papers_clean.csv`, `papers_clean.json` | Đầy đủ |
| Vector Index | `data/chroma/`, `data/embeddings/papers_embeddings.json` | Đầy đủ |
| Evaluation set | `data/eval/test_set.json` | Đầy đủ |
| Baseline metrics | `data/results/baseline_metrics.json` | Đầy đủ |
| Quality/Freshness | `data/quality/baseline_test_quality_report.json`, `test_freshness.json` | Đầy đủ |
| Baseline report | `data/reports/phase1_report.md` | Đầy đủ |

### Baseline metrics

| Metric | Giá trị Baseline | Ngưỡng yêu cầu | Đánh giá |
| :--- | :---: | :---: | :---: |
| `retrieval_hit_rate` | **1.000** | ≥ 0.800 | ✅ Đạt tuyệt đối |
| `mean_token_f1` | **0.950** | ≥ 0.700 | ✅ Đạt xuất sắc |
| `judge_accuracy` | **1.000** | ≥ 0.700 | ✅ Đạt 100% |
| `mean_judge_score` | **4.80 / 5.0** | ≥ 3.50 | ✅ Đạt chuẩn cao |

---

## 8. Data quality và freshness

### Great Expectations 1.x Quality Checks

| Check (Expectation) | Quality Dimension | Ngưỡng kỳ vọng | Kết quả Baseline | Trạng thái |
| :--- | :--- | :--- | :---: | :---: |
| `ExpectTableRowCountToBeBetween` | Completeness | [5, 5000] | 24 dòng | ✅ PASS |
| `ExpectColumnValuesToNotBeNull` (`paper_id`) | Validity | Null count = 0 | 0 null | ✅ PASS |
| `ExpectColumnValuesToNotBeNull` (`title`) | Validity | Null count = 0 | 0 null | ✅ PASS |
| `ExpectColumnValuesToNotBeNull` (`text_for_embedding`)| Validity | Null count = 0 | 0 null | ✅ PASS |
| `ExpectColumnValuesToBeUnique` (`paper_id`) | Uniqueness | Trùng lặp = 0 | 0 duplicate | ✅ PASS |
| `ExpectColumnValueLengthsToBeBetween` (`summary`) | Completeness | Min length ≥ 30 | Min = 142 | ✅ PASS |

### Freshness SLA Monitoring

| Thuộc tính | Giá trị đo lường |
| :--- | :--- |
| Nguồn đo | `data/clean/papers_clean.csv` |
| Bài báo mới nhất | `2026-07-22` |
| Bài báo cũ nhất | `2026-03-28` |
| Ngưỡng Freshness SLA | `180` ngày |
| Số bài quá hạn (Stale) | `1 / 24` (Tỷ lệ: **4.17%**) |
| Trạng thái Freshness | `FRESH` (Đạt chuẩn vì 4.17% ≤ ngưỡng tối đa 25%) |

---

## 9. Corruption scenarios và repair

| Corruption | Cơ chế tạo lỗi | Số bản ghi | Quality Signal kỳ vọng | Tác động thực tế lên RAG | Cách Repair |
| :--- | :--- | :---: | :--- | :--- | :--- |
| `drop_latest_records` | Cắt bỏ 20% bản ghi mới nhất | 4 bài báo | Row count giảm | Retrieval miss đối với nghiên cứu mới | Nạp lại từ Raw snapshot |
| `blank_summary` | Xóa rỗng trường summary | 2 bài báo | GX length check `< 30` FAIL | Mất ngữ cảnh, suy luận sai | Re-clean từ snapshot |
| `inject_noise` | Chèn chuỗi rác `0xDEADBEEF` | 2 bài báo | Biến dạng embedding | Giảm độ tương đồng Cosine | Tái tạo embedding từ clean text |
| `truncate_title` | Cắt tiêu đề thành `"Paper"` | 2 bài báo | Mất thông tin tiêu đề | Truy vấn exact lookup thất bại | Re-clean từ snapshot |
| `stale_date` | Lùi ngày xuất bản về 365 ngày | 8 bài báo | Freshness SLA FAIL (> 25%) | Hệ thống cảnh báo dữ liệu cũ | Tính lại `age_days` chuẩn |
| `duplicate_rows` | Nhân bản các dòng hiện có | 2 bài báo | GX Uniqueness FAIL | Ô nhiễm Vector Store, trùng lặp | Chạy `drop_duplicates` |

---

## 10. So sánh Baseline, Corrupted và Repaired

| Tiêu chí / Chỉ số đo lường | Baseline (Sạch) | Corrupted (Lỗi) | Repaired (Phục Hồi) | Mức độ sụt giảm | Tỷ lệ phục hồi |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Great Expectations Gate** | `PASSED` (6/6) | `FAILED` (4/6) | `PASSED` (6/6) | Bắt trúng lỗi | 100% |
| **Freshness SLA Status** | `FRESH` (4.2%) | `STALE` (36.4%) | `FRESH` (4.2%) | Vi phạm SLA | 100% |
| **Retrieval Hit Rate** | **1.000** | **0.700** | **1.000** | **-30.0%** | **100.0%** |
| **Mean Token F1** | **0.950** | **0.500** | **0.950** | **-47.4%** | **100.0%** |
| **LLM Judge Score** | **4.80** | **2.50** | **4.80** | **-2.30 điểm** | **100.0%** |
| **Judge Accuracy** | **100.0%** | **50.0%** | **100.0%** | **-50.0%** | **100.0%** |

### Hai phát hiện quan trọng có quan hệ nhân quả:
1. **Drop latest records & Blank summary $\rightarrow$ GX Gate Báo Động $\rightarrow$ Hit Rate sụt giảm nghiêm trọng:** Khi 20% bài báo mới bị drop, truy vấn về các bài này trượt khỏi Ground Truth DOI, dẫn đến Retrieval Hit = False. Đồng thời, tài liệu bị xóa summary vi phạm chốt GX (độ dài < 30), kéo Token F1 giảm 47.4%.
2. **Idempotent Repair $\rightarrow$ Khôi phục 100% Data Lineage $\rightarrow$ Metrics trở lại nguyên bản:** Cơ chế repair đọc lại immutable snapshot gốc, chạy qua pure transformation pipeline, tái tạo index vector sạch mà không hề để lại tàn dư lỗi, đưa toàn bộ chỉ số về trạng thái hoàn hảo 100%.

---

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Trong quá trình kiểm thử câu hỏi về thời gian xuất bản bài báo *Advanced Perspectives on Hybrid Search...*, câu trả lời trên Baseline và Corrupted ra kết quả giống hệt nhau (`2026-06-11`).
- **Nguyên nhân gốc (Root Cause):** Bài báo này được nhóm tiêm lỗi `inject_noise` (chèn rác vào tóm tắt) chứ không phải lỗi `stale_date`. Do đó trường `published` của bài báo không hề bị lùi ngày.
- **Cách xử lý:** Đã điều chỉnh câu hỏi kiểm thử sang bài báo mang DOI `10.1145/3637528.3671801` (*Agentic RAG...*) — là bài báo thực sự bị tiêm `stale_date` (lùi từ `2026-05-20` về `2025-05-20`).
- **Cách xác minh:** Truy vấn đối chiếu hiển thị rõ ràng sự khác biệt 365 ngày giữa Baseline và Corrupted, minh chứng sống động tác động của lỗi.

---

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| :--- | :--- | :--- |
| Corpus kích thước nhỏ (24 bài) | Độ bao phủ chuyên đề hẹp | Mở rộng cào 500 - 1000 bài báo Crossref có phân trang (`offset`, `cursor`). |
| Chốt kiểm tra Freshness chạy batch | Chỉ phát hiện stale data sau khi pipeline hoàn tất | Tích hợp streaming trigger tự động kích hoạt ingestion khi tỷ lệ stale vượt 20%. |

---

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác (`Nhóm ABCD`, MSSV của cả 3 thành viên).
- [x] Phân công khớp với module, artifact và kết quả thực tế trong `TEAM.md` và `TEAM_TASKS.md`.
- [x] Lệnh tái hiện đã được kiểm chứng thành công trên môi trường thực tế.
- [x] Baseline, corrupted và repaired dùng chung bộ đề thi cố định `test_set.json`.
- [x] Bảng metrics khớp chính xác với các file trong `data/results/`.
- [x] Quality/Freshness conclusions khớp với các báo cáo trong `data/quality/`.
- [x] Cả 3 thành viên đều có commit đóng góp độc lập trên đồ thị GitHub nhánh `main`.
- [x] Tuyệt đối không có file `.env`, API key hay secret nào bị theo dõi trên Git.
