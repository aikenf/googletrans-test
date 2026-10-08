import datetime
import html
import json
import os

def generate_heatmap_data(history, year=None):
    if year is None:
        year = datetime.datetime.now().year

    # Normalize history into a dict mapping date_str -> list of run entries
    history_by_date = {}
    if isinstance(history, list):
        for entry in history:
            d_str = entry.get("date")
            if not d_str and "timestamp" in entry:
                d_str = entry["timestamp"].split(" ")[0]
            if d_str:
                history_by_date.setdefault(d_str, []).append(entry)
    elif isinstance(history, dict):
        for k, v in history.items():
            if isinstance(v, list):
                history_by_date[k] = v
            else:
                entry = {"date": k}
                entry.update(v)
                history_by_date[k] = [entry]

    start_date = datetime.date(year, 1, 1)
    end_date = datetime.date(year, 12, 31)

    days_data = []
    curr = start_date
    while curr <= end_date:
        date_str = curr.strftime("%Y-%m-%d")
        runs = history_by_date.get(date_str, [])

        # Select the worst result for dates with multiple runs
        if runs:
            # Worst result ranking: max failed count, then min passed count
            record = max(runs, key=lambda x: (x.get("failed", 0), -x.get("passed", 0)))
        else:
            record = None

        # Status & Color logic:
        # Gray: not run
        # Green: all 20 (or more future) tests passed
        # Orange: 1 test failing
        # Red: 2 or more tests failing
        if not record:
            status = "not_run"
            color = "#2d333b"  # GitHub dark mode gray cell
            border_color = "#373e47"
            tooltip = f"{date_str}: No test runs"
        else:
            total = record.get("total", 0)
            passed = record.get("passed", 0)
            failed = record.get("failed", 0)
            rate_limit = record.get("rate_limit", 0)

            if failed == 0 and total >= 20:
                status = "passed_all"
                color = "#2e6f40"  # GitHub green / vibrant green (#39d353 or #2e6f40)
                border_color = "#39d353"
                tooltip = f"{date_str}: Passed ({passed}/{total} passed)"
            elif failed == 0: # all passed but fewer than 20
                status = "passed_all"
                color = "#2e6f40"
                border_color = "#39d353"
                tooltip = f"{date_str}: Passed ({passed}/{total} passed)"
            elif failed == 1:
                status = "failing_1"
                color = "#d97706"  # Orange
                border_color = "#f59e0b"
                tooltip = f"{date_str}: 1 test failing ({passed}/{total} passed, {rate_limit} rate limit)"
            else:
                status = "failing_multiple"
                color = "#da3633"  # Red
                border_color = "#f85149"
                tooltip = f"{date_str}: {failed} tests failing ({passed}/{total} passed, {rate_limit} rate limit)"

        sun_idx = (curr.weekday() + 1) % 7  # Sunday = 0
        days_data.append({
            "date": date_str,
            "day_obj": curr,
            "sun_idx": sun_idx,
            "record": record,
            "status": status,
            "color": color,
            "border_color": border_color,
            "tooltip": tooltip
        })
        curr += datetime.timedelta(days=1)

    return year, days_data

def generate_svg_heatmap(history, year=None):
    year, days = generate_heatmap_data(history, year)

    # Layout constants
    cell_size = 11
    cell_gap = 3
    left_padding = 35
    top_padding = 30

    # Calculate weeks
    # Week 0 starts with the week containing Jan 1
    # We can group by week index
    jan1 = datetime.date(year, 1, 1)
    jan1_sun_idx = (jan1.weekday() + 1) % 7

    svg_width = left_padding + 53 * (cell_size + cell_gap) + 20
    svg_height = top_padding + 7 * (cell_size + cell_gap) + 30

    # Month labels position
    months_labels = []
    current_month = None

    rects_svg = []
    for d in days:
        dt = d["day_obj"]
        # calculate column (week index)
        # number of days since first day of week 0
        first_sun = jan1 - datetime.timedelta(days=jan1_sun_idx)
        week_idx = (dt - first_sun).days // 7
        row_idx = d["sun_idx"]

        x = left_padding + week_idx * (cell_size + cell_gap)
        y = top_padding + row_idx * (cell_size + cell_gap)

        if dt.month != current_month:
            current_month = dt.month
            month_name = dt.strftime("%b")
            months_labels.append((x, month_name))

        safe_tooltip = html.escape(d["tooltip"])
        rects_svg.append(
            f'  <rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" ry="2" '
            f'fill="{d["color"]}" stroke="{d["border_color"]}" stroke-width="0.5">\n'
            f'    <title>{safe_tooltip}</title>\n'
            f'  </rect>'
        )

    month_svg_tags = []
    last_x = -100
    for x, m_name in months_labels:
        if x - last_x >= 25:  # avoid overlapping labels
            month_svg_tags.append(f'  <text x="{x}" y="{top_padding - 8}" class="month-label">{m_name}</text>')
            last_x = x

    day_labels = [("", 0), ("Mon", 1), ("", 2), ("Wed", 3), ("", 4), ("Fri", 5), ("", 6)]
    day_svg_tags = []
    for label, r_idx in day_labels:
        if label:
            y = top_padding + r_idx * (cell_size + cell_gap) + 9
            day_svg_tags.append(f'  <text x="5" y="{y}" class="day-label">{label}</text>')

    svg_code = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">
  <style>
    .bg {{ fill: #0d1117; rx: 8px; }}
    .title {{ fill: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; font-weight: 600; }}
    .month-label, .day-label {{ fill: #8b949e; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; }}
    .legend-text {{ fill: #8b949e; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; }}
    rect {{ cursor: pointer; transition: transform 0.1s; }}
    rect:hover {{ stroke: #ffffff; stroke-width: 1.5px; }}
  </style>
  <rect width="100%" height="100%" class="bg" />
  <text x="{left_padding}" y="18" class="title">Test Suite Execution Heatmap ({year})</text>
  {''.join(month_svg_tags)}
  {''.join(day_svg_tags)}
  {''.join(rects_svg)}

  <!-- Legend -->
  <g transform="translate({svg_width - 220}, {svg_height - 18})">
    <text x="0" y="10" class="legend-text">Less</text>
    <rect x="30" y="1" width="10" height="10" rx="2" fill="#2d333b" stroke="#373e47"><title>Gray: Not run</title></rect>
    <rect x="45" y="1" width="10" height="10" rx="2" fill="#2e6f40" stroke="#39d353"><title>Green: Passed all tests</title></rect>
    <rect x="60" y="1" width="10" height="10" rx="2" fill="#d97706" stroke="#f59e0b"><title>Orange: 1 test failing</title></rect>
    <rect x="75" y="1" width="10" height="10" rx="2" fill="#da3633" stroke="#f85149"><title>Red: 2+ tests failing</title></rect>
    <text x="92" y="10" class="legend-text">More</text>
  </g>
</svg>
"""
    return svg_code

def generate_html_heatmap(history, year=None):
    # HTML component with interactive CSS tooltips or SVG
    return generate_svg_heatmap(history, year)
