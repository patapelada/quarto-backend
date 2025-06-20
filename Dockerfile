ARG PYTHON_BASE=3.13-slim
FROM python:$PYTHON_BASE AS builder

RUN pip install -U pdm
ENV PDM_CHECK_UPDATE=false
COPY pyproject.toml pdm.lock README.md /app/
COPY src/ /app/src/

WORKDIR /app
RUN pdm install --check --prod --no-editable

FROM python:$PYTHON_BASE
COPY --from=builder /app/.venv/ /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
COPY src /app/src
EXPOSE 8000
CMD ["uvicorn", "quarto_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]