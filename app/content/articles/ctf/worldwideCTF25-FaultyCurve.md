---
title: "FaultyCurve(Crypto) WorldWideCTF 2025"
date: 2026-02-07
description: "Break an 'ECDLP' by noticing the curve is singular, then map it to $\\mathbb{F}_p^*$ (nodal case) and solve a normal DLP."
ctf: "WorldWideCTF 2025"
category: "Cryptography"
difficulty: "Very Hard"
tags: ["crypto", "ecc", "elliptic-curves", "singular-curve", "isomorphism", "discrete-log", "sage"]
---
# FaultyCurve — Write-up

At first glance this looks like a standard ECDLP setup: you get prime $p$, coefficient $a$, an $x$-coordinate for a “generator” $G$, and an $x$-coordinate for a public key $Q$ where:

$$
Q = \text{flag} \cdot G
$$

Normally, you’re dead in the water.

But the author basically hands you the exploit in a comment: Sage can’t even instantiate the curve. That’s not “Sage being annoying” — that’s Sage refusing to treat a **singular** curve like a real elliptic curve group.

So the real problem is not ECDLP. It’s: **detect singularity, classify it (cuspidal vs nodal), then use the correct group isomorphism to reduce the problem to a normal field DLP**.

---

# 1) Identify the curve is singular (the entire game)

The curve is in short Weierstrass form:

$$
y^2 = x^3 + ax + b \pmod p
$$

A curve is **non-singular** iff its discriminant $\Delta \neq 0$ mod $p$. For short Weierstrass curves:

$$
\Delta = -16(4a^3 + 27b^2)
$$

So singular means:

$$
4a^3 + 27b^2 \equiv 0 \pmod p
$$

We’re given $p$ and $a$, but not $b$. Solve for $b$:

$$
b^2 \equiv -4a^3 \cdot 27^{-1} \pmod p
$$

That yields two candidates: $b = \pm \sqrt{b^2}$.

### Picking the correct $b$
We know $G_x$ is valid, meaning $G$ lies on the curve. So:

$$
G_y^2 \equiv G_x^3 + aG_x + b \pmod p
$$

Pick the $b$ where the RHS becomes a quadratic residue (i.e., has a square root).

---

# 2) Find the singular point $(x_0, 0)$

A singular point on a Weierstrass curve satisfies:

- $y = 0$
- the derivative condition (tangent degeneracy)

For this curve, you can use:

$$
3x_0^2 + a \equiv 0 \pmod p
$$

So:

$$
x_0^2 \equiv -a \cdot 3^{-1} \pmod p
$$

Again two candidates: $x_0 = \pm \sqrt{x_0^2}$.

---

# 3) Cuspidal vs nodal (I wasted time here too)

Singular curves split into two main types:

## Cuspidal (additive)
Group of nonsingular points is isomorphic to $(\mathbb{F}_p, +)$.
Mapping often looks like:

$$
\psi(P)=\frac{x-x_0}{y}
$$

Then:

$$
\psi(Q)=\text{flag}\cdot \psi(G)
$$

So “DLP” becomes field division.

I tried this (iterating sign choices for roots), got nothing. That’s the signal: **wrong singular type**.

## Nodal (multiplicative) 
Group of nonsingular points is isomorphic to $(\mathbb{F}_p^\*, \cdot)$.

Here the map uses tangent slopes at the singular point. Slopes satisfy:

$$
m^2 \equiv 3x_0 \pmod p
$$

So $m=\pm \sqrt{3x_0}$.

Then the isomorphism:

$$
\psi(P) = \frac{y - m(x-x_0)}{y + m(x-x_0)}
$$

And now the relation becomes:

$$
\psi(Q) = \psi(G)^{\text{flag}}
$$

That’s a standard DLP in $\mathbb{F}_p^\*$:

$$
\text{flag} = \log_{\psi(G)}(\psi(Q))
$$

---

# 4) The final gotcha: Sage Integer vs Python int

Sage’s `log()` returns a Sage `Integer`, which does not have `.to_bytes()`.

Fix: cast it.

```python
py_flag = int(flag_candidate)
````

---

# Final Sage solution

Optimizations applied **without changing the logic**:

```python
#!/usr/bin/env sage
from Crypto.Util.number import long_to_bytes

p  = 3059506932006842768669313045979965122802573567548630439761719809964279577239571933
aI = 2448848303492708630919982332575904911263442803797664768836842024937962142592572096
GxI = 3
QxI = 1461547606525901279892022258912247705593987307619875233742411837094451720970084133

Fp = GF(p)
a  = Fp(aI)
Gx = Fp(GxI)
Qx = Fp(QxI)

# -----------------------------
# Fast EC ops in Fp (same logic)
# -----------------------------
def point_add(P, Q, a, F):
    if P is None: return Q
    if Q is None: return P

    x1, y1 = P
    x2, y2 = Q

    if x1 == x2 and (y1 != y2 or y1 == 0):
        return None

    if x1 == x2:
        m = (3 * x1 * x1 + a) / (2 * y1)
    else:
        m = (y2 - y1) / (x2 - x1)

    x3 = m*m - x1 - x2
    y3 = m*(x1 - x3) - y1
    return (x3, y3)

