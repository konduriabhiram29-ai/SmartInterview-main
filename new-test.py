import os
from groq import Groq

def test_truncation():
    groq_client = Groq()
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    
    response = groq_client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a 500 word essay about Python."},
        ],
        temperature=0.7,
        max_tokens=15, # artificially low to force truncation
    )
    
    choice = response.choices[0]
    print(f"Content: {choice.message.content}")
    print(f"Finish Reason: {choice.finish_reason}")
    print(f"Type of Finish Reason: {type(choice.finish_reason)}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_truncation()
