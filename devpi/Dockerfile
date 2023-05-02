FROM python:3.11.3-slim-buster

RUN apt update \
    && apt install -y procps \
    && apt clean \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && pip install --upgrade devpi-server devpi-web devpi-client build setuptools wheel \
    && devpi-init

# packages to be uploaded to devpi
COPY packages.txt /packages.txt
RUN pip download -d /tmp/packages --no-deps --no-cache-dir -r /packages.txt

# local packages for testing
COPY test-packages /test-packages
RUN sh -c "ls /test-packages | xargs -I{} python -m build /test-packages/{} --no-isolation --outdir /tmp/packages"

# register packages
COPY plugins /plugins
RUN sh -c "ls /plugins | xargs -I{} pip install -e /plugins/{} --no-cache-dir"

ENV DEVPI_SERVER_ROOT=/devpi
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/bash", "/entrypoint.sh" ]

EXPOSE 3141
