from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SESSION_NAME = "session"

CHANNEL_IDS = [
    -1001402220998,
    -100131142594,
    -1002628877785
]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

LOT_SIZE = float(os.getenv("LOT_SIZE"))
RISK_PERCENT = float(os.getenv("RISK_PERCENT"))
MAGIC_NUMBER = int(os.getenv("MAGIC_NUMBER", "123456"))



