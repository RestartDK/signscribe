# Stage 1: Build frontend
FROM oven/bun:1 AS frontend
WORKDIR /app/client
COPY client/package.json client/bun.lock ./
RUN bun install --frozen-lockfile
COPY client/ ./
RUN bun run build

# Stage 2: Python runtime with uv
FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files and install dependencies
COPY server/pyproject.toml server/uv.lock ./server/
RUN cd server && uv sync --frozen --no-dev

# Copy server code
COPY server/ ./server/

# Copy built frontend from stage 1
COPY --from=frontend /app/client/dist ./client/dist

# Expose port
EXPOSE 7860

# Run the server using uv
CMD ["uv", "run", "--directory", "server", "python", "bot_runner.py"]
