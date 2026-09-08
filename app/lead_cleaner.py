def clean_name(name):
    """Clean and standardize a person's name."""
    return " ".join(name.strip().split()).title()


def clean_email(email):
    """Clean and standardize an email address."""
    return email.strip().lower()


def clean_phone(phone):
    """Remove spaces and common formatting characters from a phone number."""
    return (
        phone.strip()
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )


def clean_company(company):
    """Clean and standardize a company name."""
    return " ".join(company.strip().split()).title()


def clean_lead(lead):
    """Clean all relevant fields in a lead."""
    return {
        "name": clean_name(lead["name"]),
        "email": clean_email(lead["email"]),
        "phone": clean_phone(lead["phone"]),
        "company": clean_company(lead["company"]),
        "message": " ".join(lead["message"].strip().split()),
    }


if __name__ == "__main__":

    messy_lead = {
        "name": "  JOHN   SMITH  ",
        "email": " JOHN@ABC.COM ",
        "phone": "0803-123-4567",
        "company": "  ABC   FURNITURE LTD ",
        "message": "  I need 50 office chairs.  ",
    }

    cleaned_lead = clean_lead(messy_lead)

    print("===== ORIGINAL LEAD =====")
    print(messy_lead)

    print("\n===== CLEANED LEAD =====")
    print(cleaned_lead)