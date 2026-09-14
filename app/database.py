import sqlite3
from pathlib import Path

from app.duplicate_detector import detect_duplicate


# ========================================
# DATABASE CONFIGURATION
# ========================================

# Find the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database location
DATABASE_PATH = BASE_DIR / "data" / "crm.db"


# ========================================
# DATABASE CONNECTION
# ========================================

def get_connection():
    """Create a connection to the CRM database."""

    connection = sqlite3.connect(DATABASE_PATH)

    # Enable foreign key support in SQLite
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ========================================
# CREATE DATABASE
# ========================================

def create_database():
    """Create or update the CRM database tables."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------
        # CREATE LEADS TABLE
        # ------------------------------------

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

        # ------------------------------------
        # CHECK EXISTING LEADS COLUMNS
        # ------------------------------------

        cursor.execute("""
            PRAGMA table_info(leads)
        """)

        columns = [
            column[1]
            for column in cursor.fetchall()
        ]

        # ------------------------------------
        # ADD STATUS COLUMN IF NECESSARY
        # ------------------------------------

        if "status" not in columns:

            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN status TEXT DEFAULT 'NEW'
            """)

        # ------------------------------------
        # CREATE IMPORT BATCHES TABLE
        # ------------------------------------

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

        # ------------------------------------
        # CHECK EXISTING LEADS COLUMNS AGAIN
        # ------------------------------------

        cursor.execute("""
            PRAGMA table_info(leads)
        """)

        columns = [
            column[1]
            for column in cursor.fetchall()
        ]

        # ------------------------------------
        # ADD IMPORT BATCH ID IF NECESSARY
        # ------------------------------------

        if "import_batch_id" not in columns:

            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN import_batch_id INTEGER
                REFERENCES import_batches(id)
            """)

        # ------------------------------------
        # CREATE INDEX FOR BATCH LOOKUPS
        # ------------------------------------

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_leads_import_batch_id
            ON leads(import_batch_id)
        """)

        # ------------------------------------
        # CREATE LEAD ACTIVITIES TABLE
        # ------------------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lead_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                description TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (lead_id)
                REFERENCES leads(id)
            )
        """)

        connection.commit()

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ========================================
# INSERT LEAD
# ========================================

def insert_lead(lead):
    """Insert a processed lead into the CRM database."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------
        # INSERT LEAD
        # ------------------------------------

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
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["name"],
            lead["email"],
            lead["phone"],
            lead["company"],
            lead["message"],

            int(
                lead.get(
                    "duplicate",
                    False
                )
            ),

            lead.get(
                "duplicate_reason"
            ),

            lead["ai_analysis"].get(
                "lead_type"
            ),

            lead["ai_analysis"].get(
                "intent"
            ),

            lead["ai_analysis"].get(
                "product"
            ),

            lead["ai_analysis"].get(
                "quantity",
                0
            ),

            lead["ai_analysis"].get(
                "timeline"
            ),

            lead["ai_analysis"].get(
                "priority"
            ),

            lead["ai_analysis"].get(
                "lead_score",
                0
            ),

            lead["ai_analysis"].get(
                "summary"
            ),

            "NEW",
        ))

        lead_id = cursor.lastrowid

        # ------------------------------------
        # AUTOMATICALLY LOG LEAD CREATION
        # ------------------------------------

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
            "Lead was added to the CRM.",
        ))

        connection.commit()

        return lead_id

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ========================================
# FIND EXISTING LEAD BY EMAIL
# ========================================

