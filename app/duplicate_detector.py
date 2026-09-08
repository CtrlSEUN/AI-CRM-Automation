from rapidfuzz.fuzz import ratio


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_for_comparison(value):
    """
    Create a simplified version of a value for comparison.

    Removes:
    - spaces
    - hyphens
    - dots
    - capitalization differences
    """

    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
    )


# ============================================================
# FUZZY SIMILARITY
# ============================================================

def similarity_score(value1, value2):
    """
    Calculate fuzzy similarity between two values.

    Returns a score from 0 to 100.
    """

    value1 = normalize_for_comparison(value1)
    value2 = normalize_for_comparison(value2)

    if not value1 or not value2:
        return 0

    return round(ratio(value1, value2), 2)


# ============================================================
# RECORD COMPARISON
# ============================================================

def compare_records(new_lead, existing_lead):
    """
    Compare two CRM records.

    Returns similarity scores for:
    - name
    - company
    - email
    - phone
    """

    return {
        "name_score": similarity_score(
            new_lead.get("name"),
            existing_lead.get("name")
        ),

        "company_score": similarity_score(
            new_lead.get("company"),
            existing_lead.get("company")
        ),

        "email_score": similarity_score(
            new_lead.get("email"),
            existing_lead.get("email")
        ),

        "phone_score": similarity_score(
            new_lead.get("phone"),
            existing_lead.get("phone")
        ),
    }


# ============================================================
# CONFIDENCE SCORING
# ============================================================

def calculate_confidence(scores):
    """
    Calculate duplicate confidence based on field similarity.

    HIGH:
        Very strong evidence of duplication.

    MEDIUM:
        Multiple pieces of evidence suggest the records
        may represent the same customer.

    LOW:
        Weak similarity that should not be treated as a
        duplicate by itself.

    UNIQUE:
        Not enough evidence of duplication.
    """

    name = scores["name_score"]
    company = scores["company_score"]
    email = scores["email_score"]
    phone = scores["phone_score"]

    # --------------------------------------------------------
    # STRONG IDENTIFIER MATCH
    # --------------------------------------------------------

    if email >= 98:
        return "HIGH", "Very strong email match"

    if phone >= 98:
        return "HIGH", "Very strong phone match"

    # --------------------------------------------------------
    # STRONG NAME + COMPANY MATCH
    # --------------------------------------------------------

    if name >= 90 and company >= 90:
        return "HIGH", "Strong name and company match"

    # --------------------------------------------------------
    # FUZZY NAME + COMPANY
    # --------------------------------------------------------

    if name >= 85 and company >= 80:
        return "MEDIUM", "Similar name and company"

    # --------------------------------------------------------
    # NAME + EMAIL
    # --------------------------------------------------------

    if name >= 85 and email >= 85:
        return "MEDIUM", "Similar name and email"

    # --------------------------------------------------------
    # NAME + PHONE
    # --------------------------------------------------------

    if name >= 85 and phone >= 85:
        return "MEDIUM", "Similar name and phone"

    # --------------------------------------------------------
    # COMPANY + EMAIL
    # --------------------------------------------------------

    if company >= 85 and email >= 85:
        return "MEDIUM", "Similar company and email"

    # --------------------------------------------------------
    # COMPANY + PHONE
    # --------------------------------------------------------

    if company >= 85 and phone >= 85:
        return "MEDIUM", "Similar company and phone"

    # --------------------------------------------------------
    # SAME NAME ONLY
    #
    # Important:
    # A matching name by itself is NOT enough evidence.
    # --------------------------------------------------------

    if name >= 95:
        return "UNIQUE", "Same or very similar name only - insufficient evidence"

    # --------------------------------------------------------
    # WEAK SIMILARITY
    # --------------------------------------------------------

    if name >= 80 or company >= 85:
        return "LOW", "Weak similarity - insufficient evidence"

    # --------------------------------------------------------
    # NO SIGNIFICANT MATCH
    # --------------------------------------------------------

    return "UNIQUE", "No significant duplicate evidence"


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def detect_duplicate(new_lead, existing_lead):
    """
    Compare two leads and determine whether they are:

    - DUPLICATE
    - POSSIBLE DUPLICATE
    - UNIQUE
    """

    scores = compare_records(
        new_lead,
        existing_lead
    )

    confidence, reason = calculate_confidence(scores)

    # --------------------------------------------------------
    # STATUS CLASSIFICATION
    # --------------------------------------------------------

    if confidence == "HIGH":

        status = "DUPLICATE"

    elif confidence == "MEDIUM":

        status = "POSSIBLE DUPLICATE"

    else:

        status = "UNIQUE"

    return {
        "status": status,
        "confidence": confidence,
        "reason": reason,
        "scores": scores,
    }


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

def is_potential_duplicate(new_lead, existing_lead):
    """
    Backward-compatible duplicate check.

    Returns:

        True, reason
        False, reason
    """

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    if result["status"] == "DUPLICATE":

        return True, result["reason"]

    if result["status"] == "POSSIBLE DUPLICATE":

        return True, result["reason"]

    return False, result["reason"]


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("INTELLIGENT DUPLICATE DETECTOR TESTS")
    print("=" * 60)


    # ========================================================
    # EXISTING RECORD
    # ========================================================

    existing_lead = {
        "name": "John Smith",
        "email": "john.smith@gmail.com",
        "phone": "08031234567",
        "company": "ABC Furniture",
    }


    # ========================================================
    # TEST 1: SAME EMAIL
    # ========================================================

    new_lead = {
        "name": "Different Person",
        "email": "john.smith@gmail.com",
        "phone": "09099999999",
        "company": "XYZ Technologies",
    }

    print("\nTEST 1: SAME EMAIL")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    # ========================================================
    # TEST 2: SAME PHONE
    # ========================================================

    new_lead = {
        "name": "Different Person",
        "email": "different@gmail.com",
        "phone": "0803-123-4567",
        "company": "XYZ Technologies",
    }

    print("\nTEST 2: SAME PHONE")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    # ========================================================
    # TEST 3: SAME NAME + COMPANY
    # ========================================================

    new_lead = {
        "name": "  JOHN   SMITH  ",
        "email": "different@gmail.com",
        "phone": "09099999999",
        "company": "ABC Furniture",
    }

    print("\nTEST 3: SAME NAME + COMPANY")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    # ========================================================
    # TEST 4: FUZZY NAME MATCH
    # ========================================================

    new_lead = {
        "name": "Jon Smith",
        "email": "another@gmail.com",
        "phone": "09088888888",
        "company": "ABC Furniture",
    }

    print("\nTEST 4: FUZZY NAME MATCH")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    # ========================================================
    # TEST 5: FUZZY COMPANY MATCH
    # ========================================================

    new_lead = {
        "name": "John Smith",
        "email": "another@gmail.com",
        "phone": "09088888888",
        "company": "ABC Furniture Limited",
    }

    print("\nTEST 5: FUZZY COMPANY MATCH")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    # ========================================================
    # TEST 6: SAME NAME ONLY
    # ========================================================

    new_lead = {
        "name": "John Smith",
        "email": "another@gmail.com",
        "phone": "09088888888",
        "company": "XYZ Technologies",
    }

    print("\nTEST 6: SAME NAME ONLY")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    # ========================================================
    # TEST 7: DIFFERENT LEADS
    # ========================================================

    new_lead = {
        "name": "Michael Johnson",
        "email": "michael@gmail.com",
        "phone": "08111111111",
        "company": "Johnson Technologies",
    }

    print("\nTEST 7: DIFFERENT LEADS")

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)


    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)