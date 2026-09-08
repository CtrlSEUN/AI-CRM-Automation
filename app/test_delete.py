from database import delete_lead


lead_id = 2

rows_deleted = delete_lead(lead_id)

if rows_deleted:
    print("Lead deleted successfully.")
    print(f"Deleted Lead ID: {lead_id}")
else:
    print("Lead not found.")