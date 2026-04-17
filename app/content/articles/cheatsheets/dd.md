---
title: "DD - Cheatsheet"
summary: "Comprehensive cheatsheet for for `dd` CLI tool for Linux."
tags: ["Linux", "Tools", "dd"]
published: true
date: 2024-12-25T10:30:00Z
slug: dd-cheatsheet
---

# `dd` Command Cheatsheet

The `dd` command is a versatile utility in Unix and Unix-like systems used for converting and copying files. It is especially powerful for tasks involving low-level data operations on drives, partitions, and files. Below is a collection of common and advanced `dd` usage examples.

## Basic Syntax

```bash
dd if=<input_file> of=<output_file> bs=<block_size> count=<count>
```
The `dd` command is a powerful and versatile tool for Unix-like systems, used for copying and converting data at a low level. Below is an explanation of each flag and option provided by the `dd` command:

## Key Options

Here are example usages for each of the dd options you listed:

### Input/Output

- `if=FILE`

```bash
dd if=/dev/sda of=disk_image.img
```

Reads from the /dev/sda device as input.
---

- `of=FILE`

---

```bash
dd if=/dev/urandom of=random_data bs=1M count=10
```

- Writes 10MB of random data to a file named random_data.

---

### Block Size

- `bs=BYTES`

```bash
dd if=/dev/zero of=/dev/null bs=1M count=1000
```
Reads and writes in 1MB blocks, 1000 times.

- `ibs=BYTES`

```bash
dd if=/dev/sda of=backup.img ibs=4k
```

Reads from the input in 4KB blocks.

- `obs=BYTES`

```bash
dd if=/dev/urandom of=large_file obs=1M count=100
```

Writes to the output in 1MB blocks.

### Other Options

- `count=N`

```bash
dd if=/dev/urandom of=sample bs=1M count=5
```
  Copies only 5 blocks of 1MB each.

- `skip=N`:
```bash
dd if=/dev/sda of=partition.img bs=512 skip=2048
```
  Skips the first 2048 blocks (1MB) before starting to copy.

- `seek=N`:
```bash
dd if=/dev/zero of=sparse_file bs=1 count=1 seek=1G
```
  Creates a 1GB sparse file by skipping 1GB before writing.

- `status=LEVEL`:
```bash
dd if=/dev/zero of=/dev/null bs=1M count=1000 status=progress
```
  Shows progress during the operation.

### Common Conversions (`conv=`)
- `ascii`:
```bash
dd if=ebcdic_file of=ascii_file conv=ascii
```
  Converts an EBCDIC file to ASCII.

- `ebcdic`:
```bash
dd if=ascii_file of=ebcdic_file conv=ebcdic
```
  Converts an ASCII file to EBCDIC.

- `lcase`:
```bash
echo "HELLO WORLD" | dd conv=lcase
```
  Converts input to lowercase.

- `ucase`:
```bash
echo "hello world" | dd conv=ucase
```
  Converts input to uppercase.

- `noerror`:
```bash
dd if=/dev/sda of=disk_image conv=noerror,sync
```
  Continues copying even if read errors occur.

- `sync`:
```bash
dd if=/dev/sda of=disk_image bs=4k conv=sync
```
  Pads every input block with nulls to maintain block size.

- `fdatasync`:
  ```bash
  dd if=/dev/urandom of=testfile bs=1M count=100 conv=fdatasync
  ```
  Ensures data is physically written to disk before finishing.


### Multiplicative Suffixes

- **`c`**: 1 byte.# What can I help with?
- **`w`**: 2 bytes.
- **`b`**: 512 bytes.
- **`kB`**: 1000 bytes.
- **`K`**: 1024 bytes (1 KiB).
- **`MB`**: 1000 * 1000 bytes.
- **`M`**: 1024 * 1024 bytes (1 MiB).
- **`GB`**: 1000 * 1000 * 1000 bytes.
- **`G`**: 1024 * 1024 * 1024 bytes (1 GiB).
- **`T`, `P`, `E`, `Z`, `Y`, `R`, `Q`**: Larger multiples.
- **`B`**: Indicates that the value counts bytes instead of blocks.

