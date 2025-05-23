#!/bin/bash

export ADDON_NAME="borg-backup"
export GITHUB_URL="https://github.com/bmanojlovic/home-assistant-borg-backup/"
export AUTHOR="Boris Manojlovic <boris@steki.net>"

sudo podman run --rm --privileged \
	-v ~/.docker:/root/.docker \
	ghcr.io/home-assistant/amd64-builder:latest --all -t borg-backup \
	-r https://github.com/bmanojlovic/home-assistant-addons -b master \
	--docker-hub "ghcr.io/bmanojlovic"

