"""
Client-facing HTML CRM intelligence report.
"""

from datetime import datetime
from html import escape
from pathlib import Path

from app.database import get_crm_intelligence_report


BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "output" / "reports"


def format_percentage(value):
    return f"{value:.1f}%"


def format_score(value):
    if value is None:
        return "N/A"
    return f"{value:.1f}"


def build_insights(report):
    database = report["database_overview"]
    quality = report["data_quality"]
    intelligence = report["lead_intelligence"]
    demand = report["demand_insights"]

    insights = []

    if intelligence["high_priority_leads"] > 0:
        insights.append(
            f"{intelligence['high_priority_leads']} high-priority "
            "lead(s) require immediate attention."
        )
    else:
        insights.append(
            "No high-priority leads were identified in this dataset."
        )

    if quality["review_required"] > 0:
        insights.append(
            f"{quality['review_required']} record(s) require manual "
            "duplicate review."
        )
    else:
        insights.append(
            "No records currently require manual duplicate review."
        )

    if demand["top_products"]:
        top_product = demand["top_products"][0]
        insights.append(
            f"{top_product['product']} generated the highest recorded "
            f"demand with {top_product['count']} lead(s)."
        )

    total_leads = database["total_leads"]

    if total_leads > 0:
        analyzed_percentage = (
            intelligence["analyzed_leads"] / total_leads
        ) * 100

        insights.append(
            f"{format_percentage(analyzed_percentage)} of leads have "
            "stored AI analysis."
        )

    if database["conversion_rate"] > 0:
        insights.append(
            f"Current conversion rate is "
            f"{format_percentage(database['conversion_rate'])}."
        )
    else:
        insights.append(
            "No converted leads are currently recorded in this dataset."
        )

    return insights


def build_actions(report):
    recommendations = report["recommended_focus"]
    actions = []

    if recommendations["high_priority_follow_up"] > 0:
        actions.append(
            f"Follow up with {recommendations['high_priority_follow_up']} "
            "high-priority lead(s)."
        )

    if recommendations["duplicate_review"] > 0:
        actions.append(
            f"Review {recommendations['duplicate_review']} "
            "possible duplicate record(s)."
        )

    if recommendations["qualified_follow_up"] > 0:
        actions.append(
            f"Follow up with {recommendations['qualified_follow_up']} "
            "qualified lead(s) that have not converted."
        )

    if recommendations["re_engagement"] > 0:
        actions.append(
            f"Consider re-engaging {recommendations['re_engagement']} "
            "lost lead(s)."
        )

    if not actions:
        actions.append(
            "Continue monitoring new leads and update statuses as activity occurs."
        )

    return actions


def status_card(label, value, css_class):
    return f"""
        <div class="stat-card">
            <div class="stat-label">{escape(label)}</div>
            <div class="stat-value {css_class}">{value}</div>
        </div>
    """


def build_html(report):
    batch = report.get("batch") or {}
    database = report["database_overview"]
    quality = report["data_quality"]
    intelligence = report["lead_intelligence"]
    demand = report["demand_insights"]

    client_name = batch.get("client_name") or "All Clients"
    dataset_name = batch.get("dataset_name") or "All CRM Data"
    generated_at = datetime.now().strftime("%d %b %Y, %H:%M")

    status_counts = database["status_counts"]
    priority_counts = intelligence["priority_counts"]

    insights = build_insights(report)
    actions = build_actions(report)

    total_leads = database["total_leads"]

    status_rows = ""

    for label, key in [
        ("New", "NEW"),
        ("Contacted", "CONTACTED"),
        ("Qualified", "QUALIFIED"),
        ("Converted", "CONVERTED"),
        ("Lost", "LOST"),
    ]:
        count = status_counts[key]

        percentage = (
            (count / total_leads * 100)
            if total_leads
            else 0
        )

        status_rows += f"""
        <div class="bar-row">
            <div class="bar-header">
                <span>{label}</span>
                <strong>{count}</strong>
            </div>
            <div class="bar-track">
                <div class="bar-fill" style="width: {percentage:.1f}%"></div>
            </div>
        </div>
        """

    product_rows = ""

    for item in demand["top_products"]:
        product_rows += f"""
        <tr>
            <td>{escape(str(item["product"]))}</td>
            <td>{item["count"]}</td>
        </tr>
        """

    if not product_rows:
        product_rows = """
        <tr>
            <td colspan="2">No product data available.</td>
        </tr>
        """

    intent_rows = ""

    for item in demand["intent_distribution"]:
        intent_rows += f"""
        <tr>
            <td>{escape(str(item["intent"]))}</td>
            <td>{item["count"]}</td>
        </tr>
        """

    if not intent_rows:
        intent_rows = """
        <tr>
            <td colspan="2">No intent data available.</td>
        </tr>
        """

    insight_html = "".join(
        f'<li>{escape(insight)}</li>'
        for insight in insights
    )

    action_html = "".join(
        f"""
        <li>
            <span class="action-number">{index}</span>
            <span>{escape(action)}</span>
        </li>
        """
        for index, action in enumerate(actions, start=1)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>
CRM Intelligence Report — {escape(client_name)}
</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    font-family:
        Inter,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    background: #f4f6f8;
    color: #17202a;
}}

