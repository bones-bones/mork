# Submissions

[← Card flows](README.md)

## Standard card submission

**Entry:** `#submissions` · background check every 5 min · `!wait` for cooldown

Closed all day **Tuesday and Saturday** in US Eastern (`America/New_York`, EST/EDT). Those days do not count toward the 22h cooldown. `#pause-projects` and other intake channels stay open.

### Happy path

```mermaid
flowchart TD
  U["User: CardName by @author(s) + image attachment"] --> CLOSED{"Tue or Sat<br/>US Eastern?"}
  CLOSED -->|yes| CLOSED_MSG["Post deleted<br/>#submissions-discussion · cooldown NOT consumed<br/>wait clock paused"]
  CLOSED -->|no| ATT{"Any attachment?"}
  ATT -->|no| MISS["Silent ignore — see validation"]
  ATT -->|yes| PING{"@ in card title?"}
  PING -->|yes| DM["DM user: no @ in title<br/>original post kept"]
  PING -->|no| NAME{"First line has card name?"}
  NAME -->|no| NONAME["#submissions-discussion:<br/>include card name + image returned<br/>Post deleted · cooldown NOT consumed"]
  NAME -->|yes| CD{"User is on the submission cooldown?"}
  CD -->|no| X["#submissions-discussion:<br/>wait N hours + delete post"]
  CD -->|yes| COOL["Write cooldown timestamp"]
  COOL --> DEL["Delete user post"]
  DEL --> MAGIC{"Feeling lucky?"}
  MAGIC -->|yes| VP["#veto-polls + discussion + log<br/>(no community poll)"]
  MAGIC -->|no| POLL["Mork reposts with 👍👎❌ + thread"]

  POLL --> LOOP["Background check · 5 min"]
  LOOP --> CHK{"Mork poll:<br/>up − down ≥ 60<br/>age ≥ 1 day?"}
  CHK -->|no| REMINDER_CHECK{"margin ≥ 55<br/>age ≥ 5.5 d"}
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
  POST["User posts in #submissions"] --> CLOSED{"Tue or Sat<br/>US Eastern?"}
  CLOSED -->|yes| CL["Post deleted · #submissions-discussion<br/>cooldown NOT consumed"]
  CLOSED -->|no| A{"Any attachment?"}

  A -->|no| MI["Missing image<br/>No bot reply<br/>Post stays in channel<br/>Cooldown NOT consumed"]
  A -->|yes| B{"First line has card name?<br/>(non-empty after trim)"}
  B -->|yes| NN["Missing name<br/>Ping in #submissions-discussion<br/>Image returned · post deleted<br/>Cooldown NOT consumed"]
  B -->|no| OK["Normal submission flow"]

  A -->|non-image file<br/>e.g. .pdf| NI["No image-type check on intake<br/>Poll still created"]
  NI --> GAL["Excluded from day markers /<br/>daily submissions gallery"]
  NI --> CHK["Background check still counts it<br/>if Mork poll has attachment"]
```

| Case                     | Trigger                           | Bot response                                 | User post                  | Cooldown       |
| ------------------------ | --------------------------------- | -------------------------------------------- | -------------------------- | -------------- |
| **Closed day**           | Tuesday or Saturday, US Eastern | `@here` in `#submissions` and `#submissions-discussion`; post deleted | Deleted                    | Not written; clock paused |
| **Missing image**        | No attachment                     | None (silent ignore)                         | **Kept** in `#submissions` | Not written    |
| **Missing card name**    | Attachment present, empty/whitespace first line | `#submissions-discussion`: include card name + image returned | Deleted                    | Not written    |
| **`@` in title**         | `@` in first line                 | DM: no `@` allowed                           | Kept                       | Not written    |
| **On cooldown**          | Submitted within 22 open hours (Tue/Sat Eastern excluded) | `#submissions-discussion`: wait message      | Deleted                    | Already active |
| **Non-image attachment** | e.g. PDF attached                 | Poll created anyway                          | Deleted (reposted as poll) | Consumed       |
| **Magic skip**           | 1/4001 roll                       | Straight to veto (no poll)                   | Deleted                    | Consumed       |

