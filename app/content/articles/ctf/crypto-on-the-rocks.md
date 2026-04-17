---
title: Crypto On the Rocks (Crypto, L3akCTF24')
summary: "Intended solution writeup for 'Crypto On the Rocks' a challenge I made for L3akCTF2024 based off the P-521 curve and a MSB biased nonce vulnerability inspired directly by CVE-2024-31497."
tags:
published: true
date: '2026-05-26'
slug: crypto-on-the-rocks-l3ak-2024
---
- **Author**: [supasuge](https://github.com/supasuge)
- **Category**: Crypto  
- **Difficulty**: Hard  

[Solution Writeup](https://github.com/supasuge/CTF-Challenges/blob/main/crypto-on-the-rocks/solution/README.md)

---

## Description

This challenge was directly inspired by CVE-2024-31497, where PuTTY’s implementation of ECDSA over the NIST P-521 curve produced biased nonces.

Specifically, nonces were generated via:

$$
k = \text{SHA512}(\text{random}) \bmod n
$$

Since SHA-512 outputs 512 bits and the curve order $n$ is 521 bits, every nonce $k$ had its top $9$ bits set to zero.

This seemingly small bias is catastrophic.

---

## Introduction

This challenge reduces to breaking ECDSA using a **lattice-based Hidden Number Problem (HNP)** attack.

We exploit:

- Partial leakage of nonce bits
- Multiple signatures over known messages
- Structured algebraic relations

End goal:

1. Recover private key $d$
2. Derive AES key:

$$
\text{AES\_KEY} = \text{SHA256}(d)
$$

3. Decrypt the flag

---

## ECDSA Refresher (P-521 Context)

We are working over a Weierstrass curve:

$$
y^2 \equiv x^3 + ax + b \pmod{p}
$$

Public parameters:

- Generator point $G$
- Order $n$
- Private key $d$
- Public key:
  $$
  Q = dG
  $$

Signature generation:

$$
r_i = (k_i G)_x \bmod n
$$

$$
s_i = k_i^{-1}(e_i + r_i d) \bmod n
$$

---

## The Vulnerability

Core issue:

```python
def get_k() -> int:
return int.from_bytes(hashlib.sha512(os.urandom(512//8)).digest(), byteorder='big') % n
```

This produces:

$$
k_i < 2^{512}
$$

But:

$$
n \approx 2^{521}
$$

So:

$$
k_i = 0\underbrace{00\cdots0}_{9\ \text{bits}} || \text{unknown bits}
$$

We know the **9 MSBs of every nonce**.

---

## Turning ECDSA into an HNP

Start from:

$$
s_i = k_i^{-1}(e_i + r_i d) \mod n
$$

Rearrange:

$$
k_i = s_i^{-1}(e_i + r_i d) \mod n
$$

Multiply both sides:

$$
k_i - s_i^{-1} r_i d - s_i^{-1} e_i \equiv 0 \mod n
$$

Define:

- $a_i = s_i^{-1} r_i \mod n$
- $b_i = s_i^{-1} e_i \mod n$

Then:

$$
k_i \equiv a_i d + b_i \mod n
$$

---

## Injecting the Bias

We know:

$$
k_i = k_i' \quad \text{with} \quad k_i < 2^{512}
$$

So:

$$
k_i = x_i
$$

with:

$$
|x_i| < 2^{512}
$$

This is now a **Hidden Number Problem**:

$$
x_i = a_i d + b_i \mod n
$$

with small $x_i$.

---

## Lattice Construction

We build a lattice to recover $d$.

Let:

- $m$ = number of signatures
- $X = 2^{512}$ (bound on $k_i$)

We construct matrix $B$:

$$
B =
\begin{bmatrix}
n & 0 & 0 & \cdots & 0 & 0 \\
0 & n & 0 & \cdots & 0 & 0 \\
\vdots & & \ddots & & & \vdots \\
0 & 0 & 0 & \cdots & n & 0 \\
a_1 & a_2 & a_3 & \cdots & a_m & \frac{X}{n} \\
b_1 - \frac{X}{2} & b_2 - \frac{X}{2} & \cdots & b_m - \frac{X}{2} & X
\end{bmatrix}
$$

Intuition:

- First rows enforce modulo $n$
- Last rows encode HNP relation
- Scaling ensures “smallness” is preserved

---

## Why LLL Works

We are looking for a vector:

$$
(x_1, x_2, \dots, x_m, d, 1)
$$

where:

- $x_i$ are small
- $d$ is consistent across equations

LLL finds a **short vector**, which corresponds to:

- Correct $d$
- Correct nonce residues

---

## Attack Flow

1. Collect signatures:

$$
(r_i, s_i)
$$

2. Compute:

$$
a_i = s_i^{-1} r_i \mod n
$$

$$
b_i = s_i^{-1} e_i \mod n
$$

3. Model:

$$
k_i = a_i d + b_i \mod n
$$

4. Use partial nonce knowledge:

$$
k_i = 0\cdots0???????
$$

5. Construct lattice

6. Run LLL

7. Extract candidate $d$

8. Verify:

$$
Q \stackrel{?}{=} dG
$$

---

## Practical Implementation Notes

From the solver:

- Partial nonces encoded as:

```

ks = PartialInteger.from_bits_be("000000000" + ("?" * 512))

```

- Attack invoked via:

```

dsa_known_msb(n, h_i, r_i, s_i, k_i)

```

- Lattice solver adapted from:
  - HNP attack implementations :contentReference[oaicite:0]{index=0}

---

## Final Step: Decryption

Once $d$ is recovered:

$$
\text{AES\_KEY} = \text{SHA256}(d)
$$

Then:

$$
\text{flag} = \text{AES-CBC}^{-1}(\text{ciphertext})
$$

---

## Key Insight

This challenge is not about elliptic curves.

It is about **entropy loss**.

If your nonce leaks even a few bits:

- Each signature leaks a linear constraint
- Enough signatures → full key recovery

---

## Takeaways

- ECDSA is only as secure as its nonce generation
- Biased randomness ⇒ lattice attacks
- MSB leakage is just as dangerous as LSB leakage
- SHA-512 → mod $n$ is NOT safe when $n > 2^{512}$

---

## Closing

This is a textbook example of:

$$
\text{Human Error (mistaking 521 for 512)} \Rightarrow \text{Full key compromise}
$$

---