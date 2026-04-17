---
title: "CoCoracle - Official Solution Writeup"
summary: "Official solution write-up for the challenge 'CoCoracle' based off the COCONUT98 cipher and a SPN reduced round number implementation (5) in order to facilitate the **Boomerang Attack** within a reasonable amount of time for for GrizzHacks8 (2026)"
tags: ["block-cipher", "differential-cryptanalysis", "crypto"]
published: true
date: '2026-4-01'
slug: cocoracle-solution-official
---

- **Category:** Crypto 
- **Challenge:** CocOracle
- **Author:** supasuge 
- **Difficulty:** Medium 
- **Reference:** Wagner, _"The Boomerang Attack"_, FSE 1999, LNCS 1636, pp. 156–170

---

## Introduction

The boomerang attack is a differential attack that attempts to generate a "quartet" structure at an intermediate value halfway through the cipher.

**CocOracle** is a chosen-plaintext oracle challenge built around a simplified variant of the COCONUT98 block cipher — a real-world cipher designed by Serge Vaudenay in 1998 using _decorrelation theory_, a formal framework intended to give provable resistance against differential cryptanalysis. Despite the existence of a mathematical proof that no differential characteristic for the full cipher achieves probability better than $\approx 2^{-64}$, David Wagner demonstrated at FSE 1999 that the cipher could be broken with just $2^{16}$ adaptive chosen plaintext/ciphertext queries using what he called the **boomerang attack**.

This writeup covers the theory behind the attack in full, the design of the challenge cipher, and a walkthrough of the solution from first principles.

> **A note on the challenge design:** The original COCONUT98 uses 8 Feistel rounds split across two halves of 4 rounds each. For this challenge I intentionally reduced the round count to **5 rounds total** to keep the brute-force key recovery tractable within a CTF time window — no one should be sitting at a terminal waiting for a $2^{32}$ exhaustive search. The attack structure is identical; fewer rounds just means lower differential trail probability requirements and smaller key search spaces. Full 8-round COCONUT98 is absolutely attackable with the same approach.

---

## Background — Differential Cryptanalysis

Before diving into the boomerang, it helps to briefly establish what differential cryptanalysis is and why cipher designers care so much about it.

Differential cryptanalysis, introduced by Biham and Shamir in their landmark analysis of DES, studies how differences in plaintext pairs propagate through a cipher. If you encrypt two plaintexts $P$ and $P' = P \oplus \Delta$ under the same key and observe ciphertexts $C$ and $C'$, the _output difference_ $\Delta^* = C \oplus C'$ is not random — it carries statistical information about the internal structure of the cipher.

A **differential characteristic** is a predicted chain:

$$\Delta_0 \to \Delta_1 \to \Delta_2 \to \cdots \to \Delta_r$$

where $\Delta_i$ is the XOR difference after round $i$. Each arrow holds with some probability $p_i$, and the overall characteristic probability is roughly $\prod p_i$. If this product is large enough relative to $2^{-n}$ for an $n$-bit block, the cipher can be broken.

The standard defence against this is straightforward in principle: design round functions such that no differential characteristic for the full cipher exceeds some small threshold probability. A cipher where the best characteristic has probability $p$ is supposed to require at least $1/p$ chosen plaintexts to attack — this is the "folk theorem" that Wagner's boomerang attack disproves.

---

## The COCONUT98 Cipher

The full cipher is defined as:

$$E = \Psi_1 \circ M \circ \Psi_0$$

Three components, composed in sequence. Let us go through each.

### Key Schedule

The master key $K = (K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8)$ consists of eight 32-bit words, giving 256 bits total. Eight round subkeys $k_1, \ldots, k_8$ are derived as XOR combinations:

| Round $i$ | 1        | 2                | 3                           | 4                |
| --------- | -------- | ---------------- | --------------------------- | ---------------- |
| $k_i$     | $K_1$    | $K_1 \oplus K_3$ | $K_1 \oplus K_3 \oplus K_4$ | $K_1 \oplus K_4$ |
| Half      | $\Psi_0$ | $\Psi_0$         | $\Psi_0$                    | $\Psi_0$         |

