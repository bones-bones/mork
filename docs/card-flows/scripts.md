# Scripts & percolation

[← Card flows](README.md)

Misc card handling stuff, like the printabledb workflow

## Printable / printing pipeline

```mermaid
flowchart TD
  subgraph source
    DB[("Database / Tokens sheets")]
  end

  subgraph pipeline
    DL["Download from sheets"] --> ST["Border stretch transform"]
    ST --> GCS["Printable images GCS bucket"]
    GCS --> PDB[("Printable DB sheet")]
  end

  subgraph qa
    REV["Vision QA review"]
    FIX["Border fix + re-upload"]
    LOCAL["Local one-card pipeline"]
  end

  DB --> DL
  PDB --> REV
  PDB --> FIX
  LOCAL --> ST
```

---

## Hellfall / catalog sync

```mermaid
flowchart LR
  HF["Hellfall JSON / catalog"] --> S1["Sync Hellfall IDs"]
  HF --> S2["Sync oracle IDs"]
  HF --> S3["Sync tags"]
  S1 --> UA[("Database (Unapproved)")]
  S2 --> UA
  S3 --> UA
```

Card acceptance also writes Hellfall UUID and oracle_id on accept via postcard sync.

---

## Manual mod percolation

No bot automation — mods transcribe by hand.

```mermaid
flowchart LR
  UA[("Database (Unapproved)")] -->|"mod transcribes"| AP[("Database approved")]
  AP --> MORK["Bot search / !info"]
  AP --> HF["Hellfall"]
  AP --> CUBE["Cube XML / Draftmancer"]
  AP --> PRINT["Print scripts"]
```
