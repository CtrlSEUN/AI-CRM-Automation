"""
Client-facing CRM intelligence reporting.

Generates both TXT and HTML client reports from CRM intelligence data.
"""

from datetime import datetime
from pathlib import Path

from app.database import get_crm_intelligence_report
from app.crm_report_html import generate_html_report


BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "output" / "reports"


def format_percentage(value):
    """Format a numeric percentage cleanly."""
    return f"{value:.1f}%"


def format_score(value):
    """Format an average lead score."""
    if value is None:
        return "N/A"

    return f"{value:.1f}"


def build_top_insights(report):
    """Generate plain-English business insights."""

    insights = []

    database = report["database_overview"]
    quality = report["data_quality"]
    intelligence = report["lead_intelligence"]
    demand = report["demand_insights"]

    total_leads = database["total_leads"]

    if intelligence["high_priority_leads"] > 0:
        insights.append(
            f'{intelligence["high_priority_leads"]} lead(s) require immediate attention.'
        )
    else:
        insights.append(
            "No high-priority leads were identified in this dataset."
        )

    if quality["review_required"] > 0:
        insights.append(
            f'{quality["review_required"]} record(s) require manual duplicate review.'
        )
    else:
        insights.append(
            "No records currently require manual duplicate review."
        )

    if demand["top_products"]:
        top_product = demand["top_products"][0]

        insights.append(
            f'{top_product["product"]} generated the highest recorded product demand '
            f'with {top_product["count"]} lead(s).'
        )
    else:
        insights.append(
            "No product demand data is currently available."
        )

    if total_leads > 0 and intelligence["analyzed_leads"] > 0:
        analyzed_percentage = (
            intelligence["analyzed_leads"] / total_leads
        ) * 100

        insights.append(
            f"{format_percentage(analyzed_percentage)} of leads "
            "have stored AI analysis."
        )

    if database["conversion_rate"] > 0:
        insights.append(
            f'Current conversion rate is '
            f'{format_percentage(database["conversion_rate"])}.'
        )
    else:
        insights.append(
            "No converted leads are currently recorded in this dataset."
        )

    return insights


def build_recommended_actions(report):
    """Generate practical next actions from CRM data."""

    actions = []

    recommendations = report["recommended_focus"]

    if recommendations["high_priority_follow_up"] > 0:
        actions.append(
            f'Follow up with {recommendations["high_priority_follow_up"]} '
            "high-priority lead(s)."
        )

    if recommendations["duplicate_review"] > 0:
        actions.append(
            f'Review {recommendations["duplicate_review"]} '
            "possible duplicate record(s) before contacting them."
        )

    if recommendations["qualified_follow_up"] > 0:
        actions.append(
            f'Follow up with {recommendations["qualified_follow_up"]} '
            "qualified lead(s) that have not yet converted."
        )

    if recommendations["re_engagement"] > 0:
        actions.append(
            f'Re-engage {recommendations["re_engagement"]} '
            "lost lead(s) where appropriate."
        )

    if not actions:
        actions.append(
            "Continue monitoring new leads and update lead statuses as activity occurs."
        )

    return actions


