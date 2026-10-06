import sqlite3
from pathlib import Path

from app.duplicate_detector import detect_duplicate


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "crm.db"

ALLOWED_STATUSES = {
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "CONVERTED",
    "LOST"
}

ALLOWED_PRIORITIES = {
    "LOW",
    "MEDIUM",
    "HIGH"
}

AI_CORE_FIELDS = (
    "lead_type",
    "intent",
    "product",
    "priority",
    "lead_score",
    "summary"
)


def get_connection():
    """
    Create and return a SQLite database connection.

    The database directory is created automatically if it does not exist.
    Foreign-key enforcement is enabled for every connection.
    """

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=10
    )

    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def create_database():
    """
    Create the CRM database and required tables/indexes.
    Existing data is preserved.
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                company TEXT,
                message TEXT,
                duplicate INTEGER DEFAULT 0,
                duplicate_reason TEXT,
                lead_type TEXT,
                intent TEXT,
                product TEXT,
                quantity INTEGER,
                timeline TEXT,
                priority TEXT,
                lead_score INTEGER,
                summary TEXT,
                recommended_action TEXT,
                follow_up_timing TEXT,
                action_status TEXT DEFAULT 'PENDING',
                action_completed_at TEXT,
                status TEXT DEFAULT 'NEW'
            )
        """)

        cursor.execute("PRAGMA table_info(leads)")
        lead_columns = [row[1] for row in cursor.fetchall()]

        if "status" not in lead_columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN status TEXT DEFAULT 'NEW'
            """)

        if "recommended_action" not in lead_columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN recommended_action TEXT
            """)

        if "follow_up_timing" not in lead_columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN follow_up_timing TEXT
            """)

        if "action_status" not in lead_columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN action_status TEXT DEFAULT 'PENDING'
            """)

        if "action_completed_at" not in lead_columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN action_completed_at TEXT
            """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_key TEXT NOT NULL UNIQUE,
                client_name TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                source_file TEXT NOT NULL,
                imported_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'COMPLETED',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("PRAGMA table_info(leads)")
        lead_columns = [row[1] for row in cursor.fetchall()]

        if "import_batch_id" not in lead_columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN import_batch_id INTEGER
                REFERENCES import_batches(id)
            """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_leads_import_batch_id
            ON leads(import_batch_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                user_id TEXT,
                event_type TEXT NOT NULL,
                tool_used TEXT,
                records_affected INTEGER DEFAULT 0,
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def insert_lead(lead):
    """
    Insert one lead and create its initial activity record.
    """

    if not isinstance(lead, dict):
        raise TypeError("lead must be a dictionary.")

    name = str(lead.get("name") or "").strip()
    email = str(lead.get("email") or "").strip()

    if not name:
        raise ValueError("Lead name is required.")

    if not email:
        raise ValueError("Lead email is required.")

    status = str(lead.get("status", "NEW") or "NEW").strip().upper()

    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status. Allowed values: {sorted(ALLOWED_STATUSES)}"
        )

    priority = lead.get("priority")

    if priority is not None:
        priority = str(priority).strip().upper()

        if priority not in ALLOWED_PRIORITIES:
            raise ValueError(
                f"Invalid priority. Allowed values: "
                f"{sorted(ALLOWED_PRIORITIES)}"
            )

    lead_score = lead.get("lead_score")

    if lead_score is not None:
        if isinstance(lead_score, bool) or not isinstance(lead_score, int):
            raise TypeError("lead_score must be an integer.")

        if not 0 <= lead_score <= 100:
            raise ValueError("lead_score must be between 0 and 100.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO leads (
                name,
                email,
                phone,
                company,
                message,
                duplicate,
                duplicate_reason,
                lead_type,
                intent,
                product,
                quantity,
                timeline,
                priority,
                lead_score,
                summary,
                status,
                import_batch_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            email,
            lead.get("phone"),
            lead.get("company"),
            lead.get("message"),
            lead.get("duplicate", 0),
            lead.get("duplicate_reason"),
            lead.get("lead_type"),
            lead.get("intent"),
            lead.get("product"),
            lead.get("quantity"),
            lead.get("timeline"),
            priority,
            lead_score,
            lead.get("summary"),
            status,
            lead.get("import_batch_id")
        ))

        lead_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                description
            )
            VALUES (?, ?, ?)
        """, (
            lead_id,
            "CREATED",
            "Lead was added to the CRM."
        ))

        conn.commit()

        return lead_id

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def save_lead_analysis(lead_id, analysis):
    """
    Save validated AI analysis results to an existing lead.

    The update is atomic:
    - Either all AI analysis fields and the activity record are saved.
    - Or nothing is saved.

    The AI response must already be validated before reaching this function.
    Database-level validation is still performed as a safety boundary.
    """

    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer.")

    if not isinstance(analysis, dict):
        raise TypeError("analysis must be a dictionary.")

    required_fields = {
        "lead_type",
        "intent",
        "product",
        "quantity",
        "timeline",
        "priority",
        "lead_score",
        "summary",
        "recommended_action",
        "follow_up_timing"
    }

    missing_fields = required_fields - set(analysis.keys())

    if missing_fields:
        raise ValueError(
            f"Missing required AI analysis fields: {sorted(missing_fields)}"
        )

    priority = str(analysis.get("priority") or "").strip().upper()

    if priority not in ALLOWED_PRIORITIES:
        raise ValueError(
            f"Invalid AI priority. Allowed values: "
            f"{sorted(ALLOWED_PRIORITIES)}"
        )

    lead_score = analysis.get("lead_score")

    if isinstance(lead_score, bool) or not isinstance(lead_score, int):
        raise TypeError("AI lead_score must be an integer.")

    if not 0 <= lead_score <= 100:
        raise ValueError("AI lead_score must be between 0 and 100.")

    quantity = analysis.get("quantity")

    if isinstance(quantity, bool):
        raise TypeError("AI quantity must be an integer or None.")

    if quantity is not None and not isinstance(quantity, int):
        raise TypeError("AI quantity must be an integer or None.")

    if quantity is not None and quantity < 0:
        raise ValueError("AI quantity cannot be negative.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id
            FROM leads
            WHERE id = ?
        """, (lead_id,))

        existing_lead = cursor.fetchone()

        if not existing_lead:
            conn.rollback()
            return False

        cursor.execute("""
            UPDATE leads
            SET
                lead_type = ?,
                intent = ?,
                product = ?,
                quantity = ?,
                timeline = ?,
                priority = ?,
                lead_score = ?,
                summary = ?,
                recommended_action = ?,
                follow_up_timing = ?
            WHERE id = ?
        """, (
            analysis.get("lead_type"),
            analysis.get("intent"),
            analysis.get("product"),
            quantity,
            analysis.get("timeline"),
            priority,
            lead_score,
            analysis.get("summary"),
            analysis.get("recommended_action"),
            analysis.get("follow_up_timing"),
            lead_id
        ))

        if cursor.rowcount == 0:
            conn.rollback()
            return False

        cursor.execute("""
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                description
            )
            VALUES (?, ?, ?)
        """, (
            lead_id,
            "AI_ANALYSIS_UPDATED",
            (
                f"AI analysis saved. "
                f"Priority: {priority}, "
                f"Score: {lead_score}."
            )
        ))

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_lead_by_email(email):
    """
    Find a lead by email using case-insensitive,
    whitespace-normalized comparison.
    """

    email = str(email or "").strip()

    if not email:
        return None

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                name,
                email,
                phone,
                company,
                status
            FROM leads
            WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))
            LIMIT 1
        """, (email,))

        return cursor.fetchone()

    finally:
        conn.close()


def import_clean_leads(
    clean_dataframe,
    batch_key=None,
    client_name=None,
    dataset_name=None,
    source_file=None
):
    """
    Import CLEAN + UNIQUE rows into the CRM.

    Exact email duplicates are skipped.

    HIGH-confidence duplicate matches are imported and flagged.

    MEDIUM-confidence REVIEW matches are also imported and flagged
    for human review.

    UNIQUE records are imported normally.
    """

    if clean_dataframe is None:
        raise ValueError("clean_dataframe is required.")

    required_columns = {
        "name",
        "email",
        "phone",
        "company",
        "message",
        "validation_status",
        "duplicate_status"
    }

    missing_columns = required_columns - set(clean_dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if not batch_key:
        raise ValueError("batch_key is required.")

    if not client_name:
        raise ValueError("client_name is required.")

    if not dataset_name:
        raise ValueError("dataset_name is required.")

    if not source_file:
        raise ValueError("source_file is required.")

    clean_rows = clean_dataframe[
        (clean_dataframe["validation_status"] == "CLEAN") &
        (clean_dataframe["duplicate_status"] == "UNIQUE")
    ].copy()

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                status,
                created_at
            FROM import_batches
            WHERE batch_key = ?
        """, (batch_key,))

        existing_batch = cursor.fetchone()

        if existing_batch:
            return {
                "imported": 0,
                "skipped": len(clean_rows),
                "existing_duplicates": 0,
                "possible_duplicates": 0,
                "review_required": 0,
                "already_imported": True,
                "batch_id": existing_batch[0]
            }

        cursor.execute("""
            INSERT INTO import_batches (
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            batch_key,
            client_name,
            dataset_name,
            source_file,
            0,
            "IMPORTING"
        ))

        batch_id = cursor.lastrowid

        cursor.execute("""
            SELECT
                id,
                name,
                email,
                phone,
                company
            FROM leads
        """)

        existing_leads = cursor.fetchall()

        imported_count = 0
        skipped_count = 0
        existing_duplicate_count = 0
        possible_duplicate_count = 0
        review_required_count = 0

        for _, row in clean_rows.iterrows():

            raw_name = row.get("name")
            raw_email = row.get("email")
            raw_phone = row.get("phone")
            raw_company = row.get("company")
            raw_message = row.get("message")

            name = (
                ""
                if raw_name is None
                else str(raw_name).strip()
            )

            email = (
                ""
                if raw_email is None
                else str(raw_email).strip()
            )

            phone = (
                ""
                if raw_phone is None
                else str(raw_phone).strip()
            )

            company = (
                ""
                if raw_company is None
                else str(raw_company).strip()
            )

            message = (
                ""
                if raw_message is None
                else str(raw_message).strip()
            )

            if not name or not email:
                skipped_count += 1
                continue

            cursor.execute("""
                SELECT
                    id,
                    name,
                    email,
                    phone,
                    company
                FROM leads
                WHERE LOWER(TRIM(email)) = LOWER(TRIM(?))
                LIMIT 1
            """, (email,))

            existing_by_email = cursor.fetchone()

            if existing_by_email:
                existing_duplicate_count += 1
                skipped_count += 1
                continue

            incoming_lead = {
                "name": name,
                "email": email,
                "phone": phone,
                "company": company
            }

            duplicate_flag = 0
            duplicate_reason = None
            duplicate_activity_type = None

            for existing_lead in existing_leads:

                existing_record = {
                    "name": existing_lead[1],
                    "email": existing_lead[2],
                    "phone": existing_lead[3],
                    "company": existing_lead[4]
                }

                duplicate_result = detect_duplicate(
                    incoming_lead,
                    existing_record
                )

                result_status = duplicate_result.get("status")
                confidence = duplicate_result.get("confidence")
                reason = duplicate_result.get("reason")

                if result_status == "DUPLICATE":

                    duplicate_flag = 1

                    duplicate_reason = (
                        f"Possible existing lead "
                        f"(Lead ID {existing_lead[0]}): "
                        f"{reason} "
                        f"Confidence: {confidence}"
                    )

                    duplicate_activity_type = "DUPLICATE_REVIEW"

                    possible_duplicate_count += 1

                    break

                if result_status == "REVIEW":

                    duplicate_flag = 1

                    duplicate_reason = (
                        f"Manual duplicate review required "
                        f"(Lead ID {existing_lead[0]}): "
                        f"{reason} "
                        f"Confidence: {confidence}"
                    )

                    duplicate_activity_type = "DUPLICATE_REVIEW"

                    review_required_count += 1

                    break

            status = row.get("status", "NEW")

            if status is None:
                status = "NEW"

            status = str(status).strip().upper()

            if status not in ALLOWED_STATUSES:
                status = "NEW"

            priority = row.get("priority")

            if priority is not None:
                priority = str(priority).strip().upper()

                if priority not in ALLOWED_PRIORITIES:
                    priority = None

            lead_score = row.get("lead_score")

            if lead_score is not None:

                try:
                    lead_score = int(lead_score)
                except (TypeError, ValueError):
                    lead_score = None

                if lead_score is not None:
                    lead_score = max(0, min(100, lead_score))

            cursor.execute("""
                INSERT INTO leads (
                    name,
                    email,
                    phone,
                    company,
                    message,
                    duplicate,
                    duplicate_reason,
                    lead_type,
                    intent,
                    product,
                    quantity,
                    timeline,
                    priority,
                    lead_score,
                    summary,
                    status,
                    import_batch_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                email,
                phone,
                company,
                message,
                duplicate_flag,
                duplicate_reason,
                row.get("lead_type"),
                row.get("intent"),
                row.get("product"),
                row.get("quantity"),
                row.get("timeline"),
                priority,
                lead_score,
                row.get("summary"),
                status,
                batch_id
            ))

            lead_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO lead_activities (
                    lead_id,
                    activity_type,
                    description
                )
                VALUES (?, ?, ?)
            """, (
                lead_id,
                "CREATED",
                "Lead was added to the CRM."
            ))

            if duplicate_flag and duplicate_activity_type:

                cursor.execute("""
                    INSERT INTO lead_activities (
                        lead_id,
                        activity_type,
                        description
                    )
                    VALUES (?, ?, ?)
                """, (
                    lead_id,
                    duplicate_activity_type,
                    duplicate_reason
                ))

            existing_leads.append((
                lead_id,
                name,
                email,
                phone,
                company
            ))

            imported_count += 1

        cursor.execute("""
            UPDATE import_batches
            SET
                imported_count = ?,
                status = ?
            WHERE id = ?
        """, (
            imported_count,
            "COMPLETED",
            batch_id
        ))

        conn.commit()

        return {
            "imported": imported_count,
            "skipped": skipped_count,
            "existing_duplicates": existing_duplicate_count,
            "possible_duplicates": possible_duplicate_count,
            "review_required": review_required_count,
            "already_imported": False,
            "batch_id": batch_id
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_import_batch(batch_key):
    if not batch_key:
        return None

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                status,
                created_at
            FROM import_batches
            WHERE batch_key = ?
        """, (batch_key,))

        return cursor.fetchone()

    finally:
        conn.close()


