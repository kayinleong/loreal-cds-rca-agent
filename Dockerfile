FROM apache/beam_python3.12_sdk:2.64.0

COPY --from=gcr.io/dataflow-templates-base/python312-template-launcher-base:20250402-rc00 /opt/google/dataflow/python_template_launcher /opt/google/dataflow/python_template_launcher

ARG WORKDIR=/dataflow/template
RUN mkdir -p ${WORKDIR}
WORKDIR ${WORKDIR}

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock README.md ./

# Copy the pipeline code and requirements
COPY src/ ./src

RUN poetry install --no-interaction --no-ansi

# Set the required environment variables
ENV FLEX_TEMPLATE_PYTHON_PY_FILE="${WORKDIR}/src/main.py"

ENTRYPOINT ["/opt/apache/beam/boot"]