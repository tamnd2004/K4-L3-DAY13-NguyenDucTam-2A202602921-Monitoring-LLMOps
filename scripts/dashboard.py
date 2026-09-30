"""Dashboard 6 panel dựng từ data/logs.jsonl theo contract config/dashboard.yaml.

Chạy:  python scripts/dashboard.py            -> mở http://127.0.0.1:8050
       python scripts/dashboard.py --summary  -> in số liệu cửa sổ 60 phút ra terminal

Chỉ dùng thư viện chuẩn + PyYAML (đã có trong requirements.txt); trình duyệt tải
Chart.js từ CDN. Tiêu đề, đơn vị, threshold, time range và refresh đều đọc từ YAML
nên dashboard runtime luôn khớp contract mà validate_dashboard.py kiểm tra.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio
from app.metrics import percentile
from scripts.validate_dashboard import load_dashboard_config

DEFAULT_CONFIG = REPO_ROOT / "config" / "dashboard.yaml"
DEFAULT_SLO = REPO_ROOT / "config" / "slo.yaml"
DEFAULT_LOG = REPO_ROOT / "data" / "logs.jsonl"


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            record["_ts"] = datetime.fromisoformat(record["ts"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        records.append(record)
    return records


def _events(records: list[dict], name: str) -> list[dict]:
    return [r for r in records if r.get("event") == name]


def _values(records: list[dict], event: str, field: str) -> list[float]:
    return [
        r[field]
        for r in _events(records, event)
        if isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool)
    ]


def _cumulative(values: list[float]) -> list[float]:
    total, out = 0.0, []
    for value in values:
        total += value
        out.append(round(total, 6))
    return out


def _latency(buckets: list[list[dict]], window: list[dict]) -> dict:
    def aggregate(records: list[dict]) -> dict:
        latency = _values(records, "response_sent", "latency_ms")
        ttft = _values(records, "response_sent", "ttft_ms")
        return {
            "p50": percentile(latency, 50) if latency else None,
            "p95": percentile(latency, 95) if latency else None,
            "p99": percentile(latency, 99) if latency else None,
            "ttft_p95": percentile(ttft, 95) if ttft else None,
        }

    per_minute = [aggregate(b) for b in buckets]
    return {
        "summary": aggregate(window),
        "series": {k: [m[k] for m in per_minute] for k in ("p50", "p95", "p99", "ttft_p95")},
    }


def _traffic(buckets: list[list[dict]], _: list[dict]) -> dict:
    counts = [len(_events(b, "request_received")) for b in buckets]
    return {
        "summary": {"count": sum(counts), "rate_per_minute": round(sum(counts) / len(buckets), 2)},
        "series": {"rate_per_minute": counts},
    }


def _errors(buckets: list[list[dict]], window: list[dict]) -> dict:
    def aggregate(records: list[dict]) -> dict:
        received = len(_events(records, "request_received"))
        failed = _events(records, "request_failed")
        # Retrieval success tính trên MỌI event có tool_success (response_sent lẫn
        # request_failed); chỉ lấy request_failed thì tỉ lệ luôn là 0%.
        tool = [r["tool_success"] for r in records if isinstance(r.get("tool_success"), bool)]
        return {
            "error_rate_pct": round(len(failed) / received * 100, 2) if received else None,
            "tool_success_rate_pct": round(sum(tool) / len(tool) * 100, 2) if tool else None,
            "count_by_value": dict(Counter(r.get("error_type") or "unknown" for r in failed)),
            "requests": received,
            "failed": len(failed),
        }

    per_minute = [aggregate(b) for b in buckets]
    return {
        "summary": aggregate(window),
        "series": {
            "error_rate_pct": [m["error_rate_pct"] for m in per_minute],
            "tool_success_rate_pct": [m["tool_success_rate_pct"] for m in per_minute],
        },
    }


def _cost(buckets: list[list[dict]], _: list[dict]) -> dict:
    per_minute = [round(sum(_values(b, "response_sent", "cost_usd")), 6) for b in buckets]
    return {
        "summary": {"total": round(sum(per_minute), 6), "sum_by_minute_max": max(per_minute)},
        "series": {"sum_by_minute": per_minute, "cumulative": _cumulative(per_minute)},
    }


def _tokens(buckets: list[list[dict]], _: list[dict]) -> dict:
    tokens_in = [sum(_values(b, "response_sent", "tokens_in")) for b in buckets]
    tokens_out = [sum(_values(b, "response_sent", "tokens_out")) for b in buckets]
    total_in, total_out = sum(tokens_in), sum(tokens_out)
    return {
        # Threshold sum_by_field áp cho từng field; field lớn nhất quyết định trạng thái.
        "summary": {"tokens_in": total_in, "tokens_out": total_out, "sum_by_field": max(total_in, total_out)},
        "series": {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cumulative_in": _cumulative(tokens_in),
            "cumulative_out": _cumulative(tokens_out),
        },
    }


def _quality(buckets: list[list[dict]], window: list[dict]) -> dict:
    def aggregate(records: list[dict]) -> float | None:
        scores = _values(records, "response_sent", "quality_score")
        return round(mean(scores), 3) if scores else None

    return {"summary": {"mean": aggregate(window)}, "series": {"mean": [aggregate(b) for b in buckets]}}


PANEL_BUILDERS = {
    "latency": _latency,
    "traffic": _traffic,
    "errors": _errors,
    "cost": _cost,
    "tokens": _tokens,
    "quality": _quality,
}


def _status(value: float | None, threshold: dict) -> str:
    if value is None:
        return "no_data"
    ok = value <= threshold["value"] if threshold["operator"] == "lte" else value >= threshold["value"]
    return "ok" if ok else "breach"


def build_dashboard(
    records: list[dict],
    config: dict,
    now: datetime | None = None,
    retrieval_min_pct: float | None = None,
) -> dict:
    dashboard = config["dashboard"]
    minutes = dashboard["time_range_minutes"]
    now = now or datetime.now(timezone.utc)
    end = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = end - timedelta(minutes=minutes)

    buckets: list[list[dict]] = [[] for _ in range(minutes)]
    for record in records:
        if start <= record["_ts"] < end:
            buckets[int((record["_ts"] - start).total_seconds() // 60)].append(record)
    window = [r for bucket in buckets for r in bucket]

    local_start = start.astimezone()
    offset = local_start.strftime("%z")
    panels = {}
    for panel_cfg in dashboard["panels"]:
        panel = PANEL_BUILDERS[panel_cfg["id"]](buckets, window)
        threshold = panel_cfg["threshold"]
        panel.update(
            title=panel_cfg["title"],
            unit=panel_cfg["unit"],
            query=panel_cfg["query"],
            threshold=threshold,
            status=_status(panel["summary"].get(threshold["aggregation"]), threshold),
        )
        panels[panel_cfg["id"]] = panel

    return {
        "title": dashboard["title"],
        "time_range_minutes": minutes,
        "refresh_seconds": dashboard["refresh_seconds"],
        "timezone": f"UTC{offset[:3]}:{offset[3:]}",
        "window": [local_start.strftime("%H:%M"), end.astimezone().strftime("%H:%M")],
        "generated_at": now.astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "labels": [(start + timedelta(minutes=i)).astimezone().strftime("%H:%M") for i in range(minutes)],
        "records_in_window": len(window),
        "retrieval_min_pct": retrieval_min_pct,
        "panels": panels,
    }


def _retrieval_min_pct(slo_path: Path) -> float | None:
    try:
        slo = yaml.safe_load(slo_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    return (slo.get("guardrails") or {}).get("retrieval_success_rate_pct_min")


def snapshot(log_path: Path, config_path: Path, slo_path: Path) -> dict:
    return build_dashboard(
        load_records(log_path),
        load_dashboard_config(config_path),
        retrieval_min_pct=_retrieval_min_pct(slo_path),
    )


def print_summary(data: dict) -> None:
    print(f"{data['title']} | {data['window'][0]}–{data['window'][1]} ({data['timezone']}) "
          f"| {data['records_in_window']} records")
    for panel_id, panel in data["panels"].items():
        t = panel["threshold"]
        op = "<=" if t["operator"] == "lte" else ">="
        print(f"- {panel_id:8} [{panel['status'].upper():7}] {t['aggregation']} {op} {t['value']} {panel['unit']}"
              f" | {json.dumps(panel['summary'], ensure_ascii=False)}")


PAGE = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Day 13 Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root { --bg:#f4f5f7; --card:#fff; --ink:#1d2330; --muted:#5f6b7a; --line:#e3e6eb;
          --ok:#12805c; --bad:#c4320a; --nodata:#98a2b3; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
         background:var(--bg); color:var(--ink); }
  header { display:flex; flex-wrap:wrap; gap:6px 22px; align-items:baseline; padding:12px 20px;
           background:var(--card); border-bottom:1px solid var(--line); }
  header h1 { font-size:18px; margin:0 8px 0 0; }
  .meta { color:var(--muted); font-size:13px; }
  .meta b { color:var(--ink); }
  main { display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; padding:14px 20px; }
  @media (max-width: 1150px) { main { grid-template-columns:repeat(2, minmax(0, 1fr)); } }
  @media (max-width: 720px) { main { grid-template-columns:1fr; padding:12px 16px; } }
  .panel { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; min-width:0; }
  .panel h2 { font-size:15px; margin:0 0 2px; display:flex; justify-content:space-between; gap:8px; }
  .badge { font-size:11px; font-weight:600; padding:2px 8px; border-radius:999px; color:#fff; white-space:nowrap; }
  .ok { background:var(--ok); } .breach { background:var(--bad); } .no_data { background:var(--nodata); }
  .sub { color:var(--muted); font-size:12px; margin-bottom:6px; }
  .stats { display:flex; flex-wrap:wrap; gap:2px 14px; font-size:13px; margin-bottom:6px; }
  .stats b { font-variant-numeric:tabular-nums; }
  .chart { position:relative; height:220px; }
</style>
</head>
<body>
<header>
  <h1 id="title">Dashboard</h1>
  <span class="meta">Time range: <b id="range">–</b></span>
  <span class="meta">Auto-refresh: <b id="refresh">–</b></span>
  <span class="meta">Source: <b>data/logs.jsonl</b> (<b id="records">0</b> records)</span>
  <span class="meta">Updated: <b id="updated">–</b></span>
</header>
<main id="grid"></main>
<script>
const ORDER = ["latency", "traffic", "errors", "cost", "tokens", "quality"];
const C = { p50:"#2e90fa", p95:"#7a5af8", p99:"#e04f16", ttft:"#12b76a", thr:"#d92d20", ref:"#f79009",
            err:"#d92d20", ok:"#12b76a", a:"#2e90fa", b:"#7a5af8" };
const charts = {};
const fmt = (v, d = 0) => v === null || v === undefined ? "–"
  : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const op = t => (t.operator === "lte" ? "≤ " : "≥ ") + t.value;
const line = (label, data, color, axis = "y", dash) => ({ type: "line", label, data, borderColor: color,
  backgroundColor: color, borderWidth: 2, pointRadius: 2, tension: 0.2, spanGaps: false, yAxisID: axis,
  borderDash: dash || [] });
const bar = (label, data, color, axis = "y") => ({ type: "bar", label, data, backgroundColor: color + "88",
  borderColor: color, borderWidth: 1, yAxisID: axis });
const rule = (n, value, label, color = C.thr, axis = "y") => ({ type: "line", label, data: Array(n).fill(value),
  borderColor: color, borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0, yAxisID: axis });
const axis = (title, extra = {}) => ({ beginAtZero: true, title: { display: true, text: title }, ...extra });

const SPECS = {
  latency: (p, n) => ({
    stats: [["P50", fmt(p.summary.p50) + " ms"], ["P95", fmt(p.summary.p95) + " ms"],
            ["P99", fmt(p.summary.p99) + " ms"], ["TTFT P95", fmt(p.summary.ttft_p95) + " ms"]],
    datasets: [line("P50", p.series.p50, C.p50), line("P95", p.series.p95, C.p95), line("P99", p.series.p99, C.p99),
               line("TTFT P95", p.series.ttft_p95, C.ttft), rule(n, p.threshold.value, "SLO P95 " + op(p.threshold) + " ms")],
    scales: { y: axis("ms") },
  }),
  traffic: (p, n) => ({
    stats: [["Requests", fmt(p.summary.count)], ["Avg rate", fmt(p.summary.rate_per_minute, 2) + " req/min"]],
    datasets: [bar("Requests / min", p.series.rate_per_minute, C.a), rule(n, p.threshold.value, "Min " + op(p.threshold) + " req/min")],
    scales: { y: axis("requests / minute", { ticks: { precision: 0 } }) },
  }),
  errors: (p, n, d) => {
    const s = p.summary, breakdown = Object.entries(s.count_by_value || {}).map(([k, v]) => k + "=" + v).join(", ");
    const ds = [line("Error rate %", p.series.error_rate_pct, C.err), line("Retrieval success %", p.series.tool_success_rate_pct, C.ok),
                rule(n, p.threshold.value, "Error rate " + op(p.threshold) + " %")];
    if (d.retrieval_min_pct !== null) ds.push(rule(n, d.retrieval_min_pct, "Retrieval success ≥ " + d.retrieval_min_pct + " %", C.ref));
    return {
      stats: [["Error rate", fmt(s.error_rate_pct, 2) + " %"], ["Retrieval success", fmt(s.tool_success_rate_pct, 1) + " %"],
              ["Failed", fmt(s.failed) + " / " + fmt(s.requests)], ["By type", breakdown || "none"]],
      datasets: ds,
      scales: { y: axis("percent", { max: 100 }) },
    };
  },
  cost: (p, n) => ({
    stats: [["Total (60m)", "$" + fmt(p.summary.total, 4)], ["Max / min", "$" + fmt(p.summary.sum_by_minute_max, 4)]],
    datasets: [bar("USD / min", p.series.sum_by_minute, C.a), line("Cumulative USD", p.series.cumulative, C.b, "y2"),
               rule(n, p.threshold.value, "Total " + op(p.threshold) + " USD", C.thr, "y2")],
    scales: { y: axis("USD / minute"), y2: axis("USD cumulative", { position: "right", grid: { drawOnChartArea: false } }) },
  }),
  tokens: (p, n) => ({
    stats: [["Input", fmt(p.summary.tokens_in) + " tokens"], ["Output", fmt(p.summary.tokens_out) + " tokens"]],
    datasets: [bar("Input / min", p.series.tokens_in, C.a), bar("Output / min", p.series.tokens_out, C.b),
               line("Cumulative input", p.series.cumulative_in, C.a, "y2", [2, 2]), line("Cumulative output", p.series.cumulative_out, C.b, "y2", [2, 2]),
               rule(n, p.threshold.value, "Per field " + op(p.threshold) + " tokens", C.thr, "y2")],
    scales: { y: axis("tokens / minute"), y2: axis("tokens cumulative", { position: "right", grid: { drawOnChartArea: false } }) },
  }),
  quality: (p, n) => ({
    stats: [["Mean", fmt(p.summary.mean, 3)]],
    datasets: [line("Mean quality", p.series.mean, C.ok), rule(n, p.threshold.value, "Min " + op(p.threshold))],
    scales: { y: axis("score (0–1)", { max: 1 }) },
  }),
};

function render(d) {
  document.title = d.title;
  document.getElementById("title").textContent = d.title;
  document.getElementById("range").textContent = "last " + d.time_range_minutes + " min (" + d.window[0] + "–" + d.window[1] + " " + d.timezone + ")";
  document.getElementById("refresh").textContent = d.refresh_seconds + " s";
  document.getElementById("records").textContent = d.records_in_window;
  document.getElementById("updated").textContent = d.generated_at;
  const grid = document.getElementById("grid");
  for (const id of ORDER) {
    const p = d.panels[id], spec = SPECS[id](p, d.labels.length, d);
    let el = document.getElementById("panel-" + id);
    if (!el) {
      el = document.createElement("section");
      el.className = "panel"; el.id = "panel-" + id;
      el.innerHTML = '<h2><span class="t"></span><span class="badge"></span></h2><div class="sub"></div>' +
                     '<div class="stats"></div><div class="chart"><canvas></canvas></div>';
      grid.appendChild(el);
    }
    el.querySelector(".t").textContent = p.title;
    const badge = el.querySelector(".badge");
    badge.className = "badge " + p.status;
    badge.textContent = { ok: "OK", breach: "BREACH", no_data: "NO DATA" }[p.status];
    el.querySelector(".sub").textContent = "Unit: " + p.unit + " · Threshold: " + p.threshold.aggregation + " " + op(p.threshold);
    el.querySelector(".stats").innerHTML = spec.stats.map(([k, v]) => k + ": <b>" + v + "</b>").join("");
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart(el.querySelector("canvas"), {
      type: "bar",
      data: { labels: d.labels, datasets: spec.datasets },
      options: { animation: false, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
                 plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
                 scales: { x: { ticks: { maxTicksLimit: 12, maxRotation: 0 } }, ...spec.scales } },
    });
  }
}

let timer;
async function load() {
  try {
    const d = await (await fetch("/api/metrics", { cache: "no-store" })).json();
    render(d);
    clearTimeout(timer);
    timer = setTimeout(load, d.refresh_seconds * 1000);
  } catch (e) {
    document.getElementById("updated").textContent = "lỗi tải dữ liệu: " + e;
    timer = setTimeout(load, 30000);
  }
}
load();
</script>
</body>
</html>
"""


class DashboardHandler(BaseHTTPRequestHandler):
    log_path: Path = DEFAULT_LOG
    config_path: Path = DEFAULT_CONFIG
    slo_path: Path = DEFAULT_SLO

    def do_GET(self) -> None:  # noqa: N802 - tên hàm do BaseHTTPRequestHandler quy định
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif path == "/api/metrics":
            data = snapshot(self.log_path, self.config_path, self.slo_path)
            self._send(200, "application/json", json.dumps(data, ensure_ascii=False).encode("utf-8"))
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        return None


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Dashboard 6 panel cho Day 13")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--summary", action="store_true", help="In số liệu rồi thoát, không chạy server")
    args = parser.parse_args()

    if args.summary:
        print_summary(snapshot(args.log, args.config, DEFAULT_SLO))
        return 0

    load_dashboard_config(args.config)  # báo lỗi contract ngay khi khởi động
    DashboardHandler.log_path, DashboardHandler.config_path = args.log, args.config
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard: http://127.0.0.1:{args.port}  (Ctrl+C để dừng)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
