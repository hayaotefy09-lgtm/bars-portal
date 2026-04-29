import os
import json
from supabase import create_client, Client

url = "https://cojvbregrwqgnzscmmub.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjkyNjE0MiwiZXhwIjoyMDkyNTAyMTQyfQ.eRgflZH9Qy2EXIVkIAN0xd5tFf9mO2pM-Iqr8IFnv7s"
supabase = create_client(url, key)

email = "514511@naischool.ae"
for table in ['users', 'profiles', 'Registry']:
    try:
        r = supabase.table(table).select('*').eq('email', email).execute()
        if r.data:
            print(f"Table: {table}")
            print(json.dumps(r.data[0], indent=2))
    except Exception as e:
        print(f"Error in {table}: {e}")