def get_import_batches():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                status,
                created_at
            FROM import_batches
            ORDER BY id DESC
        """)

        return cursor.fetchall()

    finally:
        conn.close()


def get_leads_by_import_batch(batch_id):
    if not isinstance(batch_id, int) or batch_id <= 0:
        raise ValueError("batch_id must be a positive integer.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                name,
                email,
                phone,
                company,
                priority,
                lead_score,
                status,
                duplicate,
                duplicate_reason
            FROM leads
            WHERE import_batch_id = ?
            ORDER BY id
        """, (batch_id,))

        return cursor.fetchall()

    finally:
        conn.close()


def get_import_batch_stats(batch_id):
    if not isinstance(batch_id, int) or batch_id <= 0:
        raise ValueError("batch_id must be a positive integer.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                status,
                created_at
            FROM import_batches
            WHERE id = ?
        """, (batch_id,))

        batch = cursor.fetchone()

        if not batch:
            return None

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE import_batch_id = ?
        """, (batch_id,))

        total_leads = cursor.fetchone()[0]

        status_counts = {}

        for status in sorted(ALLOWED_STATUSES):

            cursor.execute("""
                SELECT COUNT(*)
                FROM leads
                WHERE import_batch_id = ?
                AND status = ?
            """, (batch_id, status))

            status_counts[status] = cursor.fetchone()[0]

        converted_leads = status_counts["CONVERTED"]

        conversion_rate = (
            (converted_leads / total_leads) * 100
            if total_leads > 0
            else 0
        )

        return {
            "batch_id": batch[0],
            "batch_key": batch[1],
            "client_name": batch[2],
            "dataset_name": batch[3],
            "source_file": batch[4],
            "imported_count": batch[5],
            "status": batch[6],
            "created_at": batch[7],
            "total_leads": total_leads,
            "status_counts": status_counts,
            "converted_leads": converted_leads,
            "conversion_rate": conversion_rate
        }

    finally:
        conn.close()


