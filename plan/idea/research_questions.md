# Research Questions & Scope (`plan/idea/`)

## 1. Primary Research Question

> **When a professional Counter-Strike 2 team replaces one of its five active players, does its performance improve, and is any improvement sustained?**

In Counter-Strike 2, active lineups consist of exactly five players with no real-time match-day substitution. Replacing a single player alters 20% of the active roster and fundamentally disrupts tactical roles, communication, in-game leadership, and chemistry.

---

## 2. Core Research Hypotheses

1. **Pre-Change Decline (Management under pressure)**: Roster changes are preceded by a statistically significant 30-to-60 day decline in team performance and Elo rating.
2. **Short-Term "Honeymoon" Spike**: Teams experience a temporary performance boost during the initial 1–4 weeks due to tactical unpredictability and renewed motivation.
3. **Long-Term Convergence**: After 90 days, performance returns toward the team's historical baseline unless the incoming player quality delta ($\Delta \text{Quality}$) is substantially positive.

---

## 3. Secondary Research Questions

- **Role Dynamics**: Does replacing an In-Game Leader (`is_captain=1`) cause higher initial win rate volatility than replacing a Main AWPer (`is_awp=1`) or Rifler?
- **Competitive Environment**: How does performance vary between LAN tournaments (`is_lan=1`) and Online events across event tiers (`Tier 1`, `Tier 2`, `Tier 3`, `Qualifier`)?
- **Roster Composition**: Do single-country (mononational) lineups sustain longer roster spell durations and higher ranking stability than multi-country international lineups?

---

## 4. Cohort & Scope Boundaries

- **Dynamic Cohort**: Any team that appeared in the HLTV Top 30 at any point during the 2-year study window.
- **Survivor Bias Prevention**: Avoid filtering only today's Top 30 teams, which would exclude failed rosters and bias results toward surviving organizations.
- **Analysis Window**: 90 days before ($t = -13$ weeks) through 90 days after ($t = +13$ weeks) each classified roster change.
