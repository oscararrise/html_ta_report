from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, select_autoescape


BASE_DIR = Path(__file__).resolve().parent
LOW_PIPELINE_THRESHOLD = 2

def load_logo_data_uri() -> str:
    """
    Load logo.png and convert it into an embedded Base64 data URI.

    Embedding the image allows the generated HTML file to work
    independently when it is downloaded, stored in SharePoint,
    or sent as an email attachment.
    """
    logo_path = BASE_DIR / "logo.png"

    if not logo_path.exists():
        print(f"Warning: logo file was not found: {logo_path}")
        return ""

    try:
        logo_bytes = logo_path.read_bytes()
    except OSError as error:
        print(f"Warning: could not read logo file: {error}")
        return ""

    encoded_logo = base64.b64encode(
        logo_bytes
    ).decode("ascii")

    return f"data:image/png;base64,{encoded_logo}"

REPORT_TEMPLATE = """
<!doctype html>
<html lang="en">

<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>{{ area }} Talent Acquisition Report</title>

<style>
:root {
    --rare-sky: #8f85ff;
    --royal-violet: #331062;
    --blue-charcoal: #163e4f;
    --neo-jade: #75ffab;
    --lynx-white: #f6f6f6;
    --dark-rift: #081117;
    --line: rgba(246, 246, 246, 0.16);
}

* {
    box-sizing: border-box;
}

html {
    scroll-behavior: smooth;
}

body {
    margin: 0;
    font-family: "Noto Sans", "Avenir Next", Avenir, Arial, sans-serif;
    color: var(--lynx-white);
    background:
        radial-gradient(
            circle at 15% 8%,
            rgba(143, 133, 255, 0.32),
            transparent 34%
        ),
        radial-gradient(
            circle at 84% 2%,
            rgba(117, 255, 171, 0.18),
            transparent 24%
        ),
        linear-gradient(
            135deg,
            var(--dark-rift),
            #091820 48%,
            #03080c
        );
    min-height: 100vh;
}

.page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 34px 42px 54px;
}

.topline {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    margin-bottom: 26px;
}

.logo {
    display: inline-flex;
    align-items: center;
    justify-content: flex-start;
    min-height: 58px;
}

.logo img {
    display: block;
    width: auto;
    height: 58px;
    max-width: 220px;
    object-fit: contain;
}

.logo-fallback {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 48px;
    padding: 0 17px;
    border: 3px solid var(--rare-sky);
    color: var(--rare-sky);
    font-weight: 900;
    letter-spacing: -1.6px;
    font-size: 25px;
    transform: skew(-8deg);
}

.logo-fallback span {
    display: block;
    transform: skew(8deg);
}

.meta {
    text-align: right;
    color: rgba(246, 246, 246, 0.72);
    font-size: 13px;
    line-height: 1.5;
}

.hero {
    position: relative;
    overflow: hidden;
    background:
        linear-gradient(
            105deg,
            rgba(51, 16, 98, 0.95) 0%,
            rgba(51, 16, 98, 0.72) 48%,
            rgba(22, 62, 79, 0.78) 100%
        );
    border: 1px solid rgba(143, 133, 255, 0.36);
    padding: 42px;
    min-height: 250px;
    border-radius: 28px;
    box-shadow: 0 22px 80px rgba(0, 0, 0, 0.34);
}

.eyebrow {
    color: var(--neo-jade);
    text-transform: uppercase;
    font-weight: 800;
    font-size: 14px;
    letter-spacing: 0.16em;
    margin-bottom: 12px;
}

h1 {
    margin: 0;
    max-width: 800px;
    text-transform: uppercase;
    font-size: clamp(40px, 6.4vw, 76px);
    letter-spacing: -3.4px;
    line-height: 0.95;
    font-weight: 900;
}

.hero-copy {
    max-width: 720px;
    color: rgba(246, 246, 246, 0.82);
    font-size: 17px;
    line-height: 1.6;
    margin: 18px 0 0;
}

.nav {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 24px 0 30px;
}

.nav a {
    text-decoration: none;
    color: var(--lynx-white);
    border: 1px solid var(--line);
    padding: 10px 14px;
    border-radius: 999px;
    background: rgba(246, 246, 246, 0.05);
    font-size: 13px;
    font-weight: 700;
}

.nav a:hover {
    background: var(--neo-jade);
    color: var(--dark-rift);
}

.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 18px;
    margin: 26px 0;
}

.kpi {
    background: rgba(246, 246, 246, 0.96);
    color: var(--dark-rift);
    border-radius: 22px;
    padding: 24px;
    min-height: 152px;
}

.kpi.dark {
    background: linear-gradient(135deg, var(--blue-charcoal), #0d2a37);
    color: var(--lynx-white);
    border: 1px solid rgba(117, 255, 171, 0.20);
}

.kpi .value {
    font-size: 52px;
    font-weight: 900;
    letter-spacing: -2px;
    line-height: 1;
}

.kpi .label {
    margin-top: 10px;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-weight: 800;
}

.kpi .sub {
    margin-top: 12px;
    color: rgba(8, 17, 23, 0.65);
    font-size: 13px;
    line-height: 1.4;
}

.kpi.dark .sub {
    color: rgba(246, 246, 246, 0.68);
}

.section {
    margin-top: 32px;
    background: rgba(8, 17, 23, 0.56);
    border: 1px solid var(--line);
    border-radius: 28px;
    padding: 26px;
    box-shadow: 0 16px 60px rgba(0, 0, 0, 0.22);
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 20px;
    margin-bottom: 20px;
}

.section h2 {
    margin: 0;
    text-transform: uppercase;
    font-size: 30px;
    letter-spacing: -1.1px;
}

.section p {
    margin: 8px 0 0;
    color: rgba(246, 246, 246, 0.70);
    line-height: 1.5;
}

.grid-2 {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
    gap: 20px;
}

.panel {
    background: rgba(246, 246, 246, 0.06);
    border: 1px solid var(--line);
    border-radius: 22px;
    padding: 22px;
}

.panel.light {
    background: var(--lynx-white);
    color: var(--dark-rift);
}

.panel-title {
    color: var(--neo-jade);
    text-transform: uppercase;
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 0.12em;
    margin-bottom: 18px;
}

.panel.light .panel-title {
    color: var(--royal-violet);
}

.bar-row {
    display: grid;
    grid-template-columns: 220px 1fr 40px;
    gap: 12px;
    align-items: center;
    margin: 14px 0;
}

.bar-label {
    font-size: 13px;
    color: rgba(246, 246, 246, 0.82);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.bar-track {
    height: 14px;
    background: rgba(246, 246, 246, 0.14);
    border-radius: 999px;
    overflow: hidden;
}

.bar-fill {
    height: 100%;
    min-width: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--rare-sky), #b5afff);
}

.bar-fill.jade {
    background: linear-gradient(90deg, var(--neo-jade), #c7ffdd);
}

.bar-value {
    text-align: right;
    font-weight: 900;
    color: var(--neo-jade);
}

.chart-row {
    display: grid;
    grid-template-columns: minmax(220px, 340px) 1fr 42px;
    gap: 14px;
    align-items: center;
    margin: 16px 0;
}

.chart-label {
    font-size: 13px;
    color: rgba(246, 246, 246, 0.84);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.chart-track {
    height: 22px;
    background: rgba(246, 246, 246, 0.10);
    border: 1px solid rgba(246, 246, 246, 0.12);
    border-radius: 999px;
    overflow: hidden;
}

.chart-fill {
    height: 100%;
    min-width: 3px;
    border-radius: 999px;
}

.chart-fill.chart-active {
    background: linear-gradient(90deg, var(--neo-jade), #c7ffdd);
}

.chart-fill.chart-warning {
    background: linear-gradient(90deg, #ffd166, #ff9f43);
}

.chart-fill.chart-empty {
    background: linear-gradient(90deg, #ff7b8b, #ff4d68);
}

.chart-value {
    text-align: right;
    color: var(--neo-jade);
    font-size: 18px;
    font-weight: 900;
}

.mini-cards {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
}

.mini-card {
    border-radius: 20px;
    padding: 22px;
    background: linear-gradient(135deg, var(--royal-violet), #4b168d);
    color: var(--lynx-white);
    min-height: 120px;
}

.mini-value {
    font-size: 48px;
    line-height: 1;
    font-weight: 900;
}

.mini-label {
    margin-top: 8px;
    text-transform: uppercase;
    font-size: 13px;
    letter-spacing: 0.10em;
    color: rgba(246, 246, 246, 0.80);
    font-weight: 800;
}

.table-wrap {
    overflow: auto;
    border: 1px solid var(--line);
    border-radius: 20px;
}

table {
    width: 100%;
    border-collapse: collapse;
    min-width: 900px;
}

th,
td {
    text-align: left;
    padding: 15px 16px;
    vertical-align: top;
    border-bottom: 1px solid rgba(246, 246, 246, 0.12);
    font-size: 14px;
    line-height: 1.42;
}

th {
    color: var(--neo-jade);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    background: rgba(51, 16, 98, 0.42);
    white-space: nowrap;
}

tr:last-child td {
    border-bottom: none;
}

.role-name {
    font-weight: 850;
    color: var(--lynx-white);
}

.badge {
    display: inline-flex;
    align-items: center;
    padding: 7px 10px;
    border-radius: 999px;
    font-weight: 850;
    font-size: 12px;
    white-space: nowrap;
    background: rgba(143, 133, 255, 0.18);
    color: #c8c3ff;
    border: 1px solid rgba(143, 133, 255, 0.38);
}

.status {
    display: inline-flex;
    align-items: center;
    padding: 7px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 850;
    white-space: nowrap;
}

.status-active {
    color: var(--neo-jade);
    background: rgba(117, 255, 171, 0.12);
    border: 1px solid rgba(117, 255, 171, 0.36);
}

.status-warning {
    color: #ffd889;
    background: rgba(255, 190, 70, 0.12);
    border: 1px solid rgba(255, 190, 70, 0.34);
}

.status-empty {
    color: #ff9eaa;
    background: rgba(255, 100, 120, 0.12);
    border: 1px solid rgba(255, 100, 120, 0.34);
}

.hire-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 14px;
}

.hire-card {
    background: rgba(246, 246, 246, 0.06);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 18px;
}

.hire-card .month {
    color: var(--neo-jade);
    font-size: 12px;
    text-transform: uppercase;
    font-weight: 900;
    letter-spacing: 0.12em;
}

.hire-card .name {
    margin-top: 8px;
    font-size: 18px;
    font-weight: 850;
}

.hire-card .role {
    margin-top: 8px;
    color: rgba(246, 246, 246, 0.72);
    font-size: 13px;
}

.source-note {
    margin-top: 18px;
    padding: 14px 16px;
    color: rgba(246, 246, 246, 0.68);
    border-left: 4px solid var(--neo-jade);
    background: rgba(117, 255, 171, 0.06);
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.45;
}

.empty-note {
    color: rgba(246, 246, 246, 0.64);
    padding: 16px;
}

.footer {
    color: rgba(246, 246, 246, 0.46);
    font-size: 12px;
    margin-top: 26px;
    text-align: center;
}

@media (max-width: 1000px) {
    .page {
        padding: 24px;
    }

    .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .grid-2 {
        grid-template-columns: 1fr;
    }

    .hire-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 650px) {
    .topline {
        flex-direction: column;
    }

    .meta {
        text-align: left;
    }

    .kpi-grid,
    .hire-grid {
        grid-template-columns: 1fr;
    }

    .bar-row,
    .chart-row {
        grid-template-columns: 120px 1fr 30px;
    }
}

.insight-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
}

.line-chart {
    display: flex;
    align-items: stretch;
    gap: 10px;
    height: 240px;
    padding-top: 10px;
}

.insight-item {
    flex: 1;
    min-width: 0;
    height: 100%;
    display: grid;
    grid-template-rows: 22px 1fr 22px;
}

.line-value {
    font-size: 12px;
    font-weight: 800;
    color: var(--neo-jade);
    text-align: center;
}

.line-bar-area {
    display: flex;
    align-items: flex-end;
    height: 100%;
}

.line-bar {
    width: 100%;
    min-height: 0;
    border-radius: 12px 12px 0 0;
    background: linear-gradient(
        180deg,
        var(--neo-jade),
        var(--rare-sky)
    );
}

.line-bar.zero {
    height: 0 !important;
    background: none;
}

.line-label {
    margin-top: 8px;
    font-size: 11px;
    color: rgba(246, 246, 246, 0.68);
    text-align: center;
}

.insight-item {
    display: flex;
    flex-direction: column;
    align-items: stretch;
}

</style>
</head>

<body>

<main class="page">

    <div class="topline">

        {% if logo_data_uri %}
<div class="logo">
    <img
        src="{{ logo_data_uri }}"
        alt="ARRISE"
    >
</div>
{% else %}
<div class="logo-fallback">
    <span>ARRISE</span>
</div>
{% endif %}

        <div class="meta">
            <strong>Talent Acquisition Report</strong><br>
            Department: {{ area }}<br>
            Generated: {{ generated_at }}
        </div>

    </div>

    <section class="hero">

        <div class="eyebrow">
            Recruitment Pipeline
        </div>

        <h1>
            {{ area }} Talent Acquisition Report
        </h1>

        <p class="hero-copy">
            Current open requisitions, active candidate pipeline and people
            hired during {{ current_year }}.
        </p>

    </section>

    <nav class="nav">
        <a href="#snapshot">Snapshot</a>
        <a href="#pipeline">Pipeline</a>
        <a href="#vacancies">Open Requisitions</a>
        <a href="#candidates">Candidates</a>
        <a href="#hires">Hires</a>
        <a href="#analytics">Analytics</a>
    </nav>

    <section id="snapshot" class="kpi-grid">

        <div class="kpi">
            <div class="value">{{ total_open_roles }}</div>
            <div class="label">Open Requisitions</div>
            <div class="sub">
                Primary live requisitions after excluding additional location postings.
            </div>
        </div>

        <div class="kpi dark">
            <div class="value">{{ total_active_candidates }}</div>
            <div class="label">Active Candidates</div>
            <div class="sub">
                Rejected and withdrawn candidates are excluded.
            </div>
        </div>

        <div class="kpi">
            <div class="value">{{ total_hired }}</div>
            <div class="label">Hired This Year</div>
            <div class="sub">
                Hires registered during {{ current_year }}.
            </div>
        </div>

        <div class="kpi dark">
            <div class="value">{{ new_roles + backfill_roles }}</div>
            <div class="label">Role Mix</div>
            <div class="sub">
                {{ new_roles }} New / {{ backfill_roles }} Backfill
            </div>
        </div>

    </section>

    <section id="pipeline" class="section">

        <div class="section-header">
            <div>
                <h2>Candidate Pipeline</h2>
                <p>
                    Active candidates grouped by their current workflow stage.
                </p>
            </div>
        </div>

        <div class="grid-2">

            <div class="panel">

                <div class="panel-title">
                    Candidates by Stage
                </div>

                {% for stage in stage_rows %}

                <div class="bar-row">

                    <div class="bar-label" title="{{ stage.stage }}">
                        {{ stage.stage }}
                    </div>

                    <div class="bar-track">
                        <div
                            class="bar-fill"
                            style="width: {{ stage.width }}%;">
                        </div>
                    </div>

                    <div class="bar-value">
                        {{ stage.total }}
                    </div>

                </div>

                {% else %}

                <div class="empty-note">
                    No active candidates were found.
                </div>

                {% endfor %}

            </div>

            <div class="panel light">

                <div class="panel-title">
                    Requisition Type
                </div>

                <div class="mini-cards">

                    <div class="mini-card">
                        <div class="mini-value">{{ new_roles }}</div>
                        <div class="mini-label">New</div>
                    </div>

                    <div class="mini-card">
                        <div class="mini-value">{{ backfill_roles }}</div>
                        <div class="mini-label">Backfill</div>
                    </div>

                </div>

            </div>

        </div>

    </section>

    <section id="vacancies" class="section">

        <div class="section-header">
            <div>
                <h2>Open Requisitions</h2>
                <p>
                    Primary open requisitions retrieved from Jobvite.
                </p>
            </div>
        </div>

        <div class="table-wrap">

            <table>

                <thead>
                    <tr>
                        <th>Requisition ID</th>
                        <th>Job Title</th>
                        <th>Reason</th>
                        <th>Hiring Manager</th>
                        <th>Working Type</th>
                        <th>Location</th>
                    </tr>
                </thead>

                <tbody>

                    {% for role in roles %}

                    <tr>
                        <td>{{ role.requisition_id }}</td>
                        <td class="role-name">{{ role.title }}</td>
                        <td>{{ role.reason }}</td>
                        <td>{{ role.hiring_manager }}</td>
                        <td>{{ role.working_type }}</td>
                        <td>{{ role.location }}</td>
                    </tr>

                    {% else %}

                    <tr>
                        <td colspan="6" class="empty-note">
                            No open requisitions were found.
                        </td>
                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

    </section>

    <section id="candidates" class="section">

        <div class="section-header">
            <div>
                <h2>Active Candidates</h2>
                <p>
                    Candidate-level view for the currently open job titles.
                </p>
            </div>
        </div>

        <div class="table-wrap">

            <table>

                <thead>
                    <tr>
                        <th>Candidate</th>
                        <th>Job Title</th>
                        <th>Current Stage</th>
                        <th>Country</th>
                        <th>Source</th>
                    </tr>
                </thead>

                <tbody>

                    {% for candidate in candidates %}

                    <tr>
                        <td class="role-name">{{ candidate.name }}</td>
                        <td>{{ candidate.job_title }}</td>

                        <td>
                            <span class="badge">
                                {{ candidate.stage }}
                            </span>
                        </td>

                        <td>{{ candidate.country }}</td>
                        <td>{{ candidate.source }}</td>
                    </tr>

                    {% else %}

                    <tr>
                        <td colspan="5" class="empty-note">
                            No active candidates were found.
                        </td>
                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

    </section>

    <section id="hires" class="section">

        <div class="section-header">
            <div>
                <h2>Hired During {{ current_year }}</h2>
                <p>
                    People hired in the selected department during the current year.
                </p>
            </div>
        </div>

        <div class="hire-grid">

            {% for hire in hires %}

            <div class="hire-card">
                <div class="month">{{ hire.month }}</div>
                <div class="name">{{ hire.name }}</div>

                <div class="role">
                    {{ hire.job_title }}<br>
                    {{ hire.location }}
                </div>
            </div>

            {% else %}

            <div class="empty-note">
                No hires were found for {{ current_year }}.
            </div>

            {% endfor %}

        </div>

        {% if hires %}

        <div class="table-wrap" style="margin-top: 18px;">

            <table>

                <thead>
                    <tr>
                        <th>Job Title</th>
                        <th>Name</th>
                        <th>Location</th>
                        <th>Month of Hire</th>
                        <th>Hire Date</th>
                    </tr>
                </thead>

                <tbody>

                    {% for hire in hires %}

                    <tr>
                        <td class="role-name">{{ hire.job_title }}</td>
                        <td>{{ hire.name }}</td>
                        <td>{{ hire.location }}</td>
                        <td>{{ hire.month }}</td>
                        <td>{{ hire.hire_date }}</td>
                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

        {% endif %}

    </section>

    <section id="analytics" class="section">

        <div class="section-header">
            <div>
                <h2>Talent Acquisition Analytics</h2>

                <p>
                    Additional indicators based on current open requisitions,
                    active candidates and hires recorded during {{ current_year }}.
                </p>
            </div>
        </div>

        <div class="kpi-grid">

            <div class="kpi">
                <div class="value">{{ candidates_per_open_role }}</div>
                <div class="label">Candidates per Opening</div>
                <div class="sub">
                    Average active candidates for each open position.
                </div>
            </div>

            <div class="kpi dark">
                <div class="value">{{ roles_without_candidates }}</div>
                <div class="label">Roles Without Pipeline</div>
                <div class="sub">
                    Job titles currently showing no active candidates.
                </div>
            </div>

            <div class="kpi">
                <div class="value">{{ roles_with_low_pipeline }}</div>
                <div class="label">Low Pipeline Roles</div>
                <div class="sub">
                    Roles below {{ low_pipeline_threshold }} active candidates per opening.
                </div>
            </div>

            <div class="kpi dark">
                <div class="value">{{ average_hires_per_month }}</div>
                <div class="label">Average Hires per Month</div>
                <div class="sub">
                    Average monthly hiring pace during {{ current_year }}.
                </div>
            </div>

        </div>

        <div class="panel" style="margin-bottom: 20px;">

            <div class="panel-title">
                Active Candidates by Job Title
            </div>

            {% for row in title_pipeline_rows %}

            <div class="chart-row">

                <div
                    class="chart-label"
                    title="{{ row.job_title }}">
                    {{ row.job_title }}
                </div>

                <div class="chart-track">

                    <div
                        class="chart-fill {{ row.chart_class }}"
                        style="width: {{ row.chart_width }}%;">
                    </div>

                </div>

                <div class="chart-value">
                    {{ row.active_candidates }}
                </div>

            </div>

            {% else %}

            <div class="empty-note">
                No candidate pipeline data is available.
            </div>

            {% endfor %}

        </div>

        <div class="grid-2">

            <div class="panel">

                <div class="panel-title">
                    Pipeline Coverage by Job Title
                </div>

                <div class="table-wrap">

                    <table>

                        <thead>
                            <tr>
                                <th>Job Title</th>
                                <th>Open Positions</th>
                                <th>Active Candidates</th>
                                <th>Candidates per Opening</th>
                                <th>Status</th>
                            </tr>
                        </thead>

                        <tbody>

                            {% for row in title_pipeline_rows %}

                            <tr>

                                <td class="role-name">
                                    {{ row.job_title }}
                                </td>

                                <td>
                                    {{ row.open_positions }}
                                </td>

                                <td>
                                    {{ row.active_candidates }}
                                </td>

                                <td>
                                    {{ row.candidates_per_opening }}
                                </td>

                                <td>

                                    {% if row.status == "No active pipeline" %}

                                    <span class="status status-empty">
                                        {{ row.status }}
                                    </span>

                                    {% elif row.status == "Needs attention" %}

                                    <span class="status status-warning">
                                        {{ row.status }}
                                    </span>

                                    {% else %}

                                    <span class="status status-active">
                                        {{ row.status }}
                                    </span>

                                    {% endif %}

                                </td>

                            </tr>

                            {% else %}

                            <tr>
                                <td colspan="5" class="empty-note">
                                    No pipeline information is available.
                                </td>
                            </tr>

                            {% endfor %}

                        </tbody>

                    </table>

                </div>

            </div>

            <div class="panel">

                <div class="panel-title">
                    Candidate Sources
                </div>

                {% for source in source_rows %}

                <div class="bar-row">

                    <div
                        class="bar-label"
                        title="{{ source.source }}">
                        {{ source.source }}
                    </div>

                    <div class="bar-track">

                        <div
                            class="bar-fill jade"
                            style="width: {{ source.width }}%;">
                        </div>

                    </div>

                    <div class="bar-value">
                        {{ source.total }}
                    </div>

                </div>

                {% else %}

                <div class="empty-note">
                    No candidate source information is available.
                </div>

                {% endfor %}

                <div class="source-note">
                    <strong>Top candidate source:</strong>
                    {{ top_source }}

                    <br>

                    <strong>Share of active pipeline:</strong>
                    {{ top_source_share }}%
                </div>

        <div class="panel" style="margin-top: 20px;">
            <div class="panel-title">Submitted to Manager</div>

            {% for item in submitted_to_manager_rows %}
            <div class="bar-row">
                <div class="bar-label" title="{{ item.job_title }}">{{ item.job_title }}</div>
                <div class="bar-track">
                    <div class="bar-fill jade" style="width: {{ item.width }}%;"></div>
                </div>
                <div class="bar-value">{{ item.total }}</div>
            </div>
            {% else %}
            <div class="empty-note">
                No candidates are currently in Submitted to manager stage for this area.
            </div>
            {% endfor %}
        </div>

            </div>

        </div>

    </section>


    <section id="final-insights" class="section">
        <div class="section-header">
            <div>
                <h2>Final Data Insights</h2>
                <p>Additional visual analysis based on hires, active candidates and open requisitions.</p>
            </div>
        </div>

        <div class="insight-grid">

            <div class="panel">
                <div class="panel-title">Hires by Month</div>
                <div class="line-chart">
                    {% for month in hires_by_month_rows %}
<div class="insight-item">

    <div class="line-value">
        {{ month.total }}
    </div>

    <div class="line-bar-area">
        <div
            class="line-bar{% if month.total == 0 %} zero{% endif %}"
            title="{{ month.month }}: {{ month.total }}"
            style="height: {{ month.height }}%;">
        </div>
    </div>

    <div class="line-label">
        {{ month.month_short }}
    </div>

</div>
{% else %}
                    <div class="empty-note">No monthly hire data is available.</div>
                    {% endfor %}
                </div>
            </div>

            <div class="panel">
                <div class="panel-title">Active Candidates by Country</div>
                {% for country in candidate_country_rows %}
                <div class="bar-row">
                    <div class="bar-label" title="{{ country.country }}">{{ country.country }}</div>
                    <div class="bar-track"><div class="bar-fill jade" style="width: {{ country.width }}%;"></div></div>
                    <div class="bar-value">{{ country.total }}</div>
                </div>
                {% else %}
                <div class="empty-note">No country data is available.</div>
                {% endfor %}
            </div>

            <div class="panel">
                <div class="panel-title">Open Requisitions by Working Type</div>
                {% for item in working_type_rows %}
                <div class="bar-row">
                    <div class="bar-label" title="{{ item.working_type }}">{{ item.working_type }}</div>
                    <div class="bar-track"><div class="bar-fill" style="width: {{ item.width }}%;"></div></div>
                    <div class="bar-value">{{ item.total }}</div>
                </div>
                {% else %}
                <div class="empty-note">No working type data is available.</div>
                {% endfor %}
            </div>

            <div class="panel">
                <div class="panel-title">Open Requisitions by Reason</div>
                {% for item in reason_rows %}
                <div class="bar-row">
                    <div class="bar-label" title="{{ item.reason }}">{{ item.reason }}</div>
                    <div class="bar-track"><div class="bar-fill jade" style="width: {{ item.width }}%;"></div></div>
                    <div class="bar-value">{{ item.total }}</div>
                </div>
                {% else %}
                <div class="empty-note">No reason data is available.</div>
                {% endfor %}
            </div>

        </div>
    </section>

    <div class="footer">
        ARRISE Talent Acquisition report generated from Jobvite and Redshift data.
    </div>

</main>

</body>

</html>
"""


