import os
from supabase import create_client, Client

SUPABASE_URL = "https://cojvbregrwqgnzscmmub.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjkyNjE0MiwiZXhwIjoyMDkyNTAyMTQyfQ.eRgflZH9Qy2EXIVkIAN0xd5tFf9mO2pM-Iqr8IFnv7s"
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("--- Supabase User Data ---")
res = supabase_admin.table('users').select('*').execute()
print(res.data)
