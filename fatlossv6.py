# KISS SHRED v5 — ultra-stable, KISS-first
# Features: persistent settings, daily workout rotation, regenerable meals, undo, exports
# Run: streamlit run fatlossv5.py

import os, sqlite3, json, datetime, uuid, re
from pathlib import Path

import pandas as pd
import streamlit as st

APP_NAME = "KISS SHRED v5"
DB_FILE = "kiss_shred_v5.db"
ROOT = Path.cwd()
EXPORTS_DIR = ROOT / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title=APP_NAME, page_icon="🔥", layout="centered")

KISS_CSS = """
<style>
  :root { --gap: 10px; --radius: 14px; --border: #2a2a2a;}
  .block-container{padding-top:1rem; padding-bottom:5.5rem; max-width: 760px;}
  .card{border:1px solid var(--border); border-radius: var(--radius); padding:12px; margin:10px 0; background:#0f0f0f;}
  .title{font-size:22px; font-weight:800; margin-bottom:8px;}
  .muted{color:#aaa;}
  .sticky-top{position:sticky; top:0; background:#0c0c0c; padding:8px 0; z-index:10; border-bottom:1px solid var(--border);}
  .sticky-bottom{position:fixed; left:0; right:0; bottom:0; background:#0c0c0c; border-top:1px solid var(--border); padding:.5rem 1rem; z-index:100;}
  .pill{display:inline-block; border:1px solid var(--border); padding:4px 10px; border-radius:999px; margin-right:6px; font-size:12px;}
  .ok{background:#22c55e22; border-color:#22c55e;}
  .warn{background:#f59e0b22; border-color:#f59e0b;}
  .bad{background:#ef444422; border-color:#ef4444;}
</style>
"""
st.markdown(KISS_CSS, unsafe_allow_html=True)

