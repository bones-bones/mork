# Submissions

[← Card flows](README.md)

## Standard card submission

**Entry:** `#submissions` · background check every 5 min · `!wait` for cooldown

### Happy path

```mermaid
flowchart TD
  U["User: CardName by @author(s) + image attachment"] --> ATT{"Any attachment?"}
  ATT -->|no| MISS["Silent ignore — see validation"]
  ATT -->|yes| PING{"@ in card title?"}
  PING -->|yes| DM["DM user: no @ in title<br/>original post kept"]
  PING -->|no| CD{"User is on the submission cooldown?"}
  CD -->|no| X["#submissions-discussion:<br/>wait N hours + delete post"]
  CD -->|yes| COOL["Write cooldown timestamp"]
  COOL --> NAME{"content non-empty?"}
  NAME -->|no| NONAME["#submissions-discussion:<br/>include card name + delete<br/>(cooldown consumed)"]
  NAME -->|yes| DEL["Delete user post"]
  DEL --> MAGIC{"Feeling lucky?"}
  MAGIC -->|yes| VP["#veto-polls + discussion + log<br/>(no community poll)"]
  MAGIC -->|no| POLL["Mork reposts with 👍👎❌ + thread"]

  POLL --> LOOP["Background check · 5 min"]
  LOOP --> CHK{"Mork poll:<br/>up − down ≥ 40<br/>age ≥ 1 day?"}
  CHK -->|no| REMINDER_CHECK{"margin ≥ 35<br/>age ≥ 5.5 d"}
  REMINDER_CHECK -->|yes| REM["🕛 nearing-end ping"]
  REM --> POLL
  REMINDER_CHECK -->|no| POLL
  CHK -->|yes| GRAVE_CHECK{"Admin 🪦 reacted?"}
  GRAVE_CHECK -->|yes| GY["accept → HCV graveyard"]
  GRAVE_CHECK -->|no| ADMIN_SAFEGUARD{"Admin 👍 among upvotes<br/>or downvotes ≠ 1?"}
  ADMIN_SAFEGUARD -->|no| ADM["DM admin to verify"]
  ADM --> POLL
  ADMIN_SAFEGUARD -->|yes| VP2["#veto-polls"]
  VP2 --> HVP["Veto poll setup"]
  VP --> HVP
  HVP --> ANN["#submissions-discussion + log"]
  ANN --> DEL2["Delete submission poll"]
  GY --> DEL2
```

### Missing / invalid submission cases

```mermaid
flowchart TD
  POST["User posts in #submissions"] --> A{"Any attachment?"}

  A -->|no| MI["Missing image<br/>No bot reply<br/>Post stays in channel<br/>Cooldown NOT consumed"]
  A -->|yes| B{"First line empty?<br/>(no card name)"}
  B -->|yes| NN["Missing name<br/>Ping in #submissions-discussion<br/>Delete post<br/>Cooldown IS consumed"]
  B -->|no| OK["Normal submission flow"]

  A -->|non-image file<br/>e.g. .pdf| NI["No image-type check on intake<br/>Poll still created"]
  NI --> GAL["Excluded from day markers /<br/>daily submissions gallery"]
  NI --> CHK["Background check still counts it<br/>if Mork poll has attachment"]
```

| Case                     | Trigger                           | Bot response                                 | User post                  | Cooldown       |
| ------------------------ | --------------------------------- | -------------------------------------------- | -------------------------- | -------------- |
| **Missing image**        | No attachment                     | None (silent ignore)                         | **Kept** in `#submissions` | Not written    |
| **Missing card name**    | Attachment present, empty content | `#submissions-discussion`: include card name | Deleted                    | **Consumed**   |
| **`@` in title**         | `@` in first line                 | DM: no `@` allowed                           | Kept                       | Not written    |
| **On cooldown**          | Submitted within 22 h             | `#submissions-discussion`: wait message      | Deleted                    | Already active |
| **Non-image attachment** | e.g. PDF attached                 | Poll created anyway                          | Deleted (reposted as poll) | Consumed       |
| **Magic skip**           | 1/4001 roll                       | Straight to veto (no poll)                   | Deleted                    | Consumed       |

**Missing image:** Intake bails before cooldown, name checks, or repost. Text-only posts stay in channel with no ping to attach an image.

**Image detection elsewhere:** Day markers and the daily submissions gallery only count messages whose first attachment is an image (`image/*` content type or `.png` / `.jpg` / `.jpeg` / `.gif` / `.webp` / `.bmp`). That filter does not apply at initial `#submissions` intake.

---

## Masterpiece / Pause Projects submission

Same shape as standard submission; different channel, threshold, and cooldown state file.

```mermaid
flowchart TD
  U["User posts to #pause-projects"] --> ATT{"Any attachment?"}
  ATT -->|no| MISS["Silent ignore<br/>(same as #submissions missing image)"]
  ATT -->|yes| CD["Separate cooldown file"]
  CD --> POLL["Mork poll 👍👎❌"]
  POLL --> CHK{"up − down ≥ 45<br/>age ≥ 1 day?"}
  CHK -->|yes| VP["#veto-polls"]
  VP --> HVP["Veto poll setup"]
  CHK -->|no, margin ≥ 40<br/>age ≥ 5.5 d| REM["🕛 reminder"]
  REM --> POLL
  CHK -->|no| POLL
```

---

## Token submission

**Entry:** `#token-submissions` · background check every 5 min

```mermaid
flowchart TD
  U["Line 1: TokenName by @user<br/>Line 2: RelatedCard; RelatedCard2<br/>+ image"] --> VAL{"Related cards exist?"}
  VAL -->|invalid| STOP["Ping in #submissions-discussion"]
  VAL -->|ok| POLL["Mork poll 👍👎❌"]
  POLL --> CHK{"up − down ≥ 5<br/>age ≥ 1 day?"}
  CHK -->|no| POLL
  CHK -->|yes| ACC["Accept token"]
  ACC --> CL["Post #token-list"]
  ACC --> DRV["Upload to token folder"]
  ACC --> SH[("Tokens Database (Unapproved)")]
```

---

## Design Hell submission & acceptance

**Entry:** `#design-hell-submissions` · admin 🥇/🥈 reaction

```mermaid
flowchart TD
  U["User posts card name + image"] --> V["Mork adds 👍👎"]
  V --> MED{"Admin reacts 🥇 or 🥈?"}
  MED -->|no| WAIT["Community votes only"]
  MED -->|🥈| VETO["Accept as HCV.S → veto card list"]
  MED -->|🥇| PIN["Read Set: from pinned prompt"]
  PIN --> SL["Accept → secret lair channel"]
  VETO --> ACC["GCS + mandatory Hellfall postcard"]
  SL --> ACC
  ACC --> SH[("Database (Unapproved)")]
  ACC --> OK["✅ on submission"]
```

---

## Magic easter egg

```mermaid
flowchart TD
  SUB["Any standard or masterpiece submission"] --> ROLL{"random 1/4001"}
  ROLL -->|yes| SKIP["Skip community poll"]
  SKIP --> VP["Direct to #veto-polls + discussion + log"]
  ROLL -->|no| NORMAL["Normal poll flow"]
```

The roll range is bumped by 1000 each time it fires.
