---
title: "Hash vegas - NiteCTF2025 writeup"
summary: "Writeup for the crypto challenge 'Hash Vegas' from NiteCTF2025 "
tags: ["PRNG", "Crypto", "CTF", "hashes", "Cryptanalysis"]
published: true
date: 2024-12-25T10:30:00Z
slug: hash-vegas
---

# Hash Vegas Writeup (Crypto)

- **Category:** Crypto  
- **Difficulty:** Hard  
- **Flag:** `nite{...}`


## Overview

Hash Vegas is a casino-themed cryptography challenge that combines two powerful cryptographic attacks:

1. **MT19937 PRNG State Recovery** - Predicting Python's random number generator
2. **SHA1 Length Extension Attack** - Forging authenticated messages without knowing the secret

The goal is to accumulate $1,000,000,000 starting from just $10,000 to obtain the flag. The challenge provides multiple "games" (slot machine, roulette, lottery) that all share the same compromised PRNG state.

---

## MT19937 Prediction Overview

### What is MT19937?

The Mersenne Twister (MT19937) is a pseudorandom number generator (PRNG) developed in 1997 by Makoto Matsumoto and Takuji Nishimura. It's the default PRNG in Python's `random` module, PHP, Ruby, and many other languages.

### Internal State

MT19937 maintains an internal state consisting of:

- An array of 624 32-bit unsigned integers: $s_0, s_1, \ldots, s_{623}$
- An index $i$ pointing to the current position in the state array

### The Tempering Transformation

When generating a random number, MT19937 doesn't output the raw state directly. Instead, it applies a **tempering transformation** to each state word before output:

$$y = s_i$$
$$y \leftarrow y \oplus (y \gg 11)$$
$$y \leftarrow y \oplus ((y \ll 7) \land \texttt{0x9D2C5680})$$
$$y \leftarrow y \oplus ((y \ll 15) \land \texttt{0xEFC60000})$$
$$y \leftarrow y \oplus (y \gg 18)$$

The final $y$ is the output.

### Untempering: Reversing the Transformation

The critical insight for attacking MT19937 is that **the tempering transformation is invertible**. Given an output $y$, we can recover the original state word $s_i$.

For each operation, we apply the inverse:

**Inverting $y \oplus (y \gg k)$:**

For a right-shift XOR, we can recover the original by iteratively XORing:

$$y' = y \oplus (y \gg k) \oplus (y \gg 2k) \oplus \ldots$$

This works because the top $k$ bits of $y$ are unchanged, allowing us to recover the next $k$ bits, and so on.

**Inverting $y \oplus ((y \ll k) \land M)$:**

For a masked left-shift XOR, we apply:

$$y' = y \oplus ((y' \ll k) \land M)$$

iteratively, since the bottom $k$ bits are unchanged.

### State Recovery Attack

If an attacker can observe **624 consecutive 32-bit outputs**, they can:

1. Untemper each output to recover the corresponding state word
2. Reconstruct the complete internal state array
3. Predict all future outputs indefinitely

This is exactly what we exploit in this challenge.

### Python's `getrandbits(n)` for Large $n$

When Python generates a random number larger than 32 bits (e.g., `random.randrange(2**256)`), it concatenates multiple 32-bit outputs:

$$\text{result} = \sum_{i=0}^{k-1} \text{getrandbits}(32)_i \cdot 2^{32i}$$

For 256 bits, this means 8 consecutive 32-bit values are consumed, giving us 8 state words per roulette round.

---

## SHA1 Hash Length Extension Attack Overview

### The Merkle-Damgård Construction

SHA1, like MD5, SHA-256, and many other hash functions, uses the **Merkle-Damgård construction**:

1. Initialize with a fixed IV (Initialization Vector): $H_0$
2. Pad the message $M$ to a multiple of the block size (64 bytes for SHA1)
3. Process each block $B_i$ through a compression function: $H_{i+1} = f(H_i, B_i)$
4. Output the final state $H_n$

### The Padding Scheme

SHA1 padding appends:
- A single `0x80` byte
- Zero bytes until length $\equiv 56 \pmod{64}$
- The original message length as a 64-bit big-endian integer

