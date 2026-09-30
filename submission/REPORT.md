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

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** key trong `.env` (không commit) được tạo trong project `day13-k4-l3b-2A202602921`, và `GET /api/public/projects` bằng key này trả đúng tên project đó. Mọi trace do tôi tự chạy `scripts/load_test.py` hoặc gửi request có `x-request-id` tự đặt; `correlation_id` trong metadata trace khớp với dòng log trong `data/logs.jsonl` của máy tôi. Pytest chạy trong terminal không nạp key nên không tạo trace lạ.
- **Cấu trúc root/retrieval/generation observations:** trace `day13-agent-request` có root `lab-agent-run` (loại `agent`, [`app/agent.py`](../app/agent.py)) và hai child: `retrieval` (loại `retriever`, `@observe` trên `retrieve` trong [`app/mock_rag.py`](../app/mock_rag.py)) và `generation` (loại `generation`, `@observe` trên `FakeLLM.generate` trong [`app/mock_llm.py`](../app/mock_llm.py)). Generation ghi `model`, `usage_details` (input/output tokens), `cost_details` (dùng chung bảng giá với log qua `usage_cost_usd`) và `completion_start_time`, nên Langfuse hiện TTFT khoảng 0.05 s. Prompt version được link qua `propagate_attributes(prompt=managed_prompt)`: chỉ gửi object prompt lấy từ Langfuse, không gửi prompt đã điền câu hỏi. Mọi observation đặt `capture_input=False, capture_output=False` nên Input/Output trống, không có PII.
- **Cách nối trace với log:** middleware sinh hoặc nhận `correlation_id`, đưa vào `request.state`, rồi `LabAgent.run` đặt vào `propagate_attributes(metadata={"correlation_id": ...})`, nên metadata của root và cả hai child đều có ID này. Từ log lấy `correlation_id` rồi lọc metadata trên Langfuse là ra đúng trace. Ví dụ `req-c2c2c2c2` ứng với trace `c801199bd58039908e2ff5821431ee8c`.
- **Prompt name:** `day13-chat` (loại Text, ba biến `{{feature}}`, `{{docs}}`, `{{message}}`), tạo bằng Langfuse Python SDK `create_prompt` trong project cá nhân.
- **Version/label baseline:** v1 = đúng template local (`Feature=…\nDocs=…\nQuestion=…`), labels `baseline` và `production`.
- **Version/label candidate:** v2 = v1 thêm dòng `Trả lời ngắn gọn, tối đa 3 câu.`, label `candidate` (Langfuse tự gắn thêm `latest`).
- **Trace ID của mỗi version:** cùng input `How do I debug tail latency?` (feature `qa`), mỗi label chạy trên một API vừa khởi động (không dùng cache prompt cũ):

  | Label | Request | Trace ID | `prompt_version` | Prompt link trên generation | `tokens_in` |
  |---|---|---|---|---|---|
  | `baseline` | `req-0ba5e001` | `eac813f08167f7f24ad6ec1410a17872` | 1 | `day13-chat:1` | 27 |
  | `candidate` | `req-0ca4d001` | `a8536ccf89927b80e5620b9db7d74f80` | 2 | `day13-chat:2` | 35 |

  Fake LLM trả cùng một câu trả lời nên hai version chỉ khác `prompt_version` và `tokens_in` (+8 token do dòng yêu cầu ngắn gọn).
