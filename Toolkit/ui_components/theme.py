"""
Tavant look for the whole app.

Brand colours come from tavant.com (Tango #F36F26 with black and white); the
rest of the palette is built around Tango. .streamlit/config.toml sets the base
Streamlit theme (primary colour, sidebar, light/dark backgrounds); this module
adds what the theme file cannot: the hero header, gradient buttons, pill tabs,
the sidebar navigation highlight and card styles.

Light / dark is decided in the BROWSER, never on the server. Streamlit's server-side
theme value only catches up on the next rerun, so a switch in ⋮ > Settings used to leave the custom
(light) colours under Streamlit's new (light) text. Every custom colour is a CSS
variable (LIGHT / DARK below); THEME_WATCH_JS sets <html data-dm-theme="..."> from
the theme Streamlit is actually showing, so the variables follow it instantly.
"""

import os

import streamlit as st

TANGO = "#F36F26"        # Tavant brand orange
TANGO_DEEP = "#D9571A"
TANGO_SOFT = "#FF8A3D"
AMBER = "#FFB547"
CORAL = "#FF5E6C"
INK = "#15151C"          # Tavant black
INK_SOFT = "#23232D"
CREAM = "#FFF8F3"
SUCCESS = "#12805C"
# [theme.light.sidebar] / [theme.dark.sidebar] backgroundColor in .streamlit/config.toml
SIDEBAR_BG = {'light': '#FFF1E6', 'dark': '#15151C'}

# Official Tavant brand assets (from tavant.com): the wordmark and the "T" icon.
_BRAND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'brand')
BRAND_LOGO = os.path.join(_BRAND_DIR, 'tavant_logo.png')
BRAND_ICON = os.path.join(_BRAND_DIR, 'tavant_icon.png')

STEP_KINDS = ('done', 'done_issues', 'current', 'here_locked', 'ready', 'locked')

