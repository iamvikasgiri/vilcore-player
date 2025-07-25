# supabase_client.py
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from datetime import timedelta

load_dotenv()  # reads .env

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_song_signed_url(path: str, expires_in: int = 3600) -> str | None:
    """
    Generate a signed URL for a file in the 'songs' bucket.
    expires_in = lifetime in seconds (default 1 hour).
    """
    res = supabase.storage.from_("songs").create_signed_url(path, expires_in)

    # new: supabase-py v2 returns a dict:
    if isinstance(res, dict):
        return res.get("signedURL")

    # old: .data attribute
    return res.data.get("signedURL") if getattr(res, "data", None) else None