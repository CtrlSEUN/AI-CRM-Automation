import json
import os
import re

import requests
from dotenv import load_dotenv

from app.database import save_lead_analysis


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()


NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

MODEL = "openai/gpt-oss-20b"

ALLOWED_PRIORITIES = {
    "LOW",
    "MEDIUM",
    "HIGH",
}

REQUIRED_FIELDS = [
    "lead_type",
    "intent",
    "product",
    "quantity",
    "timeline",
    "priority",
    "lead_score",
    "summary",
]


# ==========================================
# INPUT VALIDATION
# ==========================================

def validate_lead_input(lead):
    """
    Validate the minimum information required
    before sending a lead to the AI.
    """

    if not isinstance(lead, dict):
        raise ValueError("Lead must be provided as a dictionary.")

    required_input_fields = [
        "name",
        "email",
        "phone",
        "company",
        "message",
    ]

    missing_fields = [
        field
        for field in required_input_fields
        if field not in lead
    ]

    if missing_fields:
        raise ValueError(
            "Lead is missing required fields: "
            + ", ".join(missing_fields)
        )


# ==========================================
# AI RESPONSE CLEANING
# ==========================================

def clean_json_response(content):
    """
    Remove common markdown/code-fence formatting
    from an AI response before JSON parsing.
    """

    if not isinstance(content, str):
        raise ValueError("AI response content must be text.")

    content = content.strip()

    content = re.sub(
        r"^```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = re.sub(
        r"\s*```$",
        "",
        content,
        flags=re.IGNORECASE,
    )

    content = content.strip()

    if not content.startswith("{"):
        json_start = content.find("{")

        if json_start != -1:
            content = content[json_start:]

    if not content.endswith("}"):
        json_end = content.rfind("}")

        if json_end != -1:
            content = content[:json_end + 1]

    return content.strip()


# ==========================================
# AI RESPONSE VALIDATION
# ==========================================

def validate_analysis(analysis):
    """
    Validate and normalize the structured response
    returned by the AI.
    """

    if not isinstance(analysis, dict):
        raise ValueError(
            "AI analysis must be returned as a JSON object."
        )

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in analysis
    ]

    if missing_fields:
        raise ValueError(
            "AI response is missing required fields: "
            + ", ".join(missing_fields)
        )

    # ------------------------------------------
    # Normalize text fields
    # ------------------------------------------

    text_fields = [
        "lead_type",
        "intent",
        "product",
        "timeline",
        "summary",
    ]

    for field in text_fields:
        value = analysis[field]

        if value is None:
            analysis[field] = "Unknown"
            continue

        if not isinstance(value, str):
            analysis[field] = str(value)

        analysis[field] = analysis[field].strip()

        if not analysis[field]:
            analysis[field] = "Unknown"

    # ------------------------------------------
    # Validate priority
    # ------------------------------------------

    priority = str(
        analysis["priority"]
    ).strip().upper()

    if priority not in ALLOWED_PRIORITIES:
        raise ValueError(
            "AI returned an invalid priority. "
            f"Expected LOW, MEDIUM, or HIGH; got: {priority}"
        )

    analysis["priority"] = priority

    # ------------------------------------------
    # Validate lead score
    # ------------------------------------------

    try:
        lead_score = int(
            analysis["lead_score"]
        )
    except (ValueError, TypeError):
        raise ValueError(
            "AI returned an invalid lead score."
        )

    if not 0 <= lead_score <= 100:
        raise ValueError(
            "AI lead score must be between 0 and 100."
        )

    analysis["lead_score"] = lead_score

    # ------------------------------------------
    # Validate quantity
    # ------------------------------------------

    try:
        quantity = int(
            analysis["quantity"]
        )
    except (ValueError, TypeError):
        raise ValueError(
            "AI returned an invalid quantity."
        )

    if quantity < 0:
        raise ValueError(
            "AI quantity cannot be negative."
        )

    analysis["quantity"] = quantity

    return analysis


# ==========================================
# BUILD AI PROMPT
# ==========================================

