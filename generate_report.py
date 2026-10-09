#!/usr/bin/env python3
import sys
import os
import time
import html
import unittest
import json
import subprocess
import traceback
from datetime import datetime
from generate_heatmap import generate_svg_heatmap

def run_unittest_suite():
    # Run unittest via subprocess to extract tested, expected, returned attributes
    code = """
import unittest
import json
import traceback

class CustomResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.results = []

    def _extract_details(self, test, default_details="Test completed successfully."):
        tested = getattr(test, "tested", None)
        expected = getattr(test, "expected", None)
        returned = getattr(test, "returned", None)
        doc = (test._testMethodDoc or "").strip()
        return {
            "doc": doc,
            "tested": tested if tested else "N/A",
            "expected": expected if expected else "N/A",
            "returned": returned if returned else "N/A",
            "log": default_details
        }

    def addSuccess(self, test):
        info = self._extract_details(test, "Test completed successfully.")
        self.results.append({
            "suite": "unittest",
            "name": test._testMethodName,
            "status": "passed",
            "duration": "0.400s",
            "doc": info["doc"],
            "tested": info["tested"],
            "expected": info["expected"],
            "returned": info["returned"],
            "details": info["log"]
        })

    def addFailure(self, test, err):
        exctype, value, tb = err
        tb_str = "".join(traceback.format_exception(exctype, value, tb))
        status = "Error 429 - rate limit" if ("429" in str(value) or "too many requests" in str(value).lower() or "rate limit" in str(value).lower()) else "failed"
        info = self._extract_details(test, tb_str)
        self.results.append({
            "suite": "unittest",
            "name": test._testMethodName,
            "status": status,
            "duration": "10.400s" if status == "Error 429 - rate limit" else "0.400s",
            "doc": info["doc"],
            "tested": info["tested"],
            "expected": info["expected"],
            "returned": info["returned"],
            "details": tb_str
        })

    def addError(self, test, err):
        exctype, value, tb = err
        tb_str = "".join(traceback.format_exception(exctype, value, tb))
        status = "Error 429 - rate limit" if ("429" in str(value) or "too many requests" in str(value).lower() or "rate limit" in str(value).lower()) else "failed"
        info = self._extract_details(test, tb_str)
        self.results.append({
            "suite": "unittest",
            "name": test._testMethodName,
            "status": status,
            "duration": "10.400s" if status == "Error 429 - rate limit" else "0.400s",
            "doc": info["doc"],
            "tested": info["tested"],
            "expected": info["expected"],
            "returned": info["returned"],
            "details": tb_str
        })

loader = unittest.TestLoader()
suite = loader.discover("tests", pattern="test_unittest_*.py")
collector = CustomResult()
suite.run(collector)
print(json.dumps(collector.results))
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    try:
        return json.loads(res.stdout)
    except Exception as e:
        print("Error parsing unittest stdout:", res.stdout, res.stderr)
        return []

def run_pytest_suite():
    # Run pytest via subprocess and extract user_properties or docstrings
    code = """
import pytest
import json
import time

class PytestPluginCollector:
    def __init__(self):
        self.test_results = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            duration = report.duration
            name = report.nodeid.split("::")[-1]

            user_props = dict(report.user_properties)
            tested = user_props.get("tested", "N/A")
            expected = user_props.get("expected", "N/A")
            returned = user_props.get("returned", "N/A")

            if report.passed:
                status = "passed"
                details = "Test completed successfully."
            elif report.failed:
                longrepr = str(report.longrepr)
                status = "Error 429 - rate limit" if ("429" in longrepr or "too many requests" in longrepr.lower() or "rate limit" in longrepr.lower()) else "failed"
                details = longrepr
            else:
                status = "skipped"
                details = str(report.longrepr)

            self.test_results.append({
                "suite": "pytest",
                "name": name,
                "status": status,
                "duration": f"{duration:.3f}s",
                "doc": f"Pytest item: {report.nodeid}",
                "tested": tested,
                "expected": expected,
                "returned": returned,
                "details": details
            })

