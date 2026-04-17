---
title: Installing Libvirtd + Virt-Manager on EndeavorOS
summary: Quick guide to installing libvirtd, qemu, and Virt-Manager on EndeavorOS and other Arch linux based-distributions
tags: ["linux", "libvirtd", "kvm"]
published: true
---
# How to install and setup Libvirtd + Virt-Manager on EndeavorOS and other Arch-based distro's

## Firstly... Why EndeavorOS?

It does what I need it to do, nothing more, nothing less. I like arch and the rolling distribution architecture. EndeavorOS is essentially an Arch Linux wrapper with some pre-installed software and a GUI that makes installation a lot easier than manual installation. I've installed arch manually, partitioning each section of the disk manually and allocating memory, and I've used the `archinstall` script. Still, in the end, I'd rather have a similar distro I don't have to spend the better part of 1-4+ hours configuring my GUI alone and ricing other dumb shit nobody cares about myself included.

Truth be told, it can be a pain in the ass sometimes with different package conflicts you never even knew existed due to the lack of documentation but the arch wiki still applies here too. It works for me for the most part and it does **the thing**, when I need it to do **the thing** with **minimal interference or intervenience**. Therefore: 

$$
\text{...Good Nuff' for me.}
$$

### KVM

KVM stands for Kernel-based Virtual machines. A Linux full virtualization solution for `x86` architecture processors which has the virtualization extension (Intel VT and AMD-V).
- [Source](https://discovery.endeavouros.com/applications/how-to-install-virt-manager-complete-edition/2021/09/)

### Installing Virt-Manager

```bash
sudo pacman -Syu virt-manager qemu-desktop dnsmasq iptables-nft
```

For a full-featured install:

```bash
sudo pacman -Syu --needed virt-manager qemu-desktop libvirt edk2-ovmf dnsmasq vde2 bridge-utils iptables-nft dmidecode qemu-emulators-full
```

- `edk2-ovmf`: ovmf is an EDK II based project to enable EUFI support for virtual machines
- `iptables-nft`: Linux kernel packet control tool (using nft interface)
- `bridge-utils`

#### Enable the `libvirtd` service. 

```bash
sudo systemctl enable --now libvirtd.service
```

- Check the status to make sure it's running:

```bash
systemctl status libvirtd.service
```

## Network

If network is disabled after rebooting the host machine and you do not find a way to enable it, you can have it enabled per fedault from the command line. This will work after rebooting the host:

```bash
sudo virsh net-autostart default
```

#### libguestfs

If you wish to edit the created virtual machine disk images you can install [libguestfs](https://www.libguestfs.org). These are set of tools that allow the user to view and edit files inside guest systems, change VM script changes, monitor disk space, create new guests, P2V, V2V, perform backups, clone VMs, and much more.

To install.

```bash
sudo pacman -S libguestfs
```

#### qemu-block-gluster

Glusterfs is a scalable network filesystem. This adds Glusterfs block support to QEMU.

To install.

```bash
sudo pacman -S qemu-block-gluster
```
#### qemu-block-iscsi

iSCI enables storage access via a network. `qemu-block-iscsi` enables QEMU to block this.

To install.

```bash
sudo pacman -S qemu-block-iscsi
```

#### samba

This would add support to [SMB/CIFS](https://wiki.archlinux.org/title/Samba) support to QEMU.

To install.

```bash
sudo pacman -S samba
```
#### Installing virtio guest drivers for Windows

... **TO BE CONTINUED**

---