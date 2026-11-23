# Errata

[← Card flows](README.md)

## Errata submission (`#errata-submissions`)

**Entry:** `on_message` for `ERRATA_SUBMISSIONS` · background auto-promote every 5 min (same channel)

```mermaid
flowchart TD
  subgraph submit["Submission"]
    U["Line 1: card ID<br/>Body: errata description"] --> VAL{"ID exists<br/>set in HC9 family or PL1?"}
    VAL -->|no| STOP["Reject in-channel + delete"]
    VAL -->|yes| REP["Repost with DB image<br/>👍👎 + thread<br/>then delete original"]
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

Allowed sets are resolved via catalog set children of `CUBE_NAME` (`HC9`, `HC9_0`, `HC9_1`, …) plus `PL1`. Rejection pings go in `#errata-submissions` so the submitter sees them.

Auto-promote scans the last **14 days**, up to **200 messages**.

Hellpit resubmits still land in `#errata-tracking` (`ERRATA_TRACKING`) with ☑️ — that path is separate from user intake.

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
  ACC --> HF["Hellfall postcard sync<br/>(Hellfall uploads GCS)"]
  ACC --> RED["Reddit skipped (errata)"]
```
