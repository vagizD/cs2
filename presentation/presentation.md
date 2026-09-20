# CS2 Roster Dynamics — 8-Minute Classroom Presentation Guide
**Research Question 1:** *"When a Top 30 team replaces 1 player, does performance on Tier 1 events sustainably improve?"*

## Presentation Deck Overview
- **Deck File:** [presentation/presentation.html](file:///home/vagiz/Desktop/desktop_vagiz/Programming/cs2-analysis/presentation/presentation.html)
- **Deep-Dive Technical Deck:** [presentation/index.html](file:///home/vagiz/Desktop/desktop_vagiz/Programming/cs2-analysis/presentation/index.html)
- **Total Slides:** 13 core slides + 2 appendix slides (15 slides total; target pacing: ~35–40s per core slide for an 8-minute presentation).
- **Stepping Control:** Boxes and cards are covered/hidden by default upon entering each slide. Press <kbd>→</kbd> or <kbd>Space</kbd> to reveal details one-by-one.

---

## Slide Breakdown & Speaker Notes (8-Minute Plan)

### Slide 1: Introduction to Field — Counter-Strike 2 (0:00 - 0:40)
- **Theme:** High-stakes esports ecosystem.
- **Visuals:** 3 clean stat cards (numbers-first design):
  1. **Real-Time 5v5 Shooter:**
     - **5 vs 5** active players
     - **< 200 ms** reaction times
     - **100 s** round limit
  2. **Global Arena Circuits:**
     - **15,000+** live arena fans
     - **1.5M+** online viewers
     - **$1.25M+** Major prize pool
  3. **Massive Financial Stakes:**
     - **$500K–$1M+** player buyout costs
     - **$25K–$50K+** monthly star salaries
     - **$40M+** team annual ecosystem
- **Talking Point:** Establish that CS2 is not just a video game; it is a high-capital corporate sports league where executive decisions carry millions of dollars in risk.

### Slide 2: Game Demo (~20s Audio/Visual Simulation) (0:40 - 1:20)
- **Theme:** Round intensity and mechanical demands.
- **Visuals:** Built-in Web Audio synthesizer player (simulating high-tempo round comms & tactical pacing) + 3 core mechanics:
  - **Instant Kill:** One headshot kills with AK-47 & AWP.
  - **No Respawns:** Eliminated players stay dead until next round.
  - **Round Economy:** Equipment purchased with earned prize money.
- **Talking Point:** Play the audio demo briefly (~10-15s). Emphasize that mistakes are irreversible, making micro-coordination and chemistry decisive.

### Slide 3: The Unit — Active Roster & Swapping (1:20 - 2:00)
- **Theme:** What constitutes a roster change.
- **Visuals:** Interactive 5-man roster slots:
  - Slots 1–4 (IGL, AWP, Entry, Support) retained.
  - Slot 5 benched ➔ New player signed.
  - Cards: Only active 5 matter (no mid-game subs); High financial risk ($200K–$1M+ buyouts).
- **Talking Point:** Unlike football or basketball, there is no bench rotation during games. Changing 20% of your unit fundamentally destabilizes the system.

### Slide 4: Research Question (RQ1) (2:00 - 2:40)
- **Theme:** Testing executive competence.
- **Visuals:** Big highlighted quote:
  > *“When a Top 30 team replaces 1 player, does performance on Tier 1 events sustainably improve?”*
  - Key takeaway note: *"We are testing how effective esports management decisions really are."*
- **Talking Point:** When a team benches a player and signs a star replacement, do they actually get better over time, or are they just reacting to short-term panic?

### Slide 5: Methodology — Workflow: Raw Web to Insights (2:40 - 3:30)
- **Theme:** Data collection and analysis pipeline.
- **Visuals:** 6 vertical steps + **HLTV.org Website Screenshot Preview**:
  - **Step 1:** HLTV.org Source Data *(Authentic live ranking preview showing NAVI, Vitality, MOUZ, FaZe)*
  - **Step 2:** Collect Web Pages (Raw HTML match & ranking logs)
  - **Step 3:** SQLite Relational Database
  - **Step 4:** Infer Roster Changes (Algorithmic 1-player delta detection)
  - **Step 5:** Aggregate Statistics per Move (Relative weeks [−12 to +12], min. 2 matches/window)
  - **Step 6:** Make Empirical Conclusion
- **Talking Point:** Explain that HLTV is the esports gold standard. Show the live screenshot and explain how raw web pages were turned into an analytical SQLite database.

### Slide 6: Data Architecture — Relational Database Schema (3:30 - 4:10)
- **Theme:** Relational hierarchy.
- **Visuals:** 5 structured tables:
  - `EVENT` ➔ `MATCH` ➔ `MAP` ➔ `PLAYER_MAP_STATS` + `RANKING_SNAPSHOT`.
- **Talking Point:** High-level events drill down to individual round player statistics and weekly 5-man lineups.

### Slide 7: Filtration Funnel — Isolating Moves (4:10 - 4:50)
- **Theme:** Isolating clean single-player moves in Tier 1.
- **Visuals:** Step-by-step funnel bars:
  1. All Snapshot Changes: **1,775**
  2. Team Held Top 30 Ranking: **456**
  3. Exactly 1 Player Swapped: **317**
  4. Snapshot History ±90 Days: **256**
  5. Clean Isolation Window (no other changes in ±90d): **70**
  6. $\ge 15$ Tier 1 Matches in ±90d: **39 Moves (1,107 Tier 1 Matches)**
- **Talking Point:** Explain why strict filtering is necessary: we must eliminate multi-player team disbandments, lower-tier farm events, and overlapping changes.

### Slide 8: Plot A — Match Win Rate Lifecycle (4:50 - 5:40)
- **Theme:** The 3-stage performance curve.
- **Visuals:** Standalone high-res Plot A crop:
  - **Stage I: Pre-Change Slump (Week −2):** Win rate bottoms out at **35%**. Morale erosion.
  - **Stage II: Adaptation Shock (Week +1):** Initial drop to **38%**. Playbook friction.
  - **Stage III: Synergy Peak (Week +8):** Climbs to **55%** (50–60 days). Roles solidify.
- **Talking Point:** Walk through the trajectory: teams do not improve immediately upon signing a player. There is an adaptation valley before peak synergy.

### Slide 9: Plot C — The 50% Coin Flip: Trend Dynamics (5:40 - 6:20)
- **Theme:** Long-term success rates.
- **Visuals:** Standalone high-res Plot C crop:
  - **50% Success Rate at +90 Days:** Reaches 50% vs. healthy baseline (and 51% net improvement over pre-period), confirming long-term tactical maturation.
  - **37% Perform Strictly Worse:** Over a third experience a net win rate drop (>5%).
  - **The $1M Coin Flip:** Massive investments yield odds equivalent to a coin toss.
- **Talking Point:** Even with months of preparation, an executive roster move is effectively a 50/50 bet.

### Slide 10: Strategic Impact — Why This Story Matters to Management (6:20 - 7:00)
- **Theme:** Strategic takeaways for team owners.
- **Visuals:** 2 strategic cards:
  - **A 50% Coin Flip for $1M:** Swapping a player yields a pure 50/50 outcome.
    - Success Rate (+90d): **50%**
    - Net Decline (>5% drop): **37%**
  - **Patience & Incomplete Data:** Lineups are disrupted before gathering enough data.
    - Same Signing Cut &le; 90d: **12%**
    - Another Role Swapped &le; 90d: **29%**
- **Talking Point:** Nearly a third of teams make another roster move within 90 days, aborting lineups before the 90-day synergy peak can materialize.

### Slide 11: Ethical Implications — The Human Toll of Roster Churn (7:00 - 7:35)
- **Theme:** Player wellbeing and corporate esports culture.
- **Visuals:** 3 cards:
  - **Pre-Change Bench Toxicity:** Playing knowing you are about to be benched.
  - **Scapegoating the 5th Player:** Replacing an individual to mask systemic coaching/organizational issues.
  - **Extreme Career Precarity:** Restrictive buyout contracts and short survival horizons with zero union protection.
- **Talking Point:** Remind the audience that behind these statistics are young players whose careers can be derailed by 60 days of executive impatience.

### Slide 12: Study Limitations — Practical & Statistical Realities (7:35 - 8:00)
- **Theme:** Honest reporting of data boundaries and unobserved variables.
- **Visuals:** 3 broad limitation cards (no chart on slide):
  - **Overlapping CIs:** Core 4 and Team 95% CIs overlap by &ge; 60% — strong directional signal rather than definitive mathematical proof.
  - **High-Quality Data Points, But Rare:** Strict Tier 1 isolation yields 39 pristine cases — trading sheer sample size for uncontaminated analytical rigor.
  - **Player Agency & Internal Friction:** Not all moves are performance cuts: players may retire, take breaks, seek transfers, or experience friction with teammates, coaches, or team politics.
- **Talking Point:** Conclude with scientific humility: we observe compelling operational patterns, but statistical overlap and human unobserved variables remind us that roster decisions involve nuanced personal dynamics.

### Slide 13: Conclusion & Q&A — Thanks! Questions? (8:00+)
- **Theme:** Official presentation conclusion and audience discussion.
- **Visuals:** Clean, bold centered typography (`Thanks! Questions?`) + direct appendix navigation links. No boxes, nothing hidden or waiting to be revealed.
- **Presenter Action:** Open the floor for professor/student questions. Use the on-screen jump buttons to smoothly access relevant appendix slides during discussion.

### Slide 14: Appendix — Metric Validation & Team Rating Breakdown (Q&A / Backup)
- **Theme:** Metric foundation and detailed rating trajectories.
- **Visuals:** Interactive plot switcher (2 plots on 1 slide):
  - **View 1 (Default): Rating vs. Win Rate Correlation (*r* = +0.87, *R*² = 0.76):** Confirms that HLTV rating is a statistically reliable predictor of Tier 1 match wins.
  - **View 2 (Revealed on Button Hit / Next): Plot B Rating Dynamics:** Core 4 vs. Team rating trajectories, showing outgoing player deficit prior to benching and overlapping 95% CIs.
- **Presenter Controls:** Click toggle pills or hit the on-screen button / <kbd>Space</kbd> clicker to toggle between Metric Correlation and Plot B.

### Slide 15: Appendix — Dual Baseline Distribution Comparison (Q&A / Backup)
- **Theme:** Comparative evaluation of baseline definitions.
- **Visuals:** Standalone high-res comparison: Healthy Baseline (Weeks −12 to −4) vs. Full Pre-Period with Slump (Weeks −12 to 0).
- **Talking Point:** Demonstrates that even when comparing against an unslumped healthy baseline, the 50% coin flip holds true.