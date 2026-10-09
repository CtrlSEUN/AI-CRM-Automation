import streamlit as st
import pandas as pd

from pathlib import Path
from io import BytesIO
from html import escape

from bulk_cleanup import (
    create_run_directory,
    standardize_dataset,
    validate_dataset,
    detect_duplicates,
    calculate_quality_metrics,
    calculate_quality_health,
    export_results,
)

from app.database import (
    get_crm_intelligence_report,
    get_connection,
    save_lead_analysis,
    get_lead_action_status,
    update_lead_action_status,
    get_follow_up_queue,
    get_follow_up_metrics,
)

from app.lead_analyzer import analyze_lead


# ========================================
# PAGE CONFIGURATION
# ========================================

st.set_page_config(
    page_title="CRM Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ========================================
# PROJECT PATHS
# ========================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ========================================
# HELPER FUNCTIONS
# ========================================

def safe_int(value, default=0):
    """Safely convert a value to an integer."""

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    """Safely convert a value to a float."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_first_value(data, keys, default=None):
    """Return the first matching key from a dictionary."""

    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data:
            return data[key]

    return default


def normalize_label(value):
    """Convert backend keys into readable labels."""

    return (
        str(value)
        .replace("_", " ")
        .replace("-", " ")
        .strip()
        .title()
    )


def get_batch_id_from_result(result):
    """Try to extract the imported CRM batch ID from export results."""

    if not isinstance(result, dict):
        return None

    possible_paths = [
        ("batch_id",),
        ("database_result", "batch_id"),
        ("database", "batch_id"),
        ("import_result", "batch_id"),
        ("database_result", "import_batch_id"),
    ]

    for path in possible_paths:

        current = result

        for key in path:

            if not isinstance(current, dict):
                current = None
                break

            current = current.get(key)

        if current is not None:

            try:
                return int(current)

            except (TypeError, ValueError):

                return current

    return None


def find_nested_dict(data, possible_keys):
    """Find a dictionary using several possible backend key names."""

    if not isinstance(data, dict):
        return {}

    for key in possible_keys:

        value = data.get(key)

        if isinstance(value, dict):
            return value

    return {}


def extract_count_mapping(data):
    """
    Convert backend count structures into a clean
    dictionary for the dashboard.

    Supports both:
    - {"HIGH": 0, "LOW": 3, "MEDIUM": 0}
    - [{"intent": "Research", "count": 3}]
    """

    if isinstance(data, dict):

        output = {}

        for key, value in data.items():

            if isinstance(value, (int, float)):
                output[normalize_label(key)] = value

        return output

    if isinstance(data, list):

        output = {}

        for item in data:

            if not isinstance(item, dict):
                continue

            label = (
                item.get("intent")
                or item.get("priority")
                or item.get("product")
                or item.get("label")
                or item.get("name")
                or item.get("category")
            )

            count = item.get("count")

            if label is not None and isinstance(
                count,
                (int, float),
            ):
                output[normalize_label(label)] = count

        return output

    return {}


def extract_intelligence_metrics(report):
    """
    Extract important CRM intelligence metrics.

    Several possible backend key names are supported so
    small backend structure changes do not break the UI.
    """

    lead_intelligence = find_nested_dict(
        report,
        [
            "lead_intelligence",
            "lead_intelligence_summary",
            "lead_analysis",
        ],
    )

    database_overview = find_nested_dict(
        report,
        [
            "database_overview",
            "overview",
        ],
    )

    demand_insights = find_nested_dict(
        report,
        [
            "demand_insights",
            "demand",
            "market_demand",
        ],
    )

    batch_info = find_nested_dict(
        report,
        [
            "batch",
            "batch_info",
        ],
    )

    priority_counts = find_nested_dict(
        lead_intelligence,
        [
            "priority_counts",
            "priorities",
            "priority_distribution",
        ],
    )

    if not priority_counts:
        priority_counts = find_nested_dict(
            report,
            [
                "priority_counts",
                "priorities",
                "priority_distribution",
            ],
        )

    intent_counts = {}

    if isinstance(demand_insights, dict):
        for key in (
            "intent_distribution",
            "intent_counts",
            "intents",
        ):
            if key in demand_insights:
                intent_counts = demand_insights[key]
                break

    if not intent_counts and isinstance(lead_intelligence, dict):
        for key in (
            "intent_distribution",
            "intent_counts",
            "intents",
        ):
            if key in lead_intelligence:
                intent_counts = lead_intelligence[key]
                break

    product_counts = find_nested_dict(
        demand_insights,
        [
            "top_products",
            "product_demand",
            "product_counts",
            "products",
        ],
    )

    if not product_counts:
        product_counts = find_nested_dict(
            lead_intelligence,
            [
                "top_products",
                "product_demand",
                "product_counts",
                "products",
            ],
        )

    recommended_focus = find_nested_dict(
        report,
        [
            "recommended_focus",
            "recommended_actions",
            "recommendations",
        ],
    )

    average_score = get_first_value(
        lead_intelligence,
        [
            "average_lead_score",
            "avg_lead_score",
            "average_score",
            "mean_lead_score",
        ],
        0,
    )

    analyzed_leads = get_first_value(
        lead_intelligence,
        [
            "analyzed_leads",
            "ai_analyzed",
            "analyzed",
        ],
        0,
    )

    # Priority distribution is the source of truth for
    # the Lead Signals cards. Backend priority keys may
    # arrive as HIGH / MEDIUM / LOW.

    normalized_priority_counts = {
        str(key).strip().lower(): safe_int(value)
        for key, value in priority_counts.items()
    }

    high_priority = normalized_priority_counts.get(
        "high",
        0,
    )

    medium_priority = normalized_priority_counts.get(
        "medium",
        0,
    )

    low_priority = normalized_priority_counts.get(
        "low",
        0,
    )

    total_leads = get_first_value(
        database_overview,
        [
            "total_leads",
            "total_records",
            "leads",
        ],
        0,
    )

    if not total_leads:
        total_leads = get_first_value(
            batch_info,
            [
                "imported_count",
                "imported",
                "records",
            ],
            0,
        )

    # Prefer an explicit backend pending/unanalyzed count.
    # Fall back to total - analyzed when the backend does not
    # provide one directly.
    unanalyzed_leads = get_first_value(
        lead_intelligence,
        [
            "unanalyzed_leads",
            "pending_leads",
            "ai_pending",
            "unanalyzed",
            "pending",
        ],
        None,
    )

    if unanalyzed_leads is None:
        unanalyzed_leads = max(
            safe_int(total_leads) - safe_int(analyzed_leads),
            0,
        )

    return {
        "average_score": safe_float(
            average_score
        ),
        "analyzed_leads": safe_int(
            analyzed_leads
        ),
        "unanalyzed_leads": safe_int(
            unanalyzed_leads
        ),
        "high_priority": safe_int(
            high_priority
        ),
        "medium_priority": safe_int(
            medium_priority
        ),
        "low_priority": safe_int(
            low_priority
        ),
        "total_leads": safe_int(
            total_leads
        ),
        "priority_counts": extract_count_mapping(
            priority_counts
        ),
        "intent_counts": extract_count_mapping(
            intent_counts
        ),
        "product_counts": extract_count_mapping(
            product_counts
        ),
        "recommended_focus": extract_count_mapping(
            recommended_focus
        ),
    }


def find_existing_intelligence_batch(
    dataframe,
    current_batch_id=None,
):
    """
    Find the existing CRM batch containing complete AI intelligence
    for the uploaded records.

    This fixes the re-run case where a new import batch is
    created with zero imported records because all records
    already exist in the CRM.

    The lookup is based on normalized email addresses.

    A record is considered AI-analyzed only when all core
    intelligence fields are present.
    """

    if dataframe is None:
        return None

    if "email" not in dataframe.columns:
        return None

    emails = []

    for value in dataframe["email"].tolist():

        if value is None:
            continue

        email = str(value).strip().lower()

        if email and email != "nan":
            emails.append(email)

    if not emails:
        return None

    emails = list(dict.fromkeys(emails))

    connection = None

    try:

        connection = get_connection()

        cursor = connection.cursor()

        placeholders = ",".join(
            ["?"] * len(emails)
        )

        cursor.execute(
            f"""
            SELECT
                import_batch_id,
                COUNT(*) AS matched_records,
                COUNT(
                    CASE
                        WHEN lead_type IS NOT NULL
                         AND intent IS NOT NULL
                         AND product IS NOT NULL
                         AND priority IS NOT NULL
                         AND lead_score IS NOT NULL
                         AND summary IS NOT NULL
                        THEN 1
                    END
                ) AS analyzed_records
            FROM leads
            WHERE LOWER(TRIM(email)) IN ({placeholders})
              AND import_batch_id IS NOT NULL
            GROUP BY import_batch_id
            ORDER BY analyzed_records DESC,
                     matched_records DESC,
                     import_batch_id DESC
            """,
            emails,
        )

        rows = cursor.fetchall()

        if not rows:
            return None

        for row in rows:

            batch_id = row[0]
            analyzed_records = safe_int(
                row[2]
            )

            if analyzed_records > 0:
                return batch_id

        return None

    except Exception:

        return None

    finally:

        if connection is not None:

            try:
                connection.close()
            except Exception:
                pass



def get_existing_leads_for_dataframe(dataframe):
    """Return existing CRM lead IDs and source data for uploaded records."""
    if dataframe is None or "email" not in dataframe.columns:
        return []

    emails = []
    for value in dataframe["email"].tolist():
        email = str(value or "").strip().lower()
        if email and email != "nan":
            emails.append(email)

    emails = list(dict.fromkeys(emails))
    if not emails:
        return []

    connection = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        placeholders = ",".join(["?"] * len(emails))
        cursor.execute(
            f"""
            SELECT id, name, email, phone, company, message
            FROM leads
            WHERE LOWER(TRIM(email)) IN ({placeholders})
            ORDER BY id ASC
            """,
            emails,
        )
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def reanalyze_uploaded_leads(dataframe):
    """Re-run NVIDIA AI analysis for existing CRM records represented by the CSV."""
    rows = get_existing_leads_for_dataframe(dataframe)
    attempted = 0
    completed = 0
    failed = 0
    errors = []

    for lead_id, name, email, phone, company, message in rows:
        attempted += 1
        lead = {
            "name": str(name or "").strip(),
            "email": str(email or "").strip().lower(),
            "phone": str(phone or "").strip(),
            "company": str(company or "").strip(),
            "message": str(message or "").strip(),
        }
        try:
            analysis = analyze_lead(lead)
            saved = save_lead_analysis(lead_id, analysis)
            if not saved:
                raise RuntimeError(
                    f"AI analysis could not be saved for lead ID {lead_id}."
                )
            completed += 1
        except Exception as error:
            failed += 1
            errors.append(
                f"{name or email}: {error}"
            )

    return {
        "total": attempted,
        "analyzed": completed,
        "failed": failed,
        "errors": errors,
    }

def render_distribution_card(
    title,
    items,
):
    """Render a polished category distribution card."""

    if not items:
        return

    cleaned_items = []

    for label, value in items.items():

        try:

            numeric_value = float(value)

        except (TypeError, ValueError):

            continue

        if numeric_value < 0:
            continue

        cleaned_items.append(
            (
                str(label),
                numeric_value,
            )
        )

    if not cleaned_items:
        return

    cleaned_items.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    total = sum(
        value
        for _, value in cleaned_items
    )

    rows = ""

    for label, value in cleaned_items[:8]:

        percentage = (
            (value / total) * 100
            if total > 0
            else 0
        )

        safe_label = escape(
            label
        )

        rows += f"""
        <div class="intel-row">

            <div class="intel-row-header">

                <span class="intel-row-label">
                    {safe_label}
                </span>

                <span class="intel-row-value">
                    {safe_int(value)}
                </span>

            </div>

            <div class="intel-progress">

                <div
                    class="intel-progress-fill"
                    style="width: {max(0, min(100, percentage))}%"
                ></div>

            </div>

        </div>
        """

    st.html(
        f"""
        <div class="dashboard-card intelligence-card">

            <div class="dashboard-card-title">
                {escape(title)}
            </div>

            {rows}

        </div>
        """
    )


def get_top_opportunities(
    batch_id,
):
    """
    Retrieve the highest-scoring AI-analyzed leads
    from the intelligence batch.
    """

    if batch_id is None:
        return []

    connection = None

    try:

        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                company,
                email,
                product,
                intent,
                priority,
                lead_score,
                summary
            FROM leads
            WHERE import_batch_id = ?
              AND lead_type IS NOT NULL
              AND intent IS NOT NULL
              AND product IS NOT NULL
              AND priority IS NOT NULL
              AND lead_score IS NOT NULL
              AND summary IS NOT NULL
            ORDER BY lead_score DESC,
                     id ASC
            LIMIT 5
            """,
            (batch_id,),
        )

        rows = cursor.fetchall()

        return rows

    except Exception:

        return []

    finally:

        if connection is not None:

            try:
                connection.close()
            except Exception:
                pass


