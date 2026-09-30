# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Đức Tâm
- **MSSV:** 2A202602921
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602921`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/pytest.txt` |
| Log validator | `evidence/log-validator.txt` |
| Dashboard validator | `evidence/dashboard-validator.txt` |
| Structured log + incident log | `evidence/01-incident-log.png` |
| Trace list | `evidence/02-trace-list.png` |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png` |
| Prompt versions + promote/rollback | `evidence/04-prompt-versioning.png` |
| Dashboard + incident metric | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

Baseline (CP0) chạy lúc 2026-09-30 09:44 (UTC+7) với 10 request của `scripts/load_test.py`, API chạy bằng `--env-file .env` (`/health`: `ok: true`, `tracing_enabled: true`). Output đầy đủ: [`evidence/00-baseline.txt`](evidence/00-baseline.txt).

| Nội dung                | Baseline                                   | Kết quả cuối | Nhận xét |
| ----------------------- | ------------------------------------------ | ------------ | -------- |
| `validate_logs.py`      | 30/100                                     |              | Baseline: 20/20 record thiếu `correlation_id` và enrichment (`user_id_hash`, `session_id`, `feature`, `model`); 0 correlation ID duy nhất. |
| `validate_dashboard.py` | HỢP LỆ 6/6 panel                           |              | Contract `config/dashboard.yaml` của starter đã đủ 6 panel. |
| `pytest`                | 22 passed                                  |              | Lần chạy mặc định: 18 passed, 4 errors do thư mục temp của pytest bị khoá quyền (WinError 5), không phải lỗi code; đổi temp root thì 22/22 pass. |
| Số traces hợp lệ        | 10 traces, chỉ có root `lab-agent-run`     |              | Chưa có child retrieval/generation; metadata `correlation_id=MISSING`. |
| Số PII leak             | 0                                          |              | `summarize_text` đã che preview, nhưng processor `scrub_event` chưa được đăng ký trong pipeline log. |
| Latency P95 / TTFT P95  | 779 ms / 51 ms                             |              | P50 = 388 ms; P95 bị kéo lên bởi request đầu tiên (1092 ms, cold start khi lấy prompt), 9 request còn lại 377–396 ms. |
| Retrieval success rate  | 100% (10/10)                               |              | Chưa bật incident. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) chạy đầu mỗi request: gọi `clear_contextvars()` để xoá context cũ, sau đó nhận header `x-request-id` nếu đúng format `req-<8-hex>` (so khớp regex, không phân biệt hoa thường). Header rỗng hoặc sai format (ví dụ `a@b.vn`, `req-XYZ`) bị bỏ và sinh ID mới `req-` + 8 ký tự đầu của `uuid4().hex`, vì header là input không tin cậy và có thể mang PII hoặc làm giả dòng log. ID được `bind_contextvars(correlation_id=...)` và gán vào `request.state.correlation_id` để agent đưa vào metadata của trace Langfuse. Response trả lại `x-request-id` và `x-response-time-ms`; body `/chat` cũng có `correlation_id`.
- **Các metadata được ghi vào structured log:** [`app/main.py`](../app/main.py) bind một lần trước dòng `request_received`: `user_id_hash` (SHA-256 cắt 12 ký tự, không ghi `user_id` gốc), `session_id`, `feature`, `model`, `env`. Nhờ context này, mọi log của request (`request_received`, `response_sent`, `request_failed`) đều có cùng bộ field cùng với `ts`, `level`, `service`, `event`, `correlation_id`. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** [`app/logging_config.py`](../app/logging_config.py) đăng ký `scrub_event` sau `format_exc_info` và trước `JsonlFileProcessor`/`JSONRenderer`, nên traceback đã được render thành chuỗi cũng bị scrub và không có đường nào ghi PII thô xuống file hay stdout. `scrub_event` duyệt đệ quy mọi chuỗi, kể cả `payload` lồng nhau và list, trừ các field do hệ thống sinh (`ts`, `level`, `correlation_id`, `user_id_hash`); `user_id_hash` là hex nên có thể trùng pattern CCCD 12 số. [`app/pii.py`](../app/pii.py) che email, điện thoại VN, CCCD, thẻ và thêm hộ chiếu VN (`[A-Z]` + 7 số). Thứ tự pattern giữ CCCD trước thẻ, vì pattern thẻ cho phép bỏ dấu cách nên nếu chạy trước sẽ ghép `001099012345 4111` thành một "số thẻ" và để lộ phần còn lại.
- **Cách kiểm chứng kết quả:**
  - Test mới trong [`tests/test_pii.py`](../tests/test_pii.py) (CCCD, 3 format thẻ, hộ chiếu, số thường không bị che, câu ghép 4 loại PII) và [`tests/test_correlation_logging.py`](../tests/test_correlation_logging.py) (header được giữ, ID sai format bị thay, mỗi request có ID riêng, log thật không còn PII, scrub payload lồng nhau và traceback). `pytest`: 31 passed.
  - Chuyển log baseline ra ngoài repo, restart API, chạy `load_test.py` thì `validate_logs.py` đạt **100/100**: 47 record, 0 thiếu field, 0 thiếu enrichment, 23 correlation ID duy nhất, 0 PII leak ([`evidence/02-log-validator.png`](evidence/02-log-validator.png)).
  - Request mẫu `req-04c0de01` trả header `x-request-id: req-04c0de01`, `x-response-time-ms: 1075.4`; hai dòng log `request_received` và `response_sent` có đủ field ([`evidence/04-structured-log.png`](evidence/04-structured-log.png)). Trace Langfuse `a8439b278aa9dc177321d4c43f6131fc` có metadata `correlation_id=req-04c0de01`.
  - Request `req-05c0de01` gửi `a@b.vn 0901234567 001099012345 4111 1111 1111 1111` (PII giả); log ghi `[REDACTED_EMAIL] [REDACTED_PHONE_VN] [REDACTED_CCCD] [REDACTED_CREDIT_CARD]` ([`evidence/05-pii-redaction.png`](evidence/05-pii-redaction.png)). Trace tương ứng: `1cd1a427df7d262d510afe4b9b795aa3`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
- **SLO và lý do chọn:**
- **Cách tính error budget:**
- **Ba alert và runbook tương ứng:**

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
