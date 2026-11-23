# Overview

[← Card flows](README.md)

## End-to-end lifecycle

```mermaid
flowchart TD
  subgraph submit["1 · Community submission"]
    A["User posts to #submissions<br/>CardName by @author(;s) + image"] --> IN{"Intake OK? not Tue/Sat Eastern · image · name · cooldown · no @ in title"}
    IN -->|no| X["Ignore, ping, closed, or return image<br/>#submissions-discussion"]
    IN -->|yes| MAG{"Feeling lucky?"}
    MAG -->|no| POLL["Mork reposts poll<br/>👍 👎 ❌ + thread"]
    POLL --> LOOP["Background check · 5 min"]
    LOOP --> CHK{"Mork poll:<br/>up − down ≥ threshold<br/>age ≥ 1 day?"}
    CHK -->|no| REMINDER_CHECK{"margin ≥ threshold−10<br/>age ≥ 5.5 d"}
    REMINDER_CHECK -->|yes| REM["🕛 nearing-end ping"]
    REM --> POLL
    REMINDER_CHECK -->|no| POLL
    CHK -->|yes| GRAVE_CHECK{"Admin 🪦 reacted?<br/>(HC9.1 only)"}
    GRAVE_CHECK -->|yes| GRAVE_ACCEPT["accept → HCV graveyard"]
    GRAVE_CHECK -->|no| ADMIN_SAFEGUARD{"Admin 👍 among upvotes<br/>or downvotes ≠ 1?"}
    ADMIN_SAFEGUARD -->|no| ADM["DM admin to verify"]
    ADM --> POLL
  end

  MAG -->|yes| VETO_FLOW
  ADMIN_SAFEGUARD -->|yes| VETO_FLOW

  subgraph veto["2 · Veto council"]
    VETO_FLOW["Post to #veto-polls"] --> H["Veto poll setup<br/>reactions + locked thread + hellpit"]
    H --> I["Council votes (accept, veto, errata)"]
    I --> J["someone runs !compileveto in #veto-discussion eventually"]
    J --> K{"Veto poll triage"}
    K -->|accepted| L["accept → Active set"]
    K -->|vetoed| M["accept → HCV graveyard"]
    K -->|errata| N["NEEDS ERRATA list"]
    K -->|purgatory| O["VETO HELL ping"]
    K -.->|judge react parallel| P["Tagged in parallel<br/>(does not block classification)"]
  end

  subgraph persist["3 · Persistence"]
    L --> Q[("Database (Unapproved)<br/>+ Hellfall postcard")]
    M --> Q
    GRAVE_ACCEPT --> Q
    Q --> R["Manual mod copy → Database"]
    R --> S["Search / Hellfall / print scripts"]
  end
```
