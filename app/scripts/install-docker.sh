#!/usr/bin/env bash
set -euo pipefail
if command -v docker &>/dev/null; then
    echo "Command: 'docker' exists. Exiting safely"
    exit 0
else
    install_docker
install_docker() {
    echo "[+] Installing Docker Engine + Compose plugin (official repo)..."

    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y

    # Install engine + compose plugin
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Enable service
    sudo systemctl enable --now docker

    # Add current user to docker group (requires logout/login to take effect)
    if ! getent group docker >/dev/null; then
    sudo groupadd docker || true
    fi

    sudo usermod -aG docker "$USER" || true
    sudo newgrp docker
    echo "[+] Docker installed."
    docker version
    docker compose version
    echo "[!] Note: re-login (or run: newgrp docker) to use docker without sudo."
    echo "[?] Testing..."
    docker run -t hello-world
}