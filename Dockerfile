FROM odoo:18

ENV PYTHONPATH="/opt:${PYTHONPATH}"

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends ghostscript \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages pypdf

USER odoo
