#!/bin/bash

apt update; apt upgrade -y -qq
apt install -y wget
/sbin/shutdown -h now