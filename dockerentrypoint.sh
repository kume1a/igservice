#!/bin/sh

echo "172.17.0.1 host.docker.internal" >> /etc/hosts

exec make run