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
    LOOP -- no --> CHK{"Mork poll:<br/>up − down ≥ threshold<br/>age ≥ 1 day?"}
    CHK -- no --> REMINDER_CHECK{"margin ≥ 50<br/>age ≥ 5.5 d"}
    REMINDER_CHECK -- yes --> REM["🕛 nearing-end ping"]


    CHK -- yes --> ADMIN_SAFEGUARD{"Has an admin 👍 or is there at least one downvote"}

    ADMIN_SAFEGUARD -- no --> ADM["DM admin to verify"]
    ADMIN_SAFEGUARD -->|yes| PROMO["promote_from_submissions<br/>Hellfall + unapproved sheet"]
  end

  MAG -->|yes| VETO_FLOW
  PROMO --> VETO_FLOW

  subgraph veto["2 · Veto council"]
    VETO_FLOW["Post to #veto-polls"] --> H["Veto poll setup<br/>reactions + locked thread + hellpit"]
    H --> I["Council votes (accept, veto, errata)"]
    I --> J["someone runs !compileveto in #veto-discussion eventually"]
    J --> K{"Veto poll triage"}
    K -->|accepted| L["accept → Active set"]
    K -->|vetoed| M["accept → HCV graveyard"]
    K -->|errata| N["NEEDS ERRATA list"]
    K -->|purgatory| O["VETO HELL ping"]
    K -->|judge react| P["Tagged in parallel<br/>(does not block classification)"]
  end

  subgraph persist["3 · Persistence"]
    L --> FIN["accept_card finalize<br/>set + accepted order · no 2nd postcard"]
    M --> FIN
    N --> ACC_ERR["accept_card + postcard<br/>(errata — no early promote)"]
    FIN --> Q[("Hellfall catalog<br/>(postcard SoR)")]
    ACC_ERR --> Q
    FIN --> Q2[("Unapproved sheet<br/>optional dual-write")]
    ACC_ERR --> Q2
    Q --> S["Search / Hellfall / print scripts"]
    Q2 -.->|"legacy export only"| S
  end
```
