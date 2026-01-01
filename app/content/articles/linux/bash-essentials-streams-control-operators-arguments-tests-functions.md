---
title: 'Bash Essentials: Streams, Control Operators, Arguments, Tests, and Functions'
summary: 'A practical reference to core Bash scripting concepts: standard streams
  and file descriptors, common control and redirection operators, positional arguments,
  test operators for files and numbers, and a simple function example.'
tags:
- bash
- shell
- scripting
published: true
date: '2025-12-27'
slug: bash-essentials-streams-control-operators-arguments-tests-functions
---

# Bash Essentials: Streams, Control Operators, Arguments, Tests, and Functions

These notes cover a handful of Bash fundamentals that show up in most real-world scripts: how programs read/write data (streams), how to chain commands (control operators), how scripts receive parameters (positional arguments), how to make decisions (test operators), and how to reuse logic (functions).

## `expr` (evaluating expressions)

`expr` evaluates expressions and is historically used for simple arithmetic and string operations. In modern Bash, you’ll often use arithmetic expansion instead (`$(( ... ))`) or `[[ ... ]]` for string comparisons, but you may still encounter `expr` in older scripts.

- `expr`: Evaluates expressions.
- Arrays can have their values swapped similarly to Python.

## Streams (stdin, stdout, stderr)

In Unix-like systems, a program communicates with its environment using *streams*. These are represented by file descriptors (fds): small integers that identify open files/streams.

- **`stdin`**: standard input
  - file descriptor: **0**
- **`stdout`**: standard output
  - file descriptor: **1**
- **`stderr`**: standard error
  - file descriptor: **2**

Why this matters in scripts:

- You can redirect output to files or other commands.
- You can separate normal output (`stdout`) from error output (`stderr`) for logging and automation.

## Control operators and redirection

Bash provides operators to control *when* commands run and *where* their input/output goes.

### Command control operators

- **`&`**: Runs a command in the background.
- **`&&`**: Logical AND; runs the second command only if the first succeeds.
- **`( ... )`**: Groups commands.
- **`;`**: Command separator; runs the next command after the previous finishes, regardless of success.
- **`;;`**: Terminates a `case` statement.
- **`|`**: Pipes the output of one command as input to another.
- **`||`**: Logical OR; runs the second command if the first fails.

### Redirection operators

- **`>`**: Redirects `stdout` to a file (overwrites).
- **`&>`**: Redirects both `stdout` and `stderr` to a file (overwrites).
- **`&>>`**: Appends both `stdout` and `stderr` to a file.
- **`<`**: Redirects input from a file to a command.
- **`<<`**: Redirects multiple input lines to a command (here document).

## Positional arguments

Scripts receive command-line arguments via positional parameters:

- `$0` is the script name.
- `$1` is the first argument.
- `$2` is the second argument, and so on.

Example script:

```bash
#!/bin/bash
# This script pings any address provided as an argument.
SCRIPT_NAME="${0}"
TARGET="${1}"
echo "Running the script ${SCRIPT_NAME}..."
echo "Pinging the target: ${TARGET}..."
ping "${TARGET}"
```

Key variables:

- `TARGET` is the first positional argument passed from the command line.
- **`$@`**: Access all positional arguments.
- **`$#`**: Get the total number of arguments passed.

## Test operators

Bash conditionals commonly use `test` / `[ ... ]` (and in more advanced usage, `[[ ... ]]`). Test operators help you check file properties and compare numbers.

### File tests

- **`-d FILE`**: Checks if `FILE` is a directory.
- **`-r FILE`**: Checks if `FILE` is readable.
- **`-x FILE`**: Checks if `FILE` is executable.
- **`-w FILE`**: Checks if `FILE` is writable.
- **`-f FILE`**: Checks if `FILE` is a regular file.
- **`-s FILE`**: Checks if `FILE` size is greater than zero.

### Numeric comparisons

- **`-eq`**: Equal to another number.
- **`-ne`**: Not equal to another number.
- **`-ge`**: Greater than or equal to a number.
- **`-gt`**: Greater than a number.
- **`-lt`**: Less than a number.
- **`-le`**: Less than or equal to a number.

## Functions

Functions let you group reusable logic under a name.

```bash
#!/bin/bash
function_example() {
  echo "example function"
}
```

In Bash, functions are commonly used to:

- avoid repeating code
- give structure to longer scripts (e.g., `parse_args`, `check_deps`, `main`)
- isolate tasks (e.g., logging, cleanup)
