# Personal Hub (bambetle Hub)

Simple Django application to coordinate social occasions, gift lists, and event roles for friends and family. User-facing interface is in Polish.

---

## 🎯 Key Concepts

- **No User Accounts:** Guests identify themselves with a unique session name rather than managing passwords or accounts. In case of name collision, the system provides suggestions or allows claiming the profile.
- **Password-Gated Pages:** Each event or gift list is secured by its own password set during creation to keep things private yet accessible without account friction.
- **Modules:**
  - **Gift List (`gifts`):** Public list of items where guests can claim, unclaim, or update claimed gifts.
  - **Events (`events`):** Group coordination tool to claim items/tasks per category, with bulk category claim/unclaim support.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.14, Django 6.0.x, Gunicorn, PostgreSQL
- **Testing:** Pytest, Playwright (E2E)
- **Tooling:** `uv`, `Makefile`

---

## 📖 Documentation & Agent Resources

All project specifications, architectural references, UX designs, and test plans are organized under [`docs/`](docs/README.md):

- **[Documentation Index & AI Agent Guide](docs/README.md)**: Entry point and context router for developers and AI agents.
- **Architecture & Reference (`docs/architecture/`)**:
  - [`PROJECT-REFERENCE.md`](docs/architecture/PROJECT-REFERENCE.md): Architecture, data models, session mechanics, and race condition handling.
  - [`HANDOFF-v2.md`](docs/architecture/HANDOFF-v2.md): Implementation status, milestone verification, and decision log.
- **Product Requirements (`docs/product/`)**:
  - [`product-brief-personal-hub.md`](docs/product/product-brief-personal-hub.md): Comprehensive product requirements, flows, and boundary conditions.
  - [`product-brief-personal-hub-distillate.md`](docs/product/product-brief-personal-hub-distillate.md): Distilled brief and core constraints.
- **UX & Design (`docs/design/`)**:
  - [`ux-design-specification.md`](docs/design/ux-design-specification.md): UX design specifications, component states, and layout guidelines.
- **Testing & QA (`docs/testing/`)**:
  - [`spec-e2e-coverage.md`](docs/testing/spec-e2e-coverage.md): E2E test scenarios and coverage matrix.
  - [`spec-e2e-admin-and-pages.md`](docs/testing/spec-e2e-admin-and-pages.md): Admin and guest page rendering specifications.
