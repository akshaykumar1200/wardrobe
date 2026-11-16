---
id: audit-f5-vs-prd
readonly: true
effort: medium
---
Read-only audit. Do NOT create, modify or delete any file, do NOT start the server or import F5 modules (F5 startup deletes files). Do NOT open `F5/wardrobe.db` or any `.env`; never print password hashes/tokens.

Context: `prds/` holds 20 feature PRDs (OOTD-01 … OOTD-20) for an Android app built on top of the F5 prototype in `F5/`. Read `prds/README.md`, `prds/SOURCE-EVIDENCE.md`, `prds/API-AND-DEPENDENCY-REGISTER.md`, then each `prds/NN-*.md`'s section 2 (requirements table). Then read all of `F5/` source: main.py, db.py, segmenter.py, matting.py, colors.py, outfit_color.py, pattern.py, seed_data.py, run_server.py, start_f5_with_tunnel.bat, static/index.html, requirements.txt, test_multiuser_isolation.py, test_polish_features.py, capture_*.py.

Answer with `file:line` evidence for every claim:
A. F5 route inventory: every HTTP route in main.py — method, path, auth dependency, request params, response shape, validation present/absent.
B. F5 data model from db.py: tables, columns, types, indexes, constraints, migrations, password hashing details, token handling, default-owner/demo user logic.
C. F5 frontend (static/index.html): list each screen/modal/section and the JS functions behind it; design tokens (colors, fonts, radii); which API each calls; loading/empty/error states present.
D. For EACH PRD OOTD-01..20, a row: existing F5 evidence (files/functions/routes) | which FRs are already met in F5 behaviour, partially met, or absent | status = one of IMPLEMENTED-IN-F5 / PARTIAL / MISSING / NOT-APPLICABLE-TO-F5 (e.g. native Android only). Be strict: code existing is not proof it works.
E. Verify each claim in `prds/SOURCE-EVIDENCE.md` tables against the code: mark CONFIRMED / WRONG (with correct fact) / UNVERIFIABLE.
F. Contradictions or ambiguities you find between PRDs themselves (e.g. README "Five public wardrobe filters" listing six values; OOTD-10 filter names "Topwear/Bottomwear/Shoes/Other" vs stored categories; register says 28 routes — count them) and between PRDs and F5 code.
G. Existing tests: what each test in test_multiuser_isolation.py and test_polish_features.py asserts, how they are run, and whether they would touch the real wardrobe.db/storage (do not run them).
H. Security observations in F5 (public /storage mount, CORS, token expiry, rate limits, upload validation, path trust).
I. AI pipeline facts: model IDs, where weights are loaded from (HF hub vs local path), device (cpu/cuda), thresholds, sizes; and the outfit scoring algorithm summary incl. the pattern_scale→scale mapping issue and raw vs adjusted score ranking.

Output: markdown with sections A–I, tables where natural, facts only.
