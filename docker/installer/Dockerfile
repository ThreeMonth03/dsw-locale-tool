FROM python:3.13-slim

WORKDIR /opt/dsw-locale-tool

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir . \
    && useradd --create-home --uid 10001 installer

ARG LOCALE_BUNDLE=dist/locale.zip
COPY ${LOCALE_BUNDLE} /opt/locale/locale.zip

USER installer

ENTRYPOINT ["dsw-locale", "install-dsw", "--bundle", "/opt/locale/locale.zip", "--default-locale"]
