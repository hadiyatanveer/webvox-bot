import os
import yaml
from dotenv import load_dotenv

load_dotenv()

# Load model settings from config.yaml so changing the model in one place applies everywhere
with open("config.yaml", "r") as f:
    _config = yaml.safe_load(f)

_provider = _config["llm"].get("provider", "groq")
_model_name = _config["llm"]["model_name"]
_temperature = _config["llm"].get("temperature", 0.1)

if _provider == "groq":
    from langchain_groq import ChatGroq
    LLM = ChatGroq(model=_model_name, temperature=_temperature, api_key=os.getenv("GROQ_API_KEY"))
elif _provider == "gemini":
    from langchain_google_genai import ChatGoogleGenerativeAI
    LLM = ChatGoogleGenerativeAI(model=_model_name, temperature=_temperature, google_api_key=os.getenv("GEMINI_API_KEY"))
else:
    raise ValueError(f"Unsupported LLM provider in config.yaml: '{_provider}'. Supported: 'groq', 'gemini'")