.container {{
    max-width: 1180px;
    margin: 0 auto;
    padding: 40px 24px 60px;
}}

.header {{
    background: #111827;
    color: white;
    border-radius: 18px;
    padding: 36px;
    margin-bottom: 24px;
}}

.header-label {{
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    opacity: 0.7;
    margin-bottom: 10px;
}}

.header h1 {{
    margin: 0 0 12px;
    font-size: 34px;
}}

.header-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    color: #d1d5db;
    font-size: 14px;
}}

.grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}}

.stat-card {{
    background: white;
    border-radius: 14px;
    padding: 22px;
    border: 1px solid #e5e7eb;
}}

.stat-label {{
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 10px;
}}

.stat-value {{
    font-size: 30px;
    font-weight: 700;
}}

.green {{
    color: #16803c;
}}

.blue {{
    color: #2563eb;
}}

.orange {{
    color: #c2410c;
}}

.red {{
    color: #dc2626;
}}

.section-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
}}

.card {{
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 26px;
}}

.card h2 {{
    margin: 0 0 20px;
    font-size: 19px;
}}

.card-subtitle {{
    color: #6b7280;
    font-size: 13px;
    margin-top: -12px;
    margin-bottom: 20px;
}}

.bar-row {{
    margin-bottom: 17px;
}}

.bar-header {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 7px;
    font-size: 14px;
}}

.bar-track {{
    width: 100%;
    height: 8px;
    background: #edf0f2;
    border-radius: 20px;
    overflow: hidden;
}}

.bar-fill {{
    height: 100%;
    background: #2563eb;
    border-radius: 20px;
}}

.priority-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}}

.priority {{
    padding: 18px;
    border-radius: 12px;
    text-align: center;
}}

.priority strong {{
    display: block;
    font-size: 27px;
    margin-bottom: 5px;
}}

.priority span {{
    font-size: 12px;
}}

.priority-high {{
    background: #fef2f2;
    color: #b91c1c;
}}

.priority-medium {{
    background: #fff7ed;
    color: #c2410c;
}}

.priority-low {{
    background: #eff6ff;
    color: #1d4ed8;
}}

.quality-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}}

.quality-item {{
    background: #f8fafc;
    border-radius: 10px;
    padding: 15px;
}}

.quality-item span {{
    display: block;
    color: #6b7280;
    font-size: 12px;
    margin-bottom: 5px;
}}

.quality-item strong {{
    font-size: 19px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
}}

th,
td {{
    padding: 12px 0;
    text-align: left;
    border-bottom: 1px solid #edf0f2;
    font-size: 14px;
}}

th {{
    color: #6b7280;
    font-weight: 500;
}}

.insights {{
    background: #111827;
    color: white;
}}

.insights h2 {{
    color: white;
}}

.insights ul {{
    padding-left: 22px;
    margin: 0;
}}

.insights li {{
    margin-bottom: 13px;
    line-height: 1.5;
    color: #e5e7eb;
}}

.actions {{
    background: #f8fafc;
}}

.actions ul {{
    list-style: none;
    padding: 0;
    margin: 0;
}}

.actions li {{
    display: flex;
    gap: 13px;
    align-items: flex-start;
    padding: 13px 0;
    border-bottom: 1px solid #e5e7eb;
    line-height: 1.5;
}}

.action-number {{
    flex: 0 0 26px;
    height: 26px;
    border-radius: 50%;
    background: #2563eb;
    color: white;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
}}

.footer {{
    text-align: center;
    color: #9ca3af;
    font-size: 12px;
    margin-top: 28px;
}}

@media (max-width: 850px) {{
    .grid {{
        grid-template-columns: repeat(2, 1fr);
    }}

    .section-grid {{
        grid-template-columns: 1fr;
    }}
}}

@media (max-width: 520px) {{
    .container {{
        padding: 20px 14px 40px;
    }}

    .header {{
        padding: 25px;
    }}

    .header h1 {{
        font-size: 27px;
    }}

    .grid {{
        grid-template-columns: 1fr;
    }}
}}

</style>
</head>

<body>

