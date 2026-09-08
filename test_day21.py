from app.database import get_connection


connection = get_connection()
cursor = connection.cursor()

# Check how many leads belong to Batch 1
cursor.execute(
    "SELECT COUNT(*) FROM leads WHERE import_batch_id = ?",
    (1,)
)

lead_count = cursor.fetchone()[0]

# Check how many CREATED activities belong to Batch 1
cursor.execute(
    """
    SELECT COUNT(*)
    FROM lead_activities
    WHERE activity_type = ?
    AND lead_id IN (
        SELECT id
        FROM leads
        WHERE import_batch_id = ?
    )
    """,
    ("CREATED", 1)
)

activity_count = cursor.fetchone()[0]

print("========================================")
print("       DAY 21 DATABASE VERIFICATION")
print("========================================")
print()
print(f"Leads in Batch 1: {lead_count}")
print(f"CREATED activities for Batch 1: {activity_count}")
print()

if lead_count == 3 and activity_count == 3:
    print("RESULT: PASS")
    print("Batch 1 contains exactly 3 leads and 3 CREATED activities.")
else:
    print("RESULT: CHECK REQUIRED")

connection.close()