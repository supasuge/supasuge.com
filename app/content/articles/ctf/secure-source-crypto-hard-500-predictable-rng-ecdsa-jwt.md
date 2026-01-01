---
title: Secure Source (Crypto, Hard 500) — Predictable RNG in ECDSA-JWT (Incomplete
  Writeup)
summary: An incomplete but structured writeup for the “Secure Source” challenge. The
  app signs JWTs with a custom ECDSA implementation whose nonce comes from Python’s
  Mersenne Twister. Note IDs leak enough RNG output to recover MT state and predict
  the next nonce, enabling signature forgery. Also covers where the public key should
  come from and how to obtain it in practice.
tags:
- ctf
- crypto
- ecdsa
- jwt
- mersenne-twister
- rng
- flask
- web
published: true
date: '2025-12-31'
slug: secure-source-crypto-hard-500-predictable-rng-ecdsa-jwt
---

# Secure Source (Crypto, Hard: 500) — Predictable RNG in ECDSA-JWT (Incomplete Writeup)

Full writeup coming soon… this is currently **INCOMPLETE**, but the core vulnerability and exploitation plan are captured and cleaned up below.

This challenge is a Flask note app that authenticates via a JWT-like token signed with an in-house ECDSA implementation. The intended break is that the ECDSA nonce $k$ is generated from Python’s `random` (Mersenne Twister), and the app leaks MT state through predictable note IDs. With 624 outputs you can recover the MT state, predict the next RNG output, and then predict the nonce used to sign the next token.

A remaining practical question (also in my notes): **where do `pubkey.x` and `pubkey.y` come from**, since `/dashboard` requires a `pubkey` cookie.

---

## Source code (relevant parts)

### `utils.py`
```python
import string
ALPHABET = string.printable
# long to bytes
def l2b(n, L=32):
    return n.to_bytes(L, 'big')
# bytes to long
def b2l(b):
    return int.from_bytes(b, 'big')
```

### `views.py` (dashboard gate)
```python
@bp.route('/dashboard', methods=['GET'])
def dashboard():
    cookies = request.cookies
    if not ('token' in cookies and 'pubkey' in cookies):
        flash('Make sure the proper cookies are set.', 'error')
        return redirect(url_for('views.home'))

    token = request.cookies.get('token')
    pubkey = request.cookies.get('pubkey').split(',')

    if not jwt.verify_token(pubkey, token):
        flash('Your token could not be verified.', 'error')
        return redirect(url_for('views.home'))
    
    if not jwt.check_admin(token):
        flash('Only admins can access the dashboard.', 'error')
        return redirect(url_for('views.home'))

    return render_template('dashboard.html', secret=open('/flag.txt').read()), 200
```

Key takeaways:

- Dashboard requires two cookies:
  - `token`: the signed token string.
  - `pubkey`: a comma-separated pair of integers: `x,y`.
- The server verifies the token *using the public key supplied by the client*.
- Then it checks admin by reading the token payload and comparing username.

### `database.py` + `models/note.py` (note IDs leak RNG)

`models/note.py`
```python
from crypto.rng import generator

class Note:
    def __init__(self, title, description):
        self.id = generator.next()
        self.title = title
        self.description = description
```

`crypto/rng.py`
```python
import random

class RNG:
    def __init__(self):
        self.pool = list(random.getstate()[1][:-1])

    def next(self):
        if len(self.pool) < 1:
            self.reset_pool()
        return self.pool.pop(0)

    def reset_pool(self):
        self.pool = list(random.getstate()[1][:-1])

    def choices(self, s, k):
        return ''.join(random.choices(s, k=k))

generator = RNG()
```

This is the core leak:

- `generator.pool` is initialized from `random.getstate()[1][:-1]`.
- For MT, `getstate()[1]` contains the internal state array (624 32-bit integers) plus an index. Slicing `[:-1]` drops the index, leaving the 624-word state.
- `generator.next()` pops and returns the **raw internal state words**, not even tempered outputs.

So each created note leaks one 32-bit word from MT’s state.

### `crypto/ecdsa.py` (nonce derived from MT)
```python
class ECDSA:
    def sign(self, m):
        k = int(generator.choices(ALPHABET, 32).encode().hex(), 16)
        H = int(sha256(m).hexdigest(), 16)
        r = (G * k).x
        s = pow(k, -1, q) * (H + self.x * r) % q
        if s == 0:
            self.sign(m)
        return base64.b64encode(l2b(r) + l2b(s))
```

This is the second half of the break:

- ECDSA nonce must be cryptographically random and never repeated.
- Here it is derived from `generator.choices(...)`, and `generator.choices()` calls `random.choices()` (Python MT), which is predictable once you recover MT state.

