# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-10-10

### Changed
- **Decoupled CI/CD Workflows:** Separated automated test execution from push deployment to prevent slow builds and timeouts on pushes to `main`:
  - `.github/workflows/deploy-pages.yml`: Runs on `push` to `main`/`master` and quickly builds and publishes GitHub Pages using committed historical data via `python generate_report.py --skip-tests` without executing network test suites.
  - `.github/workflows/run-tests.yml`: Dedicated workflow for executing test suites, appending new results to `data/history.json`, updating `data/heatmap.svg`, and triggering deployments via daily schedule (`03:13 UTC`) or manual `workflow_dispatch`.
- **Fast Dashboard Generation Option:** Added `--skip-tests` CLI option to `generate_report.py` to allow rendering `public/index.html` and `data/heatmap.svg` directly from existing history data in milliseconds.

## [1.0.1] - 2026-10-10

### Fixed
- **Pytest Report Metadata Retention:** Pre-assigned `tested` and `expected` user properties prior to executing async requests so test details and expectations are preserved in the HTML report and `data/history.json` even when network or rate-limit errors occur.
- **Accurate Unittest Execution Timers:** Replaced hardcoded execution duration constants in `CustomResult` with high-resolution `time.perf_counter()` timers.
- **Cross-Language Fallback & Rate-Limit Detection:** Enhanced silent as-is fallback detection in both `test_pytest_suite.py` and `test_unittest_suite.py` to compare source and destination languages accurately across all pairings.
- **CI Push Reliability:** Updated `.github/workflows/deploy-pages.yml` with `git pull --rebase origin ${{ github.ref_name }}` before pushing to protect against concurrent push conflicts.

### Changed
- **Appending History File Format:** Converted `data/history.json` to a growing JSON list of execution records instead of overwriting history on each test run.
- **Trigger Type Classification:** Added explicit `trigger` attribute ("scheduled" vs "manually triggered") to history run records.
- **Heatmap Multi-Run Selection Logic:** Updated `generate_heatmap.py` to process list-based history records and select the worst result (highest failure count / lowest pass count) for dates with multiple test executions.
- **Documentation Alignment:** Updated directory tree in `README.md` to document `data/`, `public/`, and `generate_heatmap.py`.
- **Restored Historical Runs:** Restored historical contribution test execution records in `data/history.json`.

## [1.0.0] - 2026-10-07

### Added
- **Initial 1.0 Release:** Production-ready release of test suites and test dashboard for `googletrans` 4.0.2.
- **Test Suites:** Created comprehensive test cases for `googletrans` 4.0.2 covering:
  - Simple single-word and sentence translations.
  - Specific target/source language selections and language auto-detection (`detect`).
  - Batch string translations.
  - Complex scenarios including special characters, HTML tags, punctuation, long texts, and invalid language code handling.
- **Independent Test Frameworks:** Supported both `pytest` (`tests/test_pytest_suite.py`) and standard library `unittest` (`tests/test_unittest_suite.py`).
- **Custom HTML Test Report Generator:** Added `generate_report.py` to aggregate results from both `pytest` and `unittest` into an interactive `public/index.html` report with collapsible test run details and status badges ("passed", "failed", "Error 429 - rate limit").
- **GitHub Pages CI/CD Workflow:** Added `.github/workflows/deploy-pages.yml` utilizing modern GitHub Actions (`actions/upload-pages-artifact@v3` and `actions/deploy-pages@v4`) avoiding Node 20 deprecation warnings.
- **Documentation:** Added `AGENTS.md`, updated `README.md` with historical background/fixes, and created `pyproject.toml`, `requirements.txt`, and `pytest.ini`.

### Historical Issues & Fix Tracking
- **Async API Migration:** In `googletrans` v3.x, `Translator.translate` was synchronous. In v4.0.0rc1/v4.0.2, methods became async (`httpx` backend). Fixed by adding `async/await` and `pytest-asyncio` support.
- **AttributeError 'coroutine' object has no attribute 'text':** Occurred when calling `t.translate(...)` without `await` in v4.0.2. Documented and tested in both test runners.
- **Rate Limit (HTTP 429) & Token Generation Errors:** Historical issues with Google's web API blocking frequent requests without API keys. Added explicit status classification in report generator.