$$\text{pad}(M) = M \| \texttt{0x80} \| \texttt{0x00}^k \| \langle|M|\rangle_{64}$$

where $k$ is chosen so the total length is a multiple of 64 bytes.

### The Length Extension Vulnerability

The vulnerability arises because **the hash output IS the internal state**. Given:

$$H = \text{SHA1}(\text{secret} \| \text{message})$$

An attacker who knows $|secret|$ and $message$ can compute:

$$H' = \text{SHA1}(\text{secret} \| \text{message} \| \text{padding} \| \text{extension})$$

**Without knowing the secret!**

### How It Works

1. **Parse the known hash** $H$ into SHA1's five 32-bit state words $(h_0, h_1, h_2, h_3, h_4)$
2. **Calculate the padding** that would have been applied to $\text{secret} \| \text{message}$
3. **Initialize a new SHA1 computation** with state $(h_0, h_1, h_2, h_3, h_4)$ as if we've already processed $\text{secret} \| \text{message} \| \text{padding}$
4. **Process the extension** through the compression function
5. **Output the new hash** $H'$

The resulting $H'$ is a valid SHA1 hash of:

$$\text{secret} \| \text{message} \| \text{padding} \| \text{extension}$$

### Mathematical Formulation

Let $L = |\text{secret}| + |\text{message}|$ and $\text{pad}_L$ be the padding for length $L$.

Given $H = \text{SHA1}(\text{secret} \| M)$, we can compute:

$$H' = f(H, \text{pad}(\text{secret} \| M \| \text{pad}_L \| E) \text{ blocks after } L + |\text{pad}_L|)$$

where $E$ is our extension and $f$ is the SHA1 compression function.

---

## Analysis

### Challenge Structure

The challenge implements a casino with four games:

```python
# Starting balance
balance = 10000

# Game limits
SPIN_ROUNDS = 56      # Slot machine
ROULETTE_ROUNDS = 64  # Roulette
# Lottery: unlimited
```

**Goal:** Reach $1,000,000,000 to get the flag.

### Game Analysis

#### 1. Slot Machine (`slotmachine.py`)

```python
def spin(self):
    wheels = []
    for _ in range(2):
        outcome = random.choice(self.slots)  # Leaks RNG!
        for i in range(8):
            wheel = (outcome >> (i*4)) & 0xF
            wheels.append(self.SYMBOLS[wheel])
```

The `Slots` class has a custom `__getitem__` that returns the index itself:

```python
def __getitem__(self, index):
    return index  # Returns raw index!
```

This means `random.choice(self.slots)` returns the raw RNG output directly!

**RNG Leakage:** 2 × 32-bit values per spin = 112 values from 56 spins

#### 2. Roulette (`roulette.py`)

```python
def get(self):
    return random.randrange(0, 2**256 - 1)  # 256-bit number!
```

The full 256-bit number is printed, giving us 8 × 32-bit values per round.
**RNG Leakage:** 8 × 32-bit values per round = 512 values from 64 rounds
**Total Available:** $112 + 512 = 624$ values — exactly what we need!

#### 3. Lottery (`lottery.py`)

The lottery has a vulnerable voucher system:

```python
# Hash function selection (SHA1 is at index 2047)
self.hash_funcs = [hashlib.sha256]*1024 + [hashlib.sha3_224]*1023 + [hashlib.sha1]

# Voucher generation - VULNERABLE to length extension!
ticket_hash = hash_func((self.secret + ticket_data).encode()).digest()[:20]
```

The redemption parses amount from the **last** pipe-separated value:

```python
for part in reversed(parts):
    try:
        amount = int(part)  # Takes LAST integer!
        break
```

---

## Vulnerability

### Vulnerability 1: MT19937 State Recovery

We can collect exactly 624 32-bit RNG outputs:
- 56 slot spins × 2 outputs = 112 values
- 64 roulette rounds × 8 outputs = 512 values
- **Total: 624 values** = Complete MT19937 state

### Vulnerability 2: SHA1 Length Extension

The voucher system uses `H(secret || data)`, which is vulnerable when:
- SHA1 is used (index 2047 in the shuffled array)
- We know the secret length (32 bytes from `os.urandom(16).hex()`)
- We can append data (the `|` separated format allows appending `|<amount>`)