### `crypto/jwt.py` (token format)
```python
class Tokenizer:
    def create_token(self, user):
        header = b64encode(json.dumps({'alg': 'EC256', 'type': 'JWT'}).encode())
        payload = b64encode(json.dumps({
            'username': user.username,
            'email': user.email,
            'iat': str(int(time.time()))
        }).encode())
        signature = ecc.sign(header + b'.' + payload)

        return header + b'.' + payload + b'.' + signature

    def verify_token(self, pubkey, token):
        if len(pubkey) != 2:
            return False

        if not (pubkey[0].isnumeric() and pubkey[1].isnumeric()):
            return False

        header, payload, signature = token.split('.')
        return ecc.verify(pubkey, signature, header + '.' + payload)

    def check_admin(self, token):
        _, payload, _ = token.split('.')
        payload_json = json.loads(b64decode(payload).decode())
        username = payload_json['username']
        return username == 'HTBAdmin1337_ZUSD3uQG4I'
```

Important details:

- This is **not** standard JWT base64url encoding (they use `base64.b64encode` without URL-safe alphabet and without stripping padding).
- Server trusts the caller-provided `pubkey` cookie to verify signatures.
- Admin is simply `username == 'HTBAdmin1337_ZUSD3uQG4I'`.

---

## Directory structure

```python
├── crypto_secure_source
│   ├── Dockerfile
│   ├── build-docker.sh
│   ├── challenge
│   │   └── application
│   │       ├── app.py # main application logic
│   │       ├── crypto
│   │       │   ├── curve.py # ECC Function's
│   │       │   ├── ecdsa.py # ECDSA function's
│   │       │   ├── jwt.py # jwt generation using ECDSA implementation
│   │       │   └── rng.py # contains the random number generation function... This is where the vuln is here
│   │       ├── database.py
│   │       ├── models
│   │       │   ├── note.py
│   │       │   └── user.py
│   │       ├── requirements.txt
│   │       ├── static
│   │       │   ├── icon.png
│   │       │   ├── jetbrains-mono.ttf
│   │       │   └── main.css
│   │       ├── templates
│   │       │   ├── create_note.html
│   │       │   ├── dashboard.html
│   │       │   ├── index.html
│   │       │   ├── login.html
│   │       │   ├── register.html
│   │       │   └── view_notes.html
│   │       ├── utils.py
│   │       └── views.py
│   └── flag.txt
```

---

## Vulnerability summary

### 1) MT internal state is directly exposed

Each note creation returns `Note.id = generator.next()` where `generator.pool` is literally the MT state array words. Collecting 624 note IDs gives you the full MT internal state in order.

### 2) ECDSA nonce $k$ is generated from MT

`generator.choices(ALPHABET, 32)` uses `random.choices`, thus MT output drives the resulting 32-character string, and then it is interpreted as a 256-bit integer.

Once you recover MT state, you can predict subsequent random output and thus predict the nonce $k$ for a future signature.

### 3) Public key is supplied by the client

`verify_token(pubkey, token)` takes `pubkey` from a cookie. That means **the verifier does not have a pinned key**.

If you can produce a valid signature under *some* key, and pass the corresponding public key in the cookie, verification will succeed.

However, to pass `check_admin`, the token payload must also contain the admin username.

---

## Solution strategy (as drafted)

- Admin username:
  - `HTBAdmin1337_ZUSD3uQG4I`

Steps:

1. Make account
2. Create 624 notes then parse the Note IDs to extract the 32-bit integers
3. Recover MT internal state and predict the next nonce used for ECDSA signatures
4. Forge a signature with payload username set to admin

---

## About the “pubkey x,y” question

> How do I get the public key x, and y?

There are two distinct paths, depending on what the challenge intended.

### Path A (most likely intended): you *don’t need* the server’s public key

Because `/dashboard` verifies the signature using the **client-provided** `pubkey` cookie, you can choose *your own* keypair:

- Generate an ECDSA keypair locally $(x, Q=xG)$.
- Put `pubkey = f"{Q.x},{Q.y}"` into the cookie.
- Sign the token with your private key $x$.

If you can do that, then you bypass the entire “recover nonce” step.

But: the server’s signing algorithm is not standard ECDSA (it uses `r = (G*k).x` without reducing mod $q$, and verify compares `r == U.x` rather than `r mod q`). If you generate your own tokens, you must match their exact signing/verification behavior.

### Path B: you really are trying to impersonate the server’s key

If the intended solve is “predict server nonce $k$ and forge a token as if signed by the server”, then you need either:

- the server public key $(Q.x,Q.y)$ to put in the cookie, or
- a way to derive the private key $x$.

In the provided code, `ecc.Q = G * ecc.x`, but the app never exposes `ecc.Q` directly. So you’d look for:

- A route/template that prints the public key (common in CTFs when the verifier expects a public key).
- A `Set-Cookie: pubkey=...` somewhere (e.g., during login).
- JavaScript that fetches it.

If none of those exist, then the only remaining way is to exploit that the server lets the client choose the verification key (Path A), making “get the public key” unnecessary.

This writeup is incomplete here because the note didn’t include HTTP traces or templates to confirm whether `pubkey` is ever issued by the server.

---

## Exploit script (draft)

The note includes a WIP script that:

- registers,
- creates notes until it collects 624 IDs,
- attempts to use `randcrack` to predict RNG output,
- and then attempts to forge an admin JWT.

