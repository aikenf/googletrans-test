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
import re
from generate_heatmap import generate_svg_heatmap, generate_hourly_svg_heatmap

def sanitize_details(text):
    if not text:
        return "Test completed successfully."
    cleaned = text
    # Normalize File ".../tests/..." references
    cleaned = re.sub(r'File \"[^\"]*?[/\\\\]tests[/\\\\](test_[^\\\"]+)\"', r'File "tests/\1"', cleaned)
    # Normalize pytest error lines like ".../tests/test_pytest_suite.py:176: Failed"
    cleaned = re.sub(r'/[^\s:\"]+[/\\\\]tests[/\\\\](test_[^:\s\"]+)', r'tests/\1', cleaned)
    # Generic replacement of user home directories & workspace paths
    cleaned = re.sub(r'/(?:home|Users)/[^/\s]+/(?:[^/\s]+/)*tests/', 'tests/', cleaned)
    cleaned = re.sub(r'/opt/hostedtoolcache/[^/\s]+/[^/\s]+/[^/\s]+/lib/[^/\s]+/', '<python-lib>/', cleaned)
    cleaned = re.sub(r'/usr/lib/python[^/\s]+/', '<python-lib>/', cleaned)
    cleaned = re.sub(r'/home/[^/\s]+/\.pyenv/[^/\s]+/[^/\s]+/lib/[^/\s]+/', '<python-lib>/', cleaned)
    cleaned = re.sub(r'/app/tests/', 'tests/', cleaned)
    cleaned = re.sub(r'/(?:home|Users)/[^/\s]+', '~', cleaned)
    return cleaned

