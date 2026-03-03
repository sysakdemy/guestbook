import os
import time

import psycopg2
import redis
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

# ── Configuration via variables d'environnement ──────────────────────────────
DB_HOST = os.getenv("DB_HOST", "db")
DB_NAME = os.getenv("DB_NAME", "guestbook")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "secret")
REDIS_HOST = os.getenv("REDIS_HOST", "cache")


# ── Helpers de connexion ──────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )


def get_redis():
    return redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)


# ── Initialisation de la base de données ─────────────────────────────────────
def init_db():
    """Attend que PostgreSQL soit prêt, puis crée la table si elle n'existe pas."""
    retries = 10
    while retries > 0:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id         SERIAL PRIMARY KEY,
                    name       VARCHAR(100) NOT NULL,
                    message    TEXT         NOT NULL,
                    created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Base de données prête.")
            return
        except Exception as exc:
            retries -= 1
            print(f"⏳ PostgreSQL pas encore prêt ({exc}) — nouvel essai dans 3 s…")
            time.sleep(3)
    raise RuntimeError("Impossible de se connecter à PostgreSQL après plusieurs tentatives.")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def index():
    # Incrémente le compteur de visites dans Redis
    r = get_redis()
    visits = r.incr("visits")

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "Anonyme").strip() or "Anonyme"
        message = request.form.get("message", "").strip()
        if message:
            cur.execute(
                "INSERT INTO messages (name, message) VALUES (%s, %s)",
                (name, message),
            )
            conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for("index"))

    cur.execute(
        "SELECT name, message, created_at FROM messages ORDER BY created_at DESC"
    )
    messages = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("index.html", messages=messages, visits=visits)


@app.route("/health")
def health():
    """Endpoint de health-check pour Docker."""
    return {"status": "ok"}, 200


# ── Initialisation au démarrage ───────────────────────────────────────────────
# Appelé ici (niveau module) pour que Gunicorn exécute init_db()
# même lorsqu'il importe le module sans passer par __main__.
init_db()

# ── Démarrage en développement direct ─────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
