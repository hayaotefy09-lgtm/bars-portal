import os
from supabase import create_client, Client

SUPABASE_URL = "https://cojvbregrwqgnzscmmub.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjkyNjE0MiwiZXhwIjoyMDkyNTAyMTQyfQ.eRgflZH9Qy2EXIVkIAN0xd5tFf9mO2pM-Iqr8IFnv7s"
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

print("--- Supabase Table Probe ---")
tables = ['users', 'profiles', 'Registry', 'Staff', 'mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings', 'sessions', 'Sessions', 'Events', 'resources', 'Resources', 'Library', 'messages', 'Messages', 'Chats']

for t in tables:
    try:
        res = supabase_admin.table(t).select('count', count='exact').limit(1).execute()
        print(f"Table '{t}': Found ({res.count} rows)")
    except Exception as e:
        print(f"Table '{t}': ERROR ({str(e)[:100]}...)")
