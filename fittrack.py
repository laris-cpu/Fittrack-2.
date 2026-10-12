
from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "fittrack.db"

BG = "#0b0e11"
SIDEBAR = "#101417"
PANEL = "#141a1e"
PANEL_2 = "#1a2226"
BORDER = "#2b353a"
TEXT = "#edf1f1"
MUTED = "#8f9ba0"
GREEN = "#c1f36b"
GREEN_DARK = "#273525"
RED = "#f08c83"

EXERCISE_SEED = [
    ("Barbell Squat", "Quads · Glutes", "Intermediate", "Barbell", "3", "8–10", "Brace your core; keep heels grounded and knees tracking over toes.", ["Stand with feet about shoulder-width apart and brace your core.", "Send your hips back and bend your knees with heels grounded.", "Lower only as far as you can while keeping a neutral spine.", "Drive through your whole foot to stand tall."]),
    ("Push-up", "Chest · Triceps", "Beginner", "Bodyweight", "3", "8–12", "Keep a straight line from head to heels and lower with control.", ["Place hands slightly wider than shoulders.", "Extend legs and brace your abs in a straight plank.", "Lower your chest with elbows at a comfortable angle.", "Push the floor away and return to the start."]),
    ("Dumbbell Row", "Back · Biceps", "Beginner", "Dumbbells", "3", "10–12", "Pull your elbow toward your hip without twisting your torso.", ["Hinge at the hips with a flat back and soft knees.", "Let the dumbbell hang under your shoulder.", "Pull your elbow back, squeezing the shoulder blade.", "Lower slowly and repeat on the other side."]),
    ("Romanian Deadlift", "Hamstrings · Glutes", "Intermediate", "Dumbbells / Barbell", "3", "8–10", "Push hips back; keep weights close and stop at a comfortable hamstring stretch.", ["Stand tall with weights in front of your thighs.", "Soften your knees and push hips backward.", "Lower weights close to your legs with a neutral spine.", "Drive hips forward to stand without leaning back."]),
    ("Plank", "Core", "Beginner", "Bodyweight", "3", "30–45 sec", "Squeeze glutes and abs; do not let your lower back sag.", ["Place forearms under your shoulders.", "Step feet back to make a straight line with your body.", "Brace abs and squeeze glutes while breathing steadily.", "Hold with hips level, then lower with control."]),
    ("Dumbbell Shoulder Press", "Shoulders · Triceps", "Intermediate", "Dumbbells", "3", "8–12", "Use a comfortable range and avoid arching your lower back.", ["Hold dumbbells at shoulder height with wrists stacked.", "Brace your core and keep ribs down.", "Press weights overhead with control.", "Lower slowly to shoulder height."]),
    ("Walking Lunge", "Quads · Glutes", "Beginner", "Bodyweight / Dumbbells", "3", "10 each side", "Step carefully and keep your front knee tracking over your toes.", ["Stand tall with feet hip-width apart.", "Step forward and bend both knees under control.", "Keep your torso upright and front foot flat.", "Push through the front foot and step forward again."]),
    ("Jumping Jack", "Full body · Cardio", "Beginner", "Bodyweight", "3", "30 sec", "Land softly; use a step-out version for lower impact.", ["Stand tall with arms at your sides.", "Jump feet apart as arms rise overhead.", "Land softly with knees relaxed.", "Return to the start and repeat steadily."]),
]

