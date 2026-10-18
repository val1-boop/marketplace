#!/usr/bin/env sh
# Exige IMDSv2 (tokens) en la instancia: mitiga SSRF contra el servicio de metadatos.
# Uso: sh ec2-imdsv2.sh i-0123456789abcdef0
set -eu
aws ec2 modify-instance-metadata-options \
  --instance-id "$1" \
  --http-tokens required \
  --http-put-response-hop-limit 1 \
  --http-endpoint enabled
