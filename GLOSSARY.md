# Personal Hub

Lightweight web application for coordinating social occasions via gift lists and event role assignments.

## Language

**Guest**:
A visitor identified solely by a session-scoped unique display name without accounts or passwords.
_Avoid_: User, account, member

**Gift List**:
A password-gated collection of gift items associated with an occasion.
_Avoid_: Wishlist, registry

**Gift Item**:
A single requested gift belonging to a Gift List that can be claimed by at most one Guest.
_Avoid_: Product, gift

**Gift Claim**:
An exclusive assignment linking a Gift Item to a Guest Name.
_Avoid_: Reservation, booking

**Event**:
A password-gated gathering containing role categories and assignable roles.
_Avoid_: Occasion, party

**Role Category**:
A logical group of Roles within an Event that can be claimed individually or atomically as a whole.
_Avoid_: Group, section

**Role**:
A specific duty or task within a Role Category assigned to a Guest.
_Avoid_: Job, assignment

**Role Assignment**:
The association between a Role and a Guest Name, optionally flagged as claimed via category.
_Avoid_: Claim, allocation

**Category Lock**:
A state where an entire Role Category has been claimed by a Guest, locking all individual roles in that category from modification.
_Avoid_: Group reservation, bulk lock

**Audit Log**:
An immutable record created atomically alongside any claim, assignment, edit, or deletion action.
_Avoid_: History, event log

