#!/usr/bin/env bash

PROJECT=$(basename $(pwd))
# TODO fix
PROJECT=dirtypipe

gdb \
-q \
-x lkd_gdb_${PROJECT}.py