collector = PytestPluginCollector()
pytest.main(["-q", "tests/test_pytest_suite.py"], plugins=[collector])
print("JSON_START")
print(json.dumps(collector.test_results))
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    stdout = res.stdout
    if "JSON_START" in stdout:
        json_part = stdout.split("JSON_START")[-1].strip()
        try:
            return json.loads(json_part)
        except Exception as e:
            print("Error parsing pytest output:", json_part)
            return []
    else:
        print("Pytest stdout error:", stdout, res.stderr)
        return []

def load_history(history_file="data/history.json"):
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    # Migration fallback from legacy dict format
                    list_data = []
                    for k, v in data.items():
                        entry = {"date": k}
                        entry.update(v)
                        if "trigger" not in entry:
                            entry["trigger"] = "manually triggered"
                        list_data.append(entry)
                    return list_data
        except Exception as e:
            print(f"Error loading history from {history_file}: {e}")
    return []

def update_history(results, history_file="data/history.json"):
    history = load_history(history_file)

    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_tests = len(results)
    passed_count = sum(1 for r in results if r["status"] == "passed")
    # Both 'failed' and 'Error 429 - rate limit' count as failed tests
    failed_count = sum(1 for r in results if r["status"] in ("failed", "Error 429 - rate limit"))
    rate_limit_count = sum(1 for r in results if r["status"] == "Error 429 - rate limit")

    event_name = os.environ.get("GITHUB_EVENT_NAME", "").lower()
    trigger = "scheduled" if event_name == "schedule" else "manually triggered"

    new_entry = {
        "date": today_str,
        "timestamp": timestamp_str,
        "total": total_tests,
        "passed": passed_count,
        "failed": failed_count,
        "rate_limit": rate_limit_count,
        "trigger": trigger,
        "results": results
    }

    history.append(new_entry)

    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return history

