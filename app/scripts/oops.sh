#!/bin/bash

# 1. Create the filename with a random hex suffix
RAND=$(openssl rand -hex 2)
FN="supasuge.com-${RAND}.tar.xz"

# 2. Navigate to the directory
cd /home/supasuge/Documents || exit

# 3. Create the compressed archive
# Added '|| exit' to stop the script if tar fails
tar -cJf "${FN}" supasuge.com || exit
echo "${FN} Created... Secure copying to server..."

KEY_PATH=~/.ssh/id_ed25519_blog_vps
REMOTE_USER="appuser"
REMOTE_HOST="supasuge.com"
REMOTE_DEST="~/"
scp -i "${KEY_PATH}" "${FN}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DEST}"

echo "Transfer complete."