| 5        | 6                | 7                           | 8                |
| -------- | ---------------- | --------------------------- | ---------------- |
| $K_2$    | $K_2 \oplus K_3$ | $K_2 \oplus K_3 \oplus K_4$ | $K_2 \oplus K_4$ |
| $\Psi_1$ | $\Psi_1$         | $\Psi_1$                    | $\Psi_1$         |

The remaining four key words $K_5, K_6, K_7, K_8$ feed exclusively into the decorrelation module $M$.

> [!warning] Key Schedule Weakness $K_3$ and $K_4$ appear in **both** Feistel halves. The schedule is a perfect mirror: $\Psi_0$ uses $(K_1, K_3, K_4)$ while $\Psi_1$ uses $(K_2, K_3, K_4)$. This shared structure is directly exploited during key recovery — once $K_3$ is recovered from one half it immediately constrains the other.

### The Feistel Round Function $F_i$

Each Feistel half consists of four applications of the same round function. For a 64-bit state split as $(x, y)$ where $x, y \in \mathbb{Z}_2^{32}$:

$$F_i(x,\ y) = \Bigl(y,;; x \oplus \varphi!\bigl(\mathrm{ROL}_{11}!\left(\varphi(y \oplus k_i)\right) + c \bmod 2^{32}\bigr)\Bigr)$$

The helper function $\varphi$ is:

$$\varphi(x) = x + 256 \cdot S(x \bmod 256) \bmod 2^{32}$$

| Symbol                                     | Description                                       |
| ------------------------------------------ | ------------------------------------------------- |
| $S : \mathbb{Z}_2^8 \to \mathbb{Z}_2^{24}$ | Fixed public S-box (8-bit input, used as integer) |
| $\mathrm{ROL}_{11}(\cdot)$                 | Left-rotate a 32-bit word by 11 bit positions     |
| $c \in \mathbb{Z}_2^{32}$                  | Public 32-bit constant — not a secret             |
| $k_i$                                      | Round subkey for round $i$                        |

The two halves are composed as:

$$\Psi_0 = F_4 \circ F_3 \circ F_2 \circ F_1 \qquad \text{(rounds 1–4)}$$

$$\Psi_1 = F_8 \circ F_7 \circ F_6 \circ F_5 \qquad \text{(rounds 5–8)}$$

Both use the identical $F_i$ function — only the subkeys differ.

### Decorrelation Module $M$

After $\Psi_0$ produces the mid-block value $(L_4, R_4)$, the decorrelation module applies:

$$M(xy) = (xy \oplus K_5 K_6) \times K_7 K_8 \bmod \mathrm{GF}(2^{64})$$

where $xy = L_4 \mathbin{|} R_4$ is the 64-bit concatenation. The term $K_5 \mathbin{|} K_6$ acts as an **additive** (XOR) key and $K_7 \mathbin{|} K_8$ acts as a **multiplicative** key in the field $\mathrm{GF}(2^{64})$.

This is a **bijective affine map** over $\mathrm{GF}(2^{64})$. Vaudenay proved that for any nonzero differential $\delta \to \delta^*$ through $M$:

$$\Pr[\delta \to \delta^*\ \text{through}\ M] = \frac{1}{2^{64} - 1}$$

averaged over all key choices. This was meant to be the kill-switch against differential attacks: no differential can cross the module with useful probability.

> [!info] The Security Claim Using decorrelation theory, Vaudenay proved that the **full cipher** $E$ admits no differential characteristic with probability better than $\approx 2^{-64}$. On its face this sounds airtight.

> [!danger] Why the Proof Doesn't Save It The proof applies to the **full cipher**, averaged over **all keys**. It says absolutely nothing about the differential behaviour of **half** the cipher at a **fixed unknown key**. Wagner's attack never pushes a differential through $M$ at all — it constructs a quartet of plaintexts and ciphertexts such that $M$ cancels out of the attack equation entirely.

---

## The Challenge Cipher — `chal.py`

The challenge departs from the full COCONUT98 in a few important ways. Reading `chal.py` carefully before attacking anything is always step one.

### The Round Function (Simplified)

```python
MASK32 = 0xFFFFFFFF
BLOCK_SIZE = 8
ROUNDS = 5  # reduced from 8 for CTF tractability

def rotl32(x: int, n: int) -> int:
    n &= 31
    return ((x << n) | (x >> (32 - n))) & MASK32

def F(R: int, k: int) -> int:
    return rotl32(R, k) ^ k

def feistel_round(L: int, R: int, k: int) -> Tuple[int, int]:
    return R, (L ^ F(R, k)) & MASK32
```

