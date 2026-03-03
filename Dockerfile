# ─────────────────────────────────────────────────────────────────────────────
# Étape 1 — builder : installation des dépendances dans un venv isolé
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────────
# Étape 2 — image finale allégée (pas d'outils de build)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Bonne pratique : ne pas tourner en root
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Récupère uniquement le venv construit à l'étape précédente
COPY --from=builder /opt/venv /opt/venv

# Copie le code source
COPY app.py .
COPY templates/ templates/

# Active le venv pour tous les CMD suivants
ENV PATH="/opt/venv/bin:$PATH" \
    DEV=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 5000

# Gunicorn en production (3 workers suffisent pour la démo)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "--timeout", "120", "app:app"]
