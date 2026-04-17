---
title: "Magical Oracle - Official Writeup"
summary: "Writeup for the crypto challenge 'Magical Oracle' I designed and created for L3akCTF25"
tags: ["Crypto", "CTF", "HNP", "Cryptanalysis"]
published: true
date: 2024-12-25T10:30:00Z
slug: magical-oracle
---

- **Author**: [supasuge](https://github.com/supasuge) | [supasuge.com](https://www.supasuge.com)
- **Category**: Crypto
- **Difficulty**: Medium

> _“What is magic but mathematics that **sleeps**?  
> Wake it up and it becomes cryptanalysis.”_

This repository contains a mini CTF-style challenge (`src/chal.py`) and two solvers (`solution/solve.py`, `solution/solve2.py`). The goal is to recover the secret number $\alpha$ that the **Magical Oracle** multiplies into every query and, with it, decrypt the flag.

Below is a compact but self-contained explanation of the attack in readable Markdown/LaTeX. If you prefer the tl;dr, jump to **Usage**.

---

## 1. Challenge in a nutshell

1. A 256-bit prime $p$ is chosen.  
2. A random secret $\alpha \in \mathbb{Z}_p$ is fixed.  
3. For each user query the service:
   - picks $t \xleftarrow{\$}\mathbb{Z}_p^*$,
   - returns one misleading number  
     $$
       z = \mathrm{MSB\_Oracle}(\alpha \,t \bmod p),
     $$
   - allows at most  
     $$
       d = 2\lceil\sqrt{n}\rceil + 3
     $$
     queries (here $d=35$).  
4. The flag is encrypted with
   $$
     \text{key} = \mathrm{SHA256}(\,\alpha\,)
   $$
   using AES-CBC and shown to the attacker.

The MSB oracle does **not** leak the exact most-significant bits; instead it returns a value *close* to the real product. Internally it draws many random candidates until

$$
  |x - z| < \frac{p}{2^{k+1}}, 
  \quad
  k = \lfloor \sqrt{n}\rfloor + n + 1.
$$

Because $k\approx26$ is large, the error is *tiny* relative to $p$, yielding a Hidden Number Problem (HNP).

---

## 2. Modelling as HNP

Each query gives an unknown signed error $e_i$ with

$$
  z_i \equiv \alpha\,t_i - e_i \pmod p,
  \quad
  |e_i| < \frac{p}{2^{k+1}}.
$$

Choosing integer representatives in $(-p/2,p/2)$,

$$
  \alpha\,t_i - z_i = e_i \quad(\text{as integers}).
$$

So we have $d$ linear equations

$$
\begin{cases}
  t_1\,\alpha - z_1 = e_1,\\
  \;\;\;\vdots\\
  t_d\,\alpha - z_d = e_d,
\end{cases}
$$

with small $e_i$.  We build the $(d+1)\times(d+1)$ lattice basis

$$
B = 
\begin{pmatrix}
  p & 0 & \cdots & 0 & 0\\
  0 & p & \cdots & 0 & 0\\
  \vdots& &\ddots& &\vdots\\
  0 & 0 & \cdots & p & 0\\
  t_1 & t_2 & \cdots & t_d & p
\end{pmatrix},
$$

and set the target vector

$$
\mathbf y = (z_1,\;z_2,\;\dots,\;z_d,\;0).
$$

Since $\mathbf y$ differs from a true lattice point by the error vector, solving the approximate **Closest Vector Problem** (CVP) against $\mathcal L=\langle B\rangle$ recovers $\alpha$ in the last coordinate.

---

## 3. Solving CVP quickly

1. **LLL-reduce** the basis.  
2. **Babai nearest-plane**: project the target onto each Gram–Schmidt vector in reverse, round, subtract.  
3. Read off $\alpha$ from the last coordinate (then reduce $\bmod p$).

Since $36\times36$ LLL+Babai on integers is sub-millisecond, the whole attack is lightning-fast.

---

## 4. Implementation highlights

| File                  | Purpose                                  |
| --------------------- | ---------------------------------------- |
| `src/chal.py`         | the vulnerable oracle & flag encryptor   |
| `solution/solve.py`   | original Sage-based solver               |
| `solution/solve2.py`  | annotated & slightly cleaner variant     |

### 🚀 Speed tricks

- **Pipelined queries**: send all `1\n` requests back-to-back to amortize RTT.  
- **Integer lattice**: multiply the fractional row by $p$ so LLL works entirely in $\mathbb{Z}$.  
- **Optional**: swap in `fpylll` for a 5–10× speed-up.

---

## 5. Usage

```bash
# Prereqs (Debian/Ubuntu):
apt-get update && apt-get install -y sage python3-venv
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt   # Crypto, pwntools, sage-conf, etc.

# Local test — launches challenge and solver
python3 solution/solve2.py

# Remote
python3 solution/solve2.py chall.host 1338
````

**Expected output** (trimmed):

```
[+] Parameters: p=9…5903, n=256, k=26, d=35
[+] Recovered alpha = 4927…

=== FLAG PLAINTEXT ===
```

*Total runtime ≈ 3.6 s (90% spent in the oracle’s artificial 0.1 s delays).*

---

## 6. References

* Adi Shamir, **How to share a secret**, *Communications of the ACM* 1979.
* Oded Regev, lecture notes on lattices & Babai’s nearest-plane (NYU 2004).
* Boneh & Venkatesan, **Breaking RSA given a small fraction of the private key bits**, CRYPTO ’98.
Here’s a cleaned-up `README.md` that should render nicely on GitHub:


# 🧙‍♂️ Magical Oracle — Write-up

> _“What is magic but mathematics that **sleeps**?  
> Wake it up and it becomes cryptanalysis.”_

This repository contains a mini CTF-style challenge (`src/chal.py`) and two solvers (`solution/solve.py`, `solution/solve2.py`). The goal is to recover the secret number $\alpha$ that the **Magical Oracle** multiplies into every query and, with it, decrypt the flag.

Below is a compact but self-contained explanation of the attack in readable Markdown/LaTeX. If you prefer the tl;dr, jump to **Usage**.

---

## 1. Challenge in a nutshell

1. A 256-bit prime $p$ is chosen.  
2. A random secret $\alpha \in \mathbb{Z}_p$ is fixed.  
3. For each user query the service:
   - picks $t \xleftarrow{\$}\mathbb{Z}_p^*$,
   - returns one misleading number  
     $$
       z = \mathrm{MSB\_Oracle}(\alpha \,t \bmod p),
     $$
   - allows at most  
     $$
       d = 2\lceil\sqrt{n}\rceil + 3
     $$
     queries (here $d=35$).  
4. The flag is encrypted with
   $$
     \text{key} = \mathrm{SHA256}(\,\alpha\,)
   $$
   using AES-CBC and shown to the attacker.

The MSB oracle does **not** leak the exact most-significant bits; instead it returns a value *close* to the real product. Internally it draws many random candidates until

$$
  |x - z| < \frac{p}{2^{k+1}}, 
  \quad
  k = \lfloor \sqrt{n}\rfloor + n + 1.
$$

Because $k\approx26$ is large, the error is *tiny* relative to $p$, yielding a Hidden Number Problem (HNP).

---

## 2. Modelling as HNP

Each query gives an unknown signed error $e_i$ with

$$
  z_i \equiv \alpha\,t_i - e_i \pmod p,
  \quad
  |e_i| < \frac{p}{2^{k+1}}.
$$

Choosing integer representatives in $(-p/2,p/2)$,

$$
  \alpha\,t_i - z_i = e_i \quad(\text{as integers}).
$$

So we have $d$ linear equations

$$
\begin{cases}
  t_1\,\alpha - z_1 = e_1,\\
  \;\;\;\vdots\\
  t_d\,\alpha - z_d = e_d,
\end{cases}
$$

with small $e_i$.  We build the $(d+1)\times(d+1)$ lattice basis

$$
B = 
\begin{pmatrix}
  p & 0 & \cdots & 0 & 0\\
  0 & p & \cdots & 0 & 0\\
  \vdots& &\ddots& &\vdots\\
  0 & 0 & \cdots & p & 0\\
  t_1 & t_2 & \cdots & t_d & p
\end{pmatrix},
$$

and set the target vector

$$
\mathbf y = (z_1,\;z_2,\;\dots,\;z_d,\;0).
$$

Since $\mathbf y$ differs from a true lattice point by the error vector, solving the approximate **Closest Vector Problem** (CVP) against $\mathcal L=\langle B\rangle$ recovers $\alpha$ in the last coordinate.

---

## 3. Solving CVP quickly

1. **LLL-reduce** the basis.  
2. **Babai nearest-plane**: project the target onto each Gram–Schmidt vector in reverse, round, subtract.  
3. Read off $\alpha$ from the last coordinate (then reduce $\bmod p$).

Since $36\times36$ LLL+Babai on integers is sub-millisecond, the whole attack is lightning-fast.

---

## 4. Implementation highlights

| File                 | Purpose                                |
| -------------------- | -------------------------------------- |
| `src/chal.py`        | the vulnerable oracle & flag encryptor |
| `solution/solve.py`  | original Sage-based solver             |
| `solution/solve2.py` | annotated & slightly cleaner variant   |

### Speed tricks

- **Pipelined queries**: send all `1\n` requests back-to-back to amortize RTT.  
- **Integer lattice**: multiply the fractional row by $p$ so LLL works entirely in $\mathbb{Z}$.  
- **Optional**: swap in `fpylll` for a 5–10× speed-up.

---

## 5. Usage

```bash
# Prereqs (Debian/Ubuntu):
apt-get update && apt-get install -y sage python3-venv
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt   # Crypto, pwntools, sage-conf, etc.
# Local test — launches challenge and solver
python3 solution/solve2.py
# Remote
python3 solution/solve2.py chall.host 1338
````

**Expected output** (trimmed):

```
[+] Parameters: p=9…5903, n=256, k=26, d=35
[+] Recovered alpha = 4927…
=== FLAG PLAINTEXT ===
flag{.....}
```

_Total runtime ≈ 3.6 s (90% spent in the oracle’s artificial 0.1 s delays)._

---

## 6. References

- Adi Shamir, **How to share a secret**, _Communications of the ACM_ 1979.
- Oded Regev, lecture notes on lattices & Babai’s nearest-plane (NYU 2004).    
- Boneh & Venkatesan, **Breaking RSA given a small fraction of the private key bits**, CRYPTO ’98.
- https://github.com/jvdsn/crypto-attacks
