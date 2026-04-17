---
title: "Sun Zi's Perfect Math Class"
summary: "Brief writeup and explaination from an old CTF involving the chinese remainder theorem word problem + a RSA problem showcasing similar priniples."
tags: ["ctf", "crypto"]
published: true
date: '2025-12-31'
slug: sun-zis-perf-math-class
---

![alt text](sunzi.png)

# Chinese Remainder Theorem (CRT)

## What CRT says (informal)

If $n_1, n_2, \dots, n_k$ are **pairwise coprime** (i.e., $\gcd(n_i,n_j)=1$ for $i\neq j$), then the system:

$$
\begin{cases}
x \equiv a_1 \pmod{n_1}\\
x \equiv a_2 \pmod{n_2}\\
\vdots\\
x \equiv a_k \pmod{n_k}
\end{cases}
$$

has a **unique solution modulo**:

$$
N = \prod_{i=1}^k n_i
$$

Meaning: there is exactly one $x$ in $[0, N)$ satisfying all congruences, and all solutions are $x + tN$.

## Why it works (intuition)

Each congruence is a “constraint” on $x$ when viewed through a modular lens (like a clock). When moduli are coprime, their cycles only align every $N$ steps, so the combined constraint nails down a unique state modulo $N$.

---

## Manual CRT recombination (how to actually build the solution)

This is the CRT construction you used implicitly in the RSA solve.

Given residues $a_i$ and moduli $n_i$:
1. Compute the product:
   $$
   N = \prod_i n_i
   $$

2. For each equation, compute:
   - $N_i = \frac{N}{n_i}$
   - $y_i = N_i^{-1} \bmod n_i$ (the modular inverse)

3. Combine:
   $$
   x \equiv \sum_{i=1}^k a_i \cdot N_i \cdot y_i \pmod{N}
   $$

### Why this construction works

- For $j \neq i$, $N_i$ contains a factor $n_j$, so $N_i \equiv 0 \pmod{n_j}$, meaning the $i$-th term vanishes under modulus $n_j$.
- Under modulus $n_i$, we force $N_i \cdot y_i \equiv 1 \pmod{n_i}$ by choosing $y_i$ as the inverse.
- Therefore, the $i$-th term becomes $a_i$ modulo $n_i$, and $0$ modulo all other moduli.

---

### Sun Zi's Perfect Math solution

To determine the exact number of soldiers Han Xin had remaining, we need to solve the following system of congruences:

$$
\begin{cases} 
x \equiv 2 \pmod{3} \\
x \equiv 4 \pmod{5} \\
x \equiv 5 \pmod{7}
\end{cases}
$$

Using the Chinese remainder theorem, we find the solution module 3 * 5 * 7 = 105
Compute:

- $N = 3\cdot 5\cdot 7 = 105$
- $N_1 = 105/3 = 35$
- $N_2 = 105/5 = 21$
- $N_3 = 105/7 = 15$

Now compute inverses:

- $35 \bmod 3 = 2$, and $2^{-1}\bmod 3 = 2$, so $y_1=2$
- $21 \bmod 5 = 1$, and $1^{-1}\bmod 5 = 1$, so $y_2=1$
- $15 \bmod 7 = 1$, and $1^{-1}\bmod 7 = 1$, so $y_3=1$

Combine:

$$
x \equiv 2\cdot 35\cdot 2 \;+\; 4\cdot 21\cdot 1 \;+\; 5\cdot 15\cdot 1 \pmod{105}
$$

Compute the sum:

- $2\cdot 35\cdot 2 = 140$
- $4\cdot 21\cdot 1 = 84$
- $5\cdot 15\cdot 1 = 75$

Total $= 140+84+75 = 299$

Reduce mod $105$:

$$
299 \equiv 89 \pmod{105}
$$

So $x \equiv 89 \pmod{105}$, matching your derivation.

Given range $1000 \le x \le 1100$:

$$
x = 89 + 105k
$$

Pick $k=9$:

$$
x = 89 + 105\cdot 9 = 1034
$$

Answer: $\boxed{1034}$

---

