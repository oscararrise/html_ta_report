from pathlib import Path

path = Path("generate_report.py")
text = path.read_text(encoding="utf-8")

functions = '''
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

'''

if "def build_count_rows(" not in text:
    text = text.replace("def build_report_context(", functions + "\ndef build_report_context(")

insert_after = '''    source_rows, top_source, top_source_share = build_source_rows(
        applications
    )
'''

extra_context_build = '''
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
'''

if "hires_by_month_rows = build_hires_by_month_rows" not in text:
    text = text.replace(insert_after, insert_after + extra_context_build)

return_insert = '''        "source_rows": source_rows,
'''

return_extra = '''        "hires_by_month_rows": hires_by_month_rows,
        "candidate_country_rows": candidate_country_rows,
        "working_type_rows": working_type_rows,
        "reason_rows": reason_rows,
'''

if '"hires_by_month_rows": hires_by_month_rows' not in text:
    text = text.replace(return_insert, return_insert + return_extra)

path.write_text(text, encoding="utf-8")
print("generate_report.py context patched")