# Every value is checked for contrast (>= 4.5:1 for text) by tests/guided_flow/test_dark_mode.py.
LIGHT = {
    'paper': CREAM, 'panel': 'rgba(255, 250, 246, 0.58)', 'panel-border': 'rgba(243, 111, 38, 0.16)',
    'panel-shadow': 'rgba(27, 27, 34, 0.08)',
    'heading': '#1B1B22', 'muted': '#5B544C', 'accent-text': '#B5400B',
    'card-bg': 'rgba(255, 255, 255, 0.86)', 'card-border': '#F2DCCB', 'card-shadow': 'rgba(27, 27, 34, 0.07)',
    'tab-rail': 'rgba(243, 111, 38, 0.07)', 'disabled-bg': '#F6DFD0', 'disabled-fg': '#86705F',
    'step-title': '#1A1815', 'step-desc': '#5A5349', 'step-border': '#E4E0D8',
    'step-done-bg': '#E6F5EE', 'step-done-accent': '#0E6B4C',
    'step-done_issues-bg': '#FFF0E3', 'step-done_issues-accent': '#A8380A',
    'step-current-bg': '#FFEBDD', 'step-current-accent': '#A8380A',
    'step-here_locked-bg': '#FFF3EA', 'step-here_locked-accent': '#A8380A',
    'step-ready-bg': '#FFF4DE', 'step-ready-accent': '#8A5200',
    'step-locked-bg': '#F6F2EE', 'step-locked-accent': '#5F584F',
    # sidebar (on SIDEBAR_BG['light'])
    'side-text': '#1B1B22', 'side-muted': '#5E564D', 'side-heading': '#A8380A',
    'side-card-bg': 'rgba(255, 255, 255, 0.72)', 'side-card-border': '#EED9C8',
    'side-hover': 'rgba(243, 111, 38, 0.08)', 'side-active-from': 'rgba(243, 111, 38, 0.22)',
    'side-active-to': 'rgba(243, 111, 38, 0.05)', 'side-active-text': '#1B1B22',
    'side-ok': '#0B6E4A', 'side-ok-bg': 'rgba(18, 163, 110, 0.12)',
    'side-bad': '#B42318', 'side-bad-bg': 'rgba(229, 72, 77, 0.12)',
    'side-none': '#7A4800', 'side-none-bg': 'rgba(232, 163, 23, 0.18)',
}
DARK = {
    'paper': '#101016', 'panel': 'rgba(16, 16, 22, 0.84)', 'panel-border': 'rgba(250, 250, 250, 0.08)',
    'panel-shadow': 'rgba(0, 0, 0, 0.35)',
    'heading': '#F7F3EF', 'muted': '#CFC8C1', 'accent-text': '#FF9A5C',
    'card-bg': 'rgba(29, 29, 38, 0.92)', 'card-border': '#34343F', 'card-shadow': 'rgba(0, 0, 0, 0.35)',
    'tab-rail': 'rgba(243, 111, 38, 0.12)', 'disabled-bg': '#3A2A22', 'disabled-fg': '#C9B5A8',
    'step-title': '#F3EFE8', 'step-desc': '#C9C2B8', 'step-border': '#3A3632',
    'step-done-bg': '#12302A', 'step-done-accent': '#7FD1C4',
    'step-done_issues-bg': '#33201A', 'step-done_issues-accent': '#FFA877',
    'step-current-bg': '#3A2213', 'step-current-accent': '#FFA466',
    'step-here_locked-bg': '#2A211C', 'step-here_locked-accent': '#FFA466',
    'step-ready-bg': '#2E2616', 'step-ready-accent': '#FFC46B',
    'step-locked-bg': '#1F1D1B', 'step-locked-accent': '#B5AEA3',
    # sidebar (on SIDEBAR_BG['dark'])
    'side-text': '#F4F1EE', 'side-muted': '#B9B3AE', 'side-heading': '#F7A26B',
    'side-card-bg': 'rgba(255, 255, 255, 0.035)', 'side-card-border': 'rgba(255, 255, 255, 0.09)',
    'side-hover': 'rgba(255, 255, 255, 0.06)', 'side-active-from': 'rgba(243, 111, 38, 0.34)',
    'side-active-to': 'rgba(243, 111, 38, 0.08)', 'side-active-text': '#FFFFFF',
    'side-ok': '#5EE0A8', 'side-ok-bg': 'rgba(94, 224, 168, 0.12)',
    'side-bad': '#FF8A80', 'side-bad-bg': 'rgba(255, 138, 128, 0.13)',
    'side-none': '#FFC46B', 'side-none-bg': 'rgba(255, 196, 107, 0.12)',
}
# Message boxes in the dark theme: (background, left accent bar, text).
DARK_ALERTS = {
    'Info': ('rgba(45, 212, 191, 0.13)', '#2DD4BF', '#D5FBF4'),
    'Warning': ('rgba(255, 181, 71, 0.14)', '#FFB547', '#FFE9C7'),
    'Success': ('rgba(94, 224, 168, 0.13)', '#5EE0A8', '#D6F9E8'),
    'Error': ('rgba(255, 122, 122, 0.14)', '#FF7A7A', '#FFDCDC'),
}


# Result-table cell tints (pandas Styler -> st.dataframe). Translucent and with no text
# colour, so the theme's own text stays readable on them in light AND dark mode.
STATUS_CELL = {
    'pass': 'background-color: rgba(18, 128, 92, 0.24); font-weight: 600',
    'fail': 'background-color: rgba(220, 53, 69, 0.24); font-weight: 600',
    'warn': 'background-color: rgba(255, 181, 71, 0.28); font-weight: 600',
    'info': 'background-color: rgba(45, 160, 220, 0.20)',
}


def status_cell(value) -> str:
    """Styler cell style for a PASS / FAIL / PENDING / SKIP style status value."""
    kind = {'PASS': 'pass', 'PASSED': 'pass', 'FAIL': 'fail', 'FAILED': 'fail', 'ERROR': 'fail',
            'PENDING': 'warn', 'SKIP': 'warn', 'SKIPPED': 'warn'}.get(str(value).strip().upper())
    return STATUS_CELL[kind] if kind else ''


