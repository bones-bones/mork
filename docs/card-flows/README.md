# Card flows

Mermaid diagrams for card-related workflows in Mork. Mork is mostly stateless, instead relying on reddit, discord, hellfall, and reddit.

## Flow index

| Doc                                  | Contents                                                                     |
| ------------------------------------ | ---------------------------------------------------------------------------- |
| [Overview](overview.md)              | End-to-end lifecycle                                                         |
| [Submissions](submissions.md)        | Standard, masterpiece, token, design hell, validation, magic roll            |
| [Veto](veto.md)                      | Poll setup, triage, compile veto, hellpit resubmit                           |
| [Errata](errata.md)                  | Errata channel, instaerrata, trusted sneak accept                            |
| [Acceptance](acceptance.md)          | accept_card persistence pipeline                                             |
| [Background](background.md)          | Cron loop, Reddit ↔ Discord (inbound / outbound), database lookup, auxiliary |
| [Scripts](scripts.md)                | Printable pipeline, Hellfall sync, manual percolation                        |
| [Post–Google Sheets](post-sheets.md) | Target flow once Hellfall replaces sheets (planned)                          |
