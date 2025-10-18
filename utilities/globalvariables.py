from langchain_groq import ChatGroq

import os
from dotenv import load_dotenv

load_dotenv()

LLM = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, api_key=os.getenv("GROQ_API_KEY"))