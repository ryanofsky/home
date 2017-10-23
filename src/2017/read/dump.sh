#!/bin/sh

echo .dump | sqlite3 "file:$PWD/db.sqlite3?mode=ro" > db.sqlite3.sql