def get_lead_by_email(email):
    """
    Find an existing CRM lead using email.

    Email matching is case-insensitive and ignores
    surrounding whitespace.
    """

    if not email:

        return None

    normalized_email = str(
        email
    ).strip().lower()

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                name,
                email,
                phone,
                company,
                status
            FROM leads
            WHERE LOWER(TRIM(email)) = ?
            LIMIT 1
        """, (
            normalized_email,
        ))

        return cursor.fetchone()

    finally:

        connection.close()


# ========================================
# IMPORT CLEAN LEADS
# ========================================

def import_clean_leads(
    clean_dataframe,
    batch_key=None,
    client_name=None,
    dataset_name=None,
    source_file=None
):
    """
    Import CLEAN and UNIQUE records from the
    bulk cleanup pipeline into the CRM database.

    Prevents duplicate imports caused by:
    1. Reusing the same batch key.
    2. Importing a lead whose email already exists
       in the CRM.
    3. Importing a lead that strongly matches an
       existing lead by identity signals such as
       name and company.

    Exact email duplicates are skipped.

    Strong identity matches are imported but flagged
    for human review.

    The system never automatically deletes or merges
    leads.

    The entire batch is handled as one transaction.
    """

    connection = get_connection()
    cursor = connection.cursor()

    imported_count = 0
    skipped_count = 0
    existing_duplicate_count = 0
    possible_duplicate_count = 0

    try:

        # ------------------------------------
        # CHECK REQUIRED COLUMNS
        # ------------------------------------

        required_columns = [
            "name",
            "email",
            "phone",
            "company",
            "message",
            "validation_status",
            "duplicate_status",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in clean_dataframe.columns
        ]

        if missing_columns:

            raise ValueError(
                "Missing required columns: "
                + ", ".join(missing_columns)
            )

        # ------------------------------------
        # FILTER ONLY CLEAN + UNIQUE RECORDS
        # ------------------------------------

        clean_records = clean_dataframe[
            (
                clean_dataframe["validation_status"]
                == "CLEAN"
            )
            &
            (
                clean_dataframe["duplicate_status"]
                == "UNIQUE"
            )
        ].copy()

        # ------------------------------------
        # NOTHING TO IMPORT
        # ------------------------------------

        if clean_records.empty:

            connection.commit()

            return {
                "imported": 0,
                "skipped": 0,
                "existing_duplicates": 0,
                "possible_duplicates": 0,
                "already_imported": False,
                "batch_id": None,
            }

        # ------------------------------------
        # CHECK BATCH INFORMATION
        # ------------------------------------

        if batch_key:

            if not client_name:
                raise ValueError(
                    "client_name is required when "
                    "batch_key is provided."
                )

            if not dataset_name:
                raise ValueError(
                    "dataset_name is required when "
                    "batch_key is provided."
                )

            if not source_file:
                raise ValueError(
                    "source_file is required when "
                    "batch_key is provided."
                )

            # --------------------------------
            # CHECK IF BATCH ALREADY EXISTS
            # --------------------------------

            cursor.execute("""
                SELECT
                    id,
                    imported_count,
                    status
                FROM import_batches
                WHERE batch_key = ?
            """, (
                batch_key,
            ))

            existing_batch = cursor.fetchone()

            if existing_batch:

                batch_id = existing_batch[0]

                return {
                    "imported": 0,
                    "skipped": len(clean_records),
                    "existing_duplicates": 0,
                    "possible_duplicates": 0,
                    "already_imported": True,
                    "batch_id": batch_id,
                }

            # --------------------------------
            # CREATE IMPORT BATCH
            # --------------------------------

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
                "IMPORTING",
            ))

            batch_id = cursor.lastrowid

        else:

            batch_id = None

        # ------------------------------------
        # LOAD EXISTING CRM LEADS
        # ------------------------------------

        cursor.execute("""
            SELECT
                id,
                name,
                email,
                phone,
                company,
                status
            FROM leads
        """)

        existing_leads = cursor.fetchall()

        # ------------------------------------
        # IMPORT EACH CLEAN RECORD
        # ------------------------------------

        for _, row in clean_records.iterrows():

            name = str(
                row.get("name", "")
            ).strip()

            email = str(
                row.get("email", "")
            ).strip()

            phone = str(
                row.get("phone", "")
            ).strip()

            company = str(
                row.get("company", "")
            ).strip()

            message = str(
                row.get("message", "")
            ).strip()

            # --------------------------------
            # SAFETY CHECK
            # --------------------------------

            if not name or not email:

                raise ValueError(
                    "A CLEAN record is missing "
                    "a required name or email."
                )

            # --------------------------------
            # CHECK EXACT EMAIL DUPLICATE
            # --------------------------------

            normalized_email = email.lower()

            cursor.execute("""
                SELECT
                    id
                FROM leads
                WHERE LOWER(TRIM(email)) = ?
                LIMIT 1
            """, (
                normalized_email,
            ))

            existing_email_lead = cursor.fetchone()

            if existing_email_lead:

                skipped_count += 1
                existing_duplicate_count += 1

                continue

            # --------------------------------
            # CHECK IDENTITY-BASED DUPLICATES
            # --------------------------------

            incoming_lead = {
                "name": name,
                "email": email,
                "phone": phone,
                "company": company,
            }

            duplicate_match = None

            for existing_lead in existing_leads:

                existing_record = {
                    "name": existing_lead[1],
                    "email": existing_lead[2],
                    "phone": existing_lead[3],
                    "company": existing_lead[4],
                }

                duplicate_result = detect_duplicate(
                    incoming_lead,
                    existing_record
                )

                if duplicate_result["status"] == "DUPLICATE":

                    duplicate_match = {
                        "lead_id": existing_lead[0],
                        "confidence": duplicate_result[
                            "confidence"
                        ],
                        "reason": duplicate_result[
                            "reason"
                        ],
                    }

                    break

            # --------------------------------
            # DETERMINE DUPLICATE FLAG
            # --------------------------------

            duplicate_flag = 0
            duplicate_reason = None

            if duplicate_match:

                duplicate_flag = 1

                duplicate_reason = (
                    "Possible existing lead "
                    f"(Lead ID "
                    f"{duplicate_match['lead_id']}): "
                    f"{duplicate_match['reason']} "
                    f"Confidence: "
                    f"{duplicate_match['confidence']}"
                )

                possible_duplicate_count += 1

            # --------------------------------
            # INSERT LEAD
            # --------------------------------

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
                VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?
                )
            """, (
                name,
                email,
                phone,
                company,
                message,

                duplicate_flag,
                duplicate_reason,
                None,
                None,
                None,
                0,
                None,
                None,
                0,
                None,

                "NEW",
                batch_id,
            ))

            lead_id = cursor.lastrowid

            # --------------------------------
            # ADD NEW LEAD TO COMPARISON LIST
            # --------------------------------
            #
            # This prevents later records in the
            # same import batch from bypassing the
            # identity-based duplicate check.

            existing_leads.append((
                lead_id,
                name,
                email,
                phone,
                company,
                "NEW",
            ))

            # --------------------------------
            # LOG CREATION ACTIVITY
            # --------------------------------

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
                "Lead was imported from the bulk CRM cleanup pipeline.",
            ))

            # --------------------------------
            # LOG DUPLICATE REVIEW FLAG
            # --------------------------------

            if duplicate_match:

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
                    duplicate_reason,
                ))

            imported_count += 1

        # ------------------------------------
        # COMPLETE IMPORT BATCH
        # ------------------------------------

        if batch_id:

            cursor.execute("""
                UPDATE import_batches
                SET
                    imported_count = ?,
                    status = 'COMPLETED'
                WHERE id = ?
            """, (
                imported_count,
                batch_id,
            ))

        # ------------------------------------
        # COMMIT ENTIRE BATCH
        # ------------------------------------

        connection.commit()

        return {
            "imported": imported_count,
            "skipped": skipped_count,
            "existing_duplicates": existing_duplicate_count,
            "possible_duplicates": possible_duplicate_count,
            "already_imported": False,
            "batch_id": batch_id,
        }

    except Exception:

        # ------------------------------------
        # ROLLBACK ENTIRE BATCH
        # ------------------------------------

        connection.rollback()

        raise

    finally:

        connection.close()


