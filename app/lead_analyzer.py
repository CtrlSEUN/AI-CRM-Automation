import os
import json
import requests


NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

MODEL = "openai/gpt-oss-20b"


def analyze_lead(lead):
    """
    Analyze a CRM lead using NVIDIA's API.

    Returns structured lead analysis as a Python dictionary.
    """

    # ==========================================
    # CHECK API KEY
    # ==========================================

    if not NVIDIA_API_KEY:
        raise RuntimeError(
            "NVIDIA_API_KEY environment variable is not set."
        )

    # ==========================================
    # AI PROMPT
    # ==========================================

    prompt = f"""
Analyze the following customer lead.

Customer:
Name: {lead['name']}
Email: {lead['email']}
Phone: {lead['phone']}
Company: {lead['company']}
Message: {lead['message']}

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
- quantity should be a number.
- timeline should identify any stated timeline, otherwise "Unknown".
- priority must be LOW, MEDIUM, or HIGH.
- lead_score must be between 0 and 100.
- summary should briefly explain the customer's request.
- Return JSON only.
"""

    # ==========================================
    # HEADERS
    # ==========================================

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # ==========================================
    # REQUEST PAYLOAD
    # ==========================================

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

    # ==========================================
    # SEND REQUEST
    # ==========================================

    try:

        response = requests.post(
            INVOKE_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )

        print(f"HTTP Status: {response.status_code}")

        # ======================================
        # NVIDIA API ERROR
        # ======================================

        if response.status_code != 200:

            print("\n===== NVIDIA API ERROR =====")
            print(response.text)
            print("============================")

            response.raise_for_status()

        # ======================================
        # PARSE RESPONSE
        # ======================================

        result = response.json()

        if "choices" not in result:
            raise ValueError(
                "NVIDIA API response does not contain 'choices'."
            )

        if not result["choices"]:
            raise ValueError(
                "NVIDIA API returned an empty choices list."
            )

        message = result["choices"][0].get(
            "message",
            {}
        )

        content = message.get("content")

        # ======================================
        # HANDLE EMPTY CONTENT
        # ======================================

        if not content:

            reasoning = message.get(
                "reasoning",
                ""
            )

            raise ValueError(
                "NVIDIA API returned empty content. "
                "The model may have used the token limit "
                "for reasoning before producing the JSON."
            )

        # ======================================
        # SHOW RAW AI RESPONSE
        # ======================================

        print("\n===== RAW AI RESPONSE =====")
        print(content)

        # ======================================
        # CLEAN RESPONSE
        # ======================================

        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]

        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        # ======================================
        # PARSE JSON
        # ======================================

        try:

            analysis = json.loads(content)

        except json.JSONDecodeError as error:

            raise ValueError(
                f"AI returned invalid JSON: {error}"
            )

        # ======================================
        # REQUIRED FIELDS
        # ======================================

        required_fields = [
            "lead_type",
            "intent",
            "product",
            "quantity",
            "timeline",
            "priority",
            "lead_score",
            "summary",
        ]

        missing_fields = [
            field
            for field in required_fields
            if field not in analysis
        ]

        if missing_fields:

            raise ValueError(
                "AI response is missing required fields: "
                + ", ".join(missing_fields)
            )

        # ======================================
        # VALIDATE PRIORITY
        # ======================================

        if analysis["priority"] not in [
            "LOW",
            "MEDIUM",
            "HIGH",
        ]:

            raise ValueError(
                "AI returned an invalid priority."
            )

        # ======================================
        # VALIDATE LEAD SCORE
        # ======================================

        try:

            lead_score = int(
                analysis["lead_score"]
            )

        except (ValueError, TypeError):

            raise ValueError(
                "AI returned an invalid lead score."
            )

        if lead_score < 0 or lead_score > 100:

            raise ValueError(
                "AI lead score must be between 0 and 100."
            )

        analysis["lead_score"] = lead_score

        # ======================================
        # VALIDATE QUANTITY
        # ======================================

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

        # ======================================
        # SUCCESS
        # ======================================

        return analysis

    # ==========================================
    # NETWORK ERRORS
    # ==========================================

    except requests.exceptions.Timeout:

        raise RuntimeError(
            "NVIDIA API request timed out."
        )

    except requests.exceptions.ConnectionError:

        raise RuntimeError(
            "Could not connect to the NVIDIA API."
        )

    except requests.exceptions.HTTPError as error:

        raise RuntimeError(
            f"NVIDIA API request failed: {error}"
        )

