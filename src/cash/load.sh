#!/bin/bash

set -e
set -x

test ! -e russ.db.new || rm -iv russ.db.new
sqlite3 russ.db.new < russ.db.sql
