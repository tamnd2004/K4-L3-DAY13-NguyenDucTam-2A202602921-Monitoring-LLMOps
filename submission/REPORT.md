# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Evidence theo hướng dẫn CP4 của buổi demo (14 mục 01–14). Hướng dẫn này được ưu tiên hơn bộ "3 text + 5 ảnh" trong bản starter cập nhật lúc 10:43 ngày 2026-09-30, vì hai nguồn mâu thuẫn và `docs/SCREENSHOT_GUIDE.md` vẫn dùng bộ 14 mục. Mọi đường dẫn là tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Đức Tâm
- **MSSV:** 2A202602921
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tamnd2004/K4-L3-DAY13-NguyenDucTam-2A202602921-Monitoring-LLMOps
- **Commit SHA cuối:** COMMIT_SHA_PLACEHOLDER
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602921`

## 2. Evidence index

| # | Evidence | Đường dẫn | ID/ghi chú để đối chiếu |
|---|---|---|---|
| 00 | Baseline CP0 (text) | [`evidence/00-baseline.txt`](evidence/00-baseline.txt) | trước khi sửa code |
| 01 | Pytest cuối (text) | [`evidence/01-pytest.txt`](evidence/01-pytest.txt) | `git log -1 --oneline` + `N passed` |
| 02 | Log validator | [`evidence/02-log-validator.png`](evidence/02-log-validator.png) | 100/100 |
| 03 | Dashboard validator | [`evidence/03-dashboard-validator.png`](evidence/03-dashboard-validator.png) | HỢP LỆ 6/6 |
| 04 | Structured log | [`evidence/04-structured-log.png`](evidence/04-structured-log.png) | `req-04c0de02` |
| 05 | PII redaction | [`evidence/05-pii-redaction.png`](evidence/05-pii-redaction.png) | `req-05c0de01` |
| 06 | Trace list | [`evidence/06-trace-list.png`](evidence/06-trace-list.png) | dòng 10:49:16 là trace của ảnh 04 |
| 07 | Trace waterfall | [`evidence/07-trace-waterfall.png`](evidence/07-trace-waterfall.png) | trace `4c2f24ff736e49e17c3846e38ec153fc` |
| 08a | Trace metadata (root) | [`evidence/08a-trace-metadata-root.png`](evidence/08a-trace-metadata-root.png) | cùng trace, `correlation_id=req-04c0de02` |
| 08b | Trace metadata (generation) | [`evidence/08b-trace-metadata-generation.png`](evidence/08b-trace-metadata-generation.png) | cùng trace, `Prompt: day13-chat - v1` |
| 09 | Prompt versions | [`evidence/09-prompt-versions.png`](evidence/09-prompt-versions.png) | v1/v2, `baseline`/`candidate`/`production` |
| 10a | Sau promote | [`evidence/10a-prompt-promote.png`](evidence/10a-prompt-promote.png) | `production` ở v2 |
| 10b | Sau rollback | [`evidence/10b-prompt-rollback.png`](evidence/10b-prompt-rollback.png) | `production` về v1 |
| 11 | Dashboard overview | [`evidence/11-dashboard-overview.png`](evidence/11-dashboard-overview.png) | 6 panel, workload CP2 |
| 12 | Incident metric | [`evidence/12-incident-metric.png`](evidence/12-incident-metric.png) | baseline 11:15, sự cố 11:16, hồi phục 11:17 |
| 13 | Incident log | [`evidence/13-incident-log.png`](evidence/13-incident-log.png) | `req-0dd32ce2` |
| 14 | Incident trace | [`evidence/14-incident-trace.png`](evidence/14-incident-trace.png) | trace `9ea4b36be292143d60299048d5c37f2d` |

Giờ trong log là UTC, còn Langfuse và dashboard hiển thị giờ Việt Nam (UTC+7), ví dụ `04:16:03Z` trong log = `11:16:03` trên Langfuse.

## 3. Kết quả kỹ thuật

Baseline (CP0) chạy lúc 2026-09-30 09:44 (UTC+7) với 10 request của `scripts/load_test.py`, API chạy bằng `--env-file .env` (`/health`: `ok: true`, `tracing_enabled: true`). Output đầy đủ: [`evidence/00-baseline.txt`](evidence/00-baseline.txt).

| Nội dung                | Baseline                                   | Kết quả cuối | Nhận xét |
| ----------------------- | ------------------------------------------ | ------------ | -------- |
| `validate_logs.py`      | 30/100                                     | **100/100** | Baseline: 20/20 record thiếu `correlation_id` và enrichment (`user_id_hash`, `session_id`, `feature`, `model`); 0 correlation ID duy nhất. Cuối: 0 record thiếu field hay enrichment, 0 PII leak ([02](evidence/02-log-validator.png); chạy lại trên log CP3 cũng 100/100). |
| `validate_dashboard.py` | HỢP LỆ 6/6 panel                           | **HỢP LỆ 6/6 panel** | Contract starter đã đủ 6 panel. Tôi chỉ thêm `response_sent` vào `events` của panel errors để retrieval success tính đúng ([03](evidence/03-dashboard-validator.png)). |
| `pytest`                | 22 passed                                  | **38 passed** | +16 test mới (PII, correlation/logging, child span, dashboard runtime). Lệnh mặc định trên máy tôi báo 4 error `PermissionError` vì thư mục temp của pytest bị khoá quyền (WinError 5), không phải lỗi code; đổi temp root thì toàn bộ pass ([01](evidence/01-pytest.txt)). |
| Số traces hợp lệ        | 10 traces, chỉ có root `lab-agent-run`     | **151 traces** đủ cây root/retrieval/generation | Từ lúc thêm child span (10:18 UTC+7) tới hết CP3, cả 151/151 trace có `correlation_id` hợp lệ `req-<8hex>` trùng với log. Project có tổng khoảng 178 root trace ([06](evidence/06-trace-list.png)). |
| Số PII leak             | 0                                          | **0** | Baseline chỉ nhờ `summarize_text` che preview; cuối cùng `scrub_event` chạy trước khi ghi mọi log, và trace không capture input/output ([05](evidence/05-pii-redaction.png), [08b](evidence/08b-trace-metadata-generation.png)). |
| Latency P95 / TTFT P95  | 779 ms / 51 ms                             | **169 ms / 50 ms** (vận hành thường) · **2656 ms / 50 ms** (phút sự cố) | Vận hành thường gồm 143 request CP2 và CP3 ngoài phút sự cố: P50 152 ms, P99 1153 ms (cold start sau khi khởi động API). P50 giảm từ 388 xuống 152 ms vì sau khi tạo prompt `day13-chat`, app không còn chờ một lần tải prompt thất bại ở mỗi request. |
| Retrieval success rate  | 100% (10/10)                               | **100%** (143/143 thường; 5/5 trong sự cố) | Sự cố CP3 là retrieval **chậm** chứ không lỗi, nên tỉ lệ vẫn 100%. Đây là lý do cần alert latency riêng (mục 7). |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** [`app/middleware.py`](../app/middleware.py) chạy đầu mỗi request: gọi `clear_contextvars()` để xoá context cũ, sau đó nhận header `x-request-id` nếu đúng format `req-<8-hex>` (so khớp regex, không phân biệt hoa thường). Header rỗng hoặc sai format (ví dụ `a@b.vn`, `req-XYZ`) bị bỏ và sinh ID mới `req-` + 8 ký tự đầu của `uuid4().hex`, vì header là input không tin cậy và có thể mang PII hoặc làm giả dòng log. ID được `bind_contextvars(correlation_id=...)` và gán vào `request.state.correlation_id` để agent đưa vào metadata của trace Langfuse. Response trả lại `x-request-id` và `x-response-time-ms`; body `/chat` cũng có `correlation_id`.
- **Các metadata được ghi vào structured log:** [`app/main.py`](../app/main.py) bind một lần trước dòng `request_received`: `user_id_hash` (SHA-256 cắt 12 ký tự, không ghi `user_id` gốc), `session_id`, `feature`, `model`, `env`. Nhờ context này, mọi log của request (`request_received`, `response_sent`, `request_failed`) đều có cùng bộ field cùng với `ts`, `level`, `service`, `event`, `correlation_id`. `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** [`app/logging_config.py`](../app/logging_config.py) đăng ký `scrub_event` sau `format_exc_info` và trước `JsonlFileProcessor`/`JSONRenderer`, nên traceback đã được render thành chuỗi cũng bị scrub và không có đường nào ghi PII thô xuống file hay stdout. `scrub_event` duyệt đệ quy mọi chuỗi, kể cả `payload` lồng nhau và list, trừ các field do hệ thống sinh (`ts`, `level`, `correlation_id`, `user_id_hash`); `user_id_hash` là hex nên có thể trùng pattern CCCD 12 số. [`app/pii.py`](../app/pii.py) che email, điện thoại VN, CCCD, thẻ và thêm hộ chiếu VN (`[A-Z]` + 7 số). Thứ tự pattern giữ CCCD trước thẻ, vì pattern thẻ cho phép bỏ dấu cách nên nếu chạy trước sẽ ghép `001099012345 4111` thành một "số thẻ" và để lộ phần còn lại.
- **Cách kiểm chứng kết quả:**
  - Test mới trong [`tests/test_pii.py`](../tests/test_pii.py) (CCCD, 3 format thẻ, hộ chiếu, số thường không bị che, câu ghép 4 loại PII) và [`tests/test_correlation_logging.py`](../tests/test_correlation_logging.py) (header được giữ, ID sai format bị thay, mỗi request có ID riêng, log thật không còn PII, scrub payload lồng nhau và traceback). `pytest`: 31 passed.
  - Chuyển log baseline ra ngoài repo, restart API, chạy `load_test.py` thì `validate_logs.py` đạt **100/100**: 47 record, 0 thiếu field, 0 thiếu enrichment, 23 correlation ID duy nhất, 0 PII leak ([`evidence/02-log-validator.png`](evidence/02-log-validator.png)).
  - Request mẫu `req-04c0de02` (gửi sau khi đã có child span và prompt Langfuse) trả header `x-request-id: req-04c0de02`, `x-response-time-ms: 161.4`. Hai dòng log `request_received` và `response_sent` có đủ `ts`, `event`, `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, `latency_ms` ([`evidence/04-structured-log.png`](evidence/04-structured-log.png)). Trace Langfuse `4c2f24ff736e49e17c3846e38ec153fc` có metadata `correlation_id=req-04c0de02` ([`evidence/08a-trace-metadata-root.png`](evidence/08a-trace-metadata-root.png)).
  - Request `req-05c0de01` gửi `a@b.vn 0901234567 001099012345 4111 1111 1111 1111` (PII giả); log ghi `[REDACTED_EMAIL] [REDACTED_PHONE_VN] [REDACTED_CCCD] [REDACTED_CREDIT_CARD]` ([`evidence/05-pii-redaction.png`](evidence/05-pii-redaction.png)). Trace tương ứng: `1cd1a427df7d262d510afe4b9b795aa3`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** key trong `.env` (không commit) được tạo trong project `day13-k4-l3b-2A202602921`, và `GET /api/public/projects` bằng key này trả đúng tên project đó. Mọi trace do tôi tự chạy `scripts/load_test.py` hoặc gửi request có `x-request-id` tự đặt; `correlation_id` trong metadata trace khớp với dòng log trong `data/logs.jsonl` của máy tôi. Pytest chạy trong terminal không nạp key nên không tạo trace lạ.
- **Cấu trúc root/retrieval/generation observations:** trace `day13-agent-request` có root `lab-agent-run` (loại `agent`, [`app/agent.py`](../app/agent.py)) và hai child: `retrieval` (loại `retriever`, `@observe` trên `retrieve` trong [`app/mock_rag.py`](../app/mock_rag.py)) và `generation` (loại `generation`, `@observe` trên `FakeLLM.generate` trong [`app/mock_llm.py`](../app/mock_llm.py)). Generation ghi `model`, `usage_details` (input/output tokens), `cost_details` (dùng chung bảng giá với log qua `usage_cost_usd`) và `completion_start_time`, nên Langfuse hiện TTFT khoảng 0.05 s. Prompt version được link qua `propagate_attributes(prompt=managed_prompt)`: chỉ gửi object prompt lấy từ Langfuse, không gửi prompt đã điền câu hỏi. Mọi observation đặt `capture_input=False, capture_output=False` nên Input/Output trống, không có PII. Evidence là trace `4c2f24ff736e49e17c3846e38ec153fc` của request ở ảnh 04:
  - Waterfall ([`07`](evidence/07-trace-waterfall.png)): root 152 ms, retrieval 0 ms, generation 151 ms.
  - Metadata root ([`08a`](evidence/08a-trace-metadata-root.png)): `prompt_name=day13-chat`, `prompt_label=production`, `prompt_version=1`, `prompt_source=langfuse`.
  - Generation ([`08b`](evidence/08b-trace-metadata-generation.png)): model `claude-sonnet-4-5`, 115 tokens, $0.001437, TTFT 0.05 s, nhãn `Prompt: day13-chat - v1`.
  - Danh sách trace ([`06`](evidence/06-trace-list.png)) có tên project cá nhân, trace name `day13-agent-request`, cột Input/Output trống, và trace này ở dòng 10:49:16.
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

  Ảnh [`11-dashboard-overview.png`](evidence/11-dashboard-overview.png) chụp workload CP2 (09:50–10:50, 158 request): cả 6 panel OK, P50 153 ms, P95 1109 ms, TTFT P95 50 ms, error 0%, retrieval 100%, cost $0.33, quality 0.876. Validator: [`03-dashboard-validator.png`](evidence/03-dashboard-validator.png).
- **SLO và lý do chọn:** giữ SLO `fast_successful_requests`: 99.5% request thành công **và** ≤ 3000 ms trong 28 ngày ([`config/slo.yaml`](../config/slo.yaml)). Baseline CP0 có P50 388 ms, P95 779 ms, tối đa 1092 ms. Sau khi tạo prompt trên Langfuse, request thường chỉ khoảng 152 ms; cold start tải prompt khoảng 1.1 s. Ngưỡng 3000 ms chừa khoảng 2.7 lần headroom so với request chậm nhất bình thường, nên cold start không đốt budget. Target 99.5% (không phải 99.9%) vì app phụ thuộc hai dịch vụ ngoài và chạy một instance, không retry/failover.
- **Cách tính error budget:** budget = 100% − 99.5% = 0.5% số request trong 28 ngày: `floor(total × 0.005)`. 10,000 request thì được phép 50 request lỗi hoặc > 3000 ms. Với workload lab khoảng 10 request/phút (403,200 request/28 ngày) thì được 2,016 request, tức khoảng 72 request/ngày hay 3 request/giờ. Một sự cố lỗi 100% traffic đốt khoảng 3 giờ budget mỗi phút, nên alert lỗi phải phát sau 5 phút.
- **Ba alert và runbook tương ứng:** định nghĩa trong [`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook trong [`docs/alerts.md`](../docs/alerts.md). Cả ba có owner `student-2A202602921` và gửi Slack `#k4-l3b-alerts`:
  1. `LatencyP95High` (warning, 5m): P95 > 2000 ms. Cảnh báo sớm dưới SLO 3000 ms, vì retrieval chậm thêm 2.5 s chỉ đưa request lên khoảng 2.65 s, chưa vượt SLO nhưng đã bất thường so với baseline ≤ 1.2 s. Nâng lên critical nếu P95 > 3000 ms. Runbook [Alert 1](../docs/alerts.md#alert-1).
  2. `ErrorRateOrRetrievalFailing` (critical, 5m): error rate > 2% hoặc retrieval success < 90%. Runbook [Alert 2](../docs/alerts.md#alert-2).
  3. `CostPerRequestSpike` (warning, 10m): chi phí trung bình > 0.005 USD/request, khoảng 2.4 lần baseline 0.0021 USD. Đo theo request để traffic tăng hợp lệ không gây báo nhầm. Runbook [Alert 3](../docs/alerts.md#alert-3).

  Mỗi runbook có ba bước Metrics → Logs → Traces kèm lệnh lọc log cụ thể và mitigation.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, 5 query feature `monitoring`, `latency_threshold_ms` 2000).
- **Khoảng thời gian điều tra:** ngày 2026-09-30, giờ UTC+7. Trước đó log cũ đã được chuyển ra ngoài repo và API chạy không `--reload`.
  - Baseline: 11:15:19–11:15:24, 10 request.
  - Challenge: 11:16:02–11:16:16 (04:16:02–04:16:16 UTC trong log).
  - Sau khi fix: 11:17:39–11:17:42, 10 request.
- **Triệu chứng từ metrics:** chỉ panel *Latency* bất thường ([`evidence/12-incident-metric.png`](evidence/12-incident-metric.png)):
  - Phút 11:16: P50 **2653 ms**, P95 **2656 ms**, so với phút baseline 11:15 là P50 152 ms. Tăng khoảng 17 lần, và cả 5/5 request vượt `latency_threshold_ms` 2000 của challenge.
  - TTFT P95 vẫn 50 ms, error rate 0%, retrieval success 100%; cost, tokens và quality (0.84 so với 0.88) nằm trong dao động bình thường. Vậy phần chậm nằm trước lúc LLM trả token đầu, và request không lỗi.
  - Panel *Traffic* báo BREACH chỉ vì cửa sổ 60 phút mới có ít request sau khi chuyển log ra ngoài, không phải triệu chứng của sự cố.
- **Log line và correlation ID liên quan:** lọc `response_sent` có `latency_ms > 2000` ra đúng 5 request challenge (session `k4-l3b-challenge-s01…s05`, 2652–2656 ms). Request đại diện là **`req-0dd32ce2`** ([`evidence/13-incident-log.png`](evidence/13-incident-log.png)):
  `{"event": "response_sent", "correlation_id": "req-0dd32ce2", "session_id": "k4-l3b-challenge-s05", "feature": "monitoring", "model": "claude-sonnet-4-5", "env": "dev", "latency_ms": 2653, "ttft_ms": 50, "tool_name": "retrieval", "tool_success": true, "ts": "2026-09-30T04:16:05.767783Z"}`.
  Log cũng có sự kiện thay đổi cấu hình `{"service": "control", "event": "incident_enabled", "ts": "2026-09-30T04:16:02.111434Z"}`, xảy ra 1 giây trước request chậm đầu tiên.
- **Trace ID và span gây ảnh hưởng:** trace **`9ea4b36be292143d60299048d5c37f2d`** (metadata `correlation_id=req-0dd32ce2`, prompt `day13-chat` production v1, [`evidence/14-incident-trace.png`](evidence/14-incident-trace.png); trong ảnh timeline, thanh xanh lá 2.50 s là `retrieval`, thanh hồng 153 ms là `generation`). Root `lab-agent-run` mất 2.654 s, trong đó **`retrieval` mất 2.500 s (94%)**. `generation` mất 0.153 s với TTFT 0.052 s, giống baseline (trace `17208be5a3c9855936b1a4429d7bfa55` của `req-e982830f`: retrieval ~0 s, generation 0.153 s). Không observation nào ở level ERROR. Cả 5 trace challenge đều có retrieval 2.500–2.501 s.
- **Root cause:** bước **retrieval (RAG) chậm thêm một lượng cố định khoảng 2.5 s mỗi lần gọi**, bắt đầu cùng lúc với thay đổi cấu hình `incident_enabled` lúc 11:16:02: đây là incident `rag_slow`, mô phỏng vector store phản hồi chậm trong [`app/mock_rag.py`](../app/mock_rag.py). Ba lớp bằng chứng cùng loại trừ các nguyên nhân khác:
  - Metric: TTFT, token và cost không đổi, nên không phải LLM hay prompt dài.
  - Log: `tool_success=true` và không có `request_failed`, nên retrieval chậm chứ không lỗi.
  - Trace: prompt vẫn production v1 và generation 0.15 s như baseline, còn retrieval chiếm 94% latency.
- **Fix action:** tắt nguồn gây chậm của retrieval (`python scripts/inject_incident.py --disable`, lúc 11:17:39; trong production tương ứng với failover hoặc khôi phục vector store) rồi kiểm chứng bằng cùng workload. 10/10 request quay về 151–154 ms. Trace sau fix `088fd888b9e4124a3e9a4ee67261ad8e` (`req-2f694a46`) có retrieval ~0 s, root 0.152 s.
- **Preventive measure:**
  1. **Alert sớm theo triệu chứng:** giữ `LatencyP95High` ở P95 > 2000 ms ([`config/alert_rules.yaml`](../config/alert_rules.yaml), runbook [Alert 1](../docs/alerts.md#alert-1)). Sự cố này có P95 2656 ms, **vẫn dưới SLO 3000 ms** nên không đốt error budget và badge dashboard vẫn OK; nếu chỉ alert theo SLO thì sẽ bỏ sót, dù người dùng chờ lâu hơn 17 lần.
  2. **Timeout + fallback cho retrieval:** đặt ngân sách khoảng 500 ms cho `retrieve()`. Quá hạn thì trả tài liệu fallback/cache và log `tool_success=false`, `error_type=RetrievalTimeout`. Latency người dùng khi đó bị chặn dưới 1 s, và sự cố hiện lên ngay ở panel retrieval success và alert 2, thay vì âm thầm làm chậm.
  3. **Metric theo từng bước:** ghi thêm `retrieval_ms`/`generation_ms` vào `response_sent` và thêm alert `p95(retrieval_ms) > 500 ms` trong 5 phút, để khoanh vùng từ dashboard mà chưa cần mở trace.
  4. **Hiển thị thay đổi cấu hình:** đưa event `service=control` (`incident_enabled`/config change) lên dashboard làm annotation, để thấy ngay thay đổi xảy ra 1 giây trước triệu chứng.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tôi đặt alert latency ở **P95 > 2000 ms**, thấp hơn ngưỡng SLO 3000 ms, thay vì alert đúng bằng SLO.
  - Lý do từ baseline: vận hành bình thường có P95 169 ms, và cả khi cold start P99 cũng chỉ khoảng 1.2 s, nên 2000 ms đã là bất thường rõ ràng.
  - Challenge CP3 chứng minh quyết định này: retrieval chậm thêm 2.5 s đẩy P95 lên 2656 ms, vẫn **dưới** SLO nên không đốt error budget và badge latency trên dashboard vẫn OK, trong khi người dùng chờ lâu hơn 17 lần. Alert theo SLO sẽ bỏ sót; alert 2000 ms (trùng `latency_threshold_ms` của đề) thì bắt được.
  - Một quyết định khác: middleware chỉ nhận `x-request-id` đúng format `req-<8hex>`, vì header do client gửi có thể chứa PII hoặc chuỗi làm giả dòng log.
- **Một lỗi/blocker đã gặp:** khi viết thêm pattern PII, tôi đổi thứ tự để pattern thẻ chạy trước CCCD (nghĩ là "pattern dài trước thì an toàn hơn"). Test câu ghép `a@b.vn 0901234567 001099012345 4111 1111 1111 1111` fail, output là `[REDACTED_EMAIL] [REDACTED_PHONE_VN] [REDACTED_CREDIT_CARD] 1111 1111 1111`, nghĩa là log vẫn lộ 12 chữ số thẻ. Blocker khác là môi trường: thư mục temp của pytest bị khoá quyền (4 error `PermissionError`), và API `GET /api/public/traces` của Langfuse trả 410 cho org mới.
- **Cách tìm nguyên nhân và xử lý:**
  - Đọc output test thì thấy pattern thẻ `\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}` cho phép bỏ dấu cách, nên đã nuốt CCCD `0010 9901 2345` cộng nhóm `4111` thành một "số thẻ", để lại ba nhóm cuối. Tôi trả thứ tự về CCCD trước thẻ, ghi chú lý do trong [`app/pii.py`](../app/pii.py), và giữ test câu ghép làm regression test.
  - Với pytest, tôi xác nhận lỗi xảy ra cả ngoài sandbox (`icacls` cũng bị từ chối), nên đó là lỗi quyền của thư mục chứ không phải code, và chạy với `PYTEST_DEBUG_TEMPROOT` trỏ sang thư mục khác.
  - Với Langfuse, tôi đọc body lỗi 410 và chuyển sang `GET /api/public/v2/observations` để kiểm tra trace bằng script.
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics trả lời *có vấn đề gì và từ lúc nào*: phút 11:16 P95 lên 2656 ms, trong khi TTFT, lỗi và cost bình thường, nên chậm nằm trước LLM và không có lỗi. Logs trả lời *request nào bị ảnh hưởng*: lọc `latency_ms > 2000` ra 5 request và chọn `req-0dd32ce2`. Traces trả lời *bước nào gây ra*: trace cùng `correlation_id` cho thấy `retrieval` chiếm 2.50/2.65 s. Mỗi lớp thu hẹp phạm vi cho lớp sau, và `correlation_id` là khoá nối log với trace. Nếu mở trace ngẫu nhiên trước thì không biết trace nào là bất thường, hay bất thường từ khi nào.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Prompt là một phần của "code" nhưng thay đổi không cần deploy. Vì vậy mỗi trace phải ghi `prompt_name/label/version`, nếu không sẽ không biết một regression đến từ prompt hay từ code. Ví dụ v2 chỉ thêm một dòng nhưng làm `tokens_in` tăng từ 27 lên 35 (+30%), tức cost input tăng theo mọi request.
  - Label giúp promote/rollback trong vài giây mà không sửa code; trace sau rollback (`705ce7b6…`, v1) chứng minh request mới đã dùng lại version cũ.
  - SLO và error budget quyết định mức khẩn cấp: sự cố CP3 không đốt budget, nên cần thêm alert theo triệu chứng để bảo vệ trải nghiệm người dùng.
- **Điều quan trọng nhất đã học:** kết luận phải đi theo bằng chứng, không theo cảm giác. Ví dụ latency baseline khoảng 380 ms thoạt nhìn giống "app chậm". Nhưng trace `c801199bd58039908e2ff5821431ee8c` (`req-c2c2c2c2`, trước khi tạo prompt) có root 1.1 s trong khi retrieval ~0 s và generation 0.15 s, metadata `prompt_source=local-fallback`, tức thời gian mất ở bước tải prompt `day13-chat` (lúc đó prompt chưa tồn tại). Tạo prompt xong thì P50 còn 152 ms, không cần sửa dòng code nào.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  1. Bước tải prompt (`resolve_prompt`) chưa có span riêng. Vài request lẻ trong CP2 (`req-2d63bbe6` 2119 ms, `req-1ae3e7fd` 1086 ms) có retrieval ~0 s và generation 0.15 s; 1–2 s còn lại là khoảng trống trong root span, nằm ngoài hai child span. Trong code, giữa retrieval và generation chỉ có `resolve_prompt`, nên nhiều khả năng là do tải hoặc làm mới prompt, nhưng waterfall chưa chứng minh được. Cần thêm span riêng `@observe(name="prompt-fetch")` để kiểm chứng.
  2. Ba alert mới được định nghĩa trong YAML và runbook, chưa nối vào hệ thống alert thật (Prometheus/Grafana hay Slack webhook).
  3. Badge Traffic tính trung bình cả cửa sổ 60 phút, nên báo BREACH khi lab chỉ chạy vài đợt ngắn (ảnh 12). Nên tính theo các phút gần nhất.
  4. Prompt v1/v2 được tạo và dời label bằng Langfuse SDK (`create_prompt`, `update_prompt`) thay vì thao tác tay trên UI; kết quả trên UI giống nhau (ảnh 09/10a/10b).
  5. Ảnh 14 chụp timeline khi tắt "Show labels", nên các thanh không có tên và được nhận diện theo màu (retriever xanh lá, generation hồng), cùng cấu trúc với ảnh 07.
  6. `config/challenge.json` đã được upstream commit vào starter (`0a7eadb`), nên có trong repo qua lần merge fork. Tôi không sửa file này.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Có evidence 01–14 theo hướng dẫn CP4 của buổi demo (xem mục 2).
- [x] Incident evidence nối đúng metric → log → trace (`req-0dd32ce2` ↔ trace `9ea4b36b…`).
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