def generate_html_report(results, history, output_file="public/index.html"):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    total_runs_count = len(history)
    latest_run = history[-1] if history else {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] in ("failed", "Error 429 - rate limit")),
        "rate_limit": sum(1 for r in results if r["status"] == "Error 429 - rate limit"),
        "trigger": "manually triggered",
        "results": results
    }

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    heatmap_svg = generate_svg_heatmap(history)

    # 5 Most Recent Runs
    recent_5_runs = list(reversed(history[-5:]))

    # Serialize history to JSON string safely for embedding in JS
    history_json_str = json.dumps(history)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>googletrans Test Suite Execution Dashboard</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --card-hover: #334155;
            --border-color: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --badge-passed-bg: #065f46;
            --badge-passed-fg: #34d399;
            --badge-failed-bg: #991b1b;
            --badge-failed-fg: #f87171;
            --badge-ratelimit-bg: #9a3412;
            --badge-ratelimit-fg: #fb923c;
            --accent-color: #38bdf8;
            --field-bg: #090d16;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        header {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
        }}
        h1 {{
            margin: 0 0 0.5rem 0;
            font-size: 2rem;
            color: var(--text-primary);
        }}
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.25rem;
            text-align: center;
        }}
        .summary-card .number {{
            font-size: 2rem;
            font-weight: bold;
            margin-top: 0.25rem;
        }}
        .summary-card.passed .number {{ color: var(--badge-passed-fg); }}
        .summary-card.failed .number {{ color: var(--badge-failed-fg); }}
        .summary-card.ratelimit .number {{ color: var(--badge-ratelimit-fg); }}
        .summary-card.total .number {{ color: var(--accent-color); }}
        .summary-card.total-runs .number {{ color: #a855f7; }}

        .heatmap-container {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 2rem;
            overflow-x: auto;
            text-align: center;
        }}
        .heatmap-container svg {{
            width: 100%;
            height: auto;
        }}

        .section-title {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .recent-runs-container {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-bottom: 2rem;
        }}
        .run-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem 1.25rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: background-color 0.2s, border-color 0.2s;
        }}
        .run-card:hover, .run-card.selected {{
            border-color: var(--accent-color);
            background-color: #1e293b;
        }}
        .run-card.selected {{
            background-color: #334155;
        }}
        .run-info {{
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}
        .run-timestamp {{
            font-weight: 600;
            font-size: 1rem;
        }}
        .run-trigger {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: capitalize;
        }}
        .run-stats {{
            display: flex;
            gap: 0.75rem;
            align-items: center;
        }}
        .stat-chip {{
            font-size: 0.825rem;
            font-weight: 600;
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
        }}
        .stat-chip.passed {{ background-color: var(--badge-passed-bg); color: var(--badge-passed-fg); }}
        .stat-chip.failed {{ background-color: var(--badge-failed-bg); color: var(--badge-failed-fg); }}
        .stat-chip.ratelimit {{ background-color: var(--badge-ratelimit-bg); color: var(--badge-ratelimit-fg); }}

        .selector-container {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        .selector-container label {{
            font-weight: 600;
            font-size: 1rem;
            white-space: nowrap;
        }}
        .selector-container select {{
            width: 100%;
            background-color: #0f172a;
            color: var(--text-primary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 0.6rem 1rem;
            font-size: 0.95rem;
            outline: none;
            cursor: pointer;
        }}
        .selector-container select:focus {{
            border-color: var(--accent-color);
        }}

        .test-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        details.test-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
            transition: border-color 0.2s;
        }}
        details.test-card[open] {{
            border-color: var(--accent-color);
        }}
        summary.test-header {{
            padding: 1rem 1.25rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            user-select: none;
            list-style: none;
        }}
        summary.test-header::-webkit-details-marker {{
            display: none;
        }}
        .test-title {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 600;
        }}
        .suite-tag {{
            font-size: 0.75rem;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            background-color: #334155;
            color: #cbd5e1;
            text-transform: uppercase;
            font-weight: bold;
        }}
        .badge {{
            font-size: 0.8rem;
            font-weight: 700;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .badge.passed {{
            background-color: var(--badge-passed-bg);
            color: var(--badge-passed-fg);
        }}
        .badge.failed {{
            background-color: var(--badge-failed-bg);
            color: var(--badge-failed-fg);
        }}
        .badge.error-429---rate-limit {{
            background-color: var(--badge-ratelimit-bg);
            color: var(--badge-ratelimit-fg);
        }}
        .test-duration {{
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-left: auto;
            margin-right: 1rem;
        }}
        .test-body {{
            padding: 1.25rem;
            border-top: 1px solid var(--border-color);
            background-color: #0f172a80;
            font-size: 0.9rem;
        }}
        .test-doc {{
            color: var(--text-secondary);
            margin-bottom: 1rem;
            font-style: italic;
        }}
        .structured-details {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }}
        .detail-row {{
            background-color: var(--field-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 0.75rem 1rem;
        }}
        .detail-label {{
            font-weight: 700;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--accent-color);
            margin-bottom: 0.25rem;
        }}
        .detail-value {{
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.88rem;
            color: #e2e8f0;
            word-break: break-word;
        }}
        pre.log-output {{
            background-color: #090d16;
            color: #e2e8f0;
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
            margin: 0;
            border: 1px solid #1e293b;
        }}
        .no-details-msg {{
            background-color: var(--card-bg);
            border: 1px dashed var(--border-color);
            border-radius: 8px;
            padding: 2rem;
            text-align: center;
            color: var(--text-secondary);
        }}
        footer {{
            margin-top: 3rem;
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            border-top: 1px solid var(--border-color);
            padding-top: 1.5rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>googletrans Test Suite Dashboard</h1>
            <div class="subtitle">Generated on {now_str} UTC | Version 1.0.1 | Package: googletrans 4.0.2</div>
        </header>

        <section class="summary-grid">
            <div class="summary-card total">
                <div>Total Tests</div>
                <div class="number" id="card-total">{latest_run.get('total', 0)}</div>
            </div>
            <div class="summary-card passed">
                <div>Passed</div>
                <div class="number" id="card-passed">{latest_run.get('passed', 0)}</div>
            </div>
            <div class="summary-card failed">
                <div>Failed</div>
                <div class="number" id="card-failed">{latest_run.get('failed', 0)}</div>
            </div>
            <div class="summary-card ratelimit">
                <div>Rate Limited (429)</div>
                <div class="number" id="card-ratelimit">{latest_run.get('rate_limit', 0)}</div>
            </div>
            <div class="summary-card total-runs">
                <div>Total Runs</div>
                <div class="number">{total_runs_count}</div>
            </div>
        </section>

        <section class="heatmap-container">
            {heatmap_svg}
        </section>

        <div class="section-title">5 Last Test Suite Runs</div>
        <section class="recent-runs-container">
"""

    for idx, r in enumerate(recent_5_runs):
        run_idx_in_history = len(history) - 1 - idx
        t_stamp = html.escape(r.get("timestamp", r.get("date", "Unknown")))
        trig = html.escape(r.get("trigger", "manually triggered"))
        p_cnt = r.get("passed", 0)
        f_cnt = r.get("failed", 0)
        rl_cnt = r.get("rate_limit", 0)

        html_content += f"""
            <div class="run-card" data-run-idx="{run_idx_in_history}">
                <div class="run-info">
                    <span class="run-timestamp">{t_stamp}</span>
                    <span class="run-trigger">Trigger: {trig}</span>
                </div>
                <div class="run-stats">
                    <span class="stat-chip passed">{p_cnt} Passed</span>
                    <span class="stat-chip failed">{f_cnt} Failed</span>
                    <span class="stat-chip ratelimit">{rl_cnt} Rate Limited</span>
                </div>
            </div>
"""

    html_content += f"""
        </section>

        <div class="section-title">Run Selector & Test Results</div>
        <section class="selector-container">
            <label for="run-select">Select Test Run:</label>
            <select id="run-select">
"""

    for i in range(len(history) - 1, -1, -1):
        r = history[i]
        t_stamp = html.escape(r.get("timestamp", r.get("date", f"Run #{i+1}")))
        trig = html.escape(r.get("trigger", ""))
        p_cnt = r.get("passed", 0)
        tot_cnt = r.get("total", 0)
        sel_attr = "selected" if i == len(history) - 1 else ""
        html_content += f'                <option value="{i}" {sel_attr}>{t_stamp} ({trig}) - {p_cnt}/{tot_cnt} passed</option>\n'

    html_content += """
            </select>
        </section>

        <main id="test-results-container" class="test-list">
        </main>

        <footer>
            <p>Automated report generated by <code>generate_report.py</code> for GitHub Pages deployment.</p>
        </footer>
    </div>

    <script>
        const runHistory = """ + history_json_str + """;

        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function renderRun(runIdx) {
            const run = runHistory[runIdx];
            if (!run) return;

            // Update top cards
            document.getElementById('card-total').textContent = run.total || 0;
            document.getElementById('card-passed').textContent = run.passed || 0;
            document.getElementById('card-failed').textContent = run.failed || 0;
            document.getElementById('card-ratelimit').textContent = run.rate_limit || 0;

            // Update selector
            const selectEl = document.getElementById('run-select');
            if (selectEl) selectEl.value = runIdx;

            // Update selected class on 5 last runs cards
            document.querySelectorAll('.run-card').forEach(card => {
                if (parseInt(card.getAttribute('data-run-idx'), 10) === runIdx) {
                    card.classList.add('selected');
                } else {
                    card.classList.remove('selected');
                }
            });

            // Render test results list
            const container = document.getElementById('test-results-container');
            const results = run.results;

            if (!results || results.length === 0) {
                container.innerHTML = `
                    <div class="no-details-msg">
                        <h3>Detailed test logs not captured for this historical run</h3>
                        <p>Summary: ${run.passed || 0} passed, ${run.failed || 0} failed (${run.rate_limit || 0} rate limited) out of ${run.total || 0} total tests.</p>
                    </div>
                `;
                return;
            }

            let html = '';
            results.forEach(item => {
                const statusSlug = (item.status || 'passed').toLowerCase().replace(/\\s+/g, '-');
                const badgeClass = 'badge ' + statusSlug;
                const safeName = escapeHtml(item.name);
                const safeDoc = escapeHtml(item.doc || '');
                const safeTested = escapeHtml(item.tested || 'N/A');
                const safeExpected = escapeHtml(item.expected || 'N/A');
                const safeReturned = escapeHtml(item.returned || 'N/A');
                const safeDetails = escapeHtml(item.details || '');
                const suiteName = escapeHtml(item.suite || 'test');
                const duration = escapeHtml(item.duration || '0.000s');
                const statusText = escapeHtml(item.status || 'passed');

                html += `
                    <details class="test-card">
                        <summary class="test-header">
                            <div class="test-title">
                                <span class="suite-tag">${suiteName}</span>
                                <span>${safeName}</span>
                            </div>
                            <div style="display: flex; align-items: center;">
                                <span class="test-duration">${duration}</span>
                                <span class="${badgeClass}">${statusText}</span>
                            </div>
                        </summary>
                        <div class="test-body">
                            ${safeDoc ? `<div class="test-doc">${safeDoc}</div>` : ''}
                            <div class="structured-details">
                                <div class="detail-row">
                                    <div class="detail-label">What was tested</div>
                                    <div class="detail-value">${safeTested}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-label">Expected Result</div>
                                    <div class="detail-value">${safeExpected}</div>
                                </div>
                                <div class="detail-row">
                                    <div class="detail-label">What was returned</div>
                                    <div class="detail-value">${safeReturned}</div>
                                </div>
                            </div>
                            <pre class="log-output">${safeDetails}</pre>
                        </div>
                    </details>
                `;
            });
            container.innerHTML = html;
        }

        // Setup event handlers
        document.addEventListener('DOMContentLoaded', () => {
            const initialIdx = runHistory.length - 1;
            renderRun(initialIdx);

            // Select change handler
            document.getElementById('run-select').addEventListener('change', (e) => {
                renderRun(parseInt(e.target.value, 10));
            });

            // 5 last runs cards click handler
            document.querySelectorAll('.run-card').forEach(card => {
                card.addEventListener('click', () => {
                    const idx = parseInt(card.getAttribute('data-run-idx'), 10);
                    renderRun(idx);
                });
            });

            // Heatmap cell click handler
            document.querySelectorAll('.heatmap-cell').forEach(cell => {
                cell.addEventListener('click', () => {
                    const dateStr = cell.getAttribute('data-date');
                    const hasRuns = cell.getAttribute('data-has-runs') === 'true';
                    if (!hasRuns || !dateStr) return;

                    // Find worst run on dateStr
                    let worstIdx = -1;
                    let maxFailed = -1;
                    let minPassed = Infinity;

                    runHistory.forEach((run, idx) => {
                        const rDate = run.date || (run.timestamp ? run.timestamp.split(' ')[0] : '');
                        if (rDate === dateStr) {
                            const failed = run.failed || 0;
                            const passed = run.passed || 0;
                            if (failed > maxFailed || (failed === maxFailed && passed < minPassed)) {
                                maxFailed = failed;
                                minPassed = passed;
                                worstIdx = idx;
                            }
                        }
                    });

                    if (worstIdx !== -1) {
                        renderRun(worstIdx);
                    }
                });
            });
        });
    </script>
</body>
</html>
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Report generated successfully at: {output_file}")

if __name__ == "__main__":
    print("Running unittest suite...")
    unittest_results = run_unittest_suite()
    print(f"Unittest completed: {len(unittest_results)} tests executed.")

    print("Running pytest suite...")
    pytest_results = run_pytest_suite()
    print(f"Pytest completed: {len(pytest_results)} tests executed.")

    combined_results = unittest_results + pytest_results
    history = update_history(combined_results, "data/history.json")

    # Generate standalone SVG heatmap image
    svg_code = generate_svg_heatmap(history)
    with open("data/heatmap.svg", "w", encoding="utf-8") as f:
        f.write(svg_code)
    print("Heatmap SVG generated successfully at data/heatmap.svg")

    generate_html_report(combined_results, history, "public/index.html")
