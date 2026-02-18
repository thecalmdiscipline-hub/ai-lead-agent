#!/usr/bin/env python3
# agent.py — ISO Lead Qualification Engine (DB-ready)

import os
import re
from openai import OpenAI

MODEL = "gpt-4o-mini"

ISO_PATTERNS = {
    "ISO 27001": r"27001",
    "ISO 9001": r"9001",
    "ISO 14001": r"14001",
}

def detect_iso_norms(text: str):
    found = []
    for iso, pattern in ISO_PATTERNS.items():
        if re.search(pattern, text):
            found.append(iso)
    return found if found else ["Niet expliciet benoemd"]

def score_lead(text: str):
    text_lower = text.lower()
    score = 0
    confidence = 0

    # ISO genoemd
    iso_norms = detect_iso_norms(text)
    if iso_norms != ["Niet expliciet benoemd"]:
        score += 3
        confidence += 30

    # Deadline
    if any(word in text_lower for word in ["maand", "deadline", "binnen", "termijn"]):
        score += 2
        confidence += 20

    # Grootte
    match = re.search(r"\b(\d{2,4})\s*(medewerkers|fte|people|employees)\b", text_lower)
    if match:
        employees = int(match.group(1))
        if employees >= 50:
            score += 3
            confidence += 30
        elif employees >= 20:
            score += 2
            confidence += 20

    # Budget
    if "€" in text or "budget" in text_lower:
        score += 2
        confidence += 20

    score = min(score, 10)
    confidence = min(confidence, 100)

    if score >= 8:
        kans = "Hoog"
    elif score >= 5:
        kans = "Gemiddeld"
    else:
        kans = "Laag"

    return score, confidence, iso_norms, kans

def analyze_lead(text: str):
    score, confidence, iso_norms, kans = score_lead(text)

    if iso_norms == ["Niet expliciet benoemd"]:
        summary = f"De organisatie toont een oriënterende interesse in compliance. Er zijn {score} volwassenheidsindicator(en) geïdentificeerd en de totale leadscore bedraagt {score}/10."
    else:
        summary = f"De organisatie toont een expliciete certificeringsbehoefte. Er zijn {score} volwassenheidsindicator(en) geïdentificeerd en de totale leadscore bedraagt {score}/10."

    actie = (
        "Advies: plan een strategische intake en start met een gestructureerde gap-analyse."
        if score >= 8
        else "Advies: kwalificeer verder via een oriënterend gesprek en informatieverstrekking."
    )

    return {
        "lead_score": score,
        "confidence": confidence,
        "iso_norm": ", ".join(iso_norms),
        "commerciele_kans": kans,
        "samenvatting": summary,
        "aanbevolen_actie": actie,
    }
