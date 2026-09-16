from app.error_handler import handle_error

from app.validation import (
    validate_name,
    validate_email,
    validate_phone,
    validate_company,
    validate_message,
    validate_priority,
    validate_lead_score,
)

from app.view_leads import (
    get_all_leads,
    search_leads_by_email,
    search_leads_by_priority,
    get_lead_by_id,
    search_leads_by_status,
)

from app.database import (
    insert_lead,
    update_lead,
    update_lead_status,
    get_dashboard_stats,
    delete_lead,
    create_lead_activity,
    get_lead_activities,
    get_import_batches,
    get_leads_by_import_batch,
    get_usage_analytics,
    track_usage,
)

from app.lead_cleaner import clean_lead
from app.lead_analyzer import analyze_lead
from app.duplicate_detector import is_potential_duplicate


# ========================================
# ALLOWED LEAD STATUSES
# ========================================

ALLOWED_STATUSES = [
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "CONVERTED",
    "LOST",
]


# ========================================
# USAGE TRACKING CONTEXT
# ========================================

CLIENT_ID = "CLIENT_A"
USER_ID = "USER_001"


def record_usage(
    event_type,
    tool_used="CRM CLI",
    records_affected=0,
    metadata=None
):
    """
    Record CRM usage without allowing analytics
    failures to interrupt normal CRM operations.
    """

    try:

        track_usage(
            client_id=CLIENT_ID,
            user_id=USER_ID,
            event_type=event_type,
            tool_used=tool_used,
            records_affected=records_affected,
            metadata=metadata
        )

    except Exception as error:

        print(
            f"\nWarning: Usage tracking failed: {error}"
        )


# ========================================
# DISPLAY MENU
# ========================================

def show_menu():
    """Display the CRM menu."""

    print("\n========================================")
    print("          AI CRM AUTOMATION")
    print("========================================")
    print("1. Add new lead")
    print("2. View all leads")
    print("3. Search by email")
    print("4. Search by priority")
    print("5. View lead by ID")
    print("6. Update priority and score")
    print("7. Update lead status")
    print("8. Search by status")
    print("9. Delete lead")
    print("10. View dashboard")
    print("11. View lead activity history")
    print("12. View import batch history")
    print("13. View usage analytics")
    print("14. Exit")
    print("========================================")


# ========================================
# DISPLAY LEAD
# ========================================

def display_lead(lead):
    """Display a single CRM lead."""

    print(f"\nID: {lead[0]}")
    print(f"Name: {lead[1]}")
    print(f"Email: {lead[2]}")
    print(f"Phone: {lead[3]}")
    print(f"Company: {lead[4]}")
    print(f"Product: {lead[10]}")
    print(f"Quantity: {lead[11]}")
    print(f"Priority: {lead[13]}")
    print(f"Lead Score: {lead[14]}")
    print(f"Status: {lead[16]}")

    if lead[6]:
        print("Duplicate: YES")
        print(f"Duplicate Reason: {lead[7]}")
    else:
        print("Duplicate: NO")

    print("----------------------------------------")


# ========================================
# VALIDATE NEW LEAD
# ========================================

def validate_new_lead(lead):
    """Validate all required customer lead fields."""

    validations = [
        ("Name", validate_name(lead["name"])),
        ("Email", validate_email(lead["email"])),
        ("Phone", validate_phone(lead["phone"])),
        ("Company", validate_company(lead["company"])),
        ("Message", validate_message(lead["message"])),
    ]

    errors = []

    for field_name, result in validations:

        valid, message = result

        if not valid:
            errors.append(
                f"{field_name}: {message}"
            )

    return errors


# ========================================
# VALIDATE STATUS
# ========================================

def validate_status(status):
    """Validate a lead status."""

    status = status.upper()

    if status not in ALLOWED_STATUSES:

        return (
            False,
            "Status must be one of: "
            + ", ".join(ALLOWED_STATUSES)
        )

    return True, "Valid status"


# ========================================
# CHECK FOR DUPLICATES
# ========================================

def check_for_duplicate(cleaned_lead):
    """Compare a new lead against existing CRM leads."""

    existing_leads = get_all_leads()

    for existing_lead in existing_leads:

        existing_lead_data = {
            "name": existing_lead[1],
            "email": existing_lead[2],
            "phone": existing_lead[3],
            "company": existing_lead[4],
            "message": existing_lead[5],
        }

        duplicate, reason = is_potential_duplicate(
            cleaned_lead,
            existing_lead_data
        )

        if duplicate:
            return True, reason

    return False, "No obvious duplicate match"


