# Story 2: The Role Dilemma - Captains vs AWPers (`plan/storytelling/`)

## 1. Problem Statement
Analyzing how specialized roles (`is_captain` / In-Game Leaders vs `is_awp` / Main AWPers vs Riflers) impact tactical stability, entry conversion, and firepower dispersion.

---

## 2. Mathematical Equations & Metrics

### 2.1 Opening Kill Conversion Ratio
$$\text{OpK Ratio} = \frac{\sum \text{opening\_kills}}{\sum \text{opening\_kills} + \sum \text{opening\_deaths}}$$

### 2.2 Firepower Dispersion Index ($\sigma_{\text{ADR}}$)
$$\sigma_{\text{ADR}} = \sqrt{\frac{1}{5} \sum_{i=1}^{5} (\text{ADR}_i - \overline{\text{ADR}})^2}$$
- **High $\sigma_{\text{ADR}}$**: Heavy reliance on 1–2 star players.
- **Low $\sigma_{\text{ADR}}$**: Balanced firepower distribution across the roster.

### 2.3 Clutch Efficiency Factor
$$\text{Clutch Factor} = \frac{\sum \text{clutches\_won}}{\text{Maps Played}}$$

---

## 3. Visualization Ideas & Outputs

1. **Role Trajectory Comparison**: Post-change win rate trajectories split by replaced role (Captain vs AWPer vs Rifler).
2. **AWP Replacement Conversion Scatterplot**: Pre- vs post-move opening kill ratio vs map win rate.
3. **Firepower Balance Radar Chart**: Comparing team combat metrics (`headshot_kills`, `multi_kills`, `flash_assists`, ADR) for Top-5 vs Top-30 teams.
