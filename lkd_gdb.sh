#!/usr/bin/env bash

PROJECT=$(basename $(pwd))

gdb \
-q \
-x lkd_gdb_${PROJECT}.py