def clean_value(value: Any, default: str = "--") -> str:
    if value is None or pd.isna(value):
        return default

    cleaned_value = str(value).strip()

    return cleaned_value or default


def get_first_available_value(
    row: pd.Series,
    column_names: list[str],
    default: str = "--",
) -> str:
    for column_name in column_names:
        if column_name not in row.index:
            continue

        value = clean_value(row[column_name], "")

        if value:
            return value

    return default


def get_location_column(
    requisitions_df: pd.DataFrame,
) -> str | None:
    possible_location_columns = [
        "location",
        "locations",
        "job_location",
        "job_location_country",
        "country",
        "job_country",
    ]

    for column_name in possible_location_columns:
        if column_name in requisitions_df.columns:
            return column_name

    return None


def is_yes_value(value: Any) -> bool:
    normalized_value = clean_value(value, "").casefold()

    return normalized_value in {
        "yes",
        "true",
        "1",
        "y",
    }


def consolidate_requisitions(
    requisitions_df: pd.DataFrame,
) -> pd.DataFrame:
    if requisitions_df.empty:
        return requisitions_df.copy()

    requisitions = requisitions_df.copy()

    if "exclude_from_live_and_ytd" not in requisitions.columns:
        return requisitions

    location_column = get_location_column(requisitions)

    requisitions["_is_additional_posting"] = requisitions["exclude_from_live_and_ytd"].apply(is_yes_value)

    grouping_columns = [
        column_name
        for column_name in [
            "title",
            "hiring_manager_user_name",
            "reason",
            "working_type",
        ]
        if column_name in requisitions.columns
    ]

    if not grouping_columns:
        return requisitions[
            ~requisitions["_is_additional_posting"]
        ].drop(
            columns=["_is_additional_posting"]
        ).reset_index(drop=True)

    grouping_key_columns = []

    for column_name in grouping_columns:
        key_column = f"_{column_name}_group_key"

        requisitions[key_column] = requisitions[column_name].fillna("").astype(str).str.strip().str.casefold()

        grouping_key_columns.append(key_column)

    consolidated_rows = []

    grouped_requisitions = requisitions.groupby(
        grouping_key_columns,
        dropna=False,
        sort=False,
    )

    for _, group in grouped_requisitions:
        primary_rows = group[~group["_is_additional_posting"]].copy()

        if primary_rows.empty:
            consolidated_rows.append(group.iloc[0].copy())
            continue

        if location_column is not None and len(primary_rows) == 1:
            locations = group[location_column].dropna().astype(str).str.strip()
            locations = locations[locations.ne("")].drop_duplicates().tolist()

            if locations:
                primary_rows.loc[:, location_column] = ", ".join(locations)

        for _, primary_row in primary_rows.iterrows():
            consolidated_rows.append(primary_row.copy())

    consolidated = pd.DataFrame(consolidated_rows)

    helper_columns = [
        column_name
        for column_name in consolidated.columns
        if column_name.startswith("_")
    ]

    consolidated = consolidated.drop(
        columns=helper_columns,
        errors="ignore",
    )

    if "requisition_id" in consolidated.columns:
        consolidated = consolidated.drop_duplicates(
            subset=["requisition_id"],
            keep="first",
        )

    return consolidated.reset_index(drop=True)


