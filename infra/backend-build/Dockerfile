FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /lab
COPY --chown=65534:65534 lab/ /lab/
USER 65534:65534
CMD ["python", "-m", "unittest", "-v", "test_query_templates", "test_select_sources", "test_butce_profilleri"]
