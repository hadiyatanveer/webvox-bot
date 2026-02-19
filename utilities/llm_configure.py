import os
import yaml
from groq import Groq
from pathlib import Path
from dotenv import load_dotenv

# Load .env
dotenv_path = Path(".") / ".env"
load_dotenv(dotenv_path, override=True)

# Load config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

provider = config["llm"]["provider"]
model_name = config["llm"]["model_name"]
temperature = config["llm"].get("temperature", 0.1)

print(f"🔧 LLM Config: provider={provider}, model={model_name}, temperature={temperature}")

if provider == "gemini":
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY") or config["providers"]["gemini"]["api_key"]
    genai.configure(api_key=api_key)

    def generate_content(prompt: str):
        model = genai.GenerativeModel(model_name)
        return model.generate_content(prompt)

elif provider == "groq":
    api_key = os.getenv("GROQ_API_KEY") or config["providers"]["groq"].get("api_key")
    client = Groq(api_key=api_key)

    def generate_content(prompt: str):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return response.choices[0].message
        except Exception as e:
            print(f"❌ Groq API error (model={model_name}): {e}")
            raise

else:
    raise ValueError(f"Unsupported provider: {provider}")