def prepare_requisitions(
    requisitions_df: pd.DataFrame,
) -> pd.DataFrame:
    if requisitions_df.empty:
        return requisitions_df.copy()

    return consolidate_requisitions(requisitions_df)


def prepare_applications(
    applications_df: pd.DataFrame,
) -> pd.DataFrame:
    if applications_df.empty:
        return applications_df.copy()

    applications = applications_df.copy()

    if "app_workflow_state_name" in applications.columns:
        workflow_states = applications["app_workflow_state_name"].fillna("").astype(str).str.strip().str.casefold()

        applications = applications[
            ~workflow_states.str.contains("reject", regex=False)
            & ~workflow_states.str.contains("withdraw", regex=False)
        ].copy()

    duplicate_columns = [
        column_name
        for column_name in [
            "app_full_name",
            "job_title",
            "app_workflow_state_name",
        ]
        if column_name in applications.columns
    ]

    if duplicate_columns:
        applications = applications.drop_duplicates(
            subset=duplicate_columns,
            keep="first",
        )

    return applications.reset_index(drop=True)


def build_stage_rows(
    applications: pd.DataFrame,
) -> list[dict[str, Any]]:
    if applications.empty:
        return []

    if "app_workflow_state_name" not in applications.columns:
        return []

    stage_counts = applications["app_workflow_state_name"].fillna("Not specified").astype(str).str.strip().replace("", "Not specified").value_counts().rename_axis("stage").reset_index(name="total")

    maximum_stage_total = int(stage_counts["total"].max())

    stage_rows = []

    for _, row in stage_counts.iterrows():
        total = int(row["total"])

        width = round(
            total / maximum_stage_total * 100,
            2,
        ) if maximum_stage_total else 0

        stage_rows.append(
            {
                "stage": clean_value(
                    row["stage"],
                    "Not specified",
                ),
                "total": total,
                "width": width,
            }
        )

    return stage_rows