def get_all_import_batch_stats():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                status,
                created_at
            FROM import_batches
            ORDER BY id DESC
        """)

        batches = cursor.fetchall()

        results = []

        for batch in batches:

            batch_id = batch[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM leads
                WHERE import_batch_id = ?
            """, (batch_id,))

            total_leads = cursor.fetchone()[0]

            status_counts = {}

            for status in sorted(ALLOWED_STATUSES):

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM leads
                    WHERE import_batch_id = ?
                    AND status = ?
                """, (batch_id, status))

                status_counts[status] = cursor.fetchone()[0]

            converted_leads = status_counts["CONVERTED"]

            conversion_rate = (
                (converted_leads / total_leads) * 100
                if total_leads > 0
                else 0
            )

            results.append({
                "batch_id": batch[0],
                "batch_key": batch[1],
                "client_name": batch[2],
                "dataset_name": batch[3],
                "source_file": batch[4],
                "imported_count": batch[5],
                "status": batch[6],
                "created_at": batch[7],
                "total_leads": total_leads,
                "status_counts": status_counts,
                "converted_leads": converted_leads,
                "conversion_rate": conversion_rate
            })

        return results

    finally:
        conn.close()


def update_lead(lead_id, priority, lead_score):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer.")

    priority = str(priority or "").strip().upper()

    if priority not in ALLOWED_PRIORITIES:
        raise ValueError(
            f"Invalid priority. Allowed values: "
            f"{sorted(ALLOWED_PRIORITIES)}"
        )

    if isinstance(lead_score, bool) or not isinstance(lead_score, int):
        raise TypeError("lead_score must be an integer.")

    if not 0 <= lead_score <= 100:
        raise ValueError("lead_score must be between 0 and 100.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE leads
            SET
                priority = ?,
                lead_score = ?
            WHERE id = ?
        """, (
            priority,
            lead_score,
            lead_id
        ))

        updated = cursor.rowcount > 0

        if updated:
            cursor.execute("""
                INSERT INTO lead_activities (
                    lead_id,
                    activity_type,
                    description
                )
                VALUES (?, ?, ?)
            """, (
                lead_id,
                "UPDATED",
                f"Lead priority/score updated to {priority}/{lead_score}."
            ))

        conn.commit()

        return updated

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_lead_status(lead_id, status):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer.")

    status = str(status or "").strip().upper()

    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status. Allowed values: {sorted(ALLOWED_STATUSES)}"
        )

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE leads
            SET status = ?
            WHERE id = ?
        """, (
            status,
            lead_id
        ))

        if cursor.rowcount == 0:
            conn.rollback()
            return False

        cursor.execute("""
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                description
            )
            VALUES (?, ?, ?)
        """, (
            lead_id,
            "STATUS_CHANGED",
            f"Lead status changed to {status}."
        ))

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()



def get_lead_action_status(lead_id):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positiveinteger.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                action_status,
                action_completed_at
            FROM leads
            WHERE id = ?
        """, (lead_id,))

        lead = cursor.fetchone()

        if not lead:
            return None

        return {
            "id": lead[0],
            "action_status": lead[1] or "PENDING",
            "action_completed_at": lead[2]
        }

    finally:
        conn.close()


