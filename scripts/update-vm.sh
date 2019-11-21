#!/bin/bash

apt update; apt upgrade -y -qq
apt install -y wget
/sbin/reboot