The challenge's round function is a deliberate simplification of the full COCONUT98 $F_i$. Rather than the full:

$$F_i(x, y) = \bigl(y,; x \oplus \varphi(\mathrm{ROL}_{11}(\varphi(y \oplus k_i)) + c)\bigr)$$

the challenge uses:

$$F_i(x, y) = \bigl(y,; x \oplus (\mathrm{ROL}_k(y) \oplus k)\bigr)$$

where both the rotation amount **and** XOR constant are the round key $k$ itself. This makes the differential behaviour considerably more transparent — the round key directly controls the rotation — which is what enables a clean meet-in-the-middle differential attack on the solver side. The structural lesson (high-probability half-cipher differentials bypass the decorrelation layer) remains identical.

### The Key Schedule

```python
def keySchedule(key: bytes) -> List[int]:
    if len(key) != 16:
        raise ValueError("Key must be 16 bytes")

    seed = int.from_bytes(key[:8], "big") ^ int.from_bytes(key[8:], "big")

    def next_u64(x: int) -> int:
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    rk = []
    x = seed & 0xFFFFFFFFFFFFFFFF
    for _ in range(ROUNDS):
        x = next_u64(x)
        rk.append(x & 0x1F)  # <-- only 5 bits!
    return rk
```

Several observations here:

1. The actual key material is 16 bytes, but the schedule seeds a **xorshift64** PRNG from a 64-bit value derived from XORing the two 8-byte halves. This means the key entropy is at most 64 bits.
2. Each round key is then masked to `0x1F` — only **5 bits**, giving 32 possible values per round key. With 5 rounds that is a worst-case key space of $32^5 = 2^{25} \approx 33$ million, but the attack will recover keys in $O(32^3)$ per candidate from the last round — far less than exhaustive.
3. The PRNG is a xorshift64 variant with a multiplicative finaliser. This is not relevant to the attack since we treat the round keys as independent unknowns.

The critical takeaway: **each round key $k_i \in {0, 1, \ldots, 31}$**. This is a five-bit value, which is what makes brute force across round keys practical.

### The Oracle Interface

```python
case ["enc", hx]:
    pt = bytes.fromhex(hx)
    if len(pt) != 8:
        print("ERR: must be exactly 8 bytes (16 hex chars)", flush=True)
        continue
    ct = encrypt(key, pt)[:8]
    print(ct.hex(), flush=True)

case ["flag"]:
    print(flag_ct.hex(), flush=True)
```

The oracle accepts an arbitrary 8-byte plaintext and returns the corresponding 8-byte ciphertext under a fixed, unknown key. The flag is separately encrypted under the same key. This is a **chosen-plaintext oracle** — we can query as many encryptions as we need.

### Encryption Flow

```
Plaintext (L₀ ‖ R₀)  —  64-bit block
        │
        ▼
  feistel_round(L, R, k₀)   →   (R, L ⊕ rotl32(R, k₀) ⊕ k₀)
  feistel_round(L, R, k₁)   →   ...
  feistel_round(L, R, k₂)   →   ...
  feistel_round(L, R, k₃)   →   ...
  feistel_round(L, R, k₄)   →   (L₅, R₅)
        │
        ▼
Ciphertext (L₅ ‖ R₅)  —  64-bit block
```

No decorrelation module is present in the challenge cipher — the module was the part of COCONUT98 that the decorrelation proof applied to. Removing it and reducing the round count gives us a pure Feistel cipher whose entire security rests on the key schedule, which we are about to attack.

---

## Differential Analysis of the Challenge Cipher

Before writing a single line of solver code, we need to understand how XOR differences propagate through the round function. This is the heart of any differential attack.

### How Differences Propagate Through $F$

The round function is:

$$F(L, R, k) \to (R,; L \oplus \mathrm{ROL}_k(R) \oplus k)$$

Consider two inputs $(L, R)$ and $(L \oplus \delta_L, R \oplus \delta_R)$. Their outputs differ as:

$$\delta_L^{\text{out}} = \delta_R$$

$$\delta_R^{\text{out}} = \delta_L \oplus \bigl(\mathrm{ROL}_k(R) \oplus \mathrm{ROL}_k(R \oplus \delta_R)\bigr)$$

