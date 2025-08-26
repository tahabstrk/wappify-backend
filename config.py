import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
APP_SECRET   = os.environ["APP_SECRET"]  # string olarak sakla