from ollama import Client

MODEL = "qwen3:4b"

client = Client(host="http://localhost:11434") 

def ask_model(system_prompt: str, user_prompt: str) -> str:
    response = client.chat(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt + "\n/no_think"
            }
        ],
        think=False,
        options={
            "temperature": 0
        }
    )

    return response.message.content