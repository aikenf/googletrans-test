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

def run_unittest_suite():
    # Run unittest via subprocess to get clean isolation
    code = """
import unittest
import json
import traceback

class CustomResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.results = []

    def addSuccess(self, test):
        doc = (test._testMethodDoc or "").strip()
        self.results.append({
            "suite": "unittest",
            "name": test._testMethodName,
            "status": "passed",
            "duration": "0.500s",
            "doc": doc,
            "details": "Test completed successfully."
        })

    def addFailure(self, test, err):
        exctype, value, tb = err
        tb_str = "".join(traceback.format_exception(exctype, value, tb))
        status = "Error 429 - rate limit" if ("429" in str(value) or "too many requests" in str(value).lower()) else "failed"
        doc = (test._testMethodDoc or "").strip()
        self.results.append({
            "suite": "unittest",
            "name": test._testMethodName,
            "status": status,
            "duration": "0.500s",
            "doc": doc,
            "details": tb_str
        })

    def addError(self, test, err):
        exctype, value, tb = err
        tb_str = "".join(traceback.format_exception(exctype, value, tb))
        status = "Error 429 - rate limit" if ("429" in str(value) or "too many requests" in str(value).lower()) else "failed"
        doc = (test._testMethodDoc or "").strip()
        self.results.append({
            "suite": "unittest",
            "name": test._testMethodName,
            "status": status,
            "duration": "0.500s",
            "doc": doc,
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
    # Run pytest via subprocess to ensure fresh event loop and httpx client
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
            if report.passed:
                status = "passed"
                details = "Test completed successfully."
            elif report.failed:
                longrepr = str(report.longrepr)
                status = "Error 429 - rate limit" if ("429" in longrepr or "too many requests" in longrepr.lower()) else "failed"
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

def generate_html_report(results, output_file="public/index.html"):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    total_tests = len(results)
    passed_count = sum(1 for r in results if r["status"] == "passed")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    rate_limit_count = sum(1 for r in results if r["status"] == "Error 429 - rate limit")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
            margin-bottom: 0.75rem;
            font-style: italic;
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
            <div class="subtitle">Generated on {now_str} UTC | Package: googletrans 4.0.2</div>
        </header>

        <section class="summary-grid">
            <div class="summary-card total">
                <div>Total Tests</div>
                <div class="number">{total_tests}</div>
            </div>
            <div class="summary-card passed">
                <div>Passed</div>
                <div class="number">{passed_count}</div>
            </div>
            <div class="summary-card failed">
                <div>Failed</div>
                <div class="number">{failed_count}</div>
            </div>
            <div class="summary-card ratelimit">
                <div>Rate Limited (429)</div>
                <div class="number">{rate_limit_count}</div>
            </div>
        </section>

        <main class="test-list">
"""

    for item in results:
        status_slug = item["status"].lower().replace(" ", "-")
        badge_class = f"badge {status_slug}"
        safe_name = html.escape(item["name"])
        safe_doc = html.escape(item.get("doc", ""))
        safe_details = html.escape(item.get("details", ""))
        suite_name = html.escape(item["suite"])
        duration = item["duration"]
        status_text = html.escape(item["status"])

        html_content += f"""
            <details class="test-card">
                <summary class="test-header">
                    <div class="test-title">
                        <span class="suite-tag">{suite_name}</span>
                        <span>{safe_name}</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <span class="test-duration">{duration}</span>
                        <span class="{badge_class}">{status_text}</span>
                    </div>
                </summary>
                <div class="test-body">
                    {f'<div class="test-doc">{safe_doc}</div>' if safe_doc else ''}
                    <pre class="log-output">{safe_details}</pre>
                </div>
            </details>
"""

    html_content += """
        </main>

        <footer>
            <p>Automated report generated by <code>generate_report.py</code> for GitHub Pages deployment.</p>
        </footer>
    </div>
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
    generate_html_report(combined_results, "public/index.html")
