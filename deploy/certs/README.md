Place the TLS certificate for your domain here (never commit real keys):

- `fullchain.pem` — certificate + intermediate chain
- `privkey.pem`   — private key (chmod 600)

For a quick internal test you can generate a self-signed certificate with
`scripts/gen-selfsigned-cert.sh <hostname>`. See docs/DEPLOYMENT.md for Let's Encrypt.
