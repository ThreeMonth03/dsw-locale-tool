FROM python:3.13-slim-bookworm

WORKDIR /opt/dsw-locale-tool

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

ENTRYPOINT ["dsw-locale"]
