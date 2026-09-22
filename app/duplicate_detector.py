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


def normalize_company(value):
    """
    Normalize company names for duplicate comparison.

    Removes common business suffixes so that:

        ABC Furniture
        ABC Furniture Ltd
        ABC Furniture Limited

    can be treated as the same underlying company.
    """

    value = normalize_for_comparison(value)

    if not value:
        return ""

    suffixes = [
        "limited",
        "ltd",
        "llc",
        "incorporated",
        "inc",
        "corporation",
        "corp",
        "plc",
        "company",
        "co",
    ]

    for suffix in suffixes:

        if value.endswith(suffix):

            value = value[:-len(suffix)]

            break

    return value


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

    return round(
        ratio(value1, value2),
        2
    )


def company_similarity_score(company1, company2):
    """
    Calculate fuzzy similarity between two company names
    using company-specific normalization.
    """

    company1 = normalize_company(company1)
    company2 = normalize_company(company2)

    if not company1 or not company2:
        return 0

    return round(
        ratio(company1, company2),
        2
    )


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

        "company_score": company_similarity_score(
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
        Strong enough evidence to classify the record as a
        confirmed duplicate.

    MEDIUM:
        Evidence suggests the records may represent the same
        customer, but the system should not make the final
        decision automatically.

    LOW:
        Weak similarity.

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

        return (
            "HIGH",
            "Very strong email match"
        )

    if phone >= 98:

        return (
            "HIGH",
            "Very strong phone match"
        )

    # --------------------------------------------------------
    # STRONG NAME + COMPANY MATCH
    # --------------------------------------------------------

    if name >= 90 and company >= 90:

        return (
            "HIGH",
            "Strong name and company match"
        )

    # --------------------------------------------------------
    # MEDIUM CONFIDENCE
    # --------------------------------------------------------

    if name >= 85 and company >= 80:

        return (
            "MEDIUM",
            "Similar name and company"
        )

    if name >= 85 and email >= 85:

        return (
            "MEDIUM",
            "Similar name and email"
        )

    if name >= 85 and phone >= 85:

        return (
            "MEDIUM",
            "Similar name and phone"
        )

    if company >= 85 and email >= 85:

        return (
            "MEDIUM",
            "Similar company and email"
        )

    if company >= 85 and phone >= 85:

        return (
            "MEDIUM",
            "Similar company and phone"
        )

    # --------------------------------------------------------
    # SAME NAME ONLY
    #
    # A matching name by itself is NOT enough evidence.
    # --------------------------------------------------------

    if name >= 95:

        return (
            "UNIQUE",
            "Same or very similar name only - insufficient evidence"
        )

    # --------------------------------------------------------
    # WEAK SIMILARITY
    # --------------------------------------------------------

    if name >= 80 or company >= 85:

        return (
            "LOW",
            "Weak similarity - insufficient evidence"
        )

    # --------------------------------------------------------
    # NO SIGNIFICANT MATCH
    # --------------------------------------------------------

    return (
        "UNIQUE",
        "No significant duplicate evidence"
    )


# ============================================================
# REVIEW DECISION
# ============================================================

def get_duplicate_decision(confidence):
    """
    Convert duplicate confidence into a safe system decision.

    HIGH:
        Treat as duplicate.

    MEDIUM:
        Flag for human review.

    LOW / UNIQUE:
        Treat as unique.

    This function does NOT merge or delete records.
    """

    if confidence == "HIGH":

        return "DUPLICATE"

    if confidence == "MEDIUM":

        return "REVIEW"

    return "UNIQUE"


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def detect_duplicate(new_lead, existing_lead):
    """
    Compare two leads and determine whether they are:

    - DUPLICATE
    - REVIEW
    - UNIQUE

    Medium-confidence matches are explicitly routed to REVIEW
    instead of being treated as confirmed duplicates.
    """

    scores = compare_records(
        new_lead,
        existing_lead
    )

    confidence, reason = calculate_confidence(
        scores
    )

    decision = get_duplicate_decision(
        confidence
    )

    return {
        "status": decision,
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

    Both confirmed duplicates and review candidates return True
    so existing import logic can continue flagging them instead
    of automatically importing them as clean records.
    """

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    if result["status"] == "DUPLICATE":

        return True, result["reason"]

    if result["status"] == "REVIEW":

        return True, result["reason"]

    return False, result["reason"]


# ============================================================
# TESTING
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("DAY 32 - DUPLICATE REVIEW DETECTOR TESTS")
    print("=" * 60)

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

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

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

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

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

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

    # ========================================================
    # TEST 4: FUZZY NAME + COMPANY
    # ========================================================

    new_lead = {
        "name": "Jon Smith",
        "email": "another@gmail.com",
        "phone": "09088888888",
        "company": "ABC Furniture",
    }

    print("\nTEST 4: FUZZY NAME + COMPANY")

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

    # ========================================================
    # TEST 5: COMPANY SUFFIX
    # ========================================================

    new_lead = {
        "name": "John Smith",
        "email": "another@gmail.com",
        "phone": "09088888888",
        "company": "ABC Furniture Limited",
    }

    print("\nTEST 5: COMPANY SUFFIX")

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

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

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

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

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

    # ========================================================
    # TEST 8: DIFFERENT EMAIL + SAME NAME + COMPANY
    #
    # This should remain a strong duplicate signal.
    # ========================================================

    new_lead = {
        "name": "John Smith",
        "email": "johnsmith@gmail.com",
        "phone": "",
        "company": "ABC Furniture",
    }

    print(
        "\nTEST 8: DIFFERENT EMAIL + SAME NAME + COMPANY"
    )

    print(
        detect_duplicate(
            new_lead,
            existing_lead
        )
    )

    # ========================================================
    # TEST 9: MEDIUM-CONFIDENCE REVIEW
    #
    # Similar name + company, but not strong enough to
    # automatically classify as a confirmed duplicate.
    # ========================================================

    new_lead = {
        "name": "John Smyth",
        "email": "different@example.com",
        "phone": "09011111111",
        "company": "ABC Furnitures",
    }

    print(
        "\nTEST 9: MEDIUM-CONFIDENCE REVIEW"
    )

    result = detect_duplicate(
        new_lead,
        existing_lead
    )

    print(result)

    assert result["confidence"] == "MEDIUM"
    assert result["status"] == "REVIEW"

    print("MEDIUM-CONFIDENCE REVIEW TEST: PASSED")

    # ========================================================
    # FINAL
    # ========================================================

    print("\n" + "=" * 60)
    print("DAY 32 DUPLICATE REVIEW TESTS COMPLETE")
    print("=" * 60)