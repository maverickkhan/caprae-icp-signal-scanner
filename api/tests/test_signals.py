from app.services.signals import regex_signals

ARS = (
    "Who We Are ARS/Rescue Rooter is a leading brand of American Residential Services LLC., which provides heating, "
    "air conditioning, indoor air quality, plumbing, drain cleaning, and sewer line services from company-owned "
    "locations across the United States. United by exceptional service, the ARS/Rescue Rooter Network serves both "
    "residential and commercial customers."
)

FALSE_QUOTES = [
    "Becoming part of our membership program gives you priority scheduling and discounts.",
    "When you call us, you become part of our family and we treat your home like our own.",
    "Ask for the company's license number before hiring any contractor.",
    "\"They came out the same day and fixed my AC - great service!\" - Maria G., Austin",
    "Come grow with us. We are hiring technicians and office staff.",
    "Every repair is backed by our Exceptional Service Guarantee.",
    "We are proud to be a member of the Better Business Bureau.",
    "We install every brand of Carrier, Trane and Lennox equipment.",
    "A division of labor keeps our crews efficient.",
]


def _affiliation(text: str) -> list[dict]:
    return [f for f in regex_signals(text, "https://x.com/") if f["category"] == "affiliations"]


def test_ars_brand_and_company_owned_are_detected():
    facts = _affiliation(ARS)
    kinds = [f["fact"] for f in facts]
    assert any(k == "The company describes itself as a brand of American Residential Services LLC." for k in kinds), kinds
    assert any(k.startswith("The company operates company-owned locations across the United States") for k in kinds), kinds
    for f in facts:
        assert "Quote:" not in f["fact"]
        assert f["evidence_quote"][0].isalnum(), f["evidence_quote"]
        assert f["evidence_quote"] in ARS.replace("\n", " ") or len(f["evidence_quote"]) <= 200
        assert not f["evidence_quote"].endswith((",", "-")), f["evidence_quote"]


def test_subsidiary_owned_and_franchise_positives():
    assert _affiliation("Acme Air is a wholly-owned subsidiary of Comfort Holdings Inc.")[0]["fact"] == (
        "The company describes itself as a subsidiary of Comfort Holdings Inc."
    )
    assert _affiliation("In 2021 the business was acquired by Bluebird Capital Partners.")[0]["fact"] == (
        "The company states it is acquired by Bluebird Capital Partners."
    )
    assert _affiliation("Mr. Rooter of Austin is an independently owned and operated franchise.")[0]["fact"] == (
        "The company describes itself as a franchise or franchisee."
    )


def test_generic_phrases_and_testimonials_never_match():
    for q in FALSE_QUOTES:
        assert _affiliation(q) == [], q


def test_person_or_family_ownership_is_not_a_corporate_signal():
    assert _affiliation("Owned by John Smith since 1985.") == []
    assert _affiliation("Proudly owned by the Garcia family for three generations.") == []


def test_family_owned_and_founding_signals():
    facts = regex_signals("Family owned and operated since 1994, serving Dallas. Over 30 years of experience.", "https://x.com/")
    kinds = {f["category"]: f["fact"] for f in facts}
    assert kinds["ownership_leadership"].startswith("The company describes itself as family owned")
    assert kinds["founding_history"] in ("The page states the business has operated since 1994.", "The page mentions 30+ years of business or experience.")
