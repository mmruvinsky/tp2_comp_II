#!/usr/bin/env bash
# Repite las mediciones del README. Se corre desde la raíz del repo:
#     bash mediciones/correr_todo.sh | tee mediciones/resultados.txt
set -euo pipefail

levantar() {  # WORKERS MODO_HASH
    WORKERS=$1 MODO_HASH=$2 docker compose up -d --force-recreate >/dev/null 2>&1
    until curl -sf http://127.0.0.1:8000/estadisticas >/dev/null; do sleep 0.2; done
}
medir() { docker compose exec -T api python "$@"; }

docker compose build >/dev/null 2>&1
echo "Fecha: $(date -Iseconds)  Núcleos: $(nproc)  CPU: $(lscpu | sed -n 's/^Model name: *//p')"

echo; echo "=== Medición 1: concurrencia I/O (WORKERS=10) ==="
levantar 10 proceso
medir mediciones/medir_io.py

echo; echo "=== Medición 2: event loop bloqueado ==="
for modo in bloqueante hilo proceso; do
    echo "MODO_HASH=$modo"
    levantar 10 "$modo"
    medir mediciones/medir_loop.py
done

echo; echo "=== Medición 3a: esperar(1 s), WORKERS=10 ==="
levantar 10 proceso
medir mediciones/medir_techo.py esperar 1 5 10 20 50 100

echo; echo "=== Medición 3b: hashear, WORKERS=64 ==="
levantar 64 proceso
medir mediciones/medir_techo.py hashear 1 2 4 6 8 12 16 24 48

echo; echo "=== Medición 3c: descargar, WORKERS=2000, LIMITE_CONEXIONES=100 ==="
levantar 2000 proceso
medir mediciones/medir_techo.py descargar 10 50 100 200 500 1000

echo; echo "=== Medición 3d: avalancha de esperar(1 s), WORKERS=10000 ==="
for cantidad in 1000 5000 10000; do
    levantar 10000 proceso
    medir mediciones/medir_techo.py avalancha "$cantidad"
done

echo; echo "=== Medición 3e: ¿el límite de POST/s es el cliente? Dos clientes a la vez ==="
levantar 10000 proceso
medir mediciones/medir_techo.py avalancha 5000 | head -1 &
medir mediciones/medir_techo.py avalancha 5000 | head -1 &
wait

echo; echo "=== Medición 3f: tareas de golpe con WORKERS=10 (la cola crece) ==="
for cantidad in 10000 100000; do
    levantar 10 proceso
    medir mediciones/medir_techo.py cola "$cantidad"
    inicio=$(date +%s.%N)
    docker compose stop >/dev/null 2>&1
    echo "  apagado: $(python3 -c "import time; print(round(time.time() - $inicio, 1))") s, exit=$(docker inspect -f '{{.State.ExitCode}}' "$(docker compose ps -aq api)")"
    docker compose logs --no-log-prefix | grep 'Estado volcado' | tail -1 | sed 's/^/  /'
done
ls -l datos/estado_*.json | tail -2 | awk '{print "  volcado:", $5, "bytes"}'
