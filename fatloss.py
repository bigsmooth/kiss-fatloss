# KISS SHRED 2.0 — fatloss.py (Reorganized UI + Phase 2 Upgrades)
# Mobile-first fat-loss coach...
import os, sqlite3, json, datetime, re, uuid, random, math
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ----------------------------
# App/Paths
# ----------------------------
APP_NAME = "KISS SHRED 2.1"
DB_FILE = "kiss_shred.db"
ROOT = Path.cwd()
PHOTOS_DIR = ROOT / "photos"
EXPORTS_DIR = ROOT / "exports"
PROGRAMS_DIR = ROOT / "programs"
MEALS_DIR = ROOT / "meals"
for d in (PHOTOS_DIR, EXPORTS_DIR, PROGRAMS_DIR, MEALS_DIR):
    d.mkdir(exist_ok=True)

st.set_page_config(page_title=APP_NAME, page_icon="🔥", layout="centered")
st.markdown(
    """
    <style>
      .block-container{padding-top:1rem; padding-bottom:5.5rem;}
      .sticky-bottom{position:fixed; bottom:0; left:0; right:0; background:#0f0f0f; padding:.5rem 1rem; border-top:1px solid #333;}
      .journey {border:1px solid #222;border-radius:12px;padding:10px;margin:.5rem 0;background:#0e0e0e}
      .journey span{display:inline-block;margin-right:8px;padding:4px 8px;border-radius:999px;border:1px solid #333}
      .active{background:#22c55e22;border-color:#22c55e;color:#a7f3d0}
      .muted{color:#aaa;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# DB helpers
# ----------------------------
def get_conn():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, val TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS weight_log(dt TEXT, weight_lbs REAL, note TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS workout_log(
        dt TEXT, env TEXT, system TEXT, phase TEXT, day_name TEXT,
        exercise TEXT, sets INT, reps TEXT, load TEXT, rpe TEXT, notes TEXT,
        session_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS cardio_log(
        dt TEXT, mode TEXT, minutes INT, details TEXT, session_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS meal_log(
        dt TEXT, source TEXT, meal TEXT, protein_g INT, kcal INT, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS habit_log(dt TEXT, water_oz INT, steps INT, sleep_hr REAL, notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS checkins(week_start TEXT, wins TEXT, blockers TEXT, plan TEXT, verdict TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS body_measurements(dt TEXT, waist_in REAL, chest_in REAL, hip_in REAL, thigh_in REAL, arm_in REAL, neck_in REAL, notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS pr_log(dt TEXT, env TEXT, system TEXT, lift TEXT, reps INT, load_lbs REAL, notes TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS photos(dt TEXT, view TEXT, filename TEXT, note TEXT)""")
    # sessions
    c.execute("""CREATE TABLE IF NOT EXISTS workout_sessions(
        session_id TEXT PRIMARY KEY, dt TEXT, start_ts TEXT, end_ts TEXT, duration_min INT,
        env TEXT, system TEXT, phase TEXT, day_name TEXT, perceived_effort INT, notes TEXT
    )""")
    # sets
    c.execute("""CREATE TABLE IF NOT EXISTS sets_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, dt TEXT, session_id TEXT, exercise TEXT,
        load_lbs REAL, reps INT, rpe REAL, volume REAL, rest_sec INT, pr_flag INT DEFAULT 0, notes TEXT
    )""")
    conn.commit()
    return conn

conn = get_conn()

def q(sql, params=()): return pd.read_sql_query(sql, conn, params=params)
def exec_i(sql, params=()): conn.execute(sql, params); conn.commit()
def set_kv(k,v): exec_i("INSERT OR REPLACE INTO settings(key,val) VALUES(?,?)",(k,json.dumps(v)))
def get_kv(k, default=None):
    row = conn.execute("SELECT val FROM settings WHERE key=?", (k,)).fetchone()
    if not row: return default
    try: return json.loads(row[0])
    except: return row[0]

today = lambda: datetime.date.today()
today_str = lambda: today().isoformat()

# ----------------------------
# Defaults & boot
# ----------------------------
DEFAULTS = {
    "profile": {
        "name":"Smooth","height_in":74,"sex":"M","age":35,
        "start_wt":300.0,"goal_wt":230.0,"protein_g":220,"steps":9000,
        "session_minutes":75,"env":"Gym","basketball_sun":True,
        "basketball_time":"08:00-11:00",
        "start_date": today_str(), "auto_phase": True,
        "sound_ping": True,
        # Auto Macros
        "cal_target": 2600,
        "auto_macro_adjust": True,
        "macro_anchor_wt": 300.0
    },
    "performance_mode": True,
    "nav":"Today",
    "system":"Linear",
    "phase":"M1-3"
}
if get_kv("_init") is None:
    for k,v in DEFAULTS.items(): set_kv(k,v)
    set_kv("_init", True)

for k,v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k]=get_kv(k,v)

# ----------------------------
# Library seeds
# ----------------------------
EX = {
    "Leg Press":{"env":"Gym","area":"Lower"}, "Hack Squat":{"env":"Gym","area":"Lower"},
    "Seated Ham Curl":{"env":"Gym","area":"Lower"}, "Leg Extension":{"env":"Gym","area":"Lower"},
    "Hip Abductor":{"env":"Gym","area":"Lower"}, "Calf Raise":{"env":"Gym","area":"Lower"},
    "Chest Press":{"env":"Gym","area":"Push"}, "Incline Chest Press":{"env":"Gym","area":"Push"},
    "Shoulder Press":{"env":"Gym","area":"Push"}, "Cable Fly":{"env":"Gym","area":"Push"},
    "Triceps Pressdown":{"env":"Gym","area":"Push"}, "Lat Pulldown":{"env":"Gym","area":"Pull"},
    "Seated Row":{"env":"Gym","area":"Pull"}, "Face Pull":{"env":"Gym","area":"Pull"},
    "Rear Delt Fly":{"env":"Gym","area":"Pull"}, "Cable Curl":{"env":"Gym","area":"Pull"},
    "DB RDL":{"env":"Both","area":"Lower"}, "Plank":{"env":"Both","area":"Core"},
    "Pallof Press":{"env":"Both","area":"Core"}, "Hanging Knee Raise":{"env":"Gym","area":"Core"},
    "Stir-the-Pot":{"env":"Both","area":"Core"},
    "Assault Bike":{"env":"Gym","area":"Conditioning"}, "Elliptical":{"env":"Both","area":"Conditioning"},
    "Treadmill Walk":{"env":"Both","area":"Conditioning"}, "Basketball":{"env":"Both","area":"Conditioning"},
    # Hotel DB
    "DB Goblet Squat":{"env":"Hotel","area":"Lower"}, "DB Split Squat":{"env":"Hotel","area":"Lower"},
    "DB Bench Press":{"env":"Hotel","area":"Push"}, "DB Shoulder Press":{"env":"Hotel","area":"Push"},
    "DB Row":{"env":"Hotel","area":"Pull"}, "Band Face Pull":{"env":"Hotel","area":"Pull"},
    "DB Rear Delt":{"env":"Hotel","area":"Pull"}, "Push-up":{"env":"Hotel","area":"Push"},
    "DB Calf Raise":{"env":"Hotel","area":"Lower"}
}

