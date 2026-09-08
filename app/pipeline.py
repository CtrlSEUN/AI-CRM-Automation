from database import create_database, insert_lead
from lead_cleaner import clean_lead
from duplicate_detector import is_potential_duplicate
from lead_analyzer import analyze_lead


# --------------------------------------------------
# 1. NEW CUSTOMER LEAD
# --------------------------------------------------

create_database()

# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------


new_lead = {
    "name": "  JOHN   SMITH  ",
    "email": " JOHN@ABC.COM ",
    "phone": "0803-123-4567",
    "company": "  ABC   FURNITURE LTD ",
    "message": "  I need 50 office chairs.  ",
}


# --------------------------------------------------
# 2. EXISTING CUSTOMER
# --------------------------------------------------

existing_lead = {
    "name": "John Smith",
    "email": "john@abc.com",
    "phone": "0803-123-4567",
    "company": "ABC Furniture Ltd",
    "message": "Interested in office chairs.",
}


print("======================================")
print("       AI CRM AUTOMATION PIPELINE")
print("======================================")


# --------------------------------------------------
# 3. CLEAN THE NEW LEAD
# --------------------------------------------------

cleaned_lead = clean_lead(new_lead)

print("\n===== CLEANED LEAD =====")
print(cleaned_lead)


# --------------------------------------------------
# 4. CHECK FOR DUPLICATE
# --------------------------------------------------

existing_lead = clean_lead(existing_lead)

duplicate, reason = is_potential_duplicate(
    cleaned_lead,
    existing_lead
)

print("\n===== DUPLICATE CHECK =====")

if duplicate:
    print("Potential duplicate: YES")
    print("Reason:", reason)
else:
    print("Potential duplicate: NO")
    print("Reason:", reason)


# --------------------------------------------------
# 5. SEND LEAD TO NVIDIA AI
# --------------------------------------------------

analysis = analyze_lead(cleaned_lead)

print("\n===== FINAL AI ANALYSIS =====")
print(analysis)


# --------------------------------------------------
# 6. FINAL CRM RECORD
# --------------------------------------------------

crm_record = {
    **cleaned_lead,
    "duplicate": duplicate,
    "duplicate_reason": reason,
    "ai_analysis": analysis,
}


print("\n===== FINAL CRM RECORD =====")
print(crm_record)


# --------------------------------------------------
# 7. SAVE LEAD TO DATABASE
# --------------------------------------------------

lead_id = insert_lead(crm_record)

print("\n===== DATABASE =====")
print(f"Lead saved successfully with ID: {lead_id}")