def build_analysis_prompt(lead):
    """
    Build a structured prompt focused on extracting
    evidence directly from the customer's message.
    """

    return f"""
You are a CRM lead-analysis system.

Your job is to extract facts from the customer's message
and classify the lead based ONLY on the information provided.

CUSTOMER INFORMATION

Name:
{lead.get("name", "Unknown")}

Email:
{lead.get("email", "Unknown")}

Phone:
{lead.get("phone", "Unknown")}

Company:
{lead.get("company", "Unknown")}

CUSTOMER MESSAGE:
{lead.get("message", "Unknown")}


IMPORTANT EXTRACTION RULES

1. PRODUCT
Identify the actual product, service, or item the customer
is asking about.

Look directly at the CUSTOMER MESSAGE.

Example:
"We need 20 office chairs for our new office."

Correct:
"product": "Office chairs"

Incorrect:
"product": "Unknown"

Only use "Unknown" when no product or service can reasonably
be identified from the message.

2. QUANTITY
Extract the number of units requested.

Example:
"We need 20 office chairs."

Correct:
"quantity": 20

If no quantity is stated, use 0.

3. TIMELINE
Extract any delivery, purchase, project, or decision timeline.

Example:
"delivery within two weeks"

Correct:
"timeline": "Within two weeks"

If no timeline is stated, use "Unknown".

4. INTENT
Determine what the customer is trying to do.

Examples:
- asking to buy something → "Purchase"
- asking for pricing → "Pricing Inquiry"
- asking for information → "Information"
- asking for support → "Support"
- just researching → "Research"

5. LEAD TYPE
Classify the business purpose of the lead.

Examples:
- purchasing a product → "Sales"
- requesting support → "Support"
- partnership request → "Partnership"
- general inquiry → "Inquiry"

6. PRIORITY

Use the customer's actual urgency and buying intent.

HIGH:
- urgent or near-term purchase
- large quantity
- explicit short deadline
- strong buying intent
- multiple urgency signals

MEDIUM:
- clear interest or purchase intent
- but no strong urgency
- moderate quantity or timeline

LOW:
- general information
- early research
- weak buying intent
- no meaningful urgency

7. LEAD SCORE

Give a meaningful score from 0 to 100.

Consider:
- buying intent
- urgency
- quantity
- timeline
- clarity of request

Examples:

Strong purchase request with quantity and short deadline:
70-95

Clear interest but no strong urgency:
40-69

General inquiry or early research:
10-39

Do NOT automatically use 0 unless there is essentially
no meaningful lead information.

8. SUMMARY
Write a short factual summary using only information
from the customer's message.

DO NOT invent facts.


RETURN ONLY VALID JSON.

Use exactly this structure:

{{
    "lead_type": "Sales",
    "intent": "Purchase",
    "product": "Office chairs",
    "quantity": 20,
    "timeline": "Within two weeks",
    "priority": "HIGH",
    "lead_score": 85,
    "summary": "Customer requests 20 office chairs with delivery within two weeks."
}}

The example values above are ONLY examples of the format.
Do not copy them unless they are supported by the actual
customer message.

Return JSON only.
"""


# ==========================================
# NVIDIA API REQUEST
# ==========================================

def request_ai_analysis(prompt):
    """
    Send an analysis request to NVIDIA's API
    and return the raw structured response.
    """

    if not NVIDIA_API_KEY:
        raise RuntimeError(
            "NVIDIA_API_KEY environment variable is not set."
        )

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.1,
        "top_p": 0.7,
        "max_tokens": 1000,
        "stream": False,
    }

    try:
        response = requests.post(
            INVOKE_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "NVIDIA API request timed out."
        )

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Could not connect to the NVIDIA API."
        )

    except requests.exceptions.RequestException as error:
        raise RuntimeError(
            f"NVIDIA API request failed: {error}"
        )

    if response.status_code != 200:
        raise RuntimeError(
            "NVIDIA API returned HTTP "
            f"{response.status_code}: {response.text}"
        )

    try:
        result = response.json()

    except ValueError:
        raise RuntimeError(
            "NVIDIA API returned an invalid JSON response."
        )

    if "choices" not in result:
        raise RuntimeError(
            "NVIDIA API response does not contain 'choices'."
        )

    if not result["choices"]:
        raise RuntimeError(
            "NVIDIA API returned an empty choices list."
        )

    message = result["choices"][0].get(
        "message",
        {},
    )

    content = message.get("content")

    if not content:
        raise RuntimeError(
            "NVIDIA API returned empty content."
        )

    return content


# ==========================================
# MAIN ANALYSIS FUNCTION
# ==========================================

def analyze_lead(lead):
    """
    Analyze a CRM lead using NVIDIA's API.

    Returns a validated and normalized
    lead-analysis dictionary.
    """

    validate_lead_input(lead)

    prompt = build_analysis_prompt(lead)

    content = request_ai_analysis(prompt)

    cleaned_content = clean_json_response(content)

    try:
        analysis = json.loads(
            cleaned_content
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"AI returned invalid JSON: {error}"
        )

    return validate_analysis(analysis)


# ==========================================
# AI ANALYSIS + DATABASE INTEGRATION
# ==========================================

def analyze_and_save_lead(lead_id, lead):
    """
    Analyze an existing CRM lead using NVIDIA's API
    and save the validated analysis to SQLite.
    """

    if not isinstance(lead_id, int) or isinstance(lead_id, bool):
        raise ValueError(
            "Lead ID must be an integer."
        )

    if lead_id <= 0:
        raise ValueError(
            "Lead ID must be greater than zero."
        )

    analysis = analyze_lead(lead)

    saved = save_lead_analysis(
        lead_id,
        analysis,
    )

    if not saved:
        raise RuntimeError(
            f"Could not save AI analysis for Lead ID {lead_id}."
        )

    return analysis