def _vars(tokens) -> str:
    return " ".join(f"--dm-{name}: {value};" for name, value in tokens.items())


def theme_vars_css() -> str:
    """The light values, the dark values (when the page is marked dark), and the OS
    preference as the guess before the watcher has marked the page."""
    return (f":root {{ {_vars(LIGHT)} }}\n"
            f':root[data-dm-theme="dark"] {{ {_vars(DARK)} }}\n'
            f"@media (prefers-color-scheme: dark) {{ :root:not([data-dm-theme]) {{ {_vars(DARK)} }} }}\n")


def _dark_alert_css() -> str:
    rules = []
    for kind, (bg, border, text) in DARK_ALERTS.items():
        box = f':root[data-dm-theme="dark"] [data-testid="stAlertContainer"]:has([data-testid="stAlertContent{kind}"])'
        rules.append(f"{box} {{ background: {bg} !important; box-shadow: inset 4px 0 0 {border}; }}\n"
                     f"{box} p, {box} li, {box} span, {box} strong {{ color: {text} !important; }}")
    return "\n".join(rules)


def _css() -> str:
    return theme_vars_css() + f"""
/* ---------- page spacing: no dead space (Streamlit's defaults are 6rem on top, 2rem per divider) ---------- */
[data-testid="stMainBlockContainer"] {{ padding-top: 2rem !important; padding-bottom: 2.5rem !important; }}
[data-testid="stHeader"] {{ height: 2.25rem; min-height: 0; }}
[data-testid="stMain"] hr {{ margin: .5rem 0 !important; }}
/* type scale (Streamlit's is 2.75 / 2.25 / 1.75 / 1.5 rem: page titles wrapped and sections shouted) */
[data-testid="stMain"] h1 {{ padding: .25rem 0 .35rem !important; font-size: 1.75rem !important; line-height: 1.2 !important; }}
[data-testid="stMain"] h2 {{ padding: .45rem 0 .3rem !important; font-size: 1.4rem !important; line-height: 1.25 !important; }}
[data-testid="stMain"] h3 {{ padding: .4rem 0 .25rem !important; font-size: 1.2rem !important; line-height: 1.3 !important; }}
[data-testid="stMain"] h4 {{ padding: .3rem 0 .2rem !important; font-size: 1.05rem !important; }}
[data-testid="stMain"] h5, [data-testid="stMain"] h6 {{ padding: .25rem 0 .15rem !important; font-size: .95rem !important; }}
[data-testid="stMain"] [data-testid="stMetricValue"] {{ font-size: 1.55rem; }}
[data-testid="stMain"] [data-testid="stMetricLabel"] p {{ font-size: .8rem; }}
/* message boxes: compact (Streamlit pads them 1rem all round) */
[data-testid="stAlertContainer"] {{ padding: .55rem .85rem !important; }}
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] li {{ font-size: .92rem; }}

/* ---------- hero header (slim: one title row + the step chips) ---------- */
.dm-hero {{
  position: relative; overflow: hidden; display: flex; align-items: center; gap: 16px;
  padding: 14px 22px; margin: 0 0 .9rem 0; border-radius: 18px; color: #fff;
  background:
    radial-gradient(120% 160% at 100% 0%, rgba(243,111,38,.62) 0%, rgba(243,111,38,0) 55%),
    radial-gradient(80% 140% at 0% 100%, rgba(255,181,71,.30) 0%, rgba(255,181,71,0) 60%),
    radial-gradient(60% 90% at 70% 120%, rgba(255,94,108,.35) 0%, rgba(255,94,108,0) 60%),
    linear-gradient(135deg, #15151C 0%, #201E27 55%, #2B1A12 100%);
  box-shadow: 0 18px 44px rgba(243,111,38,.20), inset 0 0 0 1px rgba(255,255,255,.06);
}}
.dm-hero::after {{
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background-image: radial-gradient(rgba(255,255,255,.18) 1px, transparent 1px);
  background-size: 18px 18px; mask-image: linear-gradient(90deg, transparent 35%, #000 100%);
  -webkit-mask-image: linear-gradient(90deg, transparent 35%, #000 100%);
}}
.dm-hero .dm-logo img {{ width: 100%; height: 100%; display: block; }}
.dm-hero .dm-logo {{
  flex-shrink: 0; width: 52px; height: 52px; border-radius: 14px; display: flex; align-items: center; overflow: hidden;
  justify-content: center; background: #0B0B0F; color: {TANGO}; font-weight: 800; font-size: 10.5px;
  letter-spacing: .08em; box-shadow: inset 0 0 0 1px rgba(255,255,255,.10), 0 8px 18px rgba(0,0,0,.40);
}}
.dm-hero .dm-hero-row {{ display: flex; align-items: baseline; flex-wrap: wrap; column-gap: 14px; row-gap: 2px; }}
.dm-hero .dm-title {{ font-size: 1.7rem; font-weight: 800; line-height: 1.1; color: #fff; letter-spacing: -.01em; }}
.dm-hero .dm-title span {{ background: linear-gradient(90deg, {TANGO} 0%, {AMBER} 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent; }}
.dm-hero .dm-sub {{ color: rgba(255,255,255,.78); font-size: .92rem; }}
.dm-hero .dm-chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: .45rem; }}
.dm-hero .dm-chips span {{
  font-size: .74rem; padding: 3px 9px; border-radius: 999px; color: #fff;
  background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.14);
}}
.dm-hero .dm-chips span b {{ color: {AMBER}; font-weight: 700; margin-right: 4px; }}

/* ---------- text on the content panel ---------- */
[data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {{
  color: var(--dm-heading); letter-spacing: -.01em;
}}
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p {{ color: var(--dm-muted); }}
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {{ color: var(--dm-heading); }}

/* ---------- buttons ---------- */
[data-testid="stBaseButton-primary"] {{
  background: linear-gradient(135deg, {TANGO} 0%, {TANGO_SOFT} 100%) !important;
  border: 0 !important; color: #fff !important;
  box-shadow: 0 6px 16px rgba(243,111,38,.30); transition: transform .12s ease, box-shadow .12s ease;
}}
[data-testid="stBaseButton-primary"]:hover {{ transform: translateY(-1px); box-shadow: 0 10px 24px rgba(243,111,38,.38); }}
[data-testid="stBaseButton-primary"]:disabled {{
  background: var(--dm-disabled-bg) !important; color: var(--dm-disabled-fg) !important; box-shadow: none; transform: none;
}}
[data-testid="stMain"] [data-testid="stBaseButton-secondary"]:disabled,
[data-testid="stMain"] [data-testid="stBaseButton-secondary"]:disabled p {{ color: var(--dm-disabled-fg) !important; opacity: 1; }}
[data-testid="stBaseButton-secondary"]:hover:not(:disabled) {{ border-color: {TANGO} !important; color: var(--dm-accent-text) !important; }}

/* ---------- tabs: pills on a soft rail ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: var(--dm-tab-rail); padding: 6px; border-radius: 14px; }}
.stTabs [data-baseweb="tab"] {{
  border-radius: 10px; padding: 8px 14px; background: transparent; border: 0; height: auto;
}}
.stTabs [data-baseweb="tab"]:hover {{ background: rgba(243,111,38,.12); }}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(135deg, {TANGO} 0%, {TANGO_SOFT} 100%) !important;
  box-shadow: 0 4px 14px rgba(243,111,38,.30);
}}
.stTabs [aria-selected="true"] p {{ color: #fff !important; font-weight: 600; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* ---------- cards ---------- */
.metric-card {{
  position: relative; overflow: hidden; padding: 1.1rem 1.25rem 1rem 1.5rem; border-radius: 18px;
  background: var(--dm-card-bg); border: 1px solid var(--dm-card-border); box-shadow: 0 10px 28px var(--dm-card-shadow);
}}
.metric-card::before {{
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 6px;
  background: linear-gradient(180deg, {TANGO} 0%, {AMBER} 100%);
}}
.metric-card h2 {{ color: {TANGO}; }}
.metric-card h3 {{ color: var(--dm-heading); }}
.metric-card p {{ color: var(--dm-muted); }}
[data-testid="stExpander"] details {{ border-radius: 14px; }}
[data-testid="stExpander"] summary:hover {{ color: var(--dm-accent-text); }}

/* ---------- dashboard: status bar, KPI tiles, key/value rows, activity feed ---------- */
.dm-status {{
  display: flex; align-items: center; gap: 10px; min-height: 42px; padding: 8px 14px; border-radius: 12px;
  background: var(--dm-card-bg); border: 1px solid var(--dm-card-border); color: var(--dm-heading);
  font-size: .95rem; box-shadow: inset 4px 0 0 var(--dm-status-accent);
}}
.dm-status.ok {{ --dm-status-accent: #12A36E; }}
.dm-status.bad {{ --dm-status-accent: #E5484D; }}
.dm-status.none {{ --dm-status-accent: #E8A317; }}
.dm-status .dot {{
  flex-shrink: 0; width: 9px; height: 9px; border-radius: 50%; background: var(--dm-status-accent);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--dm-status-accent) 20%, transparent);
}}
.dm-status .hint {{ color: var(--dm-muted); font-size: .85rem; }}
.st-key-dash_session h4, .st-key-dash_actions h4 {{ font-size: 1.02rem !important; font-weight: 700; }}
.dm-kpi {{
  position: relative; overflow: hidden; padding: 12px 16px 12px 18px; border-radius: 14px; margin-bottom: .55rem;
  background: var(--dm-card-bg); border: 1px solid var(--dm-card-border);
  box-shadow: 0 6px 18px var(--dm-card-shadow); transition: transform .15s ease, box-shadow .15s ease;
}}
.dm-kpi:hover {{ transform: translateY(-2px); box-shadow: 0 12px 26px var(--dm-card-shadow); }}
.dm-kpi::before {{
  content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
  background: linear-gradient(180deg, {TANGO} 0%, {AMBER} 100%);
}}
.dm-kpi-icon {{ position: absolute; right: 14px; top: 12px; font-size: 1.25rem; opacity: .9; }}
.dm-kpi-label {{ font-size: .7rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--dm-muted); }}
.dm-kpi-value {{ font-size: 1.9rem; font-weight: 800; line-height: 1.15; margin-top: 2px; color: var(--dm-accent-text); }}
.dm-kpi-sub {{ font-size: .78rem; color: var(--dm-muted); }}
.dm-kv {{
  display: flex; justify-content: space-between; gap: 12px; padding: 7px 2px; font-size: .9rem;
  border-bottom: 1px solid var(--dm-card-border);
}}
.dm-kv:last-child {{ border-bottom: 0; }}
.dm-kv .k {{ color: var(--dm-muted); }}
.dm-kv .v {{ color: var(--dm-heading); font-weight: 600; text-align: right; }}
.dm-feed {{ list-style: none; margin: 0; padding: 0; }}
.dm-feed li {{ display: flex; gap: 10px; align-items: baseline; padding: 5px 0; font-size: .88rem; color: var(--dm-heading); }}
.dm-feed li .t {{ flex-shrink: 0; color: var(--dm-muted); font-variant-numeric: tabular-nums; }}
.dm-feed li .d {{ flex-shrink: 0; width: 7px; height: 7px; border-radius: 50%; background: #12A36E; align-self: center; }}
.dm-feed li.warning .d {{ background: #E8A317; }}
.dm-feed li.error .d {{ background: #E5484D; }}

/* ---------- guided-flow step cards (step_flow.render_stepper) ---------- */
.dm-step {{
  background: var(--dm-step-bg); border: 1px solid var(--dm-step-border); border-radius: 12px;
  padding: .5rem .8rem; box-shadow: 0 4px 14px var(--dm-card-shadow); cursor: default;
}}
.dm-step.is-current {{ border: 2px solid var(--dm-step-accent); padding: calc(.5rem - 1px) calc(.8rem - 1px); }}
.dm-step .state, .dm-step .title {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.dm-step .state {{ font-size: .72rem; font-weight: 700; letter-spacing: .02em; color: var(--dm-step-accent); }}
.dm-step .title {{ font-size: .95rem; font-weight: 700; color: var(--dm-step-title); margin-top: 1px; }}
.dm-step .desc {{ font-size: .78rem; color: var(--dm-step-desc); }}
""" + "\n".join(f".dm-step--{k} {{ --dm-step-bg: var(--dm-step-{k}-bg); --dm-step-accent: var(--dm-step-{k}-accent); }}"
                for k in STEP_KINDS) + "\n" + _dark_alert_css() + _sidebar_css()


