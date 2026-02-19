import os
import sqlite3
from flask import Flask, request, jsonify, render_template
from agent import analyse_lead

app = Flask(__name__)

DB_NAME = "leads.db"


# -----------------------------
# Database init + optimization
# -----------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Main table
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT UNIQUE,
            created_at TEXT,
            iso_norm TEXT,
            lead_score INTEGER,
            commerciele_kans TEXT,
            confidence INTEGER,
            samenvatting TEXT,
            aanbevolen_actie TEXT
        )
    """)

    # Performance indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON leads(created_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lead_score ON leads(lead_score)")

    conn.commit()
    conn.close()


init_db()


# -----------------------------
# Utility: Cleanup old leads
# -----------------------------
def cleanup_old_leads(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        DELETE FROM leads
        WHERE id NOT IN (
            SELECT id FROM leads
            ORDER BY created_at DESC
            LIMIT ?
        )
    """, (limit,))

    conn.commit()
    conn.close()


# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/iso", methods=["POST"])
def analyse_iso():
    try:
        data = request.get_json()
        text = data.get("text", "")

        if not text.strip():
            return jsonify({"error": "Lege input"}), 400

        result = analyse_lead(text)

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Insert with UNIQUE reference safeguard
        c.execute("""
            INSERT OR REPLACE INTO leads (
                reference_id,
                created_at,
                iso_norm,
                lead_score,
                commerciele_kans,
                confidence,
                samenvatting,
                aanbevolen_actie
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["reference_id"],
            result["created_at"],
            result["iso_norm"],
            result["lead_score"],
            result["commerciele_kans"],
            result["confidence"],
            result["samenvatting"],
            result["aanbevolen_actie"]
        ))

        conn.commit()
        conn.close()

        cleanup_old_leads()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/leads")
def get_leads():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT reference_id, created_at, iso_norm,
               lead_score, commerciele_kans, confidence
        FROM leads
        ORDER BY created_at DESC
        LIMIT 100
    """)

    rows = c.fetchall()
    conn.close()

    leads = []
    for row in rows:
        leads.append({
            "reference_id": row[0],
            "created_at": row[1],
            "iso_norm": row[2],
            "lead_score": row[3],
            "commerciele_kans": row[4],
            "confidence": row[5]
        })

    return jsonify(leads)


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))
    debug = os.environ.get("APP_DEBUG", "0") in ("1", "true", "True")

    app.run(host=host, port=port, debug=debug)