def render_opportunity_table(
    opportunities,
):
    """Render the highest-scoring CRM opportunities."""

    if not opportunities:
        return

    rows = ""

    for row in opportunities:

        (
            lead_id,
            name,
            company,
            email,
            product,
            intent,
            priority,
            score,
            summary,
        ) = row

        priority_text = str(
            priority or "UNKNOWN"
        ).upper()

        if priority_text == "HIGH":

            badge_class = (
                "opportunity-high"
            )

        elif priority_text == "MEDIUM":

            badge_class = (
                "opportunity-medium"
            )

        else:

            badge_class = (
                "opportunity-low"
            )

        rows += f"""
        <div class="opportunity-row">

            <div class="opportunity-main">

                <div class="opportunity-name">
                    {escape(
                        str(
                            name or
                            "Unknown lead"
                        )
                    )}
                </div>

                <div class="opportunity-company">
                    {escape(
                        str(
                            company or
                            "Unknown company"
                        )
                    )}
                </div>

            </div>

            <div class="opportunity-detail">
                {escape(
                    str(
                        product or
                        "Unknown"
                    )
                )}
            </div>

            <div class="opportunity-detail">
                {escape(
                    str(
                        intent or
                        "Unknown"
                    )
                )}
            </div>

            <div class="opportunity-priority {badge_class}">
                {escape(priority_text)}
            </div>

            <div class="opportunity-score">
                {safe_int(score)}
            </div>

        </div>
        """

    st.html(
        f"""
        <div class="dashboard-card opportunity-card">

            <div class="dashboard-card-title">
                Top opportunities
            </div>

            <div class="opportunity-header">

                <span>Lead</span>
                <span>Product</span>
                <span>Intent</span>
                <span>Priority</span>
                <span>Score</span>

            </div>

            {rows}

        </div>
        """
    )


