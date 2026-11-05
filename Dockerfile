# Two stages: the first carries the compilers asyncpg and argon2 need, the
# second carries only the installed environment and the source. The same
# image serves the API and the mock ERP; the mock ERP overrides CMD.
FROM python:3.14-alpine AS builder
WORKDIR /app
RUN python -m pip install --no-cache-dir --upgrade pip pdm \
 && apk add --no-cache build-base linux-headers libffi-dev
COPY pyproject.toml pdm.lock ./
RUN pdm install --prod --no-editable --no-self

FROM python:3.14-alpine AS runtime
WORKDIR /app
RUN addgroup -S app && adduser -S -G app app \
 && apk add --no-cache libffi
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app pyproject.toml alembic.ini startup.sh ./
COPY --chown=app:app src ./src
COPY --chown=app:app migrations ./migrations
RUN chmod +x startup.sh
USER app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# The platform assigns the port at runtime; 8000 is only the default.
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}{os.environ.get(\"HEALTH_PATH\",\"/api/health/\")}').status==200 else 1)"

# ENTRYPOINT carries the script so an orchestrator can pass just the role as
# args ("api", "mock-erp", "migrate", "seed") without repeating the path.
ENTRYPOINT ["./startup.sh"]
CMD ["api"]

# `--target tools`: the runtime plus the seed scripts and the synthetic
# workbook, for a one-off migrate + seed job in an environment where the
# database is not reachable from a laptop. Never the image that serves.
FROM runtime AS tools
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app seed ./seed
