import os
import json
import urllib.request

api_key = os.environ.get("GEMINI_API_KEY")
model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

print(f"Testing model: {model}")

url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
req_payload = {
    "contents": [{"role": "user", "parts": [{"text": "Hello, simply reply with the word 'OK'."}]}],
    "generationConfig": {"temperature": 0.2}
}

req = urllib.request.Request(
    url,
    data=json.dumps(req_payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print("Success!", resp.code)
        print(resp.read().decode("utf-8"))
except Exception as e:
    print("Error:", e)
