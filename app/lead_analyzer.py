import json
import os
import re

import requests
from dotenv import load_dotenv


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

    # Remove markdown code fences.
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

    # Handle cases where the model places additional
    # text before or after the JSON object.
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
    Build the prompt used to analyze a CRM lead.
    """

    return f"""
Analyze the following customer lead.

Customer:
Name: {lead.get("name", "Unknown")}
Email: {lead.get("email", "Unknown")}
Phone: {lead.get("phone", "Unknown")}
Company: {lead.get("company", "Unknown")}
Message: {lead.get("message", "Unknown")}

Return ONLY valid JSON using exactly this structure:

{{
    "lead_type": "Sales",
    "intent": "Purchase",
    "product": "Unknown",
    "quantity": 0,
    "timeline": "Unknown",
    "priority": "LOW",
    "lead_score": 0,
    "summary": "Short summary of the lead."
}}

Rules:

- lead_type should describe the type of lead.
- intent should describe what the customer wants.
- product should identify the requested product.
- quantity must be a number.
- timeline should identify any stated timeline, otherwise "Unknown".
- priority must be LOW, MEDIUM, or HIGH.
- lead_score must be between 0 and 100.
- summary should briefly explain the customer's request.
- Do not invent information that is not present.
- Return JSON only.
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
        "temperature": 0.2,
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

    # Validate input.
    validate_lead_input(lead)

    # Build prompt.
    prompt = build_analysis_prompt(lead)

    # Send request.
    content = request_ai_analysis(prompt)

    # Clean AI response.
    cleaned_content = clean_json_response(content)

    # Parse JSON.
    try:
        analysis = json.loads(
            cleaned_content
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"AI returned invalid JSON: {error}"
        )

    # Validate and normalize result.
    return validate_analysis(analysis)