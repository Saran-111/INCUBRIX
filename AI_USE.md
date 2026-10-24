# AI_USE.md — AI Tooling & Assistant Usage Disclosure

In compliance with the IncuBrix Engineering Assessment Guidelines (Tools and resources: use anything / Disclose everything), this document discloses all AI tools, models, and assistants utilized during the engineering of this service.

---

## 1. AI Coding Assistants & Tools Used

| Tool / Assistant | Model / Provider | Primary Usage | Candidate Review & Oversight |
| :--- | :--- | :--- | :--- |
| **Antigravity AI Agent** | Gemini 3.8 Flash (DeepMind) | Architecture scaffolding, boilerplate generation, test case synthesis, and test debugging | 100% human-verified, line-by-line reviewed, and tested against live services. |

---

## 2. Work Breakdown: Where AI Assisted vs. Human Architectural Design

### Architectural Design (Candidate-Driven):
- Selection of the "One Connector, Many Destinations" configuration paradigm over separate per-instance classes.
- Designing the in-memory/file backed `IdempotencyStore` to handle safe retries after forced client timeouts without duplicate publishing.
- Defining the 5-pillar relevance scoring formula (`ai`, `saas`, `video`, `marketing`, `creators`, `founders`).
- Structuring the Appendix A connector contract implementation and lifecycle hooks.

### AI Assistance:
- **Manifest Definitions:** Translating Appendix A YAML schema into 9 concrete connector manifests (`discourse.yaml`, `lemmy.yaml`, `devto.yaml`, `ghost.yaml`, etc.).
- **Mock Simulation Engine:** Building high-fidelity injected failure triggers (`trigger_429`, `trigger_expired_token`, `trigger_renamed_field`) in `mock_server.py`.
- **Catalogue Generation:** Programmatic synthesis of 165 researched long-tail communities across 6 distinct categories.
- **Frontend Dashboard:** Rapid scaffolding of responsive dark-mode HTML5/CSS3/Vanilla JS UI for interactive live demonstration.

---

## 3. Candidate Competency & Code Ownership Declaration

The candidate understands every module, line of code, and architectural pattern in this repository, and is fully prepared to:
1. Walk through the end-to-end trace of any field from HTTP request to stored artifact.
2. Predict system behavior given unseen inputs.
3. Diagnose and fix injected bugs live in under 5 minutes.
4. Implement a brand new connector live from scratch during the 60–90 minute technical interview session.
