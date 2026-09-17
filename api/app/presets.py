"""ICP presets seeded into icp_profiles (text mirrors docs/ICP_PRESETS.md)."""

PRESETS: list[dict] = [
    {
        "name": "Search-fund buy-box",
        "description_text": (
            "Established, owner-operated service businesses that could be acquired from a retiring "
            "founder. Ideally in business for 20+ years, family-run or founder-led with the owner still "
            "visibly involved, a small team (roughly 5–50 people), serving a local or regional market, and "
            "with no obvious succession plan. Signs of an under-invested digital presence (dated website, "
            "old copyright year, no careers page) are a plus because they point to operational upside after "
            "acquisition. Avoid franchises, private-equity-backed companies, and businesses that are clearly "
            "part of a larger group."
        ),
    },
    {
        "name": "B2B sales ICP",
        "description_text": (
            "Growing small-to-mid-sized companies that are likely to buy B2B software or services now. "
            "Look for active hiring (careers page with open roles), multiple locations or recent expansion, "
            "a modern web stack or online booking/quoting, a clearly named decision-maker (owner, operations "
            "or IT lead) with public contact details, and signs of recent investment such as new services, "
            "certifications or awards. Deprioritize companies with no web presence, single-person "
            "operations, or signs of decline."
        ),
    },
]

# CLI / URL aliases -> preset name
PRESET_ALIASES = {"buybox": "Search-fund buy-box", "sales": "B2B sales ICP"}
