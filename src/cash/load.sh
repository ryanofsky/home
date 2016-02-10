#!/bin/bash

set -e
set -x

rm -iv russ.db.new
sqlite3 russ.db.new < russ.db.sql
