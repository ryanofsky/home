#! /bin/bash
#
# https://www.privateinternetaccess.com/forum/discussion/3359/port-forwarding-without-application-pia-script-advanced-users
#
# Enable port forwarding
#
# Requirements:
#   your Private Internet Access user and password as arguments
#
# Usage:
#  ./port_forward.sh <user> <password>

error( )
{
  echo "$@" 1>&2
  exit 1
}

error_and_usage( )
{
  echo "$@" 1>&2
  usage_and_exit 1
}

usage( )
{
  echo "Usage: `dirname $0`/$PROGRAM <user> <password>"
}

usage_and_exit( )
{
  usage
  exit $1
}

version( )
{
  echo "$PROGRAM version $VERSION"
}


port_forward_assignment( )
{
  echo 'Loading port forward assignment information..'
  if [ "$(uname)" == "Linux" ]; then
    local_ip=`ifconfig tun0 | grep "inet " | sed 's/ \+/\t/g' | cut -f3`
    client_id=`head -n 100 /dev/urandom | md5sum | tr -d " -"`
  fi
  if [ "$(uname)" == "Darwin" ]; then
    local_ip=`ifconfig tun0 | grep "inet " | cut -d\  -f2|tee /tmp/vpn_ip`
    client_id=`head -n 100 /dev/urandom | md5 -r | tr -d " -"`
  fi
  wget -q --post-data="user=$USER&pass=$PASSWORD&client_id=$client_id&local_ip=$local_ip" -O - 'https://www.privateinternetaccess.com/vpninfo/port_forward_assignment'
}

EXITCODE=0
PROGRAM=`basename $0`
VERSION=1.0
USER='XXX'
PASSWORD='XXX'

port_forward_assignment

exit 0
