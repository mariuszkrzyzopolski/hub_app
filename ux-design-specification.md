---
stepsCompleted: [1,2,3,4,5,6,7,8,9,11,12,13]
inputDocuments:
  - product-brief-personal-hub.md
  - product-brief-personal-hub-distillate.md
  - screenshots/home.png
  - screenshots/gift_list.png
  - templates/home.html
  - templates/gift_index.html
  - templates/gift_list.html
---

# UX Design Specification — Personal Hub

**Author:** Project Owner
**Date:** 2026-05-19

---

<!-- UX design content will be appended sequentially through collaborative workflow steps -->

## Core User Experience

### Defining Experience

The single defining interaction is a guest arriving from a group chat link, seeing a list of items or roles, and tapping one button to claim something — without creating an account, typing a name more than once, or making any decision beyond "which one." Everything else is scaffolding around that three-second moment.

### Platform Strategy

Mobile-primary web. Guests arrive from WhatsApp or Signal links mid-conversation, on a phone, likely with one hand free. All tap targets minimum 44px. All primary actions visible without scrolling on a 375px viewport. Desktop is supported but never the design target.

### Effortless Interactions

- Zero text entry after the name gate — session name assigned automatically to every claim
- Single-button claim: no confirmation, no form, immediate visual feedback
- Category-level assignment: one tap fills an entire section for guests who want to take responsibility for a whole area
- Password gate remembers across all lists in the session — enter once, access all

### Critical Success Moments

1. Password accepted → list appears immediately (no loading state if avoidable)
2. Name entered → travels silently to all future lists and events
3. `Przypisz` tapped → item visually flips to claimed state with guest's name
4. Homepage catalogue → guest can see at a glance what still needs covering across all lists

### Experience Principles

- One primary action visible per screen at any time
- Claimed state is celebratory, not just different
- Nothing about a list renders before both gates are passed
- Progress always visible — guests should never have to wonder "is everything covered?"
- Trust-based: anyone can edit or delete; the audit log is the admin's backstop, not the UX

---

## Desired Emotional Response

### Primary Emotional Goals

The primary feeling is: *"Someone thoughtful made this for their people."* The opposite of a SaaS product — more like a handwritten list passed between friends. Warm, personal, unpolished in a deliberate way.

### Emotional Journey Mapping

- Password gate → calm, private exclusivity — like being let into someone's home
- Name gate → welcoming, quick, slightly playful (suggestion chips for name collisions)
- List or event page → familiar and organised, like a printed list on the fridge
- Claim moment → quiet satisfaction, a checkbox ticked in ink
- Error or race condition → gentle reassurance, never alarming

### Micro-Emotions

- Trust (not anxiety) when entering a password: generic error message, no hints
- Belonging when the name appears in the header — "I'm in, this knows who I am"
- Accomplishment after claiming — the strikethrough and green background confirm it
- Calm when returning — the page looks exactly as left, nothing has changed structurally

### Design Implications

- Warm linen background (`#dad7cd`) carries the emotional register before any interaction — the page *feels* right before the guest reads a word
- Dark pine header (`#344e41`) is anchoring and consistent — every screen feels like the same trusted place
- Claimed items use a muted sage green (`#cfe3c9`), not a bright success green — satisfaction without excitement
- Delete confirmation uses a quiet icon circle, not a red banner — destructive but not alarming
- Empty state copy is italic and faded, not bold and prominent — absence is okay, not a problem

### Emotional Design Principles

- Calm before clarity — the background tone lands before the content
- Restraint over decoration — nothing added that does not earn its place
- Warm neutrals for structure, green only for action and completion
- Never make guests feel they could break something

---

## Design System Foundation

### Design System Choice

Custom CSS with design tokens — no framework, no build step. The existing `:root` custom property architecture in `style.css` is retained. Only colour token values are replaced. All structural tokens (radius, shadow scale, transition timing, spacing) remain unchanged.

### Rationale for Selection

The product brief explicitly prohibits JS frameworks and build steps. The existing vanilla CSS system is well-structured with a clear token layer. A framework would introduce dependency overhead and visual defaults that fight the personal, non-SaaS aesthetic. Custom tokens give precise control over the earthy palette.

