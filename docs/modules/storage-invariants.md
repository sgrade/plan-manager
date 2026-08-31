---
module_contract: plan-manager/storage-invariants
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-10
updated: 2026-08-10
---

# Module contract: storage invariants (the transactional core)

**Purpose.** One SQLite database (WAL, single process) carries ALL
coordination semantics. Correctness lives in single-writer transactions,
not in application-level locking — this concentration is what makes the
readiness join, claims, and acceptance race-free by construction. Every
other module builds on these guarantees instead of re-implementing them.

## Contract

- **Unit of work**: services own transactions, never repositories. One
  logical mutation = exactly one UoW = `BEGIN IMMEDIATE`, connection per
  UoW (never crossing an await or outliving the request), bounded jittered
  busy-retry, commit-or-rollback on every path.
- **Transactional outbox**: every mutation appends its typed event in the
  SAME transaction. No mutation without an event; no event without its
  mutation.
- **Write budget**: no template rendering, hashing of large payloads, or
  I/O beyond SQLite inside a write UoW (target < 50 ms per transaction).

## Invariants consumers may assume (and must never re-derive)

1. **Exactly-one claim per attempt** — the claim is a single CAS UPDATE
   (readiness predicate inside), serialized by the write lock;
   `RETURNING` delivers the claimed row.
2. **Fenced completion** — submit/heartbeat match `(agent, attempt)` and
   the expected status; zero rows = superseded, mutation refused.
3. **Acceptance atomicity** — verdict evaluation and the resolution write
   share one transaction, guarded by `status='SUBMITTED'`; two racing
   resolvers produce exactly one resolution.
4. **Readiness never lies** — readiness is a join evaluated at claim
   time; no counters, no cached flags, nothing to drift.
5. **Revision CAS** — a document revision lands only if `parent_rev`
   equals the current head (checked in-transaction); history never forks.
6. **Gap-free event feed** — `seq` is globally monotonic and visible in
   order; `seq > cursor` polling misses nothing; `feed_epoch` changes only
   when continuity breaks (lossy restore).
7. **Lazy expiry** — lease lapse is observed at read/claim/sweep time;
   the sweep materializes terminal EXPIRED and emits the lapse/expiry
   events; there is no background scheduler to fail.

## Consumers and their obligations

- **All services**: compose reads + writes inside ONE UoW per logical
  mutation; never open nested UoWs; never cache row state across
  transactions for decision-making.
- **Export**: reads under a single snapshot transaction; preserves `seq`
  and `feed_epoch`.
- **Nobody** touches SQL outside the storage layer (import-lint enforced).

## Non-goals

Multi-process writers (would reopen every MVCC hazard this design
deleted); ORM abstractions; portability shims. If PM outgrows one writer,
the migration is to Postgres with an explicit redesign of these
invariants — not a quiet driver swap.
