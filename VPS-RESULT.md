# VPS-RESULT.md — venues.h1756.es deployment

## Estado: FUENTE VERIFICADA, DESCRIPTOR DE DESPLIEGUE PREPARADO, PENDIENTE EJECUCIÓN EN HOST

Generado: 2026-10-08 por Hermes Qwen 3.6 (custom)
Referencia: https://venues.h1756.es (síntesis, demo mode)
Source head original: `ba108e0b1ebb2745a50bf8e42054995a0c3bd425`

---

## Cambios realizados en esta sesión

### 1. Verificaciones backend ejecutadas con éxito

| Check | Resultado |
|---|---|
| `pytest tests/ -q` (offline, -m 'not live') | 102 passed, 0 failed, 5 deselected |
| `ruff check venue_access` | All checks passed! |
| `ruff format --check venue_access` | 34 files already formatted |
| `mypy venue_access` (strict) | Success: no issues found in 34 source files |

Total de archivos de código: 132 (incluye tests, fixtures, docs, ADRs, frontend).

### 2. Repo de release creado

- `git init -b release` en `/opt/data/dev/venue-access-eu/`
- 134 archivos staged (132 code + 2 de meta)
- Commit `b5ff43c`: "release: venue-access-eu synthetic demo — source verified"
- Provenance del HEAD original preservada en `VPS-SOURCE-PROVENANCE.json`
- Repo es snapshot de release, no es upstream. No se cambia visibilidad de GitHub.

### 3. VPS-HOST-REQUEST.md creado

Documento completo en `/opt/data/dev/venue-access-eu/VPS-HOST-REQUEST.md` con:
- Pasos 1-8: verificación del directorio, construcción de imágenes, despliegue compose, verificación de salud, memoria/CPU, puertos, dataset, usuarios no-root
- Rollback: procedimiento detallado
- Notas: no instalar Pi, no cambiar DNS/firewall, no alterar contenedores vecinos, presupuesto 768 MB worst-case

---

## Qué falta hacer en el HOST (VPS-HOST-REQUEST.md)

El host del VPS tiene Docker, Coolify, red `coolify` y Traefik configurados.
Este contenedor NO tiene acceso al Docker socket (`/var/run/docker.sock` no funciona).

**Pasos que debe ejecutar el coordinador desde el host del VPS (SSH):**

1. Verificar `/opt/hermes/data/dev/venue-access-eu/` existe y tiene los archivos.
2. `docker build --target api -t venue-access-api:<sha> .` (api ~414 MB)
3. `docker build --target web -t venue-access-web:<sha> .` (web ~210 MB)
4. Desplegar compose desde `/opt/data/venue-access/compose.yml` en red `coolify`
5. `sudo docker compose -p venue-access up -d --wait`
6. Verificar healthchecks: `sudo docker compose -p venue-access ps` → ambos healthy
7. Verificar externamente: `curl -fsS https://venues.h1756.es/api/v1/ready` y web
8. Verificar `dataset_mode: demo` en `/api/v1/meta`
9. Verificar no hay puertos publicados: `sudo docker port` debe estar vacío

Todos los comandos exactos están en VPS-HOST-REQUEST.md con validaciones y rollback incluido.

---

## Verificaciones pendientes (requieren ejecución en host)

| Check | Estado |
|---|---|
| Docker images built on host | PENDIENTE — no hay docker.sock |
| Compose stack deployed on VPS | PENDIENTE |
| HTTPS healthcheck `venues.h1756.es` | PENDIENTE (desde outside container) |
| Memory/CPU in `docker stats` | PENDIENTE |
| No published ports (docker port) | PENDIENTE |
| Read-only FS + non-root user | PENDIENTE |
| No previous venues containers | PENDIENTE |

---

## Lo que ya está listo (sin ejecución en host)

- [x] Código fuente completo (132 archivos, 132 staged)
- [x] 102 tests passing (backend)
- [x] ruff check + format: limpio
- [x] mypy strict: limpio
- [x] Dockerfile con targets api + web, non-root, read-only, healthchecks
- [x] docker-compose.yml (local dev) con Caddy, ports 80/443
- [x] deploy/compose.vps.yaml (Coolify + Traefik, sin ports, labels correctos)
- [x] deploy/release.sh (build, ship, up, verify, rollback)
- [x] deploy/README.md (budget, rollback, instructions)
- [x] frontend Next.js 16, standalone, Tailwind CSS 4, React 19
- [x] dataset sintético: demo.py, 120 empresas, 12 semanas, seed 1756
- [x] portada / about / mobile / 404 / search / firms / venues / changes / sources / methodology
- [x] linkedin/firm id reparados (link to firm view by id)
- [x] fechas snapshot deterministas (retrieved_at, no wall clock)
- [x] DuckDB rápido (transactions, arrow, no pandas)
- [x] 689 membresías actuales en demo
- [x] CODE_PUBLISHABLE_DATASET_INTERNAL_ONLY respetado (solo demo)
- [x] imagen Docker con dataset baked-in, sin volumen, sin datos reales
- [x] release git commit con provenance ba108e0 → b5ff43c

---

## Cómo continuar

El coordinador debe ejecutar los pasos de VPS-HOST-REQUEST.md desde el host del VPS.
Una vez desplegado:
- Verificar HTTPS: `curl -fsS https://venues.h1756.es/` debe devolver 200
- Verificar API: `curl -fsS https://venues.h1756.es/api/v1/ready` debe devolver OK
- Verificar meta: `curl -fsS https://venues.h1756.es/api/v1/meta | grep demo`
- Verificar redirect HTTP→HTTPS
- Verificar `docker stats` sin exceder 384 MB por contenedor

Tras la verificación, se puede cerrar este encargo. El siguiente puede asumir que el despliegue es correcto y trabajar sobre él (mejoras frontend, nuevos endpoints, etc.).