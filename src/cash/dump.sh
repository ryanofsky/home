#!/bin/bash

set -e
set -x

sqlite3 russ.db <<< ".dump" > russ.db.sql
