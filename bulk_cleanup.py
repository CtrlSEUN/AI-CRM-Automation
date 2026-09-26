import pandas as pd
import phonenumbers

from pathlib import Path
from datetime import datetime
from phonenumbers import NumberParseException

from app.validation import (
    validate_name,
    validate_email,
)

from app.duplicate_detector import (
    detect_duplicate,
)

from app.database import (
    import_clean_leads,
    get_connection,
)

from app.lead_analyzer import (
    analyze_and_save_lead,
)


# ========================================
# PROJECT PATHS
# ========================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"


# ========================================
# CREATE REQUIRED FOLDERS
# ========================================

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ========================================
# CLIENT / RUN MANAGEMENT
# ========================================

def sanitize_folder_name(value):
    """
    Convert a client or dataset name into a
    safe folder name.
    """

    value = str(value).strip()

    if not value:
        return "Unnamed"

    invalid_characters = '<>:"/\\|?*'

    for character in invalid_characters:
        value = value.replace(character, "_")

    value = " ".join(value.split())
    value = value.replace(" ", "_")

    return value[:100]


def get_client_information():
    """
    Collect client and dataset information
    before starting a cleanup run.
    """

    print("\n========================================")
    print("        CLIENT INFORMATION")
    print("========================================")

    while True:

        client_name = input(
            "\nClient name: "
        ).strip()

        if client_name:
            break

        print(
            "Client name cannot be empty."
        )

    while True:

        dataset_name = input(
            "Dataset name: "
        ).strip()

        if dataset_name:
            break

        print(
            "Dataset name cannot be empty."
        )

    return client_name, dataset_name


def create_run_directory(client_name):
    """
    Create a unique timestamped directory
    for the current cleanup run.
    """

    safe_client_name = sanitize_folder_name(
        client_name
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d_%H%M%S"
    )

    client_directory = (
        OUTPUT_DIR / safe_client_name
    )

    run_directory = (
        client_directory
        / f"cleanup_{timestamp}"
    )

    run_directory.mkdir(
        parents=True,
        exist_ok=False
    )

    return run_directory


# ========================================
# LOAD CSV FILE
# ========================================

def load_csv(file_name):
    """
    Load a CSV file from the input folder.
    """

    file_path = INPUT_DIR / file_name

    if not file_path.exists():

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    dataframe = pd.read_csv(
        file_path,
        dtype={"phone": str}
    )

    return dataframe


# ========================================
# DISPLAY DATASET INFORMATION
# ========================================

def show_dataset_info(dataframe):
    """
    Display basic information about the dataset.
    """

    print("\n========================================")
    print("        DATASET INFORMATION")
    print("========================================")

    print(
        f"Total records: {len(dataframe)}"
    )

    print(
        f"Total columns: {len(dataframe.columns)}"
    )

    print("\nColumns:")

    for column in dataframe.columns:

        print(f"- {column}")

    print("\nFirst 5 records:")

    print(dataframe.head())

    print("========================================")


# ========================================
# INSPECT DATASET
# ========================================

