import os
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# 16:9 Widescreen dimensions
SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5

# Curated Dark Palette
COLOR_BG = RGBColor(13, 17, 23)        # #0D1117
COLOR_CARD = RGBColor(22, 27, 34)      # #161B22
COLOR_BORDER = RGBColor(48, 54, 61)    # #30363D
COLOR_TEXT_WHITE = RGBColor(240, 246, 252)
COLOR_TEXT_MUTED = RGBColor(139, 148, 158)
COLOR_ACCENT_BLUE = RGBColor(88, 166, 255)
COLOR_ACCENT_GREEN = RGBColor(63, 185, 80)
COLOR_ACCENT_GOLD = RGBColor(255, 184, 0)
COLOR_ACCENT_PURPLE = RGBColor(163, 113, 247)
COLOR_ACCENT_RED = RGBColor(248, 81, 73)


def apply_dark_background(slide):
    """Sets slide background to dark theme color."""
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = COLOR_BG


def add_header(slide, tag_text: str, title_text: str, subtitle_text: str, tag_color: RGBColor = COLOR_ACCENT_BLUE):
    """Creates a consistent, publication-grade header on content slides."""
    # Top Tag
    tb_tag = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.35))
    p_tag = tb_tag.text_frame.paragraphs[0]
    p_tag.text = tag_text.upper()
    p_tag.font.size = Pt(11)
    p_tag.font.bold = True
    p_tag.font.color.rgb = tag_color
    p_tag.font.name = "Arial"

    # Main Title
    tb_title = slide.shapes.add_textbox(Inches(0.8), Inches(0.68), Inches(11.7), Inches(0.55))
    p_title = tb_title.text_frame.paragraphs[0]
    p_title.text = title_text
    p_title.font.size = Pt(20)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_TEXT_WHITE
    p_title.font.name = "Arial"

    # Subtitle
    tb_sub = slide.shapes.add_textbox(Inches(0.8), Inches(1.18), Inches(11.7), Inches(0.4))
    p_sub = tb_sub.text_frame.paragraphs[0]
    p_sub.text = subtitle_text
    p_sub.font.size = Pt(12)
    p_sub.font.color.rgb = COLOR_TEXT_MUTED
    p_sub.font.name = "Arial"


