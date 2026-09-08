from app.database import get_connection


def get_all_leads():
    """Retrieve all leads from the CRM database."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM leads
        ORDER BY id
    """)

    leads = cursor.fetchall()

    connection.close()

    return leads


def search_leads_by_email(email):
    """Find leads matching an email address."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM leads
        WHERE email = ?
        ORDER BY id
    """, (email,))

    leads = cursor.fetchall()

    connection.close()

    return leads


def search_leads_by_priority(priority):
    """Find leads matching a priority level."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM leads
        WHERE priority = ?
        ORDER BY lead_score DESC
    """, (priority,))

    leads = cursor.fetchall()

    connection.close()

    return leads


def search_leads_by_status(status):
    """Find leads matching a status."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM leads
        WHERE status = ?
        ORDER BY id
    """, (status,))

    leads = cursor.fetchall()

    connection.close()

    return leads


def get_lead_by_id(lead_id):
    """Retrieve a single lead by its ID."""

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM leads
        WHERE id = ?
    """, (lead_id,))

    lead = cursor.fetchone()

    connection.close()

    return lead
