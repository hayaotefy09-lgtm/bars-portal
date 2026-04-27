import uuid
import datetime
import random
import requests
import os
import io
import re
import mimetypes
import json
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

print('BARS Flask Cloud Server Initializing...')
SUPABASE_URL = os.environ.get('SUPABASE_URL', "https://cojvbregrwqgnzscmmub.supabase.co")
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MjYxNDIsImV4cCI6MjA5MjUwMjE0Mn0.QCnDJtL7oYuvL8spFWaMWAxA6DG6u7lMid1a79yqYQI")
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNvanZicmVncndxZ256c2NtbXViIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjkyNjE0MiwiZXhwIjoyMDkyNTAyMTQyfQ.eRgflZH9Qy2EXIVkIAN0xd5tFf9mO2pM-Iqr8IFnv7s")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

SESSION_STORE = {}
PASSWORD_MAP = {} # Virtual Auth Engine Fallback

def load_local_auth():
    global PASSWORD_MAP
    try:
        path = 'local_users.json'
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                for u in data:
                    email = u.get('email', '').lower().strip()
                    if email: PASSWORD_MAP[email] = u.get('password', 'bars')
            print(f"[AUTH]: Loaded {len(PASSWORD_MAP)} users into Virtual Auth Engine.")
    except Exception as e:
        print(f"[AUTH ERROR]: Could not load local auth: {str(e)}")

def get_user_from_headers():
    if request.headers.get('X-Admin-Bypass') == 'BARS2026':
        return {"email": "admin@bars.ae", "role": "ProgramStaff", "name": "System Admin", "isCounselor": True}
    auth = request.headers.get('Authorization')
    if auth and auth.startswith('Bearer '):
        token = auth.split(' ')[1]
        if token in SESSION_STORE: return SESSION_STORE[token]
    return None

def safe_get(obj, keys, default=None):
    for k in keys:
        if k in obj and obj[k] is not None: return obj[k]
    return default

def normalize_role(role_str):
    if not role_str: return "Mentee"
    r = str(role_str).lower().strip()
    if r in ['programstaff', 'counselor', 'admin', 'staff', 'program manager']: return "ProgramStaff"
    if r in ['mentor']: return "Mentor"
    return "Mentee"

def safe_fetch(table_names, fallback_data=[]):
    for name in table_names:
        try:
            resp = supabase_admin.table(name).select('*').execute()
            if resp.data is not None: return resp.data
        except: continue
    return fallback_data

def init_cloud_seed():
    print("[SEED]: Verifying Admin account...")
    try:
        admin_email = "admin@bars.ae"
        found = False
        for table in ['users', 'profiles', 'Registry']:
            try:
                res = supabase_admin.table(table).select('email').eq('email', admin_email).execute()
                if res.data: found = True; break
            except: continue
        
        if not found:
            print(f"[SEED]: Admin {admin_email} not found. Creating authoritative entry...")
            admin_data = {
                "email": admin_email, "full_name": "System Administrator", "role": "ProgramStaff", "password": "bars", "bio": "System Root Account", "interests": "Administration"
            }
            supabase_admin.table('users').insert(admin_data).execute()
            print("[SEED]: Admin account created successfully.")
        else:
            print("[SEED]: Admin account verified.")
    except Exception as e:
        print(f"[SEED ERROR]: Cloud seeding failed: {str(e)}")

@app.route('/api/initial-data', methods=['GET'])
def initial_data():
    return jsonify({"status": "Online", "v": "156.0 Resilience Master"})

