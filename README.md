# CS2 Competitive Dynamics & Roster Change Analysis

An empirical study of competitive Counter-Strike 2 (CS2) match outcomes, team rating correlations, and roster change event dynamics in professional Tier 1 play.

---

## 🎯 Research Question 1 (RQ1)

> **"When a Tier 1 professional CS2 team replaces 1 of its 5 active players, does its performance improve, and is any improvement sustained?"**

### Core Findings Summary
1. **Foundational Metric Validation**: HLTV Rating 2.0 explains **76% of match outcome variance** (correlation r = +0.87, R² = 0.76) in Tier 1 play, proving team rating is a highly predictive metric for victory.
2. **Pre-Change Slump**: Teams experience a sharp drop in performance immediately prior to a roster move (dropping to **26.0% win rate** at Week -2) as motivation and internal alignment fray.
3. **Adaptation Period (Weeks 1 to 4)**: Replacing a player introduces tactical and communication friction (averaging 33.5% to 36.0% win rate in initial weeks).
4. **Synergy Peak (Week 9)**: Teams reach peak synergy roughly 50 to 60 days post-change, achieving an average **52.6% win rate**.
5. **Macro Success Rate**: Across all 45 isolated Tier 1 moves (90-day non-confounded window), **55% to 58% of teams sustain positive improvement** over their baseline.

---

## 🖥️ Presentation Formats

This project includes a complete, synchronized 7-slide presentation deck designed for stakeholders and teammates:

### 1. Interactive Web Presentation
Located at [`presentation/index.html`](presentation/index.html).
- **Features**: Widescreen dark UI, keyboard navigation (`Left`/`Right` arrow keys, `Spacebar`, `Home`/`End`), full-screen mode (`F`), interactive toggle between static plot and animated evolution GIF on Slide 2, and click-to-zoom Lightbox modal.
- **How to view**:
  ```bash
  # Option A: Open directly in your browser
  xdg-open presentation/index.html   # Linux
  open presentation/index.html       # macOS
  start presentation/index.html      # Windows

  # Option B: Run via a local static web server
  python3 -m http.server 8080 --directory presentation
  # Then navigate to http://localhost:8080
  ```

### 2. PowerPoint Slide Deck
Located at [`presentation/CS2_Roster_Dynamics_RQ1.pptx`](presentation/CS2_Roster_Dynamics_RQ1.pptx).
- **Features**: 16:9 widescreen, custom dark aesthetic, high-resolution embedded figures, structured takeaway cards.
- **Regenerate PPTX**:
  ```bash
  python analysis/roster_changes/generate_presentation_pptx.py
  ```

---

## 📊 Presentation Deck Outline

| Slide # | Focus Area | Key Visual Asset | Core Empirical Takeaway |
|:---:|:---|:---|:---|
| **1** | **Title & Problem Framing** | Dark theme cover card | Empirical investigation of single-player moves across 45 isolated 90-day events. |
| **2** | **Metric Validation** | Static Plot / Animated GIF | HLTV Rating 2.0 explains 76% of match outcome variance (r = +0.87, R² = 0.76). |
| **3** | **Vitality Dynasty** | `case_study_vitality.png` | Swapping Spinx for ropz sparked a 94.1% Tier 1 win rate and a triple trophy sweep (Katowice, EPL 21, Lisbon). |
| **4** | **Falcons Championship** | `case_study_falcons.png` | Signing IGL karrigan solved a 50% slump, lifting NiKo and m0NESY to win the IEM Cologne Major. |
| **5** | **MOUZ Captaincy Shift** | `case_study_mouz.png` | Trading IGL siuhy led to an initial 0/2 exit at Katowice before rebounding to a 71–75% win rate once roles stabilized. |
| **6** | **NAVI Post-Major Reset** | `case_study_navi.png` | Replacing jL with academy talent makazze led to initial Cologne struggles followed by an undefeated 100% run at StarLadder Fall. |
| **7** | **Macro Dynamics & Conclusions** | `aggregated_roster_dynamics_isolated_90d.png` | Synthesizes the 4 lifecycle stages and proves a 55–58% long-term sustainable improvement rate. |

---

## 📁 Repository Structure

```
cs2-analysis/
├── README.md                                # Project overview and presentation guide
├── requirements.txt                         # Python dependencies
├── .gitignore                               # Clean exclusion of cache, logs, and raw scrape data
├── presentation/
│   ├── index.html                           # Interactive 7-slide web presentation
│   ├── CS2_Roster_Dynamics_RQ1.pptx         # 16:9 Widescreen PowerPoint slide deck
│   └── assets/                              # High-resolution figures and animated GIF
├── analysis/
│   └── roster_changes/
│       ├── __init__.py                      # Package exports
│       ├── plot_team_case_studies.py        # Team-specific 24-week case study generator
│       ├── plot_aggregated_roster_dynamics.py # 90-day population event study generator
│       ├── plot_tier1_winrate_vs_rating.py  # Static win rate vs. rating scatter generator
│       ├── animate_tier1_winrate_vs_rating.py # Time-lapse GIF evolution generator
│       └── generate_presentation_pptx.py    # PowerPoint slide deck compiler
├── data/
│   ├── processed/
│   │   └── hltv_database.db                 # Processed SQLite database (matches, players, stats)
│   └── visualization/
│       └── roster_changes/                  # Generated analysis plots
├── scripts/
│   └── build_database.py                    # Database schema and index builder
├── src/                                     # Data collection, scraping, and parsing modules
│   ├── sourcing/
│   ├── analysis/
│   ├── db/
│   └── graph/
└── plan/                                    # Research questions, design documents, and roadmap
```

---

## 🚀 Setup & Reproduction

### 1. Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Analysis Scripts
```bash
# Generate all 4 deep-dive team case studies (Vitality, Falcons, MOUZ, NAVI):
python analysis/roster_changes/plot_team_case_studies.py --team all --window-size 10

# Generate the 90-day aggregated population event study:
python analysis/roster_changes/plot_aggregated_roster_dynamics.py \
    --cohort top30 \
    --isolation-days 90 \
    --event-tier "Tier 1" \
    --min-matches 3 \
    --window-type trailing \
    --window-days 14

# Generate the static win rate vs. rating plot:
python analysis/roster_changes/plot_tier1_winrate_vs_rating.py

# Recompile the PowerPoint presentation:
python analysis/roster_changes/generate_presentation_pptx.py
```
