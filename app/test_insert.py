from database import insert_lead


test_lead = {
    "name": "Jane Doe",
    "email": "jane@xyz.com",
    "phone": "08098765432",
    "company": "XYZ Technologies",
    "message": "We need 20 laptops for our new office.",
    "duplicate": False,
    "duplicate_reason": None,
    "ai_analysis": {
        "lead_type": "Sales",
        "intent": "Purchase",
        "product": "Laptops",
        "quantity": 20,
        "timeline": "Next month",
        "priority": "HIGH",
        "lead_score": 85,
        "summary": "Customer wants to purchase 20 laptops for a new office.",
    },
}


lead_id = insert_lead(test_lead)

print("Test lead inserted successfully.")
print(f"Lead ID: {lead_id}")