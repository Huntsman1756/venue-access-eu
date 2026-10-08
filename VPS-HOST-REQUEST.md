# VPS-HOST-REQUEST.md — venues.h1756.es deployment

## Autor
Generado automáticamente desde sesión Hermes Qwen 3.6, 2026-10-08.
HEAD fuente: `ba108e0` (VPS-SOURCE-PROVENANCE.json: ba108e0b1ebb2745a50bf8e42054995a0c3bd425, 132 archivos).

## Qué pedir al coordinador
Construir las imágenes Docker del proyecto `venue-access-eu` en el host y arrancar el stack en el VPS. **No se piden cambios de red, TLS ni firewall**: Traefik (Coolify) y el wildcard `*.h1756.es` ya están configurados. Solo contenedores en la red `coolify` con labels Traefik.

---

## 1. Verificar que el directorio existe

```bash
sudo ls -la /opt/hermes/data/dev/venue-access-eu/
```

Debe devolver los ~132 archivos del repositorio (Dockerfile, docker-compose.yml, deploy/, backend/, frontend/...).
Si no existe, clonar el repo desde GitHub:

```bash
sudo -u hermes git clone https://github.com/Huntsman1756/venue-access-eu /opt/hermes/data/dev/venue-access-eu
```

---

## 2. Construir las imágenes Docker (host)

En `/opt/hermes/data/dev/venue-access-eu`:

```bash
cd /opt/hermes/data/dev/venue-access-eu

# Obtener tag corto del commit
TAG=$(git rev-parse --short=12 HEAD)

# Construir API (FastAPI + dataset sintético embebido)
docker build --target api \
  --build-arg DEMO_SEED=1756 \
  -t "venue-access-api:${TAG}" .

# Construir web (Next.js standalone)
docker build --target web \
  --build-arg NEXT_PUBLIC_API_URL=/api/v1 \
  --build-arg NEXT_PUBLIC_SITE_URL=https://venues.h1756.es \
  -t "venue-access-web:${TAG}" .
```

**Expectativa**: api ~414 MB, web ~210 MB.

**Verificar que se crearon**:
```bash
docker images venue-access-api
docker images venue-access-web
```

---

## 3. Desplegar con compose (en red Coolify + Traefik)

Copiar el compose al VPS:

```bash
# En el host
sudo mkdir -p /opt/data/venue-access
sudo tee /opt/data/venue-access/compose.yml > /dev/null <<'EOF'
# venues.h1756.es — Coolify network + Traefik labels, no published ports.
x-logging: &logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"

services:
  venues-api:
    image: venue-access-api:${VENUE_ACCESS_TAG:?set VENUE_ACCESS_TAG}
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=64m
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    expose: ["8000"]
    networks: [coolify]
    mem_limit: 384m
    cpus: "0.5"
    logging: *logging
    labels:
      - traefik.enable=true
      - traefik.docker.network=coolify
      - traefik.http.routers.venues-api.rule=Host(`venues.h1756.es`) && PathPrefix(`/api/`)
      - traefik.http.routers.venues-api.entrypoints=https
      - traefik.http.routers.venues-api.tls=true
      - traefik.http.routers.venues-api.tls.certresolver=letsencrypt
      - traefik.http.routers.venues-api.priority=100
      - traefik.http.routers.venues-api.middlewares=venues-headers
      - traefik.http.routers.venues-api.service=venues-api
      - traefik.http.services.venues-api.loadbalancer.server.port=8000

  venues-web:
    image: venue-access-web:${VENUE_ACCESS_TAG:?set VENUE_ACCESS_TAG}
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=64m
      - /app/.next/cache:size=128m,uid=1000,gid=1000
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    expose: ["3000"]
    networks: [coolify]
    mem_limit: 384m
    cpus: "0.5"
    logging: *logging
    depends_on:
      venues-api:
        condition: service_healthy
    labels:
      - traefik.enable=true
      - traefik.docker.network=coolify
      - traefik.http.routers.venues-web.rule=Host(`venues.h1756.es`)
      - traefik.http.routers.venues-web.entrypoints=https
      - traefik.http.routers.venues-web.tls=true
      - traefik.http.routers.venues-web.tls.certresolver=letsencrypt
      - traefik.http.routers.venues-web.middlewares=venues-headers
      - traefik.http.routers.venues-web.service=venues-web
      - traefik.http.services.venues-web.loadbalancer.server.port=3000
      - traefik.http.routers.venues-http.rule=Host(`venues.h1756.es`)
      - traefik.http.routers.venues-http.entrypoints=http
      - traefik.http.routers.venues-http.middlewares=venues-redirect
      - traefik.http.middlewares.venues-redirect.redirectscheme.scheme=https
      - traefik.http.middlewares.venues-redirect.redirectscheme.permanent=true
      - traefik.http.middlewares.venues-headers.headers.stsSeconds=31536000
      - traefik.http.middlewares.venues-headers.headers.contentTypeNosniff=true
      - traefik.http.middlewares.venues-headers.headers.frameDeny=true
      - traefik.http.middlewares.venues-headers.headers.referrerPolicy=strict-origin-when-cross-origin

networks:
  coolify:
    external: true
EOF
echo "VENUE_ACCESS_TAG=$(git -C /opt/hermes/data/dev/venue-access-eu rev-parse --short=12 HEAD)" | sudo tee /opt/data/venue-access/.env > /dev/null
```

