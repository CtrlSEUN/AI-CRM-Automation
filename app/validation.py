import re


# ========================================
# NAME VALIDATION
# ========================================

def validate_name(name):
    """Validate customer name."""

    name = name.strip()

    if not name:
        return False, "Name cannot be empty."

    if len(name) < 2:
        return False, "Name must contain at least 2 characters."

    # Allow letters, spaces, apostrophes, and hyphens
    if not re.fullmatch(
        r"[A-Za-zÀ-ÖØ-öø-ÿ' -]+",
        name
    ):
        return (
            False,
            "Name can only contain letters, spaces, apostrophes, or hyphens."
        )

    return True, ""


# ========================================
# EMAIL VALIDATION
# ========================================

def validate_email(email):
    """Validate customer email address."""

    email = email.strip().lower()

    if not email:
        return False, "Email cannot be empty."

    # Email cannot contain spaces
    if " " in email:
        return False, "Email cannot contain spaces."

    # Email must contain exactly one @ symbol
    if email.count("@") != 1:
        return (
            False,
            "Email must contain exactly one @ symbol."
        )

    local_part, domain = email.split("@")

    # Local part cannot be empty
    if not local_part:
        return (
            False,
            "Email username cannot be empty."
        )

    # Domain cannot be empty
    if not domain:
        return (
            False,
            "Email domain cannot be empty."
        )

    # Local part cannot start or end with a dot
    if local_part.startswith(".") or local_part.endswith("."):
        return (
            False,
            "Email username cannot start or end with a dot."
        )

    # Email cannot contain consecutive dots
    if ".." in email:
        return (
            False,
            "Email cannot contain consecutive dots."
        )

    # Domain must contain a dot
    if "." not in domain:
        return (
            False,
            "Email must contain a valid domain."
        )

    # Domain cannot start or end with a dot
    if domain.startswith(".") or domain.endswith("."):
        return (
            False,
            "Invalid email domain."
        )

    # Validate local part characters
    local_pattern = (
        r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    )

    if not re.fullmatch(
        local_pattern,
        local_part
    ):
        return (
            False,
            "Email contains invalid characters."
        )

    # Validate domain sections
    domain_parts = domain.split(".")

    for part in domain_parts:

        if not part:
            return (
                False,
                "Invalid email domain."
            )

        if part.startswith("-") or part.endswith("-"):
            return (
                False,
                "Invalid email domain."
            )

        if not re.fullmatch(
            r"[a-zA-Z0-9-]+",
            part
        ):
            return (
                False,
                "Invalid email domain."
            )

    # Validate email extension
    extension = domain_parts[-1]

    if len(extension) < 2:
        return (
            False,
            "Email domain extension is too short."
        )

    if not extension.isalpha():
        return (
            False,
            "Email domain extension must contain letters only."
        )

    return True, ""


# ========================================
# PHONE VALIDATION
# ========================================

def validate_phone(phone):
    """Validate Nigerian customer phone number."""

    phone = phone.strip()

    if not phone:
        return False, "Phone number cannot be empty."

    # Only digits are allowed
    if not phone.isdigit():
        return (
            False,
            "Phone number must contain digits only."
        )

    # Nigerian local phone numbers must contain
    # exactly 11 digits
    if len(phone) != 11:
        return (
            False,
            "Phone number must contain exactly 11 digits."
        )

    # Nigerian mobile number prefixes
    valid_prefixes = (
        "070",
        "071",
        "080",
        "081",
        "090",
        "091",
    )

    if not phone.startswith(valid_prefixes):
        return (
            False,
            "Invalid Nigerian phone number."
        )

    return True, ""


# ========================================
# COMPANY VALIDATION
# ========================================

def validate_company(company):
    """Validate company name."""

    company = company.strip()

    if not company:
        return False, "Company name cannot be empty."

    if len(company) < 2:
        return (
            False,
            "Company name is too short."
        )

    return True, ""


# ========================================
# MESSAGE VALIDATION
# ========================================

def validate_message(message):
    """Validate customer message."""

    message = message.strip()

    if not message:
        return (
            False,
            "Customer message cannot be empty."
        )

    if len(message) < 3:
        return (
            False,
            "Customer message is too short."
        )

    return True, ""


# ========================================
# QUANTITY VALIDATION
# ========================================

def validate_quantity(quantity):
    """Validate product quantity."""

    try:
        quantity = int(quantity)

    except (ValueError, TypeError):
        return (
            False,
            "Quantity must be a number."
        )

    if quantity <= 0:
        return (
            False,
            "Quantity must be greater than 0."
        )

    return True, ""


# ========================================
# PRIORITY VALIDATION
# ========================================

def validate_priority(priority):
    """Validate lead priority."""

    priority = priority.strip().upper()

    allowed_priorities = [
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    if priority not in allowed_priorities:
        return (
            False,
            "Priority must be LOW, MEDIUM, or HIGH."
        )

    return True, ""


# ========================================
# LEAD SCORE VALIDATION
# ========================================

def validate_lead_score(score):
    """Validate lead score."""

    try:
        score = int(score)

    except (ValueError, TypeError):
        return (
            False,
            "Lead score must be a number."
        )

    if score < 0 or score > 100:
        return (
            False,
            "Lead score must be between 0 and 100."
        )

    return True, ""