# ========================================
# GET IMPORT BATCH
# ========================================

def get_import_batch(batch_key):
    """Retrieve an import batch using its unique batch key."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

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
        """, (
            batch_key,
        ))

        return cursor.fetchone()

    finally:

        connection.close()


# ========================================
# GET IMPORT BATCHES
# ========================================

def get_import_batches():
    """Retrieve all bulk import batches."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

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

        connection.close()


# ========================================
# GET LEADS BY IMPORT BATCH
# ========================================

def get_leads_by_import_batch(batch_id):
    """Retrieve all leads imported through a specific batch."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM leads
            WHERE import_batch_id = ?
            ORDER BY id ASC
        """, (
            batch_id,
        ))

        return cursor.fetchall()

    finally:

        connection.close()


# ========================================
# GET IMPORT BATCH STATISTICS
# ========================================

def get_import_batch_stats(batch_id):
    """
    Calculate lead statistics for a specific
    import batch.

    Returns the total number of leads and
    the number of leads in each CRM status.
    Also calculates the batch conversion rate.
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------
        # CHECK THAT BATCH EXISTS
        # ------------------------------------

        cursor.execute("""
            SELECT id
            FROM import_batches
            WHERE id = ?
        """, (
            batch_id,
        ))

        batch = cursor.fetchone()

        if not batch:

            return None

        # ------------------------------------
        # GET TOTAL LEADS
        # ------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE import_batch_id = ?
        """, (
            batch_id,
        ))

        total_leads = cursor.fetchone()[0]

        # ------------------------------------
        # GET LEADS BY STATUS
        # ------------------------------------

        cursor.execute("""
            SELECT
                status,
                COUNT(*)
            FROM leads
            WHERE import_batch_id = ?
            GROUP BY status
        """, (
            batch_id,
        ))

        status_counts = dict(
            cursor.fetchall()
        )

        # ------------------------------------
        # ENSURE ALL STANDARD STATUSES EXIST
        # ------------------------------------

        statuses = [
            "NEW",
            "CONTACTED",
            "QUALIFIED",
            "CONVERTED",
            "LOST",
        ]

        for status in statuses:

            status_counts.setdefault(
                status,
                0
            )

        # ------------------------------------
        # CONVERTED LEADS
        # ------------------------------------

        converted_leads = status_counts[
            "CONVERTED"
        ]

        # ------------------------------------
        # CONVERSION RATE
        # ------------------------------------

        if total_leads > 0:

            conversion_rate = (
                converted_leads
                / total_leads
            ) * 100

        else:

            conversion_rate = 0

        return {
            "batch_id": batch_id,
            "total_leads": total_leads,
            "status_counts": status_counts,
            "converted_leads": converted_leads,
            "conversion_rate": conversion_rate,
        }

    finally:

        connection.close()


# ========================================
# GET ALL IMPORT BATCH STATISTICS
# ========================================

def get_all_import_batch_stats():
    """
    Calculate performance statistics for all
    import batches.

    Returns one statistics record for every
    import batch in the database.
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------
        # GET ALL IMPORT BATCHES
        # ------------------------------------

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

        # ------------------------------------
        # CALCULATE STATISTICS FOR EACH BATCH
        # ------------------------------------

        for batch in batches:

            (
                batch_id,
                batch_key,
                client_name,
                dataset_name,
                source_file,
                imported_count,
                batch_status,
                created_at
            ) = batch

            # --------------------------------
            # GET STATUS COUNTS
            # --------------------------------

            cursor.execute("""
                SELECT
                    status,
                    COUNT(*)
                FROM leads
                WHERE import_batch_id = ?
                GROUP BY status
            """, (
                batch_id,
            ))

            status_counts = dict(
                cursor.fetchall()
            )

            # --------------------------------
            # ENSURE ALL STANDARD STATUSES EXIST
            # --------------------------------

            statuses = [
                "NEW",
                "CONTACTED",
                "QUALIFIED",
                "CONVERTED",
                "LOST",
            ]

            for status in statuses:

                status_counts.setdefault(
                    status,
                    0
                )

            # --------------------------------
            # TOTAL LEADS
            # --------------------------------

            total_leads = sum(
                status_counts.values()
            )

            # --------------------------------
            # CONVERTED LEADS
            # --------------------------------

            converted_leads = status_counts[
                "CONVERTED"
            ]

            # --------------------------------
            # CONVERSION RATE
            # --------------------------------

            if total_leads > 0:

                conversion_rate = (
                    converted_leads
                    / total_leads
                ) * 100

            else:

                conversion_rate = 0

            # --------------------------------
            # STORE BATCH STATISTICS
            # --------------------------------

            results.append({
                "batch_id": batch_id,
                "batch_key": batch_key,
                "client_name": client_name,
                "dataset_name": dataset_name,
                "source_file": source_file,
                "imported_count": imported_count,
                "status": batch_status,
                "created_at": created_at,
                "total_leads": total_leads,
                "status_counts": status_counts,
                "converted_leads": converted_leads,
                "conversion_rate": conversion_rate,
            })

        return results

    finally:

        connection.close()


