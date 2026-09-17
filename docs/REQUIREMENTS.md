# Caprae Capital — what is graded and what to submit

## Challenge
Analyze SaaSquatch Leads and build 1–2 impactful features in **≤5 hours of code**.
Quality-first (enhance one feature) or quantity-driven (several lightweight tools). We chose **quality-first**.

Must document: UX design choices and full backend architecture — **database used, caching/performance optimizations, hosting (static vs serverless), deployment process, cloud provider, exact technologies/frameworks**.

## Submission
- **GitHub repo**: all code, `README.md` with setup instructions, dataset if permissible
- **Video walkthrough**: 1–2 min — the project, the value it generates, decisions made, results
- **Demo link**: optional but recommended (live app, API demo, or notebook)
- Email to recruiting@capraecapital.com, subject: `Full Stack Developer - Handbook Submission - Abdul Hai`, with resume attached

## Rubric (40 points)
| Criteria | Pts | What they reward | How we address it |
|---|---|---|---|
| Business use case | 10 | Prioritize high-impact leads, minimize irrelevant data, fit sales workflows, actionable insights beyond scraping, align with target market | User-defined ICP; ranked leads; evidence per criterion; two presets for both audiences; outreach note |
| UX/UI | 10 | Clean, intuitive, low learning curve; guides filtering, exporting, verifying leads; smart automation | Table-first like SaaSquatch; presets; one-click scan; evidence drawer with verified/unverified badges; export |
| Technicality | 10 | Accurate multi-source extraction, parsing, scale, handles complex sites; bonus for dedupe/enrichment/validation; resilience to site changes/CAPTCHAs/IP limits; speed | Multi-source (site, RDAP, Wayback); robots-aware fetcher; Wayback fallback; grounding check; dedupe + reachability; caching; parallel extraction; evals |
| Design | 5 | Polished, modern, clear visual cues | shadcn/ui, score badges, criterion chips, clear states |
| Other | 5 | Creativity, CRM integrations, automated reporting, ethical collection, great docs/strategy | HubSpot-shaped export, ethics section, LangFuse traces, optional MCP server, strong README |

## Competitive landscape
10+ public submissions already built lead scoring, fuzzy dedupe, email validation and CSV export. The closest is LeadRadar (github.com/xhusnain/caprae-leadradar): crawler + fixed acquisition-fit score + outreach + HubSpot/Salesforce export, seeded with Texas HVAC data from OSM. **Our differentiator is user-defined, evidence-grounded criteria** — don't drift back into a fixed-score clone.
