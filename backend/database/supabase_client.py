import os

from functools import lru_cache

from supabase import create_client, Client

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

BUCKET_NAME = os.getenv("SUPABASE_BUCKET", "enterprise-documents")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(

        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment. "

        "Copy .env.example to .env and fill in your values."

    )

@lru_cache(maxsize=1)

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