def update_lead_action_status(lead_id, action_status):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positiveinteger.")

    action_status = str(action_status or "").strip().upper()

    allowed_action_statuses = {
        "PENDING",
        "IN PROGRESS",
        "COMPLETED",
        "SKIPPED"
    }

    if action_status not in allowed_action_statuses:
        raise ValueError(
            "Invalid action status. Allowed values: "
            f"{sorted(allowed_action_statuses)}"
        )

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, action_status
            FROM leads
            WHERE id = ?
        """, (lead_id,))

        lead = cursor.fetchone()

        if not lead:
            conn.rollback()
            return False

        from datetime import datetime

        completed_at = (
            datetime.now().isoformat(timespec="seconds")
            if action_status == "COMPLETED"
            else None
        )

        cursor.execute("""
            UPDATE leads
            SET
                action_status = ?,
                action_completed_at = ?
            WHERE id = ?
        """, (
            action_status,
            completed_at,
            lead_id
        ))

        cursor.execute("""
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                description
            )
            VALUES (?, ?, ?)
        """, (
            lead_id,
            "ACTION_STATUS_CHANGED",
            f"Recommended action status changed to {action_status}."
        ))

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_leads_by_status(status):
    status = str(status or "").strip().upper()

    if status not in ALLOWED_STATUSES:
        raise ValueError(
            f"Invalid status. Allowed values: {sorted(ALLOWED_STATUSES)}"
        )

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                name,
                email,
                phone,
                company,
                priority,
                lead_score,
                status,
                duplicate,
                duplicate_reason
            FROM leads
            WHERE status = ?
            ORDER BY id DESC
        """, (status,))

        return cursor.fetchall()

    finally:
        conn.close()