# The sidebar follows the theme too: [theme.light.sidebar] / [theme.dark.sidebar] in
# .streamlit/config.toml set its background, the --dm-side-* variables everything on it.


def nav_section_css() -> str:
    """A heading above the first page of each sidebar menu section (navigation.NAV_SECTIONS)."""
    from ui_components.navigation import NAV_SECTIONS
    rules, position = [], 1
    for title, pages in NAV_SECTIONS:
        label = title.upper().replace('"', '')
        rules.append(
            f'[data-testid="stSidebar"] [role="radiogroup"] > label:nth-of-type({position}) '
            f'{{ margin-top: {"22px" if position == 1 else "28px"}; }}\n'
            f'[data-testid="stSidebar"] [role="radiogroup"] > label:nth-of-type({position})::before '
            f'{{ content: "{label}"; }}')
        position += len(pages)
    return "\n".join(rules)


def _sidebar_css() -> str:
    return f"""
/* ---------- sidebar: brand (st.logo shows the Tavant wordmark above it) ---------- */
.dm-side-brand {{ margin: -.6rem 0 .8rem 2px; }}
.dm-side-brand .name {{ font-weight: 700; color: var(--dm-side-text); line-height: 1.15; font-size: 1.02rem; }}
.dm-side-brand .name small {{ display: block; font-weight: 400; color: var(--dm-side-muted); font-size: .74rem; }}

/* ---------- sidebar: connection card ---------- */
[data-testid="stSidebar"] .st-key-dm_connection_card {{
  background: var(--dm-side-card-bg); border: 1px solid var(--dm-side-card-border); border-radius: 14px;
  padding: 12px 12px 6px 12px; gap: .55rem;
}}
[data-testid="stSidebar"] .st-key-dm_connection_card label p {{ color: var(--dm-side-muted); font-size: .78rem; }}
.dm-conn-head {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }}
.dm-conn-head .title {{ font-size: .7rem; letter-spacing: .14em; font-weight: 700; color: var(--dm-side-heading); }}
.dm-conn-status {{
  display: inline-flex; align-items: center; gap: 6px; padding: 2px 9px; border-radius: 999px;
  font-size: .74rem; font-weight: 600; white-space: nowrap;
}}
.dm-conn-status .dot {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; }}
.dm-conn-status.ok   {{ color: var(--dm-side-ok); background: var(--dm-side-ok-bg); }}
.dm-conn-status.bad  {{ color: var(--dm-side-bad); background: var(--dm-side-bad-bg); }}
.dm-conn-status.none {{ color: var(--dm-side-none); background: var(--dm-side-none-bg); }}
.dm-conn-object {{ font-size: .8rem; color: var(--dm-side-muted); margin: 2px 0 4px 0; }}
.dm-conn-object b {{ color: var(--dm-side-text); font-weight: 600; }}

/* ---------- sidebar: menu (one radio, drawn as a menu) ---------- */
[data-testid="stSidebar"] [data-testid="stRadio"], [data-testid="stSidebar"] [data-testid="stRadio"] > div,
[data-testid="stSidebar"] [role="radiogroup"] {{ width: 100%; }}
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 1px; }}
[data-testid="stSidebar"] [role="radiogroup"] > label {{
  position: relative; width: 100%; max-width: none; margin: 0; padding: 6px 12px; border-radius: 10px;
  transition: background .12s ease, color .12s ease;
}}
[data-testid="stSidebar"] [role="radiogroup"] > label::before {{
  position: absolute; left: 12px; top: -19px; font-size: .68rem; font-weight: 700; letter-spacing: .14em;
  color: var(--dm-side-heading); pointer-events: none;
}}
/* hide the radio circle; the row itself is the control */
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div > div:not([data-testid]) {{ display: none; }}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{ color: var(--dm-side-text); font-size: .92rem; }}
[data-testid="stSidebar"] [role="radiogroup"] > label:hover {{ background: var(--dm-side-hover); }}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {{
  background: linear-gradient(90deg, var(--dm-side-active-from) 0%, var(--dm-side-active-to) 100%);
  box-shadow: inset 3px 0 0 {TANGO};
}}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) p {{ color: var(--dm-side-active-text); font-weight: 700; }}
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:focus-visible) {{ outline: 2px solid {TANGO_SOFT}; }}
/* the theme watcher draws nothing; do not let its slot add a gap */
[data-testid="stSidebar"] .st-key-dm_theme_watch {{ position: absolute; width: 0; height: 0; overflow: hidden; }}
{nav_section_css()}
"""


