import json
import requests

BASE = "http://127.0.0.1:8000"

TEST_LEADS = [
    {
        "name": "T1 Enterprise ISO27001 hard deadline + budget",
        "text": (
            "Wij zijn een snelgroeiende SaaS-organisatie met 120 medewerkers. "
            "Een enterprise klant eist ISO 27001 certificering binnen 6 maanden als voorwaarde voor contractverlenging. "
            "Budget is gereserveerd en we willen starten met gap-analyse, implementatie en auditvoorbereiding."
        ),
        "expect_min": 7,
        "expect_iso_contains": ["ISO 27001"],
    },
    {
        "name": "T2 MKB oriënterend",
        "text": (
            "Wij zijn een marketingbureau met 12 medewerkers. We horen iets over ISO maar weten niet wat. "
            "Misschien later, nu nog oriënterend."
        ),
        "expect_max": 4,
        "expect_iso_contains": ["Niet expliciet benoemd"],
    },
    {
        "name": "T3 Multi-norm + aanbesteding",
        "text": (
            "Wij zijn een productiebedrijf met 85 medewerkers. We willen ISO 9001 én ISO 27001 behalen "
            "om aan aanbestedingseisen te voldoen. Planning: 8 maanden. Budget beschikbaar. "
            "We starten met risicoanalyse en interne audit voorbereiding."
        ),
        "expect_min": 6,
        "expect_iso_contains": ["ISO 9001", "ISO 27001"],
    },
    {
        "name": "T4 Keyword noise / edge case",
        "text": (
            "asdf asdf compliance compliance compliance audit?? 9999 medewerkers?? "
            "planning 9 maanden misschien. implementatie gap-analyse beleid."
        ),
        "expect_min": 3,
        "expect_max": 8,
    },
    {
        "name": "T5 Extreme enterprise",
        "text": (
            "Internationale organisatie met 350 medewerkers in fintech en overheid. "
            "Klanten eisen ISO 27001, ISO 9001 en mogelijk ISO 14001. "
            "Budget €150.000. Intern compliance team, beleid, risicoanalyse, auditplanning, security framework. "
            "Deadline 4 maanden. Pre-audit gedaan. Volledige certificering nodig."
        ),
        "expect_min": 7,
        "expect_iso_contains": ["ISO 27001", "ISO 9001"],
    },
]

def call_iso(text: str) -> dict:
    r = requests.post(f"{BASE}/iso", json={"text": text}, timeout=180)
    r.raise_for_status()
    return r.json()

def main():
    print("== Smoke test ==")
    print("Checking server...")
    requests.get(BASE, timeout=10).raise_for_status()

    failures = 0

    for t in TEST_LEADS:
        print(f"\n--- {t['name']} ---")
        out = call_iso(t["text"])

        score = out.get("lead_score", None)
        iso = out.get("iso_norm", "")
        kans = out.get("commerciele_kans", "")
        conf = out.get("confidence_score", "")

        print("score:", score, "| iso:", iso, "| kans:", kans, "| conf:", conf)

        if score is None:
            failures += 1
            print("FAIL: no lead_score in response")
            print(json.dumps(out, indent=2, ensure_ascii=False))
            continue

        if "expect_min" in t and score < t["expect_min"]:
            failures += 1
            print(f"FAIL: score {score} < expected min {t['expect_min']}")

        if "expect_max" in t and score > t["expect_max"]:
            failures += 1
            print(f"FAIL: score {score} > expected max {t['expect_max']}")

        if "expect_iso_contains" in t:
            for must in t["expect_iso_contains"]:
                if must not in iso:
                    failures += 1
                    print(f"FAIL: iso_norm does not contain '{must}'")

    print("\n== Result ==")
    if failures == 0:
        print("ALL TESTS PASSED ✅")
    else:
        print(f"{failures} FAILURES ❌")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
