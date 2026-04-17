---
title: "N00bzCTF 2023 — Broadcast (Crypto) writeup"
date: 2026-02-07
description: "Repeatedly encrypting the same plaintext under different RSA moduli with small exponent $e=17$ leaks the message via CRT and an integer 17th root."
ctf: "N00bzCTF 2023"
category: "Cryptography"
difficulty: "Easy"
author: "supasuge"
tags: ["ctf", "crypto", "rsa", "hastad", "broadcast-attack", "crt"]
---

# N00bzCTF 2023 — Writeup

This is a simple RSA crypto challenge that becomes instantly solvable because the same plaintext (the flag) is encrypted many times using a **small public exponent**.

---

## Source

```python
from Crypto.Util.number import *
import time

flag = bytes_to_long(b'n00bz{***********************}')
e = 17

p = getPrime(1024)
q = getPrime(1024)
n = p*q

ct = pow(flag,e,n)
time.sleep(0.5)

print(f'{e = }')
print(f'{ct = }')
print(f'{n = }')
```

What matters:

* Public exponent: $e = 17$
* Each run generates fresh primes $p,q$ → fresh modulus $n = pq$
* Same message $m=\text{flag}$ is encrypted each time:

$$
c_i \equiv m^{17} \pmod{n_i}
$$


## What’s broken (the vulnerability)

This is exactly the setup for **Håstad’s Broadcast Attack**:

* same plaintext $m$
* same small exponent $e$
* different moduli $n_i$ (typically pairwise coprime)
* enough samples: at least $e$ ciphertexts

If you collect $e$ ciphertext/modulus pairs, you can reconstruct $m^e$ as a normal integer (not just modulo something), then take the exact $e$-th root to recover $m$.



## Attack explained (CRT -> integer root)

### Step 1 — Collect $e$ encryptions

Run the challenge 17 times to obtain:

$$
(c_1,n_1), (c_2,n_2), \dots, (c_{17},n_{17})
$$

with:

$$
c_i \equiv m^{17} \pmod{n_i}
$$

## Step 2 — CRT recombination

Because the $n_i$ are (with overwhelming probability) pairwise coprime, CRT gives a unique value $M$ modulo:

$$
N=\prod_{i=1}^{17} n_i
$$

such that:

$$
M \equiv c_i \pmod{n_i} \quad \forall i
$$

Since each $c_i \equiv m^{17} \pmod{n_i}$, CRT implies:

$$
M \equiv m^{17} \pmod{N}
$$

## Step 3 — The crucial inequality

If the message is small enough that:

$$
m^{17} < N
$$

then the congruence collapses into equality:

$$
M = m^{17}
$$

So you can recover:

$$
m = \sqrt[17]{M}
$$

as an **exact integer root**.

That’s the whole attack.

---

### Solution 

This is your original approach, cleaned:

* runs the challenge 17 times
* stores $(c_i, n_i)$
* CRT combines them
* takes exact 17th root
* converts to bytes


Note that in the real solution script, it was against a remote connection however I just switched it to the original `chall.py` for demonstration purpose.

```python
#!/usr/bin/env python3
from pwn import process
from sage.all import crt
from Crypto.Util.number import long_to_bytes
from gmpy2 import iroot

E = 17
cts = []
mods = []

for _ in range(E):
    io = process(["python3", "../src/chall.py"])

    io.recvuntil(b"ct = ")
    c = int(io.recvline().strip())

    io.recvuntil(b"n = ")
    n = int(io.recvline().strip())

    cts.append(c)
    mods.append(n)
    io.close()

# CRT: find M such that M ≡ c_i (mod n_i) for all i
M = int(crt(cts, mods))

# exact integer 17th root
m, exact = iroot(M, E)
assert exact, "Root not exact: not enough samples, padding present, or m^e >= product(n_i)."

flag = long_to_bytes(int(m))
print(flag.decode(errors="replace"))
```

---

#### Notes / sanity checks

* With random 1024-bit primes, different moduli are almost always coprime.
* The `time.sleep(0.5)` is just fluff; it doesn’t help security.
* This fails in real RSA because padding (e.g., OAEP) ensures the plaintext differs each time, so the “same $m$” requirement breaks.

---

#### Summary

This challenge is a textbook demonstration of why **textbook RSA** is not used with small public exponents + repeated plaintexts across different moduli... This is what enables Hastads broadcast attack

---