In `python`:
```python
from sympy import mod_inverse

# Given congruences:
a1, n1 = 2, 3
a2, n2 = 4, 5
a3, n3 = 5, 7

# Find the product of all moduli
N = n1 * n2 * n3

# Calculate individual components
N1 = N // n1
N2 = N // n2
N3 = N // n3

# Compute the modular inverses
inv1 = mod_inverse(N1, n1)
inv2 = mod_inverse(N2, n2)
inv3 = mod_inverse(N3, n3)

# Calculate the solution using CRT
x = (a1 * N1 * inv1 + a2 * N2 * inv2 + a3 * N3 * inv3) % N

print(f"The solution to the system of congruences is x ≡ {x} (mod {N})")

# Given the range [1000, 1100], find the appropriate value for k
k = (1000 - x + N - 1) // N  # Use floor division
solution = x + k * N

# Check if the solution is within the range
if 1000 <= solution <= 1100:
    print(f"The number of soldiers Han Xin had remaining is {solution}")
else:
    print("No solution found within the specified range")
```

---
## RSA broadcast attack (Håstad) — where CRT becomes lethal - Pt.2 of challenge
Next up, the site give's us $c1, c2, c3$ as well as the corresponding $n1, n2, n3$ from the RSA equation. The goal to get the flag is to use the Chinese Remainder theorem and hadcast's broadcast attack to get the decrypted flag.

RSA encryption is:

$$
c \equiv m^e \pmod{n}
$$

Here $e=3$. The challenge gives three ciphertexts:

$$
c_1 \equiv m^3 \pmod{n_1},\quad
c_2 \equiv m^3 \pmod{n_2},\quad
c_3 \equiv m^3 \pmod{n_3}
$$

Since $n_1,n_2,n_3$ are (assumed) pairwise coprime (typical for unrelated RSA keys), CRT lets us build a single value $X$ such that:

$$
X \equiv c_i \pmod{n_i} \quad \text{for each } i
$$

But because each $c_i$ is $m^3 \bmod n_i$, that implies:

$$
X \equiv m^3 \pmod{N}
\quad \text{where} \quad
N = n_1n_2n_3
$$

## The critical condition

If the plaintext is small enough that:
$$
m^3 < N
$$
then the congruence collapses to an equality:
$$
X = m^3
$$
So we can take the integer cube root:
$$
m = \sqrt[3]{X}
$$
That’s the broadcast attack: **same message**, **small exponent**, **multiple recipients**, **no padding**.

> Proper padding (e.g., OAEP) prevents this because each recipient encrypts a different padded value, so you no longer have the same $m^e$ across moduli.

---

# Manual CRT recombination for the RSA instance

Given the three pairs $(c_i, n_i)$:

1. Compute:
   $$
   N = n_1n_2n_3
   $$

2. For each $i$:
   $$
   N_i = \frac{N}{n_i},\quad
   y_i = N_i^{-1} \bmod n_i
   $$

3. Combine:
   $$
   X \equiv c_1N_1y_1 + c_2N_2y_2 + c_3N_3y_3 \pmod{N}
   $$

Then compute $m$ as the exact integer cube root of $X$.

Contents from `output.txt`:

```python
e = 3

c_1 = 105001824161664003599422656864176455171381720653815905925856548632486703162518989165039084097502312226864233302621924809266126953771761669365659646250634187967109683742983039295269237675751525196938138071285014551966913785883051544245059293702943821571213612968127810604163575545004589035344590577094378024637

c_2 = 31631442837619174301627703920800905351561747632091670091370206898569727230073839052473051336225502632628636256671728802750596833679629890303700500900722642779064628589492559614751281751964622696427520120657753178654351971238020964729065716984136077048928869596095134253387969208375978930557763221971977878737

c_3 = 64864977037231624991423831965394304787965838591735479931470076118956460041888044329021534008265748308238833071879576193558419510910272917201870797698253331425756509041685848066195410586013190421426307862029999566951239891512032198024716311786896333047799598891440799810584167402219122283692655717691362258659

n_1 = 147896270072551360195753454363282299426062485174745759351211846489928910241753224819735285744845837638083944350358908785909584262132415921461693027899236186075383010852224067091477810924118719861660629389172820727449033189259975221664580227157731435894163917841980802021068840549853299166437257181072372761693

n_2 = 95979365485314068430194308015982074476106529222534317931594712046922760584774363858267995698339417335986543347292707495833182921439398983540425004105990583813113065124836795470760324876649225576921655233346630422669551713602423987793822459296761403456611062240111812805323779302474406733327110287422659815403

n_3 = 95649308318281674792416471616635514342255502211688462925255401503618542159533496090638947784818456347896833168508179425853277740290242297445486511810651365722908240687732315319340403048931123530435501371881740859335793804194315675972192649001074378934213623075830325229416830786633930007188095897620439987817
```