### Implementation Approach

Replace all colour tokens in `:root`. No structural changes to selectors or component classes — only values change. The icon system migrates from emoji to inline Feather SVG paths embedded directly in Django templates.

### Customisation Strategy

Feather Icons (MIT licence) used as inline SVG — no CDN dependency, no font file, no build step. Each icon is a small inline `<svg>` with `fill="none"`, consistent `stroke-width="2"`, `stroke-linecap="round"`, `stroke-linejoin="round"`. Icon colour inherits from parent or is set via `stroke` attribute using palette tokens.

---

## Visual Design Foundation

### Colour System

Source palette (Coolors `dad7cd-a3b18a-588157-3a5a40-344e41`):

| Token | Value | Role |
|---|---|---|
| `--color-bg` | `#dad7cd` | Page background — warm linen |
| `--color-surface` | `#f0ede6` | Cards, form containers |
| `--color-surface-alt` | `#e4e0d8` | Alternate rows, nested containers |
| `--color-surface-claimed` | `#cfe3c9` | Claimed item background |
| `--color-border` | `#bbb8ae` | Default borders |
| `--color-border-subtle` | `rgba(163,177,138,0.30)` | Hairline dividers |
| `--color-primary` | `#3a5a40` | Buttons, links, interactive |
| `--color-primary-hover` | `#2e4832` | Hover — deeper forest |
| `--color-header-bg` | `#344e41` | Sticky header background |
| `--color-header-text` | `#dad7cd` | Logo and nav text on header |
| `--color-text` | `#2a2e28` | Body text |
| `--color-text-muted` | `#5a6b52` | Secondary text, metadata |
| `--color-text-light` | `#8a9980` | Placeholders, hints |
| `--color-success` | `#588157` | Progress fill, Przypisz button |
| `--color-success-bg` | `#cfe3c9` | Claimed item background |
| `--color-category-header` | `#a3b18a` | Category band background |
| `--color-danger` | `#b94040` | Delete button — warm red |
| `--color-danger-bg` | `#f9efef` | Error and delete confirmation backgrounds |

### Typography System

