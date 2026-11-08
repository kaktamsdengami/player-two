# PLAYER TWO jury site: FastAPI + the built dashboard + the browser Doom build. Add the WAD at run
# time (data/freedoom1.wad is BSD-licensed Freedoom; mount or COPY it) and HAI_API_KEY in the env.
FROM node:20-slim AS web
WORKDIR /w
COPY web/package*.json ./
RUN npm ci --silent
COPY web ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project
COPY . .
COPY --from=web /w/dist ./web/dist
RUN .venv/bin/pip install playwright && .venv/bin/playwright install --with-deps chromium || echo "no headless broadcaster"
ENV P2_LIVE_BROADCAST=1 PORT=8000
EXPOSE 8000
CMD [".venv/bin/python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
