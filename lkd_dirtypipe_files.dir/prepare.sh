#!/usr/bin/env bash

gcc -o poc poc.c && chmod 777 poc && \
echo "File owned by root!" > target_file && \
chmod 444 target_file || exit 1

exit 0