def delete_lead(lead_id):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM lead_activities
            WHERE lead_id = ?
        """, (lead_id,))

        cursor.execute("""
            DELETE FROM leads
            WHERE id = ?
        """, (lead_id,))

        deleted = cursor.rowcount > 0

        conn.commit()

        return deleted

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_dashboard_stats():
    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
        """)

        total_leads = cursor.fetchone()[0]

        status_counts = {}

        for status in sorted(ALLOWED_STATUSES):

            cursor.execute("""
                SELECT COUNT(*)
                FROM leads
                WHERE status = ?
            """, (status,))

            status_counts[status] = cursor.fetchone()[0]

        new_leads = status_counts["NEW"]
        contacted_leads = status_counts["CONTACTED"]
        qualified_leads = status_counts["QUALIFIED"]
        converted_leads = status_counts["CONVERTED"]
        lost_leads = status_counts["LOST"]

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE duplicate = 1
        """)

        duplicate_leads = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE UPPER(TRIM(priority)) = 'HIGH'
        """)

        high_priority_leads = cursor.fetchone()[0]

        cursor.execute("""
            SELECT AVG(lead_score)
            FROM leads
            WHERE lead_score IS NOT NULL
        """)

        average_lead_score = cursor.fetchone()[0]

        if average_lead_score is None:
            average_lead_score = 0

        conversion_rate = (
            (converted_leads / total_leads) * 100
            if total_leads > 0
            else 0
        )

        return {
            "total_leads": total_leads,
            "new_leads": new_leads,
            "contacted_leads": contacted_leads,
            "qualified_leads": qualified_leads,
            "converted_leads": converted_leads,
            "lost_leads": lost_leads,
            "duplicate_leads": duplicate_leads,
            "high_priority_leads": high_priority_leads,
            "average_lead_score": average_lead_score,
            "conversion_rate": conversion_rate,
            "status_counts": status_counts
        }

    finally:
        conn.close()