SWAPS = {
    "Hack Squat":["Leg Press","DB Goblet Squat"],
    "Seated Ham Curl":["DB RDL","Seated Ham Curl"],
    "Leg Extension":["DB Split Squat"],
    "Cable Fly":["Cable Fly","DB Bench Press"],
    "Seated Row":["DB Row","Seated Row"]
}

MEALS = {
    "Fast Food":[
        ("Chipotle Chicken Bowl (dbl chicken, fajita veg, salsa)",60,700,"No sour cream","Chipotle"),
        ("Panda Grilled Teriyaki + Super Greens + Rice",50,680,"Light sauce","Panda Express"),
        ("Chick-fil-A 12ct Grilled Nuggets + Side Salad",40,420,"Light dressing","Chick-fil-A"),
        ("Subway Double Chicken Bowl",55,540,"","Subway"),
        ("Starbucks Turkey Bacon Egg White + Protein Box",30,500,"","Starbucks"),
        ("Panera Warm Bowl w/ Chicken",40,650,"","Panera"),
    ],
    "Home":[
        ("Oats + Whey + Fruit",25,380,"IF-friendly if late","Home"),
        ("Chicken, Rice, Veg",50,650,"Staple bowl","Home"),
        ("Greek Yogurt Parfait",30,320,"Low-acid","Home"),
        ("Salmon + Sweet Potato",45,600,"Recovery dinner","Home"),
    ],
    "Hotel":[
        ("RTD Shake + Rice Cup",40,420,"Travel kit","Hotel"),
        ("Deli Turkey Wrap",35,480,"","Hotel"),
        ("Rotisserie Chicken + Veg Cup",50,520,"","Hotel"),
    ]
}
(PROGRAMS_DIR/"exercises.json").write_text(json.dumps(EX, indent=2))
(MEALS_DIR/"meals.json").write_text(json.dumps(MEALS, indent=2))
(PROGRAMS_DIR/"swaps.json").write_text(json.dumps(SWAPS, indent=2))

# ----------------------------
# Templates (Systems)
# ----------------------------
@dataclass
class Block:
    ex: str; sets: int; reps: str; rpe: str="7-8"; note: str=""
@dataclass
class DayTemplate:
    name: str; blocks: list; cardio: Tuple[str,int]|None=None; core: list|None=None
@dataclass
class SystemTemplate:
    name:str; env:str; phase_hint:str; session_minutes:int; rule:str; days:list; time_crunch_trim:list[str]

def _safe_ex(n:str)->str:
    if n in EX: return n
    for base, alts in SWAPS.items():
        if n==base:
            for c in alts:
                if c in EX: return c
    return n

LINEAR_GYM = SystemTemplate(
    "Linear","Gym","M1-3",75,"Top set + back-offs; double progression",
    days=[
        DayTemplate("Lower A",[
            Block(_safe_ex("Leg Press"),5,"6-10","8-9"), Block(_safe_ex("Seated Ham Curl"),4,"8-12","8"),
            Block(_safe_ex("Leg Extension"),3,"12-15","8"), Block(_safe_ex("Calf Raise"),4,"12-15","7-8")
        ], core=[Block(_safe_ex("Plank"),3,"45-60s","8")]),
        DayTemplate("Push",[
            Block(_safe_ex("Chest Press"),5,"5-8","8-9"), Block(_safe_ex("Shoulder Press"),4,"6-10","8"),
            Block(_safe_ex("Cable Fly"),3,"12-15","8"), Block(_safe_ex("Triceps Pressdown"),3,"10-12","8")
        ], core=[Block(_safe_ex("Pallof Press"),3,"10-12/side","7-8")]),
        DayTemplate("Pull",[
            Block(_safe_ex("Lat Pulldown"),5,"5-8","8-9"), Block(_safe_ex("Seated Row"),4,"6-10","8"),
            Block(_safe_ex("Face Pull"),3,"12-15","8"), Block(_safe_ex("Cable Curl"),3,"8-12","8")
        ], core=[Block(_safe_ex("Stir-the-Pot"),3,"10-12","7-8")]),
        DayTemplate("Lower B",[
            Block(_safe_ex("Hack Squat"),5,"4-6","8-9"), Block(_safe_ex("DB RDL"),4,"6-10","8"),
            Block(_safe_ex("Hip Abductor"),3,"12-15","8"), Block(_safe_ex("Calf Raise"),4,"12-15","7-8")
        ], core=[Block(_safe_ex("Plank"),3,"60s","8")]),
        DayTemplate("Conditioning + Core",
            [Block(_safe_ex("Assault Bike"),8,":20/:70","8")],
            core=[Block(_safe_ex("Pallof Press"),3,"12/side","8"), Block(_safe_ex("Hanging Knee Raise"),3,"8-12","8")],
            cardio=("Treadmill Walk",30)),
    ],
    time_crunch_trim=["Cable Fly","Rear Delt Fly","Hip Abductor","Calf Raise"]
)