### Vulnerability 3: RNG Burning with `pay=0`

```python
def buy_ticket(self, pay, username):
    if not self.shuffled:
        random.shuffle(self.hash_funcs)  # First call only
        self.shuffled = True
    
    ticket_id = random.randint(1, 11)      # Always consumed
    hash_idx = random.randint(0, 2047)     # Always consumed
    
    if pay == 0:
        print('Hey you cannot pay nothing!')
        return False  # Returns early! No wallet loss!
    
    if ticket_id > 5:
        amount = random.randint(1, 10)     # Only if winner
        # ... generates voucher ...
        return True  # Balance set to 0!
```

With `pay=0`:

- RNG is consumed (ticket_id, hash_idx)
- Balance is **NOT** set to 0
- We can "burn" RNG calls without consequences

---

## Solution Execution Strategy

### Phase 1: Collect RNG State

```
┌─────────────────────────────────────────────────────────────┐
│                    RNG STATE COLLECTION                     │
├─────────────────────────────────────────────────────────────┤
│  Slot Machine (56 spins)                                    │
│    └─→ 2 × 32-bit values per spin = 112 values              │
│                                                             │
│  Roulette (64 rounds)                                       │
│    └─→ 8 × 32-bit values per round = 512 values             │
│                                                             │
│  Total: 624 values = Complete MT19937 State                 │
└─────────────────────────────────────────────────────────────┘
```

### Phase 2: Recover MT19937 State

Apply the untemper transformation to each collected value:

```python
def untemper(y):
    y ^= y >> 18                           # Invert step 4
    y ^= (y << 15) & 0xefc60000           # Invert step 3
    for _ in range(5):                     # Invert step 2
        y ^= (y << 7) & 0x9d2c5680
    y ^= y >> 11                           # Invert step 1
    y ^= y >> 22
    return y & 0xffffffff
```

### Phase 3: Simulate Shuffle to Find SHA1

```python
# Server's hash_funcs array
# SHA1 is originally at index 2047
hash_funcs = [sha256]*1024 + [sha3_224]*1023 + [sha1]

# Simulate the shuffle with recovered RNG
indices = list(range(2048))
rng.shuffle(indices)

# Find SHA1's new position
sha1_new_index = indices.index(2047)
```

### Phase 4: Find Target Ticket

Search for a ticket position where:
- `ticket_id > 5` (winning ticket)
- `hash_idx == sha1_new_index` (SHA1 is used)

```python
for target_n in range(1, 10000):
    # Simulate burning (target_n - 1) tickets with pay=0
    rng_test.setstate(post_shuffle_state)
    
    for _ in range(target_n - 1):
        rng_test.randint(1, 11)   # ticket_id
        rng_test.randint(0, 2047) # hash_idx
        # No amount with pay=0!
    
    # Check ticket at position target_n
    ticket_id = rng_test.randint(1, 11)
    hash_idx = rng_test.randint(0, 2047)
    
    if ticket_id > 5 and hash_idx == sha1_new_index:
        # Found our target!
        break
```

### Phase 5: Execute Burn Sequence

```
┌─────────────────────────────────────────────────────────────┐
│                    RNG BURN SEQUENCE                        |
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────┐ ┌──────┐ ┌──────┐       ┌──────┐ ┌──────────────┐ │
│  │pay=0 │ │pay=0 │ │pay=0 │  ...  │pay=0 │ │   pay=1      │ │
│  │ burn │ │ burn │ │ burn │       │ burn │ │  GET SHA1!   │ │
│  └──────┘ └──────┘ └──────┘       └──────┘ └──────────────┘ │
│     1        2        3          N-1         N              │
│                                                             │
│  Each burn consumes: randint(1,11) + randint(0,2047)        │
│  Final ticket: Gets SHA1-based voucher!                     │
└─────────────────────────────────────────────────────────────┘
```

### Phase 6: SHA1 Length Extension Attack

Given voucher: `A|5` with hash `H = SHA1(secret || "A|5")`

Forge: `A|5 || padding || |1000000001`