<div class="container">

    <header class="header">

        <div class="header-label">
            CRM Intelligence
        </div>

        <h1>
            {escape(client_name)}
        </h1>

        <div class="header-meta">
            <span>
                Dataset: {escape(dataset_name)}
            </span>

            <span>
                Generated: {generated_at}
            </span>
        </div>

    </header>


    <section class="grid">

        {status_card(
            "Total Leads",
            database["total_leads"],
            "blue"
        )}

        {status_card(
            "Data Quality",
            format_percentage(quality["data_quality_rate"]),
            "green"
        )}

        {status_card(
            "Average Lead Score",
            format_score(intelligence["average_lead_score"]),
            "orange"
        )}

        {status_card(
            "Conversion Rate",
            format_percentage(database["conversion_rate"]),
            "green"
        )}

    </section>


    <section class="section-grid">

        <div class="card">

            <h2>Lead Pipeline</h2>

            <p class="card-subtitle">
                Current distribution of leads by CRM status.
            </p>

            {status_rows}

        </div>


        <div class="card">

            <h2>Lead Priority</h2>

            <p class="card-subtitle">
                Priority distribution based on stored CRM analysis.
            </p>

            <div class="priority-grid">

                <div class="priority priority-high">
                    <strong>{priority_counts["HIGH"]}</strong>
                    <span>High Priority</span>
                </div>

                <div class="priority priority-medium">
                    <strong>{priority_counts["MEDIUM"]}</strong>
                    <span>Medium Priority</span>
                </div>

                <div class="priority priority-low">
                    <strong>{priority_counts["LOW"]}</strong>
                    <span>Low Priority</span>
                </div>

            </div>

            <br>

            <div class="quality-grid">

                <div class="quality-item">
                    <span>AI Analyzed</span>
                    <strong>{intelligence["analyzed_leads"]}</strong>
                </div>

                <div class="quality-item">
                    <span>Not Analyzed</span>
                    <strong>{intelligence["unanalyzed_leads"]}</strong>
                </div>

                <div class="quality-item">
                    <span>Duplicate Records</span>
                    <strong>{quality["duplicate_records"]}</strong>
                </div>

                <div class="quality-item">
                    <span>Review Required</span>
                    <strong>{quality["review_required"]}</strong>
                </div>

            </div>

        </div>

    </section>


    <section class="section-grid">

        <div class="card">

            <h2>Data Quality</h2>

            <p class="card-subtitle">
                Record completeness and duplicate health.
            </p>

            <div class="quality-grid">

                <div class="quality-item">
                    <span>Quality Rate</span>
                    <strong>
                        {format_percentage(quality["data_quality_rate"])}
                    </strong>
                </div>

                <div class="quality-item">
                    <span>Missing Information</span>
                    <strong>
                        {quality["missing_information_total"]}
                    </strong>
                </div>

                <div class="quality-item">
                    <span>Confirmed Duplicates</span>
                    <strong>
                        {quality["confirmed_duplicates"]}
                    </strong>
                </div>

                <div class="quality-item">
                    <span>Manual Review</span>
                    <strong>
                        {quality["review_required"]}
                    </strong>
                </div>

            </div>

        </div>


        <div class="card">

            <h2>Product Demand</h2>

            <p class="card-subtitle">
                Products mentioned across the dataset.
            </p>

            <table>

                <thead>
                    <tr>
                        <th>Product</th>
                        <th>Leads</th>
                    </tr>
                </thead>

                <tbody>
                    {product_rows}
                </tbody>

            </table>

        </div>

    </section>


    <section class="section-grid">

        <div class="card">

            <h2>Lead Intent</h2>

            <p class="card-subtitle">
                Distribution of recorded lead intent.
            </p>

            <table>

                <thead>
                    <tr>
                        <th>Intent</th>
                        <th>Leads</th>
                    </tr>
                </thead>

                <tbody>
                    {intent_rows}
                </tbody>

            </table>

        </div>


        <div class="card insights">

            <h2>Top Insights</h2>

            <ul>
                {insight_html}
            </ul>

        </div>

    </section>


    <section class="card actions">

        <h2>Recommended Actions</h2>

        <p class="card-subtitle">
            Suggested operational next steps based on the current CRM data.
        </p>

        <ul>
            {action_html}
        </ul>

    </section>


    <div class="footer">
        CRM Intelligence Report · Generated from CRM data
    </div>

</div>

</body>
</html>
"""


def generate_html_report(batch_id=None):
    """Generate and save an HTML CRM intelligence report."""

    report = get_crm_intelligence_report(batch_id)

    html = build_html(report)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if batch_id is not None:
        filename = f"crm_intelligence_report_batch_{batch_id}.html"
    else:
        filename = "crm_intelligence_report.html"

    report_path = REPORTS_DIR / filename

    report_path.write_text(
        html,
        encoding="utf-8",
    )

    return {
        "path": str(report_path),
        "batch_id": batch_id,
    }


def main():
    print()
    print("=" * 70)
    print("CRM HTML REPORT GENERATOR")
    print("=" * 70)
    print()

    batch_input = input(
        "Enter batch ID (press Enter for all CRM data): "
    ).strip()

    if batch_input:
        try:
            batch_id = int(batch_input)
        except ValueError:
            print("Invalid batch ID.")
            return
    else:
        batch_id = None

    try:
        result = generate_html_report(batch_id)

        print()
        print("HTML report generated successfully.")
        print()
        print(f"Saved to:")
        print(result["path"])
        print()

    except Exception as error:
        print()
        print("REPORT GENERATION FAILED")
        print(f"Error: {error}")


if __name__ == "__main__":
    main()