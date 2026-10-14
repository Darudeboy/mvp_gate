FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY catalog ./catalog

RUN pip install --no-cache-dir .

ENV RELEASE_GATE_CATALOG=/app/catalog/catalog.yaml
ENV RELEASE_GATE_OUTPUT=/artifacts
ENV RELEASE_GATE_MODE=shadow

VOLUME ["/artifacts", "/overrides", "/catalog"]

ENTRYPOINT ["release-gate"]
CMD ["--help"]