**Closed day:** Checked first. Any user post in `#submissions` on Tuesday or Saturday (US Eastern) is deleted and noted in `#submissions-discussion`. Cooldown timestamps are not written, and elapsed wait time ignores those days. At the start of each closed day Mork posts `@here THE GATES OF HELL ARE CLOSED` in `#submissions` and `#submissions-discussion`; at the start of Wednesday and Sunday (US Eastern) Mork posts `@here THE GATES OF HELL HAVE OPENED` in those channels.

**Missing name:** Intake bails before cooldown write or repost. The card image is reattached in `#submissions-discussion` so the user can fix the title and resubmit. Whitespace-only first lines count as missing.

**Missing image:** Intake bails before cooldown, name checks, or repost. Text-only posts stay in channel with no ping to attach an image. Open days only; closed days delete the post and note the attempt in `#submissions-discussion` instead.

**Image detection elsewhere:** Day markers and the daily submissions gallery only count messages whose first attachment is an image (`image/*` content type or `.png` / `.jpg` / `.jpeg` / `.gif` / `.webp` / `.bmp`). That filter does not apply at initial `#submissions` intake.

---

## Masterpiece / Pause Projects submission

Same intake validation as standard submission (attachment, `@` in title, card name, cooldown); different channel, poll threshold, and cooldown state file. Tuesday/Saturday closures apply only to `#submissions`.

```mermaid
flowchart TD
  U["User posts to #pause-projects"] --> ATT{"Any attachment?"}
  ATT -->|no| MISS["Silent ignore<br/>(same as #submissions missing image)"]
  ATT -->|yes| NAME{"First line has card name?"}
  NAME -->|no| NONAME["#submissions-discussion:<br/>include card name + image returned<br/>Post deleted · cooldown NOT consumed"]
  NAME -->|yes| PING{"@ in card title?"}
  PING -->|yes| DM["DM user: no @ in title<br/>original post kept"]
  PING -->|no| CD{"User on masterpiece cooldown?"}
  CD -->|no| WAIT["#submissions-discussion:<br/>wait message + delete post"]
  CD -->|yes| COOL["Write masterpiece cooldown timestamp"]
  COOL --> POLL["Mork poll 👍👎❌"]
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
  POLL --> LOOP["Background check · 5 min"]
  LOOP --> CHK{"Mork poll:<br/>up − down ≥ 5<br/>age ≥ 1 day?"}
  CHK -->|no| POLL
  CHK -->|yes| ACC["Accept token"]
  ACC --> CL["Post #token-list"]
  ACC --> DRV["Upload to token folder"]
  ACC --> SH[("Tokens Database (Unapproved)")]
```

---

## Scube Lair submission & acceptance

**Entry:** `#scube-lair-submissions` · admin 🥇/🥈 reaction

```mermaid
flowchart TD
  U["User posts card name + image"] --> ATT{"Any attachment?"}
  ATT -->|no| MISS["Silent ignore"]
  ATT -->|yes| NAME{"First line has card name?"}
  NAME -->|no| NONAME["Scube lair discussion:<br/>include card name + image returned<br/>Post deleted"]
  NAME -->|yes| V["Mork adds 👍👎"]
  V --> THREAD["Public thread on submission<br/>(card name)"]
  THREAD --> MED{"Admin reacts 🥇 or 🥈?"}
  MED -->|no| WAIT["Community votes only"]
  MED -->|🥈| VETO["Accept as HCV.SCL → veto card list"]
  MED -->|🥇| TITLE{"First line has card name?"}
  TITLE -->|no| REJ["Reject acceptance<br/>(no ✅)"]
  TITLE -->|yes| PIN["Read Set: from pinned prompt"]
  PIN -->|no set| NOSET["DM admin:<br/>no set found"]
  PIN -->|found| SL["Accept → secret lair channel"]
  VETO --> ACC["GCS + mandatory Hellfall postcard"]
  SL --> ACC
  ACC --> SH[("Database (Unapproved)")]
  ACC --> OK["✅ on submission"]
```

| Case                  | Trigger                           | Bot response                                 | User post |
| --------------------- | --------------------------------- | -------------------------------------------- | --------- |
| **Missing image**     | No attachment                     | None (silent ignore)                         | Kept      |
| **Valid submission**  | Attachment + card name on first line | 👍👎 + public discussion thread (card name) | Kept      |
| **Missing card name** | Attachment present, empty/whitespace first line | Scube lair discussion channel: include card name + image returned | Deleted   |
| **Missing set (gold)** | Admin 🥇, no pin or unparsable `Set:` on first pin | DM to admin | Kept      |

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
