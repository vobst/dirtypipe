#!/usr/bin/env bash

useradd user && \
cp Makefile /home/user && chown user:user /home/user/Makefile && \
cp poc.c /home/user && chown user:user /home/user/poc.c && \
echo "File owned by root!" > /home/user/target_file && \
cd /home/user && su user && make all && chmod 777 poc || exit 1

exit 0
