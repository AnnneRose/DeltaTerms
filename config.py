import os
from dotenv import load_dotenv

load_dotenv()

BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"

HF_TOKEN = os.getenv("HF_TOKEN")
