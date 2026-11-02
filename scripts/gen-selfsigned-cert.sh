#!/usr/bin/env bash
# Generate a self-signed certificate for internal testing ONLY.
# Production must use a certificate from a trusted CA (e.g. Let's Encrypt or the corporate CA):
# LINE's in-app browser and mobile devices will refuse self-signed certificates.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST="${1:-localhost}"
mkdir -p deploy/certs
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout deploy/certs/privkey.pem -out deploy/certs/fullchain.pem \
  -subj "/CN=${HOST}" -addext "subjectAltName=DNS:${HOST},DNS:localhost,IP:127.0.0.1"
chmod 600 deploy/certs/privkey.pem
echo "self-signed certificate written to deploy/certs/ for ${HOST}"
