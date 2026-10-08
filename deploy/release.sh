#!/usr/bin/env bash
# Build, ship and start venues.h1756.es on the H1756 VPS.
#
#   deploy/release.sh build             # build + smoke-test images locally
#   deploy/release.sh ship              # docker save | ssh docker load, upload compose
#   deploy/release.sh up                # start/replace the stack on the VPS
#   deploy/release.sh verify            # external HTTPS checks
#   deploy/release.sh rollback <tag>    # restart the stack on a previous tag
#
# Tag = short git SHA of a clean tree, so every running image maps to a commit.
set -euo pipefail

HOST="${VPS_HOST:-h1756-vps1}"
REMOTE_DIR="/data/venue-access"
DOMAIN="venues.h1756.es"
cd "$(dirname "$0")/.."

tag() {
  if [ -n "$(git status --porcelain)" ]; then
    echo "refusing: working tree is not clean (images must map to a commit)" >&2
    exit 1
  fi
  git rev-parse --short=12 HEAD
}

build() {
  local t; t="$(tag)"
  docker build --target api -t "venue-access-api:$t" .
  docker build --target web -t "venue-access-web:$t" .
  # smoke: the api must be ready with the baked dataset and report demo mode
  local cid; cid="$(docker run -d --rm -p 127.0.0.1:18080:8000 "venue-access-api:$t")"
  trap 'docker stop "$cid" >/dev/null 2>&1 || true' RETURN
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:18080/api/v1/ready >/dev/null 2>&1 && break
    sleep 1
  done
  curl -fsS http://127.0.0.1:18080/api/v1/meta | grep -q '"dataset_mode":"demo"'
  echo "built and smoke-tested tag $t"
}

ship() {
  local t; t="$(tag)"
  docker save "venue-access-api:$t" "venue-access-web:$t" | gzip | ssh "$HOST" 'gunzip | sudo docker load'
  ssh "$HOST" "sudo mkdir -p $REMOTE_DIR"
  scp deploy/compose.vps.yaml "$HOST:/tmp/venue-access-compose.yml"
  ssh "$HOST" "sudo mv /tmp/venue-access-compose.yml $REMOTE_DIR/compose.yml"
  echo "shipped $t"
}

up() {
  local t="${1:-$(tag)}"
  ssh "$HOST" "cd $REMOTE_DIR && echo VENUE_ACCESS_TAG=$t | sudo tee .env >/dev/null \
    && sudo docker compose -p venue-access up -d --wait && sudo docker compose -p venue-access ps"
}

verify() {
  local base="https://$DOMAIN"
  curl -fsS -o /dev/null -w "web   %{http_code}\n" "$base/"
  curl -fsS -o /dev/null -w "about %{http_code}\n" "$base/about"
  curl -fsS "$base/api/v1/ready"; echo
  curl -fsS "$base/api/v1/meta" | grep -q '"dataset_mode":"demo"' && echo "dataset_mode demo"
  curl -sS -o /dev/null -w "http->https %{http_code} %{redirect_url}\n" "http://$DOMAIN/"
}

case "${1:-}" in
  build) build ;;
  ship) ship ;;
  up) up ;;
  verify) verify ;;
  rollback) [ -n "${2:-}" ] || { echo "usage: $0 rollback <tag>" >&2; exit 2; }; up "$2" ;;
  *) sed -n '2,10p' "$0"; exit 2 ;;
esac
