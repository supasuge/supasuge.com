---
title: 'x86 Basics: Opcodes, Operands, and a Few Core Instructions'
summary: A quick refresher on what opcodes look like in a disassembler, the three
  operand types (immediate, register, memory), and several common x86 instructions
  (MOV, LEA, NOP, SHL/SHR) plus the most common EFLAGS bits you’ll see referenced
  during reversing and exploitation.
tags:
- x86
- assembly
- reverse-engineering
- opcodes
- operands
- mov
- lea
- nop
- eflags
published: true
date: '2025-12-26'
slug: x86-opcodes-operands-core-instructions
---

# x86 Basics: Opcodes, Operands, and a Few Core Instructions

## Opcodes

A **byte** is **8 bits** (often represented in **hex**). At the machine-code level, a CPU executes sequences of bytes. Those bytes include:

- **Opcodes**: numeric values that correspond to CPU instructions
- **Operands**: the registers, immediate constants, or memory locations the instruction operates on

A **disassembler** translates raw opcode bytes into human-readable assembly.

Example: moving the immediate value `0x5f` into the `eax` register:

`mov eax, 0x5f`

In a disassembler you may see something like:

`040000:    b8 5f 00 00 00    mov eax, 0x5f`

- `040000:` is the address where the instruction is located.
- `b8` is the opcode corresponding to `mov eax, imm32`.
- `5f 00 00 00` is the immediate operand encoded in **little-endian** form.

Because of endianness, `0x0000005f` is stored as bytes `5f 00 00 00`.

If you ever need to map bytes to instructions manually, opcode references exist (e.g., http://ref.x86asm.net/index.html), but in practice disassemblers handle this automatically.

## Types of Operands

In x86 assembly, operands commonly fall into three categories:

- **Immediate operands**: constant values embedded in the instruction (e.g., `0x5f`).
- **Register operands**: CPU registers like `eax`, `ebx`, etc.
- **Memory operands**: memory references denoted by square brackets (e.g., `[eax]`).

A memory operand like `[eax]` means: treat the value in `eax` as an address, and operate on the value stored at that memory address.

## General instructions

## The MOV Instruction

`mov` copies data from a source to a destination:

`mov destination, source`

Common forms:

Move an immediate into a register:

`mov eax, 0x5f`

Copy one register into another:

`mov ebx, eax`

Load a value from an absolute memory address:

`mov eax, [0x5fc53e]`

Load via a register holding an address:

`mov ebx, 0x5fc53e   mov eax, [ebx]`

You can also use addressing expressions with offsets (very common for stack frames):

`mov eax, [ebp+4]`

This computes the address `ebp + 4` and loads the value stored at that address.

### The LEA Instruction

`lea` means **load effective address**:

`lea destination, source`

Key distinction:

- `mov eax, [ebp+4]` loads the **value at memory** address `ebp+4`.
- `lea eax, [ebp+4]` loads the **address itself** (`ebp+4`) into `eax`.

Example:

`lea eax, [ebp+4]`

Compilers often use `lea` as a convenient way to do arithmetic (including combined add/multiply patterns) without actually dereferencing memory.

### The NOP Instruction

`nop` performs **no operation**:

`nop`

It advances execution to the next instruction without changing architectural state in a meaningful way.

A classic exploitation/malware pattern is the **NOP sled**: a run of `nop` instructions used as padding so execution can “land” somewhere in the sled and slide into the real payload without needing an exact jump target.

### Shift Instructions

Shift instructions move bits left or right by a given count:

`shr destination, count   shl destination, count`

- `shl` (shift left) is commonly equivalent to multiplying by powers of two.
- `shr` (logical shift right) is commonly equivalent to dividing (unsigned) by powers of two.

Shifts also interact with CPU flags (notably the carry flag).

## x86 Flags (EFLAGS) Quick Reference

x86 maintains condition bits in the **flags register** (often referred to as **EFLAGS**). Many instructions update these flags, and conditional jumps read them.

| Flag | Abbreviation | Explanation |
|---|---|---|
| Carry | CF | Set when a carry-out or borrow is required from the most significant bit in an arithmetic operation. Also used for bit-wise shifting operations. |
| Parity | PF | Set if the least significant byte of the result contains an even number of 1 bits. |
| Auxiliary | AF | Set if a carry-out or borrow is required from bit 3 to bit 4 in an arithmetic operation (BCD arithmetic). |
| Zero | ZF | Set if the result of the operation is zero. |
| Sign | SF | Set if the result of the operation is negative (i.e., the most significant bit is 1). |
| Overflow | OF | Set if there's a signed arithmetic overflow (e.g., adding two positive numbers and getting a negative result or vice versa). |
| Direction | DF | Determines the direction for string processing instructions. If DF=0, the string is processed forward; if DF=1, the string is processed backward. |
| Interrupt Enable | IF | If set (1), it enables maskable hardware interrupts. If cleared (0), interrupts are disabled. |
