# Story 3: Pressure Cooker - LAN vs Online & Tier Dynamics (`plan/storytelling/`)

## 1. Problem Statement
Evaluating how physical stage pressure (`is_lan=1` vs `is_lan=0`) and event tier classifications (`Tier 1`, `Tier 2`, `Tier 3`, `Qualifier`) affect team consistency and tournament format volatility.

---

## 2. Mathematical Equations & Metrics

### 2.1 Environmental Rating Shift ($\Delta \text{LAN}$)
$$\Delta \text{LAN} = \overline{\text{Rating}}_{\text{LAN}} - \overline{\text{Rating}}_{\text{Online}}$$

### 2.2 Upset Volatility Index ($\text{UVI}$)
$$\text{UVI} = \frac{\text{Actual Upsets}}{\text{Total Matches}} \quad \text{where Upset occurs when } \text{Elo}_{\text{loser}} - \text{Elo}_{\text{winner}} > 100$$

---

## 3. Visualization Ideas & Outputs

1. **Online vs LAN Performance Boxplot**: Individual player rating distribution on LAN vs Online.
2. **Format Volatility Bar Chart**: Upset percentage comparison between BO1 and BO3 matches across Tier 1, Tier 2, Tier 3, and Qualifiers.
3. **Tier Transition Sankey Diagram**: Visualizing how teams transition between Tier 3/2 and Tier 1 events over time.
