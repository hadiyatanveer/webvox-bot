from langchain_groq import ChatGroq

import os
import yaml
from dotenv import load_dotenv

load_dotenv()

# Load model settings from config.yaml so changing the model in one place applies everywhere
with open("config.yaml", "r") as f:
    _config = yaml.safe_load(f)

_model_name = _config["llm"]["model_name"]
_temperature = _config["llm"].get("temperature", 0.1)

LLM = ChatGroq(model=_model_name, temperature=_temperature, api_key=os.getenv("GROQ_API_KEY"))