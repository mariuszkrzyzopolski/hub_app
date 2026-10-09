# Documentation & Agent Reference Hub

Welcome to the central documentation directory for **Personal Hub**. This directory organizes all architectural references, product briefs, UX design specifications, and testing specs for both human developers and AI agents.

---

## 📁 Directory Structure

```text
docs/
├── README.md                                  # Central index & agent navigation guide (this file)
├── architecture/                              # Architecture, data models, and system reference
│   ├── PROJECT-REFERENCE.md                   # Complete system overview, architecture, models & patterns
│   └── HANDOFF-v2.md                          # Implementation handoff, milestone tracking & verified features
├── product/                                   # Product requirements & specifications
│   ├── product-brief-personal-hub.md          # Full product brief, requirements, rules & constraints
│   └── product-brief-personal-hub-distillate.md # Distilled product brief with essential constraints
├── design/                                    # UI/UX design and interaction specs
│   └── ux-design-specification.md             # UX specifications, layout structure & design tokens
└── testing/                                   # Test plans, scenarios & E2E coverage specs
    ├── spec-e2e-coverage.md                   # Full E2E scenario coverage matrix & constraints
    └── spec-e2e-admin-and-pages.md            # E2E test specs for admin and guest pages
```

---

## 📚 Categorized Documents

### 1. Architecture & Reference (`architecture/`)
- **[`PROJECT-REFERENCE.md`](architecture/PROJECT-REFERENCE.md)**
  - System architecture (Django catalogue pattern with `core/`, `gifts/`, `events/`, `hub/`).
  - Data models, abstract models (`PasswordGatedModel`, `AuditLogEntry`), and relationships.
  - Multi-layered authentication (Name gate, Password gate, slug-scoped session management).
  - Race condition handling (`select_for_update`) and category locking logic.
  - Views, admin dashboard, audit log & soft-delete/restore mechanics.

- **[`HANDOFF-v2.md`](architecture/HANDOFF-v2.md)**
  - Implementation status and completed milestones (v1–v5).
  - Architectural decisions, invariants, and test suite verification commands.

### 2. Product & Requirements (`product/`)
- **[`product-brief-personal-hub.md`](product/product-brief-personal-hub.md)**
  - The comprehensive product brief detailing guest workflows, gift claims, event role claims, and admin capabilities.
  - Edge cases, error messaging copy (Polish UI), and boundary conditions.
  - Explicitly excluded features (no accounts, no Docker, no external notifications, no multi-language).

- **[`product-brief-personal-hub-distillate.md`](product/product-brief-personal-hub-distillate.md)**
  - Condensed summary of core product rules, model schemas, and constraints for quick reference.

### 3. Design & UX (`design/`)
- **[`ux-design-specification.md`](design/ux-design-specification.md)**
  - Visual hierarchy, typography, responsive behavior, and color schemes.
  - Interaction states (name gate modal, password gate, category claim toggles, audit logs).
  - Template structure and CSS design system guidelines.

### 4. Testing & QA (`testing/`)
- **[`spec-e2e-coverage.md`](testing/spec-e2e-coverage.md)**
  - Playwright E2E coverage matrix mapping scenarios to test cases.
  - Guidelines for test isolation, fixture reuse, and unique guest name seeding.

- **[`spec-e2e-admin-and-pages.md`](testing/spec-e2e-admin-and-pages.md)**
  - Specifications for Django admin CRUD flows and guest-facing page rendering tests.

---

## 🤖 AI Agent Quick-Routing Guide

When working on tasks, consult the relevant documentation based on the task domain:

| Task Domain | Primary Document | Secondary Reference |
|---|---|---|
| **Backend & Core Logic** | [`architecture/PROJECT-REFERENCE.md`](architecture/PROJECT-REFERENCE.md) | [`architecture/HANDOFF-v2.md`](architecture/HANDOFF-v2.md) |
| **New Mini-App or Model Changes** | [`architecture/PROJECT-REFERENCE.md`](architecture/PROJECT-REFERENCE.md) | [`product/product-brief-personal-hub.md`](product/product-brief-personal-hub.md) |
| **UI, Styling & Templates** | [`design/ux-design-specification.md`](design/ux-design-specification.md) | [`architecture/PROJECT-REFERENCE.md`](architecture/PROJECT-REFERENCE.md) |
| **Requirements & Edge Cases** | [`product/product-brief-personal-hub.md`](product/product-brief-personal-hub.md) | [`product/product-brief-personal-hub-distillate.md`](product/product-brief-personal-hub-distillate.md) |
| **E2E Testing & Test Fixes** | [`testing/spec-e2e-coverage.md`](testing/spec-e2e-coverage.md) | [`testing/spec-e2e-admin-and-pages.md`](testing/spec-e2e-admin-and-pages.md) |
| **Project Status & Decisions** | [`architecture/HANDOFF-v2.md`](architecture/HANDOFF-v2.md) | [`architecture/PROJECT-REFERENCE.md`](architecture/PROJECT-REFERENCE.md) |