- **Cách promote và rollback `production`:** label là con trỏ tới version, app chỉ hỏi Langfuse theo `LANGFUSE_PROMPT_LABEL=production` nên đổi version không cần sửa code. Tôi dời label bằng SDK `update_prompt(name="day13-chat", version=N, new_labels=[...])`, tương đương sửa label trên UI; mỗi label chỉ nằm ở một version nên gắn `production` cho v2 thì v1 tự mất label. Sau mỗi lần dời, tôi kiểm chứng bằng một API vừa khởi động (app cache prompt 60 giây) và gửi cùng input:

  | Bước | Trạng thái label sau bước | Request | Trace ID | `prompt_version` |
  |---|---|---|---|---|
  | Ban đầu | v1: `baseline`, `production` · v2: `candidate`, `latest` | | | |
  | Promote (10:32, UTC+7) | v1: `baseline` · v2: `candidate`, `latest`, `production` | `req-a0000002` | `9cd32d2116610534f1c388e196bc0f21` | 2 (`tokens_in` 35) |
  | Rollback (10:39, UTC+7) | v1: `baseline`, `production` · v2: `candidate`, `latest` | `req-b0000001` | `705ce7b66d782c1a224b0b466082129e` | 1 (`tokens_in` 27) |

  Ảnh: [`evidence/09-prompt-versions.png`](evidence/09-prompt-versions.png), sau promote [`evidence/10a-prompt-promote.png`](evidence/10a-prompt-promote.png), sau rollback [`evidence/10b-prompt-rollback.png`](evidence/10b-prompt-rollback.png). Trong vận hành thật, rollback chỉ cần dời label trong vài giây, không cần deploy lại code; trace sau rollback chứng minh request mới đã quay về v1.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** [`scripts/dashboard.py`](../scripts/dashboard.py) (`python scripts/dashboard.py` rồi mở `http://127.0.0.1:8050`). Script đọc `data/logs.jsonl` và dùng `load_dashboard_config` của validator để lấy tiêu đề, đơn vị, threshold, time range 60 phút và refresh 30 giây từ [`config/dashboard.yaml`](../config/dashboard.yaml), nên ảnh runtime luôn khớp contract. Mỗi panel có badge OK/BREACH theo threshold, số tổng hợp của cả cửa sổ và biểu đồ theo phút có đường threshold nét đứt:
  - Latency: P50/P95/P99 và TTFT P95, đường SLO P95 ≤ 3000 ms.
  - Traffic: request/phút, ngưỡng tối thiểu 1.
  - Errors: error rate % và retrieval success %, ngưỡng error ≤ 2% và retrieval ≥ 90% (lấy từ guardrail trong `slo.yaml`), kèm breakdown `error_type`.
  - Cost: USD/phút và đường luỹ kế, ngưỡng tổng ≤ 2.5 USD.
  - Tokens: input/output mỗi phút và luỹ kế, ngưỡng 50000 cho mỗi field.
  - Quality: mean, ngưỡng ≥ 0.75.

  Retrieval success tính trên mọi event có `tool_success` (`response_sent` lẫn `request_failed`), nên tôi thêm `response_sent` vào `events` của panel errors; nếu chỉ lấy `request_failed` thì tỉ lệ luôn 0%. `python scripts/dashboard.py --summary` in cùng số liệu ra terminal. Test: [`tests/test_dashboard_runtime.py`](../tests/test_dashboard_runtime.py).
- **SLO và lý do chọn:** giữ SLO `fast_successful_requests`: 99.5% request thành công **và** ≤ 3000 ms trong 28 ngày ([`config/slo.yaml`](../config/slo.yaml)). Baseline CP0 có P50 388 ms, P95 779 ms, tối đa 1092 ms. Sau khi tạo prompt trên Langfuse, request thường chỉ khoảng 152 ms; cold start tải prompt khoảng 1.1 s. Ngưỡng 3000 ms chừa khoảng 2.7 lần headroom so với request chậm nhất bình thường, nên cold start không đốt budget. Target 99.5% (không phải 99.9%) vì app phụ thuộc hai dịch vụ ngoài và chạy một instance, không retry/failover.
- **Cách tính error budget:** budget = 100% − 99.5% = 0.5% số request trong 28 ngày: `floor(total × 0.005)`. 10,000 request thì được phép 50 request lỗi hoặc > 3000 ms. Với workload lab khoảng 10 request/phút (403,200 request/28 ngày) thì được 2,016 request, tức khoảng 72 request/ngày hay 3 request/giờ. Một sự cố lỗi 100% traffic đốt khoảng 3 giờ budget mỗi phút, nên alert lỗi phải phát sau 5 phút.
- **Ba alert và runbook tương ứng:** định nghĩa trong [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook trong [`docs/alerts.md`](../docs/alerts.md). Cả ba có owner `student-2A202602921` và gửi Slack `#k4-l3b-alerts`:
  1. `LatencyP95High` (warning, 5m): P95 > 2000 ms. Cảnh báo sớm dưới SLO 3000 ms, vì retrieval chậm thêm 2.5 s chỉ đưa request lên khoảng 2.65 s, chưa vượt SLO nhưng đã bất thường so với baseline ≤ 1.2 s. Nâng lên critical nếu P95 > 3000 ms. Runbook [Alert 1](../docs/alerts.md#alert-1).
  2. `ErrorRateOrRetrievalFailing` (critical, 5m): error rate > 2% hoặc retrieval success < 90%. Runbook [Alert 2](../docs/alerts.md#alert-2).
  3. `CostPerRequestSpike` (warning, 10m): chi phí trung bình > 0.005 USD/request, khoảng 2.4 lần baseline 0.0021 USD. Đo theo request để traffic tăng hợp lệ không gây báo nhầm. Runbook [Alert 3](../docs/alerts.md#alert-3).

  Mỗi runbook có ba bước Metrics → Logs → Traces kèm lệnh lọc log cụ thể và mitigation.

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