def get_recommended_actions(
    batch_id,
):
    """Return lead-level recommended actions for one CRM batch."""

    if not batch_id:
        return []

    connection = None

    try:
        connection = get_connection()

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                company,
                priority,
                lead_score,
                recommended_action,
                follow_up_timing
            FROM leads
            WHERE import_batch_id = ?
              AND recommended_action IS NOT NULL
              AND TRIM(recommended_action) != ''
            ORDER BY
                CASE UPPER(priority)
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'LOW' THEN 3
                    ELSE 4
                END,
                lead_score DESC,
                id ASC
            LIMIT 10
            """,
            (
                batch_id,
            ),
        )

        return cursor.fetchall()

    except Exception:
        return []

    finally:

        if connection:

            try:
                connection.close()

            except Exception:
                pass


def render_follow_up_metrics(metrics):
    """Render follow-up workload, priority, and completion metrics."""

    st.html(
        """
        <div class="section-title">
            Follow-up performance
        </div>
        """
    )

    st.caption(
        "Overview of recommended actions for the selected intelligence batch. "
        "Skipped actions are excluded from the completion-rate calculation."
    )

    needs_attention = (
        metrics["pending"] + metrics["in_progress"]
    )

    columns = st.columns(4)

    columns[0].metric(
        "Needs Attention",
        needs_attention,
    )
    columns[1].metric(
        "Pending",
        metrics["pending"],
    )
    columns[2].metric(
        "In Progress",
        metrics["in_progress"],
    )
    columns[3].metric(
        "Completion Rate",
        f'{metrics["completion_rate"]:.2f}%',
    )

    columns = st.columns(5)

    columns[0].metric(
        "Completed",
        metrics["completed"],
    )
    columns[1].metric(
        "Skipped",
        metrics["skipped"],
    )
    columns[2].metric(
        "High Priority",
        metrics["high"],
    )
    columns[3].metric(
        "Medium Priority",
        metrics["medium"],
    )
    columns[4].metric(
        "Low Priority",
        metrics["low"],
    )


def render_follow_up_queue(queue):
    """Render active leads that need salesperson follow-up."""

    if not queue:
        st.info("No leads currently need follow-up.")
        return

    for row in queue:

        (
            lead_id,
            name,
            company,
            priority,
            lead_score,
            recommended_action,
            follow_up_timing,
            action_status,
            action_completed_at,
            lead_status,
        ) = row

        priority_text = str(
            priority or "LOW"
        ).upper()

        if priority_text == "HIGH":
            badge_class = "opportunity-high"
        elif priority_text == "MEDIUM":
            badge_class = "opportunity-medium"
        else:
            badge_class = "opportunity-low"

        st.html(
            f"""
            <div class="dashboard-card opportunity-card">

                <div class="opportunity-row">

                    <div class="opportunity-main">

                        <div class="opportunity-name">
                            {escape(
                                str(
                                    name or
                                    "Unknown lead"
                                )
                            )}
                        </div>

                        <div class="opportunity-company">
                            {escape(
                                str(
                                    company or
                                    "Unknown company"
                                )
                            )}
                        </div>

                    </div>

                    <div class="opportunity-detail">
                        <strong>Recommended action</strong><br>
                        {escape(
                            str(
                                recommended_action or
                                "No recommendation"
                            )
                        )}
                    </div>

                    <div class="opportunity-detail">
                        <strong>Follow-up</strong><br>
                        {escape(
                            str(
                                follow_up_timing or
                                "Not specified"
                            )
                        )}
                    </div>

                    <div class="opportunity-priority {badge_class}">
                        {escape(priority_text)}
                    </div>

                    <div class="opportunity-score">
                        {safe_int(lead_score)}
                    </div>

                </div>

            </div>
            """
        )

        status_text = str(
            action_status or "PENDING"
        ).upper()

        if action_completed_at:
            st.caption(
                f"Completed at: {action_completed_at}"
            )
        else:
            st.caption(
                f"Action status: {status_text}"
            )

        st.divider()


def render_recommended_actions(
    actions,
):
    """Render lead-level recommended next actions with action tracking."""

    if not actions:
        return

    status_options = [
        "PENDING",
        "IN PROGRESS",
        "COMPLETED",
        "SKIPPED",
    ]

    for row in actions:

        (
            lead_id,
            name,
            company,
            priority,
            lead_score,
            recommended_action,
            follow_up_timing,
        ) = row

        current_state = get_lead_action_status(
            safe_int(lead_id)
        )

        current_status = (
            current_state.get("action_status", "PENDING")
            if current_state
            else "PENDING"
        )

        completed_at = (
            current_state.get("action_completed_at")
            if current_state
            else None
        )

        priority_text = str(
            priority or "UNKNOWN"
        ).upper()

        if priority_text == "HIGH":

            badge_class = (
                "opportunity-high"
            )

        elif priority_text == "MEDIUM":

            badge_class = (
                "opportunity-medium"
            )

        else:

            badge_class = (
                "opportunity-low"
            )

        st.html(
            f"""
            <div class="dashboard-card opportunity-card">

                <div class="opportunity-row">

                    <div class="opportunity-main">

                        <div class="opportunity-name">
                            {escape(
                                str(
                                    name or
                                    "Unknown lead"
                                )
                            )}
                        </div>

                        <div class="opportunity-company">
                            {escape(
                                str(
                                    company or
                                    "Unknown company"
                                )
                            )}
                        </div>

                    </div>

                    <div class="opportunity-detail">
                        <strong>Recommended action</strong><br>
                        {escape(
                            str(
                                recommended_action or
                                "No recommendation"
                            )
                        )}
                    </div>

                    <div class="opportunity-detail">
                        <strong>Follow-up</strong><br>
                        {escape(
                            str(
                                follow_up_timing or
                                "Not specified"
                            )
                        )}
                    </div>

                    <div class="opportunity-priority {badge_class}">
                        {escape(priority_text)}
                    </div>

                    <div class="opportunity-score">
                        {safe_int(lead_score)}
                    </div>

                </div>

            </div>
            """
        )

        selected_index = (
            status_options.index(current_status)
            if current_status in status_options
            else 0
        )

        selected_status = st.selectbox(
            "Action status",
            status_options,
            index=selected_index,
            key=f"action_status_{lead_id}",
        )

        if selected_status != current_status:

            try:

                updated = update_lead_action_status(
                    safe_int(lead_id),
                    selected_status,
                )

                if updated:

                    st.success(
                        f"Action status updated to {selected_status}."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Could not update the action status."
                    )

            except Exception as exc:

                st.error(
                    f"Action status update failed: {exc}"
                )

        if completed_at:

            st.caption(
                f"Completed at: {completed_at}"
            )

        st.divider()


def extract_recommendation_items(
    report,
):
    """
    Extract recommended focus items from the backend.

    Supports numeric dictionaries, lists, dictionaries
    and plain strings.
    """

    if not isinstance(report, dict):
        return {}

    source = find_nested_dict(
        report,
        [
            "recommended_focus",
            "recommended_actions",
            "recommendations",
            "actions",
        ],
    )

    if not source:
        return {}

    output = {}

    for key, value in source.items():

        label = normalize_label(key)

        if isinstance(
            value,
            (int, float),
        ):

            output[label] = safe_int(
                value
            )

        elif isinstance(
            value,
            dict,
        ):

            count = get_first_value(
                value,
                [
                    "count",
                    "total",
                    "records",
                    "leads",
                ],
                0,
            )

            if safe_int(count) > 0:

                output[label] = safe_int(
                    count
                )

        elif isinstance(
            value,
            list,
        ):

            if len(value) > 0:

                output[label] = len(
                    value
                )

        elif isinstance(
            value,
            str,
        ):

            if value.strip():

                output[label] = 1

    return output


def render_recommendation_card(
    items,
):
    """Render recommended focus areas."""

    if not items:
        return

    recommendation_html = ""

    for label, value in items.items():

        numeric_value = safe_int(
            value
        )

        if numeric_value <= 0:
            continue

        label_text = normalize_label(
            label
        )

        recommendation_html += f"""
        <div class="recommendation-item">

            <span class="recommendation-icon">
                →
            </span>

            <span class="recommendation-text">

                <span>
                    {escape(label_text)}
                </span>

                <strong>
                    {numeric_value}
                </strong>

            </span>

        </div>
        """

    if not recommendation_html:
        return

    st.html(
        f"""
        <div class="recommendation-card">

            {recommendation_html}

        </div>
        """
    )


def render_intelligence_header(
    intelligence,
    batch_id,
    ai_attempted,
):
    """Render the premium intelligence dashboard header."""

    analyzed = intelligence[
        "analyzed_leads"
    ]

    if ai_attempted > 0:

        source_label = (
            "Current processing run"
        )

    elif analyzed > 0:

        source_label = (
            "Existing CRM intelligence"
        )

    else:

        source_label = (
            "CRM intelligence"
        )

    batch_text = (
        str(batch_id)
        if batch_id is not None
        else "—"
    )

    st.html(
        f"""
        <div class="intel-hero-card">

            <div class="intel-hero-grid">

                <div>

                    <div class="intel-eyebrow">
                        AI-powered CRM intelligence
                    </div>

                    <div class="intel-title">
                        Understand your leads.
                    </div>

                    <div class="intel-description">
                        Turn cleaned CRM records into actionable
                        signals across priority, intent, demand
                        and follow-up opportunities.
                    </div>

                </div>

                <div class="intel-hero-meta">

                    <div class="intel-source-badge">

                        <span class="intel-live-dot"></span>

                        {escape(source_label)}

                    </div>

                    <div class="intel-batch-label">
                        Intelligence batch
                    </div>

                    <div class="intel-batch-number">
                        {escape(batch_text)}
                    </div>

                </div>

            </div>

        </div>
        """
    )


def render_intelligence_stat_card(
    label,
    value,
    description,
    accent="green",
):
    """Render a premium intelligence KPI card."""

    safe_label = escape(
        str(label)
    )

    safe_description = escape(
        str(description)
    )

    safe_value = escape(
        str(value)
    )

    st.html(
        f"""
        <div class="intel-stat-card intel-stat-{accent}">

            <div class="intel-stat-top">

                <span class="intel-stat-label">
                    {safe_label}
                </span>

                <span class="intel-stat-accent"></span>

            </div>

            <div class="intel-stat-value">
                {safe_value}
            </div>

            <div class="intel-stat-description">
                {safe_description}
            </div>

        </div>
        """
    )


def render_priority_cards(
    high,
    medium,
    low,
):
    """Render high / medium / low priority cards."""

    total = high + medium + low

    if total <= 0:
        total = 1

    cards = [
        (
            "High",
            high,
            "priority-high",
            "Immediate attention",
        ),
        (
            "Medium",
            medium,
            "priority-medium",
            "Worth following up",
        ),
        (
            "Low",
            low,
            "priority-low",
            "Lower urgency",
        ),
    ]

    columns = st.columns(3)

    for column, (
        label,
        count,
        css_class,
        description,
    ) in zip(
        columns,
        cards,
    ):

        percentage = (
            count / total
        ) * 100

        with column:

            st.html(
                f"""
                <div class="priority-card {css_class}">

                    <div class="priority-card-top">

                        <span class="priority-label">
                            {escape(label)}
                        </span>

                        <span class="priority-badge">
                            {percentage:.0f}%
                        </span>

                    </div>

                    <div class="priority-count">
                        {safe_int(count)}
                    </div>

                    <div class="priority-description">
                        {escape(description)}
                    </div>

                    <div class="priority-bar">

                        <div
                            class="priority-bar-fill"
                            style="width: {max(0, min(100, percentage))}%"
                        ></div>

                    </div>

                </div>
                """
            )


def render_focus_cards(
    items,
):
    """Render recommended focus as premium action cards."""

    if not items:
        return

    visible_items = []

    for label, value in items.items():

        count = safe_int(value)

        if count <= 0:
            continue

        visible_items.append(
            (
                normalize_label(label),
                count,
            )
        )

    if not visible_items:
        return

    visible_items = visible_items[:6]

    columns = st.columns(
        min(
            3,
            len(visible_items),
        )
    )

    for index, (
        label,
        count,
    ) in enumerate(
        visible_items
    ):

        column = columns[
            index % len(columns)
        ]

        label_lower = label.lower()

        if "high" in label_lower:

            icon = "↑"
            css_class = "focus-high"

        elif "duplicate" in label_lower:

            icon = "◎"
            css_class = "focus-review"

        elif "qualified" in label_lower:

            icon = "✓"
            css_class = "focus-qualified"

        elif "re engagement" in label_lower:

            icon = "↻"
            css_class = "focus-reengage"

        else:

            icon = "→"
            css_class = "focus-default"

        with column:

            st.html(
                f"""
                <div class="focus-card {css_class}">

                    <div class="focus-icon">
                        {icon}
                    </div>

                    <div class="focus-count">
                        {safe_int(count)}
                    </div>

                    <div class="focus-label">
                        {escape(label)}
                    </div>

                    <div class="focus-action">
                        Recommended focus
                    </div>

                </div>
                """
            )


def render_priority_focus(
    intelligence,
):
    """Render a concise action-oriented opportunity summary."""

    high = intelligence[
        "high_priority"
    ]

    medium = intelligence[
        "medium_priority"
    ]

    recommended = intelligence[
        "recommended_focus"
    ]

    duplicate_review = safe_int(
        recommended.get(
            "Duplicate Review",
            0,
        )
    )

    qualified_follow_up = safe_int(
        recommended.get(
            "Qualified Follow Up",
            0,
        )
    )

    if high > 0:

        title = "Priority follow-up"

        text = (
            f"{high} high-priority "
            f"{'lead' if high == 1 else 'leads'} "
            "identified. Prioritize these records "
            "for immediate follow-up."
        )

        badge = "HIGH PRIORITY"

        css_class = (
            "focus-opportunity-high"
        )

    elif qualified_follow_up > 0:

        title = "Qualified opportunity"

        text = (
            f"{qualified_follow_up} qualified "
            f"{'lead' if qualified_follow_up == 1 else 'leads'} "
            "identified for focused follow-up."
        )

        badge = "QUALIFIED"

        css_class = (
            "focus-opportunity-green"
        )

    elif duplicate_review > 0:

        title = "Data review required"

        text = (
            f"{duplicate_review} record"
            f"{'s' if duplicate_review != 1 else ''} "
            "require manual duplicate review before "
            "final CRM use."
        )

        badge = "REVIEW"

        css_class = (
            "focus-opportunity-review"
        )

    elif medium > 0:

        title = "Follow-up opportunity"

        text = (
            f"{medium} medium-priority "
            f"{'lead' if medium == 1 else 'leads'} "
            "could benefit from timely follow-up."
        )

        badge = "FOLLOW UP"

        css_class = (
            "focus-opportunity-medium"
        )

    else:

        title = "CRM intelligence ready"

        text = (
            "No immediate priority issues were identified "
            "from the available AI intelligence."
        )

        badge = "READY"

        css_class = (
            "focus-opportunity-green"
        )

    st.html(
        f"""
        <div class="focus-opportunity {css_class}">

            <div class="focus-opportunity-icon">
                →
            </div>

            <div class="focus-opportunity-content">

                <div class="focus-opportunity-badge">
                    {escape(badge)}
                </div>

                <div class="focus-opportunity-title">
                    {escape(title)}
                </div>

                <div class="focus-opportunity-text">
                    {escape(text)}
                </div>

            </div>

        </div>
        """
    )


# ========================================
# CUSTOM STYLING
# ========================================

st.markdown(
    """
    <style>

    :root {
        --crm-green: #0F6B4F;
        --crm-green-hover: #0B5A42;
        --crm-green-soft: #EAF5F0;

        --crm-black: #111111;
        --crm-white: #FFFFFF;

        --crm-border: #E5E7EB;
        --crm-muted: #6B7280;
        --crm-surface: #FFFFFF;

        --crm-shadow: rgba(0, 0, 0, 0.045);
    }


    /* ========================================
       BASE
       ======================================== */

    .stApp {
        background: var(--crm-white);
    }

    .main {
        padding-top: 1rem;
    }

    .block-container {
        max-width: 1240px;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
        padding-bottom: 4rem;
    }

    h1,
    h2,
    h3,
    h4,
    h5,
    h6 {
        color: var(--crm-black);
    }

    p,
    label {
        color: var(--crm-black);
    }


    /* ========================================
       SECTION TITLES
       ======================================== */

    .section-title {
        margin-top: 2rem;
        margin-bottom: 1rem;

        color: var(--crm-black);

        font-size: 1.08rem;
        font-weight: 750;

        letter-spacing: -0.015em;
    }

    .section-number {
        color: var(--crm-green);

        font-weight: 800;
        margin-right: 0.45rem;

        font-size: 0.82rem;
    }


    /* ========================================
       METRICS
       ======================================== */

    div[data-testid="stMetric"] {
        background: var(--crm-surface);

        border: 1px solid var(--crm-border);
        border-radius: 16px;

        padding: 1.15rem 1.25rem;

        box-shadow:
            0 5px 18px var(--crm-shadow);

        transition:
            transform 0.18s ease,
            box-shadow 0.18s ease,
            border-color 0.18s ease;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);

        border-color: var(--crm-green);

        box-shadow:
            0 10px 26px rgba(0, 0, 0, 0.07);
    }

    div[data-testid="stMetricLabel"] {
        color: var(--crm-muted) !important;

        font-size: 0.76rem !important;
        font-weight: 600 !important;
    }

    div[data-testid="stMetricValue"] {
        color: var(--crm-black) !important;

        font-size: 1.8rem !important;
        font-weight: 800 !important;
    }


    /* ========================================
       INPUTS
       ======================================== */

    div[data-baseweb="input"] > div,
    div[data-baseweb="textarea"] > div {
        border-radius: 12px;

        border: 1px solid var(--crm-border);

        background: var(--crm-surface);

        transition:
            border-color 0.18s ease,
            box-shadow 0.18s ease;
    }

    div[data-baseweb="input"] > div:focus-within,
    div[data-baseweb="textarea"] > div:focus-within {
        border-color: var(--crm-green);

        box-shadow:
            0 0 0 3px rgba(15, 107, 79, 0.12);
    }

    input,
    textarea {
        color: var(--crm-black) !important;
    }


    /* ========================================
       FILE UPLOADER
       ======================================== */

    [data-testid="stFileUploader"] {
        background: var(--crm-surface);

        border: 1px dashed var(--crm-green);
        border-radius: 16px;

        padding: 0.5rem;

        transition:
            background 0.18s ease,
            border-color 0.18s ease;
    }

    [data-testid="stFileUploader"]:hover {
        background: var(--crm-green-soft);

        border-color:
            var(--crm-green-hover);
    }

    [data-testid="stFileUploaderDropzone"] {
        background: transparent !important;
        border: none !important;
    }


    /* ========================================
       BUTTONS
       ======================================== */

    .stButton > button {
        min-height: 2.8rem;

        border-radius: 11px;

        border: 1px solid var(--crm-border);

        background: var(--crm-white);
        color: var(--crm-black);

        font-weight: 650;

        transition:
            transform 0.16s ease,
            box-shadow 0.16s ease,
            border-color 0.16s ease,
            background 0.16s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);

        border-color: var(--crm-green);
        color: var(--crm-green);

        box-shadow:
            0 6px 18px rgba(0, 0, 0, 0.06);
    }

    .stButton > button[kind="primary"] {
        background: var(--crm-green);

        border-color: var(--crm-green);

        color: #FFFFFF;

        font-weight: 750;

        box-shadow:
            0 8px 20px rgba(15, 107, 79, 0.18);
    }

    .stButton > button[kind="primary"]:hover {
        background: var(--crm-green-hover);

        border-color: var(--crm-green-hover);

        color: #FFFFFF;

        box-shadow:
            0 10px 24px rgba(15, 107, 79, 0.24);
    }

    [data-testid="stDownloadButton"] button {
        border-radius: 11px;

        border: 1px solid var(--crm-border);

        background: var(--crm-white);
        color: var(--crm-black);

        font-weight: 650;

        transition:
            transform 0.16s ease,
            border-color 0.16s ease,
            color 0.16s ease;
    }

    [data-testid="stDownloadButton"] button:hover {
        transform: translateY(-1px);

        border-color: var(--crm-green);
        color: var(--crm-green);
    }


    /* ========================================
       ALERTS
       ======================================== */

    [data-testid="stAlert"] {
        border-radius: 13px;
    }

    .success-box {
        padding: 1rem 1.15rem;

        margin:
            0.5rem 0
            1.25rem;

        border-radius: 13px;

        background: var(--crm-green-soft);

        border:
            1px solid
            rgba(15, 107, 79, 0.22);

        color: var(--crm-green);

        line-height: 1.6;
    }

    .warning-box {
        padding: 1rem 1.15rem;

        margin:
            0.5rem 0
            1.25rem;

        border-radius: 13px;

        background: var(--crm-surface);

        border:
            1px solid
            var(--crm-border);

        color: var(--crm-black);

        line-height: 1.6;
    }


    /* ========================================
       DASHBOARD CARDS
       ======================================== */

    .dashboard-card {
        background: var(--crm-surface);

        border:
            1px solid
            var(--crm-border);

        border-radius: 18px;

        padding: 1.35rem;

        box-shadow:
            0 5px 18px var(--crm-shadow);

        height: 100%;
    }

    .dashboard-card-title {
        color: var(--crm-black);

        font-size: 0.8rem;
        font-weight: 750;

        text-transform: uppercase;

        letter-spacing: 0.08em;

        margin-bottom: 0.8rem;
    }

    .dashboard-card-value {
        color: var(--crm-black);

        font-size: 2rem;
        font-weight: 800;

        letter-spacing: -0.04em;
    }

    .dashboard-card-description {
        color: var(--crm-muted);

        font-size: 0.82rem;
        line-height: 1.5;

        margin-top: 0.4rem;
    }


    /* ========================================
       DYNAMIC HEALTH CARD
       ======================================== */

    .health-card {
        position: relative;
        overflow: hidden;

        border-radius: 24px;

        padding: 1.6rem;

        min-height: 205px;

        color: #FFFFFF;

        box-shadow:
            0 18px 40px
            rgba(15, 107, 79, 0.16);

        isolation: isolate;
    }

    .health-card::before {
        content: "";

        position: absolute;

        width: 230px;
        height: 230px;

        right: -80px;
        top: -110px;

        border-radius: 50%;

        border:
            1px solid
            rgba(255, 255, 255, 0.22);

        box-shadow:
            0 0 0 35px
            rgba(255, 255, 255, 0.055),

            0 0 0 70px
            rgba(255, 255, 255, 0.025);

        z-index: -1;
    }

    .health-card::after {
        content: "";

        position: absolute;

        width: 9px;
        height: 9px;

        right: 58px;
        bottom: 38px;

        border-radius: 50%;

        background:
            rgba(255, 255, 255, 0.95);

        box-shadow:
            0 0 0 7px
            rgba(255, 255, 255, 0.10),

            0 0 24px
            rgba(255, 255, 255, 0.65);

        z-index: -1;
    }

    .health-card.health-excellent {
        background:
            radial-gradient(
                circle at 90% 10%,
                rgba(126, 255, 202, 0.28),
                transparent 34%
            ),
            linear-gradient(
                135deg,
                #083D2E 0%,
                #0F6B4F 48%,
                #159A6C 100%
            );

        box-shadow:
            0 18px 45px
            rgba(15, 107, 79, 0.24);
    }

    .health-card.health-good {
        background:
            radial-gradient(
                circle at 90% 10%,
                rgba(255, 231, 146, 0.30),
                transparent 34%
            ),
            linear-gradient(
                135deg,
                #5A430A 0%,
                #A87512 48%,
                #D7A62D 100%
            );

        box-shadow:
            0 18px 45px
            rgba(181, 134, 25, 0.20);
    }

    .health-card.health-fair {
        background:
            radial-gradient(
                circle at 90% 10%,
                rgba(255, 205, 160, 0.30),
                transparent 34%
            ),
            linear-gradient(
                135deg,
                #713214 0%,
                #B95C25 48%,
                #E0873E 100%
            );

        box-shadow:
            0 18px 45px
            rgba(185, 92, 37, 0.20);
    }

    .health-card.health-poor {
        background:
            radial-gradient(
                circle at 90% 10%,
                rgba(255, 180, 180, 0.30),
                transparent 34%
            ),
            linear-gradient(
                135deg,
                #5E1015 0%,
                #A9252D 48%,
                #D94A50 100%
            );

        box-shadow:
            0 18px 45px
            rgba(169, 37, 45, 0.22);
    }

    .health-content {
        position: relative;
        z-index: 2;
    }

    .health-label {
        color:
            rgba(255, 255, 255, 0.72);

        font-size: 0.72rem;
        font-weight: 750;

        text-transform: uppercase;
        letter-spacing: 0.12em;
    }

    .health-score {
        color: #FFFFFF;

        font-size: 3.15rem;
        line-height: 1;

        font-weight: 850;

        letter-spacing: -0.055em;

        margin-top: 0.65rem;
    }

    .health-status {
        display: inline-flex;

        align-items: center;

        margin-top: 0.75rem;

        padding:
            0.34rem
            0.7rem;

        border-radius: 999px;

        background:
            rgba(255, 255, 255, 0.13);

        border:
            1px solid
            rgba(255, 255, 255, 0.18);

        color: #FFFFFF;

        font-size: 0.75rem;
        font-weight: 800;

        letter-spacing: 0.08em;

        text-transform: uppercase;

        backdrop-filter: blur(8px);
    }

    .health-status-dot {
        width: 7px;
        height: 7px;

        margin-right: 0.45rem;

        border-radius: 50%;

        background: #FFFFFF;

        box-shadow:
            0 0 10px
            rgba(255, 255, 255, 0.8);
    }

    .health-description {
        max-width: 390px;

        color:
            rgba(255, 255, 255, 0.72);

        font-size: 0.78rem;

        line-height: 1.55;

        margin-top: 0.7rem;
    }


    /* ========================================
       QUALITY SIGNALS
       ======================================== */

    .quality-progress {
        width: 100%;

        height: 8px;

        margin-top: 0.7rem;

        border-radius: 999px;

        background:
            var(--crm-border);

        overflow: hidden;
    }

    .quality-progress-fill {
        height: 100%;

        border-radius: 999px;

        background:
            var(--crm-green);

        transition:
            width 0.5s ease;
    }

    .quality-row {
        margin-bottom: 1.1rem;
    }

    .quality-row-header {
        display: flex;

        justify-content:
            space-between;

        align-items: center;

        color:
            var(--crm-black);

        font-size: 0.83rem;
        font-weight: 650;
    }

    .quality-row-value {
        color:
            var(--crm-green);

        font-weight: 800;
    }


    /* ========================================
       INTELLIGENCE HERO
       ======================================== */

    .intel-hero-card {
        position: relative;

        overflow: hidden;

        margin-top: 0.35rem;

        padding: 1.55rem 1.65rem;

        border-radius: 22px;

        background:
            radial-gradient(
                circle at 88% 15%,
                rgba(42, 143, 107, 0.17),
                transparent 30%
            ),
            linear-gradient(
                135deg,
                #F8FCFA 0%,
                #FFFFFF 55%,
                #F0F8F4 100%
            );

        border:
            1px solid
            rgba(15, 107, 79, 0.16);

        box-shadow:
            0 12px 34px
            rgba(15, 107, 79, 0.08);
    }

    .intel-hero-card::after {
        content: "";

        position: absolute;

        width: 180px;
        height: 180px;

        right: -80px;
        bottom: -105px;

        border-radius: 50%;

        border:
            1px solid
            rgba(15, 107, 79, 0.12);

        box-shadow:
            0 0 0 28px
            rgba(15, 107, 79, 0.035),

            0 0 0 56px
            rgba(15, 107, 79, 0.02);
    }

    .intel-hero-grid {
        position: relative;
        z-index: 2;

        display: grid;

        grid-template-columns:
            1fr
            auto;

        gap: 2rem;

        align-items: center;
    }

    .intel-eyebrow {
        color:
            var(--crm-green);

        font-size: 0.68rem;

        font-weight: 850;

        text-transform: uppercase;

        letter-spacing: 0.13em;
    }

    .intel-title {
        margin-top: 0.35rem;

        color:
            var(--crm-black);

        font-size: 1.65rem;

        font-weight: 850;

        letter-spacing: -0.04em;
    }

    .intel-description {
        max-width: 670px;

        margin-top: 0.45rem;

        color:
            var(--crm-muted);

        font-size: 0.83rem;

        line-height: 1.6;
    }

    .intel-hero-meta {
        min-width: 150px;

        padding:
            0.85rem
            1rem;

        border-radius: 15px;

        background:
            rgba(255, 255, 255, 0.72);

        border:
            1px solid
            rgba(15, 107, 79, 0.12);

        backdrop-filter:
            blur(10px);

        text-align: right;
    }

    .intel-source-badge {
        display: inline-flex;

        align-items: center;

        gap: 0.38rem;

        color:
            var(--crm-green);

        font-size: 0.63rem;

        font-weight: 800;

        text-transform: uppercase;

        letter-spacing: 0.06em;

        white-space: nowrap;
    }

    .intel-live-dot {
        width: 6px;
        height: 6px;

        border-radius: 50%;

        background:
            var(--crm-green);

        box-shadow:
            0 0 0 4px
            rgba(15, 107, 79, 0.09);
    }

    .intel-batch-label {
        margin-top: 0.8rem;

        color:
            var(--crm-muted);

        font-size: 0.62rem;

        text-transform: uppercase;

        letter-spacing: 0.09em;

        font-weight: 750;
    }

    .intel-batch-number {
        margin-top: 0.1rem;

        color:
            var(--crm-black);

        font-size: 1.15rem;

        font-weight: 850;
    }


    /* ========================================
       INTELLIGENCE KPI CARDS
       ======================================== */

    .intel-stat-card {
        position: relative;

        overflow: hidden;

        min-height: 155px;

        padding: 1.15rem 1.2rem;

        border-radius: 18px;

        background:
            var(--crm-surface);

        border:
            1px solid
            var(--crm-border);

        box-shadow:
            0 6px 20px
            var(--crm-shadow);

        transition:
            transform 0.18s ease,
            border-color 0.18s ease,
            box-shadow 0.18s ease;
    }

    .intel-stat-card:hover {
        transform:
            translateY(-2px);

        border-color:
            rgba(15, 107, 79, 0.32);

        box-shadow:
            0 12px 28px
            rgba(0, 0, 0, 0.07);
    }

    .intel-stat-card::after {
        content: "";

        position: absolute;

        width: 85px;
        height: 85px;

        right: -35px;
        bottom: -40px;

        border-radius: 50%;

        background:
            rgba(15, 107, 79, 0.045);
    }

    .intel-stat-top {
        display: flex;

        justify-content:
            space-between;

        align-items: center;
    }

    .intel-stat-label {
        color:
            var(--crm-muted);

        font-size: 0.66rem;

        font-weight: 800;

        text-transform: uppercase;

        letter-spacing: 0.09em;
    }

    .intel-stat-accent {
        width: 7px;
        height: 7px;

        border-radius: 50%;

        background:
            var(--crm-green);

        box-shadow:
            0 0 0 5px
            rgba(15, 107, 79, 0.08);
    }

    .intel-stat-value {
        margin-top: 0.75rem;

        color:
            var(--crm-black);

        font-size: 2rem;

        font-weight: 850;

        line-height: 1;

        letter-spacing: -0.045em;
    }

    .intel-stat-description {
        max-width: 190px;

        margin-top: 0.55rem;

        color:
            var(--crm-muted);

        font-size: 0.72rem;

        line-height: 1.5;
    }

    .intel-stat-amber .intel-stat-accent {
        background: #B98208;

        box-shadow:
            0 0 0 5px
            rgba(185, 130, 8, 0.09);
    }

    .intel-stat-neutral .intel-stat-accent {
        background: #7B8580;

        box-shadow:
            0 0 0 5px
            rgba(123, 133, 128, 0.09);
    }


    /* ========================================
       PRIORITY CARDS
       ======================================== */

    .priority-card {
        position: relative;

        overflow: hidden;

        min-height: 165px;

        padding: 1.2rem;

        border-radius: 18px;

        border:
            1px solid
            var(--crm-border);

        background:
            var(--crm-surface);

        box-shadow:
            0 6px 20px
            var(--crm-shadow);
    }

    .priority-card-top {
        display: flex;

        justify-content:
            space-between;

        align-items: center;
    }

    .priority-label {
        font-size: 0.7rem;

        font-weight: 850;

        text-transform: uppercase;

        letter-spacing: 0.09em;
    }

    .priority-badge {
        padding:
            0.24rem
            0.5rem;

        border-radius: 999px;

        font-size: 0.62rem;

        font-weight: 800;
    }

    .priority-count {
        margin-top: 0.75rem;

        font-size: 2.1rem;

        line-height: 1;

        font-weight: 850;

        letter-spacing: -0.045em;

        color:
            var(--crm-black);
    }

    .priority-description {
        margin-top: 0.45rem;

        color:
            var(--crm-muted);

        font-size: 0.73rem;
    }

    .priority-bar {
        height: 6px;

        margin-top: 1rem;

        overflow: hidden;

        border-radius: 999px;

        background:
            var(--crm-border);
    }

    .priority-bar-fill {
        height: 100%;

        border-radius: 999px;
    }

    .priority-high {
        border-color:
            rgba(15, 107, 79, 0.23);
    }

    .priority-high .priority-label,
    .priority-high .priority-badge {
        color: #087443;
    }

    .priority-high .priority-badge {
        background: #E8F6EF;
    }

    .priority-high .priority-bar-fill {
        background:
            linear-gradient(
                90deg,
                #0F6B4F,
                #4CC795
            );
    }

    .priority-medium .priority-label,
    .priority-medium .priority-badge {
        color: #946A00;
    }

    .priority-medium .priority-badge {
        background: #FFF5D9;
    }

    .priority-medium .priority-bar-fill {
        background:
            linear-gradient(
                90deg,
                #B98208,
                #E7C45E
            );
    }

    .priority-low .priority-label,
    .priority-low .priority-badge {
        color: #68736E;
    }

    .priority-low .priority-badge {
        background: #F0F2F1;
    }

    .priority-low .priority-bar-fill {
        background:
            linear-gradient(
                90deg,
                #7B8580,
                #AEB8B3
            );
    }


    /* ========================================
       INTELLIGENCE DISTRIBUTION
       ======================================== */

    .intelligence-card {
        min-height: 220px;
    }

    .intel-row {
        margin-bottom: 0.95rem;
    }

    .intel-row:last-child {
        margin-bottom: 0;
    }

    .intel-row-header {
        display: flex;

        justify-content:
            space-between;

        align-items: center;

        gap: 1rem;
    }

    .intel-row-label {
        color:
            var(--crm-black);

        font-size: 0.82rem;
        font-weight: 650;
    }

    .intel-row-value {
        color:
            var(--crm-green);

        font-size: 0.82rem;
        font-weight: 800;
    }

    .intel-progress {
        width: 100%;

        height: 6px;

        margin-top: 0.45rem;

        border-radius: 999px;

        background:
            var(--crm-border);

        overflow: hidden;
    }

    .intel-progress-fill {
        height: 100%;

        border-radius: 999px;

        background:
            linear-gradient(
                90deg,
                var(--crm-green),
                #48B78C
            );
    }


    /* ========================================
       PRIORITY FOCUS
       ======================================== */

    .focus-opportunity {
        position: relative;

        display: flex;

        align-items: flex-start;

        gap: 1rem;

        overflow: hidden;

        padding: 1.3rem 1.4rem;

        border-radius: 20px;

        border:
            1px solid
            rgba(15, 107, 79, 0.18);

        background:
            linear-gradient(
                135deg,
                #F7FCF9,
                #FFFFFF
            );

        box-shadow:
            0 8px 26px
            var(--crm-shadow);
    }

    .focus-opportunity::after {
        content: "";

        position: absolute;

        width: 130px;
        height: 130px;

        right: -65px;
        top: -65px;

        border-radius: 50%;

        border:
            1px solid
            rgba(15, 107, 79, 0.11);
    }

    .focus-opportunity-icon {
        display: flex;

        align-items: center;
        justify-content: center;

        flex: 0 0 auto;

        width: 42px;
        height: 42px;

        border-radius: 13px;

        background:
            var(--crm-green-soft);

        color:
            var(--crm-green);

        font-size: 1rem;

        font-weight: 900;
    }

    .focus-opportunity-content {
        position: relative;

        z-index: 2;
    }

    .focus-opportunity-badge {
        color:
            var(--crm-green);

        font-size: 0.61rem;

        font-weight: 850;

        letter-spacing: 0.1em;

        text-transform: uppercase;
    }

    .focus-opportunity-title {
        margin-top: 0.22rem;

        color:
            var(--crm-black);

        font-size: 1rem;

        font-weight: 800;
    }

    .focus-opportunity-text {
        margin-top: 0.25rem;

        color:
            var(--crm-muted);

        font-size: 0.77rem;

        line-height: 1.55;

        max-width: 690px;
    }

    .focus-opportunity-high {
        border-color:
            rgba(15, 107, 79, 0.26);
    }

    .focus-opportunity-review {
        border-color:
            rgba(185, 130, 8, 0.24);

        background:
            linear-gradient(
                135deg,
                #FFFBF0,
                #FFFFFF
            );
    }

    .focus-opportunity-review .focus-opportunity-icon,
    .focus-opportunity-review .focus-opportunity-badge {
        color: #946A00;
    }

    .focus-opportunity-review .focus-opportunity-icon {
        background: #FFF5D9;
    }

    .focus-opportunity-medium {
        border-color:
            rgba(185, 130, 8, 0.2);
    }

    .focus-opportunity-medium .focus-opportunity-icon,
    .focus-opportunity-medium .focus-opportunity-badge {
        color: #946A00;
    }

    .focus-opportunity-medium .focus-opportunity-icon {
        background: #FFF5D9;
    }


    /* ========================================
       RECOMMENDED FOCUS GRID
       ======================================== */

    .focus-card {
        position: relative;

        overflow: hidden;

        min-height: 155px;

        padding: 1.2rem;

        border-radius: 18px;

        border:
            1px solid
            var(--crm-border);

        background:
            var(--crm-surface);

        box-shadow:
            0 6px 20px
            var(--crm-shadow);

        transition:
            transform 0.18s ease,
            box-shadow 0.18s ease;
    }

    .focus-card:hover {
        transform:
            translateY(-2px);

        box-shadow:
            0 12px 28px
            rgba(0, 0, 0, 0.07);
    }

    .focus-icon {
        display: flex;

        align-items: center;
        justify-content: center;

        width: 34px;
        height: 34px;

        border-radius: 10px;

        background:
            var(--crm-green-soft);

        color:
            var(--crm-green);

        font-weight: 900;
    }

    .focus-count {
        margin-top: 0.75rem;

        color:
            var(--crm-black);

        font-size: 1.8rem;

        font-weight: 850;

        line-height: 1;
    }

    .focus-label {
        margin-top: 0.45rem;

        color:
            var(--crm-black);

        font-size: 0.78rem;

        font-weight: 750;
    }

    .focus-action {
        margin-top: 0.25rem;

        color:
            var(--crm-muted);

        font-size: 0.66rem;

        text-transform: uppercase;

        letter-spacing: 0.07em;

        font-weight: 700;
    }

    .focus-high {
        border-color:
            rgba(15, 107, 79, 0.22);
    }

    .focus-review {
        border-color:
            rgba(185, 130, 8, 0.22);
    }

    .focus-review .focus-icon {
        background: #FFF5D9;
        color: #946A00;
    }

    .focus-qualified {
        border-color:
            rgba(15, 107, 79, 0.22);
    }

    .focus-reengage .focus-icon {
        background: #F0F2F1;
        color: #68736E;
    }


    /* ========================================
       TOP OPPORTUNITIES
       ======================================== */

    .opportunity-card {
        margin-top: 0.25rem;
    }

    .opportunity-header,
    .opportunity-row {
        display: grid;

        grid-template-columns:
            1.4fr
            1fr
            1fr
            0.8fr
            0.45fr;

        gap: 1rem;

        align-items: center;
    }

    .opportunity-header {
        padding:
            0
            0
            0.7rem;

        color:
            var(--crm-muted);

        font-size: 0.68rem;

        font-weight: 750;

        text-transform: uppercase;

        letter-spacing: 0.08em;

        border-bottom:
            1px solid
            var(--crm-border);
    }

    .opportunity-row {
        padding:
            0.9rem
            0;

        border-bottom:
            1px solid
            var(--crm-border);
    }

    .opportunity-row:last-child {
        border-bottom: none;

        padding-bottom: 0;
    }

    .opportunity-name {
        color:
            var(--crm-black);

        font-size: 0.84rem;

        font-weight: 750;
    }

    .opportunity-company {
        margin-top: 0.2rem;

        color:
            var(--crm-muted);

        font-size: 0.72rem;
    }

    .opportunity-detail {
        color:
            var(--crm-black);

        font-size: 0.76rem;

        line-height: 1.4;

        word-break: break-word;
    }

    .opportunity-priority {
        display: inline-flex;

        justify-content: center;

        align-items: center;

        width: fit-content;

        padding:
            0.28rem
            0.55rem;

        border-radius: 999px;

        font-size: 0.64rem;

        font-weight: 800;

        letter-spacing: 0.05em;
    }

    .opportunity-high {
        background: #E8F6EF;
        color: #087443;
    }

    .opportunity-medium {
        background: #FFF5D9;
        color: #946A00;
    }

    .opportunity-low {
        background: #F0F2F1;
        color: #68736E;
    }

    .opportunity-score {
        color:
            var(--crm-green);

        font-size: 1rem;

        font-weight: 850;

        text-align: right;
    }


    /* ========================================
       INSIGHTS
       ======================================== */

    .insight-card {
        position: relative;

        overflow: hidden;

        background:
            linear-gradient(
                135deg,
                var(--crm-surface),
                var(--crm-green-soft)
            );

        border:
            1px solid
            rgba(15, 107, 79, 0.18);

        border-radius: 20px;

        padding: 1.4rem;

        box-shadow:
            0 8px 26px
            var(--crm-shadow);
    }

    .insight-card::before {
        content: "";

        position: absolute;

        width: 120px;
        height: 120px;

        right: -45px;
        top: -45px;

        border-radius: 50%;

        border:
            1px solid
            rgba(15, 107, 79, 0.16);

        box-shadow:
            0 0 0 25px
            rgba(15, 107, 79, 0.04),

            0 0 0 50px
            rgba(15, 107, 79, 0.025);
    }

    .insight-title {
        color:
            var(--crm-green);

        font-size: 0.75rem;

        font-weight: 800;

        text-transform: uppercase;

        letter-spacing: 0.1em;
    }

    .insight-text {
        color:
            var(--crm-black);

        font-size: 0.95rem;

        line-height: 1.65;

        margin-top: 0.55rem;

        position: relative;

        z-index: 2;
    }


    /* ========================================
       RECOMMENDATIONS
       ======================================== */

    .recommendation-card {
        background:
            var(--crm-surface);

        border:
            1px solid
            var(--crm-border);

        border-radius: 18px;

        padding:
            1.2rem
            1.3rem;

        box-shadow:
            0 5px 18px
            var(--crm-shadow);
    }

    .recommendation-item {
        display: flex;

        align-items: flex-start;

        gap: 0.7rem;

        padding:
            0.75rem
            0;

        border-bottom:
            1px solid
            var(--crm-border);

        color:
            var(--crm-black);

        font-size: 0.86rem;

        line-height: 1.5;
    }

    .recommendation-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }

    .recommendation-icon {
        display: inline-flex;

        align-items: center;
        justify-content: center;

        flex: 0 0 auto;

        width: 23px;
        height: 23px;

        border-radius: 7px;

        background:
            var(--crm-green-soft);

        color:
            var(--crm-green);

        font-size: 0.72rem;

        font-weight: 900;
    }

    .recommendation-text {
        display: flex;

        justify-content:
            space-between;

        align-items: center;

        width: 100%;

        gap: 1rem;
    }

    .recommendation-text strong {
        color:
            var(--crm-green);

        font-weight: 850;
    }


    /* ========================================
       DELIVERY
       ======================================== */

    .delivery-card {
        background:
            var(--crm-green-soft);

        border:
            1px solid
            rgba(15, 107, 79, 0.2);

        border-radius: 20px;

        padding: 1.5rem;

        margin-top: 0.5rem;
    }

    .delivery-title {
        color:
            var(--crm-green);

        font-size: 1.05rem;

        font-weight: 800;
    }

    .delivery-description {
        color:
            var(--crm-black);

        margin-top: 0.35rem;

        font-size: 0.85rem;

        line-height: 1.55;
    }


    /* ========================================
       RUN INFORMATION
       ======================================== */

    .run-info-card {
        background:
            var(--crm-surface);

        border:
            1px solid
            var(--crm-border);

        border-radius: 16px;

        padding:
            1.2rem
            1.35rem;
    }

    .run-info-item {
        margin-bottom: 0.7rem;
    }

    .run-info-label {
        color:
            var(--crm-muted);

        font-size: 0.72rem;

        text-transform: uppercase;

        letter-spacing: 0.07em;

        font-weight: 700;
    }

    .run-info-value {
        color:
            var(--crm-black);

        font-size: 0.9rem;

        font-weight: 650;

        margin-top: 0.15rem;

        word-break: break-word;
    }


    /* ========================================
       STREAMLIT COMPONENTS
       ======================================== */

    [data-testid="stDataFrame"] {
        border:
            1px solid
            var(--crm-border);

        border-radius: 14px;

        overflow: hidden;
    }

    [data-testid="stExpander"] {
        border:
            1px solid
            var(--crm-border);

        border-radius: 14px;

        background:
            var(--crm-surface);

        overflow: hidden;
    }

    [data-testid="stStatusWidget"] {
        border:
            1px solid
            var(--crm-border);

        border-radius: 14px;
    }

    [data-testid="stCode"] {
        border-radius: 12px;
    }


    /* ========================================
       SIDEBAR
       ======================================== */

    [data-testid="stSidebar"] {
        border-right:
            1px solid
            var(--crm-border);
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color:
            var(--crm-black);
    }

    .sidebar-brand {
        padding:
            0.5rem
            0
            1rem;
    }

    .sidebar-logo {
        display: inline-flex;

        align-items: center;
        justify-content: center;

        width: 34px;
        height: 34px;

        margin-bottom: 0.7rem;

        border-radius: 10px;

        background:
            var(--crm-green);

        color: #FFFFFF;

        font-weight: 800;
    }

    .sidebar-title {
        font-size: 1.1rem;

        font-weight: 800;

        color:
            var(--crm-black);
    }

    .sidebar-description {
        margin-top: 0.45rem;

        color:
            var(--crm-muted);

        font-size: 0.85rem;

        line-height: 1.6;
    }

    .sidebar-footer {
        margin-top: 1.5rem;

        padding-top: 1rem;

        border-top:
            1px solid
            var(--crm-border);

        color:
            var(--crm-muted);

        font-size: 0.75rem;

        line-height: 1.5;
    }


    /* ========================================
       FOOTER
       ======================================== */

    .footer {
        padding:
            1.5rem
            0
            0;

        color:
            var(--crm-muted);

        font-size: 0.78rem;

        text-align: center;
    }


    /* ========================================
       DARK MODE
       ======================================== */

    @media (prefers-color-scheme: dark) {

        :root {
            --crm-green: #2A8F6B;
            --crm-green-hover: #36A77E;
            --crm-green-soft: #102A21;

            --crm-black: #F5F7F6;
            --crm-white: #0D0F0E;

            --crm-border: #29312D;
            --crm-muted: #9AA5A0;
            --crm-surface: #151917;

            --crm-shadow:
                rgba(0, 0, 0, 0.22);
        }

        .stApp {
            background: #0D0F0E;
        }

        div[data-testid="stMetric"] {
            background: #151917;
            border-color: #29312D;
        }

        div[data-testid="stMetricLabel"] {
            color: #9AA5A0 !important;
        }

        div[data-testid="stMetricValue"] {
            color: #F5F7F6 !important;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            background: #151917;
            border-color: #29312D;
        }

        input,
        textarea {
            color: #F5F7F6 !important;
        }

        .stButton > button {
            background: #151917;
            border-color: #29312D;
            color: #F5F7F6;
        }

        .stButton > button:hover {
            background: #1A201D;
            color: #6ED1A8;
            border-color: #2A8F6B;
        }

        [data-testid="stDownloadButton"] button {
            background: #151917;
            border-color: #29312D;
            color: #F5F7F6;
        }

        [data-testid="stDownloadButton"] button:hover {
            background: #1A201D;
            color: #6ED1A8;
            border-color: #2A8F6B;
        }

        [data-testid="stFileUploader"] {
            background: #151917;
            border-color: #2A8F6B;
        }

        [data-testid="stFileUploader"]:hover {
            background: #102A21;
        }

        [data-testid="stExpander"],
        [data-testid="stStatusWidget"] {
            background: #151917;
            border-color: #29312D;
        }

        [data-testid="stSidebar"] {
            background: #0D0F0E;
            border-color: #29312D;
        }

        .sidebar-title {
            color: #F5F7F6;
        }

        .sidebar-description {
            color: #9AA5A0;
        }

        .sidebar-footer {
            color: #7F8984;
            border-color: #29312D;
        }

        .section-title {
            color: #F5F7F6;
        }

        .success-box {
            background: #102A21;
            border-color:
                rgba(42, 143, 107, 0.35);
            color: #6ED1A8;
        }

        .warning-box {
            background: #151917;
            border-color: #29312D;
            color: #F5F7F6;
        }

        .dashboard-card {
            background: #151917;
            border-color: #29312D;
        }

        .dashboard-card-title,
        .dashboard-card-value {
            color: #F5F7F6;
        }

        .dashboard-card-description {
            color: #9AA5A0;
        }

        .quality-row-header {
            color: #F5F7F6;
        }

        .quality-progress,
        .intel-progress,
        .priority-bar {
            background: #29312D;
        }

        .intel-row-label {
            color: #F5F7F6;
        }

        .intel-hero-card {
            background:
                radial-gradient(
                    circle at 88% 15%,
                    rgba(42, 143, 107, 0.17),
                    transparent 30%
                ),
                linear-gradient(
                    135deg,
                    #151917 0%,
                    #121614 55%,
                    #102A21 100%
                );

            border-color:
                rgba(42, 143, 107, 0.3);
        }

        .intel-title {
            color: #F5F7F6;
        }

        .intel-description {
            color: #9AA5A0;
        }

        .intel-hero-meta {
            background:
                rgba(21, 25, 23, 0.72);

            border-color:
                rgba(42, 143, 107, 0.22);
        }

        .intel-batch-number {
            color: #F5F7F6;
        }

        .intel-stat-card {
            background: #151917;
            border-color: #29312D;
        }

        .intel-stat-value {
            color: #F5F7F6;
        }

        .priority-card {
            background: #151917;
            border-color: #29312D;
        }

        .priority-count {
            color: #F5F7F6;
        }

        .priority-medium .priority-badge {
            background: #332B13;
            color: #E8C96A;
        }

        .priority-low .priority-badge {
            background: #242927;
            color: #A7B0AB;
        }

        .focus-opportunity {
            background:
                linear-gradient(
                    135deg,
                    #151917,
                    #102A21
                );

            border-color:
                rgba(42, 143, 107, 0.3);
        }

        .focus-opportunity-title {
            color: #F5F7F6;
        }

        .focus-opportunity-text {
            color: #9AA5A0;
        }

        .focus-opportunity-review {
            background:
                linear-gradient(
                    135deg,
                    #151917,
                    #211D0F
                );

            border-color:
                rgba(185, 130, 8, 0.3);
        }

        .focus-card {
            background: #151917;
            border-color: #29312D;
        }

        .focus-count,
        .focus-label {
            color: #F5F7F6;
        }

        .focus-action {
            color: #9AA5A0;
        }

        .insight-card {
            background:
                linear-gradient(
                    135deg,
                    #151917,
                    #102A21
                );

            border-color:
                rgba(42, 143, 107, 0.3);
        }

        .insight-text {
            color: #F5F7F6;
        }

        .recommendation-card {
            background: #151917;
            border-color: #29312D;
        }

        .recommendation-item {
            color: #F5F7F6;
            border-color: #29312D;
        }

        .delivery-card {
            background: #102A21;
            border-color:
                rgba(42, 143, 107, 0.35);
        }

        .delivery-title {
            color: #6ED1A8;
        }

        .delivery-description {
            color: #F5F7F6;
        }

        .run-info-card {
            background: #151917;
            border-color: #29312D;
        }

        .run-info-value {
            color: #F5F7F6;
        }

        .opportunity-header {
            color: #7F8984;
            border-color: #29312D;
        }

        .opportunity-row {
            border-color: #29312D;
        }

        .opportunity-name,
        .opportunity-detail {
            color: #F5F7F6;
        }

        .opportunity-company {
            color: #9AA5A0;
        }

        .opportunity-high {
            background: #102A21;
            color: #6ED1A8;
        }

        .opportunity-medium {
            background: #332B13;
            color: #E8C96A;
        }

        .opportunity-low {
            background: #242927;
            color: #A7B0AB;
        }

        .footer {
            color: #7F8984;
        }
    }


    /* ========================================
       MOBILE
       ======================================== */

    @media (max-width: 768px) {

        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .section-title {
            margin-top: 1.5rem;
        }

        .health-score {
            font-size: 2.5rem;
        }

        .health-card {
            min-height: 190px;
        }

        .intel-hero-grid {
            grid-template-columns: 1fr;
        }

        .intel-hero-meta {
            width: fit-content;

            min-width: 0;

            text-align: left;
        }

        .intel-title {
            font-size: 1.35rem;
        }

        .opportunity-header {
            display: none;
        }

        .opportunity-row {
            grid-template-columns:
                1fr
                auto;

            gap: 0.65rem;
        }

        .opportunity-detail:nth-child(3) {
            display: none;
        }

        .opportunity-priority {
            justify-self: start;
        }

        .opportunity-score {
            text-align: right;
        }

        .focus-opportunity {
            padding: 1.1rem;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ========================================
# SESSION STATE
# ========================================

if "result" not in st.session_state:
    st.session_state.result = None

if "run_directory" not in st.session_state:
    st.session_state.run_directory = None

if "uploaded_file_bytes" not in st.session_state:
    st.session_state.uploaded_file_bytes = None

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

if "reanalyze_requested" not in st.session_state:
    st.session_state.reanalyze_requested = False

if "reanalyze_result" not in st.session_state:
    st.session_state.reanalyze_result = None


# ========================================
# HERO
# ========================================

st.html(
    """
    <style>

    .crm-hero {
        position: relative;
        overflow: hidden;

        padding: 44px 48px;
        margin: 0 0 40px 0;

        border-radius: 24px;

        background: #111111;
        border: 1px solid #111111;

        box-shadow:
            0 18px 45px
            rgba(0, 0, 0, 0.09);
    }

    .crm-hero-content {
        position: relative;
        z-index: 2;

        max-width: 760px;
    }

    .crm-hero-eyebrow {
        display: inline-block;

        margin-bottom: 16px;

        padding:
            6px
            11px;

        border-radius: 999px;

        background:
            rgba(15, 107, 79, 0.18);

        color: #72C9A8;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        font-size: 11px;

        font-weight: 700;

        letter-spacing: 0.12em;

        text-transform: uppercase;
    }

    .crm-hero-title {
        margin: 0;

        color: #FFFFFF;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        font-size: 44px;

        line-height: 1.04;

        letter-spacing: -0.045em;

        font-weight: 800;
    }

    .crm-hero-description {
        margin: 18px 0 0 0;

        max-width: 650px;

        color: #D1D5DB;

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            sans-serif;

        font-size: 17px;

        line-height: 1.65;
    }

    .crm-hero-orbit {
        position: absolute;

        width: 270px;
        height: 270px;

        right: -95px;
        top: -115px;

        border-radius: 50%;

        border:
            1px solid
            rgba(15, 107, 79, 0.45);

        box-shadow:
            0 0 0 35px
            rgba(15, 107, 79, 0.08),

            0 0 0 70px
            rgba(15, 107, 79, 0.04);
    }

    .crm-hero-orbit::after {
        content: "";

        position: absolute;

        width: 8px;
        height: 8px;

        right: 55px;
        bottom: 42px;

        border-radius: 50%;

        background: #2A8F6B;

        box-shadow:
            0 0 0 7px
            rgba(42, 143, 107, 0.12),

            0 0 24px
            rgba(42, 143, 107, 0.5);
    }

    @media (prefers-color-scheme: dark) {

        .crm-hero {
            background: #151917;
            border-color: #29312D;

            box-shadow:
                0 18px 45px
                rgba(0, 0, 0, 0.28);
        }

        .crm-hero-title {
            color: #F5F7F6;
        }

        .crm-hero-description {
            color: #AEB8B3;
        }

        .crm-hero-eyebrow {
            color: #6ED1A8;

            background:
                rgba(42, 143, 107, 0.16);
        }

        .crm-hero-orbit {
            border-color:
                rgba(42, 143, 107, 0.42);

            box-shadow:
                0 0 0 35px
                rgba(42, 143, 107, 0.08),

                0 0 0 70px
                rgba(42, 143, 107, 0.04);
        }

        .crm-hero-orbit::after {
            background: #36A77E;
        }
    }

    @media (max-width: 768px) {

        .crm-hero {
            padding: 32px 24px;

            border-radius: 19px;
        }

        .crm-hero-title {
            font-size: 34px;
        }

        .crm-hero-description {
            font-size: 15px;

            line-height: 1.6;
        }

        .crm-hero-orbit {
            width: 190px;
            height: 190px;

            right: -85px;
            top: -80px;
        }
    }

    </style>

    <div class="crm-hero">

        <div class="crm-hero-content">

            <div class="crm-hero-eyebrow">
                CRM Data Intelligence
            </div>

            <div class="crm-hero-title">
                Turn messy CRM data<br>
                into trusted data.
            </div>

            <div class="crm-hero-description">
                Clean, validate, deduplicate and analyze your CRM data
                before it enters your workflow.
            </div>

        </div>

        <div class="crm-hero-orbit"></div>

    </div>
    """
)


# ========================================
# SIDEBAR
# ========================================

with st.sidebar:

    st.html(
        """
        <div class="sidebar-brand">

            <div class="sidebar-logo">
                ◆
            </div>

            <div class="sidebar-title">
                CRM Intelligence
            </div>

            <div class="sidebar-description">
                Clean and prepare customer data
                for reliable CRM operations.
            </div>

        </div>
        """
    )

    st.divider()

    st.html(
        """
        <div class="sidebar-description">
            Your dataset passes through the existing
            cleanup, validation, duplicate detection,
            CRM and intelligence engine.
        </div>
        """
    )

    st.html(
        """
        <div class="sidebar-footer">
            Data processing is handled by your
            existing CRM automation pipeline.
        </div>
        """
    )


# ========================================
# CLIENT INPUT
# ========================================

st.html(
    """
    <div class="section-title">

        <span class="section-number">
            01
        </span>

        Client information

    </div>
    """
)

client_col, dataset_col = st.columns(2)

with client_col:

    client_name = st.text_input(
        "Client name",
        placeholder="e.g. ABC Company",
    )

with dataset_col:

    dataset_name = st.text_input(
        "Dataset name",
        placeholder="e.g. September Leads",
    )


# ========================================
# FILE UPLOAD
# ========================================

st.html(
    """
    <div class="section-title">

        <span class="section-number">
            02
        </span>

        Upload CRM dataset

    </div>
    """
)

uploaded_file = st.file_uploader(
    "Upload a CSV file",
    type=["csv"],
    key="crm_csv_uploader",
    help="Upload a CSV containing your CRM or customer records.",
)


# ========================================
# STORE UPLOADED FILE
# ========================================

if uploaded_file is not None:

    try:

        file_bytes = uploaded_file.getvalue()

        st.session_state.uploaded_file_bytes = (
            file_bytes
        )

        st.session_state.uploaded_filename = (
            uploaded_file.name
        )

    except Exception as error:

        st.session_state.uploaded_file_bytes = None

        st.session_state.uploaded_filename = None

        st.error(
            f"Unable to store the uploaded CSV: {error}"
        )


# ========================================
# RESTORE DATASET
# ========================================

dataframe = None

source_filename = (
    st.session_state.uploaded_filename
)

if (
    st.session_state.uploaded_file_bytes
    is not None
):

    try:

        dataframe = pd.read_csv(
            BytesIO(
                st.session_state.uploaded_file_bytes
            ),
            dtype={"phone": str},
        )

    except Exception as error:

        st.session_state.uploaded_file_bytes = None

        st.session_state.uploaded_filename = None

        st.error(
            f"Unable to read the uploaded CSV: {error}"
        )

        dataframe = None


# ========================================
# DATASET PREVIEW
# ========================================

if dataframe is not None:

    st.success(
        f"CSV loaded successfully — "
        f"{len(dataframe)} records, "
        f"{len(dataframe.columns)} columns."
    )

    with st.expander(
        "Preview uploaded dataset",
        expanded=True,
    ):

        st.dataframe(
            dataframe.head(10),
            width="stretch",
        )


# ========================================
# RUN CLEANUP
# ========================================

st.html(
    """
    <div class="section-title">

        <span class="section-number">
            03
        </span>

        Run CRM intelligence

    </div>
    """
)

reprocess_existing_ai = st.checkbox(
    "Re-run AI analysis for existing CRM records",
    value=False,
    help=(
        "By default, previously analyzed CRM records reuse their existing intelligence. "
        "Enable this only when you want NVIDIA AI to analyze them again."
    ),
)

run_cleanup = st.button(
    "Run CRM Cleanup",
    type="primary",
    width="stretch",
)


if run_cleanup:

    if not client_name.strip():

        st.error(
            "Please enter a client name."
        )

        st.stop()

    if not dataset_name.strip():

        st.error(
            "Please enter a dataset name."
        )

        st.stop()

    if (
        dataframe is None
        or st.session_state.uploaded_file_bytes is None
    ):

        st.error(
            "Please upload a CSV file."
        )

        st.stop()

    if not source_filename:

        st.error(
            "The uploaded CSV filename could not be detected."
        )

        st.stop()

    try:

        with st.status(
            "Processing CRM dataset...",
            expanded=True,
        ) as status:

            st.write(
                "Creating cleanup run..."
            )

            run_directory = (
                create_run_directory(
                    client_name
                )
            )

            st.write(
                "Standardizing CRM fields..."
            )

            standardized_dataframe = (
                standardize_dataset(
                    dataframe
                )
            )

            st.write(
                "Validating records..."
            )

            validated_dataframe = (
                validate_dataset(
                    standardized_dataframe
                )
            )

            st.write(
                "Detecting duplicate records..."
            )

            duplicate_dataframe = (
                detect_duplicates(
                    validated_dataframe
                )
            )

            st.write(
                "Calculating data quality..."
            )

            metrics = (
                calculate_quality_metrics(
                    duplicate_dataframe
                )
            )

            health = (
                calculate_quality_health(
                    duplicate_dataframe
                )
            )

            st.write(
                "Saving CRM records and generating reports..."
            )

            result = export_results(
                duplicate_dataframe,
                client_name,
                dataset_name,
                run_directory,
                source_filename,
            )

            # Existing CRM records are normally reused to avoid unnecessary
            # NVIDIA API calls. When explicitly requested, refresh their AI
            # intelligence after the cleanup/import stage.
            reanalysis = {
                "total": 0,
                "analyzed": 0,
                "failed": 0,
                "errors": [],
            }

            if reprocess_existing_ai:
                st.write(
                    "Re-running AI intelligence for existing CRM records..."
                )
                reanalysis = reanalyze_uploaded_leads(
                    dataframe
                )

            result["ai_reanalysis"] = reanalysis

            status.update(
                label="CRM processing completed.",
                state="complete",
                expanded=False,
            )

        st.session_state.result = {
            "result": result,
            "dataframe": duplicate_dataframe,
            "metrics": metrics,
            "health": health,
            "run_directory": run_directory,
            "client_name": client_name,
            "dataset_name": dataset_name,
            "source_file": source_filename,
            "ai_reanalysis": result.get(
                "ai_reanalysis",
                {},
            ),
        }

        st.session_state.run_directory = (
            run_directory
        )

        st.success(
            "CRM cleanup and intelligence processing completed."
        )

    except Exception as error:

        st.error(
            f"CRM processing failed: {error}"
        )

        st.stop()


# ========================================
# DISPLAY RESULTS
# ========================================

session_result = (
    st.session_state.result
)

if session_result is not None:

    result = session_result["result"]

    metrics = session_result["metrics"]

    health = session_result["health"]

    st.divider()


    # ====================================
    # RESULTS HEADER
    # ====================================

    st.html(
        """
        <div class="section-title">
            CRM intelligence results
        </div>
        """
    )

    st.caption(
        "A summary of the quality, cleanliness and readiness of your CRM dataset."
    )


    # ====================================
    # KPI OVERVIEW
    # ====================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Total Leads",
            metrics["total_records"],
        )

    with col2:

        st.metric(
            "Clean Records",
            metrics["clean_records"],
        )

    with col3:

        st.metric(
            "Duplicate Records",
            metrics["duplicate_records"],
        )

    with col4:

        st.metric(
            "Review Required",
            metrics["possible_duplicate_records"],
        )


    # ====================================
    # HEALTH OVERVIEW
    # ====================================

    st.html(
        """
        <div class="section-title">
            Data quality overview
        </div>
        """
    )

    health_col, quality_col = st.columns(
        [0.85, 1.15]
    )

    with health_col:

        overall_health = safe_float(
            health["overall_health_score"]
        )

        health_status = str(
            health["health_status"]
        ).upper()

        if overall_health >= 90:

            health_class = (
                "health-excellent"
            )

        elif overall_health >= 70:

            health_class = (
                "health-good"
            )

        elif overall_health >= 50:

            health_class = (
                "health-fair"
            )

        else:

            health_class = (
                "health-poor"
            )

        st.html(
            f"""
            <div class="health-card {health_class}">

                <div class="health-content">

                    <div class="health-label">
                        Overall data health
                    </div>

                    <div class="health-score">
                        {overall_health:.1f}%
                    </div>

                    <div class="health-status">

                        <span class="health-status-dot"></span>

                        {escape(health_status)}

                    </div>

                    <div class="health-description">
                        Based on the current validation,
                        completeness and duplicate checks.
                    </div>

                </div>

            </div>
            """
        )

    with quality_col:

        validity = safe_float(
            health["validity_score"]
        )

        completeness = safe_float(
            health["completeness_score"]
        )

        overall = safe_float(
            health["overall_health_score"]
        )

        st.html(
            f"""
            <div class="dashboard-card">

                <div class="dashboard-card-title">
                    Quality signals
                </div>

                <div class="quality-row">

                    <div class="quality-row-header">

                        <span>
                            Overall health
                        </span>

                        <span class="quality-row-value">
                            {overall:.1f}%
                        </span>

                    </div>

                    <div class="quality-progress">

                        <div
                            class="quality-progress-fill"
                            style="
                                width:
                                {max(
                                    0,
                                    min(
                                        100,
                                        overall
                                    )
                                )}%;
                            "
                        ></div>

                    </div>

                </div>

                <div class="quality-row">

                    <div class="quality-row-header">

                        <span>
                            Validity
                        </span>

                        <span class="quality-row-value">
                            {validity:.1f}%
                        </span>

                    </div>

                    <div class="quality-progress">

                        <div
                            class="quality-progress-fill"
                            style="
                                width:
                                {max(
                                    0,
                                    min(
                                        100,
                                        validity
                                    )
                                )}%;
                            "
                        ></div>

                    </div>

                </div>

                <div class="quality-row">

                    <div class="quality-row-header">

                        <span>
                            Completeness
                        </span>

                        <span class="quality-row-value">
                            {completeness:.1f}%
                        </span>

                    </div>

                    <div class="quality-progress">

                        <div
                            class="quality-progress-fill"
                            style="
                                width:
                                {max(
                                    0,
                                    min(
                                        100,
                                        completeness
                                    )
                                )}%;
                            "
                        ></div>

                    </div>

                </div>

            </div>
            """
        )


    # ====================================
    # HEALTH MESSAGE
    # ====================================

    health_status_upper = str(
        health["health_status"]
    ).upper()

    if health_status_upper == "EXCELLENT":

        st.html(
            """
            <div class="success-box">

                <strong>
                    Dataset is ready.
                </strong>

                <br>

                The dataset passed the current CRM quality
                checks with no major issues detected.

            </div>
            """
        )

    elif health_status_upper in [
        "GOOD",
        "FAIR",
    ]:

        st.info(
            f"Health status: {health_status_upper}. "
            "Some records may require attention before use."
        )

    else:

        st.html(
            f"""
            <div class="warning-box">

                <strong>
                    Dataset requires attention.
                </strong>

                <br>

                Health status:
                {escape(health_status_upper)}.

                Some records require additional review.

            </div>
            """
        )


    # ====================================
    # RECORD BREAKDOWN
    # ====================================

    st.html(
        """
        <div class="section-title">
            Record breakdown
        </div>
        """
    )

    breakdown_col1, breakdown_col2 = (
        st.columns(2)
    )

    with breakdown_col1:

        st.html(
            f"""
            <div class="dashboard-card">

                <div class="dashboard-card-title">
                    Validation
                </div>

                <div class="dashboard-card-value">
                    {safe_int(
                        metrics["clean_records"]
                    )}
                </div>

                <div class="dashboard-card-description">
                    Clean records ready for CRM processing.
                </div>

                <br>

                <strong>
                    Validation review:
                </strong>

                {safe_int(
                    metrics["review_records"]
                )}

            </div>
            """
        )

    with breakdown_col2:

        st.html(
            f"""
            <div class="dashboard-card">

                <div class="dashboard-card-title">
                    Duplicate detection
                </div>

                <div class="dashboard-card-value">
                    {safe_int(
                        metrics["unique_records"]
                    )}
                </div>

                <div class="dashboard-card-description">
                    Unique records identified in the dataset.
                </div>

                <br>

                <strong>
                    Confirmed duplicates:
                </strong>

                {safe_int(
                    metrics["duplicate_records"]
                )}

                <br>

                <strong>
                    Review required:
                </strong>

                {safe_int(
                    metrics["possible_duplicate_records"]
                )}

            </div>
            """
        )


    # ====================================
    # AI ANALYSIS STATUS
    # ====================================

    ai_result = result.get(
        "ai_analysis",
        {},
    )

    if not isinstance(
        ai_result,
        dict,
    ):

        ai_result = {}

    ai_attempted = safe_int(
        ai_result.get(
            "total",
            0,
        )
    )

    ai_completed = safe_int(
        ai_result.get(
            "analyzed",
            0,
        )
    )

    ai_failed = safe_int(
        ai_result.get(
            "failed",
            0,
        )
    )

    # Include explicit AI re-analysis in the displayed run metrics.
    ai_reanalysis = session_result.get(
        "ai_reanalysis",
        result.get("ai_reanalysis", {}),
    )
    if not isinstance(ai_reanalysis, dict):
        ai_reanalysis = {}

    reanalysis_attempted = safe_int(
        ai_reanalysis.get("total", 0)
    )
    reanalysis_completed = safe_int(
        ai_reanalysis.get("analyzed", 0)
    )
    reanalysis_failed = safe_int(
        ai_reanalysis.get("failed", 0)
    )

    ai_attempted += reanalysis_attempted
    ai_completed += reanalysis_completed
    ai_failed += reanalysis_failed


    st.html(
        """
        <div class="section-title">
            AI intelligence
        </div>
        """
    )

    ai_status_col, ai_metrics_col = (
        st.columns(
            [0.8, 1.2]
        )
    )

    with ai_status_col:

        if ai_attempted == 0:

            st.html(
                """
                <div class="dashboard-card">

                    <div class="dashboard-card-title">
                        AI analysis
                    </div>

                    <div class="dashboard-card-value">
                        Existing CRM intelligence
                    </div>

                    <div class="dashboard-card-description">
                        Existing CRM intelligence was reused for this run.
                        Enable re-analysis above when you want fresh NVIDIA AI results.
                    </div>

                </div>
                """
            )

        elif ai_failed > 0:

            st.html(
                """
                <div class="dashboard-card">

                    <div class="dashboard-card-title">
                        AI analysis
                    </div>

                    <div class="dashboard-card-value">
                        Partial
                    </div>

                    <div class="dashboard-card-description">
                        Some records were analyzed successfully,
                        while others require another attempt.
                    </div>

                </div>
                """
            )

        else:

            st.html(
                """
                <div class="dashboard-card">

                    <div class="dashboard-card-title">
                        AI analysis
                    </div>

                    <div class="dashboard-card-value">
                        Complete
                    </div>

                    <div class="dashboard-card-description">
                        AI intelligence was successfully generated
                        for the processed CRM records.
                    </div>

                </div>
                """
            )

    with ai_metrics_col:

        ai_col1, ai_col2, ai_col3 = (
            st.columns(3)
        )

        with ai_col1:

            st.metric(
                "Attempted",
                ai_attempted,
            )

        with ai_col2:

            st.metric(
                "Completed",
                ai_completed,
            )

        with ai_col3:

            st.metric(
                "Failed",
                ai_failed,
            )

    if ai_failed > 0:

        st.warning(
            "Some AI analyses failed. "
            "The affected CRM leads remain stored safely "
            "and can be analyzed again later."
        )


    # ====================================
    # CRM INTELLIGENCE DASHBOARD
    # ====================================

    intelligence_report = None

    current_batch_id = (
        get_batch_id_from_result(
            result
        )
    )

    intelligence_batch_id = (
        current_batch_id
    )

    using_existing_intelligence = False

    try:

        # First try the current processing batch.
        if current_batch_id is not None:

            intelligence_report = (
                get_crm_intelligence_report(
                    batch_id=current_batch_id
                )
            )

        # If the current batch contains zero analyzed records,
        # this can mean the uploaded records already existed.
        #
        # In that case, find the previous batch that actually
        # contains AI intelligence for these same records.
        current_intelligence = (
            extract_intelligence_metrics(
                intelligence_report
            )
            if intelligence_report
            else {}
        )

        current_analyzed = safe_int(
            current_intelligence.get(
                "analyzed_leads",
                0,
            )
        )

        current_total = safe_int(
            current_intelligence.get(
                "total_leads",
                0,
            )
        )

        # If the current import batch contains no records, the uploaded
        # leads may already exist in the CRM. In that case, find the
        # original batch containing those same leads.
        #
        # Re-analysis updates existing CRM records without changing
        # their original import_batch_id, so this lookup is also required
        # when AI re-analysis completed in the current run.

        should_find_existing_batch = (
            dataframe is not None
            and (
                (
                    current_batch_id is not None
                    and current_analyzed == 0
                    and current_total == 0
                )
                or reanalysis_completed > 0
                or (
                    ai_completed > 0
                    and current_analyzed == 0
                )
            )
        )

        if should_find_existing_batch:

            existing_batch_id = (
                find_existing_intelligence_batch(
                    dataframe,
                    current_batch_id,
                )
            )

            if (
                existing_batch_id is not None
                and existing_batch_id != current_batch_id
            ):

                existing_report = (
                    get_crm_intelligence_report(
                        batch_id=existing_batch_id
                    )
                )

                existing_metrics = (
                    extract_intelligence_metrics(
                        existing_report
                    )
                    if existing_report
                    else {}
                )

                existing_total = safe_int(
                    existing_metrics.get(
                        "total_leads",
                        0,
                    )
                )

                if existing_total > 0:

                    intelligence_report = (
                        existing_report
                    )

                    intelligence_batch_id = (
                        existing_batch_id
                    )

                    using_existing_intelligence = (
                        True
                    )

        # IMPORTANT:
        # Do not fall back to the global CRM intelligence report.
        #
        # The global report contains every historical CRM record and
        # caused this dashboard to display 26 leads / 22 analyzed
        # instead of the 3 records processed in the current run.
        #
        # If no relevant batch-specific report exists, leave the
        # intelligence report empty rather than showing unrelated
        # historical CRM intelligence.

    except Exception:

        intelligence_report = None


    if intelligence_report:

        intelligence = (
            extract_intelligence_metrics(
                intelligence_report
            )
        )

        existing_analyzed = (
            intelligence[
                "analyzed_leads"
            ]
        )

        if (
            existing_analyzed > 0
            or intelligence[
                "high_priority"
            ] > 0
            or intelligence[
                "priority_counts"
            ]
            or intelligence[
                "intent_counts"
            ]
            or intelligence[
                "product_counts"
            ]
            or intelligence[
                "recommended_focus"
            ]
        ):

            st.html(
                """
                <div class="section-title">
                    Lead intelligence dashboard
                </div>
                """
            )

            if using_existing_intelligence:

                st.caption(
                    "Showing existing AI intelligence for records "
                    "that were already processed. No new AI analysis "
                    "was required for this run."
                )

            elif ai_attempted > 0:

                st.caption(
                    "AI-powered signals generated from the CRM records processed in this run."
                )

            else:

                st.caption(
                    "Existing AI intelligence was found for this CRM batch."
                )


            # ====================================
            # INTELLIGENCE HERO
            # ====================================

            render_intelligence_header(
                intelligence,
                intelligence_batch_id,
                ai_attempted,
            )


            # ====================================
            # INTELLIGENCE OVERVIEW
            # ====================================

            st.html(
                """
                <div style="height: 14px;"></div>
                """
            )

            intel_col1, intel_col2, intel_col3, intel_col4, intel_col5 = (
                st.columns(5)
            )

            total_for_display = (
                intelligence["total_leads"]
                or (
                    intelligence["analyzed_leads"]
                    + intelligence["unanalyzed_leads"]
                )
                or ai_attempted
                or ai_completed
            )

            with intel_col1:

                render_intelligence_stat_card(
                    "Total leads",
                    total_for_display,
                    "CRM records represented in this intelligence view.",
                    "green",
                )

            with intel_col2:

                render_intelligence_stat_card(
                    "AI analyzed",
                    intelligence["analyzed_leads"],
                    "Leads with AI-generated intelligence.",
                    "green",
                )

            with intel_col3:

                render_intelligence_stat_card(
                    "AI pending",
                    intelligence["unanalyzed_leads"],
                    "Leads still waiting for AI intelligence.",
                    "amber",
                )

            with intel_col4:

                render_intelligence_stat_card(
                    "Average score",
                    f"{intelligence['average_score']:.2f}",
                    "Average AI lead score across analyzed records.",
                    "green",
                )

            with intel_col5:

                render_intelligence_stat_card(
                    "High priority",
                    intelligence["high_priority"],
                    "Leads currently requiring the most attention.",
                    "amber",
                )


            # ====================================
            # PRIORITY FOCUS
            # ====================================

            st.html(
                """
                <div class="section-title">
                    Priority focus
                </div>
                """
            )

            render_priority_focus(
                intelligence
            )


            # ====================================
            # PRIORITY DISTRIBUTION
            # ====================================

            st.html(
                """
                <div class="section-title">
                    Lead signals
                </div>
                """
            )

            high_priority = (
                intelligence[
                    "high_priority"
                ]
            )

            medium_priority = (
                intelligence[
                    "medium_priority"
                ]
            )

            low_priority = (
                intelligence[
                    "low_priority"
                ]
            )

            render_priority_cards(
                high_priority,
                medium_priority,
                low_priority,
            )

            st.html(
                """
                <div style="height: 12px;"></div>
                """
            )


            # ====================================
            # DISTRIBUTIONS
            # ====================================

            distribution_col1, distribution_col2 = (
                st.columns(2)
            )

            with distribution_col1:

                priority_items = (
                    intelligence[
                        "priority_counts"
                    ]
                )

                if not priority_items:

                    priority_items = {
                        "High": high_priority,
                        "Medium": medium_priority,
                        "Low": low_priority,
                    }

                render_distribution_card(
                    "Priority distribution",
                    priority_items,
                )

            with distribution_col2:

                if intelligence[
                    "intent_counts"
                ]:

                    render_distribution_card(
                        "Intent distribution",
                        intelligence[
                            "intent_counts"
                        ],
                    )

                else:

                    st.html(
                        """
                        <div class="dashboard-card intelligence-card">

                            <div class="dashboard-card-title">
                                Intent distribution
                            </div>

                            <div class="dashboard-card-description">
                                No intent distribution is available
                                for this intelligence set yet.
                            </div>

                        </div>
                        """
                    )


            # ====================================
            # PRODUCT DEMAND
            # ====================================

            if intelligence[
                "product_counts"
            ]:

                st.html(
                    """
                    <div class="section-title">
                        Product demand
                    </div>
                    """
                )

                render_distribution_card(
                    "Top products",
                    intelligence[
                        "product_counts"
                    ],
                )


            # ====================================
            # TOP OPPORTUNITIES
            # ====================================

            opportunities = (
                get_top_opportunities(
                    intelligence_batch_id
                )
            )

            if opportunities:

                st.html(
                    """
                    <div class="section-title">
                        Top opportunities
                    </div>
                    """
                )

                st.caption(
                    "Highest-scoring AI-analyzed leads in this intelligence set."
                )

                render_opportunity_table(
                    opportunities
                )


            # ====================================
            # RECOMMENDED NEXT ACTIONS
            # ====================================

            follow_up_metrics = get_follow_up_metrics(
                intelligence_batch_id
            )

            render_follow_up_metrics(
                follow_up_metrics
            )

            follow_up_queue = get_follow_up_queue(
                intelligence_batch_id
            )

            if follow_up_queue:

                st.html(
                    """
                    <div class="section-title">
                        Follow-up queue
                    </div>
                    """
                )

                st.caption(
                    "Active leads that need salesperson attention."
                )

                filter_col1, filter_col2, filter_col3 = (
                    st.columns([1, 1, 2])
                )

                with filter_col1:
                    priority_filter = st.selectbox(
                        "Priority",
                        ["All", "High", "Medium", "Low"],
                        key="follow_up_priority_filter",
                    )

                with filter_col2:
                    status_filter = st.selectbox(
                        "Action status",
                        ["All", "Pending", "In Progress"],
                        key="follow_up_status_filter",
                    )

                with filter_col3:
                    search_filter = st.text_input(
                        "Search lead or company",
                        key="follow_up_search_filter",
                        placeholder="Enter a name or company",
                    )

                filtered_queue = []

                for row in follow_up_queue:
                    (
                        lead_id,
                        name,
                        company,
                        priority,
                        lead_score,
                        recommended_action,
                        follow_up_timing,
                        action_status,
                        action_completed_at,
                        lead_status,
                    ) = row

                    if (
                        priority_filter != "All"
                        and str(priority or "LOW").upper()
                        != priority_filter.upper()
                    ):
                        continue

                    if (
                        status_filter != "All"
                        and str(action_status or "PENDING").upper()
                        != status_filter.upper()
                    ):
                        continue

                    search_text = (
                        f"{name or ''} {company or ''}"
                    ).casefold()

                    if (
                        search_filter.strip()
                        and search_filter.strip().casefold()
                        not in search_text
                    ):
                        continue

                    filtered_queue.append(row)

                st.caption(
                    f"Showing {len(filtered_queue)} of "
                    f"{len(follow_up_queue)} active follow-up leads."
                )

                if filtered_queue:
                    render_follow_up_queue(filtered_queue)
                else:
                    st.info(
                        "No follow-up leads match these filters."
                    )


            recommended_actions = (
                get_recommended_actions(
                    intelligence_batch_id
                )
            )

            if recommended_actions:

                st.html(
                    """
                    <div class="section-title">
                        Recommended next actions
                    </div>
                    """
                )

                st.caption(
                    "AI-generated next steps and follow-up timing for leads in this intelligence set."
                )

                render_recommended_actions(
                    recommended_actions
                )


            # ====================================
            # RECOMMENDED FOCUS
            # ====================================

            recommended_focus = (
                extract_recommendation_items(
                    intelligence_report
                )
            )

            # Keep the normalized intelligence dictionary
            # synchronized so priority-focus logic can use
            # the recommendation counts.
            intelligence[
                "recommended_focus"
            ] = recommended_focus

            if recommended_focus:

                st.html(
                    """
                    <div class="section-title">
                        Recommended focus
                    </div>
                    """
                )

                render_focus_cards(
                    recommended_focus
                )

                render_recommendation_card(
                    recommended_focus
                )


            # ====================================
            # KEY INSIGHTS
            # ====================================

            demand_insights = (
                intelligence_report.get(
                    "demand_insights",
                    {},
                )
            )

            if isinstance(
                demand_insights,
                dict,
            ):

                insight_items = []

                for key, value in (
                    demand_insights.items()
                ):

                    if isinstance(
                        value,
                        str,
                    ):

                        insight_items.append(
                            (
                                normalize_label(
                                    key
                                ),
                                value,
                            )
                        )

                if insight_items:

                    st.html(
                        """
                        <div class="section-title">
                            Key insights
                        </div>
                        """
                    )

                    insight_columns = st.columns(
                        min(
                            2,
                            len(
                                insight_items[:4]
                            ),
                        )
                    )

                    for index, (
                        title,
                        text_value,
                    ) in enumerate(
                        insight_items[:4]
                    ):

                        with insight_columns[
                            index
                            % len(
                                insight_columns
                            )
                        ]:

                            st.html(
                                f"""
                                <div class="insight-card">

                                    <div class="insight-title">
                                        {escape(title)}
                                    </div>

                                    <div class="insight-text">
                                        {escape(
                                            str(
                                                text_value
                                            )
                                        )}
                                    </div>

                                </div>
                                """
                            )


            # ====================================
            # BATCH INFORMATION
            # ====================================

            batch_info = (
                intelligence_report.get(
                    "batch",
                    {},
                )
            )

            if isinstance(
                batch_info,
                dict,
            ):

                batch_number = (
                    get_first_value(
                        batch_info,
                        [
                            "batch_id",
                            "id",
                        ],
                        intelligence_batch_id,
                    )
                )

                imported_count = (
                    get_first_value(
                        batch_info,
                        [
                            "imported_count",
                            "imported",
                            "records",
                        ],
                        intelligence[
                            "total_leads"
                        ],
                    )
                )

                st.html(
                    f"""
                    <div style="height: 14px;"></div>

                    <div class="dashboard-card">

                        <div class="dashboard-card-title">
                            Intelligence source
                        </div>

                        <div class="dashboard-card-description">

                            Intelligence Batch ID
                            <strong>
                                {escape(
                                    str(
                                        batch_number
                                    )
                                )}
                            </strong>

                            ·

                            {safe_int(
                                imported_count
                            )}

                            records represented in
                            the CRM intelligence view.

                        </div>

                    </div>
                    """
                )


        else:

            st.html(
                """
                <div class="section-title">
                    Lead intelligence dashboard
                </div>

                <div class="dashboard-card">

                    <div class="dashboard-card-title">
                        Intelligence unavailable
                    </div>

                    <div class="dashboard-card-value">
                        No AI intelligence yet
                    </div>

                    <div class="dashboard-card-description">
                        No AI-generated intelligence was found
                        for these CRM records. Once records are
                        analyzed, lead priority, intent, product
                        demand and recommended actions will appear here.
                    </div>

                </div>
                """
            )

    elif ai_completed == 0:

        st.html(
            """
            <div class="section-title">
                Lead intelligence dashboard
            </div>

            <div class="dashboard-card">

                <div class="dashboard-card-title">
                    Intelligence unavailable
                </div>

                <div class="dashboard-card-value">
                    No AI intelligence yet
                </div>

                <div class="dashboard-card-description">
                    No AI-generated intelligence was found for
                    these CRM records. Once records are processed,
                    lead priority, intent, product demand and
                    recommended actions will appear here.
                </div>

            </div>
            """
        )


    # ====================================
    # CLIENT DELIVERY
    # ====================================

    delivery_package = result.get(
        "client_delivery"
    )

    if delivery_package:

        st.html(
            """
            <div class="section-title">
                Client delivery
            </div>
            """
        )

        st.html(
            """
            <div class="delivery-card">

                <div class="delivery-title">
                    Your CRM dataset is ready.
                </div>

                <div class="delivery-description">
                    Your cleaned dataset, intelligence reports
                    and delivery summary have been generated.
                </div>

            </div>
            """
        )

        delivery_directory = Path(
            delivery_package["directory"]
        )

        html_path = (
            delivery_package.get(
                "html_report"
            )
        )

        txt_path = (
            delivery_package.get(
                "txt_report"
            )
        )

        cleaned_path = (
            delivery_package.get(
                "cleaned_dataset"
            )
        )

        summary_path = (
            delivery_package.get(
                "delivery_summary"
            )
        )

        st.html(
            """
            <div class="section-title">
                Download deliverables
            </div>
            """
        )

        download_col1, download_col2 = (
            st.columns(2)
        )

        with download_col1:

            if (
                html_path
                and Path(
                    html_path
                ).exists()
            ):

                with open(
                    html_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download HTML Report",
                        data=file.read(),
                        file_name=(
                            "CRM Intelligence Report.html"
                        ),
                        mime="text/html",
                        width="stretch",
                    )

            if (
                cleaned_path
                and Path(
                    cleaned_path
                ).exists()
            ):

                with open(
                    cleaned_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download Cleaned Dataset",
                        data=file.read(),
                        file_name=(
                            "Cleaned Dataset.csv"
                        ),
                        mime="text/csv",
                        width="stretch",
                    )

        with download_col2:

            if (
                txt_path
                and Path(
                    txt_path
                ).exists()
            ):

                with open(
                    txt_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download TXT Report",
                        data=file.read(),
                        file_name=(
                            "CRM Intelligence Report.txt"
                        ),
                        mime="text/plain",
                        width="stretch",
                    )

            if (
                summary_path
                and Path(
                    summary_path
                ).exists()
            ):

                with open(
                    summary_path,
                    "rb",
                ) as file:

                    st.download_button(
                        "Download Delivery Summary",
                        data=file.read(),
                        file_name=(
                            "Delivery Summary.txt"
                        ),
                        mime="text/plain",
                        width="stretch",
                    )

        with st.expander(
            "View delivery location",
            expanded=False,
        ):

            st.code(
                str(
                    delivery_directory
                ),
                language="text",
            )


    # ====================================
    # RUN INFORMATION
    # ====================================

    st.html(
        """
        <div class="section-title">
            Run information
        </div>
        """
    )

    st.html(
        f"""
        <div class="run-info-card">

            <div class="run-info-item">

                <div class="run-info-label">
                    Client
                </div>

                <div class="run-info-value">
                    {escape(
                        str(
                            session_result[
                                "client_name"
                            ]
                        )
                    )}
                </div>

            </div>

            <div class="run-info-item">

                <div class="run-info-label">
                    Dataset
                </div>

                <div class="run-info-value">
                    {escape(
                        str(
                            session_result[
                                "dataset_name"
                            ]
                        )
                    )}
                </div>

            </div>

            <div class="run-info-item">

                <div class="run-info-label">
                    Source file
                </div>

                <div class="run-info-value">
                    {escape(
                        str(
                            session_result[
                                "source_file"
                            ]
                        )
                    )}
                </div>

            </div>

        </div>
        """
    )

    with st.expander(
        "View internal run directory",
        expanded=False,
    ):

        st.code(
            str(
                session_result[
                    "run_directory"
                ]
            ),
            language="text",
        )


# ========================================
# FOOTER
# ========================================

st.divider()

st.html(
    """
    <div class="footer">

        CRM Intelligence ·
        Data cleaning ·
        Validation ·
        Duplicate detection ·
        AI analysis ·
        Reporting

    </div>
    """
)