def get_crm_intelligence_report(batch_id=None):
    """
    Build a structured CRM intelligence report.

    When batch_id is supplied, the report is STRICTLY scoped to that
    import batch. It will never silently fall back to all CRM leads.

    When batch_id is None, the report covers the entire CRM.

    AI analysis is considered complete only when all core AI fields exist:
        lead_type
        intent
        product
        priority
        lead_score
        summary
    """

    if batch_id is not None:
        if not isinstance(batch_id, int) or batch_id <= 0:
            raise ValueError("batch_id must be a positive integer.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        batch_info = None

        if batch_id is not None:

            cursor.execute("""
                SELECT
                    id,
                    batch_key,
                    client_name,
                    dataset_name,
                    source_file,
                    imported_count,
                    status,
                    created_at
                FROM import_batches
                WHERE id = ?
            """, (batch_id,))

            batch = cursor.fetchone()

            if not batch:
                return None

            batch_info = {
                "batch_id": batch[0],
                "batch_key": batch[1],
                "client_name": batch[2],
                "dataset_name": batch[3],
                "source_file": batch[4],
                "imported_count": batch[5],
                "status": batch[6],
                "created_at": batch[7]
            }

        if batch_id is not None:
            where_clause = "WHERE import_batch_id = ?"
            parameters = (batch_id,)
        else:
            where_clause = ""
            parameters = ()

        # ---------------------------------------------------------
        # TOTAL LEADS
        # ---------------------------------------------------------

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            """,
            parameters
        )

        total_leads = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # STATUS COUNTS
        # ---------------------------------------------------------

        status_counts = {}

        for status in sorted(ALLOWED_STATUSES):

            query = f"""
                SELECT COUNT(*)
                FROM leads
                {where_clause}
                {"AND" if where_clause else "WHERE"}
                status = ?
            """

            cursor.execute(
                query,
                parameters + (status,)
            )

            status_counts[status] = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # PRIORITY COUNTS
        # ---------------------------------------------------------

        priority_counts = {}

        for priority in sorted(ALLOWED_PRIORITIES):

            query = f"""
                SELECT COUNT(*)
                FROM leads
                {where_clause}
                {"AND" if where_clause else "WHERE"}
                UPPER(TRIM(priority)) = ?
            """

            cursor.execute(
                query,
                parameters + (priority,)
            )

            priority_counts[priority] = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # DUPLICATES
        # ---------------------------------------------------------

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            duplicate = 1
            """,
            parameters
        )

        duplicate_records = cursor.fetchone()[0]

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            duplicate = 1
            AND duplicate_reason LIKE
                'Manual duplicate review required%'
            """,
            parameters
        )

        review_required = cursor.fetchone()[0]

        confirmed_duplicates = max(
            0,
            duplicate_records - review_required
        )

        # ---------------------------------------------------------
        # DATA QUALITY
        # ---------------------------------------------------------

        missing_email_query = f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            TRIM(COALESCE(email, '')) = ''
        """

        cursor.execute(
            missing_email_query,
            parameters
        )

        missing_email = cursor.fetchone()[0]

        missing_phone_query = f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            TRIM(COALESCE(phone, '')) = ''
        """

        cursor.execute(
            missing_phone_query,
            parameters
        )

        missing_phone = cursor.fetchone()[0]

        missing_company_query = f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            TRIM(COALESCE(company, '')) = ''
        """

        cursor.execute(
            missing_company_query,
            parameters
        )

        missing_company = cursor.fetchone()[0]

        missing_message_query = f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            TRIM(COALESCE(message, '')) = ''
        """

        cursor.execute(
            missing_message_query,
            parameters
        )

        missing_message = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # AI ANALYSIS
        # ---------------------------------------------------------
        #
        # IMPORTANT:
        # A lead is "AI analyzed" only when all core AI fields
        # required by the CRM intelligence layer are populated.
        #
        # quantity and timeline are intentionally excluded because
        # they are allowed to be None.
        # ---------------------------------------------------------

        ai_complete_condition = """
            lead_type IS NOT NULL
            AND TRIM(lead_type) != ''
            AND intent IS NOT NULL
            AND TRIM(intent) != ''
            AND product IS NOT NULL
            AND TRIM(product) != ''
            AND priority IS NOT NULL
            AND TRIM(priority) != ''
            AND lead_score IS NOT NULL
            AND summary IS NOT NULL
            AND TRIM(summary) != ''
        """

        cursor.execute(
            f"""
            SELECT AVG(lead_score)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            {ai_complete_condition}
            """,
            parameters
        )

        average_lead_score = cursor.fetchone()[0]

        if average_lead_score is None:
            average_lead_score = 0

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            {ai_complete_condition}
            """,
            parameters
        )

        analyzed_leads = cursor.fetchone()[0]

        unanalyzed_leads = max(
            total_leads - analyzed_leads,
            0
        )

        # ---------------------------------------------------------
        # HIGH PRIORITY
        # ---------------------------------------------------------

        cursor.execute(
            f"""
            SELECT COUNT(*)
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            UPPER(TRIM(priority)) = 'HIGH'
            AND {ai_complete_condition}
            """,
            parameters
        )

        high_priority_leads = cursor.fetchone()[0]

        # ---------------------------------------------------------
        # TOP PRODUCTS
        # ---------------------------------------------------------

        cursor.execute(
            f"""
            SELECT
                product,
                COUNT(*) AS demand_count
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            {ai_complete_condition}
            GROUP BY LOWER(TRIM(product))
            ORDER BY demand_count DESC
            LIMIT 10
            """,
            parameters
        )

        top_products = [
            {
                "product": row[0],
                "count": row[1]
            }
            for row in cursor.fetchall()
        ]

        # ---------------------------------------------------------
        # INTENT DISTRIBUTION
        # ---------------------------------------------------------

        cursor.execute(
            f"""
            SELECT
                intent,
                COUNT(*) AS intent_count
            FROM leads
            {where_clause}
            {"AND" if where_clause else "WHERE"}
            {ai_complete_condition}
            GROUP BY LOWER(TRIM(intent))
            ORDER BY intent_count DESC
            LIMIT 10
            """,
            parameters
        )

        intent_distribution = [
            {
                "intent": row[0],
                "count": row[1]
            }
            for row in cursor.fetchall()
        ]

        # ---------------------------------------------------------
        # CONVERSION
        # ---------------------------------------------------------

        converted_leads = status_counts["CONVERTED"]

        conversion_rate = (
            (converted_leads / total_leads) * 100
            if total_leads > 0
            else 0
        )

        # ---------------------------------------------------------
        # QUALITY METRICS
        # ---------------------------------------------------------

        missing_information_total = (
            missing_phone
            + missing_company
            + missing_message
        )

        data_quality_rate = (
            (
                (total_leads - duplicate_records)
                / total_leads
            ) * 100
            if total_leads > 0
            else 100
        )

        return {
            "batch": batch_info,

            "scope": (
                "IMPORT_BATCH"
                if batch_id is not None
                else "ALL_CRM_LEADS"
            ),

            "generated_at": None,

            "database_overview": {
                "total_leads": total_leads,
                "status_counts": status_counts,
                "conversion_rate": conversion_rate
            },

            "data_quality": {
                "duplicate_records": duplicate_records,
                "confirmed_duplicates": confirmed_duplicates,
                "review_required": review_required,
                "missing_email": missing_email,
                "missing_phone": missing_phone,
                "missing_company": missing_company,
                "missing_message": missing_message,
                "missing_information_total": missing_information_total,
                "data_quality_rate": data_quality_rate
            },

            "lead_intelligence": {
                "priority_counts": priority_counts,
                "high_priority_leads": high_priority_leads,
                "average_lead_score": average_lead_score,
                "analyzed_leads": analyzed_leads,
                "unanalyzed_leads": unanalyzed_leads
            },

            "demand_insights": {
                "top_products": top_products,
                "intent_distribution": intent_distribution
            },

            "recommended_focus": {
                "high_priority_follow_up": high_priority_leads,
                "duplicate_review": review_required,
                "qualified_follow_up": status_counts["QUALIFIED"],
                "re_engagement": (
                    status_counts["LOST"]
                    + status_counts["QUALIFIED"]
                )
            }
        }

    finally:
        conn.close()


