# Story 4: Mononational vs International Rosters (`plan/storytelling/`)

## 1. Problem Statement
Comparing single-country rosters (mononational, e.g., Denmark, Mongolia, Brazil) against multi-national international lineups in terms of communication stability, spell longevity, and performance ceilings.

---

## 2. Mathematical Equations & Metrics

### 2.1 Roster Diversity Index ($D$)
$$D = \text{Count of unique } \text{country\_name} \text{ in 5-player lineup}$$
- $D = 1$: Mononational roster
- $D \ge 3$: International mixed roster

### 2.2 Roster Spell Survival Probability $S(t)$
Kaplan-Meier estimator of roster survival without change at time $t$ days:
$$\hat{S}(t) = \prod_{t_i \le t} \left(1 - \frac{d_i}{n_i}\right)$$
- $d_i$: Roster changes at day $t_i$
- $n_i$: Active roster spells at risk

---

## 3. Visualization Ideas & Outputs

1. **Kaplan-Meier Survival Curve**: Lineup duration survival curves comparing $D=1$ (Mononational) vs $D \ge 3$ (International).
2. **Global Player Talent Density Map**: Heatmap of top-30 player counts by `country_name`.
3. **Peak Elo vs Roster Lifespan Matrix**: Scatterplot of maximum Elo reached versus days together as a lineup.