def connection_status_html(state: str, label: str) -> str:
    """Header of the sidebar connection card. state: 'ok' | 'bad' | 'none'."""
    import html
    return (f'<div class="dm-conn-head"><span class="title">CONNECTION</span>'
            f'<span class="dm-conn-status {state}"><span class="dot"></span>{html.escape(label)}</span></div>')


def status_bar_html(state: str, message_html: str, hint: str = "") -> str:
    """One-line status bar. state: 'ok' | 'bad' | 'none'. message_html must already be escaped."""
    import html
    tail = f' <span class="hint">{html.escape(hint)}</span>' if hint else ''
    return f'<div class="dm-status {state}"><span class="dot"></span><span>{message_html}{tail}</span></div>'


def kpi_tile_html(icon: str, label: str, value, sub: str) -> str:
    import html
    return (f'<div class="dm-kpi"><span class="dm-kpi-icon">{icon}</span>'
            f'<div class="dm-kpi-label">{html.escape(label)}</div>\n'
            f'<div class="dm-kpi-value">{html.escape(str(value))}</div>\n'
            f'<div class="dm-kpi-sub">{html.escape(sub)}</div></div>')


def kv_rows_html(rows) -> str:
    """[(label, value_html), ...] as label / value rows (value_html must already be escaped)."""
    import html
    return "".join(f'<div class="dm-kv"><span class="k">{html.escape(k)}</span><span class="v">{v}</span></div>'
                   for k, v in rows)


