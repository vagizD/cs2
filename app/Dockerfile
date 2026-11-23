FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY streamlit_app.py bracket.py bracket.css ./
USER 10001:10001
EXPOSE 8080
CMD ["sh", "-c", "exec python -m streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=\"${PORT:-8080}\""]
