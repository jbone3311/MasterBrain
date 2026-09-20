# Developer/CI image only, not public production infrastructure.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN pip install --no-cache-dir uv==0.12.17 && uv sync --locked --no-dev --no-editable
RUN useradd --uid 10001 --create-home brain
USER 10001
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["email-brain"]
CMD ["--help"]