```
┌─────────────────────────────────────────────────────────────┐
│                SHA1 LENGTH EXTENSION                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Original: SHA1(secret || "A|5")                            │
│                    │                                        |
│                    ▼                                        │
│            ┌──────────────┐                                 │
│            │   Hash: H    │ ◄── This IS the internal state  │
│            └──────────────┘                                 │
│                    │                                        │
│                    ▼                                        │
│  Extended: SHA1(secret || "A|5" || pad || "|1000000001")    │
│                                                             │
│  Server parses: "A|5|<padding>|1000000001"                  │
│                              └─────┬─────┘                  │
│                                    │                        │
│                         Last integer = $1,000,000,001!      │
└─────────────────────────────────────────────────────────────┘
```

### Phase 7: Profit!

1. Redeem forged voucher → Balance becomes $1,000,000,001
2. Request flag → Victory!

---

## Solve Script Explanation

### Configuration and Imports

```python
from pwn import *
import hashlib
import struct
import re
import time
import random as stdlib_random

HOST = "vegas.chals.nitectf25.live"
PORT = 1337
USERNAME = b"A"  # Short username minimizes padding complexity
```

### SHA1 Length Extension Implementation

```python
def sha1_padding(message_len):
    """
    Generate SHA1 padding for a message of given length.
    
    Padding format:
    - 0x80 byte
    - Zero bytes until length ≡ 56 (mod 64)
    - 64-bit big-endian original message length
    """
    bit_len = message_len * 8
    padding = b'\x80'
    pad_len = (56 - (message_len + 1) % 64) % 64
    padding += b'\x00' * pad_len
    padding += struct.pack('>Q', bit_len)
    return padding
```

The `sha1_length_extension` function:

```python
def sha1_length_extension(original_hash_hex, original_data, append_data, secret_len):
    # Parse original hash into SHA1 state (5 × 32-bit words)
    original_hash = bytes.fromhex(original_hash_hex)
    h0, h1, h2, h3, h4 = struct.unpack('>5I', original_hash)
    
    # Calculate padding for secret || original_data
    total_original_len = secret_len + len(original_data)
    padding = sha1_padding(total_original_len)
    
    # New data = original_data || padding || append_data
    new_data = original_data + padding + append_data
    
    # Continue SHA1 from recovered state
    # Process append_data blocks...
    
    return new_hash, new_data
```

### MT19937 Untemper Function

```python
def untemper(y):
    """
    Reverse the MT19937 tempering transformation.
    
    Forward tempering:
        y ^= (y >> 11)
        y ^= (y << 7) & 0x9d2c5680
        y ^= (y << 15) & 0xefc60000
        y ^= (y >> 18)
    """
    y = y & 0xffffffff
    
    # Reverse: y ^= y >> 18
    y ^= y >> 18
    
    # Reverse: y ^= (y << 15) & 0xefc60000
    y ^= (y << 15) & 0xefc60000
    
    # Reverse: y ^= (y << 7) & 0x9d2c5680
    # Requires ceil(32/7) = 5 iterations
    mask = 0x9d2c5680
    t = y
    for _ in range(5):
        t = y ^ ((t << 7) & mask)
    y = t
    
    # Reverse: y ^= y >> 11
    y ^= y >> 11
    y ^= y >> 22
    
    return y & 0xffffffff
```

### State Recovery and RNG Reconstruction

```python
def create_random_from_state(mt_state, index=624):
    """
    Create a random.Random instance with recovered MT19937 state.
    
    Python's random state format:
    (version=3, (state[0], state[1], ..., state[623], index), None)
    """
    rng = stdlib_random.Random()
    state_tuple = tuple(mt_state) + (index,)
    rng.setstate((3, state_tuple, None))
    return rng
```

### Slot Machine Value Extraction

```python
SYMBOLS = ['🍒', '🍋', '🍊', '🍇', '🍉', '🍓', '🍍', '🍎',
           '🍏', '🍐', '🍑', '🍈', '🍌', '🥭', '🥝', '🥥']

def symbols_to_value(symbols):
    """
    Convert 8 slot symbols back to the original RNG output.
    
    Each symbol encodes 4 bits (index 0-15 in SYMBOLS).
    8 symbols = 32 bits total.
    """
    value = 0
    for i, sym in enumerate(symbols):
        idx = SYMBOLS.index(sym)
        value |= (idx << (i * 4))
    return value
```

### Main Exploit Flow

