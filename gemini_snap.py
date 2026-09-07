"""
gemini_snap.py — Hardened. No hooks. Always-on-top overlay. Click to dismiss.
"""

import sys, io, time, threading, base64, ctypes
from ctypes import wintypes
import requests
import hashlib
import uuid
import os
import json
from datetime import datetime

SUPABASE_URL = "https://ayenovpjaahdvoqmoqbg.supabase.co"
SUPABASE_KEY = "sb_publishable_DbNeIQMh3sq1PffBE-H39Q_ueRKha56"
LICENSE_FILE = os.path.join(os.getenv("APPDATA"), "myapp_license.json")

def get_hardware_id():
    raw = str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()

def save_license(key, hwid):
    with open(LICENSE_FILE, "w") as f:
        json.dump({"key": key, "hwid": hwid}, f)

def load_license():
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, "r") as f:
            return json.load(f)
    return None

def validate_with_server(key, hwid):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }

    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/licenses?key=eq.{key}&select=*",
        headers=headers
    )

    if res.status_code != 200 or not res.json():
        return False, "Key not found"

    record = res.json()[0]

    if record["expires_at"]:
        expires = datetime.fromisoformat(record["expires_at"].replace("Z", ""))
        if datetime.utcnow() > expires:
            return False, "Key expired. Please renew."

    if record["activated"] and record["hardware_id"] != hwid:
        return False, "Key already used on another PC."

    if not record["activated"]:
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/licenses?key=eq.{key}",
            headers={**headers, "Content-Type": "application/json"},
            json={"activated": True, "hardware_id": hwid}
        )
        save_license(key, hwid)

    return True, "OK"

def ask_license_key(error_msg=""):
    """Show a popup window asking for the license key."""
    import tkinter as tk
    from tkinter import messagebox

    result = {"key": None}

    root = tk.Tk()
    root.title("GeminiSnap — License")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#1a1a2e")

    w, h = 420, 180 if error_msg else 150
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    tk.Label(
        root, text="Enter your license key",
        font=("Segoe UI", 12, "bold"), fg="#eee", bg="#1a1a2e"
    ).pack(pady=(16, 6))

    if error_msg:
        tk.Label(
            root, text=error_msg,
            font=("Segoe UI", 9), fg="#ff6b6b", bg="#1a1a2e", wraplength=380
        ).pack(pady=(0, 6))

    entry = tk.Entry(root, font=("Consolas", 12), width=36, justify="center")
    entry.pack(pady=4)
    entry.focus_set()

    def submit(event=None):
        key = entry.get().strip().upper()
        if not key:
            messagebox.showwarning("License", "Please enter a key.", parent=root)
            return
        result["key"] = key
        root.destroy()

    def cancel():
        root.destroy()

    btn = tk.Frame(root, bg="#1a1a2e")
    btn.pack(pady=12)
    tk.Button(btn, text="Activate", command=submit, width=12).pack(side="left", padx=6)
    tk.Button(btn, text="Cancel", command=cancel, width=12).pack(side="left", padx=6)

    entry.bind("<Return>", submit)
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return result["key"]


def check_license():
    hwid = get_hardware_id()
    saved = load_license()

    if saved:
        ok, msg = validate_with_server(saved["key"], hwid)
        if ok:
            return True
        # Saved key bad/expired — fall through and ask again
        error = msg
    else:
        error = ""

    while True:
        key = ask_license_key(error)
        if not key:
            return False
        ok, msg = validate_with_server(key, hwid)
        if ok:
            save_license(key, hwid)
            return True
        error = msg

# ─── GATE ──────────────────────────────────────────
if not check_license():
    sys.exit(1)

# YOUR EXISTING CODE STARTS HERE
try:
    import pyautogui
    import tkinter as tk
except ImportError:
    print("Missing: pip install pyautogui pillow requests")
    sys.exit(1)

# ── CONFIG ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = "AQ.Ab8RN6KHDIkdH4uJ-QofDqqwxPA7xBkqXJlGocbr34tlafkgug"
GEMINI_MODEL     = "gemini-3.6-flash"
CLOUDFLARE_WORKER_URL = "https://mute-dawn-b141.wain6035.workers.dev/"
HOTKEY_VKCODE    = 0xDD   # ] key
DEFAULT_PROMPT   = "Look at the screen and answer directly. No explanations, no descriptions, just the answer. Be extremely brief."
NOTIF_TIMEOUT    = 5
SCREENSHOT_DELAY = 0.3
POLL_INTERVAL    = 0.05
# ─────────────────────────────────────────────────────────────────────────────

user32 = ctypes.windll.user32
_busy  = False

HWND_TOPMOST   = -1
SWP_NOMOVE     = 0x0002
SWP_NOSIZE     = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FLAGS      = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

WS_EX_TOPMOST    = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


def force_topmost(hwnd):
    """Hammer the window to topmost every 100ms forever."""
    def _loop():
        while True:
            try:
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
            except:
                break
            time.sleep(0.1)
    threading.Thread(target=_loop, daemon=True).start()


def show_overlay(message: str):
    def _show():
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-alpha", 0.93)
        root.attributes("-topmost", True)
        root.configure(bg="#1a1a2e")

        # Click anywhere to dismiss
        root.bind("<Button-1>", lambda e: root.destroy())

        # Extra window styles
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if hwnd == 0:
            hwnd = root.winfo_id()

        GWL_EXSTYLE = -20
        cur_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              cur_style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        label = tk.Label(root, text=message, font=("Segoe UI", 12),
                         fg="#00ff88", bg="#1a1a2e", wraplength=440,
                         justify="left", padx=16, pady=12, cursor="hand2")
        label.pack()
        # Click on label also dismisses
        label.bind("<Button-1>", lambda e: root.destroy())

        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        root.geometry(f"+{sw-w-20}+{sh-h-60}")
        root.update()

        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        force_topmost(hwnd)

        root.after(NOTIF_TIMEOUT * 1000, root.destroy)
        root.mainloop()

    threading.Thread(target=_show, daemon=True).start()


def take_screenshot() -> str:
    time.sleep(SCREENSHOT_DELAY)
    img = pyautogui.screenshot()
    img.thumbnail((1280, 720))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def ask_gemini(image_b64: str) -> str:
    worker_endpoint = f"{CLOUDFLARE_WORKER_URL.rstrip('/')}/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [{
            "parts": [
                {"text": DEFAULT_PROMPT},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_b64
                    }
                }
            ]
        }]
    }

    response = requests.post(worker_endpoint, headers=headers, json=payload, timeout=12)

    if response.status_code == 200:
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text}")


def run_pipeline():
    global _busy
    if _busy:
        return
    _busy = True
    try:
        show_overlay("Analyzing...")
        image_b64 = take_screenshot()
        answer = ask_gemini(image_b64)
        show_overlay(answer)
    except Exception as e:
        show_overlay(f"Error: {e}")
    finally:
        _busy = False


def poll_hotkey():
    was_down = False
    while True:
        is_down = bool(user32.GetAsyncKeyState(HOTKEY_VKCODE) & 0x8000)
        if is_down and not was_down:
            threading.Thread(target=run_pipeline, daemon=True).start()
        was_down = is_down
        time.sleep(POLL_INTERVAL)


def main():
    print("GeminiSnap running. Press ] to analyse. Ctrl+C to quit.")
    threading.Thread(target=poll_hotkey, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped.")


if __name__ == "__main__":
    main()
