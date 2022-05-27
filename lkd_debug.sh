#!/usr/bin/env bash

docker run -it \
    --rm --cap-add=SYS_PTRACE \
    --security-opt seccomp=unconfined \
    -v $(pwd):/project:Z \
    -v $(pwd)/lkd_gdbinit:/home/dbg/.gdbinit:Z \
    --net host \
    --hostname "lkd-pwndbg-container" \
    --name lkd-pwndbg-container \
    lkd-dirtypipe
