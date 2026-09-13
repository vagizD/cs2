# Story 1: The Roster Change Paradox (`plan/storytelling/`)

## 1. Problem Statement
Evaluating whether 1-player roster replacements lead to genuine performance improvement or are simply a reflection of regression to the mean following a slump.

---

## 2. Mathematical Equations & Methodologies

### 2.1 Incoming Player Quality Delta
$$\Delta \text{Quality} = \overline{\text{Rating}}_{\text{incoming}}(t \in [-90, 0]) - \overline{\text{Rating}}_{\text{outgoing}}(t \in [-90, 0])$$

### 2.2 Opponent-Adjusted Performance Metric
$$\text{Performance}_{\text{adj}} = \text{Win}_{\text{match}} \times \left(1 + \frac{\text{Elo}_{\text{opponent}} - \text{Elo}_{\text{team}}}{400}\right)$$

### 2.3 Relative Window Alignment
Align all roster moves at $t = 0$. Track relative weekly windows $w \in [-13, +13]$ weeks ($90$ days pre and post).

---

## 3. Visualization Ideas & Outputs

1. **Event Study Plot**: Weekly average opponent-adjusted win rate with 95% bootstrap confidence intervals ($t = -13$ to $+13$).
2. **Success Distribution Heatmap**: Percentage of moves resulting in positive, neutral, or negative Elo change evaluated at 30, 60, and 90 days.
3. **Core Retained 4 Performance Shift**: Pre- vs post-move rating trajectory of the 4 retained players.