Preserving it verbatim:

```python
#!/usr/bin/python3

import requests
from bs4 import BeautifulSoup
import randcrack
import time
import random
import base64
import json
import time
from fastecdsa import curve, ecdsa
from fastecdsa.point import Point
import hashlib

ADMIN_USERNAME = "HTBAdmin1337_ZUSD3uQG4I"
E = curve.brainpoolP256r1
G = E.G
q = E.q

def create_admin_jwt(predicted_k):
    header = {'alg': 'EC256', 'typ': 'JWT'}
    payload = {
        'username': ADMIN_USERNAME,
        'email': 'admin@example.com',
        'iat': str(int(time.time()))
    }

    header_b64 = base64.b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode().rstrip('=')

    message = f"{header_b64}.{payload_b64}"

    # Use the predicted k to sign the message
    r = (G * predicted_k).x
    H = int(hashlib.sha256(message.encode()).hexdigest(), 16)
    s = pow(predicted_k, -1, q) * (H + ecc.x * r) % q

    signature = base64.b64encode(l2b(r) + l2b(s)).decode()

    return f"{message}.{signature}"

def l2b(n, L=32):
    return n.to_bytes(L, 'big')

BASE_URL = "http://83.136.255.40:44540"


SESSION = requests.Session()


def register_user():
    data = {
        "username": "user" + str(int(time.time())),
        "password": "password123",
        "email": "user@example.com"
        }

    response = SESSION.post(f"{BASE_URL}/register", data=data)
    if "The user was registered successfully" in response.text:
        print("User registered successfully")
    else:
        print("Failed to register user")
        exit(1)

def login_user(username, password):
    data = {
        "username": username,
        "password": password
    }
    response = SESSION.post(f"{BASE_URL}/login", data=data)
    if "Welcome" in response.text:
        print("Logged in successfully")
    else:
        print("Failed to log in")
        exit(1)

def create_note():
    data = {
        "title": "Note Title",
        "description": "Note Description"
    }
    response = SESSION.post(f"{BASE_URL}/create-note", data=data)
    if "Your note was successfully saved" in response.text:
        print("Note created successfully")
    else:
        print("Failed to create note")

def get_note_ids():
    response = SESSION.get(f"{BASE_URL}/view-notes")
    soup = BeautifulSoup(response.text, 'html.parser')
    note_ids = []
    for p in soup.find_all('p'):
        if 'ID :' in p.text:
            note_ids.append(int(p.text.split(':')[1].strip()))
    return note_ids

def main():
    username = "user" + str(int(time.time()))
    password = "password123"

    register_user()
    login_user(username, password)

    note_ids = []
    while len(note_ids) < 624:
        create_note()
        new_ids = get_note_ids()
        note_ids.extend([id for id in new_ids if id not in note_ids])
        print(f"Collected {len(note_ids)} note IDs")

    print("Collected 624 note IDs. Now predicting RNG...")

    rc = randcrack.RandCrack()
    for note_id in note_ids[:624]:  # Use only the first 624 IDs
        rc.submit(note_id)

    predicted_k = rc.predict_getrandbits(256)
    print(f"Predicted k: {predicted_k}")

    # TODO: Use predicted_k to forge admin JWT
    # TODO: Access dashboard with forged JWT
    admin_jwt = create_admin_jwt(predicted_k)
    print("Forged Admin JWT: ", admin_jwt)

    SESSION.cookies.set('pubkey', 'public_key_x,public_key_y')

    # Access the dashboard
    response = SESSION.get(f"{BASE_URL}/dashboard")
    
    if "Welcome, Admin!" in response.text:
        print("Successfully accessed admin dashboard!")
        # Extract the flag
        soup = BeautifulSoup(response.text, 'html.parser')
        flag = soup.find('pre', class_='secret').text.strip()
        print(f"Flag: {flag}")
    else:
        print("Failed to access admin dashboard")
        print(response.text)

    
if __name__ == "__main__":
    main()

```

Notes about the draft:

- As written, it references `ecc.x` but never imports `ecc` from the challenge code. In a real exploit you either:
  - don’t need the server private key at all (if you self-sign and provide your own public key), or
  - you must derive the server private key (much harder, and typically not intended here).
- `randcrack` works on MT outputs, but the note IDs are raw MT state words, not tempered outputs. You can still reconstruct a compatible state, but you may need to adapt how you feed data into your predictor.

---

## Open items / TODO (to complete this writeup)

- Confirm where `pubkey` is supposed to originate (templates, headers, or JS). If it is never provided by the server, then the key-substitution issue (client-chosen key) is the real authentication bypass.
- If the intended path is MT -> predict ECDSA nonce, document precisely how to map recovered MT state to the bytes consumed by `random.choices` (Python’s internal `_randbelow` calls and bit consumption matter).
- Provide a final working exploit that:
  - produces a token that passes `ecc.verify` exactly,
  - sets `pubkey` correctly,
  - sets payload username to `HTBAdmin1337_ZUSD3uQG4I`,
  - and extracts `/dashboard` secret.