The first component is trivial — the left output difference is always just the right input difference, because the left output _is_ the right input. The second component depends on how the rotation interacts with $\delta_R$.

In the solver this is implemented as:

```python
def diff_forward(dL, dR, k):
    """Propagate XOR differences forward through one Feistel round."""
    return dR, (dL ^ rotl32(dR, k)) & MASK32

def diff_backward(dL_next, dR_next, k):
    """Propagate XOR differences backward through one Feistel round (inverse)."""
    dR_prev = dL_next
    dL_prev = (dR_next ^ rotl32(dR_prev, k)) & MASK32
    return dL_prev, dR_prev
```

These are the forward and backward differential propagation functions. Note how clean the inversion is: given the output differences and the round key, we can compute the input differences exactly. This linearity of difference propagation through XOR and rotation is precisely what makes the attack work.

> [!note] Why rotation is linear over differences XOR differences are preserved perfectly under XOR and bit rotation: $\mathrm{ROL}_k(a \oplus b) = \mathrm{ROL}_k(a) \oplus \mathrm{ROL}_k(b)$ for any fixed rotation amount $k$. This means the difference $\delta_R$ rotated by $k$ gives exactly the XOR-difference contribution from the rotation step. There is no carry arithmetic here (unlike the full COCONUT98's modular addition in $\varphi$), so difference propagation through this simplified cipher is completely deterministic — probability 1 given the key.

### The Key Attack Idea

Because each round key $k_i \in {0, \ldots, 31}$ is only 5 bits, and because differential propagation is deterministic (probability 1 for any fixed key), we can mount a **meet-in-the-middle differential attack**:

1. Collect several plaintext/ciphertext difference pairs from the oracle.
2. For each candidate last-round key $k_4 \in {0, \ldots, 31}$: peel one round off the ciphertext side to get differences at round 4.
3. For candidates $(k_0, k_1) \in {0, \ldots, 31}^2$: propagate the input differences forward through the first two rounds.
4. For candidates $(k_3, k_2) \in {0, \ldots, 31}^2$: propagate the peeled differences backward through rounds 4 and 3.
5. If the forward and backward propagations meet at the middle (round 2/3 boundary), we have found a consistent key.

The cost is $32 \times (32^2 + 32^2) = 32 \times 2048 \approx 65{,}536$ operations — trivially fast. The multiple input differences we collect act as filters that eliminate false positives.

---

## The Solver — `solve.py` Walkthrough

Now let us walk through the complete solution code.

### Oracle Interface

```python
class Oracle:
    def __init__(self, tube):
        self.p = tube
        self._drain_banner()

    def _drain_banner(self):
        for _ in range(40):
            try:
                line = self.p.recvline(timeout=0.15)
            except EOFError:
                break
            if not line:
                break

    def _recv_hex_line(self, *, exact_len: int | None = None) -> bytes:
        for _ in range(500):
            line = self.p.recvline(timeout=2)
            if not line:
                continue
            s = line.strip()
            if not s or s.startswith(b"ERROR"):
                continue
            if not HEX_RE.fullmatch(s):
                continue
            if len(s) % 2 != 0:
                continue
            if exact_len is not None and len(s) != exact_len:
                continue
            return bytes.fromhex(s.decode())
        raise RuntimeError("Timed out waiting for hex response")

    def enc(self, pt: bytes) -> bytes:
        self.p.sendline(b"enc " + pt.hex().encode())
        return self._recv_hex_line(exact_len=16)

    def flag(self) -> bytes:
        self.p.sendline(b"flag")
        return self._recv_hex_line(exact_len=None)
```

The `Oracle` class wraps the pwntools tube into a clean interface with two methods: `enc(pt)` sends an 8-byte plaintext and returns the 8-byte ciphertext, and `flag()` retrieves the encrypted flag. The `_recv_hex_line` method handles all the banner noise the server emits before and after commands — it skips any line that is not pure hex, which is robust against version strings, help text, and prompt characters regardless of whether `stdin` is a tty.

The `_drain_banner` timeout of 150ms is deliberately short — we do not want to block at startup waiting for a slow server, but we do want to consume the initial banner so it does not pollute our first actual response.

### Collecting Differential Data

```python
def collect_diffs(oracle) -> List[DiffVec]:
    base = b"\x00" * 8
    deltas = [
        join_lr(0, 1),           # single bit in right half
        join_lr(1, 0),           # single bit in left half
        join_lr(0x80000000, 0x10000),  # two bits across both halves
    ]

    out = []
    for i, d in enumerate(deltas):
        c0 = oracle.enc(base)
        c1 = oracle.enc(xor_bytes(base, d))
        in_d = split_lr(d)
        out_d = split_lr(xor_bytes(c0, c1))
        log(f"[Δ{i}] in={in_d} out={out_d}")
        out.append(DiffVec(in_d, out_d))
    return out
```

We query the oracle with a fixed base plaintext (all zeros) and three variants formed by XORing in chosen input differences $\Delta$. For each pair we record:

- `in_diff`: the input XOR difference $(δ_L, δ_R)$
- `out_diff`: the observed output XOR difference $C \oplus C'$ split into $(δ_L^{\text{out}}, δ_R^{\text{out}})$

Three difference vectors gives us three independent constraints that any candidate key tuple $(k_0, k_1, k_2, k_3, k_4)$ must simultaneously satisfy. This is sufficient to uniquely identify the key in practice — a random wrong key guess satisfies all three constraints with probability roughly $(2^{-32})^3$ per component, meaning false positives are astronomically unlikely.

The choice of deltas is intentional:

- `join_lr(0, 1)` — a single bit in the low position of the right half. Clean and easy to verify manually.
- `join_lr(1, 0)` — a single bit in the low position of the left half. Tests the other path through the Feistel network.
- `join_lr(0x80000000, 0x10000)` — bits in both halves, spread across the word, exercising interaction between the two halves across multiple rounds.

### Key Recovery — Meet in the Middle

```python
def recover_keys(dv: List[DiffVec]) -> List[int]:
    for k4 in range(32):
        # Peel the last round off every observation
        peeled = []
        for v in dv:
            dLr, dRr = v.out_diff
            prev = diff_backward(dLr, dRr, k4)
            peeled.append((v.in_diff, prev))

        # Forward table: (k0, k1) → signature of middle differences
        fwd = {}
        for k0 in range(32):
            for k1 in range(32):
                sig = []
                for (dL, dR), _ in peeled:
                    a, b = diff_forward(dL, dR, k0)
                    a, b = diff_forward(a, b, k1)
                    sig.append((a, b))
                fwd[tuple(sig)] = (k0, k1)

        # Backward table: (k3, k2) → signature of middle differences
        for k3 in range(32):
            for k2 in range(32):
                sig = []
                for _, (dL, dR) in peeled:
                    a, b = diff_backward(dL, dR, k3)
                    a, b = diff_backward(a, b, k2)
                    sig.append((a, b))
                sig = tuple(sig)
                if sig in fwd:
                    k0, k1 = fwd[sig]
                    return [k0, k1, k2, k3, k4]

    raise RuntimeError("No key found")
```

This is the core of the attack. Let us step through it carefully.

**Outer loop over $k_4$**: We iterate over all 32 possible values of the last-round key. For each candidate $k_4$, we peel one round off the ciphertext differences using `diff_backward`. This gives us what the difference _should be_ at the boundary between rounds 3 and 4, assuming $k_4$ is correct.

**Forward table construction**: For each $(k_0, k_1)$ pair, we propagate every input difference forward through rounds 0 and 1. The result is a tuple of differences at the round 1/2 boundary — we store this as a signature in a dictionary keyed on the full tuple. This builds the "forward" half of the meet in the middle.

**Backward table lookup**: For each $(k_3, k_2)$ pair, we propagate the peeled differences backward through rounds 3 and 2. The result should be the same differences at the round 1/2 boundary. If this backward-propagated signature matches anything in the forward table, all five keys are consistent with all three observations — we have found the key.

The use of a Python dictionary for the forward table makes the lookup $O(1)$, so the overall complexity is:

$$O!\left(32 \times (32^2 + 32^2)\right) = O(32^3) = O(2^{15})$$

operations — negligible.

**Why the signature approach works**: A single observation pair constrains the key but does not uniquely determine it (there may be multiple $(k_0, k_1)$ pairs that propagate one input difference to the same mid-cipher difference). But with three simultaneous observations forming a joint signature, the probability that two different key pairs produce identical signatures across all three is effectively zero. No false positives survive in practice.

### Decryption and Flag Recovery

```python
def decrypt_block(ct, keys):
    L, R = split_lr(ct)
    for k in reversed(keys):
        f = F(L, k)
        L, R = (R ^ f) & MASK32, L
    return join_lr(L, R)

def unpad_pkcs7(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > BLOCK_SIZE:
        raise ValueError("Bad padding")
    if data[-pad_len:] != bytes([pad_len] * pad_len):
        raise ValueError("Bad padding")
    return data[:-pad_len]

def decrypt(ct: bytes, keys: List[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(ct), BLOCK_SIZE):
        out += decrypt_block(ct[i:i + BLOCK_SIZE], keys)
    return unpad_pkcs7(bytes(out))
```

Decryption is straightforward: apply the round function in reverse order. The Feistel inverse of $(L', R') = (R, L \oplus F(R, k))$ is obtained by noting that $L = R'$ and $R = L' \oplus F(L, k)$ — so the inverse is:

```python
f = F(L, k)     # F(L, k) = rotl32(L, k) ^ k, but L here is the previous R
L, R = (R ^ f) & MASK32, L
```

The flag is PKCS#7 padded before encryption, so after decryption we strip the padding to recover the plaintext.

### Main Flow

```python
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "remote":
        host, port = sys.argv[2], int(sys.argv[3])
        tube = remote(host, port)
    else:
        tube = process(["python3", "../build/chal.py"])

    oracle = Oracle(tube)
    try:
        dv = collect_diffs(oracle)      # 6 oracle queries total
        keys = recover_keys(dv)         # <1 second offline
        log(f"[+] Round keys: {keys}")

        ct = oracle.flag()              # 1 more query
        pt = decrypt(ct, keys)
        log(f"[+] Flag: {pt.decode(errors='replace')}")
    finally:
        oracle.close()
```

Total oracle queries: **7** — 6 to collect differential data, 1 to get the encrypted flag. Total runtime: a few seconds at most.

---

## The Full COCONUT98 Connection

It is worth being explicit about how the challenge maps to the original COCONUT98 boomerang attack, since the two are structurally parallel even though the challenge omits the decorrelation module.

### Original vs. Challenge

|Property|Original COCONUT98|CocOracle Challenge|
|---|---|---|
|Block size|64 bits|64 bits|
|Key size|256 bits|128 bits (→ 64-bit seed)|
|Rounds|8 (two halves of 4)|5 (intentionally reduced)|
|Round function|Full $\varphi$ + $\mathrm{ROL}_{11}$ + $S$-box|$\mathrm{ROL}_k(R) \oplus k$|
|Decorrelation module|Yes, $M$ over $\mathrm{GF}(2^{64})$|Omitted|
|Attack|Boomerang quartet|Meet-in-the-middle differential|
|Data complexity|$2^{16}$ adaptive CP/CC|6 chosen plaintexts|
|Key space per round key|32 bits|5 bits|

The challenge strips away the hardest part of the real attack (bypassing the decorrelation module with the boomerang quartet) and replaces it with a clean meet-in-the-middle approach that illustrates the same fundamental idea: **differential propagation through the Feistel rounds is deterministic given the key, and high-probability half-cipher characteristics can be composed to recover round keys without exhaustive search**.

### Why the Real Boomerang Works

In the full COCONUT98, the obstacle is $M$. You cannot push a differential characteristic past it because $M$ randomises differences over all keys with near-uniform probability. The boomerang sidesteps this entirely by constructing a _quartet_:

1. Choose $P$ and $P' = P \oplus \Delta$.
2. Encrypt both: obtain $C = E(P)$, $C' = E(P')$.
3. Set $D = C \oplus \nabla$ and $D' = C' \oplus \nabla$.
4. Decrypt both: obtain $Q = E^{-1}(D)$, $Q' = E^{-1}(D')$.

