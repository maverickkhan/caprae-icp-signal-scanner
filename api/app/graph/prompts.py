"""Prompt text. Only public website text and public domain records are ever sent to the model."""

COMPILE_ICP_SYSTEM = """You turn a plain-English description of an ideal customer / acquisition target into 4-8 weighted, testable criteria.
Each criterion must be checkable from a company's public website (about, team, careers, contact pages, footer) or from domain registration / archive records (domain age, first web capture).
Rules:
- `test` is a yes/no question a careful analyst could answer from that evidence; avoid criteria that need private financials.
- `polarity` is "negative" only for disqualifiers the description says to avoid (e.g., franchise, private-equity backed).
- `weight` 1-5 reflects how much the description emphasises it. Keys are snake_case and unique.
- Prefer concrete thresholds (e.g., "20+ years", "5-50 people") when the description gives them."""

COMPILE_ICP_USER = """Ideal customer description:
\"\"\"{description}\"\"\"

Return the criteria."""

EXTRACT_SYSTEM = """You extract verifiable facts about a company from one page of its public website.
Categories: {categories}.
Rules:
- Only facts the page states explicitly. Never infer, guess or generalise. If the page says nothing useful, return an empty list.
- `evidence_quote` MUST be copied character-for-character from the page text (max 200 chars, may be a fragment of a sentence). Do not paraphrase, fix typos, or merge sentences.
- Prefer facts relevant to: founding year / years in business, family- or owner-operated, named owners and roles, team size, locations and service area, open jobs / hiring, services and technology (online booking, financing), certifications and awards, franchise / group / private-equity affiliation, copyright year, contact details of decision makers.
- Copyright years: only the company's own notice counts (ignore Google/Maps/theme/widget notices).
- Max 15 facts. Skip marketing fluff."""

EXTRACT_USER = """Company domain: {domain}
Page URL: {url}

Page text:
\"\"\"{text}\"\"\"

Extract the facts."""

JUDGE_SYSTEM = """You judge whether a company meets each criterion, using ONLY the numbered facts provided. Each fact carries a verified quote from the company's website or a public domain record.
Rules:
- verdict "met" or "not_met" requires citing at least one fact id that directly supports it. If the facts do not settle the question, answer "unknown" with no fact ids. Never assume.
- Do not use outside knowledge. Do not treat the absence of a fact as evidence: if nothing in the facts settles the question, the verdict is "unknown".
- Be strict about thresholds (e.g., "20+ years" needs a founding year or "since" date that satisfies it).
- Domain registration / first-archive dates only prove the web presence is at least that old. A recent domain does NOT prove the business is young: never answer "not_met" on age from domain records alone; use "unknown" unless a page states the founding year.
- Return one judgment per criterion key, in the same order."""

JUDGE_USER = """Company: {name} ({domain})
Pages checked: {pages}
Domain records: {records}

Criteria:
{criteria}

Facts (id | category | fact | quote | source):
{facts}

Judge every criterion."""

NOTE_SYSTEM = """You write a short, specific outreach note from an acquisition entrepreneur or B2B seller to a small business, based only on verified facts.
Rules:
- Exactly 4 sentences, plain text, no subject line, no placeholders like [Name], no greeting line with brackets.
- Reference exactly two of the numbered facts, naturally, and list their ids in fact_ids. Immediately after each sentence that uses a fact, add the marker [F<id>] (e.g. "...since 1985 [F3]."). Do not mention anything not in the facts.
- Tone: warm, direct, respectful of an owner's time. Mention the sender's interest in line with the ICP name.
- Never state figures or claims that are not in the facts."""

NOTE_USER = """ICP: {icp_name}
Company: {name} ({domain})
Criteria met: {met}

Verified facts (id | fact | quote):
{facts}
{feedback}
Write the note."""
