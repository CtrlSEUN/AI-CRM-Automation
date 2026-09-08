from duplicate_detector import (
    normalize_for_comparison,
    is_potential_duplicate,
)


print("===== DUPLICATE DETECTOR TESTS =====")


# ----------------------------------------
# TEST 1: SAME EMAIL
# ----------------------------------------

lead_1 = {
    "name": "John Smith",
    "email": "john@gmail.com",
    "phone": "08031234567",
}

lead_2 = {
    "name": "Different Person",
    "email": "john@gmail.com",
    "phone": "09098765432",
}

result = is_potential_duplicate(lead_1, lead_2)

print("\nSame email:")
print(result)


# ----------------------------------------
# TEST 2: SAME PHONE
# ----------------------------------------

lead_1 = {
    "name": "John Smith",
    "email": "john@gmail.com",
    "phone": "0803-123-4567",
}

lead_2 = {
    "name": "Michael Johnson",
    "email": "michael@gmail.com",
    "phone": "08031234567",
}

result = is_potential_duplicate(lead_1, lead_2)

print("\nSame phone:")
print(result)


# ----------------------------------------
# TEST 3: SAME NAME
# ----------------------------------------

lead_1 = {
    "name": "John Smith",
    "email": "john@gmail.com",
    "phone": "08031234567",
}

lead_2 = {
    "name": " JOHN SMITH ",
    "email": "different@gmail.com",
    "phone": "09098765432",
}

result = is_potential_duplicate(lead_1, lead_2)

print("\nSame name:")
print(result)


# ----------------------------------------
# TEST 4: NOT A DUPLICATE
# ----------------------------------------

lead_1 = {
    "name": "John Smith",
    "email": "john@gmail.com",
    "phone": "08031234567",
}

lead_2 = {
    "name": "Michael Johnson",
    "email": "michael@gmail.com",
    "phone": "09098765432",
}

result = is_potential_duplicate(lead_1, lead_2)

print("\nDifferent leads:")
print(result)


print("\n===== TESTS COMPLETE =====")