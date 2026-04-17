---
title: "NiteCTF Crypto Writeup: R Stands Alone"
summary: "NiteCTF24 'R Stands Alone' crypto writeup showing how the RSA modulus with three primes falls by factoring $r = a^3 + 16b^3$ in a cubic number field, recovering $p$ and $q$ to decrypt the flag."
tags: ["nitectf24", "ctf", "rsa", "cryptography", "sagemath", "factorization"]
published: true
date: '2025-12-31'
slug: nitectf-crypto-r-stands-alone
---

This was the only challenge I solved during this event, mostly due to family and other obligations. I went down a few rabbit holes before realizing how simple the core idea was. Lesson learned: don't overcomplicate things—this one falls cleanly to an algebraic number theory trick.

- Solution/Writeup Author: https://github.com/supasuge
- Date: 12/15/2024

## Table of Contents
- [Table of Contents](#table-of-contents)
- [Challenge Source Code (Preliminary)](#challenge-source-code-preliminary)
- [Challenge Overview](#challenge-overview)
- [Vulnerability Background](#vulnerability-background)
- [Step 2: Algebraic Derivation of $r$](#step-2-algebraic-derivation-of-r)
- [Code Analysis](#code-analysis)
- [Vulnerability](#vulnerability)
- [The Norm Map](#the-norm-map)
  - [Why this helps with factorization](#why-this-helps-with-factorization)
  - [Recovery of the private key](#recovery-of-the-private-key)
- [Solution Steps](#solution-steps)
- [SageMath Solution Code](#sagemath-solution-code)
- [Final Notes](#final-notes)

## Challenge Source Code (Preliminary)
```python
from Crypto.Util.number import *

def gen_keys():
    while True:
        a = getPrime(128)
        b = getPrime(128)
        A = a+b
        B = a-b 
        
        p = ((17*A*A*A) - (15*B*B*B) - (45*A*A*B) + (51*A*B*B)) // 8

        if isPrime(p) :
            return a, b, p
    
p, q, r = gen_keys()
e = 65537
n = p*q*r

flag = b"nite{REDACTED}"

ct = pow(bytes_to_long(flag), e, n)
print(f"{r =}")
print(f"{ct =}")

"""OUTPUT :
r =17089720847522532186100904495372954796086523439343401190123572243129905753474678094845069878902485935983903151003792259885100719816542256646921114782358850654669422154056281086124314106159053995410679203972646861293990837092569959353563829625357193304859110289832087486433404114502776367901058316568043039359702726129176232071380909102959487599545443427656477659826199871583221432635475944633756787715120625352578949312795012083097635951710463898749012187679742033
ct =583923134770560329725969597854974954817875793223201855918544947864454662723867635785399659016709076642873878052382188776671557362982072671970362761186980877612369359390225243415378728776179883524295537607691571827283702387054497203051018081864728864347679606523298343320899830775463739426749812898275755128789910670953110189932506526059469355433776101712047677552367319451519452937737920833262802366767252338882535122186363375773646527797807010023406069837153015954208184298026280412545487298238972141277859462877659870292921806358086551087265080944696281740241711972141761164084554737925380675988550525333416462830465453346649622004827486255797343201397171878952840759670675361040051881542149839523371605515944524102331865520667005772313885253113470374005334182380501000
"""
```

## Challenge Overview

This challenge involves RSA with a twist: the modulus $n = p \times q \times r$ contains three primes. The value r is generated with a special algebraic construction, and the task is to exploit that structure to recover p and q, then decrypt the flag.

## Vulnerability Background

Step 1: Understanding the Prime Generation
The server generates primes using the formula below (expanded in the derivation section):

```python
p = ((17*A**3) - (15*B**3) - (45*A**2*B) + (51*A*B**2)) // 8
```

Where $A = a + b$ and $B = a − b$ for $128\text{-bit}$ primes $a$ and $b$.

Key simplification:
- This expression reduces to r = a^3 + 16b^3 (proof below). This structure is what makes the attack straightforward.

## Step 2: Algebraic Derivation of $r$

Let's expand the given formula with $A = a + b$ and $B = a − b$:

$$17A^3 = 17(a + b)^3 = 17(a^3 + 3a^2b + 3ab^2 + b^3)$$

$$-15B^3 = -15(a - b)^3 = -15(a^3 - 3a^2b + 3ab^2 - b^3)$$

$$-45A^2B = -45(a + b)^2(a - b) = -45(a^3 + a^2b - ab^2 - b^3)$$

$$51AB^2 = 51(a + b)(a - b)^2 = 51(a^3 - a^2b - ab^2 + b^3)$$

Adding these terms and dividing by 8:

$$\frac{17A^3 - 15B^3 - 45A^2B + 51AB^2}{8} = \frac{8a^3 + 128b^3}{8} = a^3 + 16b^3$$

Thus, r = a^3 + 16b^3.

## Code Analysis

```python
from Crypto.Util.number import *
def gen_keys():
    while True:
        a = getPrime(128)
        b = getPrime(128)
        A = a+b
        B = a-b 
        
        p = ((17*A*A*A) - (15*B*B*B) - (45*A*A*B) + (51*A*B*B)) // 8

        if isPrime(p):
            return a, b, p
```

- $a$: Random 128-bit prime number
- $b$: Random 128-bit prime number
- $A$: Sum $(a + b)$
- $B$: Difference $(a − b)$

$$
p = \frac{17A^3 - 15B^3 - 45A^2B + 51AB^2}{8}
$$

If $p$ is prime, the function returns $a,\ b,\ p.$ The calling code then binds these as $p,\ q,\ r$ respectively, making $r = a^3 + 16b^3$.

## Vulnerability

The key insight is that the prime r can be factored in the number field $K = \mathbb{Q}(a)$, where $a$ is a root of $x^{3} − 16$. This means $a^3 = 16$. The ring of integers of this field, $\mathcal{O}_K$, contains elements of the form $p + qa$ where $p$, $q$ are rational integers.

## The Norm Map

A crucial concept here is the norm of an element in this number field. For an element p + qa, its norm is

$N(p + qa) = (p + qa)(p + q\omega a)(p + q\omega^2 a)$

where $\omega$ is a primitive cube root of unity. Expanding gives:

$$
N(p + qa) = p^3 + 16q^3
$$

This matches the exact form of r.

### Why this helps with factorization

When we factor r in the ring of integers $\mathcal{O}_K$, we’re effectively finding elements whose norm is $r$. Since r is constructed as $p^3$ + $16q^3$, one factor must be of the form $p + qa$. The coefficients of this linear factor directly reveal the integers $p$ and $q$ needed to reconstruct $N$.

### Recovery of the private key

With $p$ and $q$ recovered, and $r$ already known, we can:

1. Calculate the modulus $N = p \cdot q \cdot r$
2. Compute Euler's totient function: $\phi(N) = (p-1)(q-1)(r-1)$
3. Find the private exponent $d \equiv e^{-1} \pmod{\phi(N)}$
4. Decrypt the ciphertext: $pt \equiv ct^d \pmod{N}$

## Solution Steps

- **Setup:** The RSA modulus is $n = p \cdot q \cdot r$. One of the primes we are given $r$, is chosen such that $r = p^3 + 16 q^3$ for some unknown $p, q$.
- **Number Field Trick:** Consider the field $\mathbb{Q}(a)$ with $a^3 = 16$....
In this field, the norm of $p + q a$ is:
$p^3 + 16 q^3$ which equals $r$.
- **Factorization in the Number Field:** Factoring $r$ in this number field (i.e., factoring the ideal $(r)$ in $\mathcal{O}_K$) gives a linear factor that reveals $p$ and $q$.
- **Decrypting the flag:** Once $p, q, r$ are found, compute $\varphi(n)=(p-1)(q-1)$ (phi, Euler's totient function).
- invert $e$ modulo $\varphi(n)$ to find $d$, and decrypt the ciphertext.

```python
d = pow(e, -1, phi)
# Or using the inverse_mod function
d = inverse_mod(e, phi)
```

## SageMath Solution Code

```python
from Crypto.Util.number import *
from sage.all import *

r = 17089720847522532186100904495372954796086523439343401190123572243129905753474678094845069878902485935983903151003792259885100719816542256646921114782358850654669422154056281086124314106159053995410679203972646861293990837092569959353563829625357193304859110289832087486433404114502776367901058316568043039359702726129176232071380909102959487599545443427656477659826199871583221432635475944633756787715120625352578949312795012083097635951710463898749012187679742033
ct = 583923134770560329725969597854974954817875793223201855918544947864454662723867635785399659016709076642873878052382188776671557362982072671970362761186980877612369359390225243415378728776179883524295537607691571827283702387054497203051018081864728864347679606523298343320899830775463739426749812898275755128789910670953110189932506526059469355433776101712047677552367319451519452937737920833262802366767252338882535122186363375773646527797807010023406069837153015954208184298026280412545487298238972141277859462877659870292921806358086551087265080944696281740241711972141761164084554737925380675988550525333416462830465453346649622004827486255797343201397171878952840759670675361040051881542149839523371605515944524102331865520667005772313885253113470374005334182380501000

# Define our number field Q(a) where a^3 = 16
x = var("x")
K = NumberField(x^3 - 16, "a")
R = K.ring_of_integers()

# Factor r in the ring of integers
factors = R(r).factor()

for factor, exponent in factors:
    # Convert factor to polynomial representation
    f = (factor^exponent).polynomial()
    
    # We're looking for a linear factor of the form p + qa
    if f.degree() == 1:
        # Extract p (constant term) and q (coefficient of a)
        p = f.constant_coefficient()
        q = f.leading_coefficient()
        
        # Verify our factorization: r should equal p^3 + 16q^3
        assert p^3 + 16 * q^3 == r
        
        # Construct RSA parameters
        n = p * q * r
        phi = (p - 1) * (q - 1) * (r - 1)
        e = 65537
        
        # Calculate private exponent
        d = inverse_mod(e, phi)
        
        # Decrypt flag
        m = pow(ct, d, n)
        flag = long_to_bytes(m)
        print(f"Flag: {flag.decode()}")
```

```bash
sage -python solve.py
Flag: nite{7h3_Latt1c3_kn0ws_Ur_Pr1m3s_very_vvery_v3Ry_w3LLL}
```

## Final Notes

LLL is not required here at all. You can solve it with LLL if you try hard enough, but it’s unnecessary—the number field structure gives a direct, elegant route to the factors. Kind of takes the fun out of it otherwise.
