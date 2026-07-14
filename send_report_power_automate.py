from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


def send_html_report(
    report_path: str | Path,
    timeout_seconds: int = 90,
) -> None:
    load_dotenv(override=True)

    flow_url = os.getenv(
        "POWER_AUTOMATE_FLOW_URL",
        "",
    ).strip()

    if not flow_url:
        raise RuntimeError(
            "Missing POWER_AUTOMATE_FLOW_URL in .env"
        )

    html_path = Path(report_path)

    if not html_path.exists():
        raise FileNotFoundError(
            f"HTML report not found: {html_path}"
        )

    html_content = html_path.read_text(
        encoding="utf-8"
    )

    payload = {
        "file_name": html_path.name,
        "file_content": html_content,
    }

    response = requests.post(
        flow_url,
        json=payload,
        timeout=timeout_seconds,
    )

    if not response.ok:
        raise RuntimeError(
            "Power Automate returned an error: "
            f"HTTP {response.status_code} - "
            f"{response.text[:1000]}"
        )

    print(
        "HTML file sent successfully to Power Automate. "
        f"HTTP {response.status_code}"
    )