def build_pipeline_by_title(
    requisitions: pd.DataFrame,
    applications: pd.DataFrame,
) -> list[dict[str, Any]]:
    if requisitions.empty or "title" not in requisitions.columns:
        return []

    open_roles_by_title = requisitions["title"].fillna("Not specified").astype(str).str.strip().replace("", "Not specified").value_counts().rename_axis("job_title").reset_index(name="open_positions")

    if applications.empty or "job_title" not in applications.columns:
        candidates_by_title = pd.DataFrame(
            columns=[
                "job_title",
                "active_candidates",
            ]
        )
    else:
        candidates_by_title = applications["job_title"].fillna("Not specified").astype(str).str.strip().replace("", "Not specified").value_counts().rename_axis("job_title").reset_index(name="active_candidates")

    pipeline_by_title = open_roles_by_title.merge(
        candidates_by_title,
        on="job_title",
        how="left",
    )

    pipeline_by_title["active_candidates"] = pipeline_by_title["active_candidates"].fillna(0).astype(int)

    pipeline_by_title["candidates_per_opening"] = (
        pipeline_by_title["active_candidates"]
        / pipeline_by_title["open_positions"]
    ).round(2)

    maximum_candidate_total = int(
        pipeline_by_title["active_candidates"].max()
    )

    def calculate_pipeline_status(
        candidates_per_opening: float,
    ) -> str:
        if candidates_per_opening == 0:
            return "No active pipeline"

        if candidates_per_opening < LOW_PIPELINE_THRESHOLD:
            return "Needs attention"

        return "Active pipeline"

    pipeline_by_title["status"] = pipeline_by_title["candidates_per_opening"].apply(calculate_pipeline_status)

    pipeline_by_title = pipeline_by_title.sort_values(
        by=[
            "active_candidates",
            "job_title",
        ],
        ascending=[
            False,
            True,
        ],
    )

    pipeline_rows = []

    for _, row in pipeline_by_title.iterrows():
        active_candidates = int(row["active_candidates"])
        candidates_per_opening = float(row["candidates_per_opening"])

        if active_candidates == 0:
            chart_class = "chart-empty"
        elif candidates_per_opening < LOW_PIPELINE_THRESHOLD:
            chart_class = "chart-warning"
        else:
            chart_class = "chart-active"

        chart_width = round(
            active_candidates / maximum_candidate_total * 100,
            2,
        ) if maximum_candidate_total else 0

        pipeline_rows.append(
            {
                "job_title": clean_value(row["job_title"]),
                "open_positions": int(row["open_positions"]),
                "active_candidates": active_candidates,
                "candidates_per_opening": candidates_per_opening,
                "status": clean_value(row["status"]),
                "chart_class": chart_class,
                "chart_width": chart_width,
            }
        )

    return pipeline_rows


