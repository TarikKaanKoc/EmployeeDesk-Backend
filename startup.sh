#!/bin/sh
# Container entrypoint. `exec` makes the server PID 1 so the orchestrator's
# SIGTERM reaches uvicorn and the pod drains instead of being killed.
#
#   ./startup.sh api       the EmployeeDesk API            (default)
#   ./startup.sh mock-erp  the mock ERP, a separate process and port
#   ./startup.sh migrate   alembic upgrade head, then exit (init job)
#   ./startup.sh seed      migrate, load the synthetic workbook, set the
#                          synthetic password; needs the `tools` image
set -eu

ROLE="${1:-api}"
PORT="${PORT:-8000}"
WORKERS="${WEB_CONCURRENCY:-1}"

case "$ROLE" in
  api)
    exec uvicorn src.app.main:app --host 0.0.0.0 --port "$PORT" \
      --workers "$WORKERS" --proxy-headers --forwarded-allow-ips '*' \
      --timeout-graceful-shutdown 20
    ;;
  mock-erp)
    exec uvicorn src.mock_erp.main:app --host 0.0.0.0 --port "$PORT" \
      --workers "$WORKERS" --timeout-graceful-shutdown 10
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  seed)
    alembic upgrade head
    python scripts/seed_data.py
    exec python scripts/create_employee.py --all "${SYNTHETIC_PASSWORD:-Synthetic-Pass-1}"
    ;;
  *)
    echo "unknown role: $ROLE (api | mock-erp | migrate | seed)" >&2
    exit 64
    ;;
esac
