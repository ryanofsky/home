#!/bin/bash

export CHROME_REMOTE_DESKTOP_LOG_FILE=/var/log/chrome-remote-desktop.$USER.log
if [ ! -f $CHROME_REMOTE_DESKTOP_LOG_FILE ]; then
  sudo touch       $CHROME_REMOTE_DESKTOP_LOG_FILE
  sudo chmod 0600  $CHROME_REMOTE_DESKTOP_LOG_FILE
  sudo chown $USER $CHROME_REMOTE_DESKTOP_LOG_FILE
fi
exec /opt/google/chrome-remote-desktop/chrome-remote-desktop -s 1200x600 -f --start
