from validation import (
    validate_name,
    validate_email,
    validate_phone,
    validate_company,
    validate_message,
    validate_quantity,
    validate_priority,
    validate_lead_score,
)


print("===== VALIDATION TESTS =====")


print("\nName:")
print(validate_name("John Smith"))
print(validate_name(""))


print("\nEmail:")
print(validate_email("john@abc.com"))
print(validate_email("john"))


print("\nPhone:")
print(validate_phone("08031234567"))
print(validate_phone("abc"))


print("\nCompany:")
print(validate_company("ABC Furniture Ltd"))
print(validate_company(""))


print("\nMessage:")
print(validate_message("I need 50 chairs."))
print(validate_message(""))


print("\nQuantity:")
print(validate_quantity("50"))
print(validate_quantity("abc"))
print(validate_quantity("-5"))


print("\nPriority:")
print(validate_priority("HIGH"))
print(validate_priority("INVALID"))


print("\nLead Score:")
print(validate_lead_score("90"))
print(validate_lead_score("150"))