# ========================================
# UPDATE LEAD
# ========================================

def update_lead(
    lead_id,
    priority,
    lead_score
):
    """Update the priority and lead score of an existing lead."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            UPDATE leads
            SET
                priority = ?,
                lead_score = ?
            WHERE id = ?
        """, (
            priority,
            lead_score,
            lead_id,
        ))

        rows_updated = cursor.rowcount

        connection.commit()

        return rows_updated

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ========================================
# UPDATE LEAD STATUS
# ========================================

def update_lead_status(
    lead_id,
    status
):
    """Update the status of an existing lead."""

    allowed_statuses = [
        "NEW",
        "CONTACTED",
        "QUALIFIED",
        "CONVERTED",
        "LOST",
    ]

    status = status.upper()

    if status not in allowed_statuses:

        raise ValueError(
            "Invalid status. Choose from: "
            + ", ".join(allowed_statuses)
        )

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            UPDATE leads
            SET status = ?
            WHERE id = ?
        """, (
            status,
            lead_id,
        ))

        rows_updated = cursor.rowcount

        connection.commit()

        return rows_updated

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ========================================
# GET LEADS BY STATUS
# ========================================

def get_leads_by_status(status):
    """Retrieve all leads with a specific status."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT *
            FROM leads
            WHERE status = ?
            ORDER BY id DESC
        """, (
            status.upper(),
        ))

        return cursor.fetchall()

    finally:

        connection.close()


# ========================================
# DELETE LEAD
# ========================================

def delete_lead(lead_id):
    """Delete a lead and its activities."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # Delete activities first
        cursor.execute("""
            DELETE FROM lead_activities
            WHERE lead_id = ?
        """, (
            lead_id,
        ))

        # Delete the lead
        cursor.execute("""
            DELETE FROM leads
            WHERE id = ?
        """, (
            lead_id,
        ))

        rows_deleted = cursor.rowcount

        connection.commit()

        return rows_deleted

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ========================================
# DASHBOARD STATISTICS
# ========================================