def run_unittest_suite():
    # Run unittest via subprocess to extract tested, expected, returned attributes
    code = """
import unittest
import json
import traceback
import time

class CustomResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.results = []
        self._start_times = {}

    def startTest(self, test):
        super().startTest(test)
        self._start_times[test.id()] = time.perf_counter()

    def _get_duration_str(self, test):
        start = self._start_times.get(test.id())
        if start is not None:
            elapsed = time.perf_counter() - start
            return f"{elapsed:.3f}s"
        return "0.000s"

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
            "duration": self._get_duration_str(test),
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
            "duration": self._get_duration_str(test),
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
            "duration": self._get_duration_str(test),
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
                    for entry in data:
                        for r in entry.get("results", []):
                            if "details" in r:
                                r["details"] = sanitize_details(r["details"])
                    return data
                elif isinstance(data, dict):
                    # Migration fallback from legacy dict format
                    list_data = []
                    for k, v in data.items():
                        entry = {"date": k}
                        entry.update(v)
                        if "trigger" not in entry:
                            entry["trigger"] = "manually triggered"
                        for r in entry.get("results", []):
                            if "details" in r:
                                r["details"] = sanitize_details(r["details"])
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

    sanitized_results = []
    for r in results:
        r_copy = dict(r)
        if "details" in r_copy:
            r_copy["details"] = sanitize_details(r_copy["details"])
        sanitized_results.append(r_copy)

    new_entry = {
        "date": today_str,
        "timestamp": timestamp_str,
        "total": total_tests,
        "passed": passed_count,
        "failed": failed_count,
        "rate_limit": rate_limit_count,
        "trigger": trigger,
        "results": sanitized_results
    }

    history.append(new_entry)

    os.makedirs(os.path.dirname(history_file) or ".", exist_ok=True)
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return history

def generate_html_report(results=None, history=None, output_file="public/index.html"):
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    if history is None:
        history = load_history("data/history.json")

    total_runs_count = len(history)
    latest_run = history[-1] if history else {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results) if results else 0,
        "passed": sum(1 for r in results if r["status"] == "passed") if results else 0,
        "failed": sum(1 for r in results if r["status"] in ("failed", "Error 429 - rate limit")) if results else 0,
        "rate_limit": sum(1 for r in results if r["status"] == "Error 429 - rate limit") if results else 0,
        "trigger": "manually triggered",
        "results": results or []
    }

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    heatmap_dark_svg = generate_svg_heatmap(history, theme="dark")
    heatmap_light_svg = generate_svg_heatmap(history, theme="light")
    hourly_heatmap_dark_svg = generate_hourly_svg_heatmap(history, theme="dark")
    hourly_heatmap_light_svg = generate_hourly_svg_heatmap(history, theme="light")

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
    <script>
        (function() {{
            var theme = localStorage.getItem('theme');
            if (theme === 'light' || (!theme && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches)) {{
                document.documentElement.setAttribute('data-theme', 'light');
            }} else {{
                document.documentElement.setAttribute('data-theme', 'dark');
            }}
        }})();
    </script>
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
            --test-body-bg: #0f172a80;
            --select-bg: #0f172a;
            --log-bg: #090d16;
            --log-fg: #e2e8f0;
            --log-border: #1e293b;
            --log-clean-bg: #041a12;
            --log-clean-fg: #86efac;
            --log-clean-border: #064e3b;
            --subtext-bg: rgba(255, 255, 255, 0.05);
            --subtext-color: #94a3b8;
            --total-runs-num: #c084fc;
            --total-runs-subtext-bg: rgba(192, 132, 252, 0.15);
            --total-runs-subtext-fg: #d8b4fe;
            --version-pill-bg: #3b82f620;
            --version-pill-fg: #60a5fa;
            --version-pill-border: #3b82f640;
            --suite-tag-bg: #334155;
            --suite-tag-fg: #cbd5e1;
            --diagnostic-passed-bg: #064e3b40;
            --diagnostic-passed-fg: #34d399;
            --diagnostic-passed-border: #05966950;
            --diagnostic-failed-bg: #7f1d1d40;
            --diagnostic-failed-fg: #f87171;
            --diagnostic-failed-border: #dc262650;
            --diagnostic-ratelimit-bg: #7c2d1240;
            --diagnostic-ratelimit-fg: #fb923c;
            --diagnostic-ratelimit-border: #ea580c50;
            --btn-bg: #1e293b;
            --btn-hover: #334155;
            --btn-border: #334155;
            --btn-text: #f8fafc;
        }}
        [data-theme="light"] {{
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --card-hover: #f1f5f9;
            --border-color: #e2e8f0;
            --text-primary: #0f172a;
            --text-secondary: #64748b;
            --badge-passed-bg: #dcfce7;
            --badge-passed-fg: #15803d;
            --badge-failed-bg: #fee2e2;
            --badge-failed-fg: #b91c1c;
            --badge-ratelimit-bg: #ffedd5;
            --badge-ratelimit-fg: #c2410c;
            --accent-color: #0284c7;
            --field-bg: #f8fafc;
            --test-body-bg: #f8fafc;
            --select-bg: #ffffff;
            --log-bg: #f8fafc;
            --log-fg: #1e293b;
            --log-border: #cbd5e1;
            --log-clean-bg: #f0fdf4;
            --log-clean-fg: #15803d;
            --log-clean-border: #bbf7d0;
            --subtext-bg: rgba(0, 0, 0, 0.05);
            --subtext-color: #64748b;
            --total-runs-num: #7c3aed;
            --total-runs-subtext-bg: rgba(124, 58, 237, 0.1);
            --total-runs-subtext-fg: #6d28d9;
            --version-pill-bg: #eff6ff;
            --version-pill-fg: #2563eb;
            --version-pill-border: #bfdbfe;
            --suite-tag-bg: #e2e8f0;
            --suite-tag-fg: #334155;
            --diagnostic-passed-bg: #ecfdf5;
            --diagnostic-passed-fg: #047857;
            --diagnostic-passed-border: #a7f3d0;
            --diagnostic-failed-bg: #fef2f2;
            --diagnostic-failed-fg: #b91c1c;
            --diagnostic-failed-border: #fecaca;
            --diagnostic-ratelimit-bg: #fff7ed;
            --diagnostic-ratelimit-fg: #c2410c;
            --diagnostic-ratelimit-border: #fed7aa;
            --btn-bg: #ffffff;
            --btn-hover: #f1f5f9;
            --btn-border: #cbd5e1;
            --btn-text: #0f172a;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 2rem;
            line-height: 1.5;
            transition: background-color 0.2s ease, color 0.2s ease;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}
        header {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1.5rem;
            flex-wrap: wrap;
        }}
        .header-info {{
            flex: 1;
            min-width: 280px;
        }}
        .theme-toggle-btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.45rem 0.95rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            cursor: pointer;
            border: 1px solid var(--btn-border);
            background-color: var(--btn-bg);
            color: var(--btn-text);
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            transition: all 0.2s ease;
            user-select: none;
        }}
        .theme-toggle-btn:hover {{
            border-color: var(--accent-color);
            background-color: var(--btn-hover);
            transform: translateY(-1px);
        }}
        .theme-toggle-btn:active {{
            transform: translateY(0);
        }}
        .theme-icon {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
        }}
        .theme-icon svg {{
            width: 16px;
            height: 16px;
        }}
        h1 {{
            margin: 0 0 0.5rem 0;
            font-size: 2rem;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}
        .version-pill {{
            font-size: 0.95rem;
            font-weight: 600;
            padding: 0.2rem 0.65rem;
            border-radius: 9999px;
            background-color: var(--version-pill-bg);
            color: var(--version-pill-fg);
            border: 1px solid var(--version-pill-border);
            letter-spacing: 0.02em;
        }}
        .subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .summary-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1.25rem 1rem;
            text-align: center;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }}
        .summary-card .card-title {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .summary-card .number {{
            font-size: 2.25rem;
            font-weight: 700;
            line-height: 1.2;
            margin-top: 0.35rem;
        }}
        .summary-card .card-subtext {{
            font-size: 0.725rem;
            margin-top: 0.35rem;
            padding: 0.15rem 0.45rem;
            border-radius: 4px;
            background-color: rgba(255, 255, 255, 0.05);
            color: var(--text-secondary);
            font-weight: 500;
        }}
        .summary-card.total-runs .number {{ color: var(--total-runs-num); }}
        .summary-card.total-runs .card-subtext {{ color: var(--total-runs-subtext-fg); background-color: var(--total-runs-subtext-bg); }}
        .summary-card.total .number {{ color: var(--accent-color); }}
        .summary-card.passed .number {{ color: var(--badge-passed-fg); }}
        .summary-card.failed .number {{ color: var(--badge-failed-fg); }}
        .summary-card.ratelimit .number {{ color: var(--badge-ratelimit-fg); }}

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
        :root:not([data-theme="light"]) .heatmap-light,
        [data-theme="dark"] .heatmap-light {{
            display: none !important;
        }}
        :root:not([data-theme="light"]) .heatmap-dark,
        [data-theme="dark"] .heatmap-dark {{
            display: block !important;
        }}
        [data-theme="light"] .heatmap-dark {{
            display: none !important;
        }}
        [data-theme="light"] .heatmap-light {{
            display: block !important;
        }}
        .heatmap-dark svg .bg {{
            fill: #0d1117 !important;
        }}
        .heatmap-dark svg .title {{
            fill: #c9d1d9 !important;
        }}
        .heatmap-dark svg .month-label,
        .heatmap-dark svg .day-label,
        .heatmap-dark svg .legend-text {{
            fill: #8b949e !important;
        }}
        .heatmap-light svg .bg {{
            fill: #ffffff !important;
        }}
        .heatmap-light svg .title {{
            fill: #1f2328 !important;
        }}
        .heatmap-light svg .month-label,
        .heatmap-light svg .day-label,
        .heatmap-light svg .legend-text {{
            fill: #656d76 !important;
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
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .run-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 0.75rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .run-card:hover {{
            border-color: var(--accent-color);
            background-color: var(--card-hover);
            transform: translateY(-2px);
        }}
        .run-card.selected {{
            border-color: var(--accent-color);
            background-color: var(--card-hover);
            box-shadow: 0 0 0 1px var(--accent-color);
        }}
        .run-info {{
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }}
        .run-timestamp {{
            font-weight: 600;
            font-size: 0.925rem;
            color: var(--text-primary);
            line-height: 1.3;
        }}
        .run-trigger {{
            font-size: 0.725rem;
            color: var(--text-secondary);
            text-transform: capitalize;
        }}
        .run-stats {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            align-items: center;
        }}
        .stat-chip {{
            font-size: 0.75rem;
            font-weight: 600;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            line-height: 1.2;
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
            background-color: var(--select-bg);
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
            background-color: var(--suite-tag-bg);
            color: var(--suite-tag-fg);
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
            background-color: var(--test-body-bg);
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
            color: var(--text-primary);
            word-break: break-word;
        }}
        pre.log-output {{
            background-color: var(--log-bg);
            color: var(--log-fg);
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
            margin: 0;
            border: 1px solid var(--log-border);
            line-height: 1.45;
        }}
        pre.log-output.clean {{
            color: var(--log-clean-fg);
            background-color: var(--log-clean-bg);
            border-color: var(--log-clean-border);
        }}
        .diagnostic-banner {{
            padding: 0.75rem 1rem;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .diagnostic-banner.passed {{
            background-color: var(--diagnostic-passed-bg);
            color: var(--diagnostic-passed-fg);
            border: 1px solid var(--diagnostic-passed-border);
        }}
        .diagnostic-banner.failed {{
            background-color: var(--diagnostic-failed-bg);
            color: var(--diagnostic-failed-fg);
            border: 1px solid var(--diagnostic-failed-border);
        }}
        .diagnostic-banner.ratelimit {{
            background-color: var(--diagnostic-ratelimit-bg);
            color: var(--diagnostic-ratelimit-fg);
            border: 1px solid var(--diagnostic-ratelimit-border);
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
            <div class="header-info">
                <h1>googletrans Test Suite Dashboard <span class="version-pill">v1.0.5</span></h1>
                <div class="subtitle">Generated on {now_str} UTC | Package: googletrans 4.0.2</div>
            </div>
            <div class="header-actions">
                <button id="theme-toggle" class="theme-toggle-btn" type="button" aria-label="Toggle color theme" title="Toggle color theme">
                    <span class="theme-icon">
                        <svg class="sun-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display: none;"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>
                        <svg class="moon-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
                    </span>
                    <span id="theme-label">Dark</span>
                </button>
            </div>
        </header>

        <section class="summary-grid">
            <div class="summary-card total-runs">
                <div class="card-title">Total Runs</div>
                <div class="number">{total_runs_count}</div>
                <div class="card-subtext">All-time historical</div>
            </div>
            <div class="summary-card total">
                <div class="card-title">Total Tests</div>
                <div class="number" id="card-total">{latest_run.get('total', 0)}</div>
                <div class="card-subtext">Selected run</div>
            </div>
            <div class="summary-card passed">
                <div class="card-title">Passed</div>
                <div class="number" id="card-passed">{latest_run.get('passed', 0)}</div>
                <div class="card-subtext">Selected run</div>
            </div>
            <div class="summary-card failed">
                <div class="card-title">Failed</div>
                <div class="number" id="card-failed">{latest_run.get('failed', 0)}</div>
                <div class="card-subtext">Selected run</div>
            </div>
            <div class="summary-card ratelimit">
                <div class="card-title">Rate Limited (429)</div>
                <div class="number" id="card-ratelimit">{latest_run.get('rate_limit', 0)}</div>
                <div class="card-subtext">Selected run</div>
            </div>
        </section>

        <section class="heatmap-container heatmap-dark">
            {heatmap_dark_svg}
        </section>
        <section class="heatmap-container heatmap-light">
            {heatmap_light_svg}
        </section>

        <section class="heatmap-container heatmap-dark">
            {hourly_heatmap_dark_svg}
        </section>
        <section class="heatmap-container heatmap-light">
            {hourly_heatmap_light_svg}
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

                let bannerHtml = '';
                let logClass = 'log-output';
                if (item.status === 'passed') {
                    bannerHtml = '<div class="diagnostic-banner passed">✓ Verification Passed: Assertion and return value matched expected criteria.</div>';
                    logClass = 'log-output clean';
                } else if (item.status === 'Error 429 - rate limit') {
                    bannerHtml = '<div class="diagnostic-banner ratelimit">⚠️ Rate Limited (HTTP 429 / As-Is Fallback): Google Translate blocked or throttled this request.</div>';
                } else {
                    bannerHtml = '<div class="diagnostic-banner failed">✗ Test Assertion Failed: Return value did not meet expected criteria.</div>';
                }

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
                            ${bannerHtml}
                            <pre class="${logClass}">${safeDetails}</pre>
                        </div>
                    </details>
                `;
            });
            container.innerHTML = html;
        }

        // Setup event handlers
        document.addEventListener('DOMContentLoaded', () => {
            // Theme toggle logic
            const themeToggleBtn = document.getElementById('theme-toggle');
            const sunIcon = themeToggleBtn ? themeToggleBtn.querySelector('.sun-icon') : null;
            const moonIcon = themeToggleBtn ? themeToggleBtn.querySelector('.moon-icon') : null;
            const themeLabel = document.getElementById('theme-label');

            function updateTheme(theme) {
                if (theme === 'light') {
                    document.documentElement.setAttribute('data-theme', 'light');
                    localStorage.setItem('theme', 'light');
                    if (sunIcon) sunIcon.style.display = 'block';
                    if (moonIcon) moonIcon.style.display = 'none';
                    if (themeLabel) themeLabel.textContent = 'Light';
                    if (themeToggleBtn) {
                        themeToggleBtn.setAttribute('title', 'Switch to Dark mode');
                        themeToggleBtn.setAttribute('aria-label', 'Switch to Dark mode');
                    }
                } else {
                    document.documentElement.setAttribute('data-theme', 'dark');
                    localStorage.setItem('theme', 'dark');
                    if (sunIcon) sunIcon.style.display = 'none';
                    if (moonIcon) moonIcon.style.display = 'block';
                    if (themeLabel) themeLabel.textContent = 'Dark';
                    if (themeToggleBtn) {
                        themeToggleBtn.setAttribute('title', 'Switch to Light mode');
                        themeToggleBtn.setAttribute('aria-label', 'Switch to Light mode');
                    }
                }
            }

            const activeTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            updateTheme(activeTheme);

            if (themeToggleBtn) {
                themeToggleBtn.addEventListener('click', () => {
                    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
                    updateTheme(currentTheme === 'light' ? 'dark' : 'light');
                });
            }

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

                    const hourAttr = cell.getAttribute('data-hour');
                    const targetHour = hourAttr !== null ? parseInt(hourAttr, 10) : null;

                    // Find worst run on dateStr (and targetHour if specified)
                    let worstIdx = -1;
                    let maxFailed = -1;
                    let minPassed = Infinity;

                    runHistory.forEach((run, idx) => {
                        const rDate = run.date || (run.timestamp ? run.timestamp.split(' ')[0] : '');
                        if (rDate === dateStr) {
                            if (targetHour !== null) {
                                let rHour = null;
                                if (run.timestamp) {
                                    const parts = run.timestamp.split(' ');
                                    if (parts.length > 1) {
                                        rHour = parseInt(parts[1].split(':')[0], 10);
                                    } else if (run.timestamp.includes('T')) {
                                        rHour = parseInt(run.timestamp.split('T')[1].split(':')[0], 10);
                                    }
                                }
                                if (rHour !== targetHour) {
                                    return;
                                }
                            }
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

def save_heatmap_assets(history):
    dark_svg = generate_svg_heatmap(history, theme="dark")
    light_svg = generate_svg_heatmap(history, theme="light")
    hourly_dark_svg = generate_hourly_svg_heatmap(history, theme="dark")
    hourly_light_svg = generate_hourly_svg_heatmap(history, theme="light")

    with open("data/heatmap_dark.svg", "w", encoding="utf-8") as f:
        f.write(dark_svg)
    with open("data/heatmap_light.svg", "w", encoding="utf-8") as f:
        f.write(light_svg)
    with open("data/heatmap.svg", "w", encoding="utf-8") as f:
        f.write(dark_svg)

    with open("data/hourly_heatmap_dark.svg", "w", encoding="utf-8") as f:
        f.write(hourly_dark_svg)
    with open("data/hourly_heatmap_light.svg", "w", encoding="utf-8") as f:
        f.write(hourly_light_svg)
    with open("data/hourly_heatmap.svg", "w", encoding="utf-8") as f:
        f.write(hourly_dark_svg)

    print("Heatmap SVGs (dark & light) generated successfully in data/")

if __name__ == "__main__":
    if "--skip-tests" in sys.argv:
        print("Skipping tests (--skip-tests). Rendering dashboard from existing history...")
        history = load_history("data/history.json")
        save_heatmap_assets(history)
        generate_html_report(history=history, output_file="public/index.html")
    else:
        print("Running unittest suite...")
        unittest_results = run_unittest_suite()
        print(f"Unittest completed: {len(unittest_results)} tests executed.")

        print("Running pytest suite...")
        pytest_results = run_pytest_suite()
        print(f"Pytest completed: {len(pytest_results)} tests executed.")

        combined_results = unittest_results + pytest_results
        history = update_history(combined_results, "data/history.json")
        save_heatmap_assets(history)
        generate_html_report(combined_results, history, "public/index.html")
