from pathlib import Path

path = Path("generate_report.py")
text = path.read_text(encoding="utf-8")

html = """
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
"""

anchor = """        <div class="source-note">
                    <strong>Top candidate source:</strong>
                    {{ top_source }}

                    <br>

                    <strong>Share of active pipeline:</strong>
                    {{ top_source_share }}%
                </div>
"""

if 'Submitted to Manager' not in text:
    text = text.replace(anchor, anchor + html)

function = '''
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

'''

if "def build_submitted_to_manager_rows(" not in text:
    text = text.replace("def build_report_context(", function + "\ndef build_report_context(")

context_anchor = """    reason_rows = build_count_rows(
        requisitions,
        column_name="reason",
        label_key="reason",
    )
"""

context_insert = """
    submitted_to_manager_rows = build_submitted_to_manager_rows(applications)
"""

if "submitted_to_manager_rows = build_submitted_to_manager_rows" not in text:
    text = text.replace(context_anchor, context_anchor + context_insert)

return_anchor = '''        "reason_rows": reason_rows,
'''

return_insert = '''        "submitted_to_manager_rows": submitted_to_manager_rows,
'''

if '"submitted_to_manager_rows": submitted_to_manager_rows' not in text:
    text = text.replace(return_anchor, return_anchor + return_insert)

path.write_text(text, encoding="utf-8")
print("Submitted to manager section added")