def create_lead_activity(lead_id, activity_type, description):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer.")

    activity_type = str(activity_type or "").strip().upper()

    if not activity_type:
        raise ValueError("activity_type is required.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, status
            FROM leads
            WHERE id = ?
        """, (lead_id,))

        lead = cursor.fetchone()

        if not lead:
            conn.rollback()
            return False

        cursor.execute("""
            INSERT INTO lead_activities (
                lead_id,
                activity_type,
                description
            )
            VALUES (?, ?, ?)
        """, (
            lead_id,
            activity_type,
            description
        ))

        outreach_types = {
            "CALL",
            "EMAIL",
            "WHATSAPP"
        }

        if activity_type in outreach_types and lead[1] == "NEW":

            cursor.execute("""
                UPDATE leads
                SET status = 'CONTACTED'
                WHERE id = ?
            """, (lead_id,))

            cursor.execute("""
                INSERT INTO lead_activities (
                    lead_id,
                    activity_type,
                    description
                )
                VALUES (?, ?, ?)
            """, (
                lead_id,
                "STATUS_CHANGED",
                "Lead automatically moved from NEW to CONTACTED after outreach."
            ))

        conn.commit()

        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_lead_activities(lead_id):
    if not isinstance(lead_id, int) or lead_id <= 0:
        raise ValueError("lead_id must be a positive integer.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                lead_id,
                activity_type,
                description,
                created_at
            FROM lead_activities
            WHERE lead_id = ?
            ORDER BY id ASC
        """, (lead_id,))

        return cursor.fetchall()

    finally:
        conn.close()


def log_usage_event(
    client_id,
    user_id,
    event_type,
    tool_used=None,
    records_affected=0,
    metadata=None
):
    """
    Store one usage event.
    """

    event_type = str(event_type or "").strip()

    if not event_type:
        raise ValueError("event_type is required.")

    if not isinstance(records_affected, int):
        raise TypeError("records_affected must be an integer.")

    if records_affected < 0:
        raise ValueError("records_affected cannot be negative.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO usage_events (
                client_id,
                user_id,
                event_type,
                tool_used,
                records_affected,
                metadata
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            user_id,
            event_type,
            tool_used,
            records_affected,
            metadata
        ))

        conn.commit()

        return cursor.lastrowid

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def track_usage(
    client_id,
    user_id,
    event_type,
    tool_used=None,
    records_affected=0,
    metadata=None
):
    """
    Reusable usage-tracking helper.
    """

    return log_usage_event(
        client_id=client_id,
        user_id=user_id,
        event_type=event_type,
        tool_used=tool_used,
        records_affected=records_affected,
        metadata=metadata
    )


