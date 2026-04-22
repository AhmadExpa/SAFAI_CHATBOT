import os
import requests
from dotenv import load_dotenv

# Load .env file from backend folder
load_dotenv()

XAI_API_KEY = os.getenv("XAI_API_KEY")
BASE_URL = "https://api.x.ai/v1"

if not XAI_API_KEY:
    raise ValueError("❌ Missing XAI_API_KEY in .env file.")


def chat_with_grok(prompt_text: str, model: str = "grok-4-fast-reasoning"):
    """
    Chat with Grok text models (grok-4-fast-reasoning, grok-3).
    """
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt_text}
        ],
        "max_tokens": 500
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(
            f"❌ Grok API error {response.status_code}: {response.text}"
        )

    data = response.json()
    return data["choices"][0]["message"]["content"]


def generate_image_with_grok(prompt_text: str, model: str = "grok-2-image"):
    """
    Generate an image with Grok (grok-2-image).
    Returns the image URL.
    """
    url = f"{BASE_URL}/images/generations"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "prompt": prompt_text,
        "size": "1024x1024"
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise RuntimeError(
            f"❌ Grok API error {response.status_code}: {response.text}"
        )

    data = response.json()
    return data["data"][0]["url"]


# --- Quick test ---
if __name__ == "__main__":
    print("🔹 Testing grok-4-fast-reasoning...")
    reply = chat_with_grok("Explain quantum physics simply.", model="grok-4-fast-reasoning")
    print("Grok-4:", reply)

    print("\n🔹 Testing grok-3...")
    reply = chat_with_grok("Tell me a joke about AI.", model="grok-3")
    print("Grok-3:", reply)

    print("\n🔹 Testing grok-2-image...")
    image_url = generate_image_with_grok("A futuristic city on Mars in neon lights")
    print("Image generated:", image_url)