```python
def main():
    # Phase 1: Collect from slot machine (112 values)
    for i in range(56):
        v1, v2 = spin_slot(p)
        collected_values.extend([v1, v2])
    
    # Phase 2: Collect from roulette (512 values)
    for i in range(64):
        num = roulette_leak(p)  # 256-bit value
        for j in range(8):
            collected_values.append((num >> (32 * j)) & 0xffffffff)
    
    # Phase 3: Recover state
    mt_state = [untemper(v) for v in collected_values[:624]]
    rng = create_random_from_state(mt_state, index=624)
    
    # Phase 4: Simulate shuffle
    indices = list(range(2048))
    rng.shuffle(indices)
    sha1_new_index = indices.index(2047)
    
    # Phase 5: Find target ticket
    for target_n in range(1, 10000):
        rng_test.setstate(sim_state)
        for _ in range(target_n - 1):
            rng_test.randint(1, 11)
            rng_test.randint(0, 2047)
        
        ticket_id = rng_test.randint(1, 11)
        hash_idx = rng_test.randint(0, 2047)
        
        if ticket_id > 5 and hash_idx == sha1_new_index:
            tickets_to_burn = target_n - 1
            break
    
    # Phase 6: Execute burns
    for _ in range(tickets_to_burn):
        buy_lottery_ticket(p, 0)  # pay=0 burns RNG safely
    
    # Phase 7: Buy SHA1 ticket
    result = buy_lottery_ticket(p, 1)
    
    # Phase 8: Length extension attack
    new_hash, new_data = sha1_length_extension(
        result['voucher_code'],
        bytes.fromhex(result['voucher_data']),
        b"|1000000001",
        32  # Secret length
    )
    
    # Phase 9: Redeem and get flag
    redeem_voucher(p, new_hash[:40], new_data.hex())
    get_flag(p)
```

---

## Key Takeaways

### 1. MT19937 is NOT Cryptographically Secure

Despite its long period ($2^{19937} - 1$) and good statistical properties, MT19937 is **completely predictable** after observing just 624 outputs. This is why cryptographic applications must use CSPRNGs like `secrets` module or `/dev/urandom`.

**Key takeaway:** Never use `random` module for security-sensitive applications.

### 2. Hash-Based MACs Must Use HMAC

The construct $H(\text{secret} \| \text{message})$ is fundamentally broken for Merkle-Damgård hashes. The secure alternative is HMAC:

$$\text{HMAC}(K, M) = H((K' \oplus \text{opad}) \| H((K' \oplus \text{ipad}) \| M))$$

This construction is immune to length extension attacks because:

- The inner hash output is not directly exposed
- The outer hash "seals" the construction

### 3. Simulation Beats Prediction

Instead of manually reimplementing RNG algorithms (which can have subtle bugs), it's often better to:

1. Recover the state
2. Inject it into the actual library's RNG
3. Use the library's own functions for simulation

This ensures perfect accuracy without reimplementation bugs.

### 4. "Burn" Primitives Can Be Powerful

The `pay=0` path in the lottery allowed us to consume RNG calls without consequences. This kind of "oracle" for advancing state is incredibly powerful when combined with prediction attacks.

### 5. Defense in Depth Matters

This challenge had multiple vulnerabilities that chained together:

- RNG leakage -> State recovery -> Prediction
- Prediction -> Targeting SHA1 hash function
- SHA1 -> Length extension -> Forged $1B voucher

Any single fix would have broken the chain:

- Using CSPRNG
- Using HMAC instead of $H(\text{secret} \| \text{data})$
- Not leaking RNG outputs
- Not allowing `pay=0` RNG consumption
- Using SHA3 (which is resistant to length extension)

---

## References

1. Matsumoto, M., & Nishimura, T. (1998). Mersenne Twister: A 623-dimensionally equidistributed uniform pseudo-random number generator.
2. Duong, T., & Rizzo, J. (2009). Flickr's API Signature Forgery Vulnerability.
3. NIST FIPS 198-1: The Keyed-Hash Message Authentication Code (HMAC)
4. Merkle, R. C. (1989). A Certified Digital Signature.

---

*Writeup by Evan Pardon ([supasuge](https://github.com/supasuge) | NiteCTF 2025)*