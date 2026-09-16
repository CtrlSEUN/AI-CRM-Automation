import sqlite3
from pathlib import Path
from app.duplicate_detector import detect_duplicate


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "crm.db"


def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_database():
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

        # Day 27: Usage Analytics Foundation
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
            lead.get("name"),
            lead.get("email"),
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
            lead.get("priority"),
            lead.get("lead_score"),
            lead.get("summary"),
            lead.get("status", "NEW"),
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


def get_lead_by_email(email):
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

    clean_rows = clean_dataframe[
        (clean_dataframe["validation_status"] == "CLEAN") &
        (clean_dataframe["duplicate_status"] == "UNIQUE")
    ].copy()

    conn = get_connection()

    try:
        cursor = conn.cursor()

        if batch_key:
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
                    "already_imported": True,
                    "batch_id": existing_batch[0]
                }

        if not batch_key:
            raise ValueError("batch_key is required.")

        if not client_name:
            raise ValueError("client_name is required.")

        if not dataset_name:
            raise ValueError("dataset_name is required.")

        if not source_file:
            raise ValueError("source_file is required.")

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

        for _, row in clean_rows.iterrows():

            name = str(row["name"]).strip()
            email = str(row["email"]).strip()
            phone = str(row["phone"]).strip()
            company = str(row["company"]).strip()
            message = str(row["message"]).strip()

            if not name or not email:
                skipped_count += 1
                continue

            existing_by_email = get_lead_by_email(email)

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

                if duplicate_result["status"] == "DUPLICATE":
                    duplicate_flag = 1

                    duplicate_reason = (
                        f"Possible existing lead "
                        f"(Lead ID {existing_lead[0]}): "
                        f"{duplicate_result['reason']} "
                        f"Confidence: {duplicate_result['confidence']}"
                    )

                    possible_duplicate_count += 1
                    break

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
                row.get("priority"),
                row.get("lead_score"),
                row.get("summary"),
                row.get("status", "NEW"),
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

            if duplicate_flag:
                cursor.execute("""
                    INSERT INTO lead_activities (
                        lead_id,
                        activity_type,
                        description
                    )
                    VALUES (?, ?, ?)
                """, (
                    lead_id,
                    "DUPLICATE_REVIEW",
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
            "already_imported": False,
            "batch_id": batch_id
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_import_batch(batch_key):
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

        statuses = [
            "NEW",
            "CONTACTED",
            "QUALIFIED",
            "CONVERTED",
            "LOST"
        ]

        status_counts = {}

        for status in statuses:
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

        statuses = [
            "NEW",
            "CONTACTED",
            "QUALIFIED",
            "CONVERTED",
            "LOST"
        ]

        for batch in batches:

            batch_id = batch[0]

            cursor.execute("""
                SELECT COUNT(*)
                FROM leads
                WHERE import_batch_id = ?
            """, (batch_id,))

            total_leads = cursor.fetchone()[0]

            status_counts = {}

            for status in statuses:
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

        conn.commit()

        return cursor.rowcount > 0

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_lead_status(lead_id, status):
    allowed_statuses = {
        "NEW",
        "CONTACTED",
        "QUALIFIED",
        "CONVERTED",
        "LOST"
    }

    status = status.upper()

    if status not in allowed_statuses:
        raise ValueError(
            f"Invalid status. Allowed values: {sorted(allowed_statuses)}"
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


def get_leads_by_status(status):
    status = status.upper()

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

        statuses = [
            "NEW",
            "CONTACTED",
            "QUALIFIED",
            "CONVERTED",
            "LOST"
        ]

        status_counts = {}

        for status in statuses:
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


def create_lead_activity(lead_id, activity_type, description):
    conn = get_connection()

    try:
        cursor = conn.cursor()

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

        if activity_type.upper() in outreach_types:

            cursor.execute("""
                SELECT status
                FROM leads
                WHERE id = ?
            """, (lead_id,))

            lead = cursor.fetchone()

            if lead and lead[0] == "NEW":

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

    This keeps usage tracking consistent across
    CRM features and future application services.
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

    This is intended for internal/admin analytics.
    """

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

    This provides the foundation for future
    admin/client analytics dashboards.
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # Total number of tracked events.
        total_events = cursor.execute("""
            SELECT COUNT(*)
            FROM usage_events
        """).fetchone()[0]

        # Total number of records affected by tracked events.
        total_records_affected = cursor.execute("""
            SELECT COALESCE(SUM(records_affected), 0)
            FROM usage_events
        """).fetchone()[0]

        # Number of lead creation events.
        leads_created = cursor.execute("""
            SELECT COUNT(*)
            FROM usage_events
            WHERE event_type = 'LEAD_CREATED'
        """).fetchone()[0]

        # Number of distinct users that have generated events.
        unique_users = cursor.execute("""
            SELECT COUNT(DISTINCT user_id)
            FROM usage_events
            WHERE user_id IS NOT NULL
        """).fetchone()[0]

        # Number of distinct clients that have generated events.
        unique_clients = cursor.execute("""
            SELECT COUNT(DISTINCT client_id)
            FROM usage_events
            WHERE client_id IS NOT NULL
        """).fetchone()[0]

        # Users active during the last 24 hours.
        active_users_24h = cursor.execute("""
            SELECT COUNT(DISTINCT user_id)
            FROM usage_events
            WHERE user_id IS NOT NULL
            AND created_at >= datetime('now', '-24 hours')
        """).fetchone()[0]

        # Clients active during the last 24 hours.
        active_clients_24h = cursor.execute("""
            SELECT COUNT(DISTINCT client_id)
            FROM usage_events
            WHERE client_id IS NOT NULL
            AND created_at >= datetime('now', '-24 hours')
        """).fetchone()[0]

        # Events grouped by event type.
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

        # Events grouped by tool.
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

        # Records processed grouped by tool.
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

        # Most recent usage event.
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