# ========================================
# SHOW DASHBOARD
# ========================================

def show_dashboard():
    """Display CRM dashboard statistics."""

    try:

        stats = get_dashboard_stats()

        record_usage(
            event_type="DASHBOARD_VIEWED"
        )

        print("\n========================================")
        print("             CRM DASHBOARD")
        print("========================================")

        print(
            f"Total Leads: "
            f"{stats['total_leads']}"
        )

        print(
            f"High Priority Leads: "
            f"{stats['high_priority_leads']}"
        )

        print(
            f"Average Lead Score: "
            f"{stats['average_lead_score']:.2f}"
        )

        print(
            f"Converted Leads: "
            f"{stats['converted_leads']}"
        )

        print(
            f"Conversion Rate: "
            f"{stats['conversion_rate']:.2f}%"
        )

        print("\nLEADS BY STATUS")

        for status in ALLOWED_STATUSES:

            count = stats[
                "status_counts"
            ].get(
                status,
                0
            )

            print(
                f"{status}: {count}"
            )

        print("========================================")

    except Exception as error:

        handle_error(
            error,
            "Displaying CRM dashboard"
        )


# ========================================
# SHOW USAGE ANALYTICS
# ========================================

def show_usage_analytics():
    """Display internal CRM usage analytics."""

    try:

        analytics = get_usage_analytics()

        record_usage(
            event_type="USAGE_ANALYTICS_VIEWED"
        )

        print("\n========================================")
        print("          USAGE ANALYTICS")
        print("========================================")

        print(
            f"Total Events: "
            f"{analytics['total_events']}"
        )

        print(
            f"Total Records Affected: "
            f"{analytics['total_records_affected']}"
        )

        print(
            f"Leads Created: "
            f"{analytics['leads_created']}"
        )

        print(
            f"Unique Users: "
            f"{analytics['unique_users']}"
        )

        print(
            f"Unique Clients: "
            f"{analytics['unique_clients']}"
        )

        print(
            f"Active Users (24h): "
            f"{analytics['active_users_24h']}"
        )

        print(
            f"Active Clients (24h): "
            f"{analytics['active_clients_24h']}"
        )

        print("\nEVENTS BY TYPE")

        if analytics["events_by_type"]:

            for event_type, count in (
                analytics["events_by_type"].items()
            ):

                print(
                    f"{event_type}: {count}"
                )

        else:

            print("No usage events recorded.")

        print("\nEVENTS BY TOOL")

        if analytics["events_by_tool"]:

            for tool, count in (
                analytics["events_by_tool"].items()
            ):

                print(
                    f"{tool}: {count}"
                )

        else:

            print("No tool usage recorded.")

        print("\nRECORDS AFFECTED BY TOOL")

        if analytics["records_by_tool"]:

            for tool, count in (
                analytics["records_by_tool"].items()
            ):

                print(
                    f"{tool}: {count}"
                )

        else:

            print("No record usage recorded.")

        print("\nLATEST ACTIVITY")

        latest_activity = analytics[
            "latest_activity"
        ]

        if latest_activity:

            print(
                f"Event ID: {latest_activity[0]}"
            )

            print(
                f"Client: {latest_activity[1]}"
            )

            print(
                f"User: {latest_activity[2]}"
            )

            print(
                f"Event: {latest_activity[3]}"
            )

            print(
                f"Tool: {latest_activity[4]}"
            )

            print(
                f"Records Affected: "
                f"{latest_activity[5]}"
            )

            print(
                f"Metadata: {latest_activity[6]}"
            )

            print(
                f"Date: {latest_activity[7]}"
            )

        else:

            print("No recent activity.")

        print("========================================")

    except Exception as error:

        handle_error(
            error,
            "Displaying usage analytics"
        )


# ========================================
# DISPLAY LEAD ACTIVITIES
# ========================================