def build_source_rows(
    applications: pd.DataFrame,
) -> tuple[list[dict[str, Any]], str, float]:
    if applications.empty or "app_sourcetype" not in applications.columns:
        return [], "--", 0

    source_counts = applications["app_sourcetype"].fillna("Not specified").astype(str).str.strip().replace("", "Not specified").value_counts().rename_axis("source").reset_index(name="total")

    total_candidates = int(source_counts["total"].sum())
    maximum_source_total = int(source_counts["total"].max())

    source_rows = []

    for _, row in source_counts.iterrows():
        total = int(row["total"])

        source_rows.append(
            {
                "source": clean_value(
                    row["source"],
                    "Not specified",
                ),
                "total": total,
                "share": round(
                    total / total_candidates * 100,
                    1,
                ) if total_candidates else 0,
                "width": round(
                    total / maximum_source_total * 100,
                    2,
                ) if maximum_source_total else 0,
            }
        )

    top_source = clean_value(
        source_counts.iloc[0]["source"],
        "Not specified",
    )

    top_source_total = int(
        source_counts.iloc[0]["total"]
    )

    top_source_share = round(
        top_source_total / total_candidates * 100,
        1,
    ) if total_candidates else 0

    return source_rows, top_source, top_source_share



def build_count_rows(
    dataframe: pd.DataFrame,
    column_name: str,
    label_key: str,
    total_key: str = "total",
    limit: int = 10,
) -> list[dict[str, Any]]:
    if dataframe.empty or column_name not in dataframe.columns:
        return []

    counts = (
        dataframe[column_name]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
        .replace("", "Not specified")
        .value_counts()
        .head(limit)
        .rename_axis(label_key)
        .reset_index(name=total_key)
    )

    maximum_total = int(counts[total_key].max()) if not counts.empty else 0

    rows = []

    for _, row in counts.iterrows():
        total = int(row[total_key])

        rows.append(
            {
                label_key: clean_value(row[label_key], "Not specified"),
                total_key: total,
                "width": round(total / maximum_total * 100, 2) if maximum_total else 0,
            }
        )

    return rows


