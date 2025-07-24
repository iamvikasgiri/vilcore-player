# supabase_client.py
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()  # reads .env

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