## Examples

### 1. Filling a Drive with Random Data
Useful for securely wiping a drive.

```bash
dd if=/dev/urandom of=/dev/sda bs=4k
```

### 2. Drive-to-Drive Duplication
Copy the contents of one drive to another.

```bash
dd if=/dev/sda of=/dev/sdb bs=4096
```

### 3. Cleaning Up a Hard Drive# What can I help with?
Write zeros to a drive to erase its contents.

```bash
dd if=/dev/zero of=/dev/sda bs=4k
```

### 4. Copying from File to Tape Device
Copy data from a file to a tape device with synchronized I/O.

```bash
dd if=inputfile of=/dev/st0 bs=32k conv=sync
```

### 5. Copying Data from Tape to File
Reverse the previous operation, copying data from a tape device to a file.

```bash
dd if=/dev/st0 of=outfile bs=32k conv=sync
```

### 6. Checking if a Drive is Zeroed Out
Check for non-zero data on a drive.

```bash
dd if=/dev/sda | hexdump -C | grep [^00]
```

### 7. Filling Out a Partition with Random Data
Fill a partition with random data.

```bash
dd if=/dev/urandom of=/home/$USER/hugefile bs=4096
```

### 8. Scrambling a File
Overwrite a file with random data before deleting it.

```bash
dd if=/dev/urandom of=myfile bs=$(stat -c%s myfile) count=1
rm myfile
```

### 9. Copying a Partition to Another Partition
Copy data from one partition to another without truncating.

```bash
dd if=/dev/sda3 of=/dev/sdb3 bs=4096 conv=notrunc,noerror
```

### 10. Creating a Gzipped Image of a Partition
Create a compressed image of a partition.

```bash
dd if=/dev/sdb2 ibs=4096 | gzip > partition.image.gz conv=noerror
```

### 11. Copying Tape Drive Contents to a File
Convert from EBCDIC to ASCII while copying tape drive contents to a file.

```bash
dd bs=10240 cbs=80 conv=ascii,unblock if=/dev/st0 of=ascii.out
```

### 12. Copying from 1KB Block Device to 2KB Block Device
Copy data between devices with different block sizes.

```bash
dd if=/dev/st0 ibs=1024 obs=2048 of=/dev/st1
```

### 13. Copying Zeros to /dev/null
Benchmark I/O speed by copying zeros to the null device.

```bash
dd if=/dev/zero of=/dev/null bs=100M count=100
```

### 14. Erasing GPT from Disk
Erase the GPT by writing zeros to the beginning and end of the drive.

```bash
dd if=/dev/zero of=/dev/sda bs=512 count=2
dd if=/dev/zero of=/dev/sda seek=$(($(fdisk -s /dev/sda) - 20)) bs=1k
```

### 15. Creating a Bootable USB Drive
Write an image file to a USB drive to make it bootable.

```bash
dd if=/location/of/bootimage.img of=/dev/sdX
```

### 16. Checking for Bad Blocks
Read a drive to check for bad blocks.

```bash
dd if=/dev/sda of=/dev/null bs=1M
```

### 17. Copying the MBR to a Floppy
Copy the Master Boot Record (MBR) to a floppy disk.

```bash
dd if=/dev/sda of=/dev/fd0 bs=512 count=1
```

### 18. Drive-to-Drive Duplication with Partitions
Duplicate a specific partition from one drive to another.

```bash
dd if=/dev/sda1 of=/dev/sdb1 bs=4096
```

### 19. Creating a CD Image
Create an ISO image of a CD.

```bash
dd if=/dev/sr0 of=/home/$USER/mycdimage.iso bs=2048 conv=nosync
```

### 20. Replacing a Disk with Another of Identical Size
Replace a disk with another of identical size.

```bash
dd if=/dev/sda of=/dev/sdb bs=64k conv=sync
```

### 21. Creating DVD Images of a Partition
Create multiple DVD images of a partition for backup purposes.