def build_hires_by_month_rows(
    hired_people: pd.DataFrame,
) -> list[dict[str, Any]]:
    month_names = [
        ("January", "Jan"),
        ("February", "Feb"),
        ("March", "Mar"),
        ("April", "Apr"),
        ("May", "May"),
        ("June", "Jun"),
        ("July", "Jul"),
        ("August", "Aug"),
        ("September", "Sep"),
        ("October", "Oct"),
        ("November", "Nov"),
        ("December", "Dec"),
    ]

    if hired_people.empty or "app_hire_date" not in hired_people.columns:
        return [
            {"month": month, "month_short": short, "total": 0, "height": 0}
            for month, short in month_names
        ]

    hire_dates = pd.to_datetime(
        hired_people["app_hire_date"],
        errors="coerce",
    ).dropna()

    month_counts = hire_dates.dt.month.value_counts().to_dict()
    maximum_total = max(month_counts.values()) if month_counts else 0

    rows = []

    for month_number, (month, short) in enumerate(month_names, start=1):
        total = int(month_counts.get(month_number, 0))

        rows.append(
            {
                "month": month,
                "month_short": short,
                "total": total,
                "height": round(total / maximum_total * 100, 2) if maximum_total else 0,
            }
        )

    return rows



def build_submitted_to_manager_rows(
    applications: pd.DataFrame,
) -> list[dict[str, Any]]:
    if applications.empty:
        return []

    required_columns = {
        "app_workflow_state_name",
        "job_title",
    }

    if not required_columns.issubset(applications.columns):
        return []

    submitted = applications[
        applications["app_workflow_state_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq("submitted to manager")
    ].copy()

    return build_count_rows(
        submitted,
        column_name="job_title",
        label_key="job_title",
    )


def build_report_context(
    area: str,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
) -> dict[str, Any]:
    requisitions = prepare_requisitions(requisitions_df)
    applications = prepare_applications(applications_df)
    hired_people = hired_people_df.copy()

    location_column = get_location_column(requisitions)

    roles = []

    for _, row in requisitions.iterrows():
        location_columns = [
            column_name
            for column_name in [
                location_column,
                "location",
                "job_location",
                "job_location_country",
                "country",
                "job_country",
            ]
            if column_name
        ]

        roles.append(
            {
                "requisition_id": get_first_available_value(
                    row,
                    [
                        "requisition_id",
                        "job_eid",
                    ],
                ),
                "title": get_first_available_value(
                    row,
                    [
                        "title",
                        "job_title",
                    ],
                ),
                "reason": get_first_available_value(
                    row,
                    ["reason"],
                    "Not specified",
                ),
                "hiring_manager": get_first_available_value(
                    row,
                    [
                        "hiring_manager_user_name",
                        "job_primary_hm_full_name",
                        "hiring_manager",
                    ],
                ),
                "working_type": get_first_available_value(
                    row,
                    ["working_type"],
                ),
                "location": get_first_available_value(
                    row,
                    location_columns,
                ),
            }
        )

    candidates = []

    for _, row in applications.iterrows():
        candidates.append(
            {
                "name": get_first_available_value(
                    row,
                    ["app_full_name"],
                ),
                "job_title": get_first_available_value(
                    row,
                    ["job_title"],
                ),
                "stage": get_first_available_value(
                    row,
                    ["app_workflow_state_name"],
                    "Not specified",
                ),
                "country": get_first_available_value(
                    row,
                    ["app_country"],
                ),
                "source": get_first_available_value(
                    row,
                    ["app_sourcetype"],
                ),
            }
        )

    hires = []

    for _, row in hired_people.iterrows():
        hire_date_value = row.get("app_hire_date")

        if hire_date_value is not None and not pd.isna(hire_date_value):
            hire_date = pd.to_datetime(
                hire_date_value
            ).strftime("%Y-%m-%d")
        else:
            hire_date = "--"

        hires.append(
            {
                "job_title": get_first_available_value(
                    row,
                    ["job_title"],
                ),
                "name": get_first_available_value(
                    row,
                    [
                        "name",
                        "app_full_name",
                    ],
                ),
                "location": get_first_available_value(
                    row,
                    [
                        "location",
                        "app_country",
                    ],
                ),
                "month": get_first_available_value(
                    row,
                    ["month_of_hire"],
                ),
                "hire_date": hire_date,
            }
        )

    stage_rows = build_stage_rows(applications)

    title_pipeline_rows = build_pipeline_by_title(
        requisitions,
        applications,
    )

    source_rows, top_source, top_source_share = build_source_rows(
        applications
    )

    hires_by_month_rows = build_hires_by_month_rows(hired_people)

    candidate_country_rows = build_count_rows(
        applications,
        column_name="app_country",
        label_key="country",
    )

    working_type_rows = build_count_rows(
        requisitions,
        column_name="working_type",
        label_key="working_type",
    )

    reason_rows = build_count_rows(
        requisitions,
        column_name="reason",
        label_key="reason",
    )

    submitted_to_manager_rows = build_submitted_to_manager_rows(applications)

    total_open_roles = len(requisitions)
    total_active_candidates = len(applications)
    total_hired = len(hired_people)

    candidates_per_open_role = round(
        total_active_candidates / total_open_roles,
        2,
    ) if total_open_roles else 0

    roles_without_candidates = sum(
        1
        for row in title_pipeline_rows
        if row["active_candidates"] == 0
    )

    roles_with_low_pipeline = sum(
        1
        for row in title_pipeline_rows
        if 0 < row["candidates_per_opening"] < LOW_PIPELINE_THRESHOLD
    )

    current_month_number = datetime.now().month

    average_hires_per_month = round(
        total_hired / current_month_number,
        2,
    ) if current_month_number else 0

    if "reason" in requisitions.columns:
        reasons = requisitions["reason"].fillna("").astype(str).str.strip().str.casefold()
    else:
        reasons = pd.Series(dtype=str)

    new_roles = int(reasons.eq("new").sum())
    backfill_roles = int(reasons.eq("backfill").sum())

    return {
        "area": clean_value(area, "Unknown"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "current_year": datetime.now().year,
        "total_open_roles": total_open_roles,
        "total_active_candidates": total_active_candidates,
        "total_hired": total_hired,
        "new_roles": new_roles,
        "backfill_roles": backfill_roles,
        "candidates_per_open_role": candidates_per_open_role,
        "roles_without_candidates": roles_without_candidates,
        "roles_with_low_pipeline": roles_with_low_pipeline,
        "average_hires_per_month": average_hires_per_month,
        "top_source": top_source,
        "top_source_share": top_source_share,
        "low_pipeline_threshold": LOW_PIPELINE_THRESHOLD,
        "roles": roles,
        "candidates": candidates,
        "stage_rows": stage_rows,
        "hires": hires,
        "title_pipeline_rows": title_pipeline_rows,
        "source_rows": source_rows,
        "hires_by_month_rows": hires_by_month_rows,
        "candidate_country_rows": candidate_country_rows,
        "working_type_rows": working_type_rows,
        "reason_rows": reason_rows,
        "submitted_to_manager_rows": submitted_to_manager_rows,
        "logo_data_uri": load_logo_data_uri(),
    }


def generate_report(
    area: str,
    requisitions_df: pd.DataFrame,
    applications_df: pd.DataFrame,
    hired_people_df: pd.DataFrame,
) -> Path:
    context = build_report_context(
        area=area,
        requisitions_df=requisitions_df,
        applications_df=applications_df,
        hired_people_df=hired_people_df,
    )

    environment = Environment(
        autoescape=select_autoescape(
            enabled_extensions=(
                "html",
                "xml",
            ),
            default_for_string=True,
        )
    )

    template = environment.from_string(
        REPORT_TEMPLATE
    )

    html = template.render(
        **context
    )

    output_directory = BASE_DIR / "output"
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_area = area.strip().lower().replace(" ", "_")

    generated_timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )

    output_file = output_directory / (
        f"{safe_area}_ta_report_{generated_timestamp}.html"
    )

    output_file.write_text(
        html,
        encoding="utf-8",
    )

    return output_file