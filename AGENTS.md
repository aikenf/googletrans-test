# AGENTS.md

Welcome! This repository contains test suites, custom test report generators, and CI/CD automation for validating the Python `googletrans` library (version 4.0.2) - Version 1.0.3.

## Instructions for AI Agents & Developers

### Overview
`googletrans` is a free and unlimited Python library that implements the Google Translate API. Starting with version 4.0.0+, `googletrans` uses `httpx` internally and many methods (such as `Translator.translate` and `Translator.detect`) are **asynchronous coroutines**.

### Code Conventions & Guidelines
- **Asynchronous Execution:** Always call `Translator` methods within an async context (`await translator.translate(...)`) or wrap them in `asyncio.run(...)` when writing synchronous wrappers or tests.
- **Testing Requirements:** Tests are split into two independent test runners:
  1. `pytest` suite in `tests/test_pytest_suite.py`
  2. `unittest` suite in `tests/test_unittest_suite.py`
- **Error Handling:** Google Translate endpoints can return HTTP 429 (Too Many Requests) or JSON parsing errors when rate-limited. Test cases should gracefully handle rate limits when appropriate.

### Commands to Run Tests & Verification
- **Run Pytest Suite:**
  ```bash
  pytest tests/test_pytest_suite.py
  ```
- **Run Unittest Suite:**
  ```bash
  python -m unittest discover -s tests -p "test_unittest_*.py"
  ```
- **Generate Custom Test Report (Run tests & update history):**
  ```bash
  python generate_report.py
  ```
  This command executes both test suites and generates `public/index.html` for GitHub Pages deployment. It appends the run entry to `data/history.json` and updates `data/heatmap.svg`.
- **Render Dashboard from Existing History (Fast, no tests run):**
  ```bash
  python generate_report.py --skip-tests
  ```

### History Tracking & Heatmap Rules
- `data/history.json` is an appending JSON list of test execution records containing `date`, `timestamp`, `total`, `passed`, `failed`, `rate_limit`, and `trigger` ("scheduled" or "manually triggered").
- For dates with multiple run entries, `generate_heatmap.py` interprets the growing history by selecting the worst result (highest failure count / lowest pass count) for rendering that day's heatmap tile.

### Verification Checklist
Before committing any changes:
1. Ensure both `pytest` and `unittest` run cleanly without syntax errors.
2. Run `python generate_report.py` to confirm that `public/index.html` builds correctly.
3. Check that no sensitive tokens or environment variables are leaked.