LINEAR_HOTEL = SystemTemplate(
    "Linear","Hotel","M1-3",60,"Double progression; DB focus",
    days=[
        DayTemplate("Lower A",[
            Block(_safe_ex("DB Goblet Squat"),5,"6-10","8-9"), Block(_safe_ex("DB RDL"),4,"6-10","8"),
            Block(_safe_ex("DB Split Squat"),3,"8-12/leg","8"), Block(_safe_ex("DB Calf Raise"),4,"12-15","8")
        ], core=[Block(_safe_ex("Plank"),3,"45-60s","8")]),
        DayTemplate("Push",[
            Block(_safe_ex("DB Bench Press"),5,"6-10","8-9"), Block(_safe_ex("DB Shoulder Press"),4,"6-10","8"), Block(_safe_ex("Push-up"),3,"AMRAP","8")
        ], core=[Block(_safe_ex("Pallof Press"),3,"10-12/side","7-8")]),
        DayTemplate("Pull",[
            Block(_safe_ex("DB Row"),5,"6-10","8-9"), Block(_safe_ex("Band Face Pull"),3,"12-15","8"), Block(_safe_ex("DB Rear Delt"),3,"12-15","8"),
            Block(_safe_ex("Cable Curl"),3,"8-12","8") if "Cable Curl" in EX else Block(_safe_ex("DB Row"),1,"8-12","8")
        ], core=[Block(_safe_ex("Stir-the-Pot"),3,"10-12","7-8")]),
        DayTemplate("Conditioning + Core",
            [Block(_safe_ex("Elliptical"),1,"30-40 min","7-8")],
            core=[Block(_safe_ex("Pallof Press"),3,"12/side","8")],
            cardio=("Elliptical",35)),
    ],
    time_crunch_trim=["DB Rear Delt","DB Calf Raise"]
)

POWERBUILD_GYM = SystemTemplate(
    "PowerBuild","Gym","M4-6",75,"Main 4x4–6 heavy + accessories 3x8–12",
    days=[
        DayTemplate("Lower A",[Block(_safe_ex("Hack Squat"),4,"4-6","8-9"), Block(_safe_ex("Seated Ham Curl"),3,"8-12","8"), Block(_safe_ex("Leg Extension"),3,"10-15","8"), Block(_safe_ex("Calf Raise"),4,"12-15","8")]),
        DayTemplate("Upper Push",[Block(_safe_ex("Chest Press"),4,"4-6","8-9"), Block(_safe_ex("Shoulder Press"),3,"6-8","8"), Block(_safe_ex("Cable Fly"),3,"12-15","8"), Block(_safe_ex("Triceps Pressdown"),3,"10-12","8")]),
        DayTemplate("Upper Pull",[Block(_safe_ex("Lat Pulldown"),4,"4-6","8-9"), Block(_safe_ex("Seated Row"),3,"6-10","8"), Block(_safe_ex("Face Pull"),3,"12-15","8"), Block(_safe_ex("Cable Curl"),3,"8-12","8")]),
        DayTemplate("Conditioning",[Block(_safe_ex("Assault Bike"),8,":20/:70","8")], cardio=("Assault Bike",20)),
    ],
    time_crunch_trim=["Rear Delt Fly","Hip Abductor","Calf Raise"]
)

METCON_GYM = SystemTemplate(
    "MetCon","Gym","M7-9",60,"Superset strength + cardio; short rests",
    days=[
        DayTemplate("A",[Block(_safe_ex("Leg Press"),4,"8","8"), Block(_safe_ex("Assault Bike"),8,":20/:70","8"), Block(_safe_ex("Seated Ham Curl"),3,"10-12","8"), Block(_safe_ex("Plank"),3,"45-60s","8")], cardio=("Assault Bike",20)),
        DayTemplate("B",[Block(_safe_ex("Chest Press"),4,"8","8"), Block(_safe_ex("Treadmill Walk"),1,"10 min","7"), Block(_safe_ex("Lat Pulldown"),3,"8-10","8"), Block(_safe_ex("Pallof Press"),3,"12/side","8")], cardio=("Treadmill Walk",20)),
    ],
    time_crunch_trim=["Rear Delt Fly","Calf Raise"]
)

ATHLETIC_GYM = SystemTemplate(
    "Athletic","Gym","M10-12",75,"Explosive strength + skills (Sun basketball)",
    days=[
        DayTemplate("Lower Power",[Block(_safe_ex("Leg Press"),4,"5-6","8-9"), Block(_safe_ex("Seated Ham Curl"),3,"6-8","8"), Block(_safe_ex("Hack Squat"),3,"4-6","8-9")], core=[Block(_safe_ex("Pallof Press"),3,"12/side","8")]),
        DayTemplate("Upper Power",[Block(_safe_ex("Chest Press"),4,"5-6","8-9"), Block(_safe_ex("Shoulder Press"),3,"6-8","8"), Block(_safe_ex("Seated Row"),3,"6-8","8")], core=[Block(_safe_ex("Stir-the-Pot"),3,"10-12","8")]),
        DayTemplate("Skills + Mobility (Sun Basketball)",[Block(_safe_ex("Basketball"),1,"120-180 min","7-9","Sunday 8–11am")], cardio=("Basketball",150), core=[Block(_safe_ex("Pallof Press"),2,"12/side","6")]),
    ],
    time_crunch_trim=["Rear Delt Fly","Hip Abductor","Calf Raise"]
)

SYSTEMS = {
    "Linear":{"Gym":LINEAR_GYM,"Hotel":LINEAR_HOTEL},
    "PowerBuild":{"Gym":POWERBUILD_GYM,"Hotel":LINEAR_HOTEL},
    "MetCon":{"Gym":METCON_GYM,"Hotel":LINEAR_HOTEL},
    "Athletic":{"Gym":ATHLETIC_GYM,"Hotel":LINEAR_HOTEL},
}
def get_system(name, env): return SYSTEMS.get(name,{}).get(env)

# ----------------------------
# Auto-phase + Journey
# ----------------------------
PHASE_FLOW = [("M1-3","Linear"),("M4-6","PowerBuild"),("M7-9","MetCon"),("M10-12","Athletic")]
def months_since_start(iso): 
    try: start = datetime.date.fromisoformat(iso)
    except: start = today()
    return max(0,(today().year-start.year)*12+(today().month-start.month))