def inspect_dataset(dataframe):
    """
    Inspect the dataset for missing values,
    duplicate rows, and empty values.
    """

    print("\n========================================")
    print("        DATASET INSPECTION")
    print("========================================")

    print("\nMissing values:")

    missing_values = dataframe.isnull().sum()

    for column, count in missing_values.items():

        print(
            f"- {column}: {count}"
        )

    print("\nDuplicate records:")

    duplicate_count = dataframe.duplicated().sum()

    print(
        f"- Exact duplicate rows: "
        f"{duplicate_count}"
    )

    print("\nEmpty values:")

    for column in dataframe.columns:

        empty_count = (
            dataframe[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        print(
            f"- {column}: {empty_count}"
        )

    print("========================================")


# ========================================
# STANDARDIZE PHONE NUMBER
# ========================================

def standardize_phone(phone, country):
    """
    Convert a phone number into international
    E.164 format using the supplied country code.
    """

    if pd.isna(phone):
        return ""

    phone = str(phone).strip()

    if not phone:
        return ""

    country = str(country).strip().upper()

    try:

        parsed_number = phonenumbers.parse(
            phone,
            country
        )

        if not phonenumbers.is_valid_number(
            parsed_number
        ):

            return ""

        return phonenumbers.format_number(
            parsed_number,
            phonenumbers.PhoneNumberFormat.E164
        )

    except NumberParseException:

        return ""


# ========================================
# STANDARDIZE DATASET
# ========================================

def standardize_dataset(dataframe):
    """
    Standardize common CRM fields.
    """

    dataframe = dataframe.copy()

    # ------------------------------------
    # STANDARDIZE NAME
    # ------------------------------------

    if "name" in dataframe.columns:

        dataframe["name"] = (
            dataframe["name"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.replace(
                r"\s+",
                " ",
                regex=True
            )
            .str.title()
        )

    # ------------------------------------
    # STANDARDIZE EMAIL
    # ------------------------------------

    if "email" in dataframe.columns:

        dataframe["email"] = (
            dataframe["email"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

    # ------------------------------------
    # STANDARDIZE PHONE
    # ------------------------------------

    if (
        "phone" in dataframe.columns
        and "country" in dataframe.columns
    ):

        dataframe["phone_original"] = (
            dataframe["phone"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        dataframe["phone"] = dataframe.apply(
            lambda row: standardize_phone(
                row["phone"],
                row["country"]
            ),
            axis=1
        )

    # ------------------------------------
    # STANDARDIZE COMPANY
    # ------------------------------------

    if "company" in dataframe.columns:

        dataframe["company"] = (
            dataframe["company"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.replace(
                r"\s+",
                " ",
                regex=True
            )
        )

    # ------------------------------------
    # STANDARDIZE MESSAGE
    # ------------------------------------

    if "message" in dataframe.columns:

        dataframe["message"] = (
            dataframe["message"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.replace(
                r"\s+",
                " ",
                regex=True
            )
        )

    return dataframe


# ========================================
# VALIDATE DATASET
# ========================================

def validate_dataset(dataframe):
    """
    Validate important CRM fields and identify
    records that need attention.
    """

    dataframe = dataframe.copy()

    dataframe["validation_status"] = "CLEAN"
    dataframe["validation_issues"] = ""

    for index, row in dataframe.iterrows():

        issues = []

        # ------------------------------------
        # VALIDATE NAME
        # ------------------------------------

        name = row.get("name", "")

        if not name:

            issues.append(
                "Missing name"
            )

        else:

            try:

                name_result = validate_name(
                    name
                )

                if name_result is False:

                    issues.append(
                        "Invalid name"
                    )

            except Exception:

                issues.append(
                    "Invalid name"
                )

        # ------------------------------------
        # VALIDATE EMAIL
        # ------------------------------------

        email = row.get("email", "")

        if not email:

            issues.append(
                "Missing email"
            )

        else:

            try:

                email_result = validate_email(
                    email
                )

                if email_result is False:

                    issues.append(
                        "Invalid email"
                    )

            except Exception:

                issues.append(
                    "Invalid email"
                )

        # ------------------------------------
        # VALIDATE PHONE
        # ------------------------------------

        phone = row.get("phone", "")

        if not phone:

            issues.append(
                "Invalid phone"
            )

        # ------------------------------------
        # ASSIGN VALIDATION RESULT
        # ------------------------------------

        if issues:

            dataframe.at[
                index,
                "validation_status"
            ] = "REVIEW"

            dataframe.at[
                index,
                "validation_issues"
            ] = "; ".join(issues)

    return dataframe


# ========================================
# DISPLAY STANDARDIZED DATA
# ========================================

def show_standardized_data(dataframe):
    """
    Display the standardized dataset.
    """

    print("\n========================================")
    print("        STANDARDIZED DATA")
    print("========================================")

    print(
        dataframe.to_string(index=False)
    )

    print("========================================")


# ========================================
# DISPLAY VALIDATION RESULTS
# ========================================

def show_validation_results(dataframe):
    """
    Display validation results for every record.
    """

    print("\n========================================")
    print("        VALIDATION RESULTS")
    print("========================================")

    for index, row in dataframe.iterrows():

        print(
            f"\nRecord {index + 1}: "
            f"{row.get('name', '')}"
        )

        print(
            f"Status: "
            f"{row['validation_status']}"
        )

        if row["validation_issues"]:

            print(
                f"Issues: "
                f"{row['validation_issues']}"
            )

        else:

            print(
                "Issues: None"
            )

    print("\n========================================")


# ========================================
# INTELLIGENT DUPLICATE DETECTION
# ========================================

def detect_duplicates(dataframe):
    """
    Detect duplicate CRM records using fuzzy
    matching and confidence scoring.

    Decision model:

    HIGH confidence
        -> DUPLICATE

    MEDIUM confidence
        -> REVIEW

    LOW / no meaningful match
        -> UNIQUE

    Records are flagged, not deleted.

    Each record is compared against every other
    record in the dataset.

    The strongest meaningful match is kept.
    """

    dataframe = dataframe.copy()

    dataframe["duplicate_status"] = "UNIQUE"
    dataframe["duplicate_confidence"] = "UNIQUE"
    dataframe["duplicate_reason"] = ""
    dataframe["matched_record"] = ""

    dataframe["name_similarity"] = 0.0
    dataframe["company_similarity"] = 0.0
    dataframe["email_similarity"] = 0.0
    dataframe["phone_similarity"] = 0.0

    best_matches = {}

    for index, row in dataframe.iterrows():

        current_record = row.to_dict()

        best_match = None
        best_match_strength = -1

        for other_index, other_row in dataframe.iterrows():

            if index == other_index:
                continue

            other_record = other_row.to_dict()

            result = detect_duplicate(
                current_record,
                other_record
            )

            status = result["status"]
            confidence = result["confidence"]
            scores = result["scores"]

            # --------------------------------
            # DUPLICATE DECISION PRIORITY
            # --------------------------------

            if status == "DUPLICATE":

                priority = 3

            elif status == "REVIEW":

                priority = 2

            else:

                priority = 0

            if priority == 0:
                continue

            score_values = [
                scores["name_score"],
                scores["company_score"],
                scores["email_score"],
                scores["phone_score"],
            ]

            strongest_score = max(
                score_values
            )

            match_strength = (
                priority * 1000
                + strongest_score
            )

            if match_strength > best_match_strength:

                best_match_strength = (
                    match_strength
                )

                best_match = {
                    "index": other_index,
                    "status": status,
                    "confidence": confidence,
                    "reason": result["reason"],
                    "scores": scores,
                }

        best_matches[index] = best_match

    # ------------------------------------
    # APPLY BEST MATCHES
    # ------------------------------------

    for index, match in best_matches.items():

        if match is None:
            continue

        status = match["status"]

        if status in [
            "DUPLICATE",
            "REVIEW"
        ]:

            dataframe.at[
                index,
                "duplicate_status"
            ] = status

            dataframe.at[
                index,
                "duplicate_confidence"
            ] = match["confidence"]

            dataframe.at[
                index,
                "duplicate_reason"
            ] = match["reason"]

            dataframe.at[
                index,
                "matched_record"
            ] = (
                f"Record {match['index'] + 1}"
            )

            dataframe.at[
                index,
                "name_similarity"
            ] = match["scores"]["name_score"]

            dataframe.at[
                index,
                "company_similarity"
            ] = match["scores"]["company_score"]

            dataframe.at[
                index,
                "email_similarity"
            ] = match["scores"]["email_score"]

            dataframe.at[
                index,
                "phone_similarity"
            ] = match["scores"]["phone_score"]

    return dataframe


# ========================================
# DISPLAY DUPLICATE RESULTS
# ========================================

def show_duplicate_results(dataframe):
    """
    Display intelligent duplicate detection results.
    """

    print("\n========================================")
    print("   INTELLIGENT DUPLICATE DETECTION")
    print("========================================")

    for index, row in dataframe.iterrows():

        status = row["duplicate_status"]

        if status == "DUPLICATE":

            display_status = "CONFIRMED DUPLICATE"

        elif status == "REVIEW":

            display_status = "REVIEW REQUIRED"

        else:

            display_status = "UNIQUE"

        print(
            f"\nRecord {index + 1}: "
            f"{row.get('name', '')}"
        )

        print(
            f"Email: "
            f"{row.get('email', '')}"
        )

        print(
            f"Phone: "
            f"{row.get('phone', '')}"
        )

        print(
            f"Status: "
            f"{display_status}"
        )

        print(
            f"Confidence: "
            f"{row['duplicate_confidence']}"
        )

        print(
            f"Reason: "
            f"{row['duplicate_reason'] or 'None'}"
        )

        print(
            f"Matched record: "
            f"{row['matched_record'] or 'None'}"
        )

        if status != "UNIQUE":

            print(
                f"Name similarity: "
                f"{row['name_similarity']:.2f}%"
            )

            print(
                f"Company similarity: "
                f"{row['company_similarity']:.2f}%"
            )

            print(
                f"Email similarity: "
                f"{row['email_similarity']:.2f}%"
            )

            print(
                f"Phone similarity: "
                f"{row['phone_similarity']:.2f}%"
            )

    print("\n========================================")


# ========================================
# CALCULATE DUPLICATE GROUPS
# ========================================

def calculate_duplicate_groups(dataframe):
    """
    Calculate actual confirmed duplicate groups.

    Only DUPLICATE records are included.

    REVIEW records are intentionally excluded because
    they require human confirmation first.
    """

    duplicate_rows = dataframe[
        dataframe["duplicate_status"] == "DUPLICATE"
    ]

    if duplicate_rows.empty:

        return 0

    parent = {}

    def find(value):

        if parent[value] != value:

            parent[value] = find(
                parent[value]
            )

        return parent[value]

    def union(first, second):

        first_root = find(first)
        second_root = find(second)

        if first_root != second_root:

            parent[second_root] = first_root

    # ------------------------------------
    # INITIALIZE DUPLICATE RECORDS
    # ------------------------------------

    for index in duplicate_rows.index:

        parent[index] = index

    # ------------------------------------
    # CONNECT MATCHED RECORDS
    # ------------------------------------

    for index, row in duplicate_rows.iterrows():

        matched_record = str(
            row.get(
                "matched_record",
                ""
            )
        ).strip()

        if not matched_record:
            continue

        if not matched_record.startswith(
            "Record "
        ):
            continue

        try:

            matched_number = int(
                matched_record.replace(
                    "Record ",
                    ""
                )
            )

            matched_index = (
                matched_number - 1
            )

            if matched_index in parent:

                union(
                    index,
                    matched_index
                )

        except ValueError:

            continue

    # ------------------------------------
    # COUNT CONNECTED GROUPS
    # ------------------------------------

    groups = set()

    for index in parent:

        groups.add(
            find(index)
        )

    return len(groups)


# ========================================
# CALCULATE DATA QUALITY METRICS
# ========================================

def calculate_quality_metrics(dataframe):
    """
    Calculate business-level data quality statistics.

    review_records:
        Validation issues only.

    possible_duplicate_records:
        REVIEW duplicate matches requiring
        human review.

    The key name possible_duplicate_records is
    retained for backward compatibility with
    existing reports and integrations.
    """

    total_records = len(dataframe)

    if total_records == 0:

        return {
            "total_records": 0,
            "clean_records": 0,
            "review_records": 0,
            "duplicate_records": 0,
            "possible_duplicate_records": 0,
            "unique_records": 0,
            "missing_name": 0,
            "missing_email": 0,
            "invalid_email": 0,
            "invalid_phone": 0,
            "missing_phone": 0,
            "validation_issue_records": 0,
            "duplicate_review_records": 0,
            "duplicate_groups": 0,
            "data_quality_score": 0.0,
        }

    # ------------------------------------
    # VALIDATION REVIEW
    # ------------------------------------

    review_records = int(
        (
            dataframe["validation_status"]
            == "REVIEW"
        ).sum()
    )

    # ------------------------------------
    # CONFIRMED DUPLICATES
    # ------------------------------------

    duplicate_records = int(
        (
            dataframe["duplicate_status"]
            == "DUPLICATE"
        ).sum()
    )

    # ------------------------------------
    # DUPLICATES REQUIRING REVIEW
    # ------------------------------------

    possible_duplicate_records = int(
        (
            dataframe["duplicate_status"]
            == "REVIEW"
        ).sum()
    )

    # ------------------------------------
    # UNIQUE RECORDS
    # ------------------------------------

    unique_records = int(
        (
            dataframe["duplicate_status"]
            == "UNIQUE"
        ).sum()
    )

    # ------------------------------------
    # CLEAN RECORDS
    # ------------------------------------

    clean_records = int(
        (
            (dataframe["validation_status"] == "CLEAN")
            &
            (dataframe["duplicate_status"] == "UNIQUE")
        ).sum()
    )

    # ------------------------------------
    # VALIDATION ISSUES
    # ------------------------------------

    issues = (
        dataframe["validation_issues"]
        .fillna("")
        .astype(str)
    )

    missing_name = int(
        issues.str.contains(
            "Missing name",
            regex=False
        ).sum()
    )

    missing_email = int(
        issues.str.contains(
            "Missing email",
            regex=False
        ).sum()
    )

    invalid_email = int(
        issues.str.contains(
            "Invalid email",
            regex=False
        ).sum()
    )

    invalid_phone = int(
        issues.str.contains(
            "Invalid phone",
            regex=False
        ).sum()
    )

    missing_phone = int(
        (
            dataframe["phone"]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
        ).sum()
    )

    # ------------------------------------
    # DUPLICATE GROUPS
    # ------------------------------------

    duplicate_groups = calculate_duplicate_groups(
        dataframe
    )

    # ------------------------------------
    # OVERALL CLEAN DATA SCORE
    # ------------------------------------

    data_quality_score = (
        clean_records / total_records
    ) * 100

    return {
        "total_records": total_records,
        "clean_records": clean_records,
        "review_records": review_records,
        "duplicate_records": duplicate_records,

        "possible_duplicate_records":
            possible_duplicate_records,

        "unique_records": unique_records,
        "missing_name": missing_name,
        "missing_email": missing_email,
        "invalid_email": invalid_email,
        "invalid_phone": invalid_phone,
        "missing_phone": missing_phone,

        "validation_issue_records":
            review_records,

        "duplicate_review_records":
            possible_duplicate_records,

        "duplicate_groups":
            duplicate_groups,

        "data_quality_score": round(
            data_quality_score,
            2
        ),
    }


# ========================================
# CALCULATE DATA QUALITY HEALTH
# ========================================

def calculate_quality_health(dataframe):
    """
    Calculate a multidimensional CRM data quality
    health score.

    Scoring:
    - Validity: 40%
    - Uniqueness: 35%
    - Completeness: 25%

    REVIEW duplicate records are not treated as
    confirmed duplicates in the uniqueness score.
    """

    total_records = len(dataframe)

    if total_records == 0:

        return {
            "validity_score": 0.0,
            "uniqueness_score": 0.0,
            "completeness_score": 0.0,
            "overall_health_score": 0.0,
            "health_status": "NO DATA",
        }

    # ====================================
    # VALIDITY SCORE
    # ====================================

    valid_records = int(
        (
            dataframe["validation_status"]
            == "CLEAN"
        ).sum()
    )

    validity_score = (
        valid_records / total_records
    ) * 100

    # ====================================
    # UNIQUENESS SCORE
    # ====================================

    confirmed_duplicates = int(
        (
            dataframe["duplicate_status"]
            == "DUPLICATE"
        ).sum()
    )

    review_duplicates = int(
        (
            dataframe["duplicate_status"]
            == "REVIEW"
        ).sum()
    )

    records_without_confirmed_duplicate = (
        total_records - confirmed_duplicates
    )

    uniqueness_score = (
        records_without_confirmed_duplicate
        / total_records
    ) * 100

    # ====================================
    # COMPLETENESS SCORE
    # ====================================

    important_fields = [
        "name",
        "email",
        "phone",
    ]

    field_scores = []

    for field in important_fields:

        if field in dataframe.columns:

            populated = (
                dataframe[field]
                .fillna("")
                .astype(str)
                .str.strip()
            )

            populated_count = int(
                (populated != "").sum()
            )

            field_score = (
                populated_count
                / total_records
            ) * 100

            field_scores.append(
                field_score
            )

    if field_scores:

        completeness_score = (
            sum(field_scores)
            / len(field_scores)
        )

    else:

        completeness_score = 0.0

    # ====================================
    # OVERALL HEALTH SCORE
    # ====================================

    overall_health_score = (
        (validity_score * 0.40)
        +
        (uniqueness_score * 0.35)
        +
        (completeness_score * 0.25)
    )

    # ====================================
    # HEALTH STATUS
    # ====================================

    if overall_health_score >= 90:

        health_status = "EXCELLENT"

    elif overall_health_score >= 75:

        health_status = "GOOD"

    elif overall_health_score >= 60:

        health_status = "FAIR"

    else:

        health_status = "NEEDS IMPROVEMENT"

    return {
        "validity_score": round(
            validity_score,
            2
        ),
        "uniqueness_score": round(
            uniqueness_score,
            2
        ),
        "completeness_score": round(
            completeness_score,
            2
        ),
        "overall_health_score": round(
            overall_health_score,
            2
        ),
        "health_status": health_status,

        "confirmed_duplicate_records":
            confirmed_duplicates,

        "duplicate_review_records":
            review_duplicates,
    }


# ========================================
# DISPLAY QUALITY SUMMARY
# ========================================

def show_quality_summary(dataframe):
    """
    Display a business-friendly quality summary.
    """

    metrics = calculate_quality_metrics(
        dataframe
    )

    health = calculate_quality_health(
        dataframe
    )

    print("\n========================================")
    print("       DATA QUALITY SUMMARY")
    print("========================================")

    print(
        f"\nTotal records: "
        f"{metrics['total_records']}"
    )

    print(
        f"Clean records: "
        f"{metrics['clean_records']}"
    )

    print(
        f"Records needing validation review: "
        f"{metrics['review_records']}"
    )

    print(
        f"Confirmed duplicates: "
        f"{metrics['duplicate_records']}"
    )

    print(
        f"Duplicates requiring manual review: "
        f"{metrics['possible_duplicate_records']}"
    )

    print(
        f"Unique records: "
        f"{metrics['unique_records']}"
    )

    print("\nIssues detected:")

    print(
        f"- Missing names: "
        f"{metrics['missing_name']}"
    )

    print(
        f"- Missing emails: "
        f"{metrics['missing_email']}"
    )

    print(
        f"- Invalid emails: "
        f"{metrics['invalid_email']}"
    )

    print(
        f"- Invalid phones: "
        f"{metrics['invalid_phone']}"
    )

    print(
        f"- Missing phones: "
        f"{metrics['missing_phone']}"
    )

    print(
        f"- Confirmed duplicate groups: "
        f"{metrics['duplicate_groups']}"
    )

    print("\n========================================")
    print("       DATA QUALITY HEALTH")
    print("========================================")

    print(
        f"\nOverall Health Score: "
        f"{health['overall_health_score']:.2f}%"
    )

    print(
        f"Validity:             "
        f"{health['validity_score']:.2f}%"
    )

    print(
        f"Uniqueness:           "
        f"{health['uniqueness_score']:.2f}%"
    )

    print(
        f"Completeness:         "
        f"{health['completeness_score']:.2f}%"
    )

    print(
        f"Status:               "
        f"{health['health_status']}"
    )

    print("\n========================================")


# ========================================
# GENERATE BUSINESS RECOMMENDATIONS
# ========================================

def generate_recommendations(metrics):
    """
    Generate recommendations based on
    detected data-quality problems.
    """

    recommendations = []

    if metrics["review_records"] > 0:

        recommendations.append(
            f"Review {metrics['review_records']} "
            f"record(s) with validation issues."
        )

    if metrics["duplicate_records"] > 0:

        recommendations.append(
            f"Review {metrics['duplicate_records']} "
            f"confirmed duplicate record(s) "
            f"before merging or deleting."
        )

    if metrics["possible_duplicate_records"] > 0:

        recommendations.append(
            f"Manually review "
            f"{metrics['possible_duplicate_records']} "
            f"possible duplicate record(s) before import."
        )

    if metrics["missing_name"] > 0:

        recommendations.append(
            "Complete missing customer names "
            "before importing the data into a CRM."
        )

    if metrics["missing_email"] > 0:

        recommendations.append(
            "Complete missing email addresses "
            "where possible before outreach."
        )

    if metrics["invalid_email"] > 0:

        recommendations.append(
            "Correct invalid email addresses "
            "before using the dataset for outreach."
        )

    if metrics["invalid_phone"] > 0:

        recommendations.append(
            "Correct or verify invalid phone "
            "numbers before contacting customers."
        )

    if metrics["missing_phone"] > 0:

        recommendations.append(
            "Complete missing phone numbers "
            "where possible."
        )

    if not recommendations:

        recommendations.append(
            "No major data-quality issues were detected."
        )

    return recommendations


# ========================================
# GENERATE CLIENT DELIVERY SUMMARY
# ========================================

def generate_client_delivery_summary(
    client_name,
    dataset_name,
    source_file,
    run_directory,
    metrics,
    health
):
    """
    Generate a simple client-facing summary
    of the completed CRM cleanup.
    """

    summary_file = (
        run_directory
        / "client_delivery_summary.txt"
    )

    run_time = datetime.now().strftime(
        "%B %d, %Y at %H:%M:%S"
    )

    summary = f"""
============================================================
                 CRM CLEANUP SUMMARY
============================================================

CLIENT INFORMATION
------------------------------------------------------------

Client:
{client_name}

Dataset:
{dataset_name}

Source File:
{source_file}

Cleanup Date:
{run_time}


CLEANUP RESULTS
------------------------------------------------------------

Records Processed:
{metrics['total_records']}

Clean Records:
{metrics['clean_records']}

Records Requiring Validation Review:
{metrics['review_records']}

Confirmed Duplicate Records:
{metrics['duplicate_records']}

Records Requiring Duplicate Review:
{metrics['possible_duplicate_records']}

Unique Records:
{metrics['unique_records']}


DATA QUALITY HEALTH
------------------------------------------------------------

Overall Health Score:
{health['overall_health_score']:.2f}%

Health Status:
{health['health_status']}

Validity:
{health['validity_score']:.2f}%

Uniqueness:
{health['uniqueness_score']:.2f}%

Completeness:
{health['completeness_score']:.2f}%


KEY ISSUES IDENTIFIED
------------------------------------------------------------

Missing Names:
{metrics['missing_name']}

Missing Emails:
{metrics['missing_email']}

Invalid Emails:
{metrics['invalid_email']}

Invalid Phones:
{metrics['invalid_phone']}

Missing Phones:
{metrics['missing_phone']}

Confirmed Duplicate Groups:
{metrics['duplicate_groups']}


DELIVERABLES
------------------------------------------------------------

The following files were generated as part of this
CRM data cleanup:

1. cleaned_leads.csv
   Clean records ready for further CRM use.

2. review_leads.csv
   Records requiring validation or data correction.

3. duplicate_leads.csv
   Records identified as confirmed duplicates.

4. possible_duplicate_leads.csv
   Records requiring human review because they may
   represent duplicate customers.

5. cleanup_report.txt
   Detailed technical and business data-quality report.

6. client_delivery_summary.txt
   This client-facing summary.


RECOMMENDED NEXT STEPS
------------------------------------------------------------

"""

    if metrics["review_records"] > 0:

        summary += (
            f"- Review the {metrics['review_records']} "
            f"record(s) requiring validation attention.\n"
        )

    if metrics["duplicate_records"] > 0:

        summary += (
            f"- Review the {metrics['duplicate_records']} "
            f"confirmed duplicate record(s) before "
            f"merging or deleting.\n"
        )

    if metrics["possible_duplicate_records"] > 0:

        summary += (
            f"- Manually verify the "
            f"{metrics['possible_duplicate_records']} "
            f"record(s) marked REVIEW REQUIRED for "
            f"possible duplication before import.\n"
        )

    if metrics["missing_name"] > 0:

        summary += (
            f"- Complete {metrics['missing_name']} "
            f"missing customer name(s).\n"
        )

    if metrics["invalid_phone"] > 0:

        summary += (
            f"- Correct or verify "
            f"{metrics['invalid_phone']} "
            f"invalid phone number(s).\n"
        )

    if metrics["missing_phone"] > 0:

        summary += (
            f"- Complete {metrics['missing_phone']} "
            f"missing phone number(s) where possible.\n"
        )

    if (
        metrics["review_records"] == 0
        and metrics["duplicate_records"] == 0
        and metrics["possible_duplicate_records"] == 0
        and metrics["missing_name"] == 0
        and metrics["invalid_phone"] == 0
        and metrics["missing_phone"] == 0
    ):

        summary += (
            "- No major data-quality issues were detected.\n"
        )

    summary += f"""

DELIVERY LOCATION
------------------------------------------------------------

{run_directory}


IMPORTANT
------------------------------------------------------------

This cleanup system identifies and flags potentially
problematic records.

It does NOT automatically delete, merge, or overwrite
customer records.

Human review is recommended before making destructive
changes to CRM data.


============================================================
              CRM CLEANUP COMPLETED
============================================================
"""

    with open(
        summary_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(summary)

    return summary_file


# ========================================
# IMPORT CLEAN RECORDS INTO SQLITE
# ========================================

def import_clean_records_to_database(
    dataframe,
    client_name,
    dataset_name,
    source_file,
    batch_key
):
    """
    Import CLEAN + UNIQUE records into the
    CRM SQLite database.

    Only records that are:

    - validation_status == CLEAN
    - duplicate_status == UNIQUE

    are eligible for import.

    REVIEW and DUPLICATE records are never
    automatically imported.
    """

    clean_records = dataframe[
        (dataframe["validation_status"] == "CLEAN")
        &
        (dataframe["duplicate_status"] == "UNIQUE")
    ].copy()

    print("\n========================================")
    print("        CRM DATABASE IMPORT")
    print("========================================")

    print(
        f"\nClean + Unique records ready for import: "
        f"{len(clean_records)}"
    )

    print(
        f"Batch Key: "
        f"{batch_key}"
    )

    if clean_records.empty:

        print(
            "\nNo CLEAN + UNIQUE records found."
        )

        return {
            "imported": 0,
            "skipped": 0,
            "already_imported": False,
            "batch_id": None,
            "review_required": 0,
        }

    result = import_clean_leads(
        clean_records,
        batch_key=batch_key,
        client_name=client_name,
        dataset_name=dataset_name,
        source_file=source_file
    )

    if result.get("already_imported"):

        print(
            "\nWARNING: This batch has already "
            "been imported."
        )

        print(
            f"Batch ID: "
            f"{result['batch_id']}"
        )

        print(
            f"Records skipped: "
            f"{result['skipped']}"
        )

    else:

        print(
            f"\nSuccessfully imported: "
            f"{result['imported']}"
        )

        print(
            f"Skipped: "
            f"{result['skipped']}"
        )

        print(
            f"Batch ID: "
            f"{result['batch_id']}"
        )

        if result.get("review_required", 0):

            print(
                f"Manual duplicate reviews: "
                f"{result['review_required']}"
            )

    print("\n========================================")

    return result


# ========================================
# BULK AI LEAD ANALYSIS
# ========================================

def analyze_imported_leads(
    batch_id,
    client_name,
    dataset_name
):
    """
    Run AI analysis on all leads imported by
    the current cleanup batch.

    AI failures do not delete, rollback, or
    modify the imported lead.

    Each lead is analyzed independently so that
    one failed AI request does not stop the
    remaining leads from being processed.
    """

    print("\n========================================")
    print("        BULK AI LEAD ANALYSIS")
    print("========================================")

    if not batch_id:

        print(
            "\nNo batch ID available."
        )

        return {
            "total": 0,
            "analyzed": 0,
            "failed": 0,
        }

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                id,
                name,
                email,
                phone,
                company,
                message,
                status
            FROM leads
            WHERE import_batch_id = ?
            ORDER BY id
            """,
            (batch_id,)
        )

        imported_leads = cursor.fetchall()

    finally:

        conn.close()

    total = len(imported_leads)

    analyzed = 0
    failed = 0

    print(
        f"\nLeads imported in this batch: "
        f"{total}"
    )

    if total == 0:

        print(
            "\nNo newly imported leads require AI analysis."
        )

        return {
            "total": 0,
            "analyzed": 0,
            "failed": 0,
        }

    for position, lead in enumerate(
        imported_leads,
        start=1
    ):

        lead_id = lead[0]

        lead_data = {
            "name": lead[1],
            "email": lead[2],
            "phone": lead[3],
            "company": lead[4],
            "message": lead[5],
            "status": lead[6],
        }

        print("\n----------------------------------------")

        print(
            f"AI Analysis {position}/{total}"
        )

        print(
            f"Lead ID: {lead_id}"
        )

        print(
            f"Name: {lead_data['name']}"
        )

        print(
            f"Company: {lead_data['company']}"
        )

        try:

            analyze_and_save_lead(
                lead_id,
                lead_data
            )

            analyzed += 1

            print(
                "\nAI analysis saved successfully."
            )

        except Exception as error:

            failed += 1

            print(
                "\nAI analysis failed."
            )

            print(
                f"Lead ID: {lead_id}"
            )

            print(
                f"Error: {error}"
            )

            print(
                "Lead remains safely stored in the CRM."
            )

    print("\n========================================")
    print("        BULK AI ANALYSIS RESULT")
    print("========================================")

    print(
        f"\nClient: {client_name}"
    )

    print(
        f"Dataset: {dataset_name}"
    )

    print(
        f"Total imported leads: {total}"
    )

    print(
        f"Successfully analyzed: {analyzed}"
    )

    print(
        f"AI analysis failed: {failed}"
    )

    if failed > 0:

        print(
            "\nSome AI analyses failed."
        )

        print(
            "The affected leads remain safely stored "
            "in the CRM and can be analyzed again later."
        )

    else:

        print(
            "\nAll imported leads were analyzed successfully."
        )

    print("\n========================================")

    return {
        "total": total,
        "analyzed": analyzed,
        "failed": failed,
    }


# ========================================
# EXPORT RESULTS
# ========================================

def export_results(
    dataframe,
    client_name,
    dataset_name,
    run_directory,
    source_file
):
    """
    Export all cleanup results into the
    client-specific run directory.

    Import CLEAN + UNIQUE records into SQLite,
    then run AI analysis against the newly
    imported leads.
    """

    # ------------------------------------
    # CLEAN RECORDS
    # ------------------------------------

    clean_records = dataframe[
        (dataframe["validation_status"] == "CLEAN")
        &
        (dataframe["duplicate_status"] == "UNIQUE")
    ].copy()

    # ------------------------------------
    # RECORDS NEEDING VALIDATION REVIEW
    # ------------------------------------

    review_records = dataframe[
        dataframe["validation_status"]
        == "REVIEW"
    ].copy()

    # ------------------------------------
    # CONFIRMED DUPLICATES
    # ------------------------------------

    duplicate_records = dataframe[
        dataframe["duplicate_status"]
        == "DUPLICATE"
    ].copy()

    # ------------------------------------
    # RECORDS REQUIRING DUPLICATE REVIEW
    # ------------------------------------

    possible_duplicate_records = dataframe[
        dataframe["duplicate_status"]
        == "REVIEW"
    ].copy()

    # ------------------------------------
    # FILE PATHS
    # ------------------------------------

    cleaned_file = (
        run_directory / "cleaned_leads.csv"
    )

    review_file = (
        run_directory / "review_leads.csv"
    )

    duplicate_file = (
        run_directory / "duplicate_leads.csv"
    )

    possible_duplicate_file = (
        run_directory
        / "possible_duplicate_leads.csv"
    )

    report_file = (
        run_directory / "cleanup_report.txt"
    )

    # ------------------------------------
    # EXPORT CSV FILES
    # ------------------------------------

    clean_records.to_csv(
        cleaned_file,
        index=False
    )

    review_records.to_csv(
        review_file,
        index=False
    )

    duplicate_records.to_csv(
        duplicate_file,
        index=False
    )

    possible_duplicate_records.to_csv(
        possible_duplicate_file,
        index=False
    )

    # ------------------------------------
    # CALCULATE METRICS
    # ------------------------------------

    metrics = calculate_quality_metrics(
        dataframe
    )

    health = calculate_quality_health(
        dataframe
    )

    recommendations = generate_recommendations(
        metrics
    )

    # ------------------------------------
    # CLIENT DELIVERY SUMMARY
    # ------------------------------------

    summary_file = generate_client_delivery_summary(
        client_name,
        dataset_name,
        source_file,
        run_directory,
        metrics,
        health
    )

    # ------------------------------------
    # RUN INFORMATION
    # ------------------------------------

    run_time = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # ------------------------------------
    # RECOMMENDATION TEXT
    # ------------------------------------

    recommendation_text = "\n".join(
        [
            f"{number}. {recommendation}"
            for number, recommendation
            in enumerate(
                recommendations,
                start=1
            )
        ]
    )

    # ------------------------------------
    # PROFESSIONAL CLIENT REPORT
    # ------------------------------------

    report = f"""
============================================================
                 CRM DATA QUALITY REPORT
============================================================

CLIENT INFORMATION
------------------------------------------------------------

Client Name:
{client_name}

Dataset Name:
{dataset_name}

Source File:
{source_file}

Cleanup Run:
{run_time}

Delivery Directory:
{run_directory}


EXECUTIVE SUMMARY
------------------------------------------------------------

This report summarizes the results of the CRM data quality
analysis performed on the submitted dataset.

The dataset was inspected, standardized, validated, and
analyzed for confirmed duplicates and records requiring
manual duplicate review.

Overall Data Quality Health:
{health['overall_health_score']:.2f}%

Health Status:
{health['health_status']}


DATASET OVERVIEW
------------------------------------------------------------

Total Records Processed:
{metrics['total_records']}

Clean Records:
{metrics['clean_records']}

Records Requiring Validation Review:
{metrics['review_records']}

Confirmed Duplicate Records:
{metrics['duplicate_records']}

Records Requiring Duplicate Review:
{metrics['possible_duplicate_records']}

Unique Records:
{metrics['unique_records']}


DATA QUALITY HEALTH
------------------------------------------------------------

Overall Health Score:
{health['overall_health_score']:.2f}%

Validity:
{health['validity_score']:.2f}%

Uniqueness:
{health['uniqueness_score']:.2f}%

Completeness:
{health['completeness_score']:.2f}%


HEALTH SCORE METHODOLOGY
------------------------------------------------------------

Validity:
Measures how many records pass the validation stage.

Weight:
40%

Uniqueness:
Measures the absence of confirmed duplicate records.

Weight:
35%

Completeness:
Measures whether important CRM fields contain usable
values.

Important fields:
- Name
- Email
- Phone

Weight:
25%


ISSUES IDENTIFIED
------------------------------------------------------------

Records With Validation Issues:
{metrics['validation_issue_records']}

Missing Names:
{metrics['missing_name']}

Missing Emails:
{metrics['missing_email']}

Invalid Emails:
{metrics['invalid_email']}

Invalid Phones:
{metrics['invalid_phone']}

Missing Phones:
{metrics['missing_phone']}


DUPLICATE ANALYSIS
------------------------------------------------------------

Confirmed Duplicate Records:
{metrics['duplicate_records']}

Confirmed Duplicate Groups:
{metrics['duplicate_groups']}

Records Requiring Duplicate Review:
{metrics['possible_duplicate_records']}

Unique Records:
{metrics['unique_records']}

The duplicate detection system uses multiple CRM fields
including name, company, email, and phone.

Confirmed duplicates are identified using strong matching
evidence.

Medium-confidence matches are classified as REVIEW and
flagged for human review rather than being automatically
merged or deleted.


CLEANUP ACTIONS PERFORMED
------------------------------------------------------------

[OK] CSV dataset loaded
[OK] Dataset inspected
[OK] Missing values detected
[OK] Empty values detected
[OK] Data standardized
[OK] Phone numbers normalized to international format
[OK] Records validated
[OK] Intelligent duplicate detection completed
[OK] Similarity scoring completed
[OK] Confidence scoring completed
[OK] Data quality metrics calculated
[OK] Data quality health calculated
[OK] Results exported
[OK] Client delivery summary generated
[OK] CLEAN + UNIQUE records imported into CRM
[OK] Imported leads prepared for AI analysis


RECOMMENDED ACTIONS
------------------------------------------------------------

{recommendation_text}


DELIVERED FILES
------------------------------------------------------------

1. cleaned_leads.csv
   Contains records that passed validation and were not
   identified as duplicates or manual-review records.

2. review_leads.csv
   Contains records requiring validation review.

3. duplicate_leads.csv
   Contains records identified as confirmed duplicates.

4. possible_duplicate_leads.csv
   Contains records classified as REVIEW because they may
   represent duplicate customers and require human review.

5. cleanup_report.txt
   Contains this data quality analysis report.

6. client_delivery_summary.txt
   Contains a concise client-facing summary of the cleanup
   results, data quality health, key issues, and recommended
   next steps.


DUPLICATE SAFETY
------------------------------------------------------------

The system is designed to identify and flag suspicious
records rather than automatically performing destructive
actions.

The system does NOT automatically:

- Delete records
- Merge records
- Overwrite customer information
- Remove potentially valuable CRM data

Human review is recommended before merging, deleting,
or modifying CRM records.


TECHNICAL METHODOLOGY
------------------------------------------------------------

The CRM cleanup pipeline performs the following stages:

1. CSV ingestion
2. Dataset inspection
3. Missing-value detection
4. Data standardization
5. Phone number normalization
6. Field validation
7. Intelligent duplicate detection
8. Fuzzy similarity analysis
9. Duplicate confidence scoring
10. Data quality health scoring
11. Record classification
12. CSV export
13. Business report generation
14. Client delivery summary generation
15. Safe SQLite import of CLEAN + UNIQUE records
16. AI lead analysis of newly imported CRM records


RECORD CLASSIFICATION
------------------------------------------------------------

CLEAN:
The record passed validation and was not identified as
a duplicate.

REVIEW:
The record contains validation issues OR a medium-confidence
duplicate match requiring human attention.

DUPLICATE:
The system found strong evidence that the record is
a duplicate of another record.

UNIQUE:
The record was not identified as a duplicate.

NOTE:
A duplicate record classified as REVIEW is exported
separately and is NOT automatically imported into the
CRM database.


QUALITY STATUS SCALE
------------------------------------------------------------

90% - 100%:
EXCELLENT

75% - 89.99%:
GOOD

60% - 74.99%:
FAIR

Below 60%:
NEEDS IMPROVEMENT


REPORT CONCLUSION
------------------------------------------------------------

CRM cleanup analysis completed successfully.

The resulting files separate clean records from records
requiring attention, allowing the dataset owner to review
and improve data quality before using the information for
CRM operations, sales outreach, reporting, or automation.


============================================================
                  END OF REPORT
============================================================
"""

    # ------------------------------------
    # WRITE REPORT
    # ------------------------------------

    with open(
        report_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(report)

    # ------------------------------------
    # CREATE BATCH KEY
    # ------------------------------------

    batch_key = run_directory.name

    # ------------------------------------
    # IMPORT CLEAN RECORDS INTO SQLITE
    # ------------------------------------

    database_result = (
        import_clean_records_to_database(
            dataframe,
            client_name,
            dataset_name,
            source_file,
            batch_key
        )
    )

    # ------------------------------------
    # BULK AI ANALYSIS
    # ------------------------------------

    ai_result = {
        "total": 0,
        "analyzed": 0,
        "failed": 0,
    }

    if (
        not database_result.get("already_imported")
        and database_result.get("batch_id")
        and database_result.get("imported", 0) > 0
    ):

        ai_result = analyze_imported_leads(
            database_result["batch_id"],
            client_name,
            dataset_name
        )

    elif database_result.get("already_imported"):

        print(
            "\nAI analysis skipped because "
            "this batch was already imported."
        )

    else:

        print(
            "\nAI analysis skipped because "
            "no new CRM leads were imported."
        )

    # ------------------------------------
    # DISPLAY EXPORT RESULTS
    # ------------------------------------

    print("\n========================================")
    print("        EXPORT COMPLETED")
    print("========================================")

    print(
        f"\nClient: "
        f"{client_name}"
    )

    print(
        f"Dataset: "
        f"{dataset_name}"
    )

    print(
        f"Clean records exported: "
        f"{metrics['clean_records']}"
    )

    print(
        f"Validation review records exported: "
        f"{metrics['review_records']}"
    )

    print(
        f"Confirmed duplicates exported: "
        f"{metrics['duplicate_records']}"
    )

    print(
        f"Duplicate review records exported: "
        f"{metrics['possible_duplicate_records']}"
    )

    print(
        f"\nOverall Health Score: "
        f"{health['overall_health_score']:.2f}%"
    )

    print(
        f"Health Status: "
        f"{health['health_status']}"
    )

    print("\nDelivery folder:")

    print(
        f"{run_directory}"
    )

    print("\nFiles created:")

    print(
        f"- {cleaned_file.name}"
    )

    print(
        f"- {review_file.name}"
    )

    print(
        f"- {duplicate_file.name}"
    )

    print(
        f"- {possible_duplicate_file.name}"
    )

    print(
        f"- {report_file.name}"
    )

    print(
        f"- {summary_file.name}"
    )

    # ------------------------------------
    # DATABASE RESULT
    # ------------------------------------

    print("\n========================================")
    print("        SQLITE DATABASE RESULT")
    print("========================================")

    print(
        f"\nBatch Key: "
        f"{batch_key}"
    )

    print(
        f"Imported into SQLite: "
        f"{database_result['imported']}"
    )

    print(
        f"Skipped: "
        f"{database_result['skipped']}"
    )

    if database_result.get("review_required"):

        print(
            f"Manual duplicate reviews: "
            f"{database_result['review_required']}"
        )

    if database_result.get("already_imported"):

        print(
            "\nStatus: BATCH ALREADY IMPORTED"
        )

    elif database_result.get("imported", 0) > 0:

        print(
            "\nStatus: NEW BATCH IMPORTED"
        )

    elif database_result.get("skipped", 0) > 0:

        print(
            "\nStatus: NEW BATCH PROCESSED - "
            "ALL ELIGIBLE RECORDS SKIPPED"
        )

    else:

        print(
            "\nStatus: NEW BATCH PROCESSED - "
            "NO RECORDS IMPORTED"
        )

    print("\n========================================")

    # ------------------------------------
    # BULK AI RESULT
    # ------------------------------------

    print("\n========================================")
    print("        BULK AI RESULT")
    print("========================================")

    print(
        f"\nAI analysis attempted: "
        f"{ai_result['total']}"
    )

    print(
        f"AI analysis completed: "
        f"{ai_result['analyzed']}"
    )

    print(
        f"AI analysis failed: "
        f"{ai_result['failed']}"
    )

    print("\n========================================")

    database_result["ai_analysis"] = ai_result

    return database_result


# ========================================
# MAIN PROGRAM
# ========================================

def main():

    print("\n========================================")
    print("       CRM BULK CLEANUP PIPELINE")
    print("========================================")

    try:

        # --------------------------------
        # CLIENT INFORMATION
        # --------------------------------

        client_name, dataset_name = (
            get_client_information()
        )

        # --------------------------------
        # INPUT FILE
        # --------------------------------

        file_name = input(
            "\nEnter CSV file name: "
        ).strip()

        if not file_name:

            print(
                "\nERROR: CSV file name cannot "
                "be empty."
            )

            return

        # --------------------------------
        # LOAD
        # --------------------------------

        dataframe = load_csv(
            file_name
        )

        print(
            "\nCSV file loaded successfully."
        )

        # --------------------------------
        # CREATE RUN DIRECTORY
        # --------------------------------

        run_directory = create_run_directory(
            client_name
        )

        print(
            "\nCleanup run created successfully."
        )

        print(
            f"Client: {client_name}"
        )

        print(
            f"Dataset: {dataset_name}"
        )

        print(
            f"Run directory: {run_directory}"
        )

        # --------------------------------
        # INSPECT
        # --------------------------------

        show_dataset_info(
            dataframe
        )

        inspect_dataset(
            dataframe
        )

        # --------------------------------
        # STANDARDIZE
        # --------------------------------

        standardized_dataframe = (
            standardize_dataset(
                dataframe
            )
        )

        show_standardized_data(
            standardized_dataframe
        )

        # --------------------------------
        # VALIDATE
        # --------------------------------

        validated_dataframe = (
            validate_dataset(
                standardized_dataframe
            )
        )

        show_validation_results(
            validated_dataframe
        )

        # --------------------------------
        # DUPLICATE DETECTION
        # --------------------------------

        duplicate_dataframe = (
            detect_duplicates(
                validated_dataframe
            )
        )

        show_duplicate_results(
            duplicate_dataframe
        )

        # --------------------------------
        # QUALITY ANALYSIS
        # --------------------------------

        show_quality_summary(
            duplicate_dataframe
        )

        # --------------------------------
        # EXPORT + SQLITE + AI
        # --------------------------------

        database_result = export_results(
            duplicate_dataframe,
            client_name,
            dataset_name,
            run_directory,
            file_name
        )

        # --------------------------------
        # FINAL RESULT
        # --------------------------------

        print(
            "\nCRM cleanup run completed successfully."
        )

        print(
            f"SQLite records imported: "
            f"{database_result['imported']}"
        )

        print(
            f"SQLite records skipped: "
            f"{database_result['skipped']}"
        )

        if database_result.get("review_required"):

            print(
                f"Manual duplicate reviews: "
                f"{database_result['review_required']}"
            )

        # --------------------------------
        # AI FINAL RESULT
        # --------------------------------

        ai_result = database_result.get(
            "ai_analysis",
            {}
        )

        if ai_result:

            print(
                f"\nAI analyses completed: "
                f"{ai_result.get('analyzed', 0)}"
            )

            print(
                f"AI analyses failed: "
                f"{ai_result.get('failed', 0)}"
            )

    except FileNotFoundError as error:

        print(
            f"\nERROR: {error}"
        )

    except pd.errors.EmptyDataError:

        print(
            "\nERROR: The CSV file is empty."
        )

    except Exception as error:

        print(
            f"\nUnexpected error: {error}"
        )


# ========================================
# RUN PROGRAM
# ========================================

if __name__ == "__main__":

    main()