```bash
dd if=/dev/sda2 of=/home/$USER/hddimage1.img bs=1M count=4430
```

### 22. Restoring from a Backup
Restore data from previously created DVD images.

```bash
dd if=/$location/hddimage1.img of=/dev/sda2 bs=1M
```

### 23. Destroying the Superblock
Destroy the superblock of a filesystem.

```bash
dd if=/dev/zero count=1 bs=1024 seek=1 of=/dev/sda6
```

### 24. Checking a File for Viruses
Check a file for viruses using ClamAV.

```bash
dd if=/home/$USER/suspicious.doc | clamscan -
```

### 25. Looking at the Contents of a Binary File
View the contents of a binary file using hexdump.

```bash
dd if=/home/$USER/binaryfile | hexdump -C | less
```

### 26. Benchmarking Hard Drive Read/Write Speed
Benchmark the read/write speed of a hard drive.

```bash
dd if=/dev/zero of=/home/$USER/bigfile bs=1024 count=1000000
```

### 27. Copying RAM to a File
Create an image of the system RAM.

```bash
dd if=/dev/mem of=myRAM bs=1024
```

### 28. Viewing MBR Content
Display the content of the Master Boot Record in hex and ASCII.

```bash
dd if=/dev/sda bs=512 count=1 | od -xa
```

### 29. Creating a Partition Copy with Limited Size
Create a copy of a partition, splitting it into smaller files.

```bash
dd if=/dev/sda1 | split -b 700m - sda1-image
```

### 30. Converting Text to Uppercase
Convert the output of a command to uppercase.

```bash
ls -l | dd conv=ucase
```

### 31. Converting Text to Lowercase
Convert any text to lowercase.

```bash
echo "MY UPPER CASE TEXT" | dd conv=lcase
```

### 32. Creating a Temporary Swap Space
Create a temporary swap file.

```bash
dd if=/dev/zero of=tmpswap bs=1k count=1000000
chmod 600 tmpswap
mkswap tmpswap
swapon tmpswap
```

### 33. Copying a Floppy Disk
Create an image of a floppy disk.

```bash
dd if=/dev/fd0 of=/home/$USER/floppy.image bs=2x80x18b conv=notrunc
```

### 34. Creating a 1KB File of Random Gibberish
Create a small file with random data.

```bash
dd if=/dev/urandom of=/home/$USER/myrandom bs=100 count=1
```

### 35. Printing a File to Stdout
Print the contents of a file to the terminal.

```bash
dd if=/home/$USER/myfile
```

### 36. Searching a Partition for a String
Search for a specific string within a partition.

```bash
dd if=/dev/sda2 bs=16065 | hexdump -C | grep 'text_to_search'
```

### 37. Reading BIOS
Read the BIOS contents.

```bash
dd if=/dev/mem bs=1k skip=768 count=256 2>/dev/null | strings -n 8
```

### 38. Converting Nero Image to ISO
Convert a Nero image to a standard ISO image.

```bash
dd bs=1k if=imagefile.nrg of=imagefile.iso skip=300k
```

### 39. Determining I/O Speed
Measure the I/O speed of a drive by reading 1GB of data.

```bash
dd if=/dev/sda of=/dev/null bs=1024k count=1024
```

### 40. Generating a Random Number
Generate a random number.

```bash
dd if=/dev/random count=1 2>/dev/null

 | od -t u1 | awk '{ print $2}' | head -1
```

### 41. Restoring MBR Without Partition Table
Restore the MBR without disturbing the partition table.

```bash
dd if=/my/old/mbr of=/dev/sda bs=446 count=1
```

### 42. Examining Memory Contents
Examine memory contents for human-readable strings.

```bash
dd if=/dev/mem | strings | grep 'string_to_search'
```

### 43. Converting ASCII to EBCDIC
Convert a text file from ASCII to EBCDIC.

```bash
dd if=text.ascii of=text.ebcdic conv=ebcdic
```

### 44. Converting a File to Uppercase
Convert the contents of a file to uppercase.

```bash
dd if=myfile of=myfile conv=ucase
```

---
