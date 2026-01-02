#!/usr/bin/env python3
import subprocess
import json
import requests
import time

# === CONFIGURATION ===
BACKEND_URL = "https://global-connection-se4b.onrender.com/api"  # replace with your server URL if cloud
POLL_INTERVAL = 5  # seconds between checking outgoing messages
PROCESSED_FOLDER = "/data/data/com.termux/files/home/.sms_processed.json"

# Load processed SMS IDs to avoid duplicates
try:
    with open(PROCESSED_FOLDER, "r") as f:
        processed_ids = set(json.load(f))
except:
    processed_ids = set()


def save_processed():
    with open(PROCESSED_FOLDER, "w") as f:
        json.dump(list(processed_ids), f)


def read_incoming_sms():
    """Reads unread SMS using Termux API"""
    cmd = ["termux-sms-list", "-l", "20"]  # get last 20 messages
    result = subprocess.run(cmd, capture_output=True, text=True)
    messages = json.loads(result.stdout)

    new_messages = []
    for msg in messages:
        sms_id = msg.get("id") or msg.get("thread_id") or msg.get("received")  # fallback
        if sms_id and sms_id not in processed_ids:
            new_messages.append(msg)
            processed_ids.add(sms_id)

    if new_messages:
        save_processed()

    return new_messages



def send_to_backend(msg):
    """Send SMS content to Django backend"""
    phone = msg["address"]
    content = msg["body"]

    payload = {"phone": phone, "message": content}
    try:
        r = requests.post(f"{BACKEND_URL}/incoming/", json=payload)
        if r.status_code == 200:
            print(f"[INCOMING] Sent to backend: {content[:50]}")
        else:
            print(f"[ERROR] Backend returned {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Sending to backend failed: {e}")


def poll_outgoing():
    """Poll backend for unsent AI replies"""
    try:
        r = requests.get(f"{BACKEND_URL}/outgoing/")
        if r.status_code != 200:
            print(f"[ERROR] Outgoing fetch failed: {r.status_code}")
            return []

        return r.json()
    except Exception as e:
        print(f"[ERROR] Outgoing fetch exception: {e}")
        return []


def send_sms(phone, message):
    """Send SMS using Termux API"""
    cmd = ["termux-sms-send", "-n", phone, message]
    subprocess.run(cmd)
    print(f"[SENT] {phone}: {message[:50]}")


def mark_sent(msg_id):
    """Mark message as sent in backend"""
    try:
        r = requests.post(f"{BACKEND_URL}/sent/", json={"id": msg_id})
        if r.status_code == 200:
            print(f"[MARKED SENT] ID: {msg_id}")
        else:
            print(f"[ERROR] Mark sent failed: {r.status_code}")
    except Exception as e:
        print(f"[ERROR] Mark sent exception: {e}")


# === MAIN LOOP ===
if __name__ == "__main__":
    print("[SMS Gateway] Starting...")
    while True:
        # 1️⃣ Check for new SMS
        incoming = read_incoming_sms()
        for msg in incoming:
            send_to_backend(msg)

        # 2️⃣ Check for AI replies to send
        outgoing = poll_outgoing()
        for msg in outgoing:
            send_sms(msg["phone"], msg["message"])
            mark_sent(msg["id"])

        # 3️⃣ Wait before next poll
        time.sleep(POLL_INTERVAL)
