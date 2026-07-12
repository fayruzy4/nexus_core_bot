from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None

def get_supabase() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL atau SUPABASE_KEY belum diisi.")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client