def show_lead_activities(lead_id):
    """Display the activity history of a lead."""

    try:

        activities = get_lead_activities(
            lead_id
        )

        record_usage(
            event_type="ACTIVITY_HISTORY_VIEWED",
            metadata=f"Lead ID: {lead_id}"
        )

        print("\n========================================")
        print("        LEAD ACTIVITY HISTORY")
        print("========================================")

        if not activities:

            print(
                "No activity history found."
            )

            return

        for activity in activities:

            print(
                f"\nActivity ID: {activity[0]}"
            )

            print(
                f"Lead ID: {activity[1]}"
            )

            print(
                f"Type: {activity[2]}"
            )

            print(
                f"Description: {activity[3]}"
            )

            print(
                f"Date: {activity[4]}"
            )

            print(
                "----------------------------------------"
            )

    except Exception as error:

        handle_error(
            error,
            "Retrieving lead activity history"
        )


# ========================================
# DISPLAY IMPORT BATCHES
# ========================================

def show_import_batches():
    """Display all recorded CRM import batches."""

    try:

        batches = get_import_batches()

        record_usage(
            event_type="IMPORT_BATCH_HISTORY_VIEWED"
        )

        print("\n========================================")
        print("          IMPORT BATCH HISTORY")
        print("========================================")

        if not batches:

            print("No import batches found.")

            return

        for batch in batches:

            print(f"\nBatch ID: {batch[0]}")
            print(f"Batch Key: {batch[1]}")
            print(f"Client: {batch[2]}")
            print(f"Dataset: {batch[3]}")
            print(f"Source File: {batch[4]}")
            print(f"Imported Records: {batch[5]}")
            print(f"Status: {batch[6]}")
            print(f"Created: {batch[7]}")

            print("----------------------------------------")

        batch_id = input(
            "\nEnter a Batch ID to view its leads, "
            "or press Enter to return: "
        ).strip()

        if not batch_id:

            return

        if not batch_id.isdigit():

            print("Invalid Batch ID.")

            return

        show_import_batch_details(
            int(batch_id)
        )

    except Exception as error:

        handle_error(
            error,
            "Displaying import batch history"
        )


# ========================================
# DISPLAY IMPORT BATCH DETAILS
# ========================================

def show_import_batch_details(batch_id):
    """Display details and leads belonging to one batch."""

    try:

        batches = get_import_batches()

        selected_batch = None

        for batch in batches:

            if batch[0] == batch_id:

                selected_batch = batch

                break

        print("\n========================================")
        print("          IMPORT BATCH DETAILS")
        print("========================================")

        if not selected_batch:

            print("Import batch not found.")

            return

        print(
            f"Batch ID: {selected_batch[0]}"
        )

        print(
            f"Batch Key: {selected_batch[1]}"
        )

        print(
            f"Client: {selected_batch[2]}"
        )

        print(
            f"Dataset: {selected_batch[3]}"
        )

        print(
            f"Source File: {selected_batch[4]}"
        )

        print(
            f"Imported Records: {selected_batch[5]}"
        )

        print(
            f"Status: {selected_batch[6]}"
        )

        print(
            f"Created: {selected_batch[7]}"
        )

        print("----------------------------------------")

        leads = get_leads_by_import_batch(
            batch_id
        )

        print("\nLEADS IN THIS BATCH")

        if not leads:

            print(
                "No leads found for this batch."
            )

            return

        for lead in leads:

            display_lead(
                lead
            )

        print(
            f"Total leads in batch: {len(leads)}"
        )

    except Exception as error:

        handle_error(
            error,
            "Displaying import batch details"
        )


# ========================================
# MAIN CRM LOOP
# ========================================