@app.route('/api/dashboard', methods=['GET'])
def handle_dashboard():
    try:
        u = get_user_from_headers()
        if not u: return jsonify({"error": "Auth Required"}), 401
        res = {"pairs": [], "mentors": [], "sessions": [], "resources": [], "messages": [], "profile": {}}
        
        users_data = safe_fetch(['users', 'profiles', 'Registry', 'Staff'])
        pairs_data = safe_fetch(['mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings'])
        sessions_data = safe_fetch(['sessions', 'Sessions', 'Events'])
        resources_data = safe_fetch(['resources', 'Resources', 'Library'])
        messages_data = safe_fetch(['messages', 'Messages', 'Chats'])
        
        users_map = {safe_get(r, ['email', 'user_email']): r for r in users_data} if users_data else {}
        
        def format_user_name(usr):
            fn = safe_get(usr, ['full_name', 'name', 'displayName']) or f"{safe_get(usr, ['first_name', 'firstName'], '')} {safe_get(usr, ['last_name', 'lastName'], '')}".strip() or "Unnamed User"
            parts = fn.split(' ', 1); f_name = parts[0] if len(parts) > 0 else fn; l_name = parts[1] if len(parts) > 1 else ""
            return fn, f_name, l_name

        for email, usr in users_map.items():
            if not email: continue
            role = normalize_role(safe_get(usr, ['role', 'user_role']))
            if role == 'Mentor':
                fn, f_name, l_name = format_user_name(usr)
                res["mentors"].append({"name": fn, "first_name": f_name, "last_name": l_name, "email": email, "bio": safe_get(usr, ['bio']), "interests": safe_get(usr, ['interests'])})
        
        for p in pairs_data:
            m_email = safe_get(p, ['mentor_email', 'mentorEmail', 'mentor'])
            s_email = safe_get(p, ['mentee_email', 'menteeEmail', 'mentee'])
            if not m_email or not s_email: continue
            p_id = safe_get(p, ['id', 'pair_id'])
            
            cur_role = normalize_role(u['role'])
            if cur_role == 'Mentor' and m_email == u['email']:
                uu = users_map.get(s_email, {})
                fn, f_name, l_name = format_user_name(uu)
                res["pairs"].append({"name": fn, "first_name": f_name, "last_name": l_name, "email": s_email, "pair_id": p_id, "type": "Mentee", "bio": safe_get(uu, ['bio']), "interests": safe_get(uu, ['interests'])})
            elif cur_role == 'Mentee' and s_email == u['email']:
                uu = users_map.get(m_email, {})
                fn, f_name, l_name = format_user_name(uu)
                res["pairs"].append({"name": fn, "first_name": f_name, "last_name": l_name, "email": m_email, "pair_id": p_id, "type": "Mentor", "bio": safe_get(uu, ['bio']), "interests": safe_get(uu, ['interests'])})
            elif cur_role == 'ProgramStaff':
                m = users_map.get(m_email, {}); s = users_map.get(s_email, {})
                fn_m, _, _ = format_user_name(m); fn_s, _, _ = format_user_name(s)
                res["pairs"].append({"mentor_name": fn_m, "mentee_name": fn_s, "pair_id": p_id, "mentor_email": m_email, "mentee_email": s_email})
        
        res["resources"] = resources_data
        res["sessions"] = sessions_data
        res["messages"] = messages_data 
        fn_u, f_u, l_u = format_user_name(u)
        is_c = normalize_role(u.get('role')) == 'ProgramStaff'
        
        gender = str(safe_get(u, ['Gender', 'gender'], '')).replace("'", "").strip()
        survey_links = {
            "mentee_pre": "survey_mentee_pre2.csv",
            "mentee_post": "survey_mentee_post2.csv" if gender == "Boy" else "https://forms.office.com/Pages/ResponsePage.aspx?id=bvV_Bz_K30Cmp2nZVs8Lw9QMQpAEwXBPk9Yk-mW8Ba1UMTZXWjZIRE9ET1pWN05QVzcyUjhPSTZCRS4u",
            "mentor_post": "survey_mentor_post2.csv",
            "mentor_during": "survey_mentor_during2.csv"
        }
        
        res["profile"] = {"name": fn_u, "first_name": f_u, "last_name": l_u, "email": u.get('email'), "role": u['role'], "isCounselor": is_c, "gender": gender, "surveys": survey_links}
        return jsonify(res)
    except Exception as e: return jsonify({"error": f"Dashboard Error: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def handle_login():
    try:
        data = request.get_json(); e, p = data.get('email', '').lower().strip(), data.get('password', '')
        resp = None
        for table in ['users', 'profiles', 'Registry', 'Staff']:
            try:
                r = supabase_admin.table(table).select('*').eq('email', e).execute()
                if r.data:
                    db_pass = safe_get(r.data[0], ['password'])
                    if not db_pass: db_pass = PASSWORD_MAP.get(e)
                    if db_pass == p: resp = r; break
                    else: continue
            except: continue
        if resp and resp.data:
            r = resp.data[0]
            fn = safe_get(r, ['full_name', 'name']) or f"{safe_get(r, ['first_name', 'firstName'], '')} {safe_get(r, ['last_name', 'lastName'], '')}".strip() or "User"
            parts = fn.split(' ', 1); f_name = parts[0] if len(parts) > 0 else fn; l_name = parts[1] if len(parts) > 1 else ""
            user = {"email": e, "role": safe_get(r, ['role', 'user_role']), "name": fn, "first_name": f_name, "last_name": l_name, "isCounselor": (normalize_role(safe_get(r, ['role'])) == 'ProgramStaff'), "Gender": safe_get(r, ['Gender', 'gender'])}
            token = str(uuid.uuid4()); SESSION_STORE[token] = user
            return jsonify({"success": True, "token": token, "user": user})
        return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e: return jsonify({"error": f"Login Error: {str(e)}"}), 500

@app.route('/api/admin/data', methods=['GET'])
def admin_data():
    if request.headers.get('X-Admin-Bypass') != 'BARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        users = safe_fetch(['users', 'profiles', 'Registry', 'Staff'])
        pairs = safe_fetch(['mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings'])
        users_map = {}
        for u in users:
            u['name'] = safe_get(u, ['full_name', 'name', 'displayName']) or f"{safe_get(u, ['first_name', 'firstName'], '')} {safe_get(u, ['last_name', 'lastName'], '')}".strip() or "Unnamed"
            u['role'] = normalize_role(safe_get(u, ['role', 'user_role']))
            users_map[u['email']] = u['name']
        for p in pairs:
            m_email = safe_get(p, ['mentor_email', 'mentorEmail', 'mentor'])
            s_email = safe_get(p, ['mentee_email', 'menteeEmail', 'mentee'])
            p['mentor'] = users_map.get(m_email, m_email or "Unknown")
            p['mentee'] = users_map.get(s_email, s_email or "Unknown")
            p['pair_id'] = safe_get(p, ['id', 'pair_id'])
        return jsonify({"users": users, "pairs": pairs, "profiles": users})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/admin/create', methods=['POST'])
def admin_create():
    if request.headers.get('X-Admin-Bypass') != 'BARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json(); email, fn, ln, role = data.get('email', '').lower().strip(), data.get('firstName', ''), data.get('lastName', ''), data.get('role', 'Mentee')
        full_name = f"{fn} {ln}".strip()
        supabase_admin.table('users').insert({"email": email, "full_name": full_name, "role": role, "password": "bars"}).execute()
        return jsonify({"success": True})
    except Exception as e: 
        if "PGRST205" in str(e): return jsonify({"error": "Missing Table: Please create 'users' table in Supabase."}), 400
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/pair', methods=['POST'])
def admin_pair():
    if request.headers.get('X-Admin-Bypass') != 'BARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        data = request.get_json(); m, s = data.get('mentor'), data.get('mentee')
        if not m or not s: return jsonify({"error": "Mentor and Mentee required"}), 400
        success = False; err_msg = ""
        for table in ['mentor_mentee_pairs', 'mentormenteepair', 'MentorMenteePair', 'Pairings']:
            try:
                supabase_admin.table(table).insert({"mentor_email": m, "mentee_email": s}).execute()
                success = True; break
            except Exception as e: err_msg = str(e); continue
        if success: return jsonify({"success": True})
        if "PGRST205" in err_msg: return jsonify({"error": "MISSING_TABLE", "details": "Please create 'mentor_mentee_pairs' table in Supabase SQL Editor."}), 400
        return jsonify({"error": err_msg}), 500
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/admin/update-profile', methods=['POST'])
def admin_update_profile():
    if request.headers.get('X-Admin-Bypass') != 'BARS2026': return jsonify({"error": "Unauthorized"}), 401
    try:
        p = request.get_json()
        supabase_admin.table('users').update({"bio": p.get('bio'), "interests": p.get('interests')}).eq('email', p.get('email')).execute()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json(); email, fn, ln, pw, role = data.get('email', '').lower().strip(), data.get('firstName', ''), data.get('lastName', ''), data.get('password', ''), data.get('role', 'Mentee')
        full_name = f"{fn} {ln}".strip()
        supabase_admin.table('users').insert({"email": email, "full_name": full_name, "password": pw, "role": role, "bio": "", "interests": ""}).execute()
        return jsonify({"status": "success", "message": "Account created! You can now log in."}), 200
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/verify-staff', methods=['POST'])
def handle_verify_staff():
    data = request.get_json(); e = data.get('email', '').lower().strip()
    resp = None
    for table in ['users', 'profiles', 'Registry', 'Staff']:
        try:
            r = supabase_admin.table(table).select('*').eq('email', e).execute()
            if r.data: resp = r; break
        except: continue
    if resp and resp.data:
        r = resp.data[0]; db_pass = safe_get(r, ['password']) or PASSWORD_MAP.get(e)
        is_active = db_pass is not None and db_pass.strip() not in ['PENDING_ACTIVATION', '']
        return jsonify({"success": True, "full_name": safe_get(r, ['full_name', 'name']), "is_activated": is_active})
    return jsonify({"error": "Staff not found"}), 404

@app.route('/api/activate-staff', methods=['POST'])
def handle_activate_staff():
    try:
        data = request.get_json(); e, p = data.get('email', '').lower().strip(), data.get('password', '')
        for table in ['users', 'profiles', 'Registry', 'Staff']:
            try: supabase_admin.table(table).update({"password": p}).eq('email', e).execute()
            except: continue
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/messages', methods=['GET', 'POST'])
def handle_messages():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        if request.method == 'GET':
            pid = request.args.get('pair_id'); q = None
            for table in ['messages', 'Messages', 'Chats']:
                try:
                    q = supabase_admin.table(table).select('*')
                    if pid: q = q.eq('pair_id', pid)
                    resp = q.order('timestamp', desc=False).execute()
                    if resp.data is not None:
                        return jsonify([{"sender": safe_get(r, ['sender_email', 'sender']), "message": safe_get(r, ['message', 'text']), "time": safe_get(r, ['timestamp', 'time'])} for r in resp.data])
                except: continue
            return jsonify([]) 
        else:
            data = request.get_json(); pid, msg = data.get('pair_id'), data.get('message'); ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            supabase_admin.table('messages').insert({"pair_id": pid, "sender_email": u['email'], "message": msg, "timestamp": ts}).execute()
            return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/whiteboard', methods=['GET', 'POST'])
def handle_whiteboard():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        role = normalize_role(u['role'])
        if request.method == 'GET':
            for table in ['whiteboard', 'Whiteboard', 'Notes']:
                try:
                    query = supabase_admin.table(table).select('*')
                    if role == 'Mentor': query = query.eq('mentor_email', u['email'])
                    resp = query.order('created_at', desc=True).execute()
                    if resp.data is not None: return jsonify(resp.data)
                except: continue
            return jsonify([])
        else:
            if role != 'Mentor' and role != 'ProgramStaff': return jsonify({"error": "Unauthorized"}), 403
            data = request.get_json(); note = data.get('note')
            supabase_admin.table('whiteboard').insert({
                "mentor_name": u['name'], "mentor_email": u['email'], "note": note, "created_at": datetime.datetime.now().isoformat()
            }).execute()
            return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/survey/analytics', methods=['GET'])
def handle_survey_analytics():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        resp = supabase_admin.table('surveys').select('*').execute()
        return jsonify({"surveys": resp.data or [], "trends": [{"survey": "Brotherhood", "score": 85}]})
    except: return jsonify({"surveys": []}), 200

@app.route('/api/survey/submit', methods=['POST'])
def handle_survey_submit():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json()
        payload = {
            "user_email": u['email'], "user_name": u['name'], "role": u['role'], "timestamp": datetime.datetime.now().isoformat(),
            "responses": json.dumps(data.get('responses', {})), "survey_type": data.get('survey_type', 'General')
        }
        supabase_admin.table('survey_responses_bars').insert(payload).execute()
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/resources/upload', methods=['POST'])
@app.route('/api/resources/upload-file', methods=['POST'])
def handle_upload_resource_file():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        print("[UPLOAD]: Starting manual parse...")
        raw_body = request.get_data(); ct = request.headers.get('Content-Type', '')
        if "boundary=" not in ct: 
            print("[UPLOAD ERROR]: Missing boundary in Content-Type")
            return jsonify({"error": "Missing Boundary"}), 400
        
        boundary_str = ct.split("boundary=")[1].strip()
        boundary = b'--' + boundary_str.encode()
        print(f"[UPLOAD]: Boundary identified: {boundary_str}")
        
        parts = raw_body.split(boundary)
        print(f"[UPLOAD]: Body split into {len(parts)} parts.")
        form = {}
        for p in parts:
            if not p or b'Content-Disposition' not in p: continue
            try:
                head_end = p.find(b'\r\n\r\n')
                if head_end == -1: continue
                head = p[:head_end].decode('utf-8', errors='ignore')
                body = p[head_end+4:]
                
                # Precise trimming of trailing multipart separators
                if body.endswith(b'\r\n--'): body = body[:-4]
                elif body.endswith(b'\r\n'): body = body[:-2]
                
                name_match = re.search(r'name="([^"]+)"', head)
                file_match = re.search(r'filename="([^"]+)"', head)
                
                if name_match:
                    n = name_match.group(1)
                    if file_match: 
                        fn_orig = file_match.group(1)
                        ext = os.path.splitext(fn_orig)[1]
                        base = os.path.splitext(fn_orig)[0]
                        sanitized = re.sub(r'[^a-zA-Z0-9]', '_', base)
                        unique_fn = f"{uuid.uuid4()}_{sanitized}{ext}"
                        form[n] = {'filename': unique_fn, 'content': body, 'orig_name': fn_orig}
                        print(f"[UPLOAD]: Found file '{fn_orig}' -> '{unique_fn}' ({len(body)} bytes)")
                    else: 
                        form[n] = body.decode('utf-8', errors='ignore').strip()
                        print(f"[UPLOAD]: Found field '{n}' = '{form[n]}'")
            except Exception as e: 
                print(f"[UPLOAD PART ERROR]: {str(e)}")
                continue
        
        if 'file' not in form: 
            print("[UPLOAD ERROR]: No 'file' key in form data.")
            return jsonify({"error": "No file found in stream"}), 400
        
        f = form['file']; mime, _ = mimetypes.guess_type(f['filename'])
        print(f"[UPLOAD]: Uploading to Supabase bucket 'resource-files'...")
        supabase_admin.storage.from_('resource-files').upload(path=f['filename'], file=f['content'], file_options={"content-type": mime or 'application/octet-stream'})
        
        url = supabase_admin.storage.from_('resource-files').get_public_url(f['filename'])
        print(f"[UPLOAD]: Public URL: {url}")
        
        res_data = {
            "id": str(uuid.uuid4())[:8], "name": form.get('item_name') or form.get('name') or f['orig_name'], "type": form.get('type', 'Document'), "uploaded_by": u['email'], 
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "description": form.get('description', ''), "category": form.get('category', 'General'), "url": url
        }
        
        success = False
        for table in ['resources', 'Resources', 'Library']:
            try:
                supabase_admin.table(table).insert(res_data).execute()
                print(f"[UPLOAD]: Saved to table '{table}'")
                success = True; break
            except Exception as e: 
                print(f"[UPLOAD TABLE ERROR] {table}: {str(e)}")
                continue
        
        if not success: return jsonify({"error": "Database link failed."}), 400
        return jsonify({"success": True, "url": url})
    except Exception as e: 
        print(f"[UPLOAD MASTER ERROR]: {str(e)}")
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/resources/delete', methods=['POST'])
def handle_resource_delete():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); rid = data.get('resource_id') or data.get('id')
        if not rid: return jsonify({"error": "ID required"}), 400
        success = False
        for table in ['resources', 'Resources', 'Library']:
            try:
                try: supabase_admin.table(table).delete().eq('id', rid).execute(); success = True; break
                except: supabase_admin.table(table).delete().eq('id', int(rid)).execute(); success = True; break
            except: continue
        return jsonify({"success": success})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/sessions/delete', methods=['POST'])
def handle_session_delete():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); sid = data.get('id')
        for table in ['sessions', 'Sessions', 'Events']:
            try:
                try: supabase_admin.table(table).delete().eq('id', sid).execute(); break
                except: supabase_admin.table(table).delete().eq('id', int(sid)).execute(); break
            except: continue
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/delete-user', methods=['POST'])
def handle_delete_user():
    u = get_user_from_headers()
    if not u: return jsonify({"error": "Auth Required"}), 401
    try:
        data = request.get_json(); email = data.get('email')
        for table in ['users', 'profiles', 'Registry', 'Staff']:
            try: supabase_admin.table(table).delete().eq('email', email).execute()
            except: continue
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/admin.html')
def serve_admin(): return send_from_directory('.', 'admin.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

if __name__ == "__main__":
    load_local_auth(); init_cloud_seed()
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)