def build_report_text(report):
    """Build the complete client-facing CRM intelligence report."""

    batch = report.get("batch") or {}
    database = report["database_overview"]
    quality = report["data_quality"]
    intelligence = report["lead_intelligence"]
    demand = report["demand_insights"]

    client_name = batch.get("client_name") or "All Clients"
    dataset_name = batch.get("dataset_name") or "All CRM Data"

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_counts = database["status_counts"]
    priority_counts = intelligence["priority_counts"]

    insights = build_top_insights(report)
    actions = build_recommended_actions(report)

    lines = []

    lines.append("=" * 70)
    lines.append("CRM INTELLIGENCE REPORT")
    lines.append("=" * 70)
    lines.append("")
    lines.append(f"Client:     {client_name}")
    lines.append(f"Dataset:    {dataset_name}")
    lines.append(f"Generated:  {generated_at}")
    lines.append("")

    lines.append("DATABASE OVERVIEW")
    lines.append("-" * 70)
    lines.append(f"Total Leads:        {database['total_leads']}")
    lines.append(f"New Leads:          {status_counts['NEW']}")
    lines.append(f"Contacted:          {status_counts['CONTACTED']}")
    lines.append(f"Qualified:          {status_counts['QUALIFIED']}")
    lines.append(f"Converted:          {status_counts['CONVERTED']}")
    lines.append(f"Lost:               {status_counts['LOST']}")
    lines.append(
        f"Conversion Rate:    {format_percentage(database['conversion_rate'])}"
    )
    lines.append("")

    lines.append("DATA QUALITY")
    lines.append("-" * 70)
    lines.append(
        f"Data Quality Rate:  {format_percentage(quality['data_quality_rate'])}"
    )
    lines.append(f"Duplicate Records:  {quality['duplicate_records']}")
    lines.append(
        f"Confirmed Duplicates:{quality['confirmed_duplicates']:>3}"
    )
    lines.append(f"Review Required:    {quality['review_required']}")
    lines.append(
        f"Missing Information:{quality['missing_information_total']:>3}"
    )
    lines.append("")

    lines.append("LEAD INTELLIGENCE")
    lines.append("-" * 70)
    lines.append(f"High Priority:      {priority_counts['HIGH']}")
    lines.append(f"Medium Priority:    {priority_counts['MEDIUM']}")
    lines.append(f"Low Priority:       {priority_counts['LOW']}")
    lines.append(
        f"Average Lead Score: "
        f"{format_score(intelligence['average_lead_score'])}"
    )
    lines.append(f"AI Analyzed:        {intelligence['analyzed_leads']}")
    lines.append(f"Not Analyzed:       {intelligence['unanalyzed_leads']}")
    lines.append("")

    lines.append("DEMAND INSIGHTS")
    lines.append("-" * 70)

    if demand["top_products"]:
        lines.append("Top Products:")

        for item in demand["top_products"]:
            lines.append(
                f"  • {item['product']}: {item['count']} lead(s)"
            )
    else:
        lines.append(
            "Top Products: No product data available."
        )

    lines.append("")

    if demand["intent_distribution"]:
        lines.append("Lead Intent:")

        for item in demand["intent_distribution"]:
            lines.append(
                f"  • {item['intent']}: {item['count']} lead(s)"
            )
    else:
        lines.append(
            "Lead Intent: No intent data available."
        )

    lines.append("")

    lines.append("TOP INSIGHTS")
    lines.append("-" * 70)

    for insight in insights:
        lines.append(f"• {insight}")

    lines.append("")

    lines.append("RECOMMENDED ACTIONS")
    lines.append("-" * 70)

    for index, action in enumerate(actions, start=1):
        lines.append(f"{index}. {action}")

    lines.append("")
    lines.append("=" * 70)
    lines.append("End of CRM Intelligence Report")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_txt_report(report, batch_id=None):
    """Generate and save the plain-text CRM report."""

    report_text = build_report_text(report)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if batch_id is not None:
        filename = f"crm_intelligence_report_batch_{batch_id}.txt"
    else:
        filename = "crm_intelligence_report.txt"

    report_path = REPORTS_DIR / filename

    report_path.write_text(
        report_text,
        encoding="utf-8",
    )

    return report_path


def generate_client_report(batch_id=None):
    """
    Generate the complete client report package.

    Creates both TXT and HTML versions using the same CRM data.
    """

    report = get_crm_intelligence_report(batch_id)

    txt_path = generate_txt_report(
        report,
        batch_id=batch_id,
    )

    html_result = generate_html_report(
        batch_id=batch_id,
    )

    return {
        "batch_id": batch_id,
        "txt_path": str(txt_path),
        "html_path": html_result["path"],
        "report": report,
    }


def generate_crm_report(batch_id=None):
    """
    Backward-compatible TXT report generator.

    Existing code can continue calling this function.
    """

    report = get_crm_intelligence_report(batch_id)

    report_path = generate_txt_report(
        report,
        batch_id=batch_id,
    )

    return {
        "report": build_report_text(report),
        "path": str(report_path),
        "batch_id": batch_id,
    }


def main():
    """Generate the complete client-facing report package."""

    print()
    print("=" * 70)
    print("CRM CLIENT REPORT GENERATOR")
    print("=" * 70)
    print()

    batch_input = input(
        "Enter batch ID (press Enter for all CRM data): "
    ).strip()

    if batch_input:
        try:
            batch_id = int(batch_input)
        except ValueError:
            print("Invalid batch ID. Please enter a number.")
            return
    else:
        batch_id = None

    try:
        result = generate_client_report(batch_id)

        print()
        print("=" * 70)
        print("CLIENT REPORT PACKAGE GENERATED")
        print("=" * 70)
        print()
        print("TXT report:")
        print(result["txt_path"])
        print()
        print("HTML report:")
        print(result["html_path"])
        print()
        print("Both reports are ready for client delivery.")
        print()

    except Exception as error:
        print()
        print("=" * 70)
        print("REPORT GENERATION FAILED")
        print("=" * 70)
        print(f"Error: {error}")
        print("=" * 70)


if __name__ == "__main__":
    main()