def get_dashboard_stats():
    """Retrieve important CRM dashboard statistics."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------
        # TOTAL LEADS
        # ------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
        """)

        total_leads = cursor.fetchone()[0]

        # ------------------------------------
        # LEADS BY STATUS
        # ------------------------------------

        cursor.execute("""
            SELECT
                status,
                COUNT(*)
            FROM leads
            GROUP BY status
        """)

        status_counts = dict(
            cursor.fetchall()
        )

        # ------------------------------------
        # HIGH PRIORITY LEADS
        # ------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE priority = 'HIGH'
        """)

        high_priority_leads = (
            cursor.fetchone()[0]
        )

        # ------------------------------------
        # AVERAGE LEAD SCORE
        # ------------------------------------

        cursor.execute("""
            SELECT AVG(lead_score)
            FROM leads
        """)

        average_lead_score = (
            cursor.fetchone()[0]
        )

        # ------------------------------------
        # CONVERTED LEADS
        # ------------------------------------

        cursor.execute("""
            SELECT COUNT(*)
            FROM leads
            WHERE status = 'CONVERTED'
        """)

        converted_leads = (
            cursor.fetchone()[0]
        )

    finally:

        connection.close()

    # ------------------------------------
    # CONVERSION RATE
    # ------------------------------------

    if total_leads > 0:

        conversion_rate = (
            converted_leads
            / total_leads
        ) * 100

    else:

        conversion_rate = 0

    return {
        "total_leads": total_leads,
        "status_counts": status_counts,
        "high_priority_leads": high_priority_leads,
        "average_lead_score": (
            average_lead_score or 0
        ),
        "converted_leads": converted_leads,
        "conversion_rate": conversion_rate,
    }


# ========================================
# CREATE LEAD ACTIVITY
# ========================================

def create_lead_activity(
    lead_id,
    activity_type,
    description
):
    """
    Create a new activity for a lead.

    If the lead is currently NEW and the
    activity is an outreach activity,
    automatically move the lead to CONTACTED.
    """

    # ------------------------------------
    # OUTREACH ACTIVITIES
    # ------------------------------------

    outreach_activities = [
        "CALL",
        "EMAIL",
        "WHATSAPP",
    ]

    activity_type = activity_type.upper()

    connection = get_connection()
    cursor = connection.cursor()

    try:

        # ------------------------------------
        # CHECK THAT LEAD EXISTS
        # ------------------------------------

        cursor.execute("""
            SELECT status
            FROM leads
            WHERE id = ?
        """, (
            lead_id,
        ))

        lead = cursor.fetchone()

        if not lead:

            raise ValueError(
                f"Lead with ID {lead_id} does not exist."
            )

        current_status = lead[0]

        # ------------------------------------
        # CREATE ACTIVITY
        # ------------------------------------

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
            description,
        ))

        activity_id = cursor.lastrowid

        # ------------------------------------
        # AUTOMATIC STATUS CHANGE
        # ------------------------------------

        if (
            current_status == "NEW"
            and activity_type in outreach_activities
        ):

            cursor.execute("""
                UPDATE leads
                SET status = 'CONTACTED'
                WHERE id = ?
            """, (
                lead_id,
            ))

            # --------------------------------
            # LOG AUTOMATIC STATUS CHANGE
            # --------------------------------

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
                (
                    "Lead automatically moved from "
                    "NEW to CONTACTED after first outreach."
                ),
            ))

        connection.commit()

        return activity_id

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


# ========================================
# GET LEAD ACTIVITIES
# ========================================

def get_lead_activities(lead_id):
    """Retrieve all activities for a specific lead."""

    connection = get_connection()
    cursor = connection.cursor()

    try:

        cursor.execute("""
            SELECT
                id,
                lead_id,
                activity_type,
                description,
                created_at
            FROM lead_activities
            WHERE lead_id = ?
            ORDER BY created_at DESC, id DESC
        """, (
            lead_id,
        ))

        return cursor.fetchall()

    finally:

        connection.close()


# ========================================
# RUN DATABASE SETUP DIRECTLY
# ========================================

if __name__ == "__main__":

    create_database()

    print(
        "CRM database created successfully."
    )