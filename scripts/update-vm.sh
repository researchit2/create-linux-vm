#!/bin/bash

apt update; apt upgrade -y -qq
apt install wget -y -qq
/sbin/shutdown -h now