def get_usage_events(
    client_id=None,
    user_id=None,
    event_type=None,
    tool_used=None,
    limit=100
):
    """
    Retrieve usage events with optional filters.
    Intended for internal/admin analytics.
    """

    if not isinstance(limit, int):
        raise TypeError("limit must be an integer.")

    if limit <= 0:
        raise ValueError("limit must be greater than 0.")

    conn = get_connection()

    try:
        cursor = conn.cursor()

        query = """
            SELECT
                id,
                client_id,
                user_id,
                event_type,
                tool_used,
                records_affected,
                metadata,
                created_at
            FROM usage_events
        """

        conditions = []
        parameters = []

        if client_id is not None:
            conditions.append("client_id = ?")
            parameters.append(client_id)

        if user_id is not None:
            conditions.append("user_id = ?")
            parameters.append(user_id)

        if event_type is not None:
            conditions.append("event_type = ?")
            parameters.append(event_type)

        if tool_used is not None:
            conditions.append("tool_used = ?")
            parameters.append(tool_used)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY id DESC
            LIMIT ?
        """

        parameters.append(limit)

        cursor.execute(query, tuple(parameters))

        return cursor.fetchall()

    finally:
        conn.close()


def get_usage_analytics():
    """
    Return high-level usage analytics.
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()

        total_events = cursor.execute("""
            SELECT COUNT(*)
            FROM usage_events
        """).fetchone()[0]

        total_records_affected = cursor.execute("""
            SELECT COALESCE(SUM(records_affected), 0)
            FROM usage_events
        """).fetchone()[0]

        leads_created = cursor.execute("""
            SELECT COUNT(*)
            FROM usage_events
            WHERE event_type = 'LEAD_CREATED'
        """).fetchone()[0]

        unique_users = cursor.execute("""
            SELECT COUNT(DISTINCT user_id)
            FROM usage_events
            WHERE user_id IS NOT NULL
        """).fetchone()[0]

        unique_clients = cursor.execute("""
            SELECT COUNT(DISTINCT client_id)
            FROM usage_events
            WHERE client_id IS NOT NULL
        """).fetchone()[0]

        active_users_24h = cursor.execute("""
            SELECT COUNT(DISTINCT user_id)
            FROM usage_events
            WHERE user_id IS NOT NULL
            AND created_at >= datetime('now', '-24 hours')
        """).fetchone()[0]

        active_clients_24h = cursor.execute("""
            SELECT COUNT(DISTINCT client_id)
            FROM usage_events
            WHERE client_id IS NOT NULL
            AND created_at >= datetime('now', '-24 hours')
        """).fetchone()[0]

        cursor.execute("""
            SELECT
                event_type,
                COUNT(*) AS event_count
            FROM usage_events
            GROUP BY event_type
            ORDER BY event_count DESC
        """)

        events_by_type = {
            row[0]: row[1]
            for row in cursor.fetchall()
        }

        cursor.execute("""
            SELECT
                tool_used,
                COUNT(*) AS event_count
            FROM usage_events
            WHERE tool_used IS NOT NULL
            GROUP BY tool_used
            ORDER BY event_count DESC
        """)

        events_by_tool = {
            row[0]: row[1]
            for row in cursor.fetchall()
        }

        cursor.execute("""
            SELECT
                tool_used,
                COALESCE(SUM(records_affected), 0) AS records_affected
            FROM usage_events
            WHERE tool_used IS NOT NULL
            GROUP BY tool_used
            ORDER BY records_affected DESC
        """)

        records_by_tool = {
            row[0]: row[1]
            for row in cursor.fetchall()
        }

        cursor.execute("""
            SELECT
                id,
                client_id,
                user_id,
                event_type,
                tool_used,
                records_affected,
                metadata,
                created_at
            FROM usage_events
            ORDER BY id DESC
            LIMIT 1
        """)

        latest_activity = cursor.fetchone()

        return {
            "total_events": total_events,
            "total_records_affected": total_records_affected,
            "leads_created": leads_created,
            "unique_users": unique_users,
            "unique_clients": unique_clients,
            "active_users_24h": active_users_24h,
            "active_clients_24h": active_clients_24h,
            "events_by_type": events_by_type,
            "events_by_tool": events_by_tool,
            "records_by_tool": records_by_tool,
            "latest_activity": latest_activity
        }

    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
    print("CRM database created successfully.")