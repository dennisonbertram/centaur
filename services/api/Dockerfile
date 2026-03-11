FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl \
    ripgrep fd-find jq yq tree gettext-base \
    && ln -sf /usr/bin/fdfind /usr/local/bin/fd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# 1. Install core dependencies from pyproject metadata.
COPY services/api/pyproject.toml ./
COPY centaur_sdk/ centaur_sdk/
# Fix centaur-sdk path for Docker layout (repo root = /app, not ../../)
RUN sed -i 's|path = "../../centaur_sdk"|path = "centaur_sdk"|' pyproject.toml \
    && rm -f uv.lock
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# 2. Install project with source
COPY services/api/api/ api/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# 3. Install tool dependencies via bind mount
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=tools,target=/tmp/tools \
    python -c "\
import tomllib, pathlib; \
deps = set(); \
[deps.update(tomllib.load(open(p,'rb')).get('project',{}).get('dependencies',[])) \
 for p in pathlib.Path('/tmp/tools').glob('**/pyproject.toml')]; \
open('/tmp/pd.txt','w').write('\n'.join(sorted(deps)))" \
    && uv pip install -r /tmp/pd.txt --quiet \
    && rm /tmp/pd.txt

# 4. Copy tool source
COPY tools/ tools/

COPY services/api/bootstrap-secrets.sh /app/scripts/bootstrap-secrets.sh
COPY services/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/scripts/bootstrap-secrets.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/app/.venv/bin/uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
