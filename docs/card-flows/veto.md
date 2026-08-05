# Veto

[← Card flows](README.md)

## Veto poll setup

**Entry:** Any new message in `#veto-polls` · also called from submission checks, errata flows, hellpit resubmit

```mermaid
flowchart TD
  MSG["Card message + attachment<br/>in #veto-polls"] --> RX["Add reactions:<br/>⏰ 👍 errata 👎 NERF BUFF 🤮 🤔"]
  RX --> VT["Create locked thread on veto message"]
  RX --> HP["Create private hellpit thread<br/>in #veto-polls-hellpit"]
  HP --> LINK["Cross-link thread URLs"]
  LINK --> PING["Ping veto council + judges + author(s)"]
```

---

## Veto poll triage

**Callers:** `!compileveto [count]` (processes results) · `!personalhell` (read-only purgatory list)

### Scan & filter

```mermaid
flowchart TD
  START["Scan veto polls"] --> PHRASE["Send random catchphrase"]
  PHRASE --> HIST["#veto-polls history<br/>last 6 weeks"]
  HIST --> LOOP["For each message"]

  LOOP --> ATT{"Has attachment?"}
  ATT -->|no| SKIP["skip"]
  ATT -->|yes| AGE{"age ≥ 1 day?"}
  AGE -->|no| SKIP
  AGE -->|yes| DONE{"Has ✅ or ❌?"}
  DONE -->|yes| SKIP
  DONE -->|no| COUNT["Count reactions"]
```

### Reaction counts

Missing reactions default to **−1** (not 0):

| Vote   | Emoji    | Count           |
| ------ | -------- | --------------- |
| Up     | 👍       | count or **−1** |
| Down   | 👎       | count or **−1** |
| Errata | Spelling | count or **−1** |

### Classification (if / elif chain)

Each eligible message lands in **exactly one** of four outcome buckets. Order matters — first match wins.

```mermaid
flowchart TD
  COUNT["up, down, errata counted"] --> JUDGE{"Has judge react?"}
  JUDGE -->|yes| JL["Also tag judge list<br/>(parallel, not a bucket)"]
  JUDGE --> E1{"errata > 4<br/>AND errata ≥ up<br/>AND errata ≥ down?"}
  JL --> E1
  E1 -->|yes| ERR["Needs errata"]
  E1 -->|no| E2{"down > 4<br/>AND down ≥ up<br/>AND down ≥ errata?"}
  E2 -->|yes| VET["Vetoed"]
  E2 -->|no| E3{"up > 5<br/>AND up ≥ down<br/>AND up ≥ errata?"}
  E3 -->|yes| ACC["Accepted"]
  E3 -->|no| PUR["Purgatory"]
```

**Threshold cheat sheet** (with missing reactions at −1):

| Outcome   | Minimum winning votes | Must also beat  |
| --------- | --------------------- | --------------- |
| Errata    | 5 errata (`> 4`)      | up and down     |
| Vetoed    | 5 down (`> 4`)        | up and errata   |
| Accepted  | 6 up (`> 5`)          | down and errata |
| Purgatory | everything else       | —               |

**Judge react:** Adds a parallel tag in addition to normal classification. `compileveto` and `personalhell` do not read that list — a judge-tagged card can still be accepted, vetoed, errata, or purgatory on the next compile.

### Batch limit (`!compileveto [count]`)

```mermaid
flowchart TD
  IN["Triage results + optional count"] --> MERGE["Merge accepted + veto + errata + purgatory<br/>(judge list excluded)"]
  MERGE --> SORT["Sort by created_at ascending<br/>(oldest first)"]
  SORT --> CAP{"count provided?"}
  CAP -->|yes| TAKE["Keep first N messages"]
  CAP -->|no| ALL["Keep all"]
  TAKE --> FILTER
  ALL --> FILTER
  FILTER["Filter each category<br/>to allowed IDs"] --> OUT["Results<br/>judge list unchanged"]
```

### Worked examples

| 👍  | 👎  | errata | Result        | Why                                    |
| --- | --- | ------ | ------------- | -------------------------------------- |
| 8   | 2   | 1      | **accepted**  | up > 5, up ≥ down, up ≥ errata         |
| 3   | 7   | 2      | **vetoed**    | down > 4, down ≥ up, down ≥ errata     |
| 4   | 4   | 6      | **errata**    | errata > 4, errata ≥ up, errata ≥ down |
| 4   | 3   | 2      | **purgatory** | no category clears its threshold       |
| 6   | 6   | 6      | **purgatory** | ties block all three winners           |
| 2   | 1   | −1     | **purgatory** | up ≤ 5                                 |

---

## Compile veto (batch processing)

**Entry:** `!compileveto` in `#veto-discussion` (veto council only)

```mermaid
flowchart TD
  CMD["!compileveto [count]"] --> TRI["Veto poll triage"]
  TRI --> LIM["Apply batch limit<br/>oldest N across categories"]

  LIM --> ACC["Accepted cards"]
  ACC --> AC1{"Errata card ID<br/>on message?"}
  AC1 -->|yes| SET1["Set from errata card's cardset"]
  AC1 -->|no| SET2["Set SOH → soh card list"]
  SET1 --> AC1B["Accept + GCS + Hellfall"]
  SET2 --> AC1B
  AC1B --> RD1{"> 5 cards?"}
  RD1 -->|yes| DEF["Defer to deferred_reddit/"]
  RD1 -->|no| RED1["Reddit accepted flair"]
  AC1B --> ARC1["Archive veto thread + ✅"]

  LIM --> VET["Vetoed cards"]
  VET --> AC2["Accept as HCV → veto card list"]
  AC2 --> RED2["Reddit vetoed flair"]
  AC2 --> ARC2["Archive + ✅"]

  LIM --> ERR["Errata cards"]
  ERR --> LIST["List in #veto-discussion<br/>NEEDS ERRATA"]
  ERR --> ARC3["Archive thread only"]

  LIM --> PUR["Purgatory > 6 days"]
  PUR --> PING["Ping council in veto thread"]
  PUR --> HELL["List as VETO HELL"]

  DEF --> CATCH["Auto redditcatchup 1/hour<br/>+ !redditcatchup N manual drain"]
```

## Hellpit resubmit (errata rework)

**Entry:** ✅ on a message in a `#veto-polls-hellpit` thread (admin/veto only)

```mermaid
flowchart TD
  RX["✅ in hellpit thread"] --> READ["Follow link → original veto-poll message"]
  READ --> REPOST["Repost fixed card to #veto-polls"]
  REPOST --> HVP["Veto poll setup (new poll)"]
  READ --> MARK["Mark original veto poll ❌"]
  MARK --> ERR["Copy to #errata-submissions with ☑️"]
```