System sans-serif stack unchanged (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto`). Adjustments:
- Heading `letter-spacing: -0.02em` for intentional, grounded feel
- Body `line-height: 1.65` for mobile readability
- Button `font-weight: 600`, `letter-spacing: 0.01em`
- Form labels uppercase, `letter-spacing: 0.04em`, `font-size: 0.6875rem` — stationery-like field labelling

### Spacing and Layout Foundation

8px base grid retained. No changes to spacing tokens. Homepage `section-tabs` widget removed — the two catalogue cards serve as the full homepage, eliminating redundant navigation duplication.

### Accessibility Considerations

- All interactive elements minimum 44px touch target height
- Colour contrast: `#2a2e28` text on `#f0ede6` surface — passes WCAG AA
- `#344e41` header with `#dad7cd` text — passes WCAG AA
- `#fff` text on `#588157` button — passes WCAG AA
- Danger red `#b94040` on white — passes WCAG AA
- Icons always accompanied by visible text labels — never icon-only interactive elements

---

## Component Strategy

### Component Inventory

All components are custom vanilla CSS — no design system library. The existing class architecture is retained; only token values and icon implementation change.

| Component | Class | Status | Change |
|---|---|---|---|
| Page header | `.page-header` | Keep | Token update only |
| Catalogue card | `.card` | Keep | Token update only |
| Entry list row | `.entry-list li` | Keep | Token update only |
| Gift/role item row | `.item` | Keep | Token update only |
| Claimed item state | `.item.claimed` | Keep | Token update only |
| Progress bar | `.progress-bar` / `.progress-bar-fill` | Keep | Token update only |
| Category block | `.category` | Keep | Token update only |
| Category header band | `.category-header` | Keep | Token update only |
| Password gate container | `.gate-container` | Keep | Token update only |
| Name gate container | `.gate-container` | Keep | Token update only |
| Info screen (archived/WIP) | `.info-container` | Adjust | Replace emoji `.info-icon` with SVG circle container |
| Form group | `.form-group` | Keep | Token update only |
| Button — primary | `.btn-primary` | Keep | Token update only |
| Button — success (claim) | `.btn-success` | Keep | Token + icon |
| Button — danger (delete) | `.btn-danger` | Keep | Token + icon |
| Button — link (edit) | `.btn-link` | Adjust | Replace `✎` prefix with inline SVG; remove `::before` pseudo |
| Button — secondary | `.btn-secondary` | Keep | Token update only |
| Dialog overlay | `.dialog-overlay` / `.dialog` | Keep | Token update only |
| Header navigation | `header nav` | Adjust | Background → `#344e41`, text → `#dad7cd` |
| Logo | `.logo` | Adjust | Replace `✦` with inline star SVG |
| Guest name display | `.guest-name` | Adjust | Replace `👤` `::before` with inline SVG user icon |
| Homepage tabs | `.section-tabs` | **Remove** | Eliminated — redundant with catalogue cards |
| Name suggestions | `.suggestions a` | Keep | Token update only |
| Name taken options | `.name-taken-options` | Keep | Token update only |

### Icon Implementation Strategy

All emoji and CSS `content: '...'` pseudo-element icons replaced with inline Feather SVG paths embedded directly in Django templates. No CDN dependency. No font file.

Standard icon spec for all instances:
```html
<svg width="N" height="N" viewBox="0 0 24 24" fill="none"
     stroke="currentColor" stroke-width="2"
     stroke-linecap="round" stroke-linejoin="round">
  <!-- feather path -->
</svg>
```

Icon assignments:

| Context | Feather icon | Colour |
|---|---|---|
| Gift list section / catalogue | `gift` | `#588157` on `#cfe3c9` pill |
| Events section / catalogue | `calendar` | `#3a5a40` on `#dce8d2` pill |
| Password gate heading | `lock` | `#3a5a40` |
| Name gate heading | `user` | `#3a5a40` |
| Assign button | `check` | `#fff` on `#588157` |
| Edit button | `edit-2` | `#3a5a40` |
| Delete button | `trash-2` | `#fff` on `#b94040` |
| Delete dialog icon | `trash-2` | `#b94040` on `#f9efef` |
| Update claims link | `refresh-cw` | `#3a5a40` |
| Category assign button | `user-plus` | `#fff` on `#3a5a40` |
| Category release button | `x-circle` | `#3a5a40` outline |
| Archived state screen | `archive` | `#5a6b52` on `#e8e4da` |
| In-progress state screen | `clock` | `#588157` on `#cfe3c9` |
| Logo mark in header | `star` | `#dad7cd` at 50% opacity |
| Guest user in header | `user` inline | `#dad7cd` |
| Food category example | `coffee` | `#344e41` |
| Music category example | `music` | `#344e41` |

### Homepage Section-Tabs Removal

The `.section-tabs` block and all associated CSS is removed entirely. The homepage becomes two catalogue cards only, matching the `home.html` template's `.grid` section. The tabs added navigation without adding information — both links were already visible as card headers one scroll-unit below.

---

## UX Consistency Patterns

### Button Hierarchy

Three visual tiers, strictly applied per row:

| Tier | Class | Use case | Visual |
|---|---|---|---|
| Primary action | `.btn-success` | Claim / Assign | `#588157` fill, white text, check icon |
| Destructive action | `.btn-danger` | Delete | `#b94040` fill, white text, trash icon |
| Subordinate action | `.btn-link` | Edit | No fill, `#3a5a40` text, pencil icon, underline on hover |
| Gate / form submit | `.btn-primary` | Enter password, submit name | `#3a5a40` fill, full width |
| Secondary / release | `.btn-secondary` | Unclaim category, Cancel in dialog | No fill, `#bbb8ae` border |

Rule: never more than one filled button per `.item-actions` group. Assign and Delete cannot both be filled. Edit is always the subordinate link.

### Feedback Patterns

| Situation | Pattern |
|---|---|
| Successful claim | Item row background flips to `#cfe3c9`; name text strikethrough in `#588157`; claimant name appears below item name |
| Race condition (item just claimed) | Modal dialog with Fibonacci backoff message; refresh button; no page reload |
| Wrong password | Generic inline error below input (`#b94040` text on `#f9efef` bg); no hint about correct value |
| Name taken | Inline suggestion chips appear below input; reclaim option below chips |
| Delete confirmation | Modal with trash icon circle, item name in bold, two-button group (Usuń / Anuluj) |
| Category locked | Category items 65% opacity; "Zwolnij" button replaces "Przypisz całą kategorię"; claimant name shown in header |

### Navigation Patterns

- Header is sticky, always shows logo + guest name + Zmień link
- Logo always links to `/` (homepage catalogue)
- No breadcrumbs — single-level depth makes them redundant
- Back navigation via browser — no explicit back buttons
- Index pages (`/gifts/`, `/events/`) linked from homepage catalogue cards only; the tabs that duplicated this are removed

### Form Patterns

- Labels always uppercase, small-caps style, above the input
- Single input per gate screen — full width, autofocus on load
- Submit button always full width on gate screens
- Error appears below the input that caused it, never above the form
- Name suggestions appear as tappable chips between the input and the submit button

### Progress Patterns

- Progress bar: 4px height, `#3a5a40` fill, `#bbb8ae` track, always below the header actions row
- Progress text: `X / Y` format, muted label, bold numbers in `#3a5a40`
- Fully claimed state: progress fill turns `#588157`, progress text shows full count
- Homepage catalogue: progress badge `X/Y` right-aligned in each entry list row; fully claimed badge turns `#588157`

### Empty and State Screens

| State | Icon | Copy style | Background |
|---|---|---|---|
| No items in list | — | Italic faded text inline, not a full screen | — |
| Archived | `archive` in muted circle | Calm, two sentences | Standard linen bg |
| In progress / no items yet | `clock` in green circle | Friendly, one sentence | Standard linen bg |
| Empty catalogue section | Italic empty string | No icon, no heading | Inside catalogue card |

---

## Responsive Design and Accessibility

### Responsive Strategy

Mobile-first. One breakpoint: `≤600px`. No tablet-specific breakpoint — the single-column mobile layout scales well to 768px without adjustment.

| Element | Mobile (≤600px) | Desktop (>600px) |
|---|---|---|
| `.item` rows | Stack vertically: info above, actions below, full-width action buttons | Horizontal: info left, actions right |
| `.gate-container` | `margin: 1.5rem auto`, tighter padding | `margin: 3rem auto` |
| Homepage `.grid` | Single column | Two columns (currently single column — acceptable) |
| Header guest name | `max-width: 80px`, truncated | `max-width: 120px` |
| Category header | Wraps on two lines if needed | Single line |
| Dialog `.btn-group` | Stacks on very small screens | Side by side |

### Touch Targets

All interactive elements: `min-height: 44px`. On mobile, `.item` action buttons expand to `min-height: 40px` (acceptable — the item card itself provides additional tap area).

### Accessibility Requirements

- All SVG icons used decoratively: `aria-hidden="true"`
- Icon-only buttons (if any): `aria-label` attribute required — none currently exist
- Form inputs: `<label>` associated via `for`/`id` pair
- Colour contrast verified for all text/background combinations (see Visual Foundation)
- `<input autofocus>` on gate screens — keyboard users land immediately in the input
- `Cache-Control: no-store` on all gated pages — prevents back-button cache exposure
- Session cookie settings: `HttpOnly`, `SameSite=Lax`, `Secure` over HTTPS

### Animation and Motion

- Progress bar fill: `transition: width 300ms ease` — provides satisfying feedback without distraction
- Dialog overlay: `fadeIn 150ms ease`, dialog panel: `slideUp 200ms ease` — lightweight, not dramatic
- Button active state: `transform: scale(0.97)` — tactile micro-feedback on tap
- No animation on claimed item state flip — instantaneous is more satisfying than animated for a claim

### i18n Readiness (v4)

- All user-facing copy uses Django `{% trans %}`/`gettext` — no hardcoded strings in templates
- `.po` files in `core/locale/` and per-app `locale/` directories
- Both paths listed in `LOCALE_PATHS` in `settings.py`
- `compilemessages` runs as Docker image build step
- No directional (RTL) requirements identified — Polish is LTR only