def connection_project_html(project_name) -> str:
    """'📁 Project: Valmont' under the sidebar pickers (the File Library shows that project)."""
    import html
    value = f"<b>{html.escape(str(project_name))}</b>" if project_name else "not set (⚙️ Configuration → Projects)"
    return f'<div class="dm-conn-object">📁 Project: {value}</div>'


def connection_object_html(object_name) -> str:
    import html
    value = f"<b>{html.escape(str(object_name))}</b>" if object_name else "none selected"
    return f'<div class="dm-conn-object">🎯 Object: {value}</div>'


def apply_theme() -> None:
    """Inject the Tavant styles (call once per run, before the page content)."""
    st.markdown(f"<style>{_css()}</style>", unsafe_allow_html=True)


# Marks <html data-dm-theme="light|dark"> with the theme Streamlit is SHOWING, read from
# the app's text colour (light text = dark theme). Streamlit restyles the page instantly
# when the theme changes in ⋮ > Settings (a click) or under "System" (an OS change), but
# the server only hears about it on the next rerun -- so this runs in the browser.
THEME_WATCH_JS = """
export default function () {
  const root = document.documentElement;
  const detect = () => {
    const app = document.querySelector('[data-testid="stApp"]');
    if (!app) return;
    const rgb = (getComputedStyle(app).color.match(/[\\d.]+/g) || []).map(Number);
    if (rgb.length < 3) return;
    const theme = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255 > 0.5 ? 'dark' : 'light';
    if (root.dataset.dmTheme !== theme) root.dataset.dmTheme = theme;
  };
  detect();
  if (window.__dmThemeWatch) return;
  window.__dmThemeWatch = true;
  const soon = () => { requestAnimationFrame(detect); setTimeout(detect, 80); setTimeout(detect, 300); };
  document.addEventListener('click', soon, true);
  document.addEventListener('keyup', soon, true);
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', soon);
  const app = document.querySelector('[data-testid="stApp"]');
  if (app) new MutationObserver(detect).observe(app, { attributes: true, attributeFilter: ['class', 'style'] });
  setInterval(detect, 1000);  // safety net
}
"""
_theme_watch = (None, None)   # (component registry it was registered in, mount function)