### Final Python Solution (manual CRT + exact cube root)
```python
#!/usr/bin/env python3
from sympy import mod_inverse, integer_nthroot
from Crypto.Util.number import long_to_bytes

e = 3

c_1 = 105001824161664003599422656864176455171381720653815905925856548632486703162518989165039084097502312226864233302621924809266126953771761669365659646250634187967109683742983039295269237675751525196938138071285014551966913785883051544245059293702943821571213612968127810604163575545004589035344590577094378024637
c_2 = 31631442837619174301627703920800905351561747632091670091370206898569727230073839052473051336225502632628636256671728802750596833679629890303700500900722642779064628589492559614751281751964622696427520120657753178654351971238020964729065716984136077048928869596095134253387969208375978930557763221971977878737
c_3 = 64864977037231624991423831965394304787965838591735479931470076118956460041888044329021534008265748308238833071879576193558419510910272917201870797698253331425756509041685848066195410586013190421426307862029999566951239891512032198024716311786896333047799598891440799810584167402219122283692655717691362258659

n_1 = 147896270072551360195753454363282299426062485174745759351211846489928910241753224819735285744845837638083944350358908785909584262132415921461693027899236186075383010852224067091477810924118719861660629389172820727449033189259975221664580227157731435894163917841980802021068840549853299166437257181072372761693
n_2 = 95979365485314068430194308015982074476106529222534317931594712046922760584774363858267995698339417335986543347292707495833182921439398983540425004105990583813113065124836795470760324876649225576921655233346630422669551713602423987793822459296761403456611062240111812805323779302474406733327110287422659815403
n_3 = 95649308318281674792416471616635514342255502211688462925255401503618542159533496090638947784818456347896833168508179425853277740290242297445486511810651365722908240687732315319340403048931123530435501371881740859335793804194315675972192649001074378934213623075830325229416830786633930007188095897620439987817

C = [c_1, c_2, c_3]
N = [n_1, n_2, n_3]

def prod(nums):
    out = 1
    for x in nums:
        out *= x
    return out

def crt(residues, moduli):
    """
    Manual CRT recombination:
      X = sum(a_i * N_i * inv(N_i mod n_i)) mod N
    where N = product(n_i), N_i = N/n_i.
    """
    assert len(residues) == len(moduli)
    bigN = prod(moduli)
    total = 0

    for a_i, n_i in zip(residues, moduli):
        N_i = bigN // n_i
        inv = mod_inverse(N_i, n_i)   # N_i^{-1} mod n_i
        total += a_i * N_i * inv

    return total % bigN, bigN

X, bigN = crt(C, N)
m, exact = integer_nthroot(X, 3)
if not exact:
    raise SystemExit("Cube root not exact: broadcast attack conditions not met (padding / not enough samples / m^3 >= N).")
pt = long_to_bytes(int(m))
print(f"Ciphertext: {pt.decode(errors="replace")}\nInteger: {int(m)}")
```

```python
python3 solve.py
Cleartext: DUCTF{btw_y0u_c4n_als0_us3_CRT_f0r_p4rt14l_fr4ct10ns}
Integer:  11564025922867522871782912815123211630478650327759091593792994457296772521676766420142199669845768991886967888274582504750347133
```

Answer:
`DUCTF{btw_y0u_c4n_als0_us3_CRT_f0r_p4rt14l_fr4ct10ns}`