The four texts $(P, P', Q, Q')$ form a **right quartet** when two differential characteristics hold simultaneously — one through $\Psi_0$ in the forward direction, one through $\Psi_1^{-1}$ in the backward direction. The quartet condition is:

$$E_0(Q) \oplus E_0(Q') = \Delta^*$$

Because $M$ is affine over $\mathrm{GF}(2^{64})$, it satisfies $M(a) \oplus M(b) = M(a \oplus b)$ for any fixed key. This means the difference imposed at the ciphertext side, when decrypted through $\Psi_1^{-1}$, maps to a difference at the input of $M$ that depends only on the key — not on the actual ciphertext values. Across the two pairs in the quartet, this key-dependent difference appears twice and cancels:

$$\Delta^* \oplus \nabla^* \oplus \nabla^* = \Delta^*$$

The $\nabla^*$ terms vanish. The attacker never needs to know $K_5, K_6, K_7, K_8$. The module that was supposed to provide $2^{64}$ security is sidestepped in $O(q^{-4})$ queries, where $q \approx 2^{-4.3}$ is the half-cipher characteristic probability — giving $O(2^{16})$.

For $\Delta = \nabla = (e_{10}, e_{31})$ (single-bit differences at specific positions), the combined success probability per quartet is:

$$p \approx 0.023 \times 0.023 \approx \frac{1}{1900}$$

About 3800 queries are needed to distinguish; key recovery requires around $2^{16}$ total adaptive chosen plaintext/ciphertext queries and $2^{38}$ offline work. Compare this to the best classical attack (meet-in-the-middle on the key schedule), which requires $2^{96}$ trial encryptions.

---

## Running the Solver

### Local

```bash
# Start the challenge
python3 chal.py

# In a second terminal (or use the process wrapper in solve.py)
python3 solve.py
```

The solve script defaults to launching `../build/chal.py` as a subprocess:

```python
tube = process(["python3", "../build/chal.py"])
```

### Remote

```bash
python3 solve.py remote <host> <port>
```

### Expected Output

```
[+] Starting challenge
[Δ0] in=(0, 1) out=(some, values)
[Δ1] in=(1, 0) out=(some, values)
[Δ2] in=(2147483648, 65536) out=(some, values)
[+] Brute-forcing last round key k4
[+] KEY FOUND
[+] Round keys: [k0, k1, k2, k3, k4]
[+] Flag: GRIZZ{...}
```

---

## Design Lessons

COCONUT98 remains one of the most instructive examples in the history of symmetric cryptography for two reasons that are in tension with each other:

**Decorrelation theory works as advertised.** The full cipher genuinely has no differential characteristic better than $2^{-64}$. The mathematical proof is correct. The framework is sound and has proved influential in subsequent cipher design.

**Proofs about the full cipher do not guarantee security against all attacks.** The boomerang attack is not a differential attack on $E$ — it is two differential attacks on $E_0$ and $E_1^{-1}$ independently, whose outputs are combined via a quartet structure that sidesteps the hard middle layer. The folk theorem "eliminate all high-probability differentials and you are safe against differential attacks" is provably false. A characteristic of probability $q$ for _half_ the cipher is sufficient for a boomerang attack needing only $O(q^{-4})$ queries.

The implication for cipher designers: it is not enough to place a strong randomising layer in the middle of a cipher and prove security for the whole construction. That layer must be robust against being bypassed. Wagner suggests two fixes:

- Use significantly more rounds in each Feistel half (at least 16 rather than 4), so that half-cipher characteristics lose all probability.
- Embed decorrelation modules _within_ each round rather than only at the midpoint — as done in the DFC AES submission.

The challenge is designed to let you experience this lesson directly: a cipher with provable-sounding security properties falls apart in six queries once you understand the differential structure of its rounds.

---

## References

- Wagner, D. (1999). [_The Boomerang Attack_](https://link.springer.com/content/pdf/10.1007/3-540-48519-8_12.pdf). FSE 1999, LNCS 1636, pp. 156–170.
- Vaudenay, S. (1998). [_Provable Security for Block Ciphers by Decorrelation_](https://link.springer.com/chapter/10.1007/BFb0028566). STACS 1998.
- Biham, E., Shamir, A. (1991). _Differential Cryptanalysis of DES-like Cryptosystems_. Journal of Cryptology 4(1), pp. 3–72.

---

## Tags

`#ctf-writeup` `#grizzhacks8` `#cryptanalysis` `#block-cipher` `#feistel` `#differential-cryptanalysis` `#boomerang-attack` `#chosen-plaintext` `#meet-in-the-middle` `#python`