def current_phase_and_system(profile:dict):
    m = months_since_start(profile.get("start_date", today_str()))
    idx = min(len(PHASE_FLOW)-1, m//3)
    return PHASE_FLOW[idx]

def journey_map_html(active_idx:int):
    labels=["Linear","PowerBuild","MetCon","Athletic"]
    chips=[f"<span class='{'active' if i==active_idx else ''}'>{lbl}</span>" for i,lbl in enumerate(labels)]
    return "<div class='journey'><b>Your 12-Month Shred Roadmap:</b> "+ " ".join(chips) +"</div>"

# ----------------------------
# Populate helpers
# ----------------------------
@dataclass
class _DF:  # small utility
    data: Any

def _blocks_to_df(day: DayTemplate):
    rows=[{"Exercise":b.ex,"Sets":b.sets,"Reps":b.reps,"RPE":b.rpe,"Note":b.note} for b in day.blocks]
    if day.core:
        rows += [{"Exercise":b.ex,"Sets":b.sets,"Reps":b.reps,"RPE":b.rpe,"Note":b.note or "Core"} for b in day.core]
    return pd.DataFrame(rows)

def populate_workout_for(date_str: str, env: str, system_name: str, day_obj: DayTemplate, phase: str="Auto"):
    for b in day_obj.blocks:
        exec_i("""INSERT INTO workout_log(dt, env, system, phase, day_name, exercise, sets, reps, load, rpe, notes)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
               (date_str, env, system_name, phase, day_obj.name, b.ex, int(b.sets), str(b.reps), "", str(b.rpe), b.note or ""))
    if day_obj.core:
        for b in day_obj.core:
            exec_i("""INSERT INTO workout_log(dt, env, system, phase, day_name, exercise, sets, reps, load, rpe, notes)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                   (date_str, env, system_name, phase, day_obj.name, b.ex, int(b.sets), str(b.reps), "", str(b.rpe), b.note or "Core"))
    if day_obj.cardio:
        mode, mins = day_obj.cardio
        exec_i("INSERT INTO cardio_log(dt, mode, minutes, details) VALUES(?,?,?,?)",
               (date_str, mode, int(mins), f"From {system_name} {day_obj.name}"))

# ----------------------------
# Coach Brain (incl. Auto Macros)
# ----------------------------
def _last_n_days(n=14):
    base=today(); return [(base-datetime.timedelta(days=i)).isoformat() for i in range(n)][::-1]

def detect_weight_plateau():
    days=_last_n_days(14)
    df=q("SELECT dt, weight_lbs FROM weight_log WHERE dt>=? ORDER BY date(dt)",(days[0],))
    if df.empty or len(df)<10: return None
    vals=[v for v in df["weight_lbs"].tolist() if v is not None]
    if not vals: return None
    if max(vals)-min(vals)<=0.5: return {"type":"plateau","msg":"Weight flat ~14d. +1k steps, +15g protein, +10% cardio for 7d."}

def coach_insights():
    outs=[detect_weight_plateau()]
    tips=["Hit protein early.","Short rests, clean reps.","Add 1k steps.","Hydrate 16–24 oz pre-gym.","Pick a fast-food fallback."]
    outs.append({"type":"tip","msg":random.choice(tips)})
    return [o for o in outs if o]

def macro_adjust_if_needed():
    """If weight is ≥5 lb below anchor, calories -5% (min 1800) and protein ≈ 0.9 g/lb. Updates anchor."""
    prof = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    if not prof.get("auto_macro_adjust", True):
        return None
    anchor = float(prof.get("macro_anchor_wt", prof.get("start_wt", 0)))
    row = conn.execute("SELECT dt, weight_lbs FROM weight_log ORDER BY date(dt) DESC LIMIT 1").fetchone()
    if not row or not row[1]: return None
    cur = float(row[1])
    if cur <= anchor - 5.0:
        prev_cal = int(prof.get("cal_target", 2600))
        new_cal = int(max(1800, round(prev_cal * 0.95 / 10) * 10))
        new_pro = int(max(160, round(cur * 0.9)))
        prof["cal_target"] = new_cal
        prof["protein_g"] = new_pro
        prof["macro_anchor_wt"] = cur
        set_kv("profile", prof)
        set_kv("last_macro_adjust", {"dt": today_str(),"from_wt": anchor,"to_wt": cur,"cal_target": new_cal,"protein_g": new_pro})
        return {"cal_target": new_cal, "protein_g": new_pro, "cur": cur, "from": anchor}
    return None

# ----------------------------
# Sessions
# ----------------------------
def start_session_for(dt_iso, env, system, phase, day_name, start_ts=None):
    sid=uuid.uuid4().hex[:12]; ts=start_ts or datetime.datetime.now()
    exec_i("""INSERT INTO workout_sessions(session_id, dt, start_ts, env, system, phase, day_name)
              VALUES(?,?,?,?,?,?,?)""",(sid, dt_iso, ts.isoformat(timespec='seconds'), env, system, phase, day_name))
    set_kv("active_session", {"id":sid,"dt":dt_iso,"start_ts":ts.isoformat(timespec='seconds')})
    exec_i("UPDATE workout_log SET session_id=? WHERE dt=? AND (session_id IS NULL OR session_id='')",(sid,dt_iso))
    exec_i("UPDATE cardio_log SET session_id=? WHERE dt=? AND (session_id IS NULL OR session_id='')",(sid,dt_iso))
    return sid

def end_session(perceived_effort=7, notes="", end_ts=None):
    active=get_kv("active_session")
    if not active: return False
    sid=active["id"]
    row=conn.execute("SELECT start_ts FROM workout_sessions WHERE session_id=?", (sid,)).fetchone()
    if not row: set_kv("active_session", None); return False
    s_ts=datetime.datetime.fromisoformat(row[0]); e_ts=end_ts or datetime.datetime.now()
    dur=max(1,int((e_ts-s_ts).total_seconds()//60))
    exec_i("UPDATE workout_sessions SET end_ts=?, duration_min=?, perceived_effort=?, notes=? WHERE session_id=?",
           (e_ts.isoformat(timespec='seconds'), dur, int(perceived_effort), notes, sid))
    set_kv("active_session", None); return True

# ----------------------------
# Set Logger + PRs + Timer
# ----------------------------
def record_set(dt, session_id, exercise, load_lbs, reps, rpe, rest_sec, notes):
    volume=float(load_lbs)*int(reps)
    best=q("SELECT MAX(volume) AS m FROM sets_log WHERE exercise=?", (exercise,))
    prev=float(best["m"].iloc[0]) if (not best.empty and best["m"].iloc[0] is not None) else 0
    is_pr=1 if volume>prev else 0
    exec_i("""INSERT INTO sets_log(dt, session_id, exercise, load_lbs, reps, rpe, volume, rest_sec, pr_flag, notes)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",(dt, session_id, exercise, load_lbs, reps, rpe, volume, rest_sec, is_pr, notes))
    if is_pr: exec_i("""INSERT INTO pr_log(dt, env, system, lift, reps, load_lbs, notes) VALUES(?,?,?,?,?,?,?)""",
                      (dt, get_kv("profile",DEFAULTS["profile"]).get("env","Gym"), get_kv("system","Linear"), exercise, reps, load_lbs, "Auto PR"))
    return is_pr

def get_last_sets(exercise, limit=5):
    return q("SELECT dt, load_lbs, reps, rpe, volume, pr_flag FROM sets_log WHERE exercise=? ORDER BY date(dt) DESC, id DESC LIMIT ?",
             (exercise, limit))

def popup_timer(seconds=60, sound=True):
    audio = "https://actions.google.com/sounds/v1/alarms/alarm_clock.ogg"
    html = f"""
    <style>
      #overlay {{ position:fixed; inset:0; background:rgba(0,0,0,.85); z-index:9999;
                 display:flex;align-items:center;justify-content:center;flex-direction:column;color:#fff; }}
      #timer {{ font-size:72px; margin-bottom:16px; font-weight:800; }}
      .btns button {{ margin:0 6px; padding:10px 20px; border:none; border-radius:8px; font-size:16px; }}
    </style>
    <div id="overlay">
      <div id="timer">{seconds}</div>
      <div class="btns">
        <button onclick="skip()">Skip</button>
        <button onclick="add30()">+30s</button>
        <button onclick="done()">Done</button>
      </div>
      <audio id="beep" src="{audio}"></audio>
    </div>
    <script>
      var secs = {seconds};
      var tEl = document.getElementById('timer');
      var beep = document.getElementById('beep');
      function tick() {{
        tEl.innerText = secs;
        if(secs<=0) {{ clearInterval(t); { 'beep.play();' if sound else '' } document.body.removeChild(document.getElementById('overlay')); }}
        secs--;
      }}
      function skip() {{ clearInterval(t); document.body.removeChild(document.getElementById('overlay')); }}
      function add30() {{ secs += 30; }}
      function done() {{ clearInterval(t); document.body.removeChild(document.getElementById('overlay')); }}
      var t=setInterval(tick,1000);
    </script>
    """
    components.html(html, height=380)

# ----------------------------
# UI HEADER
# ----------------------------
st.title(f"{APP_NAME} 🔥")
st.caption("Mobile-first • Coach Mode • 12-Month Cut")

prof = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
phase_auto, sys_auto = current_phase_and_system(prof)
active_phase_index = ["M1-3","M4-6","M7-9","M10-12"].index(phase_auto)
st.markdown(journey_map_html(active_phase_index), unsafe_allow_html=True)
st.caption(f"Phase: **{phase_auto}** • Suggested system: **{sys_auto}** • Auto-Phase is {'ON' if prof.get('auto_phase',True) else 'OFF'}")

# ----------------------------
# BOTTOM NAV
# ----------------------------
NAV_ITEMS = ["Today","Program","Meals","Trends","Instructions","Me"]
col_nav = st.columns(len(NAV_ITEMS))
nav = st.session_state.get("nav","Today")
for i,item in enumerate(NAV_ITEMS):
    if col_nav[i].button(item, use_container_width=True, key=f"nav_{item}"):
        st.session_state["nav"]=item; nav=item
st.markdown('<div class="sticky-bottom muted">' + ' · '.join(NAV_ITEMS) + '</div>', unsafe_allow_html=True)

# ----------------------------
# PROGRAM
# ----------------------------
if nav=="Program":
    st.subheader("Program Loader")
    with st.expander("Auto-Phase Settings", expanded=False):
        ap = st.toggle("Auto-Phase Mode (suggest system by month)", value=prof.get("auto_phase", True), key="ap_toggle")
        if st.button("Save Auto-Phase"):
            prof["auto_phase"]=bool(ap); set_kv("profile", prof); st.success("Saved Auto-Phase setting")

    phase_suggest, system_suggest = current_phase_and_system(prof)
    env = st.selectbox("Environment", ["Gym","Hotel"], index=0 if prof.get("env","Gym")=="Gym" else 1)
    systems_list = list(SYSTEMS.keys())
    default_sys = system_suggest if prof.get("auto_phase",True) else get_kv("system","Linear")
    system_name = st.selectbox("System", systems_list, index=systems_list.index(default_sys))
    phase = st.selectbox("Phase", ["M1-3","M4-6","M7-9","M10-12","Any"],
                         index=["M1-3","M4-6","M7-9","M10-12","Any"].index(phase_suggest if prof.get("auto_phase",True) else get_kv("phase","M1-3")))
    sys_obj = get_system(system_name, env)
    day_names=[d.name for d in sys_obj.days]
    day_name = st.selectbox("Day", day_names)
    target_date = st.date_input("Date", today())
    time_crunch = st.select_slider("Time Box (min)", options=[45,60,75,90], value=prof.get("session_minutes",75))

    day_obj = next(d for d in sys_obj.days if d.name==day_name)
    st.markdown("**Preview — Exercises**")
    st.dataframe(_blocks_to_df(day_obj), use_container_width=True)
    if day_obj.cardio: st.caption(f"Cardio: {day_obj.cardio[0]} • {day_obj.cardio[1]} min")
    if time_crunch<=60 and sys_obj.time_crunch_trim: st.info("Time-crunch: accessories may be trimmed when populated.")

    c1,c2,c3 = st.columns(3)
    def _trim(day): return DayTemplate(day.name,[b for b in day.blocks if not (time_crunch<=60 and b.ex in sys_obj.time_crunch_trim)], day.cardio, day.core)
    with c1:
        if st.button("Load → TODAY", use_container_width=True):
            use_day=_trim(day_obj); populate_workout_for(today_str(), env, system_name, use_day, phase)
            set_kv("system", system_name); set_kv("phase", phase)
            prof["env"]=env; prof["session_minutes"]=time_crunch; set_kv("profile",prof)
            st.session_state["nav"]="Today"; st.rerun()
    with c2:
        if st.button("Load → Selected Date", use_container_width=True):
            use_day=_trim(day_obj); populate_workout_for(target_date.isoformat(), env, system_name, use_day, phase)
            st.success(f"Loaded {system_name}/{day_name} to {target_date}")
    with c3:
        if st.button("Clear Selected Date", use_container_width=True):
            exec_i("DELETE FROM workout_log WHERE dt=?", (target_date.isoformat(),))
            exec_i("DELETE FROM cardio_log WHERE dt=?", (target_date.isoformat(),))
            st.info("Cleared selected date.")

# ----------------------------
# SUNDAY HOOPS AUTO-INSERT
# ----------------------------
def ensure_sunday_basketball(date_iso: str):
    """Auto-insert 8–11am basketball cardio on Sundays if enabled and not already logged."""
    dt = datetime.date.fromisoformat(date_iso)
    if dt.weekday() != 6:  # Monday=0 ... Sunday=6
        return
    profile = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    if not profile.get("basketball_sun", True):
        return
    exists = conn.execute("SELECT 1 FROM cardio_log WHERE dt=? AND mode='Basketball' LIMIT 1", (date_iso,)).fetchone()
    if exists:  # don't duplicate
        return
    exec_i("INSERT INTO cardio_log(dt, mode, minutes, details) VALUES(?,?,?,?)",
           (date_iso, "Basketball", 180, "Auto-insert: Sunday 8–11am"))
    try: st.toast("🏀 Auto-added Sunday Basketball 8–11am (180m)")
    except Exception: pass

# ----------------------------
# TODAY
# ----------------------------
if nav=="Today":
    st.subheader("Today — Train, Log, Win")

    # show targets banner
    _prof = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    st.caption(f"Targets → Calories: **{int(_prof.get('cal_target',2600))}** kcal • Protein: **{int(_prof.get('protein_g',220))}** g")

    log_date = st.date_input("Log for date", value=today())
    d_iso = log_date.isoformat()

    # Sunday hoops auto-add
    ensure_sunday_basketball(d_iso)

    plan = q("SELECT env, system, phase, day_name FROM workout_log WHERE dt=? LIMIT 1", (d_iso,))
    env_guess = plan["env"].iloc[0] if not plan.empty else _prof.get("env","Gym")
    sys_guess = plan["system"].iloc[0] if not plan.empty else get_kv("system","Linear")
    phase_guess = plan["phase"].iloc[0] if not plan.empty else get_kv("phase","M1-3")
    day_guess = plan["day_name"].iloc[0] if not plan.empty else "Session"

    active = get_kv("active_session")
    cA,cB,cC = st.columns(3)
    with cA:
        if not active:
            if st.button("▶️ Start Session", use_container_width=True):
                sid = start_session_for(d_iso, env_guess, sys_guess, phase_guess, day_guess)
                st.success(f"Session started • {sid}"); st.rerun()
        else:
            st.caption(f"Active: {active['id']} • started {active['start_ts']}")
    with cB:
        if active:
            start_ts = datetime.datetime.fromisoformat(active["start_ts"])
            mins = int((datetime.datetime.now() - start_ts).total_seconds()//60)
            st.metric("Elapsed", f"{mins} min")
        else: st.metric("Elapsed","—")
    with cC:
        if active and st.button("⏹ End Session", use_container_width=True):
            st.session_state["show_end_form"]=True
    if st.session_state.get("show_end_form") and active:
        with st.form("end_form"):
            effort = st.slider("Perceived effort (1–10)", 1, 10, 7)
            notes = st.text_input("Notes", placeholder="Quads fried; next +2.5 on Chest Press.")
            if st.form_submit_button("Save & Close"):
                if end_session(effort, notes): st.success("Session saved."); st.session_state["show_end_form"]=False; st.rerun()

    ins = coach_insights()
    if ins:
        with st.expander("Coach Says", expanded=True):
            for i in ins:
                if i["type"]=="plateau": st.info("📉 "+i["msg"])
                else: st.caption("💡 "+i["msg"])

    w_today = q("SELECT day_name, exercise, sets, reps, rpe, notes FROM workout_log WHERE dt=? ORDER BY rowid", (d_iso,))
    c_today = q("SELECT mode, minutes, details FROM cardio_log WHERE dt=?", (d_iso,))
    if w_today.empty: st.warning("No workout loaded. Go to **Program** → Load → TODAY.")
    else:
        st.markdown("### Workout Plan")
        st.dataframe(w_today, use_container_width=True)
    if not c_today.empty:
        st.markdown("### Cardio Plan")
        st.dataframe(c_today, use_container_width=True)

    # Quick Set Logger
    st.markdown("### Quick Set Logger")
    rows = q("SELECT exercise FROM workout_log WHERE dt=? ORDER BY exercise", (d_iso,))
    exercises = sorted(set([str(x) for x in rows["exercise"].tolist()]))
    def _slug(s:str)->str: return re.sub(r"[^a-z0-9]+","_",s.lower()).strip("_")
    if exercises:
        for i, ex in enumerate(exercises):
            slug=_slug(ex)
            with st.expander(f"🏋️ {ex}", expanded=False):
                hist = get_last_sets(ex)
                if not hist.empty:
                    st.caption("Last sets:")
                    st.dataframe(hist, use_container_width=True)
                form_key=f"setform_{slug}_{d_iso}_{i}"
                w_key=f"w_{slug}_{d_iso}_{i}"; r_key=f"r_{slug}_{d_iso}_{i}"
                rp_key=f"rp_{slug}_{d_iso}_{i}"; rest_key=f"rest_{slug}_{d_iso}_{i}"
                n_key=f"n_{slug}_{d_iso}_{i}"
                with st.form(form_key):
                    c1,c2,c3,c4 = st.columns(4)
                    with c1: w = st.number_input("Weight", 0, 1500, 100, key=w_key)
                    with c2: r = st.number_input("Reps", 1, 30, 10, key=r_key)
                    with c3: rp = st.slider("RPE", 5.0, 10.0, 8.0, 0.5, key=rp_key)
                    with c4: rest = st.select_slider("Rest (s)", options=[30,45,60,75,90,120], value=60, key=rest_key)
                    notes = st.text_input("Notes", key=n_key, placeholder="Form, fatigue, etc.")
                    if st.form_submit_button("Save & Start Timer", use_container_width=True):
                        sess = get_kv("active_session"); sid = sess["id"] if sess else None
                        is_pr = record_set(d_iso, sid, ex, w, r, rp, rest, notes)
                        if is_pr:
                            st.success("Set saved ✅  🎉 **PR!**")
                            try: st.balloons()
                            except Exception: pass
                            st.toast(f"PR on {ex}!")
                        else:
                            st.success("Set saved ✅")
                        popup_timer(rest, sound=_prof.get("sound_ping", True))
    else: st.info("No exercises loaded for today.")

    # Quick Logs
    st.markdown("### Quick Log")
    col1,col2,col3 = st.columns(3)
    with col1:
        wt = st.number_input("Weigh-in (lb)", min_value=0.0, value=0.0, step=0.1, key="wt_today")
        if st.button("Save Weight"):
            exec_i("INSERT INTO weight_log(dt, weight_lbs, note) VALUES(?,?,?)", (d_iso, wt, ""))
            st.success("Weight saved")
            adj = macro_adjust_if_needed()
            if adj:
                st.success(f"Macros updated → {adj['cal_target']} kcal & {adj['protein_g']} g protein (at {adj['cur']} lb).")
                try: st.toast("Auto-adjusted macros (−5% cals, protein ≈ 0.9 g/lb).")
                except Exception: pass
    with col2: steps = st.number_input("Steps", min_value=0, value=8000, step=500)
    with col3: sleep = st.number_input("Sleep (h)", min_value=0.0, value=7.0, step=0.25)
    if st.button("Save Habits"): exec_i("INSERT INTO habit_log(dt, water_oz, steps, sleep_hr, notes) VALUES(?,?,?,?,?)",(d_iso, 100, steps, sleep, "PM check-in")); st.success("Habits saved")

# ----------------------------
# MEALS
# ----------------------------
if nav=="Meals":
    st.subheader("Meals — Fast & On-the-Go")
    # show current targets
    _prof = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    st.caption(f"Targets → Calories: **{int(_prof.get('cal_target',2600))}** kcal • Protein: **{int(_prof.get('protein_g',220))}** g")

    d = today_str()
    def meals_db():
        try: return json.loads((MEALS_DIR/"meals.json").read_text())
        except: return MEALS
    mdb = meals_db()
    day_meals = q("SELECT rowid, dt, source, meal, protein_g, kcal, notes FROM meal_log WHERE dt=? ORDER BY rowid DESC", (d,))
    total_p = int(day_meals["protein_g"].sum()) if not day_meals.empty else 0
    total_k = int(day_meals["kcal"].sum()) if not day_meals.empty else 0
    st.markdown(f"**Today Totals:** Protein **{total_p} g** • Calories **{total_k} kcal**")
    c1,c2 = st.columns(2)
    with c1:
        cat = st.selectbox("Category", list(mdb.keys()), index=list(mdb.keys()).index("Fast Food") if "Fast Food" in mdb else 0)
        items = mdb.get(cat, []); names=[m[0] for m in items]
        choice = st.selectbox("Preset", names) if names else None
        if st.button("Add Preset", use_container_width=True) and choice:
            m = items[names.index(choice)]
            exec_i("INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                   (d, m[4], m[0], int(m[1]), int(m[2]), m[3])); st.success("Added meal preset")
    with c2:
        st.markdown("**Custom Meal**")
        cname = st.text_input("Name", placeholder="Chicken bowl")
        cprot = st.number_input("Protein (g)", 0, 200, 40)
        ckcal = st.number_input("Calories", 0, 1500, 600)
        csrc = st.text_input("Source/Place", placeholder="Home / Chipotle / Panda …")
        cnote = st.text_input("Notes", placeholder="No sauce, extra veggies")
        if st.button("Add Custom", use_container_width=True) and cname:
            exec_i("INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                   (d, csrc or "Custom", cname, int(cprot), int(ckcal), cnote)); st.success("Added custom meal")
    st.markdown("### Today’s Meals")
    day_meals = q("SELECT rowid, dt, source, meal, protein_g, kcal, notes FROM meal_log WHERE dt=? ORDER BY rowid DESC", (d,))
    st.dataframe(day_meals, use_container_width=True)

# ----------------------------
# TRENDS (+ charts + weekly PR recap)
# ----------------------------
if nav=="Trends":
    st.subheader("Trends — Progress at a Glance")

    # Weight 60d line
    since60 = (today() - datetime.timedelta(days=60)).isoformat()
    w = q("SELECT dt, weight_lbs FROM weight_log WHERE dt>=? ORDER BY date(dt)", (since60,))
    if not w.empty:
        st.markdown("**Weight (last 60 days)**")
        w2 = w.set_index("dt")["weight_lbs"]
        st.line_chart(w2)
        st.caption(f"Latest: **{round(w2.dropna().iloc[-1],1)} lb**") if not w2.dropna().empty else None
    else:
        st.caption("No weight entries yet.")

    # Protein 14d bars
    since14 = (today() - datetime.timedelta(days=14)).isoformat()
    m = q("SELECT dt, protein_g FROM meal_log WHERE dt>=?", (since14,))
    if not m.empty:
        st.markdown("**Daily Protein (last 14 days)**")
        idx = [ (today()-datetime.timedelta(days=i)).isoformat() for i in range(13,-1,-1) ]
        prot = m.groupby("dt")["protein_g"].sum().reindex(idx, fill_value=0)
        st.bar_chart(prot)
    else:
        st.caption("No meals logged in the last 14 days.")

    # Cardio minutes per week (8w) bars
    since56 = (today() - datetime.timedelta(days=56)).isoformat()
    c = q("SELECT dt, minutes FROM cardio_log WHERE dt>=?", (since56,))
    if not c.empty:
        st.markdown("**Cardio Minutes (last 8 weeks)**")
        c["week"] = c["dt"].apply(lambda x: datetime.date.fromisoformat(x).isocalendar().week)
        weekly = c.groupby("week")["minutes"].sum()
        st.bar_chart(weekly)
    else:
        st.caption("No cardio logged in the last 8 weeks.")

    # Weekly PR recap
    st.markdown("### Weekly PR Recap")
    since7 = (today() - datetime.timedelta(days=7)).isoformat()
    prs7 = q("SELECT dt, lift, load_lbs, reps FROM pr_log WHERE dt>=? ORDER BY date(dt) DESC, load_lbs DESC", (since7,))
    if prs7.empty:
        st.caption("No PRs this week yet — go hunt one today 🔥")
    else:
        st.dataframe(prs7, use_container_width=True)
        st.success(f"🔥 **{len(prs7)} PRs** in the last 7 days. Keep smashing!")

# ----------------------------
# INSTRUCTIONS
# ----------------------------
if nav=="Instructions":
    st.subheader("How to Use KISS SHRED 2.1")
    st.markdown("""
**12-Month Flow**  
• **M1–3:** Linear • **M4–6:** PowerBuild (or GVT) • **M7–9:** MetCon • **M10–12:** Athletic

**Daily**  
1) Program → **Load → TODAY**  
2) Today → **Start Session** → train → **End Session**  
3) Log a few sets with the **Quick Set Logger**  
4) Meals → add fast-food preset if needed

