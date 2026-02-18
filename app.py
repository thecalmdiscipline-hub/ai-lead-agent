from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
import uuid
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

DB_FILE = "leads.db"

app = Flask(__name__, template_folder="templates")


# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            created_at TEXT,
            samenvatting TEXT,
            iso_norm TEXT,
            lead_score INTEGER,
            commerciele_kans TEXT,
            confidence INTEGER,
            aanbevolen_actie TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


# ================= SCORING ENGINE =================

def score_lead(text: str):
    text_lower = text.lower()
    score = 0

    # ISO norms
    if "iso 27001" in text_lower:
        score += 4
    if "iso 9001" in text_lower:
        score += 3
    if "iso 14001" in text_lower:
        score += 2

    # urgency
    if "maanden" in text_lower or "deadline" in text_lower:
        score += 2

    # budget
    if "budget" in text_lower:
        score += 2

    # general compliance indicators (robustness for edge cases)
    if "certificering" in text_lower:
        score += 1
    if "kwaliteit" in text_lower:
        score += 1
    if "aanbesteding" in text_lower:
        score += 1
    if "klant" in text_lower:
        score += 1

    score = min(score, 10)

    if score >= 8:
        kans = "Hoog"
        confidence = 100
    elif score >= 5:
        kans = "Gemiddeld"
        confidence = 60
    else:
        kans = "Laag"
        confidence = 30

    iso_norms = []
    if "iso 27001" in text_lower:
        iso_norms.append("ISO 27001")
    if "iso 9001" in text_lower:
        iso_norms.append("ISO 9001")
    if "iso 14001" in text_lower:
        iso_norms.append("ISO 14001")

    iso_display = ", ".join(iso_norms) if iso_norms else "Niet expliciet benoemd"

    return {
        "samenvatting": f"De organisatie toont een expliciete certificeringsbehoefte. "
                        f"Er zijn {score} volwassenheidsindicator(en) geïdentificeerd "
                        f"en de totale leadscore bedraagt {score}/10.",
        "iso_norm": iso_display,
        "lead_score": score,
        "commerciele_kans": kans,
        "confidence": confidence,
        "aanbevolen_actie": "Advies: plan een strategische intake en start met een gestructureerde gap-analyse."
    }


# ================= ROUTES =================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/iso", methods=["POST"])
def analyse_iso():
    data = request.get_json()
    text = data.get("text", "")

    result = score_lead(text)

    reference_id = uuid.uuid4().hex[:8]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    result["reference_id"] = reference_id
    result["created_at"] = created_at

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO leads VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        reference_id,
        created_at,
        result["samenvatting"],
        result["iso_norm"],
        result["lead_score"],
        result["commerciele_kans"],
        result["confidence"],
        result["aanbevolen_actie"]
    ))
    conn.commit()
    conn.close()

    return jsonify(result)


@app.route("/leads")
def get_leads():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()

    leads = []
    for row in rows:
        leads.append({
            "reference_id": row[0],
            "created_at": row[1],
            "samenvatting": row[2],
            "iso_norm": row[3],
            "lead_score": row[4],
            "commerciele_kans": row[5],
            "confidence": row[6],
            "aanbevolen_actie": row[7]
        })

    return jsonify(leads)


@app.route("/download-pdf/<ref_id>")
def download_pdf(ref_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE id=?", (ref_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Lead not found"}), 404

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("ISO Lead Rapport", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Referentie: {row[0]}", styles["Normal"]))
    elements.append(Paragraph(f"Datum: {row[1]}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Score: {row[4]}/10", styles["Heading2"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"ISO Norm(en): {row[3]}", styles["Normal"]))
    elements.append(Paragraph(f"Commerciële Kans: {row[5]}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Samenvatting: {row[2]}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Aanbevolen Actie: {row[7]}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"ISO_Report_{ref_id}.pdf",
        mimetype="application/pdf"
    )


if __name__ == "__main__":
    app.run(port=8000, debug=True)
