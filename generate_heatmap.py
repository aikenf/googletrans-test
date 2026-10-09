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

        num_runs = len(runs)

        # Status & Color logic:
        # Gray: not covered
        # Green: all passed
        # Orange: one failed
        # Red: more than one failed
        if not record or num_runs == 0:
            status = "not_run"
            color = "#2d333b"  # GitHub dark mode gray cell
            border_color = "#373e47"
            tooltip = f"{date_str}: No test runs (not covered)"
        else:
            total = record.get("total", 0)
            passed = record.get("passed", 0)
            failed = record.get("failed", 0)
            rate_limit = record.get("rate_limit", 0)
            pass_ratio = (passed / total * 100) if total > 0 else 0.0

            runs_prefix = f"{num_runs} runs" if num_runs > 1 else "1 run"
            run_desc = f"Worst run: {passed}/{total} passed ({pass_ratio:.0f}% pass ratio)" if num_runs > 1 else f"{passed}/{total} passed ({pass_ratio:.0f}% pass ratio)"

            if failed == 0:
                status = "passed_all"
                color = "#2e6f40"  # Green
                border_color = "#39d353"
                tooltip = f"{date_str}: {runs_prefix} | {run_desc}"
            elif failed == 1:
                status = "failing_1"
                color = "#d97706"  # Orange
                border_color = "#f59e0b"
                tooltip = f"{date_str}: {runs_prefix} | {run_desc}, 1 failed ({rate_limit} rate limited)"
            else:
                status = "failing_multiple"
                color = "#da3633"  # Red
                border_color = "#f85149"
                tooltip = f"{date_str}: {runs_prefix} | {run_desc}, {failed} failed ({rate_limit} rate limited)"

        sun_idx = (curr.weekday() + 1) % 7  # Sunday = 0
        days_data.append({
            "date": date_str,
            "day_obj": curr,
            "sun_idx": sun_idx,
            "record": record,
            "num_runs": num_runs,
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
    top_padding = 50  # Increased top padding to prevent title / month label overlap

    jan1 = datetime.date(year, 1, 1)
    jan1_sun_idx = (jan1.weekday() + 1) % 7

    svg_width = left_padding + 53 * (cell_size + cell_gap) + 20
    svg_height = top_padding + 7 * (cell_size + cell_gap) + 40

    # Month labels position
    months_labels = []
    current_month = None

    rects_svg = []
    for d in days:
        dt = d["day_obj"]
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
        has_runs = "true" if d["num_runs"] > 0 else "false"
        rects_svg.append(
            f'  <rect class="heatmap-cell" data-date="{d["date"]}" data-has-runs="{has_runs}" '
            f'x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" ry="2" '
            f'fill="{d["color"]}" stroke="{d["border_color"]}" stroke-width="0.5">\n'
            f'    <title>{safe_tooltip}</title>\n'
            f'  </rect>'
        )

    month_svg_tags = []
    last_x = -100
    for x, m_name in months_labels:
        if x - last_x >= 25:  # avoid overlapping labels
            month_svg_tags.append(f'  <text x="{x}" y="{top_padding - 10}" class="month-label">{m_name}</text>')
            last_x = x

    day_labels = [("", 0), ("Mon", 1), ("", 2), ("Wed", 3), ("", 4), ("Fri", 5), ("", 6)]
    day_svg_tags = []
    for label, r_idx in day_labels:
        if label:
            y = top_padding + r_idx * (cell_size + cell_gap) + 9
            day_svg_tags.append(f'  <text x="5" y="{y}" class="day-label">{label}</text>')

    # Legend items with precise spacing
    # Box (10x10), space, label text, and gap before next item
    legend_y = svg_height - 18
    legend_items = [
        ("#2d333b", "#373e47", "not covered"),
        ("#2e6f40", "#39d353", "all passed"),
        ("#d97706", "#f59e0b", "one failed"),
        ("#da3633", "#f85149", "more than one failed")
    ]

    legend_svg_group = []
    start_x = left_padding
    curr_x = start_x
    for fill_c, stroke_c, text_l in legend_items:
        legend_svg_group.append(
            f'<rect x="{curr_x}" y="0" width="10" height="10" rx="2" fill="{fill_c}" stroke="{stroke_c}" stroke-width="0.5" />'
            f'<text x="{curr_x + 14}" y="9" class="legend-text">{text_l}</text>'
        )
        # 10px box + 4px gap + ~6px per char + 20px item margin
        approx_text_width = len(text_l) * 6 + 14 + 20
        curr_x += approx_text_width

    svg_code = f"""<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" preserveAspectRatio="xMidYMid meet">
  <style>
    .bg {{ fill: #0d1117; rx: 8px; }}
    .title {{ fill: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; font-weight: 600; }}
    .month-label, .day-label {{ fill: #8b949e; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; }}
    .legend-text {{ fill: #8b949e; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; }}
    .heatmap-cell {{ cursor: pointer; transition: transform 0.1s; }}
    .heatmap-cell:hover {{ stroke: #ffffff; stroke-width: 1.5px; }}
  </style>
  <rect width="100%" height="100%" class="bg" />
  <text x="{left_padding}" y="22" class="title">Test Suite Execution Heatmap ({year})</text>
  {''.join(month_svg_tags)}
  {''.join(day_svg_tags)}
  {''.join(rects_svg)}

  <!-- Legend -->
  <g transform="translate(0, {legend_y})">
    {''.join(legend_svg_group)}
  </g>
</svg>
"""
    return svg_code

def generate_html_heatmap(history, year=None):
    return generate_svg_heatmap(history, year)