def point_mul(k, P, a, F):
    # Montgomery-ladder style (as in your code)
    R0 = None
    R1 = P
    for bit in bin(int(k))[2:]:
        if bit == '0':
            R1 = point_add(R0, R1, a, F)
            R0 = point_add(R0, R0, a, F)
        else:
            R0 = point_add(R0, R1, a, F)
            R1 = point_add(R1, R1, a, F)
    return R0

def sqrt_or_none(x):
    return x.sqrt() if x.is_square() else None

print("[+] Step 1: assume singularity and recover b via 4a^3 + 27b^2 = 0")

inv27 = Fp(27)^-1
b2 = -4 * a^3 * inv27
b_root = sqrt_or_none(b2)
if b_root is None:
    print("[-] b^2 is not a square; unexpected. Exiting.")
    quit()

b_candidates = [b_root, -b_root]
print("    found b candidates (+/- sqrt(b^2))")

print("[+] Step 2: choose correct b using Gx membership")
b = None
for cand in b_candidates:
    rhs = Gx^3 + a*Gx + cand
    if rhs.is_square():
        b = cand
        break
if b is None:
    print("[-] No b makes Gx land on the curve. Exiting.")
    quit()
print("    selected b =", int(b))

print("[+] Step 3: find singular x0 from 3x0^2 + a = 0")
inv3 = Fp(3)^-1
x0_sq = -a * inv3
x0_root = sqrt_or_none(x0_sq)
if x0_root is None:
    print("[-] x0^2 is not a square. Exiting.")
    quit()
x0_candidates = [x0_root, -x0_root]
print("    found x0 candidates")

print("[+] Step 4: recover Gy, Qy (two signs each)")
Gy_root = sqrt_or_none(Gx^3 + a*Gx + b)
if Gy_root is None:
    print("[-] Gy does not exist; inconsistent. Exiting.")
    quit()
Gy_candidates = [Gy_root, -Gy_root]

Q_rhs = Qx^3 + a*Qx + b
Qy_root = sqrt_or_none(Q_rhs)
if Qy_root is None:
    print("[-] Qx not on curve under chosen b. Exiting.")
    quit()
Qy_candidates = [Qy_root, -Qy_root]

print("[+] Step 5: nodal isomorphism → solve DLP in Fp*")

F = Fp  # alias

# Try all combinations of x0, tangent slope sign, Gy sign, Qy sign
for x0 in x0_candidates:
    m_sq = 3 * x0
    m_root = sqrt_or_none(m_sq)
    if m_root is None:
        continue
    for slope in [m_root, -m_root]:
        for Gy in Gy_candidates:
            for Qy in Qy_candidates:
                denG = Gy + slope * (Gx - x0)
                denQ = Qy + slope * (Qx - x0)
                if denG == 0 or denQ == 0:
                    continue

                numG = Gy - slope * (Gx - x0)
                numQ = Qy - slope * (Qx - x0)

                psiG = numG / denG
                psiQ = numQ / denQ

                # avoid degenerate cases
                if psiG in [0, 1] or psiQ == 0:
                    continue

                try:
                    k = psiQ.log(psiG)  # psiQ = psiG^k
                except (ValueError, ZeroDivisionError):
                    continue

                # Verify by scalar multiplication: does k*G have x == Qx?
                G_point = (Gx, Gy)
                Qcand = point_mul(k, G_point, a, F)

                if Qcand is not None and Qcand[0] == Qx:
                    print("\n[+] Found candidate producing correct Qx.")
                    py_k = int(k)
                    if py_k <= 0:
                        continue

                    flag_bytes = py_k.to_bytes((py_k.bit_length() + 7)//8, "big")
                    try:
                        flag = flag_bytes.decode("ascii")
                    except UnicodeDecodeError:
                        continue

                    if flag.startswith("wwf{"):
                        print("\n>>> FLAG:", flag, "<<<\n")
                        quit()

print("[-] No valid flag found.")
```

---

# Output (as observed)

The correct candidate decodes cleanly to:

`wwf{sup3rs1ngul4r_1s0m0rph15ms!}`

---

# Why this challenge is “Very Hard” (and why it’s still fair)

If you treat it like ECDLP, you’ll burn time doing nothing.

The only viable route is:

1. notice Sage failing is a *signal*
2. derive $b$ from singularity
3. classify the singularity (cuspidal vs nodal)
4. use the correct isomorphism
5. reduce to a regular DLP in the base field

That’s not brute force — it’s recognizing the group is not elliptic anymore.

---

# Takeaways

- If the curve discriminant is $0$, you do **not** have an elliptic curve group.
- Singular curves leak structure:

  - cuspidal $\rightarrow$ additive group $(\mathbb{F}_p, +)$
  - nodal $\rightarrow$ multiplicative group $(\mathbb{F}_p^*, \cdot)$
- Once mapped, “ECDLP” becomes a normal DLP you can solve with `log()`.

---