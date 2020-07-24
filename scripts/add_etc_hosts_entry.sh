#!/bin/bash


if [ $(cat /etc/hosts | grep "registry.local" | wc -l) -eq 0 ] ; then
  echo "127.0.0.1	registry.local" >> /etc/hosts 
fi