Arrancar el stack:

```bash
cd /opt/data/venue-access
sudo docker compose -p venue-access up -d --wait
```

**Esperar a que los healthchecks pasen** (`--wait` lo hace por defecto, pero verificar):

```bash
sudo docker compose -p venue-access ps
```

Ambos servicios deben estar `healthy` / `running`.

---

## 4. Verificar salud del despliegue

```bash
# Healthcheck API
sudo docker exec venue-access-venues-api-1 curl -fsS http://127.0.0.1:8000/api/v1/ready

# Meta API (debe devolver dataset_mode: demo)
sudo docker exec venue-access-venues-api-1 curl -fsS http://127.0.0.1:8000/api/v1/meta

# Healthcheck Web
sudo docker exec venue-access-venues-web-1 curl -fsS http://127.0.0.1:3000/

# Desde fuera (o localhost del host)
curl -fsS -o /dev/null -w "web %{{http_code}}\n" https://venues.h1756.es/
curl -fsS -o /dev/null -w "about %{{http_code}}\n" https://venues.h1756.es/about
curl -fsS https://venues.h1756.es/api/v1/ready
curl -fsS https://venues.h1756.es/api/v1/meta | grep '"dataset_mode":"demo"'
curl -sS -o /dev/null -w "http->https %{{http_code}} %{{redirect_url}}\n" http://venues.h1756.es/
```

**Verificar que no hay nada previo reclamando el dominio**:
```bash
sudo docker ps --format '{{.Names}} {{.Labels}}' | grep venues.h1756.es
```

---

## 5. Verificar memoria y CPU en tiempo real

```bash
sudo docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' \
  venue-access-venues-api-1 venue-access-venues-web-1
```

Esperado: api ~72 MiB, web ~59 MiB en reposo. Límites máximos 384 MiB c/u + 0.5 CPU.

---

## 6. Verificar que no se publican puertos

```bash
sudo docker port venue-access-venues-api-1  # debe estar vacío
sudo docker port venue-access-venues-web-1  # debe estar vacío
```

Los puertos 8000 y 3000 solo están expuestos dentro de la red `coolify` (expose, no ports).

---

## 7. Verificar que las imágenes tienen el dataset sintético

```bash
sudo docker exec venue-access-venues-api-1 ls -la /dataset/
sudo docker exec venue-access-venues-api-1 grep '"dataset_mode":"demo"' <(curl -s http://127.0.0.1:8000/api/v1/meta)
```

---

## 8. Verificar usuarios no-root y filesystem readonly

```bash
sudo docker inspect --format='{{.Config.User}}' venue-access-venues-api-1
sudo docker inspect --format='{{.Config.User}}' venue-access-venues-web-1
# Debe devolver 10001 para api, node para web
```

---

## Rollback

```bash
# Listar imágenes disponibles
sudo docker images venue-access-api

# Detener stack actual
sudo docker compose -p venue-access down

# Cambiar TAG en .env
echo "VENUE_ACCESS_TAG=<anterior-sha>" | sudo tee /opt/data/venue-access/.env > /dev/null

# Arrancar con imagen anterior
cd /opt/data/venue-access && sudo docker compose -p venue-access up -d --wait

# Verificar
sudo docker compose -p venue-access ps
curl -fsS https://venues.h1756.es/api/v1/ready

# Eliminar imagen anterior (solo tras verificar nueva)
sudo docker image rm venue-access-api:<nuevo-sha>  # solo tras rollback verificado
```

---

## Notas

- **Dataset**: sintético (demo mode, seed 1756). No hay volumen, no hay nada que backuppear.
- **No instalar Pi**: el VPS ya tiene Coolify; no se necesita Pi/Gentle Shell para esto.
- **No cambiar visibilidad GitHub**: el repo ya es público, no tocar.
- **No alterar contenedores vecinos**: Coolify y sus servicios deben seguir intactos.
- **RAM total del VPS**: 8 GB compartida. Worst-case del stack: 768 MB (384×2).
- **No modificar DNS ni firewall**: Traefik wildcard `*.h1756.es` y TLS ya están configurados.