# Linux Kernel Debugging - 'dirtypipe' edition

This is the kernel debugging setup used in our [blogpost](https://lolcads.github.io/posts/2022/06/dirty_pipe_cve_2022_0847/) on the dirtypipe vulnerability. The setup was adapted from [here](https://github.com/martinclauss/linux-kernel-debugging).

## Quick Start

Check the [requirements](#requirements) and see the [example](#example) session!

## Design Decisions

### Terminology

- **host**: Probably the machine you are sitting in front of!
- **container**: A Docker container, that we use for `pwndbg` (`gdb`). It is not essential to use Docker but it keeps the host system cleaner.
- **virtual machine**: This is what QEMU provides us, and we use it to run the Linux kernel with a Debian root filesystem.

### QEMU

QEMU allows us to run the Linux kernel inside a virtualized / emulated environment so that it can be stopped and continued as we want. Currently it is not possible (at least to for me) to enable KVM because single stepping will be disturbed by certain interrupts (see https://lkml.kernel.org/lkml/20210315221020.661693-3-mlevitsk@redhat.com/). So we have to stick with full emulation until this gets "fixed". Unfortunately, this makes the execution of the virtual machine slower. You can try it yourself by adding `-enable-kvm` as a command line argument to `qemu-system-x86_64` in `lkd_run_qemu.sh` and start debugging with `lkd_debug.sh`. Watch the behavior during single stepping.

We also use `-smp 1` to only have a single virtual CPU.

### Debian

Since we are only interested in debugging the (vanilla) Linux kernel it does not really matter what distribution (files, services, utils, ...) we use. Debian is a good choice and it is also very easy to create a root filesystem with `debootstrap`. So we use a vanilla Linux kernel with the Debian filesystem.

### pwndbg

`pwndbg` is a very nice overlay / extension to `gdb` that eases the debugging process a lot with nice visualizations and handy functions.

### Docker

For debugging we use `pwndbg` but also install `pwntools` for convenience. Since I do not want to clutter my host system too much I like to use containers. This is the only reason I use Docker here. You could also just run the debugger on your host by ignoring the `lkd_debug.sh` script and use `lkd_gdb.sh` directly.

## Files

The files (except `README.md`) are all prefixed with `lkd` (Linux Kernel Debugging) so that you can see more easily which files belong to the Linux kernel and which not once the kernel is cloned to the same directory.

Overview of the interesting files. In parenthesis you see where it is used in the default setup:

- `lkd_Dockerfile` (host)
    - a Dockerfile that sets up a container with `pwndbg` and `pwntools` for more convenient debugging (Arch Linux based)

- `lkd_build_kernel.sh` (host)
    - makes the necessary kernel configurations for a kernel that is able to be debugged
    - builds the kernel

- `lkd_create_root_fs.sh` (host)
    - creates a 5GB QCOW2 disk image and installs a root filesystem in it (necessary tools and files)
    - also changes the password for `root` to `test`
    - some other settings

- `lkd_debug.sh` (host)
    - starts the Docker image (with some bind mounts, user permission settings, capabilities to allow debugging, e.g. SYS_PTRACE, ...)

- `lkd_docker_create_user.sh` (container)
    - runs inside the Docker container and creates a `dbg` user (and group) with password `test`
    - you might want to change the `YOUR_HOST_UID` and `YOUR_HOST_GID` according to your `id -u` and `id -g` output on your host system

- `lkd_gdb.sh` (container)
    - actually run gdb with some initial commands (attach, set correct architecture, ...)

- `lkd_gdbinit` (container)
    - custom `.gdbinit` that will be available inside the Docker container and sets some default values (and also loads `pwndbg`)

- `lkd_init.sh` (host)
    - clones the recent kernel into to current directory (next to the `lkd_*` files)
    - executes other scripts to
      - build the kernel
        - this takes a while... ☕
      - create the root filesystem
        - **Note**: this step uses `sudo` so don't miss the chance to enter your password, otherwise there will be a timeout!
    - builds the Docker image (`lkd_Dockerfile`)
    
- `lkd_kill_qemu.sh` (host)
    - kills `qemu-system-x86_64` process if something goes wrong / hangs

- `lkd_run_qemu.sh` (host)
    - starts QEMU with the appropriate command line arguments
    - if you provide the `debug` argument QEMU starts in debugging mode and waits until a debugger is attached (before the kernel starts)
        - `./lkd_run_qemu.sh` -> QEMU runs *without* gdb support enabled
        - `./lkd_run_qemu.sh debug` -> QEMU runs *with* gdb support enabled

- `lkd_dirtypipe_files.dir/poc.c` (virtual machine)
	- minimal proof-of-concept (POC) program for illustrating the 'dirtypipe' vulnerability

- `lkd_dirtypipe_files.dir/prepare.sh` (virtual machine)
	- creates an unprivileged user
	- creates the targeted file
	- switches to user and compiles the POC

## Requirements

### Arch Linux

```
# get system up-to-date
$ sudo pacman -Syu

# install all requirements
$ sudo pacman -S rsync git qemu debootstrap base-devel docker bc wget

# start docker service
$ sudo systemctl start docker

# you might want to add your user to the docker group
$ sudo usermod -aG docker $USER
```

### Fedora

Note: Red Hat also develops `podman` which should also be fine (`sudo dnf update && sudo dnf install podman podman-docker`).

```
# get system up-to-date
$ sudo dnf update

# install Docker according to https://docs.docker.com/engine/install/fedora/
$ sudo dnf install dnf-plugins-core
$ sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
$ sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# install compilers and development tools
$ sudo dnf groupinstall "Development Tools"

# install the rest of the requirements
$ sudo dnf install rsync git qemu-system-x86 qemu-img debootstrap bc openssl iproute wget

# start docker service
$ sudo systemctl start docker

# you might want to add your user to the docker group
$ sudo usermod -aG docker $USER
```

### Ubuntu

```
# get system up-to-date
$ sudo apt-get update && sudo apt-get upgrade

# install Docker according to https://docs.docker.com/engine/install/ubuntu/
$ sudo apt-get install ca-certificates curl gnupg lsb-release
$ curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
$ echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
$ sudo apt-get update
$ sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# install the rest of the requirements (compilers, build tools, qemu, ...)
$ sudo apt-get install build-essential rsync git qemu-system-x86 debootstrap bc openssl libncurses-dev gawk flex bison libssl-dev dkms libelf-dev libudev-dev libpci-dev libiberty-dev autoconf wget

# start docker service
$ sudo systemctl start docker

# you might want to add your user to the docker group
$ sudo usermod -aG docker $USER
```

If you are using any other distribution you need to install the equivalent packages. Open a Pull Request if you want to contribute installation instructions for other distributions ;)

## Example

In one terminal window run:

```
$ git clone https://github.com/vobst/dirtypipe
$ cd dirtypipe
```

Edit the variables in `ldk_init.sh`, `lkd_Dockerfile` and `lkd_create_root_fs.sh` to match your setup. Then run:

```
$ ./lkd_init.sh
$ ./lkd_run_qemu.sh debug
```

Sign in as user `root` with password `test`. (Alternatively, run 
QEMU detached and connect via `$ ssh lkd_qemu`). In the guest run:

```
# ./prepare.sh
$ ./poc
```

In *another* terminal window run:

```
$ ./lkd_debug.sh
$ ./lkd_gdb.sh
```

You should now see a `pwndbg` session that waits to hit its first breakpoint.

Back in the first window press any key to step through the different stages of the POC and observe the output in the other window.


## Contributions

Just open a PR and I'll see what I can do :)