class FitTrackDB:
    def __init__(self, path: Path = DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._setup()

    def _setup(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          display_name TEXT NOT NULL,
          salt TEXT NOT NULL,
          password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS profiles (
          user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
          fitness_goal TEXT NOT NULL DEFAULT 'Build strength',
          experience_level TEXT NOT NULL DEFAULT 'Beginner',
          weekly_target INTEGER NOT NULL DEFAULT 4,
          body_weight REAL
        );
        CREATE TABLE IF NOT EXISTS exercises (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE NOT NULL,
          muscles TEXT NOT NULL,
          level TEXT NOT NULL,
          equipment TEXT NOT NULL,
          recommended_sets TEXT NOT NULL,
          recommended_reps TEXT NOT NULL,
          cue TEXT NOT NULL,
          steps TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS routines (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          name TEXT NOT NULL,
          focus TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS routine_exercises (
          routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
          exercise_id INTEGER NOT NULL REFERENCES exercises(id),
          position INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (routine_id, exercise_id)
        );
        CREATE TABLE IF NOT EXISTS workouts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          routine_name TEXT NOT NULL,
          started_at TEXT NOT NULL,
          duration_minutes INTEGER NOT NULL DEFAULT 1,
          volume_kg REAL NOT NULL DEFAULT 0,
          sets_completed INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS workout_sets (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
          exercise_id INTEGER NOT NULL REFERENCES exercises(id),
          set_number INTEGER NOT NULL,
          weight_kg REAL NOT NULL DEFAULT 0,
          reps INTEGER NOT NULL DEFAULT 0,
          done INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS idx_routines_user ON routines(user_id);
        CREATE INDEX IF NOT EXISTS idx_workouts_user ON workouts(user_id);
        """)
        for row in EXERCISE_SEED:
            self.conn.execute(
                "INSERT OR IGNORE INTO exercises(name,muscles,level,equipment,recommended_sets,recommended_reps,cue,steps) VALUES(?,?,?,?,?,?,?,?)",
                (*row[:7], "\n".join(row[7]))
            )
        self.conn.commit()

    @staticmethod
    def _hash_password(password: str, salt_hex: str | None = None):
        salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
        return salt.hex(), hashed.hex()

    def create_user(self, email: str, display_name: str, password: str):
        salt, digest = self._hash_password(password)
        try:
            cur = self.conn.execute(
                "INSERT INTO users(email,display_name,salt,password_hash,created_at) VALUES(?,?,?,?,?)",
                (email.strip().lower(), display_name.strip(), salt, digest, datetime.now().isoformat(timespec="seconds"))
            )
            user_id = cur.lastrowid
            self.conn.execute("INSERT INTO profiles(user_id) VALUES(?)", (user_id,))
            self._create_starter_routines(user_id)
            self.conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            return None

    def verify_user(self, email: str, password: str):
        row = self.conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not row:
            return None
        _, digest = self._hash_password(password, row["salt"])
        return dict(row) if secrets.compare_digest(digest, row["password_hash"]) else None

    def _create_starter_routines(self, user_id: int):
        starters = [
            ("Full Body Foundation", "Full body", ["Push-up", "Dumbbell Row", "Barbell Squat", "Plank"]),
            ("Strength & Power", "Strength", ["Barbell Squat", "Romanian Deadlift", "Dumbbell Shoulder Press"]),
            ("Quick Cardio Reset", "Cardio", ["Jumping Jack", "Walking Lunge", "Plank"]),
        ]
        for name, focus, names in starters:
            cur = self.conn.execute("INSERT INTO routines(user_id,name,focus,created_at) VALUES(?,?,?,?)", (user_id, name, focus, datetime.now().date().isoformat()))
            rid = cur.lastrowid
            for pos, ex_name in enumerate(names):
                row = self.conn.execute("SELECT id FROM exercises WHERE name=?", (ex_name,)).fetchone()
                if row:
                    self.conn.execute("INSERT OR IGNORE INTO routine_exercises(routine_id,exercise_id,position) VALUES(?,?,?)", (rid, row["id"], pos))

    def profile(self, user_id: int):
        return self.conn.execute("SELECT u.display_name,p.* FROM users u JOIN profiles p ON p.user_id=u.id WHERE u.id=?", (user_id,)).fetchone()

    def save_profile(self, user_id: int, name: str, goal: str, level: str, target: int, weight: str):
        self.conn.execute("UPDATE users SET display_name=? WHERE id=?", (name.strip() or "Athlete", user_id))
        body_weight = float(weight) if weight.strip() else None
        self.conn.execute("UPDATE profiles SET fitness_goal=?,experience_level=?,weekly_target=?,body_weight=? WHERE user_id=?", (goal, level, target, body_weight, user_id))
        self.conn.commit()

    def exercises(self, query: str = ""):
        if query:
            term = f"%{query.strip()}%"
            return self.conn.execute("SELECT * FROM exercises WHERE name LIKE ? OR muscles LIKE ? OR equipment LIKE ? ORDER BY name", (term, term, term)).fetchall()
        return self.conn.execute("SELECT * FROM exercises ORDER BY name").fetchall()

    def create_routine(self, user_id: int, name: str, focus: str, exercise_ids: list[int]):
        cur = self.conn.execute("INSERT INTO routines(user_id,name,focus,created_at) VALUES(?,?,?,?)", (user_id, name.strip(), focus, datetime.now().date().isoformat()))
        rid = cur.lastrowid
        for pos, exid in enumerate(exercise_ids):
            self.conn.execute("INSERT OR IGNORE INTO routine_exercises(routine_id,exercise_id,position) VALUES(?,?,?)", (rid, exid, pos))
        self.conn.commit()
        return rid

    def routines(self, user_id: int):
        rows = self.conn.execute("SELECT * FROM routines WHERE user_id=? ORDER BY id DESC", (user_id,)).fetchall()
        result = []
        for r in rows:
            names = self.conn.execute("SELECT e.name FROM routine_exercises re JOIN exercises e ON e.id=re.exercise_id WHERE re.routine_id=? ORDER BY re.position", (r["id"],)).fetchall()
            result.append({**dict(r), "exercise_names": [x["name"] for x in names]})
        return result

    def routine(self, user_id: int, routine_id: int):
        row = self.conn.execute("SELECT * FROM routines WHERE id=? AND user_id=?", (routine_id, user_id)).fetchone()
        if not row:
            return None
        exercises = self.conn.execute("SELECT e.* FROM routine_exercises re JOIN exercises e ON e.id=re.exercise_id WHERE re.routine_id=? ORDER BY re.position", (routine_id,)).fetchall()
        return {**dict(row), "exercises": exercises}

    def delete_routine(self, user_id: int, routine_id: int):
        self.conn.execute("DELETE FROM routines WHERE id=? AND user_id=?", (routine_id, user_id))
        self.conn.commit()

    def save_workout(self, user_id: int, routine_name: str, started_at: datetime, sets: list[dict]):
        finished = datetime.now()
        duration = max(1, int((finished - started_at).total_seconds() // 60))
        completed = [s for s in sets if s["done"]]
        volume = sum(s["weight"] * s["reps"] for s in completed)
        cur = self.conn.execute("INSERT INTO workouts(user_id,routine_name,started_at,duration_minutes,volume_kg,sets_completed) VALUES(?,?,?,?,?,?)", (user_id, routine_name, finished.isoformat(timespec="seconds"), duration, volume, len(completed)))
        workout_id = cur.lastrowid
        for s in completed:
            self.conn.execute("INSERT INTO workout_sets(workout_id,exercise_id,set_number,weight_kg,reps,done) VALUES(?,?,?,?,?,1)", (workout_id, s["exercise_id"], s["set_number"], s["weight"], s["reps"]))
        self.conn.commit()
        return workout_id

    def workouts(self, user_id: int, search: str = ""):
        if search:
            term = f"%{search.strip()}%"
            return self.conn.execute("SELECT * FROM workouts WHERE user_id=? AND routine_name LIKE ? ORDER BY started_at DESC LIMIT 250", (user_id, term)).fetchall()
        return self.conn.execute("SELECT * FROM workouts WHERE user_id=? ORDER BY started_at DESC LIMIT 250", (user_id,)).fetchall()

    def delete_workout(self, user_id: int, workout_id: int):
        self.conn.execute("DELETE FROM workouts WHERE user_id=? AND id=?", (user_id, workout_id))
        self.conn.commit()

    def stats(self, user_id: int):
        base = self.conn.execute("SELECT COUNT(*) workouts, COALESCE(SUM(duration_minutes),0) minutes, COALESCE(SUM(volume_kg),0) volume, COALESCE(SUM(sets_completed),0) sets FROM workouts WHERE user_id=?", (user_id,)).fetchone()
        since = (datetime.now() - timedelta(days=7)).isoformat()
        week = self.conn.execute("SELECT COUNT(*) FROM workouts WHERE user_id=? AND started_at>=?", (user_id, since)).fetchone()[0]
        prs = self.conn.execute("SELECT e.name,e.muscles,MAX(ws.weight_kg) best FROM workout_sets ws JOIN workouts w ON w.id=ws.workout_id JOIN exercises e ON e.id=ws.exercise_id WHERE w.user_id=? AND ws.done=1 GROUP BY e.id HAVING best>0 ORDER BY best DESC", (user_id,)).fetchall()
        return {**dict(base), "week": week, "prs": prs}

    def close(self):
        self.conn.close()

class FitTrackApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FitTrack — Workout Management System")
        self.geometry("1220x800")
        self.minsize(920, 650)
        self.configure(bg=BG)
        self.db = FitTrackDB()
        self.user = None
        self.active_routine = None
        self.workout_started = None
        self.tracking_rows = []
        self.page = None
        self._style_ttk()
        self.show_auth()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style_ttk(self):
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=30, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=GREEN, relief="flat", font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", GREEN_DARK)], foreground=[("selected", TEXT)])
        style.configure("TCombobox", fieldbackground=PANEL_2, background=PANEL_2, foreground=TEXT, arrowcolor=GREEN)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_2)], foreground=[("readonly", TEXT)])

    def button(self, parent, text, command, primary=False, **kwargs):
        return tk.Button(parent, text=text, command=command, bg=GREEN if primary else PANEL_2, fg="#172015" if primary else TEXT,
                         activebackground="#d3ff8e" if primary else BORDER, activeforeground="#172015" if primary else TEXT,
                         relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 10, "bold"), padx=14, pady=10, **kwargs)

    def label(self, parent, text, size=10, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", parent.cget("bg") if hasattr(parent, "cget") else BG), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), **kwargs)

    def entry(self, parent, textvariable=None, width=None, show=None):
        e = tk.Entry(parent, textvariable=textvariable, width=width, show=show, bg=PANEL_2, fg=TEXT, insertbackground=GREEN,
                     relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER, highlightcolor=GREEN,
                     font=("Segoe UI", 11))
        e.configure(highlightthickness=1)
        return e

    def field(self, parent, caption, variable=None, show=None, width=32):
        wrap = tk.Frame(parent, bg=parent.cget("bg"))
        self.label(wrap, caption, 9, MUTED, True).pack(anchor="w", pady=(0, 6))
        ent = self.entry(wrap, variable, width, show)
        ent.pack(fill="x", ipady=10)
        return wrap, ent

    def show_auth(self):
        self.auth_signup = False
        for child in self.winfo_children(): child.destroy()
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True)
        left = tk.Frame(root, bg="#111813", width=510, padx=45, pady=40)
        left.pack(side="left", fill="both", expand=True)
        left.pack_propagate(False)
        mark = tk.Frame(left, bg=GREEN, width=45, height=45)
        mark.pack(anchor="w")
        mark.pack_propagate(False)
        tk.Label(mark, text="⚡", bg=GREEN, fg="#172015", font=("Segoe UI", 20, "bold")).place(relx=.5, rely=.5, anchor="center")
        self.label(left, "fittrack.", 23, TEXT, True).pack(anchor="w", pady=(14, 0))
        self.label(left, "TRAIN WITH PURPOSE", 8, GREEN, True).pack(anchor="w")
        spacer = tk.Frame(left, bg="#111813", height=65); spacer.pack()
        self.label(left, "YOUR FITNESS, IN FOCUS", 9, GREEN, True).pack(anchor="w")
        tk.Label(left, text="Show up today.\nGet stronger tomorrow.", bg="#111813", fg=TEXT, font=("Segoe UI", 31, "bold"), justify="left").pack(anchor="w", pady=(16, 12))
        tk.Label(left, text="Create routines, track your workouts, and celebrate progress — one rep at a time.", bg="#111813", fg=MUTED, font=("Segoe UI", 12), wraplength=410, justify="left").pack(anchor="w")
        for title, subtitle in [("Plan your workouts", "Routines that match your goals"), ("Track every set", "Weights, reps, and training volume"), ("See your progress", "Workout history and personal records")]:
            row = tk.Frame(left, bg="#18211a", padx=13, pady=12, highlightbackground="#303b30", highlightthickness=1)
            row.pack(fill="x", pady=(20, 0))
            tk.Label(row, text="✓", fg=GREEN, bg="#18211a", font=("Segoe UI", 17, "bold")).pack(side="left", padx=(0, 12))
            col = tk.Frame(row, bg="#18211a"); col.pack(side="left", fill="x")
            self.label(col, title, 11, TEXT, True).pack(anchor="w")
            self.label(col, subtitle, 9, MUTED).pack(anchor="w", pady=(4, 0))

        right = tk.Frame(root, bg=BG, padx=35, pady=35)
        right.pack(side="right", fill="both", expand=True)
        card = tk.Frame(right, bg=PANEL, padx=28, pady=28, highlightbackground=BORDER, highlightthickness=1)
        card.place(relx=.5, rely=.5, anchor="center", relwidth=.95)
        self.auth_card = card
        self._render_auth_card()

    def _render_auth_card(self):
        for child in self.auth_card.winfo_children(): child.destroy()
        signup = self.auth_signup
        self.label(self.auth_card, "YOUR PERSONAL WORKOUT SPACE", 9, GREEN, True).pack(anchor="w")
        self.label(self.auth_card, "Create your account" if signup else "Welcome back.", 23, TEXT, True).pack(anchor="w", pady=(12, 4))
        self.label(self.auth_card, "Sign up to start tracking." if signup else "Log in to continue your fitness journey.", 10, MUTED).pack(anchor="w", pady=(0, 23))
        self.auth_name = tk.StringVar()
        self.auth_email = tk.StringVar()
        self.auth_pass = tk.StringVar()
        if signup:
            wrap, _ = self.field(self.auth_card, "DISPLAY NAME", self.auth_name)
            wrap.pack(fill="x", pady=(0, 14))
        wrap, self.email_entry = self.field(self.auth_card, "EMAIL", self.auth_email)
        wrap.pack(fill="x", pady=(0, 14))
        wrap, self.password_entry = self.field(self.auth_card, "PASSWORD (MIN. 8 CHARACTERS)", self.auth_pass, show="•")
        wrap.pack(fill="x", pady=(0, 20))
        self.auth_error_label = tk.Label(self.auth_card, text="", bg=PANEL, fg=RED, font=("Segoe UI", 9), wraplength=330, justify="left")
        self.auth_error_label.pack(anchor="w", pady=(0, 7))
        self.button(self.auth_card, "CREATE ACCOUNT" if signup else "LOG IN", self._submit_auth, primary=True).pack(fill="x")
        row = tk.Frame(self.auth_card, bg=PANEL); row.pack(pady=(18, 8))
        self.label(row, "Already have an account?" if signup else "New to FitTrack?", 9, MUTED).pack(side="left")
        link = self.button(row, "Log in" if signup else "Sign up", self._toggle_auth_mode)
        link.configure(bg=PANEL, fg=GREEN, padx=8, pady=4)
        link.pack(side="left")
        self.label(self.auth_card, "Your workout data is saved in a local SQLite database on this computer.", 9, MUTED, wraplength=340, justify="center").pack(fill="x", pady=(17, 0))
        self.email_entry.focus_set()

    def _toggle_auth_mode(self):
        self.auth_signup = not self.auth_signup
        self._render_auth_card()

    def _submit_auth(self):
        email = self.auth_email.get().strip().lower()
        password = self.auth_pass.get()
        if not email or "@" not in email:
            self.auth_error_label.configure(text="Enter a valid email address."); return
        if len(password) < 8:
            self.auth_error_label.configure(text="Password must be at least 8 characters."); return
        if self.auth_signup:
            name = self.auth_name.get().strip()
            if not name:
                self.auth_error_label.configure(text="Enter your display name."); return
            uid = self.db.create_user(email, name, password)
            if not uid:
                self.auth_error_label.configure(text="That email is already registered. Try logging in."); return
            self.user = dict(self.db.conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        else:
            self.user = self.db.verify_user(email, password)
            if not self.user:
                self.auth_error_label.configure(text="Email or password is incorrect."); return
        self.show_shell()

    def show_shell(self):
        for child in self.winfo_children(): child.destroy()
        shell = tk.Frame(self, bg=BG); shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=SIDEBAR, width=235, padx=15, pady=20)
        sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)
        tk.Label(sidebar, text="⚡  fittrack.", bg=SIDEBAR, fg=GREEN, font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=7, pady=(4, 1))
        tk.Label(sidebar, text="TRAIN WITH PURPOSE", bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=9, pady=(0, 28))
        self.label(sidebar, "WORKSPACE", 8, MUTED, True).pack(anchor="w", padx=10, pady=(0, 10))
        nav_items = [("Overview", "⌂"), ("Routines", "▤"), ("Exercise Library", "▦"), ("Track Workout", "◉"), ("Progress", "▥"), ("Workout History", "◷"), ("Personal Records", "♛"), ("Recommendations", "✦"), ("Profile", "♙")]
        for name, icon in nav_items:
            b = tk.Button(sidebar, text=f"{icon}   {name}", command=lambda n=name: self.show_page(n), anchor="w", bg=SIDEBAR, fg=TEXT if name != "Overview" else GREEN, activebackground=GREEN_DARK, activeforeground=GREEN, relief="flat", padx=12, pady=11, font=("Segoe UI", 10, "bold"), cursor="hand2")
            b.pack(fill="x", pady=2)
        bottom = tk.Frame(sidebar, bg=SIDEBAR); bottom.pack(side="bottom", fill="x", pady=5)
        tk.Frame(bottom, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))
        tk.Label(bottom, text=self.user["display_name"], bg=SIDEBAR, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        tk.Label(bottom, text=self.user["email"], bg=SIDEBAR, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(3, 10))
        self.button(bottom, "Sign out", self.sign_out).pack(fill="x", padx=4)
        main = tk.Frame(shell, bg=BG); main.pack(side="right", fill="both", expand=True)
        header = tk.Frame(main, bg=BG, padx=25, pady=17); header.pack(fill="x")
        self.breadcrumb = tk.Label(header, text="Workspace  /  Overview", bg=BG, fg=MUTED, font=("Segoe UI", 10)); self.breadcrumb.pack(side="left")
        tk.Label(header, text="●  YOUR FITNESS, IN FOCUS", bg=BG, fg=GREEN, font=("Segoe UI", 8, "bold")).pack(side="right")
        self.content = tk.Frame(main, bg=BG, padx=25, pady=8); self.content.pack(fill="both", expand=True)
        self.show_page("Overview")

    def clear_content(self):
        for child in self.content.winfo_children(): child.destroy()

    def heading(self, eyebrow, title, subtitle=""):
        self.label(self.content, eyebrow.upper(), 8, GREEN, True).pack(anchor="w")
        self.label(self.content, title, 25, TEXT, True).pack(anchor="w", pady=(7, 3))
        if subtitle: self.label(self.content, subtitle, 10, MUTED, wraplength=900, justify="left").pack(anchor="w", pady=(0, 18))
        else: tk.Frame(self.content, bg=BG, height=15).pack()

    def card(self, parent, **kwargs):
        return tk.Frame(parent, bg=PANEL, padx=18, pady=17, highlightbackground=BORDER, highlightthickness=1, **kwargs)

    def metric_card(self, parent, title, value, note):
        f = self.card(parent)
        self.label(f, title.upper(), 8, MUTED, True).pack(anchor="w")
        self.label(f, str(value), 25, GREEN, True).pack(anchor="w", pady=(12, 2))
        self.label(f, note, 8, MUTED).pack(anchor="w")
        return f

    def show_page(self, name):
        self.page = name
        self.breadcrumb.configure(text=f"Workspace  /  {name}")
        self.clear_content()
        method = {
            "Overview": self.page_overview, "Routines": self.page_routines,
            "Exercise Library": self.page_library, "Track Workout": self.page_track,
            "Progress": self.page_progress, "Workout History": self.page_history,
            "Personal Records": self.page_records, "Recommendations": self.page_recommendations,
            "Profile": self.page_profile,
        }[name]
        method()

    def page_overview(self):
        p = self.db.profile(self.user["id"]); stats = self.db.stats(self.user["id"])
        self.heading("Your training space", f"Let's get stronger, {p['display_name']}.", "A little progress today goes a long way. Ready for your next session?")
        hero = tk.Frame(self.content, bg="#1d2a1d", padx=25, pady=20, highlightbackground="#35452e", highlightthickness=1)
        hero.pack(fill="x", pady=(0, 18))
        tk.Label(hero, text="YOUR WEEKLY MOMENTUM", bg="#1d2a1d", fg=GREEN, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(hero, text="Progress isn't always loud.\nKeep showing up.", bg="#1d2a1d", fg=TEXT, font=("Segoe UI", 22, "bold"), justify="left").pack(anchor="w", pady=(10, 4))
        tk.Label(hero, text="Build a routine that fits your life. Track the work, celebrate the wins.", bg="#1d2a1d", fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 14))
        self.button(hero, "＋  Plan a workout", lambda: self.show_page("Routines"), primary=True).pack(anchor="w")
        metrics = tk.Frame(self.content, bg=BG); metrics.pack(fill="x", pady=(0, 18))
        vals = [("Workouts logged", stats["workouts"], "Total sessions"), ("Time invested", f"{stats['minutes']} min", "Across all workouts"), ("Total volume", f"{stats['volume']:,.0f} kg", "Weight × reps logged"), ("Sets completed", stats["sets"], "One set at a time")]
        for i, (t, v, n) in enumerate(vals):
            m = self.metric_card(metrics, t, v, n); m.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6)); metrics.grid_columnconfigure(i, weight=1, uniform="metric")
        row = tk.Frame(self.content, bg=BG); row.pack(fill="both", expand=True)
        left = self.card(row); left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.label(left, "Your routines", 13, TEXT, True).pack(anchor="w")
        for r in self.db.routines(self.user["id"])[:4]:
            line = tk.Frame(left, bg=PANEL, pady=10); line.pack(fill="x")
            tk.Label(line, text="▤", bg=GREEN_DARK, fg=GREEN, width=3, pady=8, font=("Segoe UI", 12, "bold")).pack(side="left", padx=(0, 10))
            col = tk.Frame(line, bg=PANEL); col.pack(side="left", fill="x", expand=True)
            self.label(col, r["name"], 10, TEXT, True).pack(anchor="w")
            self.label(col, f"{r['focus']} · {len(r['exercise_names'])} exercises", 8, MUTED).pack(anchor="w", pady=(4, 0))
            self.button(line, "Start", lambda rid=r["id"]: self.begin_workout(rid)).pack(side="right")
        right = self.card(row); right.pack(side="right", fill="both", expand=True, padx=(8, 0))
        self.label(right, "Recent sessions", 13, TEXT, True).pack(anchor="w", pady=(0, 8))
        recent = self.db.workouts(self.user["id"])[:4]
        if not recent: self.label(right, "No sessions yet. Start a routine to log your first workout.", 9, MUTED, wraplength=300).pack(anchor="w", pady=20)
        for s in recent:
            self.label(right, s["routine_name"], 10, TEXT, True).pack(anchor="w", pady=(7, 0))
            self.label(right, f"{s['started_at'][:10]} · {s['duration_minutes']} min · {s['sets_completed']} sets", 8, MUTED).pack(anchor="w", pady=(2, 5))

    def page_routines(self):
        self.heading("Plan your training", "Your workout routines", "Create a plan that works for you, then start tracking when you're ready.")
        toolbar = tk.Frame(self.content, bg=BG); toolbar.pack(fill="x", pady=(0, 12))
        self.button(toolbar, "＋ Create routine", self.create_routine_dialog, primary=True).pack(side="left")
        for r in self.db.routines(self.user["id"]):
            c = self.card(self.content); c.pack(fill="x", pady=6)
            left = tk.Frame(c, bg=PANEL); left.pack(side="left", fill="x", expand=True)
            self.label(left, r["name"], 13, TEXT, True).pack(anchor="w")
            self.label(left, f"{r['focus']}  ·  {len(r['exercise_names'])} exercises", 9, GREEN).pack(anchor="w", pady=(4, 3))
            self.label(left, " · ".join(r["exercise_names"]), 9, MUTED, wraplength=620, justify="left").pack(anchor="w")
            actions = tk.Frame(c, bg=PANEL); actions.pack(side="right", padx=(10, 0))
            self.button(actions, "▶ Start", lambda rid=r["id"]: self.begin_workout(rid), primary=True).pack(pady=3)
            self.button(actions, "Delete", lambda rid=r["id"]: self.remove_routine(rid)).pack(pady=3)

    def create_routine_dialog(self, preset=None):
        exercises = self.db.exercises()
        win = tk.Toplevel(self); win.title("Create workout routine"); win.configure(bg=BG); win.geometry("520x680"); win.transient(self); win.grab_set()
        outer = tk.Frame(win, bg=BG, padx=22, pady=18); outer.pack(fill="both", expand=True)
        self.label(outer, "NEW ROUTINE", 9, GREEN, True).pack(anchor="w")
        name_var = tk.StringVar(value=(preset or {}).get("name", "")); focus_var = tk.StringVar(value=(preset or {}).get("focus", "Full body"))
        wrap, _ = self.field(outer, "ROUTINE NAME", name_var); wrap.pack(fill="x", pady=(14, 12))
        self.label(outer, "TRAINING FOCUS", 9, MUTED, True).pack(anchor="w", pady=(0, 5))
        ttk.Combobox(outer, textvariable=focus_var, values=["Full body", "Strength", "Build muscle", "Cardio", "Mobility", "Improve endurance"], state="readonly").pack(fill="x", ipady=5)
        self.label(outer, "SELECT EXERCISES", 9, GREEN, True).pack(anchor="w", pady=(15, 8))
        listwrap = tk.Frame(outer, bg=PANEL); listwrap.pack(fill="both", expand=True)
        canvas = tk.Canvas(listwrap, bg=PANEL, highlightthickness=0); sb = ttk.Scrollbar(listwrap, orient="vertical", command=canvas.yview); inner = tk.Frame(canvas, bg=PANEL)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=445); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        variables = {}
        preset_names = set((preset or {}).get("exercises", []))
        for ex in exercises:
            var = tk.BooleanVar(value=ex["name"] in preset_names)
            variables[ex["id"]] = var
            tk.Checkbutton(inner, text=f"{ex['name']}   ·   {ex['muscles']}", variable=var, anchor="w", bg=PANEL, fg=TEXT, activebackground=PANEL, activeforeground=GREEN, selectcolor=PANEL_2, relief="flat", padx=10, pady=8).pack(fill="x")
        def save():
            name = name_var.get().strip(); ids = [eid for eid, v in variables.items() if v.get()]
            if not name or not ids: messagebox.showwarning("Incomplete routine", "Enter a routine name and select at least one exercise.", parent=win); return
            self.db.create_routine(self.user["id"], name, focus_var.get(), ids); win.destroy(); self.show_page("Routines")
        self.button(outer, "Save routine", save, primary=True).pack(fill="x", pady=(13, 0))

    def remove_routine(self, rid):
        if messagebox.askyesno("Delete routine", "Delete this workout routine? Past workout history will be retained."):
            self.db.delete_routine(self.user["id"], rid); self.show_page("Routines")

    def page_library(self):
        self.heading("Learn the movement", "Exercise library", "Search exercises and open a step-by-step form tutorial.")
        row = tk.Frame(self.content, bg=BG); row.pack(fill="x", pady=(0, 13))
        q = tk.StringVar(); search = self.entry(row, q); search.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 10))
        self.button(row, "Search", lambda: render()).pack(side="left")
        listbox = tk.Frame(self.content, bg=BG); listbox.pack(fill="both", expand=True)
        def render():
            for w in listbox.winfo_children(): w.destroy()
            data = self.db.exercises(q.get())
            for i, ex in enumerate(data):
                card = self.card(listbox); card.pack(fill="x", pady=5)
                tk.Label(card, text="✦", bg=GREEN_DARK, fg=GREEN, font=("Segoe UI", 20), width=3, pady=8).pack(side="left", padx=(0, 12))
                col = tk.Frame(card, bg=PANEL); col.pack(side="left", fill="x", expand=True)
                self.label(col, ex["name"], 12, TEXT, True).pack(anchor="w")
                self.label(col, f"{ex['muscles']} · {ex['level']} · {ex['equipment']}", 9, MUTED).pack(anchor="w", pady=(4, 6))
                self.label(col, f"{ex['recommended_sets']} sets · {ex['recommended_reps']} reps", 9, GREEN).pack(anchor="w")
                self.button(card, "View tutorial", lambda e=dict(ex): self.tutorial_dialog(e)).pack(side="right", padx=(10, 0))
        render(); search.bind("<Return>", lambda e: render())

    def tutorial_dialog(self, ex):
        win = tk.Toplevel(self); win.title(f"Tutorial — {ex['name']}"); win.configure(bg=BG); win.geometry("570x620"); win.transient(self)
        pad = tk.Frame(win, bg=BG, padx=25, pady=22); pad.pack(fill="both", expand=True)
        tk.Label(pad, text="✦", bg=GREEN_DARK, fg=GREEN, font=("Segoe UI", 46), width=4, height=2).pack(anchor="w")
        self.label(pad, ex["name"], 22, TEXT, True).pack(anchor="w", pady=(16, 4))
        self.label(pad, f"{ex['muscles']}  ·  {ex['level']}", 10, GREEN, True).pack(anchor="w")
        self.label(pad, ex["cue"], 10, MUTED, wraplength=500, justify="left").pack(anchor="w", pady=(12, 15))
        self.label(pad, "HOW TO PERFORM", 9, GREEN, True).pack(anchor="w", pady=(0, 7))
        for idx, step in enumerate(ex["steps"].splitlines(), 1):
            row = tk.Frame(pad, bg=PANEL, padx=10, pady=9); row.pack(fill="x", pady=4)
            tk.Label(row, text=f"{idx:02d}", bg=GREEN_DARK, fg=GREEN, font=("Segoe UI", 9, "bold"), padx=8, pady=5).pack(side="left", padx=(0, 10))
            tk.Label(row, text=step, bg=PANEL, fg=TEXT, font=("Segoe UI", 9), wraplength=420, justify="left").pack(side="left", fill="x")
        tk.Label(pad, text="Use a comfortable range of motion and stop if you feel sharp pain.", bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=500).pack(anchor="w", pady=12)

    def page_track(self):
        self.heading("One rep at a time", "Track a workout", "Start a routine, enter each set's weight and reps, and mark completed sets.")
        if self.active_routine is None:
            routines = self.db.routines(self.user["id"])
            if not routines:
                self.label(self.content, "Create a routine before tracking a workout.", 11, MUTED).pack(anchor="w")
                self.button(self.content, "Create routine", self.create_routine_dialog, primary=True).pack(anchor="w", pady=10)
            else:
                for r in routines:
                    c = self.card(self.content); c.pack(fill="x", pady=6)
                    col = tk.Frame(c, bg=PANEL); col.pack(side="left", fill="x", expand=True)
                    self.label(col, r["name"], 12, TEXT, True).pack(anchor="w")
                    self.label(col, f"{r['focus']} · {len(r['exercise_names'])} exercises", 9, MUTED).pack(anchor="w", pady=(4, 0))
                    self.button(c, "▶ Start tracking", lambda rid=r["id"]: self.begin_workout(rid), primary=True).pack(side="right")
            return
        r = self.active_routine
        summary = self.card(self.content); summary.pack(fill="x", pady=(0, 12))
        self.label(summary, f"SESSION IN PROGRESS · {r['name']}", 12, GREEN, True).pack(anchor="w")
        self.label(summary, "Enter weights and reps for each set, then check Done for sets you completed.", 9, MUTED).pack(anchor="w", pady=(5, 0))
        # Scrollable exercise/set table
        container = tk.Frame(self.content, bg=BG); container.pack(fill="both", expand=True)
        canvas = tk.Canvas(container, bg=BG, highlightthickness=0); sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview); inner = tk.Frame(canvas, bg=BG)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=900); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.tracking_rows = []
        for ex in r["exercises"]:
            c = self.card(inner); c.pack(fill="x", pady=5)
            self.label(c, ex["name"], 12, TEXT, True).pack(anchor="w")
            self.label(c, f"{ex['muscles']} · Suggested {ex['recommended_sets']} sets × {ex['recommended_reps']}", 8, MUTED).pack(anchor="w", pady=(3, 9))
            row_head = tk.Frame(c, bg=PANEL); row_head.pack(fill="x")
            for txt, w in [("SET", 7), ("WEIGHT KG", 12), ("REPS", 10), ("DONE", 7)]:
                tk.Label(row_head, text=txt, width=w, anchor="w", bg=PANEL, fg=GREEN, font=("Segoe UI", 8, "bold")).pack(side="left", padx=3)
            for i in range(3): self.add_tracking_set(c, ex, i + 1)
            self.button(c, "＋ Add set", lambda parent=c, exercise=dict(ex): self.add_tracking_set(parent, exercise, None)).pack(anchor="w", pady=(8, 0))
        actions = tk.Frame(self.content, bg=BG); actions.pack(fill="x", pady=13)
        self.button(actions, "Discard workout", self.discard_workout).pack(side="left")
        self.button(actions, "Finish & save workout", self.finish_workout, primary=True).pack(side="right")

    def add_tracking_set(self, parent, ex, number):
        if number is None:
            number = 1 + sum(1 for row in self.tracking_rows if row["exercise_id"] == ex["id"])
        row = tk.Frame(parent, bg=PANEL, pady=3); row.pack(fill="x")
        tk.Label(row, text=f"{number:02d}", width=7, anchor="w", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=3)
        weight = tk.StringVar(value="0"); reps = tk.StringVar(value="8"); done = tk.BooleanVar(value=False)
        ew = self.entry(row, weight, width=10); ew.pack(side="left", padx=3, ipady=5)
        er = self.entry(row, reps, width=8); er.pack(side="left", padx=3, ipady=5)
        tk.Checkbutton(row, variable=done, bg=PANEL, activebackground=PANEL, selectcolor=PANEL_2, text="Done", fg=TEXT).pack(side="left", padx=8)
        self.tracking_rows.append({"exercise_id": ex["id"], "exercise_name": ex["name"], "set_number": number, "weight_var": weight, "reps_var": reps, "done_var": done})

    def begin_workout(self, rid):
        self.active_routine = self.db.routine(self.user["id"], rid)
        if not self.active_routine or not self.active_routine["exercises"]:
            messagebox.showwarning("Empty routine", "This routine has no exercises."); self.active_routine = None; return
        self.workout_started = datetime.now(); self.show_page("Track Workout")

    def discard_workout(self):
        if messagebox.askyesno("Discard workout", "Discard this workout session without saving?"):
            self.active_routine = None; self.workout_started = None; self.tracking_rows = []; self.show_page("Track Workout")

    def finish_workout(self):
        saved = []
        for row in self.tracking_rows:
            try: weight = float(row["weight_var"].get() or 0); reps = int(row["reps_var"].get() or 0)
            except ValueError:
                messagebox.showwarning("Check set values", "Weight must be a number and reps must be a whole number."); return
            if weight < 0 or reps < 0:
                messagebox.showwarning("Invalid values", "Weight and reps cannot be negative."); return
            saved.append({"exercise_id": row["exercise_id"], "set_number": row["set_number"], "weight": weight, "reps": reps, "done": row["done_var"].get()})
        if not any(s["done"] for s in saved):
            messagebox.showwarning("No completed sets", "Mark at least one set as Done before saving."); return
        name = self.active_routine["name"]
        self.db.save_workout(self.user["id"], name, self.workout_started or datetime.now(), saved)
        self.active_routine = None; self.workout_started = None; self.tracking_rows = []
        messagebox.showinfo("Workout saved", "Great work! Your workout has been saved to the database.")
        self.show_page("Overview")

    def page_history(self):
        self.heading("Every session counts", "Workout history", "Review past sessions saved to your FitTrack database.")
        bar = tk.Frame(self.content, bg=BG); bar.pack(fill="x", pady=(0, 10))
        q = tk.StringVar(); ent = self.entry(bar, q); ent.pack(side="left", fill="x", expand=True, ipady=9, padx=(0, 8))
        tree = ttk.Treeview(self.content, columns=("date", "routine", "duration", "sets", "volume"), show="headings", height=15)
        for col, title, width in [("date", "DATE", 160), ("routine", "WORKOUT", 250), ("duration", "MINUTES", 90), ("sets", "SETS", 80), ("volume", "VOLUME KG", 110)]: tree.heading(col, text=title); tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        def render():
            tree.delete(*tree.get_children())
            for w in self.db.workouts(self.user["id"], q.get()): tree.insert("", "end", iid=str(w["id"]), values=(w["started_at"][:16].replace("T", " "), w["routine_name"], w["duration_minutes"], w["sets_completed"], f"{w['volume_kg']:,.0f}"))
        render(); ent.bind("<Return>", lambda e: render())
        row = tk.Frame(self.content, bg=BG); row.pack(fill="x", pady=10)
        self.button(row, "Search history", render).pack(side="left")
        def delete():
            sel = tree.selection()
            if not sel: messagebox.showinfo("Select a workout", "Choose a session first."); return
            if messagebox.askyesno("Delete session", "Permanently delete the selected workout from history?"):
                self.db.delete_workout(self.user["id"], int(sel[0])); render()
        self.button(row, "Delete selected", delete).pack(side="right")

    def page_progress(self):
        self.heading("The work adds up", "Your progress", "A snapshot of your training consistency, time, and total volume.")
        s = self.db.stats(self.user["id"]); profile = self.db.profile(self.user["id"])
        row = tk.Frame(self.content, bg=BG); row.pack(fill="x", pady=(0, 18))
        for i, (t, v, n) in enumerate([("Workouts", s["workouts"], "All time"), ("Training time", f"{s['minutes']} min", "Recorded sessions"), ("Volume moved", f"{s['volume']:,.0f} kg", "Weight × reps"), ("Completed sets", s["sets"], "Logged sets")]):
            c = self.metric_card(row, t, v, n); c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6)); row.grid_columnconfigure(i, weight=1, uniform="progress")
        panel = self.card(self.content); panel.pack(fill="x", pady=5)
        self.label(panel, "Weekly consistency", 13, TEXT, True).pack(anchor="w")
        self.label(panel, f"{s['week']} sessions this week  /  target {profile['weekly_target']}", 10, MUTED).pack(anchor="w", pady=(6, 10))
        progress = min(100, int(s["week"] / max(1, profile["weekly_target"]) * 100))
        bar = tk.Frame(panel, bg=PANEL_2, height=12); bar.pack(fill="x"); tk.Frame(bar, bg=GREEN, height=12, width=max(2, progress * 7)).pack(side="left")
        self.label(panel, f"{progress}% of weekly target", 9, GREEN, True).pack(anchor="w", pady=(8, 0))
        c = self.card(self.content); c.pack(fill="both", expand=True, pady=8)
        self.label(c, "Strength highlights", 13, TEXT, True).pack(anchor="w", pady=(0, 8))
        if not s["prs"]: self.label(c, "No personal records yet. Log a completed set with a weight to get started.", 9, MUTED).pack(anchor="w", pady=8)
        else:
            for pr in s["prs"][:7]:
                row = tk.Frame(c, bg=PANEL, pady=8); row.pack(fill="x")
                self.label(row, pr["name"], 10, TEXT, True).pack(side="left")
                self.label(row, f"{pr['best']:g} kg", 10, GREEN, True).pack(side="right")

    def page_records(self):
        self.heading("Celebrate your wins", "Personal records", "Your highest completed weight for each exercise, calculated from workout history.")
        prs = self.db.stats(self.user["id"])["prs"]
        tree = ttk.Treeview(self.content, columns=("exercise", "muscle", "weight"), show="headings", height=18)
        for col, title, width in [("exercise", "EXERCISE", 270), ("muscle", "MUSCLES", 280), ("weight", "BEST WEIGHT", 140)]: tree.heading(col, text=title); tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        for pr in prs: tree.insert("", "end", values=(pr["name"], pr["muscles"], f"{pr['best']:g} kg"))
        if not prs: self.label(self.content, "Your leaderboard is waiting. Complete a weighted set to see your records here.", 10, MUTED).pack(anchor="w", pady=10)

    def page_recommendations(self):
        self.heading("A plan that fits you", "Workout recommendations", "Choose your focus to create a starter routine you can customize.")
        goal = tk.StringVar(value=self.db.profile(self.user["id"])["fitness_goal"])
        panel = self.card(self.content); panel.pack(fill="x", pady=(0, 15))
        self.label(panel, "WHAT'S YOUR FOCUS?", 9, GREEN, True).pack(anchor="w")
        ttk.Combobox(panel, textvariable=goal, values=["Build strength", "Build muscle", "Improve endurance", "Get moving", "Stay consistent"], state="readonly").pack(fill="x", pady=(8, 4), ipady=5)
        result = tk.Frame(self.content, bg=BG); result.pack(fill="both", expand=True)
        def render():
            for w in result.winfo_children(): w.destroy()
            g = goal.get()
            if g == "Improve endurance": names = ["Jumping Jack", "Walking Lunge", "Plank"]
            elif g == "Build muscle": names = ["Barbell Squat", "Dumbbell Row", "Push-up", "Dumbbell Shoulder Press"]
            elif g == "Get moving": names = ["Push-up", "Walking Lunge", "Plank"]
            else: names = ["Barbell Squat", "Romanian Deadlift", "Dumbbell Row", "Push-up"]
            self.label(result, "SUGGESTED STARTER PLAN", 9, GREEN, True).pack(anchor="w", pady=(0, 8))
            for n in names:
                self.label(result, "•  " + n, 11, TEXT).pack(anchor="w", pady=6)
            self.button(result, "Create this routine", lambda: self.create_routine_dialog({"name": g + " Plan", "focus": g, "exercises": names}), primary=True).pack(anchor="w", pady=15)
        self.button(panel, "Refresh recommendation", render).pack(anchor="w", pady=(10, 0)); render()

    def page_profile(self):
        self.heading("Your baseline", "Your profile", "Personalize FitTrack around your goals and weekly schedule.")
        p = self.db.profile(self.user["id"])
        form = self.card(self.content); form.pack(fill="x")
        name = tk.StringVar(value=p["display_name"]); goal = tk.StringVar(value=p["fitness_goal"]); level = tk.StringVar(value=p["experience_level"]); target = tk.IntVar(value=p["weekly_target"]); weight = tk.StringVar(value="" if p["body_weight"] is None else str(p["body_weight"]))
        wrap, _ = self.field(form, "DISPLAY NAME", name); wrap.pack(fill="x", pady=(0, 13))
        self.label(form, "FITNESS GOAL", 9, MUTED, True).pack(anchor="w", pady=(0, 5)); ttk.Combobox(form, textvariable=goal, values=["Build strength", "Build muscle", "Improve endurance", "Get moving", "Stay consistent"], state="readonly").pack(fill="x", ipady=5, pady=(0, 13))
        self.label(form, "EXPERIENCE LEVEL", 9, MUTED, True).pack(anchor="w", pady=(0, 5)); ttk.Combobox(form, textvariable=level, values=["Beginner", "Intermediate", "Advanced"], state="readonly").pack(fill="x", ipady=5, pady=(0, 13))
        self.label(form, "WEEKLY WORKOUT TARGET", 9, MUTED, True).pack(anchor="w", pady=(0, 5)); ttk.Combobox(form, textvariable=target, values=[2, 3, 4, 5, 6, 7], state="readonly").pack(fill="x", ipady=5, pady=(0, 13))
        wrap, _ = self.field(form, "BODY WEIGHT KG (OPTIONAL)", weight); wrap.pack(fill="x", pady=(0, 18))
        def save():
            try:
                if weight.get().strip() and float(weight.get()) <= 0: raise ValueError
                self.db.save_profile(self.user["id"], name.get(), goal.get(), level.get(), int(target.get()), weight.get())
                self.user["display_name"] = name.get().strip() or "Athlete"
                messagebox.showinfo("Profile saved", "Your profile has been saved to the database.")
                self.show_page("Profile")
            except ValueError: messagebox.showwarning("Invalid body weight", "Enter a positive number or leave body weight blank.")
        self.button(form, "Save profile", save, primary=True).pack(anchor="w")

    def sign_out(self):
        self.user = None; self.active_routine = None; self.show_auth()

    def _on_close(self):
        try: self.db.close()
        finally: self.destroy()

if __name__ == "__main__":
    app = FitTrackApp()
    app.mainloop()