while True:

    show_menu()

    choice = input(
        "Choose an option: "
    ).strip()

    # ==================================================
    # 1. ADD NEW LEAD
    # ==================================================

    if choice == "1":

        print("\n===== ADD NEW LEAD =====")

        new_lead = {
            "name": input(
                "Customer name: "
            ).strip(),

            "email": input(
                "Customer email: "
            ).strip().lower(),

            "phone": input(
                "Customer phone: "
            ).strip(),

            "company": input(
                "Company: "
            ).strip(),

            "message": input(
                "Customer message: "
            ).strip(),
        }

        try:

            validation_errors = validate_new_lead(
                new_lead
            )

        except Exception as error:

            handle_error(
                error,
                "Lead validation"
            )

            continue

        if validation_errors:

            print(
                "\n===== VALIDATION ERRORS ====="
            )

            for error in validation_errors:

                print(
                    f"❌ {error}"
                )

            print(
                "\nLead was not saved."
            )

            continue

        print(
            "\n===== VALIDATION PASSED ====="
        )

        print(
            "All lead information is valid."
        )

        # ----------------------------------------------
        # CLEAN LEAD
        # ----------------------------------------------

        try:

            cleaned_lead = clean_lead(
                new_lead
            )

            print(
                "\n===== CLEANED LEAD ====="
            )

            print(
                cleaned_lead
            )

        except Exception as error:

            handle_error(
                error,
                "Lead cleaning"
            )

            print(
                "\nLead was not saved."
            )

            continue

        # ----------------------------------------------
        # DUPLICATE DETECTION
        # ----------------------------------------------

        print(
            "\n===== DUPLICATE CHECK ====="
        )

        try:

            duplicate, duplicate_reason = (
                check_for_duplicate(
                    cleaned_lead
                )
            )

            if duplicate:

                print(
                    "Potential duplicate: YES"
                )

            else:

                print(
                    "Potential duplicate: NO"
                )

            print(
                f"Reason: {duplicate_reason}"
            )

        except Exception as error:

            handle_error(
                error,
                "Duplicate lead detection"
            )

            print(
                "\nLead was not saved."
            )

            continue

        # ----------------------------------------------
        # AI ANALYSIS
        # ----------------------------------------------

        print(
            "\n===== AI ANALYSIS ====="
        )

        try:

            analysis = analyze_lead(
                cleaned_lead
            )

            print(
                analysis
            )

        except Exception as error:

            handle_error(
                error,
                "AI lead analysis"
            )

            print(
                "\nLead was not saved because "
                "AI analysis failed."
            )

            continue

        # ----------------------------------------------
        # CREATE CRM RECORD
        # ----------------------------------------------

        crm_record = {
            **cleaned_lead,

            "duplicate": duplicate,

            "duplicate_reason":
                duplicate_reason,

            "ai_analysis":
                analysis,
        }

        # ----------------------------------------------
        # SAVE LEAD
        # ----------------------------------------------

        try:

            lead_id = insert_lead(
                crm_record
            )

            record_usage(
                event_type="LEAD_CREATED",
                records_affected=1,
                metadata=f"Lead ID: {lead_id}"
            )

            print(
                "\n===== LEAD SAVED ====="
            )

            print(
                "Lead saved successfully."
            )

            print(
                f"Lead ID: {lead_id}"
            )

            print(
                "Status: NEW"
            )

        except Exception as error:

            handle_error(
                error,
                "Saving lead to database"
            )

            print(
                "\nLead could not be saved."
            )

    # ==================================================
    # 2. VIEW ALL LEADS
    # ==================================================

    elif choice == "2":

        try:

            leads = get_all_leads()

            record_usage(
                event_type="LEADS_VIEWED",
                records_affected=len(leads)
            )

            print(
                "\n===== ALL CRM LEADS ====="
            )

            if leads:

                for lead in leads:

                    display_lead(
                        lead
                    )

            else:

                print(
                    "No leads found."
                )

        except Exception as error:

            handle_error(
                error,
                "Retrieving all leads"
            )

    # ==================================================
    # 3. SEARCH BY EMAIL
    # ==================================================

    elif choice == "3":

        email = input(
            "Enter customer email: "
        ).strip().lower()

        valid, message = validate_email(
            email
        )

        if not valid:

            print(
                f"\nInvalid email: {message}"
            )

            continue

        try:

            results = search_leads_by_email(
                email
            )

            record_usage(
                event_type="EMAIL_SEARCH",
                records_affected=len(results),
                metadata=f"Email: {email}"
            )

            print(
                "\n===== EMAIL SEARCH RESULTS ====="
            )

            if results:

                for lead in results:

                    display_lead(
                        lead
                    )

            else:

                print(
                    "No lead found with that email."
                )

        except Exception as error:

            handle_error(
                error,
                "Searching leads by email"
            )

    # ==================================================
    # 4. SEARCH BY PRIORITY
    # ==================================================

    elif choice == "4":

        priority = input(
            "Enter priority (LOW, MEDIUM, HIGH): "
        ).strip().upper()

        valid, message = validate_priority(
            priority
        )

        if not valid:

            print(
                f"\nInvalid priority: {message}"
            )

            continue

        try:

            results = search_leads_by_priority(
                priority
            )

            record_usage(
                event_type="PRIORITY_SEARCH",
                records_affected=len(results),
                metadata=f"Priority: {priority}"
            )

            print(
                "\n===== PRIORITY SEARCH RESULTS ====="
            )

            if results:

                for lead in results:

                    display_lead(
                        lead
                    )

            else:

                print(
                    "No leads found with that priority."
                )

        except Exception as error:

            handle_error(
                error,
                "Searching leads by priority"
            )

    # ==================================================
    # 5. VIEW LEAD BY ID
    # ==================================================

    elif choice == "5":

        lead_id = input(
            "Enter lead ID: "
        ).strip()

        if not lead_id.isdigit():

            print(
                "Invalid lead ID."
            )

            continue

        try:

            lead = get_lead_by_id(
                int(lead_id)
            )

            if lead:

                record_usage(
                    event_type="LEAD_VIEWED",
                    metadata=f"Lead ID: {lead_id}"
                )

            print(
                "\n===== LEAD DETAILS ====="
            )

            if lead:

                display_lead(
                    lead
                )

            else:

                print(
                    "Lead not found."
                )

        except Exception as error:

            handle_error(
                error,
                "Retrieving lead by ID"
            )

    # ==================================================
    # 6. UPDATE PRIORITY AND SCORE
    # ==================================================

    elif choice == "6":

        lead_id = input(
            "Enter lead ID: "
        ).strip()

        if not lead_id.isdigit():

            print(
                "Invalid lead ID."
            )

            continue

        lead_id = int(
            lead_id
        )

        try:

            existing_lead = get_lead_by_id(
                lead_id
            )

            if not existing_lead:

                print(
                    "Lead not found."
                )

                continue

            display_lead(
                existing_lead
            )

            priority = input(
                "Enter new priority "
                "(LOW, MEDIUM, HIGH): "
            ).strip().upper()

            valid, message = validate_priority(
                priority
            )

            if not valid:

                print(
                    f"\nInvalid priority: {message}"
                )

                continue

            score_input = input(
                "Enter new lead score (0-100): "
            ).strip()

            if not score_input.isdigit():

                print(
                    "Lead score must be a number."
                )

                continue

            lead_score = int(
                score_input
            )

            valid, message = (
                validate_lead_score(
                    lead_score
                )
            )

            if not valid:

                print(
                    f"\nInvalid lead score: {message}"
                )

                continue

            rows_updated = update_lead(
                lead_id,
                priority,
                lead_score
            )

            if rows_updated:

                create_lead_activity(
                    lead_id,
                    "LEAD_UPDATED",
                    (
                        f"Priority changed to "
                        f"{priority}. Lead score "
                        f"changed to {lead_score}."
                    )
                )

                record_usage(
                    event_type="LEAD_UPDATED",
                    records_affected=1,
                    metadata=(
                        f"Lead ID: {lead_id}; "
                        f"Priority: {priority}; "
                        f"Score: {lead_score}"
                    )
                )

                print(
                    "\nLead updated successfully."
                )

            else:

                print(
                    "Lead could not be updated."
                )

        except Exception as error:

            handle_error(
                error,
                "Updating lead"
            )

    # ==================================================
    # 7. UPDATE LEAD STATUS
    # ==================================================

    elif choice == "7":

        lead_id = input(
            "Enter lead ID: "
        ).strip()

        if not lead_id.isdigit():

            print(
                "Invalid lead ID."
            )

            continue

        lead_id = int(
            lead_id
        )

        try:

            existing_lead = get_lead_by_id(
                lead_id
            )

            if not existing_lead:

                print(
                    "Lead not found."
                )

                continue

            old_status = existing_lead[16]

            print(
                "\nCurrent lead:"
            )

            display_lead(
                existing_lead
            )

            print(
                "\nAvailable statuses:"
            )

            print(
                ", ".join(
                    ALLOWED_STATUSES
                )
            )

            status = input(
                "Enter new status: "
            ).strip().upper()

            valid, message = validate_status(
                status
            )

            if not valid:

                print(
                    f"\nInvalid status: {message}"
                )

                continue

            if status == old_status:

                print(
                    "\nThis lead already has "
                    f"the status: {status}"
                )

                continue

            rows_updated = update_lead_status(
                lead_id,
                status
            )

            if rows_updated:

                description = (
                    f"Lead status changed from "
                    f"{old_status} to {status}."
                )

                create_lead_activity(
                    lead_id,
                    "STATUS_CHANGED",
                    description
                )

                record_usage(
                    event_type="STATUS_CHANGED",
                    records_affected=1,
                    metadata=(
                        f"Lead ID: {lead_id}; "
                        f"{old_status} -> {status}"
                    )
                )

                print(
                    "\nLead status updated successfully."
                )

                print(
                    f"Previous status: {old_status}"
                )

                print(
                    f"New status: {status}"
                )

                print(
                    "Activity automatically recorded."
                )

            else:

                print(
                    "Lead status could not be updated."
                )

        except Exception as error:

            handle_error(
                error,
                "Updating lead status"
            )

    # ==================================================
    # 8. SEARCH BY STATUS
    # ==================================================

    elif choice == "8":

        print(
            "\nAvailable statuses:"
        )

        print(
            ", ".join(
                ALLOWED_STATUSES
            )
        )

        status = input(
            "Enter lead status: "
        ).strip().upper()

        valid, message = validate_status(
            status
        )

        if not valid:

            print(
                f"\nInvalid status: {message}"
            )

            continue

        try:

            results = search_leads_by_status(
                status
            )

            record_usage(
                event_type="STATUS_SEARCH",
                records_affected=len(results),
                metadata=f"Status: {status}"
            )

            print(
                f"\n===== {status} LEADS ====="
            )

            if results:

                for lead in results:

                    display_lead(
                        lead
                    )

            else:

                print(
                    f"No leads found with "
                    f"status: {status}"
                )

        except Exception as error:

            handle_error(
                error,
                "Searching leads by status"
            )

    # ==================================================
    # 9. DELETE LEAD
    # ==================================================

    elif choice == "9":

        lead_id = input(
            "Enter lead ID to delete: "
        ).strip()

        if not lead_id.isdigit():

            print(
                "Invalid lead ID."
            )

            continue

        lead_id = int(
            lead_id
        )

        try:

            existing_lead = get_lead_by_id(
                lead_id
            )

            if not existing_lead:

                print(
                    "Lead not found."
                )

                continue

            print(
                "\nLead selected for deletion:"
            )

            display_lead(
                existing_lead
            )

            confirmation = input(
                "Are you sure you want to "
                "delete this lead? (yes/no): "
            ).strip().lower()

            if confirmation == "yes":

                rows_deleted = delete_lead(
                    lead_id
                )

                if rows_deleted:

                    record_usage(
                        event_type="LEAD_DELETED",
                        records_affected=1,
                        metadata=f"Lead ID: {lead_id}"
                    )

                    print(
                        "\nLead deleted successfully."
                    )

                else:

                    print(
                        "Lead could not be deleted."
                    )

            else:

                print(
                    "Deletion cancelled."
                )

        except Exception as error:

            handle_error(
                error,
                "Deleting lead"
            )

    # ==================================================
    # 10. VIEW DASHBOARD
    # ==================================================

    elif choice == "10":

        show_dashboard()

    # ==================================================
    # 11. VIEW LEAD ACTIVITY HISTORY
    # ==================================================

    elif choice == "11":

        lead_id = input(
            "Enter lead ID: "
        ).strip()

        if not lead_id.isdigit():

            print(
                "Invalid lead ID."
            )

            continue

        lead_id = int(
            lead_id
        )

        try:

            existing_lead = get_lead_by_id(
                lead_id
            )

            if not existing_lead:

                print(
                    "Lead not found."
                )

                continue

            print(
                "\nLead:"
            )

            display_lead(
                existing_lead
            )

            show_lead_activities(
                lead_id
            )

        except Exception as error:

            handle_error(
                error,
                "Viewing lead activity history"
            )

    # ==================================================
    # 12. VIEW IMPORT BATCH HISTORY
    # ==================================================

    elif choice == "12":

        show_import_batches()

    # ==================================================
    # 13. VIEW USAGE ANALYTICS
    # ==================================================

    elif choice == "13":

        show_usage_analytics()

    # ==================================================
    # 14. EXIT
    # ==================================================

    elif choice == "14":

        print(
            "\nGoodbye!"
        )

        break

    # ==================================================
    # INVALID OPTION
    # ==================================================

    else:

        print(
            "\nInvalid option. "
            "Please choose 1-14."
        )