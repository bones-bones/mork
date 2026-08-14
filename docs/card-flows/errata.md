# Errata

[← Card flows](README.md)

## Errata submission (`#errata-submissions`)

**Entry:** `#errata-submissions` message handler · background auto-promote every 5 min

```mermaid
flowchart TD
  subgraph submit["Submission"]
    U["Line 1: card ID<br/>Body: errata description"] --> VAL{"ID exists<br/>set is HC9.0 or HC9.1?"}
    VAL -->|no| STOP["Rejected + delete"]
    VAL -->|yes| REP["Replace with DB image<br/>👍👎 + thread"]
  end

  subgraph promote["Auto-promote"]
    REP --> CHK{"up − down > 20?"}
    CHK -->|no| WAIT["Wait for votes"]
    CHK -->|yes| MARK["✅ on errata post"]
    MARK --> VP["#veto-polls:<br/>Name by Creator<br/>Errata: {id}"]
    VP --> HVP["Veto poll setup"]
    HVP --> TXT["Errata body in veto thread"]
  end
```

Auto-promote scans the last **14 days**, up to **200 messages**.

---

## Admin instant errata

**Entry:** `!instaerrata` (admin or instaerrata-review role) with attachment + text:

```
Cardname by Author
Errata: <card id>
```

```mermaid
flowchart TD
  CMD["!instaerrata + attachment"] --> LOOKUP["Lookup card by ID"]
  LOOKUP --> VAL{"Image attached?"}
  VAL -->|no| ASK["Please attach an image file"]
  VAL -->|yes| TYPE{"File is image/*?"}
  TYPE -->|no| BAD["Must be an image"]
  TYPE -->|yes| ACC["Accept as errata"]
  ACC --> CL["Post to set's card-list channel"]
  ACC --> SH[("Database (Unapproved)")]
  ACC --> HF["GCS + Hellfall postcard sync"]
  ACC --> RED["Reddit skipped (errata)"]
```

---
