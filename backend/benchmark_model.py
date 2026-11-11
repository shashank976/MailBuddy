
import os
import time
from ollama import Client

MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:4b-instruct",
)

client = Client(
    host="http://127.0.0.1:11434",
    timeout=120,
)

email = """
Subject: Interview Availability

Hi,

We would like to schedule an interview
for the software engineering internship.

Please confirm whether Thursday at 3 PM works.

Thanks,
Recruiting Team
"""

print(f"Testing model: {MODEL}", flush=True)

start = time.perf_counter()

response = client.chat(
    model=MODEL,
    messages=[
        {
            "role": "user",
            "content": (
                "Classify this email as high or low "
                "priority. Give one short sentence "
                "explaining why.\n\n" + email
            ),
        }
    ],
    think=False,
    options={
        "temperature": 0,
        "num_predict": 100,
    },
)

elapsed = time.perf_counter() - start

print("\n--- BENCHMARK ---")
print(f"Wall time: {elapsed:.2f}s")
print(f"Model load: {(response.load_duration or 0) / 1e9:.2f}s")
print(f"Input tokens: {response.prompt_eval_count}")
print(f"Output tokens: {response.eval_count}")
print(f"Generation: {(response.eval_duration or 0) / 1e9:.2f}s")
print(f"Response: {response.message.content}")
