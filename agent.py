import uuid
from datetime import datetime
import re

def analyse_lead(text: str):

    text_lower = text.lower()

    # -----------------------
    # ISO detectie
    # -----------------------
    iso_list = []

    if "27001" in text_lower:
        iso_list.append("ISO 27001")
    if "9001" in text_lower:
        iso_list.append("ISO 9001")
    if "14001" in text_lower:
        iso_list.append("ISO 14001")

    iso_norm = ", ".join(sorted(iso_list)) if iso_list else "Niet expliciet benoemd"

    # -----------------------
    # Indicator scoring
    # -----------------------
    score = 0

    if iso_list:
        score += 3

    if any(word in text_lower for word in ["deadline", "maand", "binnen", "spoed"]):
        score += 2

    if any(word in text_lower for word in ["budget", "gereserveerd", "investering"]):
        score += 2

    if any(word in text_lower for word in ["enterprise", "aanbesteding", "verplichting"]):
        score += 2

    if any(word in text_lower for word in ["risicoanalyse", "interne audit", "compliance team"]):
        score += 1

    # 🔒 Minimum logica
    if score == 0:
        final_score = 0
    else:
        final_score = max(score, 3)

    if final_score >= 8:
        kans = "Hoog"
    elif final_score >= 5:
        kans = "Gemiddeld"
    else:
        kans = "Laag"

    confidence = min(final_score * 10, 100)

    # -----------------------
    # Reference ID
    # -----------------------
    reference_id = str(uuid.uuid4())[:8]

    # -----------------------
    # Samenvatting
    # -----------------------
    samenvatting = (
        f"De organisatie toont een expliciete certificeringsbehoefte. "
        f"Er zijn {final_score} volwassenheidsindicator(en) geïdentificeerd "
        f"en de totale leadscore bedraagt {final_score}/10."
        if final_score >= 5
        else
        f"De organisatie toont een oriënterende interesse in compliance. "
        f"Er zijn {final_score} volwassenheidsindicator(en) geïdentificeerd "
        f"en de totale leadscore bedraagt {final_score}/10."
    )

    aanbevolen_actie = (
        "Advies: plan een strategische intake en start met een gestructureerde gap-analyse."
        if final_score >= 5
        else
        "Advies: kwalificeer verder via een oriënterend gesprek en informatieverstrekking."
    )

    return {
        "reference_id": reference_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "iso_norm": iso_norm,
        "lead_score": final_score,
        "commerciele_kans": kans,
        "confidence": confidence,
        "samenvatting": samenvatting,
        "aanbevolen_actie": aanbevolen_actie
    }