def mount_theme_watcher() -> None:
    """Mount the theme watcher (call once per run, at the bottom of the sidebar).

    Registered once per Streamlit runtime: the registry belongs to the runtime, so a
    restarted runtime (or a new AppTest) needs the component registered again.
    """
    global _theme_watch
    from streamlit.components.v2 import get_bidi_component_manager
    registry = get_bidi_component_manager()
    owner, mount = _theme_watch
    if mount is None or owner is not registry:
        mount = st.components.v2.component("dm_theme_watch", js=THEME_WATCH_JS, isolate_styles=False)
        _theme_watch = (registry, mount)
    mount(key="dm_theme_watch")
    st.session_state['_dm_theme_watch_mounted'] = True


def _png_data_uri(path: str) -> str:
    import base64
    try:
        with open(path, 'rb') as handle:
            return "data:image/png;base64," + base64.b64encode(handle.read()).decode('ascii')
    except OSError:
        return ""


def hero_html() -> str:
    """Hero banner: the Tavant "T" icon, the product name and the four guided steps."""
    icon = _png_data_uri(BRAND_ICON)
    logo = f'<img src="{icon}" alt="Tavant">' if icon else 'TAVANT'
    return f"""<div class="dm-hero">
             <div class="dm-logo">{logo}</div>
             <div>
               <div class="dm-hero-row">
                 <div class="dm-title">DM <span>Toolkit</span></div>
                 <div class="dm-sub">Data Migration &amp; Validation Platform</div>
               </div>
               <div class="dm-chips">
                 <span><b>1</b>Source / Target</span><span><b>2</b>Map &amp; Validate</span>
                 <span><b>3</b>Load</span><span><b>4</b>Test</span>
               </div>
             </div>
           </div>"""


def render_header() -> None:
    """Hero banner at the top of every page."""
    st.markdown(hero_html(), unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    """The official Tavant wordmark at the top of the sidebar (its "T" icon when the sidebar is
    collapsed), with the product name under it."""
    if os.path.exists(BRAND_LOGO):
        st.logo(BRAND_LOGO, size="large", icon_image=BRAND_ICON if os.path.exists(BRAND_ICON) else None)
    st.markdown('<div class="dm-side-brand"><div class="name">DM Toolkit'
                '<small>Data Migration &amp; Validation</small></div></div>', unsafe_allow_html=True)