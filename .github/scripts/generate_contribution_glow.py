#!/usr/bin/env python3
"""Generate an animated SVG from a GitHub contribution calendar."""

import html
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            contributionLevel
            date
            weekday
          }
        }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def fetch_calendar(username: str, token: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"login": username}}).encode()
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "contribution-glow-generator",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)

    if result.get("errors"):
        raise RuntimeError(result["errors"])
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user {username!r} was not found")
    return user["contributionsCollection"]["contributionCalendar"]


def render_svg(calendar: dict) -> str:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    width = max(860, 55 + len(weeks) * 15)
    cells = []
    labels = []
    previous_month = None

    for week_index, week in enumerate(weeks):
        days = week["contributionDays"]
        if days:
            current = date.fromisoformat(days[0]["date"])
            if current.month != previous_month and current.day <= 7:
                labels.append(
                    f'<text class="label month" x="{47 + week_index * 15}" y="42">{MONTHS[current.month - 1]}</text>'
                )
                previous_month = current.month

        for day in days:
            count = day["contributionCount"]
            level = LEVELS[day["contributionLevel"]]
            x = 47 + week_index * 15
            y = 52 + day["weekday"] * 15
            delay = -((week_index * 7 + day["weekday"]) % 48) * 0.09
            active = " active" if count else ""
            title = html.escape(f'{day["date"]}: {count} contribution{"s" if count != 1 else ""}')
            cells.append(
                f'<rect class="cell level-{level}{active}" x="{x}" y="{y}" width="11" height="11" '
                f'rx="2" style="--delay:{delay:.2f}s"><title>{title}</title></rect>'
            )

    day_labels = "".join(
        f'<text class="label" x="7" y="{61 + weekday * 15}">{name}</text>'
        for weekday, name in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="180" viewBox="0 0 {width} 180" role="img" aria-labelledby="title desc">
  <title id="title">Animated GitHub contribution graph</title>
  <desc id="desc">{total} contributions in the last year. Active days glow in a continuous wave.</desc>
  <defs>
    <filter id="glow" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="2.4" result="blur" />
      <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
    </filter>
  </defs>
  <style>
    :root {{ color-scheme: light dark; }}
    .background {{ fill: #ffffff; }}
    .heading {{ fill: #1f2328; font: 600 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .label {{ fill: #656d76; font: 10px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .cell {{ fill: #ebedf0; }}
    .level-1 {{ fill: #9be9a8; }}
    .level-2 {{ fill: #40c463; }}
    .level-3 {{ fill: #30a14e; }}
    .level-4 {{ fill: #216e39; }}
    .active {{
      animation: contribution-glow 4.32s ease-in-out infinite;
      animation-delay: var(--delay);
      transform-box: fill-box;
      transform-origin: center;
    }}
    @keyframes contribution-glow {{
      0%, 70%, 100% {{ filter: none; opacity: 1; transform: scale(1); }}
      82% {{ filter: url(#glow); opacity: 1; transform: scale(1.3); }}
      92% {{ filter: none; opacity: 1; transform: scale(1); }}
    }}
    @media (prefers-color-scheme: dark) {{
      .background {{ fill: #0d1117; }}
      .heading {{ fill: #e6edf3; }}
      .label {{ fill: #8b949e; }}
      .cell {{ fill: #161b22; }}
      .level-1 {{ fill: #0e4429; }}
      .level-2 {{ fill: #006d32; }}
      .level-3 {{ fill: #26a641; }}
      .level-4 {{ fill: #39d353; }}
    }}
    @media (prefers-reduced-motion: reduce) {{ .active {{ animation: none; }} }}
  </style>
  <rect class="background" width="100%" height="100%" rx="8" />
  <text class="heading" x="7" y="20">{total} contributions in the last year</text>
  {''.join(labels)}
  {day_labels}
  {''.join(cells)}
</svg>
'''


def main() -> None:
    username = os.environ.get("GITHUB_REPOSITORY_OWNER") or os.environ.get("GITHUB_USER")
    token = os.environ.get("GITHUB_TOKEN")
    if not username or not token:
        sys.exit("GITHUB_REPOSITORY_OWNER (or GITHUB_USER) and GITHUB_TOKEN are required")

    output = Path(os.environ.get("OUTPUT_PATH", "dist/contribution-glow.svg"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(fetch_calendar(username, token)), encoding="utf-8")
    print(f"Generated {output}")


if __name__ == "__main__":
    main()
