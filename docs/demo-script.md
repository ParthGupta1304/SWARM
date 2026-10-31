# Two-minute Phase 1 demo

Start the normal demo with `uv run --no-sync python -m swarm.demo`. Keep the
marketplace and console in separate tabs. Prepare the selected run before the
presentation; provider rate limits make a full benchmark longer than two minutes.

For an offline fallback, use
`uv run --no-sync python -m swarm.demo --scripted --port 8081`.
Keep its scripted-fixture banner visible. Its model choices and token counts are
synthetic, while marketplace actions, detectors and replay are real. Do not
present these counts as real AI detection performance.

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:20 | Bazaar storefront, product, account selector, cart | “This is Bazaar, our running multi-user marketplace. Normal purchases work, but it has eight controlled correctness and abuse failures.” |
| 0:20–0:40 | Saved isolated baseline results | “First, each persona uses a separate seeded snapshot. They cannot collide. Here is what that condition actually found.” Use the saved result's real figures, or identify the offline fixture explicitly. |
| 0:40–1:10 | Swarm activity, ten actors, shared-resource graph | “Now ten normal users and adversaries share one app. They have measurable goals and bounded budgets. Their business actions are synchronized to exercise interactions.” |
| 1:10–1:40 | One finding, reduced request sequence, verification activity | “This failure was replayed on a different fresh database. These are the actions and necessary actors. Other agents active in the same round were removed from the reproduction.” |
| 1:40–2:00 | Baseline/swarm comparison, cost and acceptance status | “We report the full three-seed comparison, mean and range, assessed precision and cost. A scripted fixture cannot pass AI acceptance; a human also checks evidence before acceptance.” |

For a live marketplace walkthrough, buy as `bob_buyer`, switch to
`alice_seller` to fulfil the order, then switch back to write a review. The
synthetic account selector intentionally makes multi-user demonstrations easy.
Seller and sock-buyer accounts share an owner, but only fulfilled purchases
qualify for reviews. Blocked direct messages are rejected; item questions
exercise the planted alternate contact path.

If Groq is unavailable, play the recorded fallback or use the scripted mode.
The recording is a walkthrough of actual captured manual and scripted fixture
states, not a claim of uninterrupted live AI discovery. Phase 2 memory, auto-fix
and GitHub Actions are not part of this Phase 1 demonstration.

Recorded fallback: [two-minute captured UI walkthrough](demo/phase1-fallback.mp4).
It distinguishes manual shopping, scripted integration, and real Groq results.
