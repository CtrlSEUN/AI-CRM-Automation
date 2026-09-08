from database import update_lead


lead_id = 2

rows_updated = update_lead(
    lead_id,
    "HIGH",
    95
)

if rows_updated:
    print("Lead updated successfully.")
    print(f"Lead ID: {lead_id}")
    print("New Priority: HIGH")
    print("New Lead Score: 95")
else:
    print("Lead not found.")