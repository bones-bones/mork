# Scripts & percolation

[← Card flows](README.md)

Misc card handling stuff, like the printabledb workflow

## Printable / printing pipeline

**Preferred source:** Hellfall catalog (`--printable-source catalog` on
[`scripts/download_and_upload_images_gcs.py`](../../scripts/download_and_upload_images_gcs.py)).
The Printable DB sheet remains the QA ledger (append/update after GCS upload).

Legacy **sheet** mode (`--printable-source sheet`, default) still scans the approved Database tab.

```mermaid
flowchart TD
  subgraph source
    CAT["Hellfall catalog JSON"]
    DB[("Database sheet (legacy)")]
  end

  subgraph pipeline
    DL["Download art URLs"] --> ST["Border stretch transform"]
    ST --> GCS["Printable images GCS bucket"]
    GCS --> PDB[("Printable DB sheet — QA ledger")]
  end

  subgraph qa
    REV["Vision QA review"]
    FIX["Border fix + re-upload"]
    LOCAL["Local one-card pipeline"]
  end

  CAT --> DL
  DB --> DL
  PDB --> REV
  PDB --> FIX
  LOCAL --> ST
```

Example (printable only, catalog):

```bash
python scripts/download_and_upload_images_gcs.py --printable-only --printable-source catalog
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

## Manual mod percolation (retired)

**Retired** for normal ops once Hellfall postcard is the approval path: accepted cards land in the
catalog without a mod transcribing unapproved → approved Database.

The unapproved/approved sheets may still receive optional dual-writes for export/backfill; do not
treat manual copy as a required step for search, Hellfall, or printables.

```mermaid
flowchart LR
  UA[("Database (Unapproved)")] -.->|"optional export / backfill"| AP[("Database approved")]
  POST["Hellfall postcard on accept"] --> CAT["Hellfall catalog"]
  CAT --> MORK["Bot search / !info"]
  CAT --> HF["Hellfall"]
  CAT --> CUBE["Cube XML / Draftmancer"]
  CAT --> PRINT["Print scripts (--printable-source catalog)"]
```
