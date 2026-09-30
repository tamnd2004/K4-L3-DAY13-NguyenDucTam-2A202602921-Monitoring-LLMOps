# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `LatencyP95High`
- Severity: `warning` (nâng lên `critical` nếu P95 > 3000 ms, tức vượt SLO, trong 5 phút)
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency của `response_sent.latency_ms`; SLO `fast_successful_requests` (99.5% request thành công và ≤ 3000 ms trong 28 ngày), xem [`config/slo.yaml`](../config/slo.yaml).
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2000 ms` liên tục 5 phút. Baseline P95 ≤ 1.2 s kể cả cold start tải prompt, nên 2000 ms là tín hiệu sớm trước khi request vượt 3000 ms và đốt error budget.
- Ảnh hưởng tới người dùng: phải chờ lâu hơn trước khi nhận câu trả lời. Nếu TTFT vẫn bình thường mà latency tăng thì phần chậm nằm trước LLM (retrieval hoặc tải prompt).
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** mở panel *Latency percentiles and TTFT* trên dashboard (`python scripts/dashboard.py`), xác định phút bắt đầu tăng và so P95/P99 với TTFT P95. Kiểm tra panel *Request traffic* để loại trừ việc tăng tải.
  2. **Logs:** lọc request chậm trong khoảng đó, chọn một `correlation_id`:
     `python -c "import json; rows=[json.loads(l) for l in open('data/logs.jsonl', encoding='utf-8')]; [print(r['ts'], r['correlation_id'], r['session_id'], r['latency_ms'], 'ms') for r in rows if r.get('event')=='response_sent' and r.get('latency_ms',0)>2000]"`
  3. **Traces:** trên Langfuse → Tracing, lọc metadata `correlation_id` bằng ID vừa chọn, mở waterfall. So thời gian `retrieval` với `generation`; nếu cả hai ngắn mà `lab-agent-run` dài thì chậm ở bước tải prompt (xem `prompt_source`, `prompt_fetch_error` trong metadata).
- Mitigation tạm thời: nếu `retrieval` chậm thì chuyển sang tài liệu fallback/cache hoặc tắt backend chậm (practice: `python scripts/inject_incident.py --scenario rag_slow --disable`). Nếu `generation` chậm sau khi đổi prompt thì rollback label `production` về version trước. Nếu chậm ở bước tải prompt thì kiểm tra region/key Langfuse; app vẫn chạy nhờ fallback local.
- Owner: `student-2A202602921`

## Alert 2

- Tên: `ErrorRateOrRetrievalFailing`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate `count(request_failed) / count(request_received)` và retrieval success `count(tool_success == true) / count(tool_success != null)`; SLO `fast_successful_requests` và guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90`.
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` **hoặc** `tool_success_rate_pct < 90` liên tục 5 phút. Mọi request lỗi đều tính vào error budget, và ở workload ~10 request/phút một sự cố lỗi 100% đốt ~3 giờ budget mỗi phút, nên phải báo ngay sau 5 phút.
- Ảnh hưởng tới người dùng: nhận HTTP 500 thay vì câu trả lời, hoặc câu trả lời thiếu context nếu retrieval thất bại.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** mở panel *Error rate and retrieval success*, xác định phút bắt đầu lỗi, breakdown `error_type` và retrieval success có giảm cùng lúc không.
  2. **Logs:** lọc request lỗi, chọn một `correlation_id`:
     `python -c "import json; rows=[json.loads(l) for l in open('data/logs.jsonl', encoding='utf-8')]; [print(r['ts'], r['correlation_id'], r.get('error_type'), r.get('tool_name'), r.get('payload',{}).get('detail')) for r in rows if r.get('event')=='request_failed']"`
  3. **Traces:** mở trace cùng `correlation_id` trên Langfuse. Observation lỗi có level `ERROR` và status message (ví dụ `retrieval` báo `Vector store timeout`); nếu `generation` không xuất hiện thì request đã dừng ở bước retrieval.
- Mitigation tạm thời: nếu lỗi ở `retrieval` thì chuyển sang câu trả lời fallback không cần context hoặc failover vector store (practice: `python scripts/inject_incident.py --scenario tool_fail --disable`). Nếu lỗi xuất hiện ngay sau khi promote prompt/config mới thì rollback về version trước.
- Owner: `student-2A202602921`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: chi phí trung bình mỗi request `avg(response_sent.cost_usd)`, cùng panel *Cost over time* và *Input and output tokens*; guardrail `daily_cost_usd_max: 2.5`.
- Điều kiện và thời gian duy trì: `avg(cost_usd) > 0.005 USD/request` liên tục 10 phút. Baseline khoảng 0.0021 USD/request, nên 0.005 ≈ 2.4 lần baseline. Đo theo request nên traffic tăng hợp lệ không gây báo nhầm. Duration dài hơn hai alert kia vì cost không làm hỏng request ngay.
- Ảnh hưởng tới người dùng: không thấy lỗi ngay, nhưng ngân sách LLM cạn nhanh hơn dự kiến. Câu trả lời dài bất thường cũng thường chậm hơn và khó đọc hơn.
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** mở panel *Cost over time* và *Input and output tokens*. Nếu cost/phút tăng mà traffic phẳng thì chi phí mỗi request đã tăng. Xác định field tăng là `tokens_in` (prompt dài hơn) hay `tokens_out` (câu trả lời dài hơn).
  2. **Logs:** lọc request đắt, chọn một `correlation_id`:
     `python -c "import json; rows=[json.loads(l) for l in open('data/logs.jsonl', encoding='utf-8')]; [print(r['ts'], r['correlation_id'], r['tokens_in'], r['tokens_out'], r['cost_usd']) for r in rows if r.get('event')=='response_sent' and r.get('cost_usd',0)>0.005]"`
  3. **Traces:** mở trace cùng `correlation_id`, bấm observation `generation`: xem usage input/output, cost, model và nhãn prompt `day13-chat - vN`. So `prompt_version` với các request trước đó để biết cost tăng có trùng lúc đổi label `production` không.
- Mitigation tạm thời: nếu tăng sau khi promote prompt thì rollback label `production` về version trước. Nếu `tokens_out` tăng mà prompt không đổi thì giới hạn max output tokens hoặc tạm chuyển model rẻ hơn (practice: `python scripts/inject_incident.py --scenario cost_spike --disable`).
- Owner: `student-2A202602921`
