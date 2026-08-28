# UI/UX Pro Max - remote MCP server
# Build context = root repo. Railway mendeteksi Dockerfile ini otomatis.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Mesin cari + data CSV (source of truth), lalu pembungkus MCP-nya.
COPY src/ui-ux-pro-max/ ./src/ui-ux-pro-max/
COPY mcp_server/ ./mcp_server/

EXPOSE 8080
CMD ["python", "mcp_server/server.py"]
