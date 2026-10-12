# FitTrack — Workout Management System

A desktop GUI workout manager built with **Python Tkinter** and an **SQLite database**. It needs Python 3.10+ and has no third-party package dependencies.

## Run it

1. Install Python 3.10 or newer from https://www.python.org/downloads/ (on Windows, tick **Add Python to PATH**).
2. Extract this folder to your computer.
3. Open a terminal/PowerShell in the folder.
4. Run:

   ```bash
   python fittrack.py
   ```

   On some macOS/Linux systems, use `python3 fittrack.py`.

5. Choose **Sign up**, enter a display name, email and password (at least 8 characters), then log in.

The app automatically creates `fittrack.db` in this folder on first run. This file is the SQLite database containing users, profiles, routines, exercises, workout history, and completed sets. Back up this file to back up the app's data.

## Included features

- Dark GUI with neon-green accents
- Sign up / log in / sign out (passwords are stored as salted PBKDF2-SHA256 hashes, not plain text)
- User profile and training goals
- Create and delete workout routines
- Seeded exercise library with form cues and step-by-step tutorial windows
- Workout tracking with weight, reps, completed-set checkboxes and extra sets
- SQLite-backed workout history with search and delete
- Progress totals, weekly-target progress, training volume, and personal records
- Goal-based workout recommendations
- Per-user profile/routine/workout records using SQLite foreign keys

## Project files

- `fittrack.py` — complete GUI, account flow, business logic and SQLite schema
- `requirements.txt` — no external dependencies required
- `fittrack.db` — created automatically at runtime; not included in this ZIP

## Notes

- This is a local desktop edition. Its SQLite database lives on the computer where it runs; it does not sync between devices.
- Exercise tutorial windows provide written steps and cues, not recorded workout video.
- Use this as a student project starter. For a production service, add password reset, stronger account security controls, database backup procedures, and formal privacy/terms pages.