def add_card(slide, left, top, width, height, bg_color=COLOR_CARD, border_color=COLOR_BORDER):
    """Draws a sleek rounded card container for content."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.2)
    return shape


def build_presentation(output_pptx: str):
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH_IN)
    prs.slide_height = Inches(SLIDE_HEIGHT_IN)
    blank_layout = prs.slide_layouts[6]

    # -------------------------------------------------------------
    # SLIDE 1: Title Slide
    # -------------------------------------------------------------
    s1 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s1)

    # Kicker
    kicker = s1.shapes.add_textbox(Inches(1.0), Inches(1.2), Inches(11.3), Inches(0.4))
    pk = kicker.text_frame.paragraphs[0]
    pk.text = "RESEARCH QUESTION 1 &bull; EMPIRICAL EVENT STUDY".replace("&bull;", "•")
    pk.font.size = Pt(12)
    pk.font.bold = True
    pk.font.color.rgb = COLOR_ACCENT_BLUE

    # Title Hero
    th = s1.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(11.3), Inches(1.8))
    pth = th.text_frame.paragraphs[0]
    pth.text = "When a Tier 1 Team Replaces 1 Player,\nDoes Performance Sustainably Improve?"
    pth.font.size = Pt(36)
    pth.font.bold = True
    pth.font.color.rgb = COLOR_TEXT_WHITE

    # Desc
    td = s1.shapes.add_textbox(Inches(1.0), Inches(3.6), Inches(11.3), Inches(0.8))
    ptd = td.text_frame.paragraphs[0]
    ptd.text = "An empirical event study measuring macroeconomic match win rates and individual player performance dynamics across ±90 days surrounding isolated single-player substitutions in modern Tier 1 Counter-Strike 2."
    ptd.font.size = Pt(15)
    ptd.font.color.rgb = COLOR_TEXT_MUTED

    # 4 Stat Cards
    stats = [
        ("45", "Isolated 1-Player Moves", "Clean 90d window", COLOR_ACCENT_BLUE),
        ("1,171", "Tier 1 Matches", "HLTV verified dataset", COLOR_ACCENT_GREEN),
        ("+0.87", "Win Rate Correlation (r)", "R² = 0.76 explained variance", COLOR_ACCENT_GOLD),
        ("55–58%", "Sustained Success Rate", "Positive 90-day trajectory", COLOR_ACCENT_PURPLE),
    ]

    card_w = Inches(2.68)
    card_h = Inches(1.45)
    card_top = Inches(4.7)
    for i, (val, label, sub, color) in enumerate(stats):
        c_left = Inches(1.0 + i * 2.88)
        add_card(s1, c_left, card_top, card_w, card_h)

        tb = s1.shapes.add_textbox(c_left + Inches(0.15), card_top + Inches(0.15), card_w - Inches(0.3), card_h - Inches(0.3))
        p1 = tb.text_frame.paragraphs[0]
        p1.text = val
        p1.font.size = Pt(28)
        p1.font.bold = True
        p1.font.color.rgb = color

        p2 = tb.text_frame.add_paragraph()
        p2.text = label
        p2.font.size = Pt(11)
        p2.font.bold = True
        p2.font.color.rgb = COLOR_TEXT_WHITE
        p2.space_before = Pt(4)

        p3 = tb.text_frame.add_paragraph()
        p3.text = sub
        p3.font.size = Pt(9.5)
        p3.font.color.rgb = COLOR_TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 2: Metric Validation (Scatter Plot & Rating Significance)
    # -------------------------------------------------------------
    s2 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s2)
    add_header(s2, "01 / Metric Validation", "Why HLTV Rating Matters: Predictive Ground Truth", "Demonstrating that individual and aggregate team ratings strongly predict Tier 1 match outcomes (r = +0.87, R² = 0.76)")

    # Image (Left)
    img_path = "data/visualization/roster_changes/tier1_winrate_vs_rating_raw.png"
    if os.path.exists(img_path):
        s2.shapes.add_picture(img_path, Inches(0.8), Inches(1.8), width=Inches(7.2))

    # Right Card: Insights
    rw = Inches(4.3)
    rh = Inches(5.1)
    rx = Inches(8.25)
    ry = Inches(1.8)
    add_card(s2, rx, ry, rw, rh)

    tb_r = s2.shapes.add_textbox(rx + Inches(0.3), ry + Inches(0.3), rw - Inches(0.6), rh - Inches(0.6))
    tf = tb_r.text_frame
    tf.word_wrap = True

    p = tf.paragraphs[0]
    p.text = "Key Validation Principles"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_BLUE

    bullets = [
        ("Decisive Predictor", "HLTV rating is not statistical noise. Team rating explains 76% of match win rate variance across top 30 play."),
        ("Tier 1 Dominance Tier", "Teams maintaining a 1.11+ average rating (Spirit, Vitality, MOUZ) convert at a 66%–77% win rate."),
        ("Sub-1.04 Danger Zone", "Teams averaging below 1.04 rating win fewer than 45% of Tier 1 matches, struggling to survive group stages."),
        ("Methodological Link", "Validates our 2-panel case study design: individual player rating shifts directly drive team win rate changes."),
        ("Animated Evolution", "Animation demonstrates that rating advantages hold consistently over time, not as short-term flukes.")
    ]

    for title, desc in bullets:
        p_b = tf.add_paragraph()
        p_b.space_before = Pt(12)
        r1 = p_b.add_run()
        r1.text = f"• {title}: "
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = COLOR_TEXT_WHITE

        r2 = p_b.add_run()
        r2.text = desc
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = COLOR_TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 3: Case Study 1 - Team Vitality (+ropz, -Spinx)
    # -------------------------------------------------------------
    s3 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s3)
    add_header(s3, "02 / Case Study", "Team Vitality (+ropz, -Spinx) / Tier 1", "Vitality Dynasty (2025-01-13) • Forging an Unstoppable 94.1% Tier 1 Win Rate Machine", COLOR_ACCENT_GREEN)

    img_v = "data/visualization/roster_changes/case_study_vitality.png"
    if os.path.exists(img_v):
        s3.shapes.add_picture(img_v, Inches(0.8), Inches(1.8), width=Inches(7.2))

    add_card(s3, rx, ry, rw, rh)
    tb_v = s3.shapes.add_textbox(rx + Inches(0.3), ry + Inches(0.3), rw - Inches(0.6), rh - Inches(0.6))
    tf_v = tb_v.text_frame
    tf_v.word_wrap = True

    p = tf_v.paragraphs[0]
    p.text = "Strategic Insights & Roster Impact"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_GREEN

    v_bullets = [
        ("Trading from Strength", "Vitality reached the Shanghai Major semifinals, but traded Spinx (departing at 1.17 rating) to upgrade team synergy."),
        ("94.1% Win Rate Machine", "16 wins in 17 matches across the 90-day post-change period, dropping only a single opening group match."),
        ("Triple Trophy Sweep", "Flawless 100% tournament win rates at IEM Katowice [1st], ESL Pro League Season 21 [1st], and BLAST Open Lisbon [1st]."),
        ("ZywOo Unleashed", "ropz (1.21 rating) locked down passive anchoring, enabling superstar ZywOo to peak at a staggering 1.49 rating."),
        ("Verdict", "The gold standard of successful 1-player upgrades: elevated the core baseline from 1.12 to 1.34+.")
    ]

    for title, desc in v_bullets:
        p_b = tf_v.add_paragraph()
        p_b.space_before = Pt(12)
        r1 = p_b.add_run()
        r1.text = f"• {title}: "
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = COLOR_TEXT_WHITE

        r2 = p_b.add_run()
        r2.text = desc
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = COLOR_TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 4: Case Study 2 - Team Falcons (+karrigan, -kyxsan)
    # -------------------------------------------------------------
    s4 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s4)
    add_header(s4, "03 / Case Study", "Falcons (+karrigan, -kyxsan) / Tier 1", "Falcons Championship Blueprint (2026-04-20) • Tactical Leadership Masterstroke to Major Glory", COLOR_ACCENT_PURPLE)

    img_f = "data/visualization/roster_changes/case_study_falcons.png"
    if os.path.exists(img_f):
        s4.shapes.add_picture(img_f, Inches(0.8), Inches(1.8), width=Inches(7.2))

    add_card(s4, rx, ry, rw, rh)
    tb_f = s4.shapes.add_textbox(rx + Inches(0.3), ry + Inches(0.3), rw - Inches(0.6), rh - Inches(0.6))
    tf_f = tb_f.text_frame
    tf_f.word_wrap = True

    p = tf_f.paragraphs[0]
    p.text = "Strategic Insights & Roster Impact"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_PURPLE

    f_bullets = [
        ("The Pre-Change Dilemma", "Falcons were stuck at a 50% European win rate; outgoing IGL kyxsan had a fragging gap (0.99) next to a 1.20+ core."),
        ("The Leadership Trade-off", "karrigan brought modest individual fragging (0.71–0.78), but installed an aggressive macro calling system."),
        ("Superstars Unlocked", "karrigan's spacing created optimal trade scenarios for NiKo and m0NESY, both dominating above 1.25 rating."),
        ("Major Champions", "Lift to 71–80% win rates in Asia/Astana climaxed with the IEM Cologne Major 2026 title (6/7 wins, 3-0 Grand Final)."),
        ("Verdict", "Proves that trading individual rating for elite leadership can transform a playoff fringe roster into Major Champions.")
    ]

    for title, desc in f_bullets:
        p_b = tf_f.add_paragraph()
        p_b.space_before = Pt(12)
        r1 = p_b.add_run()
        r1.text = f"• {title}: "
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = COLOR_TEXT_WHITE

        r2 = p_b.add_run()
        r2.text = desc
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = COLOR_TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 5: Case Study 3 - MOUZ (+Spinx, -siuhy)
    # -------------------------------------------------------------
    s5 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s5)
    add_header(s5, "04 / Case Study", "MOUZ (+Spinx, -siuhy) / Tier 1", "MOUZ Captaincy Shift (2025-01-27) • Firepower Injection & The Cost of Role Readjustment", COLOR_ACCENT_GOLD)

    img_m = "data/visualization/roster_changes/case_study_mouz.png"
    if os.path.exists(img_m):
        s5.shapes.add_picture(img_m, Inches(0.8), Inches(1.8), width=Inches(7.2))

    add_card(s5, rx, ry, rw, rh)
    tb_m = s5.shapes.add_textbox(rx + Inches(0.3), ry + Inches(0.3), rw - Inches(0.6), rh - Inches(0.6))
    tf_m = tb_m.text_frame
    tf_m.word_wrap = True

    p = tf_m.paragraphs[0]
    p.text = "Strategic Insights & Roster Impact"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_GOLD

    m_bullets = [
        ("The Captaincy Gamble", "MOUZ parted with long-standing IGL siuhy, injecting superstar rifler Spinx to boost pure fragging power."),
        ("Adaptation Shock", "Loss of caller caused immediate tactical confusion: 0/2 elimination at IEM Katowice 2025 (Week 1)."),
        ("Post-Break Rebound", "Following a 4-week role recalibration, MOUZ surged back with a 71–75% win rate across PGL Cluj and EPL S21."),
        ("Floor Elevation", "Spinx stabilized at a reliable 1.13 rating, raising the core floor from 1.04 to 1.13."),
        ("Verdict", "Illustrates the classic adaptation valley: high-caliber firepower eventually pays off, but demands a 3–4 week grace period.")
    ]

    for title, desc in m_bullets:
        p_b = tf_m.add_paragraph()
        p_b.space_before = Pt(12)
        r1 = p_b.add_run()
        r1.text = f"• {title}: "
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = COLOR_TEXT_WHITE

        r2 = p_b.add_run()
        r2.text = desc
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = COLOR_TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 6: Case Study 4 - Natus Vincere (+makazze, -jL)
    # -------------------------------------------------------------
    s6 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s6)
    add_header(s6, "05 / Case Study", "Natus Vincere (+makazze, -jL) / Tier 1", "NAVI Post-Major Reset (2025-07-14) • Promoting Youth Talent After Major Hangover", COLOR_ACCENT_BLUE)

    img_n = "data/visualization/roster_changes/case_study_navi.png"
    if os.path.exists(img_n):
        s6.shapes.add_picture(img_n, Inches(0.8), Inches(1.8), width=Inches(7.2))

    add_card(s6, rx, ry, rw, rh)
    tb_n = s6.shapes.add_textbox(rx + Inches(0.3), ry + Inches(0.3), rw - Inches(0.6), rh - Inches(0.6))
    tf_n = tb_n.text_frame
    tf_n.word_wrap = True

    p = tf_n.paragraphs[0]
    p.text = "Strategic Insights & Roster Impact"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_BLUE

    n_bullets = [
        ("Major Hangover", "Austin Major MVP jL suffered a sharp form slump (dropping to 0.86 rating), prompting NAVI to promote youth talent makazze."),
        ("Initial Stumble", "Going 3–6 at IEM Cologne 2025 (Week 2) during role integration showed typical adaptation friction."),
        ("Breakout Star", "makazze posted a 1.16 average post-change rating, peaking at 1.33 and outperforming the predecessor by +0.30."),
        ("StarLadder Champions", "Powered an undefeated 100% win rate run at StarLadder Fall and playoffs at ESL Pro League Season 22."),
        ("Verdict", "A textbook promotion case study: resolving a declining player slot restored championship pedigree within 6 weeks.")
    ]

    for title, desc in n_bullets:
        p_b = tf_n.add_paragraph()
        p_b.space_before = Pt(12)
        r1 = p_b.add_run()
        r1.text = f"• {title}: "
        r1.font.bold = True
        r1.font.size = Pt(11)
        r1.font.color.rgb = COLOR_TEXT_WHITE

        r2 = p_b.add_run()
        r2.text = desc
        r2.font.size = Pt(10.5)
        r2.font.color.rgb = COLOR_TEXT_MUTED

    # -------------------------------------------------------------
    # SLIDE 7: Macro Dynamics & Conclusions (Huge Slide)
    # -------------------------------------------------------------
    s7 = prs.slides.add_slide(blank_layout)
    apply_dark_background(s7)
    add_header(s7, "06 / Macro Synthesis", "The 90-Day CS2 Roster Lifecycle: Empirical Conclusions", "Macroeconomic findings across 45 isolated 1-player substitutions • 1,171 Tier 1 matches", COLOR_ACCENT_GREEN)

    img_agg = "data/visualization/roster_changes/aggregated_roster_dynamics_isolated_90d.png"
    if os.path.exists(img_agg):
        s7.shapes.add_picture(img_agg, Inches(0.8), Inches(1.8), width=Inches(7.2))

    add_card(s7, rx, ry, rw, rh)
    tb_agg = s7.shapes.add_textbox(rx + Inches(0.3), ry + Inches(0.3), rw - Inches(0.6), rh - Inches(0.6))
    tf_agg = tb_agg.text_frame
    tf_agg.word_wrap = True

    p = tf_agg.paragraphs[0]
    p.text = "The 4 Lifecycle Stages of CS2 Roster Moves"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_GREEN

    stages = [
        ("Stage I: Pre-Change Slump", "Weeks -4 to 0", "Win rate plunges to a 26.0% trough at Week -2. Knowledge of benching destroys internal trust and execution.", COLOR_ACCENT_RED),
        ("Stage II: Adaptation Valley", "Weeks 1 to 4", "Disruption shock: 33.5% WR at Week 1. Role overlap, comms recalibration, and playbook adjustments create drag.", COLOR_ACCENT_GOLD),
        ("Stage III: Synergy Peak", "Weeks 5 to 9", "Monotonic ascent reaching 52.6% win rate at Week 9 (~50–60 days). Setups are internalized; synergy peaks.", COLOR_ACCENT_GREEN),
        ("Stage IV: Equilibrium", "Weeks 10 to 12", "Settles into sustainable Tier 1 baseline (45–50% WR against elite competition).", COLOR_ACCENT_BLUE),
    ]

    for title, weeks, desc, col in stages:
        p_s = tf_agg.add_paragraph()
        p_s.space_before = Pt(9)
        r1 = p_s.add_run()
        r1.text = f"{title} ({weeks}): "
        r1.font.bold = True
        r1.font.size = Pt(10.5)
        r1.font.color.rgb = col

        r2 = p_s.add_run()
        r2.text = desc
        r2.font.size = Pt(9.5)
        r2.font.color.rgb = COLOR_TEXT_MUTED

    # Definitive Answer Box
    p_ans = tf_agg.add_paragraph()
    p_ans.space_before = Pt(12)
    r_ans = p_ans.add_run()
    r_ans.text = "Definitive Answer to RQ1: "
    r_ans.font.bold = True
    r_ans.font.size = Pt(11)
    r_ans.font.color.rgb = COLOR_TEXT_WHITE

    r_ans_t = p_ans.add_run()
    r_ans_t.text = "Performance DOES improve significantly (+26.6% trough-to-peak), and improvement is SUSTAINED in 55%–58% of isolated Tier 1 roster moves."
    r_ans_t.font.size = Pt(10.5)
    r_ans_t.font.color.rgb = COLOR_ACCENT_BLUE

    os.makedirs(os.path.dirname(os.path.abspath(output_pptx)), exist_ok=True)
    prs.save(output_pptx)
    print(f"[PowerPoint Generated] {output_pptx}")


if __name__ == "__main__":
    out_file = "presentation/CS2_Roster_Dynamics_RQ1.pptx"
    build_presentation(out_file)
