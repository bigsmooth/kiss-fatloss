# KISS SHRED 2.2 — fatloss.py (Final Full App)
# See header comments for features & deploy notes.

import os, sqlite3, json, datetime, re, uuid, random, math, sys
from pathlib import Path
from dataclasses import dataclass
from typing import Tuple, Any, Dict, List

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

APP_NAME = "KISS SHRED 2.2"
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
      .block-container{padding-top:1rem; padding-bottom:5.5rem; max-width: 760px;}
      .sticky-bottom{position:fixed; bottom:0; left:0; right:0; background:#0f0f0f; padding:.5rem 1rem; border-top:1px solid #333;}
      .journey {border:1px solid #222;border-radius:12px;padding:10px;margin:.5rem 0;background:#0e0e0e}
      .journey span{display:inline-block;margin-right:8px;padding:4px 8px;border-radius:999px;border:1px solid #333}
      .active{background:#22c55e22;border-color:#22c55e;color:#a7f3d0}
      .muted{color:#aaa;}
      .badge{display:inline-block; padding:4px 8px; border:1px solid #333; border-radius:999px; margin-right:6px; font-size:12px}
      .good{background:#22c55e22; border-color:#22c55e;}
      .warn{background:#f59e0b22; border-color:#f59e0b;}
      .bad{background:#ef444422; border-color:#ef4444;}
    </style>
    """,
    unsafe_allow_html=True,
)

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
    c.execute("""CREATE TABLE IF NOT EXISTS workout_sessions(
        session_id TEXT PRIMARY KEY, dt TEXT, start_ts TEXT, end_ts TEXT, duration_min INT,
        env TEXT, system TEXT, phase TEXT, day_name TEXT, perceived_effort INT, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS sets_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, dt TEXT, session_id TEXT, exercise TEXT,
        load_lbs REAL, reps INT, rpe REAL, volume REAL, rest_sec INT, pr_flag INT DEFAULT 0, notes TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS meal_prefs(
        id INTEGER PRIMARY KEY, plan TEXT, dislikes TEXT, allergies TEXT, kcal_target INT, protein_target INT
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

def set_kv(k,v): exec_i("INSERT OR REPLACE INTO settings(key,val) VALUES(?,?)",(k,json.dumps(v)))
def get_kv(k, default=None):
    row = conn.execute("SELECT val FROM settings WHERE key=?", (k,)).fetchone()
    if not row: return default
    try: return json.loads(row[0])
    except: return row[0]

today = lambda: datetime.date.today()
today_str = lambda: today().isoformat()

DEFAULTS = {
    "profile": {
        "name": "Smooth",
        "height_in": 74,
        "sex": "M",
        "age": 35,
        "start_wt": 300.0,
        "goal_wt": 230.0,
        "protein_g": 220,
        "steps": 9000,
        "session_minutes": 75,
        "env": "Gym",
        "basketball_sun": True,
        "basketball_time": "08:00-11:00",
        "start_date": today_str(),
        "auto_phase": True,
        "sound_ping": True,
        "cal_target": 2600,
        "auto_macro_adjust": True,
        "macro_anchor_wt": 300.0,

        # 🔥 NEW meal personalization fields
        "lifestyle": "Mediterranean Reset",   # or: Pescatarian Flow, Power Build, Gastritis Gentle, Low-Carb Shred, Paleo Core
        "dislikes": ["spinach"],              # user food dislikes
        "allergies": [],                      # e.g., ["eggs", "shellfish"]
        "cook_time_cap": 25,                  # max minutes they'll cook
        "kitchen_access": "Full",             # "Full", "Microwave", "No-Cook"
    },

    "performance_mode": True,
    "nav": "Today",
    "system": "Linear",
    "phase": "M1-3"
}



if get_kv("_init") is None:
    for k,v in DEFAULTS.items(): set_kv(k,v)
    set_kv("_init", True)

for k,v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k]=get_kv(k,v)

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
        ("Big-Ass Salad (chicken, greens, olive oil)",45,520,"Mediterranean-ish","Home"),
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

def _blocks_to_df(day: DayTemplate):
    rows=[{"Exercise":b.ex,"Sets":b.sets,"Reps":b.reps,"RPE":b.rpe,"Note":b.note} for b in day.blocks]
    if day.core:
        rows += [{"Exercise":b.ex,"Sets":b.sets,"Reps":b.reps,"RPE":b.rpe,"Note":b.note or "Core"} for b in day.core]
    return pd.DataFrame(rows)

def clear_day(date_iso: str):
    exec_i("DELETE FROM workout_log WHERE dt=?", (date_iso,))
    exec_i("DELETE FROM cardio_log WHERE dt=?", (date_iso,))

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
    since7=(today()-datetime.timedelta(days=7)).isoformat()
    prs=q("SELECT COUNT(*) as c FROM pr_log WHERE dt>=?",(since7,))
    prc=int(prs['c'].iloc[0]) if not prs.empty else 0
    if prc>=3: outs.append({"type":"badge","msg":"PR Hunter (3+ this week)"})
    w5=q("SELECT COUNT(*) as c FROM weight_log WHERE dt>=?",((today()-datetime.timedelta(days=5)).isoformat(),))
    wc=int(w5['c'].iloc[0]) if not w5.empty else 0
    if wc>=5: outs.append({"type":"badge","msg":"Scale Streak (5-day)"})
    return [o for o in outs if o]

# ----------------------------
# AutoMeal Engine (50+ meals/lifestyle via smart generators)
# ----------------------------
LIFESTYLES = [
    "Power Build","Mediterranean Reset","Pescatarian Flow",
    "Gastritis Gentle","Low-Carb Shred","Paleo Core"
]

def _contains_any(text, words):
    t = text.lower()
    for w in words or []:
        if w.strip().lower() in t:
            return True
    return False

def _fits_tools(meal, kitchen_access):
    tool = meal.get("tool","Full")
    if kitchen_access == "Full": return True
    if kitchen_access == "Microwave": return tool in ["Microwave","No-Cook"]
    if kitchen_access == "No-Cook": return tool == "No-Cook"
    return True

def _approx_kcal(p, c, f):  # basic macro → kcal
    return int(p*4 + c*4 + f*9)

def _mk(meal, p, c, f, cat, tool, notes="", tags=None, prep=15):
    return {
        "name": meal, "category": cat, "protein": p, "carbs": c, "fat": f,
        "kcal": _approx_kcal(p,c,f), "prep_min": prep, "tool": tool,
        "notes": notes, "tags": tags or []
    }

def _gen_pool_for(lifestyle:str):
    """Return a list of 60–90 candidate meals for a lifestyle; we’ll filter to ~50."""
    L = []

    if lifestyle == "Mediterranean Reset":
        base = [
            _mk("Greek yogurt, berries, honey, walnuts", 30,35,12,"Breakfast","No-Cook","Anti-inflammatory",["med"]),
            _mk("Olive-oil egg scramble, tomato, feta, pita", 28,30,18,"Breakfast","Full","Herb + lemon",["med"]),
            _mk("Salmon, couscous, roasted zucchini + olive oil", 42,48,18,"Dinner","Full","Lemon zest",["med","fish"]),
            _mk("Chicken souvlaki bowl (brown rice, cucumber, tzatziki)", 40,55,12,"Lunch","Full","Tzatziki light",["med"]),
            _mk("Tuna bean salad (olive oil, parsley, lemon) + crackers", 35,40,14,"Lunch","No-Cook","Pantry-friendly",["med","fish"]),
            _mk("Shrimp, orzo, spinach, cherry tomato, olive oil", 38,52,14,"Dinner","Full","Add capers if you like",["med","fish"]),
            _mk("Lentil tomato soup + whole grain bread", 24,45,8,"Lunch","Full","Garlic + oregano",["med"]),
            _mk("Chickpea veggie bowl w/ tahini", 22,50,16,"Lunch","No-Cook","Tahini drizzle",["med","veg"]),
            _mk("Sardine avocado toast (lemon + herbs)", 35,30,20,"Snack","No-Cook","Omega-3 boost",["med","fish"]),
            _mk("Halloumi salad (olives, tomato, cukes) + olive oil", 26,18,20,"Lunch","Full","Grill halloumi",["med"]),
        ]
        # Expand variants quickly
        for b in base:
            L.append(b)
            L.append({**b, "name": b["name"]+" (quinoa swap)", "carbs": b["carbs"]+10, "kcal": _approx_kcal(b["protein"], b["carbs"]+10, b["fat"])})
            L.append({**b, "name": b["name"]+" (extra veg)", "carbs": max(10,b["carbs"]-8), "kcal": _approx_kcal(b["protein"], max(10,b["carbs"]-8), b["fat"])})
        # Add quick/portable snacks
        L += [
            _mk("Cottage cheese + cherry tomatoes + olive oil", 28,12,10,"Snack","No-Cook","Salt + pepper",["med"]),
            _mk("Hummus + veg + whole grain pita", 14,40,12,"Snack","No-Cook","Add lemon",["med","veg"])
        ]

    if lifestyle == "Pescatarian Flow":
        base = [
            _mk("Smoked salmon, light cream cheese, capers on whole grain", 32,34,14,"Breakfast","No-Cook","Lemon squeeze",["fish"]),
            _mk("Shrimp stir-fry (frozen veg) over jasmine rice", 36,60,10,"Dinner","Full","Fast skillet",["fish"]),
            _mk("Seared tuna, brown rice, sesame cukes", 42,45,12,"Dinner","Full","Soy/ginger light",["fish"]),
            _mk("Greek yogurt + chia + mango", 28,40,8,"Breakfast","No-Cook","Chia boost",["med"]),
            _mk("Sardine tomato pasta (olive oil + parsley)", 35,62,16,"Dinner","Full","Pantry pasta",["fish"]),
            _mk("Canned salmon salad wrap", 38,35,14,"Lunch","No-Cook","Dijon + dill",["fish"]),
            _mk("Miso cod + rice + steamed broccoli", 40,48,10,"Dinner","Full","Sheet pan",["fish"]),
        ]
        for b in base:
            L.append(b)
            L.append({**b, "name": b["name"]+" (low-carb swap)", "carbs": max(12,b["carbs"]-25), "fat": b["fat"]+2, "kcal": _approx_kcal(b["protein"], max(12,b["carbs"]-25), b["fat"]+2)})
            L.append({**b, "name": b["name"]+" (15-min version)", "prep_min": 15})
        L += [
            _mk("Protein smoothie (whey, banana, spinach, water/ice)", 32,28,4,"Snack","No-Cook","Travel-ready",["shaker"]),
            _mk("RTD shake + rice cup + nori", 30,40,5,"Snack","Microwave","Hotel hack",["travel"])
        ]

    if lifestyle == "Power Build":
        base = [
            _mk("Egg white scramble + turkey + oats", 45,45,8,"Breakfast","Full","Cinnamon in oats",["bulk"]),
            _mk("Chicken, rice, green beans, olive oil", 45,55,12,"Lunch","Full","Staple bowl",["bulk"]),
            _mk("Lean beef + potato + asparagus", 45,45,15,"Dinner","Full","Salt & pepper",["bulk"]),
            _mk("Greek yogurt + whey + berries", 45,35,5,"Snack","No-Cook","Fast protein",["bulk"]),
        ]
        for b in base:
            L.append(b)
            L.append({**b, "name": b["name"]+" (extra protein)", "protein": b["protein"]+10, "kcal": _approx_kcal(b["protein"]+10, b["carbs"], b["fat"])})
            L.append({**b, "name": b["name"]+" (lower fat)", "fat": max(3,b["fat"]-6), "kcal": _approx_kcal(b["protein"], b["carbs"], max(3,b["fat"]-6))})

    if lifestyle == "Gastritis Gentle":
        base = [
            _mk("Overnight oats (almond milk) + banana", 18,45,8,"Breakfast","No-Cook","Low-acid",["gg"]),
            _mk("Poached chicken + white rice + zucchini", 40,50,6,"Lunch","Full","Very gentle",["gg"]),
            _mk("Baked cod + mashed potato + carrots", 38,45,7,"Dinner","Full","No spice",["gg"]),
            _mk("Greek yogurt (plain) + honey", 20,25,3,"Snack","No-Cook","Small portions",["gg"]),
            _mk("Turkey deli wrap (spinach-free) + rice crisps", 32,40,8,"Lunch","No-Cook","Light mustard",["gg"]),
        ]
        L += base + [ {**b, "name": b["name"]+" (microwave)", "tool":"Microwave"} for b in base ]

    if lifestyle == "Low-Carb Shred":
        base = [
            _mk("Egg scramble + avocado + salsa", 28,12,22,"Breakfast","Full","Salsa mild",["lc"]),
            _mk("Chicken salad (olive oil + lemon) over greens", 40,10,18,"Lunch","No-Cook","Crisp veggies",["lc"]),
            _mk("Salmon + asparagus + butter", 42,8,20,"Dinner","Full","Lemon zest",["lc","fish"]),
            _mk("Cottage cheese + cucumber", 28,8,6,"Snack","No-Cook","Salt/pepper",["lc"]),
        ]
        for b in base:
            L.append(b)
            L.append({**b, "name": b["name"]+" (very-low-carb)", "carbs": max(4,b["carbs"]-6), "kcal": _approx_kcal(b["protein"], max(4,b["carbs"]-6), b["fat"])})

    if lifestyle == "Paleo Core":
        base = [
            _mk("Scrambled eggs + berries + nuts", 24,18,20,"Breakfast","Full","No grains",["paleo"]),
            _mk("Grilled chicken + roasted sweet potato + broccoli", 42,36,10,"Lunch","Full","Olive oil",["paleo"]),
            _mk("Beef patty + greens + olive oil + olives", 35,8,24,"Dinner","Full","No bun",["paleo"]),
            _mk("Apple + almonds", 6,22,14,"Snack","No-Cook","Simple",["paleo"]),
        ]
        for b in base:
            L.append(b)
            L.append({**b, "name": b["name"]+" (sheet-pan quick)", "prep_min": 15})

    # Guarantee enough variety
    # If < 60 items, echo variations to reach 60–90
    while len(L) < 60:
        for item in list(L):
            if len(L) >= 60: break
            L.append({**item, "name": item["name"]+" *alt*", "prep_min": max(10, item["prep_min"]-5)})

    return L

def build_auto_plan(profile, training_day=True):
    """
    Returns a list of 3–4 meals tailored to lifestyle, dislikes/allergies, tools, time,
    and macro targets (higher carbs on training days).
    """
    lifestyle = profile.get("lifestyle","Mediterranean Reset")
    dislikes = profile.get("dislikes",[])
    allergies = profile.get("allergies",[])
    cap = int(profile.get("cook_time_cap",25))
    kitchen = profile.get("kitchen_access","Full")
    p_target = int(profile.get("protein_g", 200))
    kcal_target = int(profile.get("cal_target", 2400)) if "cal_target" in profile else 2400

    pool = _gen_pool_for(lifestyle)

    # filter: dislikes/allergies, tools, time
    filt = []
    banned = set(x.lower() for x in (dislikes or []) + (allergies or []))
    for m in pool:
        name = m["name"]
        if _contains_any(name, banned): 
            continue
        if not _fits_tools(m, kitchen): 
            continue
        if m["prep_min"] > cap: 
            continue
        filt.append(m)

    # training day bias: allow +15–20% carbs; rest day: trim carbs
    def adjust_for_day(m):
        m = dict(m)
        if training_day:
            m["carbs"] = int(m["carbs"] * 1.15)
        else:
            m["carbs"] = max(8, int(m["carbs"] * 0.85))
        m["kcal"] = _approx_kcal(m["protein"], m["carbs"], m["fat"])
        return m

    filt = [adjust_for_day(m) for m in filt]

    # greedy pick: 4 meals, prioritize protein coverage, then calories
    day = []
    p_sum = 0; kcal_sum = 0
    buckets = {"Breakfast":[], "Lunch":[], "Dinner":[], "Snack":[]}
    for m in filt:
        buckets[m["category"]].append(m)

    def pick(cat, target_p_left):
        cand = sorted(buckets.get(cat,[]), key=lambda x: (abs(x["protein"]-target_p_left), abs(x["kcal"]-kcal_target/4)))
        return cand[0] if cand else None

    # Aim for 4 touches: B/L/D + Snack
    for cat in ["Breakfast","Lunch","Dinner","Snack"]:
        need_p = max(0, p_target - p_sum)
        m = pick(cat, need_p/ (1 if cat=="Snack" else 2))
        if m:
            day.append(m)
            p_sum += m["protein"]; kcal_sum += m["kcal"]

    # If protein still low, add one extra snack
    if p_sum < 0.9*p_target:
        extra = pick("Snack", p_target - p_sum)
        if extra: 
            day.append(extra); p_sum += extra["protein"]; kcal_sum += extra["kcal"]

    # Final cap: 3–5 meals
    return day[:5]



def macro_adjust_if_needed():
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

DIET_TYPES = ["Gastritis-Friendly","High Protein / Low Fat","Low Carb","Mediterranean","Paleo","Balanced"]
DEFAULT_EXCLUSIONS = ["lentils"]

MEAL_TEMPLATES = {
    "Gastritis-Friendly": [
        ("Greek Yogurt + Honey + Banana", 20, 300, "Avoid citrus; low-acid"),
        ("Oatmeal + Whey + Blueberries", 30, 420, "Cooked oats; skip cinnamon if sensitive"),
        ("Chicken + Rice + Zucchini", 45, 620, "Low spice"),
        ("Salmon + Sweet Potato + Spinach", 45, 620, "Use olive oil light"),
    ],
    "High Protein / Low Fat": [
        ("Egg Whites Scramble + Toast", 28, 300, "Add salsa if tolerated"),
        ("Chicken Bowl (rice + veggies)", 55, 650, "Chipotle or home"),
        ("Nonfat Greek Yogurt Parfait", 30, 320, "Berries + honey"),
        ("Grilled Shrimp + Veg", 35, 450, "Lemon/garlic"),
    ],
    "Low Carb": [
        ("Protein Shake + Almonds", 40, 380, "Unsweetened"),
        ("Chicken + Greens + Olive Oil", 50, 520, "Big salad"),
        ("Bunless Burger + Veg", 40, 600, "Lean beef or turkey"),
        ("Egg/White Omelet + Veg", 30, 350, "Avoid heavy cheese"),
    ],
    "Mediterranean": [
        ("Greek Omelet (feta, tomato)", 28, 420, "If dairy OK"),
        ("Chicken + Quinoa + Tabbouleh", 45, 620, "Olive oil + lemon"),
        ("Salmon + Farro + Greens", 45, 650, "Herbs"),
        ("Yogurt + Nuts + Fruit", 25, 400, "Olive oil drizzle"),
    ],
    "Paleo": [
        ("Eggs + Fruit + Nuts", 25, 550, "No grains"),
        ("Chicken + Roasted Veg", 45, 580, "Olive oil"),
        ("Shrimp + Cauli Rice", 40, 480, "Garlic/herbs"),
        ("Steak + Greens + Avocado", 45, 700, "Lean cut"),
    ],
    "Balanced": [
        ("Oats + Whey + Fruit", 25, 380, ""),
        ("Chicken, Rice, Veg", 50, 650, ""),
        ("Turkey Wrap + Fruit", 35, 520, ""),
        ("Salmon + Sweet Potato", 45, 600, ""),
    ],
}
def generate_meal_plan(diet: str, kcal_target: int, protein_target: int, dislikes: List[str], allergies: List[str]) -> List[Dict[str, Any]]:
    pool = MEAL_TEMPLATES.get(diet, MEAL_TEMPLATES["Balanced"]).copy()
    pool += [(name, p, k, f"Fast: {place}") for (name, p, k, _, place) in MEALS["Fast Food"]]
    def unacceptable(name: str) -> bool:
        low = name.lower()
        for bad in dislikes + allergies:
            if bad.strip() and bad.lower() in low:
                return True
        return False
    filtered = [m for m in pool if not unacceptable(m[0])]
    if not filtered: filtered = pool
    plan = []
    rem_p = protein_target; rem_k = kcal_target
    filtered.sort(key=lambda x: (-x[1], x[2]))
    for name, p, k, note in filtered:
        if rem_p <= 0 and rem_k <= 0: break
        if p < 20 and rem_p > 30:  # skip tiny protein entries early
            continue
        plan.append({"meal": name, "protein_g": p, "kcal": k, "notes": note})
        rem_p -= p; rem_k -= k
        if len(plan) >= 5: break
    while len(plan) < 3 and filtered:
        pick = filtered[len(plan) % len(filtered)]
        plan.append({"meal": pick[0], "protein_g": pick[1], "kcal": pick[2], "notes": pick[3]})
    return plan

def ensure_sunday_basketball(date_iso: str):
    dt = datetime.date.fromisoformat(date_iso)
    if dt.weekday() != 6: return
    profile = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    if not profile.get("basketball_sun", True): return
    exists = conn.execute("SELECT 1 FROM cardio_log WHERE dt=? AND mode='Basketball' LIMIT 1", (date_iso,)).fetchone()
    if exists: return
    exec_i("INSERT INTO cardio_log(dt, mode, minutes, details) VALUES(?,?,?,?)",
           (date_iso, "Basketball", 180, "Auto-insert: Sunday 8–11am"))
    try: st.toast("🏀 Auto-added Sunday Basketball 8–11am (180m)")
    except Exception: pass

st.title(f"{APP_NAME} 🔥")
st.caption("Mobile-first • Coach Mode • 12-Month Cut")

prof = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
phase_auto, sys_auto = current_phase_and_system(prof)
active_phase_index = ["M1-3","M4-6","M7-9","M10-12"].index(phase_auto)
st.markdown(journey_map_html(active_phase_index), unsafe_allow_html=True)
st.caption(f"Phase: **{phase_auto}** • Suggested system: **{sys_auto}** • Auto-Phase is {'ON' if prof.get('auto_phase',True) else 'OFF'}")

NAV_ITEMS = ["Today","Program","Meals","Trends","Instructions","Me"]
col_nav = st.columns(len(NAV_ITEMS))
nav = st.session_state.get("nav","Today")
for i,item in enumerate(NAV_ITEMS):
    if col_nav[i].button(item, use_container_width=True, key=f"nav_{item}"):
        st.session_state["nav"]=item; nav=item
st.markdown('<div class="sticky-bottom muted">' + ' · '.join(NAV_ITEMS) + '</div>', unsafe_allow_html=True)

if nav=="Program":
    st.subheader("Program Loader")
    with st.expander("Auto-Phase Settings", expanded=False):
        ap = st.toggle("Auto-Phase Mode (suggest system by month)", value=prof.get("auto_phase", True), key="ap_toggle")
        if st.button("Save Auto-Phase", key="save_autophase"):
            prof["auto_phase"]=bool(ap); set_kv("profile", prof); st.success("Saved Auto-Phase setting")

    phase_suggest, system_suggest = current_phase_and_system(prof)
    env = st.selectbox("Environment", ["Gym","Hotel"], index=0 if prof.get("env","Gym")=="Gym" else 1, key="env_sel")
    systems_list = list(SYSTEMS.keys())
    default_sys = system_suggest if prof.get("auto_phase",True) else get_kv("system","Linear")
    system_name = st.selectbox("System", systems_list, index=systems_list.index(default_sys), key="system_sel")
    phase = st.selectbox("Phase", ["M1-3","M4-6","M7-9","M10-12","Any"],
                         index=["M1-3","M4-6","M7-9","M10-12","Any"].index(phase_suggest if prof.get("auto_phase",True) else get_kv("phase","M1-3")),
                         key="phase_sel")
    sys_obj = get_system(system_name, env)
    day_names=[d.name for d in sys_obj.days]
    day_name = st.selectbox("Day", day_names, key="day_sel")
    target_date = st.date_input("Date", today(), key="prog_date")
    time_crunch = st.select_slider("Time Box (min)", options=[45,60,75,90], value=prof.get("session_minutes",75), key="time_box")

    day_obj = next(d for d in sys_obj.days if d.name==day_name)
    st.markdown("**Preview — Exercises**")
    st.dataframe(_blocks_to_df(day_obj), use_container_width=True)
    if day_obj.cardio: st.caption(f"Cardio: {day_obj.cardio[0]} • {day_obj.cardio[1]} min")
    if time_crunch<=60 and sys_obj.time_crunch_trim: st.info("Time-crunch: accessories may be trimmed when populated.")

    c1,c2,c3 = st.columns(3)
    def _trim(day): return DayTemplate(day.name,[b for b in day.blocks if not (time_crunch<=60 and b.ex in sys_obj.time_crunch_trim)], day.cardio, day.core)
    
    with c1:
        if st.button("Load → TODAY", use_container_width=True, key="load_today"):
            use_day = _trim(day_obj)
            clear_day(today_str())  # 🔥 ensure idempotent
            populate_workout_for(today_str(), env, system_name, use_day, phase)
            set_kv("system", system_name)
            set_kv("phase", phase)
            prof["env"] = env
            prof["session_minutes"] = time_crunch
            set_kv("profile", prof)
            st.session_state["nav"] = "Today"
            st.rerun()
    with c2:
        if st.button("Load → Selected Date", use_container_width=True, key="load_sel"):
            use_day = _trim(day_obj)
            clear_day(target_date.isoformat())  # 🔥 ensure idempotent
            populate_workout_for(target_date.isoformat(), env, system_name, use_day, phase)
            st.success(f"Loaded {system_name}/{day_name} to {target_date}")
    with c3:
        if st.button("Clear Selected Date", use_container_width=True, key="clear_sel"):
            exec_i("DELETE FROM workout_log WHERE dt=?", (target_date.isoformat(),))
            exec_i("DELETE FROM cardio_log WHERE dt=?", (target_date.isoformat(),))
            st.info("Cleared selected date.")

if nav=="Today":
    st.subheader("Today — Train, Log, Win")
    _prof = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    st.caption(f"Targets → Calories: **{int(_prof.get('cal_target',2600))}** kcal • Protein: **{int(_prof.get('protein_g',220))}** g")

    log_date = st.date_input("Log for date", value=today(), key="log_date")
    d_iso = log_date.isoformat()

    ensure_sunday_basketball(d_iso)

    plan = q("SELECT env, system, phase, day_name FROM workout_log WHERE dt=? ORDER BY rowid DESC LIMIT 1",
    (d_iso,),)

    env_guess = plan["env"].iloc[0] if not plan.empty else _prof.get("env","Gym")
    sys_guess = plan["system"].iloc[0] if not plan.empty else get_kv("system","Linear")
    phase_guess = plan["phase"].iloc[0] if not plan.empty else get_kv("phase","M1-3")
    day_guess = plan["day_name"].iloc[0] if not plan.empty else "Session"

    active = get_kv("active_session")
    cA,cB,cC = st.columns(3)
    with cA:
        if not active:
            if st.button("▶️ Start Session", use_container_width=True, key=f"start_{d_iso}"):
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
        if active and st.button("⏹ End Session", use_container_width=True, key=f"end_{active['id']}"):
            st.session_state["show_end_form"]=True
    if st.session_state.get("show_end_form") and active:
        with st.form("end_form"):
            effort = st.slider("Perceived effort (1–10)", 1, 10, 7, key="effort")
            notes = st.text_input("Notes", placeholder="Quads fried; next +2.5 on Chest Press.", key="end_notes")
            if st.form_submit_button("Save & Close"):
                if end_session(effort, notes): st.success("Session saved."); st.session_state["show_end_form"]=False; st.rerun()

    ins = coach_insights()
    if ins:
        with st.expander("Coach Says", expanded=True):
            for i in ins:
                if i["type"]=="plateau": st.info("📉 "+i["msg"])
                elif i["type"]=="badge": st.success("🏅 "+i["msg"])
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

    st.markdown("### Quick Log")
    col1,col2,col3 = st.columns(3)
    with col1:
        wt = st.number_input("Weigh-in (lb)", min_value=0.0, value=0.0, step=0.1, key=f"wt_{d_iso}")
        if st.button("Save Weight", key=f"save_weight_{d_iso}"):
            if wt > 0:
                exec_i("INSERT INTO weight_log(dt, weight_lbs, note) VALUES(?,?,?)",(d_iso, wt, ""))
                st.success("Weight saved")
                adj = macro_adjust_if_needed()
                if adj:
                    st.success(f"Macros updated → {adj['cal_target']} kcal & {adj['protein_g']} g (at {adj['cur']} lb).")
                    try: st.toast("Auto-adjusted macros")
                    except: pass
            else:
                st.warning("Enter a valid weight (> 0).")

    with col2: steps = st.number_input("Steps", min_value=0, value=8000, step=500, key=f"steps_{d_iso}")
    with col3: sleep = st.number_input("Sleep (h)", min_value=0.0, value=7.0, step=0.25, key=f"sleep_{d_iso}")
    if st.button("Save Habits", key=f"save_habits_{d_iso}"):
        exec_i("INSERT INTO habit_log(dt, water_oz, steps, sleep_hr, notes) VALUES(?,?,?,?,?)",(d_iso, 100, steps, sleep, "PM check-in"))
        st.success("Habits saved")



# ----------------------------
# MEALS  (replace this whole block)
# ----------------------------
if nav == "Meals":
    st.subheader("Meals — Fast & On-the-Go")

    prof_now = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    target_cal = int(prof_now.get("cal_target", 2600))
    target_pro = int(prof_now.get("protein_g", 220))

    d_iso = today_str()

    # --- AutoPlan form (executes only on submit) ---
    with st.form("autoplan_form"):
        st.markdown("#### Auto Meal Plan")
        colA, colB, colC = st.columns([1, 1, 1])
        with colA:
            style = st.selectbox(
                "Style",
                ["High Protein (default)", "Gastritis-friendly", "Low Carb", "Mediterranean", "Paleo"],
                index=0,
            )
        with colB:
            day_cals = st.number_input("Calorie Budget (kcal)", 1200, 6000, target_cal, step=50, key="meal_cals")
        with colC:
            day_pro = st.number_input("Protein Goal (g)", 80, 350, target_pro, step=10, key="meal_pro")

        excl = st.text_input("Exclude ingredients (comma-separated)", placeholder="spinach, eggs, spicy", key="exclude_ing")
        submitted = st.form_submit_button("Generate / Replace Plan", use_container_width=True)

    def _excludes(name: str, excl_list: List[str]) -> bool:
        nm = name.lower()
        return any(x.strip().lower() in nm for x in excl_list if x.strip())

    def _base_pool(style_name: str):
        # pull from JSON if present, else fallback
        try:
            meals_map = json.loads((MEALS_DIR / "meals.json").read_text())
        except Exception:
            meals_map = MEALS
        # very light style mapping – you can expand later
        pool = []
        if style_name == "Gastritis-friendly":
            for cat in ("Home", "Fast Food", "Hotel"):
                for m in meals_map.get(cat, []):
                    # avoid spicy/acidic defaults
                    if _excludes(m[0], ["spicy", "salsa", "tomato"]):
                        continue
                    pool.append(m)
        elif style_name == "Low Carb":
            for cat in meals_map:
                for m in meals_map[cat]:
                    if _excludes(m[0], ["rice", "bread", "wrap", "sweet potato"]):
                        continue
                    pool.append(m)
        elif style_name == "Mediterranean":
            # keep lean proteins, olive oil, fish forward
            for cat in meals_map:
                for m in meals_map[cat]:
                    if "salmon" in m[0].lower() or "chicken" in m[0].lower() or "olive" in m[0].lower():
                        pool.append(m)
        elif style_name == "Paleo":
            for cat in meals_map:
                for m in meals_map[cat]:
                    if _excludes(m[0], ["rice", "bread", "wrap", "box"]):
                        continue
                    pool.append(m)
        else:  # High Protein (default)
            for cat in meals_map:
                for m in meals_map[cat]:
                    if m[1] >= 30:  # protein_g
                        pool.append(m)
        return pool

    if submitted:
        # prevent duplicate inserts on rerun:
        exec_i("DELETE FROM meal_log WHERE dt=? AND source='AutoPlan'", (d_iso,))

        exclusions = [x.strip() for x in excl.split(",")] if excl else []
        pool = [m for m in _base_pool(style) if not _excludes(m[0], exclusions)]
        random.shuffle(pool)

        cur_kcal = 0
        cur_pro = 0
        used = set()
        # Fill to budget (±200 kcal window), prefer higher protein density first
        pool.sort(key=lambda m: (m[1] / max(m[2], 1)), reverse=True)  # protein/kcal density
        for m in pool:
            name, p, k, note, src = m
            key = (name, src)
            if key in used:
                continue
            # stop when we're close to target calories
            if cur_kcal >= day_cals - 200:
                break
            exec_i(
                "INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                (d_iso, "AutoPlan", name, int(p), int(k), f"{note} • {style}"),
            )
            used.add(key)
            cur_kcal += int(k)
            cur_pro += int(p)

        st.success(f"AutoPlan created: ~{cur_kcal} kcal, {cur_pro} g protein. You can edit or delete items below.")
        st.rerun()

    # --- Controls row ---
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Clear AutoPlan (today)", use_container_width=True, key="clear_autoplan"):
            exec_i("DELETE FROM meal_log WHERE dt=? AND source='AutoPlan'", (d_iso,))
            st.info("Cleared AutoPlan for today.")
            st.rerun()
    with c2:
        if st.button("Clear ALL meals (today)", use_container_width=True, key="clear_all_meals"):
            exec_i("DELETE FROM meal_log WHERE dt=?", (d_iso,))
            st.info("Cleared all meals for today.")
            st.rerun()
    with c3:
        st.caption("Tip: Use exclusions to avoid spinach/eggs/etc.")

    # --- Manual add (unchanged core inputs) ---
    st.markdown("#### Quick Add")
    colL, colR = st.columns(2)
    with colL:
        try:
            meals_map = json.loads((MEALS_DIR / "meals.json").read_text())
        except Exception:
            meals_map = MEALS
        cat = st.selectbox("Category", list(meals_map.keys()), key="meal_cat")
        names = [m[0] for m in meals_map.get(cat, [])]
        choice = st.selectbox("Preset", names, key="meal_choice") if names else None
        if st.button("Add Preset", use_container_width=True, key="add_preset_left"):
            m = meals_map[cat][names.index(choice)]
            exec_i(
                "INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                (d_iso, m[4], m[0], int(m[1]), int(m[2]), m[3]),
            )
            st.success("Added meal preset")
            st.rerun()
    with colR:
        st.markdown("**Custom**")
        cname = st.text_input("Name", placeholder="Chicken bowl", key="c_name")
        cprot = st.number_input("Protein (g)", 0, 200, 40, key="c_pro")
        ckcal = st.number_input("Calories", 0, 1500, 600, key="c_kcal")
        csrc = st.text_input("Source/Place", placeholder="Home / Chipotle / Panda …", key="c_src")
        cnote = st.text_input("Notes", placeholder="No sauce, extra veggies", key="c_note")
        if st.button("Add Custom", use_container_width=True, key="add_custom") and cname:
            exec_i(
                "INSERT INTO meal_log(dt, source, meal, protein_g, kcal, notes) VALUES(?,?,?,?,?,?)",
                (d_iso, csrc or "Custom", cname, int(cprot), int(ckcal), cnote),
            )
            st.success("Added custom meal")
            st.rerun()

    # --- Today’s Meals table with delete buttons ---
    st.markdown("### Today’s Meals")
    day_meals = q(
        "SELECT rowid, dt, source, meal, protein_g, kcal, notes FROM meal_log WHERE dt=? ORDER BY rowid DESC",
        (d_iso,),
    )
    total_p = int(day_meals["protein_g"].sum()) if not day_meals.empty else 0
    total_k = int(day_meals["kcal"].sum()) if not day_meals.empty else 0

    # Totals + progress bars
    st.markdown(
        f"**Totals:** {total_p} g protein / {total_k} kcal  •  Targets: {target_pro} g / {target_cal} kcal"
    )
    st.progress(min(total_p / max(target_pro, 1), 1.0))
    st.progress(min(total_k / max(target_cal, 1), 1.0))

    if day_meals.empty:
        st.caption("No meals logged yet.")
    else:
        # Render with delete per row
        for _, r in day_meals.iterrows():
            with st.expander(f"🧾 {r['meal']}  —  {r['protein_g']} g / {r['kcal']} kcal  ({r['source']})", expanded=False):
                st.caption(r.get("notes") or "")
                cols = st.columns([1, 1])

                with cols[0]:
                    if st.button("🗑️ Delete", key=f"del_{r['rowid']}"):
                        exec_i("DELETE FROM meal_log WHERE rowid=?", (int(r["rowid"]),))
                        st.rerun()
                with cols[1]:
                    st.caption(f"Logged on {r['dt']}")



if nav=="Instructions":
    st.subheader("How to Use KISS SHRED")
    st.markdown("""
**12-Month Flow**  
• **M1–3:** Linear • **M4–6:** PowerBuild • **M7–9:** MetCon • **M10–12:** Athletic

**Daily**  
1) Program → **Load → TODAY**  
2) Today → **Start Session** → train → **End Session**  
3) Log sets with **Quick Set Logger** (PRs tracked)  
4) Meals → use **Auto Plan** or add presets/custom

**Rules**  
Protein **0.8–1.0 g/lb** • Steps **8–12k** • Cardio 2–4×20–30 min • Sleep **7+ h**  
Plateau 14d? **+1k steps, +15g protein, +10% cardio** for 7d.

**Auto Macros**  
When latest weigh-in is **≥ 5 lb** below last anchor:
- Calories **−5%** (min **1800**)
- Protein ≈ **0.9 g/lb** current
""")


if nav=="Me":
    st.subheader("Me — Profile & Settings")
    with st.form("profile_form"):
        name = st.text_input("Name", value=prof.get("name","Smooth"), key="p_name")
        height_in = st.number_input("Height (in)", 48, 90, int(prof.get("height_in",74)), key="p_height")
        sex = st.selectbox("Sex", ["M","F"], index=0 if prof.get("sex","M")=="M" else 1, key="p_sex")
        age = st.number_input("Age", 16, 85, int(prof.get("age",35)), key="p_age")
        start_wt = st.number_input("Start Weight (lb)", 50.0, 800.0, float(prof.get("start_wt",300.0)), step=0.5, key="p_startwt")
        goal_wt = st.number_input("Goal Weight (lb)", 50.0, 800.0, float(prof.get("goal_wt",230.0)), step=0.5, key="p_goalwt")
        protein_g = st.number_input("Protein Target (g)", 80, 350, int(prof.get("protein_g",220)), key="p_pro")
        cal_target = st.number_input("Daily Calories Target", 1200, 6000, int(prof.get("cal_target", 2600)), step=50, key="p_cals")
        steps = st.number_input("Steps Target", 2000, 30000, int(prof.get("steps",9000)), step=500, key="p_steps")
        session_minutes = st.select_slider("Default Session (min)", options=[45,60,75,90], value=int(prof.get("session_minutes",75)), key="p_sessmin")
        env = st.selectbox("Default Environment", ["Gym","Hotel"], index=0 if prof.get("env","Gym")=="Gym" else 1, key="p_env")
        start_date = st.date_input("Journey Start Date", value=datetime.date.fromisoformat(prof.get("start_date", today_str())), key="p_startdate")
        auto_phase = st.checkbox("Auto-Phase Mode", value=prof.get("auto_phase", True), key="p_ap")
        auto_adj = st.checkbox("Auto-Adjust Macros when weight drops ≥ 5 lb", value=prof.get("auto_macro_adjust", True), key="p_autoadj")
        sound_ping = st.checkbox("Timer Sound Ping", value=prof.get("sound_ping", True), key="p_sound")
        perf = st.checkbox("Performance Mode (fast Today screen)", value=get_kv("performance_mode", True), key="p_perf")
        basketball_sun = st.checkbox("Sunday Basketball 8–11am", value=prof.get("basketball_sun", True), key="p_bb")
        lifestyle = st.selectbox("Lifestyle Profile", LIFESTYLES, index=LIFESTYLES.index(prof.get("lifestyle","Mediterranean Reset")), key="p_lifestyle")
        dislikes = st.text_input("Food dislikes (comma)", value=",".join(prof.get("dislikes",[])), key="p_dislikes")
        allergies = st.text_input("Allergies (comma)", value=",".join(prof.get("allergies",[])), key="p_allergies")
        cookcap = st.slider("Max meal prep time (min)", 5, 60, int(prof.get("cook_time_cap",25)), key="p_cookcap")
        kitchen = st.selectbox("Kitchen access", ["Full","Microwave","No-Cook"], index=["Full","Microwave","No-Cook"].index(prof.get("kitchen_access","Full")), key="p_kitchen")


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
                "macro_anchor_wt": float(prof.get("macro_anchor_wt", start_wt)),
                "lifestyle": lifestyle,
                "dislikes": [x.strip() for x in dislikes.split(",") if x.strip()],
                "allergies": [x.strip() for x in allergies.split(",") if x.strip()],
                "cook_time_cap": int(cookcap),
                "kitchen_access": kitchen,

            })
            set_kv("profile", prof); set_kv("performance_mode", bool(perf)); st.success("Saved profile & settings")

    st.markdown("### Data & Backup")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Export CSVs", use_container_width=True, key="export_csvs"):
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
        if st.button("Reset TODAY only", use_container_width=True, key="reset_today"):
            exec_i("DELETE FROM workout_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM cardio_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM meal_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM habit_log WHERE dt=?", (today_str(),))
            exec_i("DELETE FROM weight_log WHERE dt=?", (today_str(),))

            st.info("Cleared today’s entries")
    with c3:
        if st.button("⚠️ Full Reset (ALL data)", use_container_width=True, key="full_reset"):
            st.warning("This deletes ALL data. Type DELETE below and press Confirm.")
            val = st.text_input("Type DELETE to confirm", key="confirm_del")
            if val=="DELETE":
                try:
                    conn.close()
                except Exception:
                    pass
                try:
                    os.remove(DB_FILE); st.success("Database removed. Restart the app.")
                except Exception as e: st.error(f"Could not remove database: {e}")


# === DAILY ROTATION + SMART MEAL PATCH (already merged if you insert per guide) ===

# KISS SHRED 2.2 — Patch: Daily Workout Rotation + Smarter Auto Meals
# How to use:
# 1) In fatloss.py, REPLACE the following functions with the versions below:
#    - current_phase_and_system (optional tweak preserved)
#    - ensure_daily_program (NEW)  ➜ call this in Today view before rendering
#    - build_auto_plan (REPLACEMENT)  ➜ smarter meal plan
# 2) In Today view (nav=="Today"), add:  ensure_daily_program(d_iso)  right after d_iso is defined.
# 3) In Meals view, no changes needed if you already call build_auto_plan(); this replaces it.

import datetime, json, random, re
import pandas as pd

# ---- Phase/system (unchanged semantics; kept for completeness) ----
PHASE_FLOW = [("M1-3","Linear"),("M4-6","PowerBuild"),("M7-9","MetCon"),("M10-12","Athletic")]

def months_since_start(iso): 
    try: start = datetime.date.fromisoformat(iso)
    except: start = datetime.date.today()
    return max(0,(datetime.date.today().year-start.year)*12+(datetime.date.today().month-start.month))

def current_phase_and_system(profile:dict):
    m = months_since_start(profile.get("start_date", datetime.date.today().isoformat()))
    idx = min(len(PHASE_FLOW)-1, m//3)
    return PHASE_FLOW[idx]

# ---- NEW: ensure_daily_program ----
def ensure_daily_program(date_iso: str):
    """
    Auto-populates today's workout if empty, rotating day-to-day based on weekday and last used day.
    - Uses Auto-Phase/system.
    - Cycles through system.days deterministically.
    """
    # Already loaded?
    existing = conn.execute("SELECT 1 FROM workout_log WHERE dt=? LIMIT 1",(date_iso,)).fetchone()
    if existing: 
        return

    profile = get_kv("profile", DEFAULTS["profile"]) or DEFAULTS["profile"]
    phase, system_name = current_phase_and_system(profile) if profile.get("auto_phase", True) else (get_kv("phase","M1-3"), get_kv("system","Linear"))
    env = profile.get("env","Gym")

    sys_obj = get_system(system_name, env)
    if not sys_obj or not sys_obj.days:
        return

    # Rotation index: prefer weekday; fall back to stored last index
    wd = datetime.date.fromisoformat(date_iso).weekday()  # 0=Mon..6=Sun
    key = f"last_idx::{system_name}::{env}"
    last_idx = int(get_kv(key, -1) or -1)

    # Use weekday to spread days, but keep continuity if user trains irregularly
    idx = (wd % len(sys_obj.days))
    if idx == last_idx:
        idx = (idx + 1) % len(sys_obj.days)

    day_obj = sys_obj.days[idx]
    # Trim for time box
    time_crunch = int(profile.get("session_minutes", sys_obj.session_minutes))
    def _trim(day): 
        return DayTemplate(day.name,[b for b in day.blocks if not (time_crunch<=60 and b.ex in sys_obj.time_crunch_trim)], day.cardio, day.core)
    use_day = _trim(day_obj)

    # Clear any partials & populate
    clear_day(date_iso)
    populate_workout_for(date_iso, env, system_name, use_day, phase)
    set_kv("system", system_name); set_kv("phase", phase)
    profile["env"]=env; set_kv("profile", profile)
    set_kv(key, idx)

# ---- REPLACEMENT: build_auto_plan (smarter selection) ----
def build_auto_plan(profile, training_day=True):
    """
    Smarter 3–5 meal plan:
      • Honors lifestyle, dislikes, allergies, kitchen access, prep time cap
      • Biases protein distribution across meals
      • Targets kcal ±200 and protein ≥90% of target
      • Ensures category variety (B/L/D + Snack)
    """
    lifestyle = profile.get("lifestyle","Mediterranean Reset")
    dislikes = [x.strip().lower() for x in (profile.get("dislikes",[]) or [])]
    allergies = [x.strip().lower() for x in (profile.get("allergies",[]) or [])]
    cap = int(profile.get("cook_time_cap",25))
    kitchen = profile.get("kitchen_access","Full")
    p_target = int(profile.get("protein_g", 200))
    kcal_target = int(profile.get("cal_target", 2400)) if "cal_target" in profile else 2400

    # Build pool and filter
    pool = _gen_pool_for(lifestyle)

    def blocked(name:str)->bool:
        low=name.lower()
        for x in dislikes + allergies:
            if x and x in low: return True
        return False

    def fits(m)->bool:
        if blocked(m["name"]): return False
        # kitchen tool
        if kitchen=="No-Cook" and m["tool"]!="No-Cook": return False
        if kitchen=="Microwave" and m["tool"] not in ("Microwave","No-Cook"): return False
        if m["prep_min"]>cap: return False
        return True

    cand=[m for m in pool if fits(m)]

    # Day bias
    def adj(m):
        m=dict(m)
        if training_day: m["carbs"]=int(m["carbs"]*1.15)
        else: m["carbs"]=max(8,int(m["carbs"]*0.85))
        m["kcal"]=_approx_kcal(m["protein"],m["carbs"],m["fat"])
        return m

    cand=[adj(m) for m in cand]

    # Target split per touch
    touches=4
    per_p=max(20, round(p_target/touches))
    per_k=max(250, round(kcal_target/touches))

    # Bucket by category
    buckets={"Breakfast":[], "Lunch":[], "Dinner":[], "Snack":[]}
    for m in cand:
        buckets.setdefault(m["category"],[]).append(m)

    # Score: prioritize meals closer to per-touch and higher protein density
    def score(m, p_left, k_left):
        dens=m["protein"]/max(1,m["kcal"])
        return (abs(m["protein"]-p_left)*1.2 + abs(m["kcal"]-k_left)*0.8) - 100*dens

    plan=[]; p_sum=0; k_sum=0
    for cat in ["Breakfast","Lunch","Dinner","Snack"]:
        p_left=max(0,p_target-p_sum); k_left=max(0,kcal_target-k_sum)
        picks=buckets.get(cat,[])
        if not picks: continue
        picks=sorted(picks, key=lambda m: score(m, min(per_p,p_left), min(per_k,k_left)))
        best=picks[0]
        plan.append(best); p_sum+=best["protein"]; k_sum+=best["kcal"]

    # Optional extra snack if protein low
    if p_sum < 0.9*p_target and buckets.get("Snack"):
        extra=sorted(buckets["Snack"], key=lambda m: -m["protein"]/max(1,m["kcal"]))[0]
        # avoid duplicate exact name
        if not any(x["name"]==extra["name"] for x in plan):
            plan.append(extra); p_sum+=extra["protein"]; k_sum+=extra["kcal"]

    # Clip to 5
    plan=plan[:5]

    # Convert to simple list used downstream
    out=[{"meal":m["name"],"protein_g":int(m["protein"]), "kcal":int(m["kcal"]), "notes": ", ".join(m.get("tags",[])) or m.get("notes","")} for m in plan]
    return out
