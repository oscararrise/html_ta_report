from pathlib import Path

path = Path("generate_report.py")
text = path.read_text(encoding="utf-8")

css = """
.insight-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 20px;
}

.line-chart {
    display: flex;
    align-items: end;
    gap: 10px;
    height: 220px;
    padding-top: 20px;
}

.line-bar {
    flex: 1;
    min-height: 4px;
    border-radius: 12px 12px 0 0;
    background: linear-gradient(180deg, var(--neo-jade), var(--rare-sky));
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
"""

html = """
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
                        <div class="line-bar" title="{{ month.month }}: {{ month.total }}" style="height: {{ month.height }}%;"></div>
                        <div class="line-label">{{ month.month_short }}</div>
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
"""

if ".insight-grid" not in text:
    text = text.replace("</style>", css + "\n</style>")

if 'id="final-insights"' not in text:
    text = text.replace('    <div class="footer">', html + '\n    <div class="footer">')

path.write_text(text, encoding="utf-8")
print("generate_report.py patched")