# ---------- DB ----------
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, val TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS workout_log(
        dt TEXT, day_name TEXT, exercise TEXT, sets INT, reps TEXT, rpe TEXT, session_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cardio_log(
        dt TEXT, mode TEXT, minutes INT, details TEXT, session_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sets_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, dt TEXT, session_id TEXT, exercise TEXT,
        load_lbs REAL, reps INT, rpe REAL, volume REAL, rest_sec INT, pr_flag INT DEFAULT 0, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS weight_log(dt TEXT, weight_lbs REAL, note TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS meal_log(
        rowid_alias INTEGER PRIMARY KEY AUTOINCREMENT,
        dt TEXT, source TEXT, meal TEXT, protein_g INT, kcal INT, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        session_id TEXT PRIMARY KEY, dt TEXT, start_ts TEXT, end_ts TEXT, duration_min INT, effort INT, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS undo_stack(
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, table_name TEXT, pk TEXT, payload TEXT
    )""")
    conn.commit()
    return conn

conn = get_conn()

def q(sql, params=()):
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"DB query failed: {e}")
        return pd.DataFrame()

def exec_i(sql, params=()):
    try:
        conn.execute(sql, params); conn.commit()
    except Exception as e:
        st.error(f"DB exec failed: {e}")

def set_kv(k, v): exec_i("INSERT OR REPLACE INTO settings(key,val) VALUES(?,?)",(k, json.dumps(v)))
def get_kv(k, default=None):
    row = conn.execute("SELECT val FROM settings WHERE key=?", (k,)).fetchone()
    if not row: return default
    try: return json.loads(row[0])
    except: return default

today = lambda: datetime.date.today()
today_str = lambda: today().isoformat()

# ---------- Defaults ----------
DEFAULTS = {
    "profile": {
        "name": "You",
        "height_in": 74, "sex": "M", "age": 35,
        "start_wt": 300.0, "goal_wt": 230.0,
        "protein_g": 220, "cal_target": 2600,
        "steps": 9000, "session_minutes": 75,
        "env": "Gym", "start_date": today_str(),
        "auto_phase": True, "performance_mode": True,
        "sound_ping": True,
        "lifestyle": "Balanced",
        "dislikes": ["spinach"], "allergies": [],
        "cook_time_cap": 25, "kitchen_access": "Full",
    },
    "nav": "Today",
    "last_saved": None,
}

if get_kv("_init") is None:
    for k, v in DEFAULTS.items(): set_kv(k, v)
    set_kv("_init", True)

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = get_kv(k, v)

# ---------- Data ----------
EX = {
    "Leg Press":{"area":"Lower"}, "Seated Ham Curl":{"area":"Lower"},
    "Chest Press":{"area":"Push"}, "Shoulder Press":{"area":"Push"},
    "Lat Pulldown":{"area":"Pull"}, "Seated Row":{"area":"Pull"},
    "Cable Curl":{"area":"Pull"}, "Face Pull":{"area":"Pull"},
    "Plank":{"area":"Core"}, "Pallof Press":{"area":"Core"},
    "Assault Bike":{"area":"Cond"}, "Treadmill Walk":{"area":"Cond"}
}

TEMPLATES = [
    {"name":"A Lower","blocks":[("Leg Press",5,"6-10","8-9"),("Seated Ham Curl",4,"8-12","8")], "cardio":("Treadmill Walk",20)},
    {"name":"B Push","blocks":[("Chest Press",5,"5-8","8-9"),("Shoulder Press",4,"6-10","8")], "cardio":None},
    {"name":"C Pull","blocks":[("Lat Pulldown",5,"5-8","8-9"),("Seated Row",4,"6-10","8"),("Face Pull",3,"12-15","8")], "cardio":("Assault Bike",12)},
    {"name":"D Mix","blocks":[("Chest Press",4,"6-8","8"),("Leg Press",4,"8-10","8")], "cardio":("Treadmill Walk",15)},
]

FAST_MEALS = [
    ("Chipotle Double Chicken Bowl",60,700,"No sour cream","Chipotle"),
    ("Panda Grilled Teriyaki + Super Greens + Rice",50,680,"Light sauce","Panda"),
    ("Chick-fil-A 12ct Grilled Nuggets + Side Salad",40,420,"Light dressing","Chick-fil-A"),
    ("Subway Double Chicken Bowl",55,540,"","Subway"),
    ("Starbucks Turkey Bacon Egg White + Protein Box",30,500,"","Starbucks"),
]

HOME_MEALS = [
    ("Oats + Whey + Fruit",25,380,"IF-friendly if late","Home"),
    ("Chicken, Rice, Veg",50,650,"Staple bowl","Home"),
    ("Greek Yogurt Parfait",30,320,"Low-acid","Home"),
    ("Salmon + Sweet Potato",45,600,"Recovery dinner","Home"),
]

def day_index_from_date(d: datetime.date) -> int:
    # Stable rotation per date (Mon→Sun = 0..6 mapped into 0..3)
    return (d.toordinal() % len(TEMPLATES))

def clear_day(iso: str):
    exec_i("DELETE FROM workout_log WHERE dt=?", (iso,))
    exec_i("DELETE FROM cardio_log WHERE dt=?", (iso,))

def populate_day(iso: str, template_idx: int):
    tpl = TEMPLATES[template_idx % len(TEMPLATES)]
    for ex, sets, reps, rpe in tpl["blocks"]:
        exec_i("""INSERT INTO workout_log(dt, day_name, exercise, sets, reps, rpe, session_id)
                  VALUES(?,?,?,?,?,?,?)""", (iso, tpl["name"], ex, int(sets), str(reps), str(rpe), ""))
    if tpl.get("cardio"):
        mode, mins = tpl["cardio"]
        exec_i("INSERT INTO cardio_log(dt, mode, minutes, details, session_id) VALUES(?,?,?,?,?)",
               (iso, mode, int(mins), f"Auto from {tpl['name']}", ""))

def start_session(iso: str):
    sid = uuid.uuid4().hex[:10]
    exec_i("INSERT INTO sessions(session_id, dt, start_ts) VALUES(?,?,?)",
           (sid, iso, datetime.datetime.now().isoformat(timespec="seconds")))
    set_kv("active_session", {"id": sid, "dt": iso, "start": datetime.datetime.now().isoformat(timespec="seconds")})
    exec_i("UPDATE workout_log SET session_id=? WHERE dt=? AND (session_id IS NULL OR session_id='')", (sid, iso))
    exec_i("UPDATE cardio_log SET session_id=? WHERE dt=? AND (session_id IS NULL OR session_id='')", (sid, iso))
    return sid

def end_session(effort: int, notes: str):
    active = get_kv("active_session")
    if not active: return False
    sid = active["id"]
    row = conn.execute("SELECT start_ts FROM sessions WHERE session_id=?", (sid,)).fetchone()
    if not row: set_kv("active_session", None); return False
    s_ts = datetime.datetime.fromisoformat(row[0]); e_ts = datetime.datetime.now()
    dur = max(1, int((e_ts - s_ts).total_seconds() // 60))
    exec_i("UPDATE sessions SET end_ts=?, duration_min=?, effort=?, notes=? WHERE session_id=?",
           (e_ts.isoformat(timespec="seconds"), dur, int(effort), notes, sid))
    set_kv("active_session", None)
    return True

def record_set(iso: str, exercise: str, load_lbs: float, reps: int, rpe: float, rest_sec: int, notes: str):
    sess = get_kv("active_session")
    sid = sess["id"] if sess else ""
    vol = float(load_lbs) * int(reps)
    best = q("SELECT MAX(volume) AS m FROM sets_log WHERE exercise=?", (exercise,))
    prev = float(best["m"].iloc[0]) if (not best.empty and best["m"].iloc[0] is not None) else 0.0
    pr = 1 if vol > prev else 0
    exec_i("""INSERT INTO sets_log(dt, session_id, exercise, load_lbs, reps, rpe, volume, rest_sec, pr_flag, notes)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",(iso, sid, exercise, load_lbs, reps, rpe, vol, rest_sec, pr, notes))
    return pr

def push_undo(table_name: str, pk: str, payload: dict):
    exec_i("INSERT INTO undo_stack(ts, table_name, pk, payload) VALUES(?,?,?,?)",
           (datetime.datetime.now().isoformat(timespec="seconds"), table_name, pk, json.dumps(payload)))

def undo_last():
    row = conn.execute("SELECT id, table_name, pk, payload FROM undo_stack ORDER BY id DESC LIMIT 1").fetchone()
    if not row: return False, "Nothing to undo"
    _id, table_name, pk, payload = row
    data = json.loads(payload)
    # Only support delete restoration for meal_log in v5
    if table_name == "meal_log":
        exec_i("""INSERT INTO meal_log(rowid_alias, dt, source, meal, protein_g, kcal, notes)
                  VALUES(?,?,?,?,?,?,?)""",
               (data["rowid_alias"], data["dt"], data["source"], data["meal"], data["protein_g"], data["kcal"], data["notes"]))
        exec_i("DELETE FROM undo_stack WHERE id=?", (_id,))
        return True, "Restored last deleted meal"
    return False, "Nothing to undo"

# ---------- UI ----------
st.markdown(f"<div class='sticky-top'><span class='title'>{APP_NAME}</span> <span class='pill'>KISS</span></div>", unsafe_allow_html=True)

NAV = ["Today","Program","Meals","Trends","Me"]
cols = st.columns(len(NAV))
nav = st.session_state.get("nav","Today")
for i, item in enumerate(NAV):
    if cols[i].button(item, use_container_width=True, key=f"nav_{item}"):
        st.session_state["nav"] = item; nav = item
st.markdown("<div class='sticky-bottom muted'>Today · Program · Meals · Trends · Me</div>", unsafe_allow_html=True)

# ---------- Program ----------
if nav == "Program":
    st.subheader("Program — Daily Rotation")
    prof = get_kv("profile", DEFAULTS["profile"])

    d = st.date_input("Date", value=today(), key="pgm_date")
    idx = day_index_from_date(d)
    tpl = TEMPLATES[idx]
    st.write(f"Suggested Day: **{tpl['name']}**")
    st.write(pd.DataFrame([{"Exercise":b[0], "Sets":b[1], "Reps":b[2], "RPE":b[3]} for b in tpl["blocks"]]))

    colA, colB = st.columns(2)
    with colA:
        if st.button("Load → Selected Date", use_container_width=True, key="pgm_load"):
            clear_day(d.isoformat())
            populate_day(d.isoformat(), idx)
            st.success(f"Loaded {tpl['name']} to {d.isoformat()}")
    with colB:
        if st.button("Load → TODAY", use_container_width=True, key="pgm_load_today"):
            iso = today_str()
            clear_day(iso)
            populate_day(iso, day_index_from_date(today()))
            st.success("Loaded today's plan")

# ---------- Today ----------
if nav == "Today":
    st.subheader("Today — Train")
    prof = get_kv("profile", DEFAULTS["profile"])

    d = st.date_input("Log Date", value=today(), key="tdy_date")
    iso = d.isoformat()

    # Auto ensure rotation exists
    has = q("SELECT COUNT(*) AS c FROM workout_log WHERE dt=?", (iso,))
    if int(has["c"].iloc[0]) == 0:
        clear_day(iso); populate_day(iso, day_index_from_date(d))

    plan_w = q("SELECT day_name, exercise, sets, reps, rpe FROM workout_log WHERE dt=? ORDER BY rowid", (iso,))
    plan_c = q("SELECT mode, minutes, details FROM cardio_log WHERE dt=?", (iso,))
    if plan_w.empty:
        st.warning("No workout loaded. Go to Program → Load.")
    else:
        with st.expander("Workout Plan", expanded=True):
            st.dataframe(plan_w, use_container_width=True)
        if not plan_c.empty:
            with st.expander("Cardio", expanded=False):
                st.dataframe(plan_c, use_container_width=True)

    active = get_kv("active_session")
    c1, c2, c3 = st.columns(3)
    with c1:
        if not active and st.button("▶ Start", use_container_width=True, key="tdy_start"):
            sid = start_session(iso); st.toast(f"Session {sid} started"); st.rerun()
        if active: st.caption(f"Active: {active['id']}")
    with c2:
        if active and st.button("⏹ End", use_container_width=True, key="tdy_end"):
            with st.form("end_form"):
                effort = st.slider("Effort (1–10)", 1, 10, 7, key="end_eff")
                notes = st.text_input("Notes", key="end_notes")
                if st.form_submit_button("Save & Close"):
                    if end_session(effort, notes): st.success("Saved"); st.rerun()
    with c3:
        st.caption("Tips: Enter set → Save. Undo for meals below.")

    # Quick Set Logger
    st.markdown("### Quick Set Logger")
    exs = sorted(plan_w["exercise"].unique().tolist()) if not plan_w.empty else []
    if exs:
        for i, ex in enumerate(exs):
            with st.expander(f"🏋️ {ex}", expanded=False):
                with st.form(f"setform_{iso}_{i}_{re.sub(r'[^a-z0-9]+','_',ex.lower())}"):
                    cA, cB, cC, cD = st.columns(4)
                    w = cA.number_input("Weight", 0.0, 1500.0, 100.0, 2.5, key=f"w_{iso}_{i}")
                    r = cB.number_input("Reps", 1, 30, 10, key=f"r_{iso}_{i}")
                    rp = cC.slider("RPE", 5.0, 10.0, 8.0, 0.5, key=f"rp_{iso}_{i}")
                    rest = cD.select_slider("Rest (s)", options=[30,45,60,75,90,120], value=60, key=f"rest_{iso}_{i}")
                    notes = st.text_input("Notes", key=f"notes_{iso}_{i}")
                    if st.form_submit_button("Save Set", use_container_width=True):
                        if w <= 0 or r <= 0:
                            st.error("Enter valid weight/reps")
                        else:
                            pr = record_set(iso, ex, w, int(r), float(rp), int(rest), notes)
                            st.success("Saved ✅" + ("  🎉 PR!" if pr else ""))
    else:
        st.caption("Load a plan to log sets.")

    # Weight quick log
    st.markdown("### Quick Log")
    colW, colS = st.columns(2)
    with colW:
        wv = st.number_input("Weigh-in (lb)", 0.0, 800.0, 0.0, 0.1, key=f"wt_{iso}")
        if st.button("Save Weight", key=f"save_wt_{iso}"):
            if wv > 0:
                exec_i("INSERT INTO weight_log(dt, weight_lbs, note) VALUES(?,?,?)", (iso, float(wv), ""))
                st.success("Weight saved")
            else:
                st.warning("Enter a valid weight (> 0).")
    with colS:
        st.caption("Steps/Sleep tracking removed for KISS v5 (history only via CSV import).")

# ---------- Meals ----------
if nav == "Meals":
    st.subheader("Meals — Auto + Quick")
    prof = get_kv("profile", DEFAULTS["profile"])
    iso = today_str()

    target_cal = int(prof.get("cal_target",2600))
    target_pro = int(prof.get("protein_g",220))

    with st.form("auto_meals_form"):
        colA, colB, colC = st.columns(3)
        style = colA.selectbox("Style", ["High Protein","Gastritis","Low Carb","Mediterranean","Balanced"], key="meal_style")
        budget = colB.number_input("Cal Budget", 1200, 6000, target_cal, 50, key="meal_budget")
        pgoal = colC.number_input("Protein Goal", 80, 350, target_pro, 10, key="meal_pgoal")
        excl = st.text_input("Exclude (comma)", value="spinach", key="meal_excl")
        if st.form_submit_button("Generate / Replace", use_container_width=True):
            exec_i("DELETE FROM meal_log WHERE dt=? AND source='Auto'", (iso,))
            exclusions = [x.strip().lower() for x in excl.split(",") if x.strip()]
            pool = HOME_MEALS + FAST_MEALS
            # style filters (KISS heuristics)
            def ok(name:str):
                n=name.lower()
                if any(x in n for x in exclusions): return False
                if style=="Low Carb" and any(x in n for x in ["rice","bread","wrap","pasta","potato"]): return False
                if style=="Gastritis" and any(x in n for x in ["spicy","salsa","citrus","tomato"]): return False
                return True
            pool = [m for m in pool if ok(m[0])]
            # greedy by protein density
            pool.sort(key=lambda m: (m[1]/max(m[2],1)), reverse=True)
            cur_kcal=0; cur_pro=0
            for name, p, k, note, src in pool:
                if cur_kcal >= budget - 200: break
                exec_i("INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                       (iso, "Auto", name, int(p), int(k), f"{note} • {style}"))
                cur_kcal += int(k); cur_pro += int(p)
            st.success(f"Auto plan: ~{cur_kcal} kcal / {cur_pro} g")
            st.rerun()

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Clear Auto (today)", key="ml_clear_auto", use_container_width=True):
            exec_i("DELETE FROM meal_log WHERE dt=? AND source='Auto'", (iso,)); st.rerun()
    with c2:
        if st.button("Clear ALL (today)", key="ml_clear_all", use_container_width=True):
            exec_i("DELETE FROM meal_log WHERE dt=?", (iso,)); st.rerun()
    with c3:
        if st.button("↩ Undo Delete", key="ml_undo", use_container_width=True):
            ok, msg = undo_last()
            (st.success if ok else st.info)(msg); st.rerun()

    # Quick Add
    with st.form("ml_quick_add"):
        colL, colR = st.columns(2)
        with colL:
            cat = st.selectbox("Preset Source", ["Home","Fast"], key="ml_cat")
            choices = (HOME_MEALS if cat=="Home" else FAST_MEALS)
            names = [m[0] for m in choices]
            choice = st.selectbox("Preset", names, key="ml_choice")
        with colR:
            cname = st.text_input("Custom Name", key="ml_c_name")
            cprot = st.number_input("Protein (g)", 0, 200, 40, key="ml_c_p")
            ckcal = st.number_input("Calories", 0, 1500, 600, key="ml_c_k")
            csrc = st.text_input("Source", value="Custom", key="ml_c_src")
        submit = st.form_submit_button("Add Meal", use_container_width=True)
        if submit:
            if cname.strip():
                exec_i("INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                       (iso, csrc or "Custom", cname.strip(), int(cprot), int(ckcal), ""))
                st.success("Added custom")
                st.rerun()
            else:
                # add preset
                sel = choices[names.index(choice)]
                exec_i("INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                       (iso, sel[4], sel[0], int(sel[1]), int(sel[2]), sel[3]))
                st.success("Added preset")
                st.rerun()

    # Today meals list
    meals = q("SELECT rowid_alias, dt, source, meal, protein_g, kcal, notes FROM meal_log WHERE dt=? ORDER BY rowid_alias DESC", (iso,))
    total_p = int(meals["protein_g"].sum()) if not meals.empty else 0
    total_k = int(meals["kcal"].sum()) if not meals.empty else 0
    st.markdown(f"**Totals:** {total_p} g / {total_k} kcal  · Targets: {target_pro} g / {target_cal} kcal")

    if meals.empty:
        st.caption("No meals yet")
    else:
        for _, r in meals.iterrows():
            with st.expander(f"🧾 {r['meal']} — {r['protein_g']} g / {r['kcal']} kcal  ({r['source']})", expanded=False):
                st.caption(r.get("notes") or "")
                cA, cB = st.columns(2)
                with cA:
                    if st.button("🗑 Delete", key=f"del_{int(r['rowid_alias'])}"):
                        # push to undo stack
                        push_undo("meal_log", str(int(r["rowid_alias"])), dict(r))
                        exec_i("DELETE FROM meal_log WHERE rowid_alias=?", (int(r["rowid_alias"]),))
                        st.rerun()
                with cB: st.caption(f"Logged {r['dt']}")

# ---------- Me ----------
if nav == "Me":
    st.subheader("Profile & Settings")
    prof = get_kv("profile", DEFAULTS["profile"])

    with st.form("profile_form"):
        name = st.text_input("Name", value=prof.get("name","You"), key="me_name")
        height_in = st.number_input("Height (in)", 48, 90, int(prof.get("height_in",74)), key="me_h")
        sex = st.selectbox("Sex", ["M","F"], index=0 if prof.get("sex","M")=="M" else 1, key="me_sex")
        age = st.number_input("Age", 16, 85, int(prof.get("age",35)), key="me_age")
        start_wt = st.number_input("Start Weight (lb)", 50.0, 800.0, float(prof.get("start_wt",300.0)), 0.5, key="me_sw")
        goal_wt = st.number_input("Goal Weight (lb)", 50.0, 800.0, float(prof.get("goal_wt",230.0)), 0.5, key="me_gw")
        protein_g = st.number_input("Protein Target (g)", 80, 350, int(prof.get("protein_g",220)), key="me_p")
        cal_target = st.number_input("Daily Calories", 1200, 6000, int(prof.get("cal_target",2600)), 50, key="me_k")
        steps = st.number_input("Steps Target", 2000, 30000, int(prof.get("steps",9000)), 500, key="me_steps")
        session_minutes = st.select_slider("Default Session (min)", options=[45,60,75,90], value=int(prof.get("session_minutes",75)), key="me_sess")
        env = st.selectbox("Default Environment", ["Gym","Hotel"], index=0 if prof.get("env","Gym")=="Gym" else 1, key="me_env")
        start_date = st.date_input("Journey Start Date", value=datetime.date.fromisoformat(prof.get("start_date", today_str())), key="me_sd")
        auto_phase = st.checkbox("Auto-Phase", value=prof.get("auto_phase", True), key="me_auto")
        perf = st.checkbox("Performance Mode (hide heavy UI)", value=prof.get("performance_mode", True), key="me_perf")
        sound_ping = st.checkbox("Timer Sound", value=prof.get("sound_ping", True), key="me_ping")
        lifestyle = st.selectbox("Lifestyle", ["Balanced","Mediterranean","Low Carb","Gastritis"], index=["Balanced","Mediterranean","Low Carb","Gastritis"].index(prof.get("lifestyle","Balanced")), key="me_ls")
        dislikes = st.text_input("Dislikes (comma)", value=",".join(prof.get("dislikes",[])), key="me_dis")
        allergies = st.text_input("Allergies (comma)", value=",".join(prof.get("allergies",[])), key="me_all")
        cookcap = st.slider("Max prep time (min)", 5, 60, int(prof.get("cook_time_cap",25)), key="me_cook")
        kitchen = st.selectbox("Kitchen", ["Full","Microwave","No-Cook"], index=["Full","Microwave","No-Cook"].index(prof.get("kitchen_access","Full")), key="me_kitch")

        if st.form_submit_button("Save Settings", use_container_width=True):
            prof.update({
                "name":name,"height_in":int(height_in),"sex":sex,"age":int(age),
                "start_wt":float(start_wt),"goal_wt":float(goal_wt),
                "protein_g":int(protein_g),"cal_target":int(cal_target),
                "steps":int(steps),"session_minutes":int(session_minutes),
                "env":env,"start_date":start_date.isoformat(),
                "auto_phase":bool(auto_phase),"performance_mode":bool(perf),
                "sound_ping":bool(sound_ping),"lifestyle":lifestyle,
                "dislikes":[x.strip() for x in dislikes.split(",") if x.strip()],
                "allergies":[x.strip() for x in allergies.split(",") if x.strip()],
                "cook_time_cap":int(cookcap),"kitchen_access":kitchen,
            })
            set_kv("profile", prof)
            st.toast("Saved")
            st.session_state["last_saved"] = datetime.datetime.now().isoformat(timespec="seconds")

    if st.session_state.get("last_saved"):
        st.caption(f"Saved · {st.session_state['last_saved']}")

    st.markdown("### Data")
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Export CSVs", use_container_width=True, key="exp"):
            q("SELECT * FROM workout_log").to_csv(EXPORTS_DIR/"workout_log.csv", index=False)
            q("SELECT * FROM cardio_log").to_csv(EXPORTS_DIR/"cardio_log.csv", index=False)
            q("SELECT * FROM sets_log").to_csv(EXPORTS_DIR/"sets_log.csv", index=False)
            q("SELECT * FROM weight_log").to_csv(EXPORTS_DIR/"weight_log.csv", index=False)
            q("SELECT * FROM meal_log").to_csv(EXPORTS_DIR/"meal_log.csv", index=False)
            st.success("Exports saved to /exports")
    with c2:
        if st.button("Reset TODAY", use_container_width=True, key="rst_today"):
            exec_i("DELETE FROM workout_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM cardio_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM meal_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM weight_log WHERE dt=?", (today_str(),))
            st.info("Cleared today")
    with c3:
        st.caption("Full reset not included in v5 KISS")
