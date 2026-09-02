FROM odoo:18

ENV PYTHONPATH="/opt:${PYTHONPATH}"

USER root

RUN pip3 install --no-cache-dir --break-system-packages pypdf

USER odoo