**Rules**  
Protein **0.8–1.0 g/lb** • Steps **8–12k** • Cardio 2–4×20–30 min • Sleep **7+ h**  
Plateau 14d? **+1k steps, +15g protein, +10% cardio** for 7d.

**Auto Macros**  
When your latest weigh-in is **≥ 5 lb** below your last anchor, the app adjusts:  
• Calories **−5%** (never below **1800**)  
• Protein ≈ **0.9 g/lb** current.  
Toggle in **Me**.
""")

# ----------------------------
# ME (Profile / Export)
# ----------------------------
if nav=="Me":
    st.subheader("Me — Profile & Settings")
    with st.form("profile_form"):
        name = st.text_input("Name", value=prof.get("name","Smooth"))
        height_in = st.number_input("Height (in)", 48, 90, int(prof.get("height_in",74)))
        sex = st.selectbox("Sex", ["M","F"], index=0 if prof.get("sex","M")=="M" else 1)
        age = st.number_input("Age", 16, 85, int(prof.get("age",35)))
        start_wt = st.number_input("Start Weight (lb)", 50.0, 800.0, float(prof.get("start_wt",300.0)), step=0.5)
        goal_wt = st.number_input("Goal Weight (lb)", 50.0, 800.0, float(prof.get("goal_wt",230.0)), step=0.5)
        protein_g = st.number_input("Protein Target (g)", 80, 350, int(prof.get("protein_g",220)))
        cal_target = st.number_input("Daily Calories Target", 1200, 6000, int(prof.get("cal_target", 2600)), step=50)
        steps = st.number_input("Steps Target", 2000, 30000, int(prof.get("steps",9000)), step=500)
        session_minutes = st.select_slider("Default Session (min)", options=[45,60,75,90], value=int(prof.get("session_minutes",75)))
        env = st.selectbox("Default Environment", ["Gym","Hotel"], index=0 if prof.get("env","Gym")=="Gym" else 1)
        start_date = st.date_input("Journey Start Date", value=datetime.date.fromisoformat(prof.get("start_date", today_str())))
        auto_phase = st.checkbox("Auto-Phase Mode", value=prof.get("auto_phase", True))
        auto_adj = st.checkbox("Auto-Adjust Macros when weight drops ≥ 5 lb", value=prof.get("auto_macro_adjust", True))
        sound_ping = st.checkbox("Timer Sound Ping", value=prof.get("sound_ping", True))
        perf = st.checkbox("Performance Mode (fast Today screen)", value=get_kv("performance_mode", True))
        basketball_sun = st.checkbox("Sunday Basketball 8–11am", value=prof.get("basketball_sun", True))

        # optional re-anchor button
        st.caption(f"Macro anchor: **{round(float(prof.get('macro_anchor_wt', prof.get('start_wt', 0))),1)} lb**")
        if st.form_submit_button("Save Profile"):
            prof.update({
                "name":name,"height_in":int(height_in),"sex":sex,"age":int(age),
                "start_wt":float(start_wt),"goal_wt":float(goal_wt),
                "protein_g":int(protein_g),"cal_target":int(cal_target),
                "steps":int(steps),"session_minutes":int(session_minutes),"env":env,
                "basketball_sun":bool(basketball_sun),"start_date":start_date.isoformat(),
                "auto_phase":bool(auto_phase),"sound_ping":bool(sound_ping),
                "auto_macro_adjust": bool(auto_adj),
                "macro_anchor_wt": float(prof.get("macro_anchor_wt", start_wt))
            })
            set_kv("profile", prof); set_kv("performance_mode", bool(perf)); st.success("Saved profile & settings")

    st.markdown("### Data & Backup")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Export CSVs", use_container_width=True):
            EXPORTS_DIR.mkdir(exist_ok=True)
            q("SELECT * FROM weight_log").to_csv(EXPORTS_DIR/"weight_log.csv", index=False)
            q("SELECT * FROM workout_log").to_csv(EXPORTS_DIR/"workout_log.csv", index=False)
            q("SELECT * FROM cardio_log").to_csv(EXPORTS_DIR/"cardio_log.csv", index=False)
            q("SELECT * FROM meal_log").to_csv(EXPORTS_DIR/"meal_log.csv", index=False)
            q("SELECT * FROM habit_log").to_csv(EXPORTS_DIR/"habit_log.csv", index=False)
            q("SELECT * FROM checkins").to_csv(EXPORTS_DIR/"checkins.csv", index=False)
            q("SELECT * FROM body_measurements").to_csv(EXPORTS_DIR/"body_measurements.csv", index=False)
            q("SELECT * FROM pr_log").to_csv(EXPORTS_DIR/"pr_log.csv", index=False)
            st.success("Exports saved to /exports")
    with c2:
        if st.button("Reset TODAY only", use_container_width=True):
            exec_i("DELETE FROM workout_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM cardio_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM meal_log WHERE dt=?", (today_str(),))
            st.info("Cleared today’s entries")
    with c3:
        if st.button("⚠️ Full Reset (ALL data)", use_container_width=True):
            st.warning("This deletes ALL data. Type DELETE below and press Confirm.")
            val = st.text_input("Type DELETE to confirm", key="confirm_del")
            if val=="DELETE":
                conn.close()
                try: os.remove(DB_FILE); st.success("Database removed. Restart the app.")
                except Exception as e: st.error(f"Could not remove database: {e}")