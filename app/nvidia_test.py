import os
import requests
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

# Get our NVIDIA API key
api_key = os.getenv("NVIDIA_API_KEY")

if not api_key:
    raise RuntimeError("NVIDIA_API_KEY was not found in .env")

url = "https://integrate.api.nvidia.com/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

payload = {
    "model": "meta/llama-3.1-8b-instruct",
    "messages": [
        {
            "role": "user",
            "content": "Explain what a CRM is in one simple sentence."
        }
    ],
    "temperature": 0.2,
    "max_tokens": 100,
}

response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=60,
)

print("HTTP Status:", response.status_code)

response.raise_for_status()

result = response.json()

answer = result["choices"][0]["message"]["content"]

print("\nNVIDIA AI RESPONSE:")
print(answer)