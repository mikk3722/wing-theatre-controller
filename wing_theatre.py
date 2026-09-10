"""
Wing Theatre Controller
DiGiCo-inspired snapshot and cue list control for Behringer Wing Rack
"""

import sys
import os
import datetime
import copy
import json
import threading

def _copy_channel_scopes(src):
    """
    Explicitly copy a {channel_key: ChannelScope} dict.
    Uses a simple loop instead of copy.deepcopy to avoid PyQt6/Python-3.14 slot crashes.
    ChannelScope is defined later in the file but this function is only CALLED at runtime.
    """
    result = {}
    for k, cs in src.items():
        new_cs = cs.__class__()          # calls ChannelScope.__init__()
        new_cs.overrides  = dict(cs.overrides)
        new_cs.fader_fade = float(cs.fader_fade)
        new_cs.sends_fade = float(cs.sends_fade)
        new_cs.send_overrides = dict(getattr(cs, 'send_overrides', {}))
        result[k] = new_cs
    return result
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget, QListWidgetItem,
    QSplitter, QDoubleSpinBox, QSpinBox, QTabWidget, QScrollArea, QGridLayout,
    QMessageBox, QInputDialog, QStatusBar, QToolBar, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QStyledItemDelegate, QStyleOptionViewItem,
    QCompleter, QMenu, QStyle, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize, QRect, QEvent, QStringListModel
from PyQt6.QtGui import (
    QColor, QPalette, QKeySequence, QShortcut, QFont,
    QPainter, QBrush, QPen
)

# ─── Colours ─────────────────────────────────────────────────────────────────
C = {
    "bg":           "#111111",
    "bg2":          "#1a1a1a",
    "bg3":          "#222222",
    "bg4":          "#2a2a2a",
    "border":       "#333333",
    "border2":      "#444444",
    "text":         "#e0e0e0",
    "text2":        "#aaaaaa",
    "text3":        "#666666",
    "green":        "#52b788",
    "green_bg":     "#1e3a2a",
    "green_border": "#2d6a4f",
    "red":          "#c0392b",
    "red_bg":       "#2a1a1a",
    "red_border":   "#5c1f1f",
    "amber":        "#f4a261",
    "amber_bg":     "#2a1e10",
    "blue":         "#4895ef",
    "active_cue":   "#1e2a22",
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: 'Helvetica Neue', Arial;
    font-size: 13px;
}}
QLabel {{ color: {C['text']}; background: transparent; }}
QLineEdit {{
    background: {C['bg3']}; color: {C['text']};
    border: 1px solid {C['border']}; border-radius: 4px; padding: 4px 8px;
}}
QLineEdit:focus {{ border-color: {C['green']}; }}
QPushButton {{
    background: {C['bg3']}; color: {C['text']};
    border: 1px solid {C['border']}; border-radius: 4px; padding: 5px 14px;
}}
QPushButton:hover {{ background: {C['bg4']}; border-color: {C['border2']}; }}
QPushButton:pressed {{ background: {C['bg']}; }}
QPushButton:disabled {{ color: {C['text3']}; border-color: {C['border']}; }}
QPushButton#go_btn {{
    background: {C['green_bg']}; color: {C['green']};
    border: 2px solid {C['green_border']}; border-radius: 6px;
    font-size: 18px; font-weight: bold; padding: 10px 30px;
    margin-top: 2px;
}}
QPushButton#go_btn:hover {{ background: #254d35; border-color: {C['green']}; }}
QPushButton#go_btn:pressed {{
    background: {C['green']}; color: {C['bg']};
    border-color: {C['green']}; margin-top: 3px; margin-bottom: -1px;
}}
QPushButton#go_btn:disabled {{
    background: {C['bg3']}; color: {C['text3']}; border-color: {C['border']};
}}
QPushButton#danger_btn {{
    background: {C['red_bg']}; color: {C['red']}; border: 1px solid {C['red_border']};
}}
QPushButton#danger_btn:hover {{ background: #3a1a1a; }}
QPushButton#green_btn {{
    background: {C['green_bg']}; color: {C['green']}; border: 1px solid {C['green_border']};
}}
QPushButton#green_btn:hover {{ background: #254d35; }}
QPushButton#amber_btn {{
    background: {C['amber_bg']}; color: {C['amber']}; border: 1px solid #5c3a10;
}}
QListWidget {{
    background: {C['bg']}; color: {C['text']};
    border: 1px solid {C['border']}; border-radius: 4px; outline: none;
}}
QListWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {C['border']}; }}
QListWidget::item:selected {{
    background: #1e3a5f; color: {C['text']}; border-left: 3px solid {C['text3']};
}}
QListWidget::item:hover {{ background: {C['bg3']}; }}
QTabWidget::pane {{ border: 1px solid {C['border']}; background: {C['bg2']}; }}
QTabBar::tab {{
    background: {C['bg3']}; color: {C['text2']};
    border: 1px solid {C['border']}; padding: 6px 16px;
    margin-right: 2px; border-bottom: none; border-radius: 4px 4px 0 0;
}}
QTabBar::tab:selected {{
    background: {C['bg2']}; color: {C['green']}; border-bottom: 2px solid {C['green']};
}}
QTabBar::tab:hover {{ color: {C['text']}; }}
QTreeWidget {{
    background: {C['bg']}; color: {C['text']};
    border: none; outline: none;
    alternate-background-color: {C['bg2']};
    show-decoration-selected: 1;
}}
QTreeWidget::item {{
    padding: 2px 4px;
    border-bottom: 1px solid #1e1e1e;
    min-height: 28px;
}}
QTreeWidget::item:selected {{
    background: {C['active_cue']}; color: {C['text']};
}}
QTreeWidget::item:hover {{ background: {C['bg3']}; }}
QTreeWidget::branch {{
    background: {C['bg']};
}}
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {{
    border-image: none;
    image: none;
}}
QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {{
    border-image: none;
    image: none;
}}
QHeaderView::section {{
    background: {C['bg3']}; color: {C['text3']};
    border: none; border-right: 1px solid {C['border']};
    border-bottom: 1px solid {C['border']};
    padding: 4px 6px; font-size: 10px; letter-spacing: 0.04em;
}}
QScrollBar:vertical {{
    background: {C['bg']}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C['border2']}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {C['bg']}; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {C['border2']}; border-radius: 4px; min-width: 30px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QDoubleSpinBox, QSpinBox {{
    background: {C['bg3']}; color: {C['text']};
    border: 1px solid {C['border']}; border-radius: 4px; padding: 4px 8px;
}}
QGroupBox {{
    color: {C['text3']}; border: 1px solid {C['border']};
    border-radius: 6px; margin-top: 14px; padding-top: 10px;
    font-size: 10px; letter-spacing: 0.08em;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {C['text3']};
}}
QStatusBar {{
    background: {C['bg']}; color: {C['text3']};
    border-top: 1px solid {C['border']}; font-size: 11px;
}}
QSplitter::handle {{ background: {C['border']}; width: 1px; height: 1px; }}
QToolBar {{
    background: {C['bg']}; border-bottom: 1px solid {C['border']};
    spacing: 4px; padding: 4px 8px;
}}
QTableWidget {{
    background: {C['bg']}; color: {C['text']};
    border: 1px solid {C['border']}; gridline-color: {C['border']}; outline: none;
}}
QTableWidget::item {{ padding: 4px 8px; }}
QTableWidget::item:selected {{ background: {C['active_cue']}; color: {C['green']}; }}
"""

# ─── Wing Snapshot Scope -- matches Wing's exact 24 scope parameters ───────────
#
# Wing's actual scope params (from Home > Library > Snapshots > Save + Scope):
#   Config, Surface, Prefs, Left/Center/Right layers, CC
#   Customization, Tags, Conn, In, Filter, Delay, Gate, Dynamics,
#   Pre Insert, Post Insert, EQ, Pan, Mains, Sends, Fader, Mute, Config(rack)
#
# We map these to columns in the scope tree.

WING_SCOPE_COLS = [
    # (key,         short label,  tooltip)
    ("conn",        "Conn",       "Connection / Patch / Source"),
    ("in",          "In",         "Input Gain, Trim, Polarity"),
    ("filter",      "Filter",     "HPF, LPF, Tilt EQ"),
    ("delay",       "Delay",      "Channel Delay"),
    ("gate",        "Gate",       "Gate / Expander"),
    ("dynamics",    "Dyn",        "Compressor / Dynamics"),
    ("pre_insert",  "Pre Ins",    "Pre-Fader Insert FX slot"),
    ("post_insert", "Post Ins",   "Post-Fader Insert FX slot"),
    ("eq",          "EQ",         "Parametric EQ"),
    ("pan",         "Pan",        "Pan / Balance"),
    ("mains",       "Mains",      "Main Output Assignment & Level (M1–M4)"),
    ("sends",       "Sends",      "Bus & Matrix Send Levels / Mutes"),
    ("fader",       "Fader",      "Fader Level"),
    ("mute",        "Mute",       "Mute Status"),
    ("rack_config", "Cfg",        "Rack / Processing Order & Tap Points"),
    ("custom",      "Name",       "Channel Name & Icon (Customization)"),
    ("tags",        "Tags",       "DCA & Mute Group Assignments"),
]

WING_SCOPE_KEYS = [k for k, _, _ in WING_SCOPE_COLS]

# Default ON = most processing; OFF = patch/routing/cosmetic
DEFAULT_SCOPE = {k: True for k in WING_SCOPE_KEYS}
for k in ["conn", "rack_config", "tags"]:
    DEFAULT_SCOPE[k] = False
# custom (name/color/icon) is ON by default — part of snapshot identity

# Path groups in the main channel scope tree (no FX or Config here)
SCOPE_PATH_GROUPS = [
    ("inputs", "All Input Channels", [(f"input_{i+1:02d}", f"Input Ch {i+1:02d}") for i in range(48)]),
    ("buses",  "All Buses",          [(f"bus_{i+1:02d}",   f"Bus {i+1:02d}")       for i in range(16)]),
    ("matrix", "All Matrix Outputs", [(f"matrix_{i+1:02d}",f"Matrix {i+1:02d}")    for i in range(8)]),
    ("mains",  "Main Outputs",       [("main_1","Main 1"), ("main_2","Main 2"),
                                      ("main_3","Main 3"), ("main_4","Main 4")]),
    ("dcas",   "DCA Groups",         [(f"dca_{i+1:02d}",   f"DCA {i+1:02d}")       for i in range(16)]),
]

# Scope keys applicable to DCA groups (no EQ, dynamics, inserts, sends, filter, input)
DCA_APPLICABLE = {"fader", "mute", "custom"}

# FX slots -- simple single on/off per slot (stored in snapshot.fx_scope)
FX_SLOTS = [(f"fx_{i+1:02d}", f"FX Slot {i+1:02d}") for i in range(16)]

# Console config items -- simple single on/off each (stored in snapshot.cfg_scope)
CFG_ITEMS = [
    ("cfg_surface", "Surface Layout"),
    ("cfg_prefs",   "Preferences"),
    ("cfg_layers",  "Layers  (Left / Centre / Right)"),
    ("cfg_cc",      "Custom Controls (CC)"),
]

# Defaults for FX and Config scope -- defined here so FX_SLOTS/CFG_ITEMS exist
# These are mutable at runtime via the Default Scope dialog
DEFAULT_FX_SCOPE  = {k: True  for k, _ in FX_SLOTS}
DEFAULT_CFG_SCOPE = {k: False for k, _ in CFG_ITEMS}

# Default crossfade times per path group -- mutable at runtime via Default Scope dialog
DEFAULT_GROUP_FADES = {gk: {"fader": 0.0, "sends": 0.0} for gk, _, _ in SCOPE_PATH_GROUPS}

# ─── Wing OSC Path Mappings ─────────────────────────────────────────────────
# Wing OSC path mapping constants -- inserted after DEFAULT_GROUP_FADES

WING_CH_PATHS = {}
for _i in range(48): WING_CH_PATHS[f"input_{_i+1:02d}"] = f"/ch/{_i+1}"
for _i in range(16): WING_CH_PATHS[f"bus_{_i+1:02d}"]   = f"/bus/{_i+1}"
for _i in range(8):  WING_CH_PATHS[f"matrix_{_i+1:02d}"]= f"/mtx/{_i+1}"
for _i in range(4):  WING_CH_PATHS[f"main_{_i+1}"]      = f"/main/{_i+1}"
for _i in range(16): WING_CH_PATHS[f"dca_{_i+1:02d}"]   = f"/dca/{_i+1}"

# Scope key -> sub-paths relative to channel base (/ch/1, /bus/2, …)
WING_SCOPE_SUBPATHS = {
    "fader":       ["/fdr"],
    "mute":        ["/mute"],
    "pan":         ["/pan", "/panmode"],
    "in":          ["/trim", "/src", "/pol"],
    "filter":      ["/hpf/on", "/hpf/freq", "/hpf/slop",
                    "/lpf/on", "/lpf/freq", "/lpf/slop"],
    "delay":       ["/dly/on", "/dly/time"],
    "gate":        ["/gate/on", "/gate/thr", "/gate/rng",
                    "/gate/atk", "/gate/hld", "/gate/rel"],
    "dynamics":    ["/dyn/on", "/dyn/thr", "/dyn/rat",
                    "/dyn/kne", "/dyn/atk", "/dyn/rel", "/dyn/gain"],
    "pre_insert":  ["/preins/on", "/preins/slot"],
    "post_insert": ["/postins/on", "/postins/slot"],
    "eq":          ["/eq/on"] +
                   [f"/eq/{b}/{p}" for b in range(1, 7)
                    for p in ["g", "f", "q", "t"]],
    "mains":       [f"/mout/{m}/on"  for m in range(1, 5)] +
                   [f"/mout/{m}/lvl" for m in range(1, 5)],
    "sends":       [f"/send/{b}/on"  for b in range(1, 17)] +
                   [f"/send/{b}/lvl" for b in range(1, 17)],
    "conn":        ["/src"],
    "custom":      ["/name", "/icon"],
    "tags":        [f"/dca/{d}"  for d in range(1, 17)] +
                   [f"/mgrp/{m}" for m in range(1, 9)],
    "rack_config": ["/proc"],
}



# Default per-channel scope overrides -- stores the exact channel_scopes from the
# Default dialog so _reset_default and new snapshots get a 1-to-1 copy.
DEFAULT_CHANNEL_SCOPES = {}   # channel_key -> ChannelScope

# Auto-update exclusion parameters.
# Each has 3 possible states: "snap" (current snapshot), "group" (current cue group), "all" (all snapshots)
# Auto-update exclusion parameters -- derived from WING_SCOPE_COLS so they match
# the snapshot scope categories exactly. Label = "Short -- Tooltip" for readability.
AU_PARAMS = [(key, f"{short}  --  {tip}") for key, short, tip in WING_SCOPE_COLS] + [
    ("fx_rack", "FX Racks  --  Global FX Rack Effects (Rack 1–16)"),
]
AU_STATES = ["snap", "group", "all"]   # 3 column values

SECTION_COLORS = ["#52b788","#e76f51","#4895ef","#f4a261","#c77dff","#ff6b6b"]

# ─── Data Model ──────────────────────────────────────────────────────────────

class Section:
    def __init__(self, name, color="#52b788"):
        self.name = name
        self.color = color
        # "snap" = current snapshot only, "group" = current cue group, "all" = all snapshots
        # Start everything as "all", then opt-in the most snapshot-specific params to "snap"
        self.exclusions = {k: "all" for k, _ in AU_PARAMS}
        for k in ["fader", "mute", "sends", "fx_rack"]:
            if k in self.exclusions:
                self.exclusions[k] = "snap"
        self.channels = []

    def to_dict(self):
        return {"name":self.name,"color":self.color,
                "exclusions":self.exclusions,"channels":self.channels}

    @staticmethod
    def from_dict(d):
        s = Section(d["name"], d.get("color","#52b788"))
        raw = d.get("exclusions", s.exclusions)
        # Backwards compat: True -> "snap", False -> "all"
        migrated = {}
        for k, v in raw.items():
            if v is True:   migrated[k] = "snap"
            elif v is False: migrated[k] = "all"
            else:            migrated[k] = v
        s.exclusions = migrated
        s.channels = d.get("channels", [])
        return s


class ChannelScope:
    def __init__(self):
        self.overrides   = {}    # scope_key -> bool
        self.fader_fade  = 0.0   # seconds (0 = use group default)
        self.sends_fade  = 0.0   # seconds (0 = use group default)
        # Per-bus send overrides: bus_num (1-16) -> bool. Only set when the
        # user has explicitly customised an individual send in the expanded
        # Sends columns. Absent = fall back to the aggregate 'sends' entry
        # in `overrides` (unchanged existing behaviour).
        self.send_overrides = {}

    def to_dict(self):
        return {"overrides": self.overrides,
                "fader_fade": self.fader_fade,
                "sends_fade": self.sends_fade,
                "send_overrides": self.send_overrides}

    @staticmethod
    def from_dict(d):
        cs = ChannelScope()
        # backwards compat: old files stored just the overrides dict
        if isinstance(d, dict) and "overrides" in d:
            cs.overrides   = d.get("overrides", {})
            cs.fader_fade  = d.get("fader_fade", 0.0)
            cs.sends_fade  = d.get("sends_fade", 0.0)
            # Old files won't have this key -- default to {} (no per-bus
            # customisation), same as a brand new ChannelScope. Keys are
            # raw strings matching Wing's own send-destination naming
            # ("1".."16" for buses, "MX1".."MX8" for matrix) -- JSON object
            # keys are already strings, so no conversion needed.
            cs.send_overrides = d.get("send_overrides", {})
        else:
            cs.overrides = d   # old format
        return cs


class Snapshot:
    def __init__(self, name="New Snapshot", number=1):
        self.number = number
        self.name   = name
        self.notes  = ""
        self.data   = {}
        self.scope  = dict(DEFAULT_SCOPE)
        # Copy default per-channel overrides directly (1-to-1 from Default dialog)
        self.channel_scopes = _copy_channel_scopes(DEFAULT_CHANNEL_SCOPES)
        self.fx_scope   = dict(DEFAULT_FX_SCOPE)
        self.cfg_scope  = dict(DEFAULT_CFG_SCOPE)
        # Per-group fade defaults: group_key -> {"fader": secs, "sends": secs}
        self.group_fades = {gk: dict(fades) for gk, fades in DEFAULT_GROUP_FADES.items()}
        self.cue_group   = ""
        self.osc_messages = []

    def get_ch_scope(self, key):
        if key not in self.channel_scopes:
            self.channel_scopes[key] = ChannelScope()
        return self.channel_scopes[key]

    def get_group_fade(self, group_key, param="fader"):
        return self.group_fades.get(group_key, {}).get(param, 0.0)

    def set_group_fade(self, group_key, param, value):
        if group_key not in self.group_fades:
            self.group_fades[group_key] = {}
        self.group_fades[group_key][param] = value

    def to_dict(self):
        return {"number":self.number,"name":self.name,"notes":self.notes,
                "cue_group":self.cue_group,
                "data":self.data,"scope":self.scope,
                "channel_scopes":{k:v.to_dict() for k,v in self.channel_scopes.items()},
                "fx_scope":self.fx_scope,"cfg_scope":self.cfg_scope,
                "group_fades":self.group_fades,
                "osc_messages":self.osc_messages}

    @staticmethod
    def from_dict(d):
        s = Snapshot(d.get("name","Snapshot"),d.get("number",1))
        s.notes       = d.get("notes","")
        s.cue_group   = d.get("cue_group","")
        s.data        = d.get("data",{})
        s.scope       = d.get("scope",dict(DEFAULT_SCOPE))
        s.channel_scopes = {k:ChannelScope.from_dict(v)
                            for k,v in d.get("channel_scopes",{}).items()}
        s.fx_scope    = d.get("fx_scope",  {k: True  for k,_ in FX_SLOTS})
        s.cfg_scope   = d.get("cfg_scope", {k: False for k,_ in CFG_ITEMS})
        s.group_fades = d.get("group_fades", {})
        s.osc_messages = d.get("osc_messages", [])
        return s


class OscOutput:
    """An external OSC target -- messages are sent to this endpoint on snapshot recall."""
    def __init__(self, name="OSC Output", ip="127.0.0.1", port=8000, bind_ip=""):
        self.name    = name
        self.ip      = ip
        self.port    = port
        self.enabled = True
        self.bind_ip = bind_ip  # local interface IP, "" = auto

    def to_dict(self):
        return {"name":self.name,"ip":self.ip,"port":self.port,"enabled":self.enabled,"bind_ip":self.bind_ip}

    @staticmethod
    def from_dict(d):
        o = OscOutput(d.get("name","OSC Output"),d.get("ip","127.0.0.1"),d.get("port",8000),d.get("bind_ip",""))
        o.enabled = d.get("enabled",True); return o


class ShowFile:
    def __init__(self):
        self.name = "New Show"
        self.snapshots  = []
        self.sections   = []
        self.osc_outputs = []
        self.groups     = []   # ordered list of group names (persists independently of snapshots)
        self.filepath   = None
        # App-level UI settings persisted per show: Wing IP/interface, OSC/TCP
        # remote control ports + on-off state, autosave interval, and the
        # customised Default Recall Scope (edited via right-click Default).
        # Populated by MainWindow._collect_app_settings() just before saving,
        # and applied back by MainWindow._apply_app_settings() after loading.
        self.app_settings = {}

    def to_dict(self):
        return {"name":self.name,
                "groups": self.groups,
                "snapshots":[s.to_dict() for s in self.snapshots],
                "sections": [s.to_dict() for s in self.sections],
                "osc_outputs":[o.to_dict() for o in self.osc_outputs],
                "app_settings": self.app_settings}

    def save(self, fp):
        with open(fp,"w") as f: json.dump(self.to_dict(),f,indent=2)
        self.filepath = fp

    @staticmethod
    def load(fp):
        with open(fp) as f: d = json.load(f)
        s = ShowFile()
        import os
        filename_name = os.path.splitext(os.path.basename(fp))[0]
        stored_name = d.get("name", "Show")
        # Use filename as name (more reliable than stored name which may be default)
        s.name = filename_name if stored_name in ("New Show", "Show", "") else stored_name
        s.groups     = d.get("groups", [])
        s.snapshots  = [Snapshot.from_dict(x) for x in d.get("snapshots",[])]
        s.sections   = [Section.from_dict(x)  for x in d.get("sections",[])]
        s.osc_outputs = [OscOutput.from_dict(x) for x in d.get("osc_outputs",[])]
        s.app_settings = d.get("app_settings", {})   # missing on older show files -- fine, just empty
        # Ensure any group used in a snapshot also exists in the groups list
        for snap in s.snapshots:
            g = (snap.cue_group or "").strip()
            if g and g not in s.groups:
                s.groups.append(g)
        s.filepath   = fp
        return s



# ─── Remote Control TCP Server ────────────────────────────────────────────────
class RemoteTCPServer(QObject):
    """
    Single-client TCP server for Companion/remote control.
    Protocol (newline-delimited UTF-8):
      Client→Server:  GO / NEXT_GO / PREV_GO / SNAP_GO <n|name>
                      AU_ON / AU_OFF / AU_TOGGLE / ADD_SNAP [name] / GET_STATE
      Server→Client:  STATE key=value
    """
    command_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._port    = 9000
        self._server  = None
        self._client  = None
        self._client_addr = None
        self._running = False
        self._thread  = None
        self._lock    = threading.Lock()

    def start(self, port: int):
        self.stop()
        self._port    = port
        self._running = True
        self._thread  = threading.Thread(target=self._serve, daemon=True,
                                          name="RemoteTCP")
        self._thread.start()

    def stop(self):
        self._running = False
        with self._lock:
            if self._client:
                try: self._client.close()
                except: pass
                self._client = None
            if self._server:
                try: self._server.close()
                except: pass
                self._server = None

    def send_state(self, key: str, value):
        msg = f"STATE {key}={value}\n"
        with self._lock:
            c = self._client
        if not c:
            return
        try:
            c.sendall(msg.encode())
        except Exception:
            with self._lock:
                self._client = None

    def send_full_state(self, state: dict):
        for k, v in state.items():
            self.send_state(k, v)

    @property
    def client_addr(self):
        return self._client_addr

    def _serve(self):
        import socket as _socket
        try:
            srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", self._port))
            srv.listen(1)
            srv.settimeout(1.0)
            with self._lock:
                self._server = srv
            while self._running:
                try:
                    conn, addr = srv.accept()
                except _socket.timeout:
                    continue
                except Exception:
                    break
                with self._lock:
                    if self._client:
                        try: self._client.close()
                        except: pass
                    self._client = conn
                    self._client_addr = addr[0]
                self.command_received.emit(f"__connected__{addr[0]}")
                self._handle_client(conn)
                with self._lock:
                    if self._client is conn:
                        self._client = None
                        self._client_addr = None
                self.command_received.emit("__disconnected__")
        except Exception:
            pass

    def _handle_client(self, conn):
        import socket as _socket
        buf = ""
        conn.settimeout(1.0)
        while self._running:
            try:
                data = conn.recv(1024).decode(errors="replace")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self.command_received.emit(line)
            except (_socket.timeout, TimeoutError):
                continue  # normal — no data yet, keep waiting
            except Exception:
                break     # real error — close connection


# ─── OSC Engine ──────────────────────────────────────────────────────────────




def _find_propmap_path():
    """Find propmap.jsonl — works in dev, PyInstaller bundle, and cross-platform."""
    import sys, os
    # 1. PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, 'propmap.jsonl')
        if os.path.exists(p): return p
    # 2. Same folder as script/exe
    base = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__))
    p = os.path.join(base, 'propmap.jsonl')
    if os.path.exists(p): return p
    # 3. Mac dev path
    p = os.path.expanduser('~/WingTheatre/libwing/propmap.jsonl')
    if os.path.exists(p): return p
    return os.path.join(base, 'propmap.jsonl')


def _find_wingmon_path():
    """Find wingmon binary — works in dev, PyInstaller, Windows and macOS."""
    import sys, os, shutil
    exe_name = 'wingmon.exe' if sys.platform == 'win32' else 'wingmon'
    # Older macOS builds bundled the binary under its build-artifact name
    # ('wingmon-macos') instead of the plain name below -- checked as a
    # fallback so already-downloaded older builds don't regress, though
    # current builds bundle it correctly under 'wingmon' now.
    alt_names = ['wingmon-macos'] if sys.platform == 'darwin' else []
    # 1. PyInstaller bundle
    if hasattr(sys, '_MEIPASS'):
        for name in [exe_name] + alt_names:
            p = os.path.join(sys._MEIPASS, name)
            if os.path.exists(p): return p
    # 2. Same folder as script/exe
    base = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, 'frozen', False) else __file__))
    for name in [exe_name] + alt_names:
        p = os.path.join(base, name)
        if os.path.exists(p): return p
    # 3. Mac dev path
    p = os.path.expanduser(f'~/WingTheatre/{exe_name}')
    if os.path.exists(p): return p
    # 4. System PATH
    p = shutil.which(exe_name)
    if p: return p
    return os.path.join(base, exe_name)  # fallback for error message


class WingOSC(QObject):
    """
    Behringer Wing OSC engine -- firmware 3.x / port 2223 UDP.

    Uses raw UDP socket + manual OSC parsing to avoid python-osc quirks.
    Subscription: /wremote ,s osc  (renewed every 8 s).
    Capture: polls each parameter individually with GET requests.
    Recall:  sends dB values as floats, ints as ints.
    """

    connected          = pyqtSignal(bool)
    log_message        = pyqtSignal(str)
    capture_done       = pyqtSignal(dict, int)   # (data, target_snapshot_idx)
    parameter_received = pyqtSignal(str, object)
    connection_lost    = pyqtSignal()
    connection_ready   = pyqtSignal()   # emitted on main thread after connect
    capture_finished   = pyqtSignal()   # emitted from wingmon thread -> finish on main
    sync_complete      = pyqtSignal(int)   # initial state sync done (param count)
    WING_PORT    = 2223
    WINGMON_PATH = _find_wingmon_path()
    PROPMAP_PATH   = _find_propmap_path()
    POLL_PARAMS = [
        # Fader / Mute / Pan / Width
        ("fader",    "/fdr"),
        ("mute",     "/mute"),
        ("pan",      "/pan"),
        ("pan",      "/wid"),   # stereo width
        # Input
        ("in",       "/in/set/trim"), ("in", "/in/set/inv"),
        ("in",       "/in/set/srcauto"), ("in", "/in/set/altsrc"),
        ("in",       "/in/set/dlyon"), ("in", "/in/set/dlymode"), ("in", "/in/set/dly"),
        # Connection / Patch
        ("conn",     "/in/conn/grp"), ("conn", "/in/conn/in"),
        ("conn",     "/in/conn/altgrp"), ("conn", "/in/conn/altin"),
        # Filter
        ("filter",   "/flt/lc"),  ("filter", "/flt/lcf"), ("filter", "/flt/lcs"),
        ("filter",   "/flt/hc"),  ("filter", "/flt/hcf"), ("filter", "/flt/hcs"),
        ("filter",   "/flt/tf"),
        # Gate
        ("gate", "/gate/on"),  ("gate", "/gate/mix"),  ("gate", "/gate/gain"),
        ("gate", "/gate/thr"), ("gate", "/gate/range"),
        ("gate", "/gate/att"), ("gate", "/gate/hld"),  ("gate", "/gate/rel"),
        ("gate", "/gate/acc"), ("gate", "/gate/ratio"),
        # Dynamics
        ("dynamics", "/dyn/on"),  ("dynamics", "/dyn/mix"),  ("dynamics", "/dyn/gain"),
        ("dynamics", "/dyn/thr"), ("dynamics", "/dyn/ratio"), ("dynamics", "/dyn/knee"),
        ("dynamics", "/dyn/det"), ("dynamics", "/dyn/att"),  ("dynamics", "/dyn/hld"),
        ("dynamics", "/dyn/rel"), ("dynamics", "/dyn/env"),  ("dynamics", "/dyn/auto"),
        # Pre/Post Insert
        ("pre_insert",  "/preins/on"),  ("pre_insert",  "/preins/ins"),
        ("post_insert", "/postins/on"), ("post_insert", "/postins/ins"),
        ("post_insert", "/postins/mode"),
        # EQ (confirmed OSC format: 1g not 1/g)
        ("eq",  "/eq/on"),
        ("eq",  "/eq/lg"), ("eq", "/eq/lf"), ("eq", "/eq/lq"),
        ("eq",  "/eq/1g"), ("eq", "/eq/1f"), ("eq", "/eq/1q"),
        ("eq",  "/eq/2g"), ("eq", "/eq/2f"), ("eq", "/eq/2q"),
        ("eq",  "/eq/3g"), ("eq", "/eq/3f"), ("eq", "/eq/3q"),
        ("eq",  "/eq/4g"), ("eq", "/eq/4f"), ("eq", "/eq/4q"),
        ("eq",  "/eq/5g"), ("eq", "/eq/5f"), ("eq", "/eq/5q"),
        ("eq",  "/eq/6g"), ("eq", "/eq/6f"), ("eq", "/eq/6q"),
        ("eq",  "/eq/hg"), ("eq", "/eq/hf"), ("eq", "/eq/hq"),
        # Bus Delay (bus/mtx/main only)
        ("delay",    "/dly/on"),  ("delay", "/dly/mode"), ("delay", "/dly/dly"),
        # Custom
        ("custom",   "/name"), ("custom", "/icon"), ("custom", "/col"),
        # Tags (DCA & mute group assignments)
        ("tags",     "/tags"),
        # Rack config
        ("rack_config", "/proc"), ("rack_config", "/ptap"),
    ] + [("sends", f"/send/{b}/on")  for b in range(1, 17)] \
      + [("sends", f"/send/{b}/lvl") for b in range(1, 17)] \
      + [("sends", f"/send/{b}/pan") for b in range(1, 17)] \
      + [("mains", f"/main/{m}/on")  for m in range(1, 5)]  \
      + [("mains", f"/main/{m}/lvl") for m in range(1, 5)]  \
      + [("mains", f"/main/{m}/pre") for m in range(1, 5)]


    def __init__(self):
        super().__init__()
        self.ip             = "192.168.1.1"
        self.port           = self.WING_PORT
        self.local_ip       = "0.0.0.0"   # set on connect
        self.is_connected   = False
        self._wing_state    = {}
        # _wing_state is written from the wingmon background thread (every
        # live event) and iterated/copied from the main thread (Add Snap,
        # Update from Wing, Auto Update, fade start-value lookups). Without
        # this lock, a live event arriving mid-iteration can raise
        # "RuntimeError: dictionary changed size during iteration" and
        # crash the app -- this was intermittent and hit more easily on
        # Windows due to differing thread scheduling.
        self._wing_state_lock = threading.Lock()
        self._capture_buf_lock = threading.Lock()  # same race risk as _wing_state, during "Store from Wing"
        self._auto_update   = False
        self._auto_update_count = 0
        self._au_baseline   = {}
        self._capturing     = False
        self._capture_buf   = {}
        self._capture_timer = None
        self._poll_index    = 0
        self._poll_paths    = []
        self._learned_poll_paths = []
        self._fades         = []
        self._fade_jobs     = []
        # path -> {"target": end_db, "deadline": timestamp}. While a path is
        # fading, Auto Update ignores live events for it UNTIL the incoming
        # value actually matches "target" (the fade's real destination) --
        # far more reliable than guessing how long Wing's echo round-trip
        # takes. "deadline" is only a safety fallback so a path can't stay
        # suppressed forever if the target is somehow never seen.
        self._fading_paths  = {}
        self._unified_timer = QTimer(self)
        self._unified_timer.timeout.connect(self._unified_step)
        # Thread-safe signal routing
        self.connection_ready.connect(self._poll_dynamic_models,
                                      Qt.ConnectionType.QueuedConnection)
        self.capture_finished.connect(self._finish_capture,
                                      Qt.ConnectionType.QueuedConnection)
        self.sync_complete.connect(
            self._on_sync_complete, Qt.ConnectionType.QueuedConnection)
        self._wingmon_proc  = None
        self._wingmon_running = False
        self._prop_lookup   = {}
        self._dyn_models    = {}   # {(ch_path, section): model_name}

    def set_auto_update(self, enabled, poll_paths=None):
        """
        Toggle AU. Wingmon handles ALL real-time push events.
        OSC polling is ONLY used in start_capture (Store from Wing).
        If wingmon is not running, AU shows a warning but does NOT fall back to polling.
        """
        try:
            self._set_auto_update_impl(enabled, poll_paths)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log_message.emit(f"⚠ Auto Update error: {e}")

    def _set_auto_update_impl(self, enabled, poll_paths=None):
        self._auto_update = enabled
        self._auto_update_count = 0
        # Stop any leftover timers from old sessions
        for attr in ("_au_poll_timer", "_au_report_timer", "_eq_poll_timer"):
            t = getattr(self, attr, None)
            if t:
                try: t.stop()
                except: pass
        if not enabled:
            return
        # Populate baseline from current wing_state
        with self._wing_state_lock:
            snapshot_items = list(self._wing_state.items())
        for k, v in snapshot_items:
            if k not in self._au_baseline:
                self._au_baseline[k] = v
        wingmon_running = bool(getattr(self, "_wingmon_proc", None))
        if wingmon_running:
            self.log_message.emit("Auto Update ON -- wingmon real-time push active")
        else:
            self.log_message.emit(
                "⚠ Auto Update ON -- wingmon not running. "
                "Store from Wing first, then reconnect.")
        self._au_report_timer = QTimer(self)
        self._au_report_timer.setInterval(3000)
        self._au_report_timer.timeout.connect(self._report_au_activity)
        self._au_report_timer.start()

    def _load_dynamic_propmap(self):
        """
        Load propmap.jsonl to resolve anonymous propN events from wingmon.
        Returns ({(section, index): param_name}, float_key_sets).

        IMPORTANT (confirmed from real propmap.jsonl, Sep 2026 libwing):
        fullname paths do NOT embed a model name. It's simply
        /ch/1/eq/lg, /ch/1/eq/1g, /ch/1/eq/leq etc -- section then the
        parameter name directly, e.g.:
            {"fullname":"/ch/1/eq/lg","id":-959296371,"index":1,...}
            {"fullname":"/ch/1/eq/1g","id":349565323,"index":5,...}
        An EARLIER version of libwing (checked back in August) DID embed
        the model in the path (/ch/1/eq/STD/lg) -- that schema is gone.
        Our lookup previously assumed the old 5+-segment/model-in-path
        shape, which made `param` always come out empty and `lookup` end
        up with 0 entries -- explaining why every band-indexed parameter
        (everything except explicitly-named ones) silently failed to
        resolve, while models themselves (an unrelated, always-named /mdl
        path) kept working fine.

        float_key_sets is a dict with two members used to check whether a
        given RUNTIME path is float-typed:
          - 'plain': literal fullname strings, for anything not matching
            the sectioned pattern (still exact-match, e.g. /ch/N/fdr).
          - 'sectioned': (section, param) tuples, channel/bus-number
            agnostic (propmap.jsonl only lists channel 1, e.g. /ch/1/eq/lg
            -- comparing against a path built for /ch/5/eq/lg needs the
            channel number ignored, same reasoning as before, just without
            the model dimension that never actually existed).
        """
        import json
        lookup = {}
        float_plain     = set()
        float_sectioned = set()
        CHANNEL_SECTIONS = {"eq", "gate", "dyn", "flt"}
        FLOAT_TYPES = {"linear float", "log float"}
        try:
            with open(self.PROPMAP_PATH) as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        fn   = e.get("fullname", "")
                        pidx = e.get("index", 0)
                        tp   = e.get("type", "")
                        if not fn:
                            continue
                        parts = fn.split("/")
                        is_float = tp in FLOAT_TYPES and "$" not in fn
                        # /ch/1/eq/lg -> parts = ['', 'ch', '1', 'eq', 'lg']
                        is_sectioned = (len(parts) == 5 and
                                        parts[1] in ("ch","bus","mtx","main","dca") and
                                        parts[3] in CHANNEL_SECTIONS)
                        # /fx/1/mix -> parts = ['', 'fx', '1', 'mix']
                        is_fx = (len(parts) == 4 and parts[1] == "fx")
                        if is_sectioned:
                            sec, param = parts[3], parts[4]
                            if is_float:
                                float_sectioned.add((sec, param))
                            if pidx > 0:
                                lookup.setdefault((sec, pidx), param)
                        elif is_fx:
                            param = parts[3]
                            if is_float:
                                float_sectioned.add(("fx", param))
                            if pidx > 0:
                                lookup.setdefault(("fx", pidx), param)
                        elif is_float:
                            float_plain.add(fn)
                    except Exception:
                        pass
            self.log_message.emit(
                f"Dynamic propmap: {len(lookup)} entries "
                f"(EQ/Gate/Dyn/Filter/FX), "
                f"{len(float_plain) + len(float_sectioned)} float-type params")
        except FileNotFoundError:
            self.log_message.emit(
                "propmap.jsonl not found -- wingmon props won't be fully resolved")
        return lookup, {'plain': float_plain, 'sectioned': float_sectioned}

    def _is_float_path(self, path):
        """Check whether a runtime path is a known float-typed parameter,
        channel/bus-number-agnostic (see _load_dynamic_propmap).

        Handles TWO path shapes that both occur in practice:
          - /ch/N/eq/1g            (propN-resolved, via our propmap lookup
            -- most band-indexed params, no model segment)
          - /ch/N/eq/STD/hf        (sent directly by Wing as a fully named
            event, WITH the model segment -- confirmed from a real capture:
            the high-shelf band comes through this way even though every
            other EQ band comes through the plain, model-less form above.
            Both shapes are real and must both be recognised.)
        """
        fk = getattr(self, '_float_keys', None)
        if not fk:
            return False
        parts = path.split('/')
        if len(parts) >= 5 and parts[1] in ("ch","bus","mtx","main","dca") and parts[3] in ("eq","gate","dyn","flt"):
            # Try the plain (no-model) param first: /ch/N/section/param
            if (parts[3], parts[4]) in fk['sectioned']:
                return True
            # Fall back to the model-included shape: /ch/N/section/MODEL/param
            if len(parts) >= 6 and (parts[3], parts[5]) in fk['sectioned']:
                return True
            return False
        if len(parts) >= 4 and parts[1] == "fx":
            if ("fx", parts[3]) in fk['sectioned']:
                return True
            if len(parts) >= 5 and ("fx", parts[4]) in fk['sectioned']:
                return True
            return False
        return path in fk['plain']

    def _resolve_prop(self, section, model, idx, ch_path, val_str):
        """Safety-net resolver for propN events from a wingmon build that
        predates hash support (see print_node/wingmon.rs) -- current builds
        always send the hash directly and this path is not exercised.
        Falls back to propmap.jsonl (only ever describes ONE canonical
        model per section -- fine when the active model happens to match
        it, wrong otherwise; see _load_dynamic_propmap). Returns None on a
        miss rather than guessing, since a wrong parameter name is worse
        than no data at all.
        """
        return self._prop_lookup.get((section, idx))

    def connect(self, ip, port=2223, local_ip="0.0.0.0"):
        """Connect to Wing via wingmon TCP. No OSC socket needed."""
        self.ip       = ip
        self.port     = port
        self.local_ip = local_ip
        self._start_wingmon()

    def disconnect(self):
        self.is_connected = False
        self._stop_wingmon()
        for t in [getattr(self, '_au_report_timer', None),
                  getattr(self, '_capture_timer', None),
                  getattr(self, '_keepalive_timer', None)]:
            if t:
                try: t.stop()
                except: pass
        self._cancel_all_fades()
        with self._wing_state_lock:
            self._wing_state.clear()
        self._au_baseline.clear()
        self._dyn_models.clear()
        self.connected.emit(False)
        self.log_message.emit('Disconnected from Wing')

    def _start_wingmon(self):
        """Start wingmon -- runs constantly while connected to Wing."""
        if not os.path.exists(self.WINGMON_PATH):
            self.log_message.emit(
                f"wingmon not found at {self.WINGMON_PATH}")
            return
        import subprocess, threading
        try:
            self._prop_lookup, self._float_keys = self._load_dynamic_propmap()
            self._dyn_models    = {}
            self._wingmon_running = True

            # Try to ensure Wing traffic routes through the selected interface.
            # Prevents Wing traffic taking the wrong path when multiple
            # interfaces are active (WiFi, Ethernet, VPN etc.).
            env = os.environ.copy()
            if self.local_ip and self.local_ip != "0.0.0.0":
                try:
                    if sys.platform != 'win32':
                        iface_name = self._get_iface_name(self.local_ip)
                        if iface_name:
                            subprocess.run(
                                ['route', 'add', '-host', self.ip,
                                 '-interface', iface_name],
                                capture_output=True, timeout=3)
                            env['BIND_ADDR'] = self.local_ip
                            self.log_message.emit(
                                f"Route set: {self.ip} -> {iface_name} ({self.local_ip})")
                    else:
                        # Windows: add a host route via the selected interface's
                        # own IP as gateway — forces traffic to that interface
                        # even when other interfaces (VPN, second NIC etc.) exist.
                        subprocess.run(
                            ['route', 'add', self.ip, 'mask', '255.255.255.255',
                             self.local_ip, 'metric', '1'],
                            capture_output=True, timeout=3,
                            creationflags=subprocess.CREATE_NO_WINDOW)
                        env['BIND_ADDR'] = self.local_ip
                        self.log_message.emit(
                            f"Route set: {self.ip} -> via {self.local_ip}")
                except Exception:
                    pass

            cmd = [self.WINGMON_PATH, '-h', self.ip]   # -h = direct TCP, no WiFi discovery

            # Hide console window on Windows
            popen_kwargs = dict(
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True, bufsize=1, env=env)
            if sys.platform == 'win32':
                popen_kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

            self._wingmon_proc = subprocess.Popen(cmd, **popen_kwargs)

            # Stream wingmon stderr to log in real-time (shows errors on Windows)
            def _stderr_reader():
                try:
                    for line in self._wingmon_proc.stderr:
                        line = line.strip()
                        if line:
                            self.log_message.emit(f"[wingmon] {line}")
                except Exception:
                    pass
            threading.Thread(target=_stderr_reader, daemon=True,
                           name="wingmon-stderr").start()
            # Check for immediate failure (e.g. DiscoveryError)
            import time; time.sleep(0.4)
            if self._wingmon_proc.poll() is not None:
                err = self._wingmon_proc.stderr.read(200).strip()
                self.log_message.emit(
                    f"⚠ wingmon failed: {err}. "
                    f"If WiFi is on, disable it or run: "
                    f"sudo route add -host {self.ip} {self.local_ip or '<your-ethernet-ip>'}")
                self._wingmon_running = False
                self._wingmon_proc = None
                return

            threading.Thread(
                target=self._wingmon_loop, daemon=True, name="WingMon"
            ).start()
            self.log_message.emit("wingmon running -- real-time Wing state tracking active")
            # Keepalive is handled inside wingmon itself (every 4s, independent
            # of stdin). A Python-side timer would only duplicate that traffic
            # and stops working when stdin is EOF, as in a PyInstaller build.
        except Exception as e:
            self.log_message.emit(f"wingmon error: {e}")

    @staticmethod
    def _get_iface_name(local_ip):
        """Find macOS interface name (e.g. 'en5') for a given local IP."""
        try:
            import subprocess
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
            current_iface = None
            for line in result.stdout.splitlines():
                if line and not line.startswith('\t') and not line.startswith(' '):
                    current_iface = line.split(':')[0]
                if local_ip in line and current_iface:
                    return current_iface
        except Exception:
            pass
        return None

    def _parse_wing_val(self, path: str, val_str: str):
        """Parse a Wing parameter value.

        Uses propmap type info so that float params (EQ gain, dyn threshold etc.)
        are always stored as float even when Wing sends whole-number values.
        Without this, set_int(0) for EQ gain would set step 0 (≈ -12 dB) not 0 dB
        -- and the same misclassification can happen for ANY whole-number
        value, not just 0/1 (e.g. a Dual Dynamic EQ threshold or gain that
        happens to land on an integer dB value like -2 or 5).
        """
        val_str = val_str.strip()
        if '.' in val_str:
            try: return float(val_str)
            except: return val_str
        try:
            iv = int(val_str)
            # Check propmap type for EVERY whole-number value, not just 0/1.
            # A value outside [0,1] is NOT unambiguously float -- Wing has
            # genuine integer enum/selector params (band select, detector
            # mode, filter type etc.) whose values can be 2, 3, 4... and
            # those must stay int, or wingmon sends set_float for a
            # parameter Wing expects as set_int.
            if self._is_float_path(path):
                return float(iv)
            return iv   # int param (boolean, enum/selector, etc.)
        except ValueError:
            return val_str


    def _wingmon_loop(self):
        """
        Read wingmon stdout. Handles:
        - DATA /path = value   -> capture response (TCP GET)
        - DATA_END /node       -> marks end of one GET response
        - /path = value        -> live event (auto-update)
        - propN = value        -> dynamic property, resolved via current_ctx
        """
        import re
        # Group 1: section (eq/gate/dyn/flt/fx) -- explicit now, read
        #   directly from Wing's own definitions on the wingmon side, not
        #   guessed client-side. Only present for hash-addressed events.
        # Group 2: index (still used for diagnostics/logging)
        # Group 3: optional 8-hex-digit raw hash -- Wing's own unambiguous
        #   address for this exact parameter.
        # Group 4: value
        prop_re = re.compile(r"^(?:([a-z]+):)?prop(\d+)(?:#([0-9a-fA-F]{8}))? = (.+)$")
        current_ctx = {}
        # Diagnostic: log each distinct model name the first time it's seen
        # (not per-channel -- that would be 48+ messages on every connect),
        # so the exact string Wing uses (e.g. for "Dual Dynamic EQ") is
        # visible even if we've never seen it selected before.
        _seen_model_names = set()
        try:
            for line in self._wingmon_proc.stdout:
                if not getattr(self, '_wingmon_running', False):
                    break
                line = line.strip()
                if not line or '$' in line:
                    continue

                # ── Check for connection confirmation ─────────────────────────
                if line == "Connected!":
                    self.is_connected = True
                    self.connected.emit(True)   # ← enables Disconnect button immediately
                    self.log_message.emit(
                        f"Connected to Wing at {self.ip} -- syncing state…")
                    # No command needed here -- wingmon already began its own
                    # full SYNC (every ch/bus/main/mtx/dca/fx node, including
                    # every section's active model) automatically at startup,
                    # before it even started reading stdin. The DATA lines
                    # from that sync are already on their way; we just wait
                    # for SYNC_COMPLETE below. (A literal "SYNC" stdin command
                    # used to be sent here, but wingmon never recognised it --
                    # only BATCH_SET/SET/KEEPALIVE are handled -- so it was a
                    # harmless no-op, just misleading.)
                    continue

                if line.startswith("SYNC_COMPLETE"):
                    parts = line.split()
                    n = int(parts[1]) if len(parts) > 1 else len(self._wing_state)
                    self.sync_complete.emit(n)
                    continue

                if line.startswith("DATA_END "):
                    node = line[9:].strip()
                    pending = getattr(self, '_capture_nodes', set())
                    pending.discard(node)
                    if self._capturing and not pending:
                        self.capture_finished.emit()
                    continue

                if line.startswith("DATA "):
                    rest = line[5:]

                    # DATA propN -- resolve using explicit section when
                    # given (hash-addressed case), else fall back to trying
                    # every currently-tracked section (pre-hash wingmon).
                    m = prop_re.match(rest.strip())
                    if m:
                        wire_section = m.group(1)
                        idx          = int(m.group(2))
                        hash_hex     = m.group(3)
                        val_str      = m.group(4).strip()
                        if wire_section:
                            # Explicit section from wingmon -- only resolve
                            # if we've already seen this section's /mdl for
                            # the current channel; never guess across other
                            # sections when we know exactly which one this is.
                            sections = ([(wire_section, current_ctx[wire_section])]
                                        if wire_section in current_ctx else [])
                        else:
                            # Old-format event (no section given, pre-hash
                            # wingmon) -- fall back to trying every
                            # currently-tracked section, same as before.
                            sections = list(current_ctx.items())
                        for section, (ch_path, model) in sections:
                            if hash_hex:
                                # Hash-direct: Wing's own unambiguous address
                                # for this exact parameter, regardless of
                                # which model is loaded. Store the RAW string
                                # verbatim -- no int/float reinterpretation --
                                # so recall can echo back exactly what Wing
                                # sent, preserving whichever type Wing itself
                                # chose. No name/model guessing needed at all.
                                path  = f"{ch_path}/{section}/#{hash_hex.lower()}"
                                value = val_str
                                if self._capturing:
                                    with self._capture_buf_lock:
                                        self._capture_buf[path] = value
                                    self._au_baseline[path] = value
                                with self._wing_state_lock:
                                    self._wing_state[path] = value
                            else:
                                # Safety fallback for a wingmon build that
                                # predates hash support -- name-based
                                # resolution, same as before.
                                param = self._resolve_prop(section, model, idx, ch_path, val_str)
                                if param:
                                    if section == 'fx':
                                        path = f"{ch_path}/{param}"
                                    else:
                                        path = f"{ch_path}/{section}/{param}"
                                    try:
                                        value = self._parse_wing_val(path, val_str)
                                    except ValueError:
                                        value = val_str
                                    if self._capturing:
                                        with self._capture_buf_lock:
                                            self._capture_buf[path] = value
                                        self._au_baseline[path] = value
                                    with self._wing_state_lock:
                                        self._wing_state[path] = value
                        continue

                    if " = " not in rest:
                        continue
                    path, val_str = rest.split(" = ", 1)
                    path = path.strip(); val_str = val_str.strip()
                    if not path.startswith('/'):
                        continue

                    # Track EQ/gate/dyn context for subsequent propN in DATA stream
                    parts = path.split('/')
                    if path.endswith('/mdl') and len(parts) >= 5 and parts[3] in ('eq','gate','dyn','flt'):
                        ch_path = '/' + '/'.join(parts[1:3])
                        mdl_name = val_str.strip()
                        current_ctx[parts[3]] = (ch_path, mdl_name)
                        self._dyn_models[(ch_path, parts[3])] = mdl_name
                        if (parts[3], mdl_name) not in _seen_model_names:
                            _seen_model_names.add((parts[3], mdl_name))
                            self.log_message.emit(
                                f"Model seen: {parts[3]} = '{mdl_name}'")
                    elif path.endswith('/mdl') and len(parts) >= 4 and parts[1] == 'fx':
                        current_ctx['fx'] = ('/fx/' + parts[2], val_str.strip())
                    # NOTE: previously there was a fallback here that guessed
                    # a "model" from ANY named path with 5+ segments under
                    # eq/gate/dyn/flt (treating parts[4] as the model name).
                    # That's wrong for non-model-nested params that also live
                    # directly under these sections -- e.g. /ch/1/eq/mix or
                    # /ch/1/dyn/gain are real top-level parameters, not model
                    # names, per Wing's own OSC command list. That fallback
                    # was corrupting current_ctx (log showed "Model seen:
                    # eq = 'mix'"), so it's removed -- context now comes
                    # only from genuine /mdl lines, which Wing reliably
                    # sends for every section during SYNC.

                    try:
                        value = self._parse_wing_val(path, val_str)
                    except ValueError:
                        value = val_str

                    # Convert native wingmon paths to OSC format
                    path = path
                    if self._capturing:
                        with self._capture_buf_lock:
                            self._capture_buf[path] = value
                        self._au_baseline[path] = value
                    with self._wing_state_lock:
                        self._wing_state[path] = value
                    continue

                # ── Resolve anonymous propN ───────────────────────────────────
                m = prop_re.match(line)
                if m:
                    wire_section = m.group(1)
                    idx          = int(m.group(2))
                    hash_hex     = m.group(3)
                    val_str      = m.group(4).strip()
                    if wire_section:
                        sections = ([(wire_section, current_ctx[wire_section])]
                                    if wire_section in current_ctx else [])
                    else:
                        sections = list(current_ctx.items())
                    for section, (ch_path, model) in sections:
                        if hash_hex:
                            path  = f"{ch_path}/{section}/#{hash_hex.lower()}"
                            value = val_str
                            self._emit_wing_event(path, value)
                        else:
                            # Safety fallback for a wingmon build that
                            # predates hash support.
                            param = self._resolve_prop(section, model, idx, ch_path, val_str)
                            if param:
                                if section == 'fx':
                                    path = f"{ch_path}/{param}"
                                else:
                                    path = f"{ch_path}/{section}/{param}"
                                try:
                                    value = self._parse_wing_val(path, val_str)
                                except ValueError:
                                    value = val_str
                                self._emit_wing_event(path, value)
                    continue

                if '=' not in line:
                    continue

                try:
                    path, val_str = line.split('=', 1)
                    path    = path.strip()
                    val_str = val_str.strip()
                    if not path.startswith('/'):
                        continue
                    parts = path.split('/')

                    # Track model for propN context
                    if path.endswith('/mdl'):
                        if len(parts) >= 5 and parts[3] in ('eq','gate','dyn','flt'):
                            ch_path = '/' + '/'.join(parts[1:3])
                            section = parts[3]
                            mdl_name = val_str.strip()
                            current_ctx[section] = (ch_path, mdl_name)
                            self._dyn_models[(ch_path, section)] = mdl_name
                            if (section, mdl_name) not in _seen_model_names:
                                _seen_model_names.add((section, mdl_name))
                                self.log_message.emit(
                                    f"Model seen: {section} = '{mdl_name}'")
                        elif len(parts) >= 4 and parts[1] == 'fx':
                            current_ctx['fx'] = ('/fx/' + parts[2], val_str.strip())
                        self._emit_wing_event(path, val_str.strip())
                        continue

                    # NOTE: same removal as in the DATA-stream path above --
                    # guessing a "model" from any named path under
                    # eq/gate/dyn/flt/fx was corrupting current_ctx for
                    # genuine non-model-nested parameters (e.g. /ch/1/eq/mix,
                    # /ch/1/dyn/gain). Context now comes only from explicit
                    # /mdl lines, handled above.

                    try:
                        if '.' in val_str:
                            value = float(val_str)
                        else:
                            iv = int(val_str)
                            # Check propmap type for EVERY whole-number
                            # value, not just 0/1 -- values outside [0,1]
                            # are NOT unambiguously float (genuine integer
                            # enum/selector params exist too).
                            value = float(iv) if self._is_float_path(path) else iv
                    except ValueError:
                        value = val_str
                    self._emit_wing_event(path, value)
                except Exception as e:
                    import traceback
                    self.log_message.emit(f"Event error: {e} -- {line[:60]}")
        except Exception:
            pass
        finally:
            if self.is_connected:
                self.is_connected = False
                self.connected.emit(False)
                self.log_message.emit("⚠ wingmon disconnected -- Wing connection lost")

    def _emit_wing_event(self, path, value):
        """Store Wing event in _wing_state. Always updated, AU only writes to snapshot."""
        with self._wing_state_lock:
            self._wing_state[path] = value
        self._live_event_count = getattr(self, '_live_event_count', 0) + 1

        # Update title bar every 100 events so user can see events arriving
        if self._live_event_count % 100 == 1:
            self.log_message.emit(
                f"Wing state: {len(self._wing_state)} params, "
                f"{self._live_event_count} live events")

        if not self._auto_update:
            self._au_baseline[path] = value
            return
        baseline_val = self._au_baseline.get(path)
        if baseline_val is not None and self._approx_equal(baseline_val, value):
            return
        self._au_baseline[path] = value
        self._auto_update_count += 1
        self.parameter_received.emit(path, value)

    @staticmethod
    def _approx_equal(a, b):
        """True if two values are close enough to be considered 'unchanged'."""
        try:
            return abs(float(a) - float(b)) < 0.01
        except (TypeError, ValueError):
            return a == b

    def _stop_wingmon(self):
        self._wingmon_running = False
        proc = getattr(self, '_wingmon_proc', None)
        if proc:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except: pass
            try: proc.terminate()
            except: pass
            try: proc.wait(timeout=2)
            except: pass
            self._wingmon_proc = None

    def _on_sync_complete(self, param_count: int):
        """Called on main thread when initial Wing state sync is done."""
        self.log_message.emit(
            f"Wing state synced -- {param_count} parameters ready")

    def _poll_dynamic_models(self):
        """With TCP sync, models come via the initial sync. No-op."""
        pass

    def _report_au_activity(self):
        n = self._auto_update_count
        self._auto_update_count = 0
        if n == 0:
            self.log_message.emit("Auto Update: no events -- move a fader on Wing")
        else:
            self.log_message.emit(f"Auto Update: {n} events in last 3s")

    # ── Subscription ─────────────────────────────────────────────────────────

    def _wingmon_stdin(self, cmd: str):
        """Send a command to wingmon via stdin (SET/GET/KEEPALIVE)."""
        proc = getattr(self, '_wingmon_proc', None)
        if proc and proc.stdin:
            try:
                proc.stdin.write(cmd if cmd.endswith('\n') else cmd + '\n')
                proc.stdin.flush()
            except Exception:
                pass

    def _wingmon_running_ok(self) -> bool:
        proc = getattr(self, '_wingmon_proc', None)
        return bool(proc and proc.poll() is None)

    # ── TCP Capture (replaces OSC polling when wingmon available) ─────────────

    # Top-level nodes to GET -- one request per node, Wing returns all children.
    # This replaces the old POLL_PARAMS list and captures MORE parameters.
    @property
    def CAPTURE_NODES(self):
        """Individual node paths -- libwing requires specific channel IDs, not root nodes."""
        return (
            [f'/ch/{i}'   for i in range(1, 49)] +
            [f'/bus/{i}'  for i in range(1, 17)] +
            [f'/main/{i}' for i in range(1,  5)] +
            [f'/mtx/{i}'  for i in range(1,  9)] +
            [f'/dca/{i}'  for i in range(1, 17)] +
            [f'/fx/{i}'   for i in range(1, 17)]
        )

    def start_capture(self, duration_ms=12000):
        """
        Capture all Wing parameters.
        Uses TCP GET via wingmon (fast, reliable). There is no OSC-polling
        fallback -- wingmon is required for capture.
        """
        if self._wingmon_running_ok():
            self._start_capture_tcp()
        else:
            self.log_message.emit(
                "Capture unavailable -- wingmon is not running. Reconnect to Wing and try again.")

    def _start_capture_tcp(self):
        """Fast capture: send GET for each top-level node via wingmon TCP."""
        self._capture_buf   = {}
        self._capturing     = True
        nodes = self.CAPTURE_NODES
        self._capture_nodes = set(nodes)
        self.log_message.emit(
            f"TCP Capture: requesting {len(nodes)} nodes (ch/bus/main/mtx/dca/fx)…")
        for node in nodes:
            self._wingmon_stdin(f"GET {node}")
        # Safety timeout -- if DATA_END never arrives
        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.timeout.connect(self._finish_capture)
        self._capture_timer.start(8000)

    def _finish_capture(self):
        self._capturing = False
        with self._capture_buf_lock:
            data = dict(self._capture_buf)
            self._capture_buf = {}

        if data:
            self._learned_poll_paths = sorted(data.keys())
            self.log_message.emit(
                f"Capture complete -- {len(data)} parameters stored")
        else:
            self.log_message.emit(
                "Capture: 0 parameters -- Wing did not respond. "
                "Check that Wing is on and IP is correct.")

        self.capture_done.emit(data, getattr(self, "_capture_target_idx", -1))

    # ── Recall ────────────────────────────────────────────────────────────────

    def recall_snapshot(self, snapshot):
        """Recall snapshot to Wing via BATCH_SET. Priority: mutes/faders first,
        then all other in-scope params sorted by dependency order."""
        self._cancel_all_fades()

        # Build param list: (dot_path, value_str, is_priority)
        params = []     # (dot_path_str, is_priority)
        delayed_cmds = []
        faded_paths = set()

        for path, value in snapshot.data.items():
            if not self._path_in_scope(path, snapshot):
                continue
            scope_key = self._path_to_scope_key(path)
            fade_t    = self._get_fade_time(path, snapshot)

            if fade_t > 0.01 and isinstance(value, (int, float)):
                current = self._wing_state.get(path, value)
                current = float(current)
                target  = float(value)
                # Guard against -inf/+inf/NaN as a fade start OR end value.
                # If Wing sends the literal string "-inf" for a fader at
                # silence, Python's float() happily parses that to real
                # negative infinity -- and interpolating to/from infinity
                # produces NaN for the whole fade ("-inf + inf" is
                # undefined), which Wing then can't parse, so the fader
                # doesn't move at all until the final tick sends the real
                # target value directly, looking like a sudden jump. Clamp
                # both ends to Wing's practical floor/ceiling instead so the
                # fade always has real finite endpoints.
                import math
                if not math.isfinite(current):
                    current = -144.0 if current < 0 else 144.0
                if not math.isfinite(target):
                    target = -144.0 if target < 0 else 144.0
                if abs(current - target) > 0.01:
                    self._start_fade(path, current, target, fade_t)
                    faded_paths.add(path)
                    if scope_key == 'fader':
                        mute_path = path.replace('/fdr', '/mute')
                        mute_val  = snapshot.data.get(mute_path)
                        if mute_val is not None and self._path_in_scope(mute_path, snapshot):
                            prev_mute   = int(self._wing_state.get(mute_path, 0))
                            fading_down = target < current - 0.5
                            fading_up   = target > current + 0.5
                            target_mute = int(mute_val)
                            if fading_down and target_mute == 1 and prev_mute == 0:
                                delayed_cmds.append((int(fade_t * 950), mute_path, 1))
                            elif fading_up and target_mute == 0 and prev_mute == 1:
                                faded_paths.add(mute_path)
                                params.insert(0, (mute_path, '0', True))
                continue

            if path not in faded_paths:
                if '/#' in path:
                    # Hash-addressed parameter (model-ambiguous when
                    # captured -- see print_node/wingmon.rs). `value` is
                    # already the raw string exactly as Wing sent it, with
                    # no int/float reinterpretation at any point. Send it
                    # back completely unchanged -- wingmon's encode_param
                    # recognises the embedded hash and addresses the
                    # parameter directly, and the untouched string
                    # preserves whichever type (int/float/string) Wing
                    # itself originally chose for it.
                    with self._wing_state_lock:
                        self._wing_state[path] = value
                    is_pri = scope_key in ('mute', 'fader')
                    params.append((path, str(value), is_pri))
                    continue
                # `value` was already correctly typed (int vs float) at
                # capture time by _parse_wing_val, which checks propmap's
                # float_paths. Re-deriving that here was redundant and could
                # even flip an already-correct float back to int -- just
                # trust the stored type.
                v = value
                if isinstance(v, str):
                    try:    v = int(v)
                    except ValueError:
                        try: v = float(v)
                        except ValueError: pass
                with self._wing_state_lock:
                    self._wing_state[path] = v
                if isinstance(v, float):
                    vstr = f"{v:.6g}"
                    # Ensure decimal so wingmon uses set_float not set_int
                    if '.' not in vstr and 'e' not in vstr:
                        vstr += '.0'
                else:
                    vstr = str(v)
                is_pri = scope_key in ('mute', 'fader')
                params.append((path, vstr, is_pri))

        def _send_batches():
            proc = getattr(self, '_wingmon_proc', None)
            if not proc or not proc.stdin:
                return
            import time

            def order_key(pv):
                """mode/link before dependent params within sends and delay.
                Model select (/mdl) before its own model's parameters within
                eq/gate/dyn/flt -- otherwise a model-specific value (e.g. a
                Dual Dynamic EQ threshold) can be sent while Wing is still on
                the PREVIOUS model and gets silently ignored, then the model
                switch arrives after, too late to matter."""
                path = pv[0]
                if '/send/' in path:
                    if path.endswith('/mode'):  return (0, path)
                    if path.endswith('/plink'): return (1, path)
                    if path.endswith('/pon'):   return (2, path)
                    if path.endswith('/pan'):   return (9, path)
                    return (5, path)
                if 'dlymode' in path or path.endswith('/dly/mode'):
                    return (0, path)
                if 'dlyon' in path or path.endswith('/dly/on'):
                    return (9, path)
                if path.endswith('/mdl'):
                    parts = path.split('/')
                    if len(parts) >= 4 and parts[3] in ('eq', 'gate', 'dyn', 'flt'):
                        return (0, path)
                return (5, path)

            def _is_model_select(path):
                if not path.endswith('/mdl'):
                    return False
                parts = path.split('/')
                return len(parts) >= 4 and parts[3] in ('eq', 'gate', 'dyn', 'flt')

            # Mutes/faders first, then rest sorted by dependency order.
            # Model-select (/mdl) paths are pulled into their own batch and
            # sent with a real pause before anything else -- correct SEND
            # ORDER alone isn't enough: switching an eq/dyn model is a real
            # DSP-side operation on Wing that takes actual time, and with
            # everything arriving in the same sub-millisecond burst, Wing
            # can still be mid-switch when the model's own parameter values
            # (e.g. Dual Dynamic EQ thresholds) arrive, and silently drops
            # them. This was tested and confirmed: order fix alone was not
            # sufficient, values still didn't land until this pause was added.
            model_selects = sorted([(p,v) for p,v,pri in params if _is_model_select(p)], key=order_key)
            priority  = sorted([(p,v) for p,v,pri in params if pri and not _is_model_select(p)],     key=order_key)
            secondary = sorted([(p,v) for p,v,pri in params if not pri and not _is_model_select(p)], key=order_key)

            def send_batch(param_list, chunk_size=500, delay=0.002):
                for i in range(0, len(param_list), chunk_size):
                    chunk = param_list[i:i+chunk_size]
                    line = ','.join(f"{p}={v}" for p,v in chunk)
                    proc.stdin.write(f"BATCH_SET {line}\n")
                    proc.stdin.flush()
                    if i + chunk_size < len(param_list):
                        time.sleep(delay)

            MODEL_SWITCH_SETTLE_SECS = 0.08

            try:
                if model_selects:
                    send_batch(model_selects)
                    time.sleep(MODEL_SWITCH_SETTLE_SECS)
                send_batch(priority)
                send_batch(secondary)
                for ms, path, val in delayed_cmds:
                    time.sleep(ms / 1000)
                    self._wingmon_stdin(f"SET {path} {val}")
            except Exception:
                import traceback, sys
                traceback.print_exc(file=sys.stderr)

        import threading
        threading.Thread(target=_send_batches, daemon=True, name="RecallBatch").start()

    def _path_in_scope(self, path, snapshot):
        ch_key    = self._path_to_ch_key(path)
        scope_key = self._path_to_scope_key(path)
        if not ch_key or not scope_key:
            return False
        # FX slots use snapshot.fx_scope keyed by 'fx_01' etc.
        if ch_key.startswith('fx_'):
            return snapshot.fx_scope.get(ch_key, True)
        cs = snapshot.get_ch_scope(ch_key)
        if scope_key == 'sends':
            bus = self._path_to_send_dest_key(path)
            if bus is not None and bus in cs.send_overrides:
                # Explicit per-bus override exists (set via the expanded
                # Sends columns) -- use it instead of the aggregate toggle.
                return cs.send_overrides[bus]
        return cs.overrides.get(scope_key, snapshot.scope.get(scope_key, True))

    def _path_to_send_dest_key(self, path):
        """Extract the send destination key from a /ch/N/send/D/... or
        /bus/N/send/D/... path. D is the raw string Wing uses -- a plain
        number for a bus destination ("1".."16"), or "MX1".."MX8" for a
        matrix destination (confirmed from a live event: a channel send to
        matrix arrives as /ch/N/send/MX1/lvl, not a numeric continuation).
        Returns None if this isn't a send path at all."""
        p = path.split('/')
        if len(p) >= 5 and p[3] == 'send':
            return p[4]
        return None

    def _path_to_ch_key(self, path):
        p = path.split('/')
        if len(p) < 3: return None
        kind, num_s = p[1], p[2]
        try:    num = int(num_s)
        except: return None
        if kind == 'ch':   return f"input_{num:02d}"
        if kind == 'bus':  return f"bus_{num:02d}"
        if kind == 'fx':   return f"fx_{num:02d}"
        if kind == 'mtx':  return f"matrix_{num:02d}"
        if kind == 'main': return f"main_{num}"
        if kind == 'dca':  return f"dca_{num:02d}"
        return None

    def _path_to_scope_key(self, path):
        p = path.split('/', 3)
        if len(p) < 4: return None
        sub = '/' + p[3]

        # FX racks (/fx/1/mdl etc.) -- dedicated fx_rack scope
        if p[1] == 'fx':
            return 'fx_rack'

        if sub == '/fdr':                                    return 'fader'
        if sub == '/mute':                                   return 'mute'
        if sub.startswith('/pan') or sub.startswith('/wid'):  return 'pan'
        if sub.startswith('/flt'):                           return 'filter'
        if sub.startswith('/dly'):                           return 'delay'
        if sub.startswith('/gate'):                          return 'gate'
        if sub.startswith('/dyn'):                           return 'dynamics'
        if sub.startswith('/preins'):                        return 'pre_insert'
        if sub.startswith('/postins'):                       return 'post_insert'
        if sub.startswith('/eq') or sub.startswith('/peq'): return 'eq'
        if sub.startswith('/main'):                          return 'mains'
        if sub.startswith('/send'):                          return 'sends'
        if sub.startswith('/in/conn'):                       return 'conn'
        if sub.startswith('/in/set/dly'):                    return 'delay'
        if sub in ('/trim', '/pol') or sub.startswith('/in/set'): return 'in'
        if sub in ('/name', '/icon', '/col', '/led'):   return 'custom'
        if sub == '/tags':                                   return 'tags'
        if sub.startswith('/dca') or sub.startswith('/mgrp'): return 'tags'
        if sub.startswith('/wid') or sub in ('/proc', '/ptap', '/solosafe',
               '/mon', '/clink', '/tapwid', '/busmono', '/cgrp'): return 'rack_config'
        return None

    def _get_fade_time(self, path, snapshot):
        ch_key    = self._path_to_ch_key(path)
        scope_key = self._path_to_scope_key(path)
        if not ch_key or scope_key not in ('fader', 'sends'): return 0.0
        cs = snapshot.get_ch_scope(ch_key)
        gk = self._ch_key_to_group(ch_key)
        if scope_key == 'fader':
            return cs.fader_fade if cs.fader_fade > 0 else snapshot.get_group_fade(gk,'fader')
        return cs.sends_fade if cs.sends_fade > 0 else snapshot.get_group_fade(gk,'sends')

    def _ch_key_to_group(self, ch_key):
        if ch_key.startswith('input'):  return 'inputs'
        if ch_key.startswith('bus'):    return 'buses'
        if ch_key.startswith('matrix'): return 'matrix'
        if ch_key.startswith('main'):   return 'mains'
        return 'dcas'

    # ── Fading ────────────────────────────────────────────────────────────────

    def _start_fade(self, path, start_db, end_db, fade_secs, fps=40):
        """Queue a fade -- interpolates linearly in dB space for smooth visual movement."""
        steps = max(2, int(fade_secs * fps))
        self._fade_jobs.append([path, float(start_db), float(end_db), steps, 0])
        # Suppress Auto Update writes for this path until we actually see the
        # fade's real target value come back from Wing -- not just "some
        # amount of time has passed". We know exactly what value the fade is
        # heading to (end_db), so instead of guessing how long Wing's echo
        # round-trip takes, we just wait to see that exact value arrive.
        # A generous safety deadline is kept as a fallback only, in case the
        # target is never seen (fade interrupted, connection hiccup, Wing
        # quantizes to a slightly different value, etc.) so a path can never
        # get stuck suppressed forever.
        import time as _time
        SAFETY_MARGIN = 1.0
        self._fading_paths[path] = {
            "target":   float(end_db),
            "deadline": _time.time() + fade_secs + SAFETY_MARGIN,
        }
        if not self._unified_timer.isActive():
            self._unified_timer.start(int(1000 / fps))

    # Fade curve tuning: the -30..0dB range gets more of the available
    # steps than the same dB distance below -30, since that's where level
    # changes are actually audible/visible -- the -144..-30 range is mostly
    # silence anyway, so it doesn't need fine resolution.
    _FADE_BREAK_DB = -30.0
    _FADE_BOOST    = 3.0   # -30..0 gets ~3x the step density of below -30

    @classmethod
    def _db_to_weighted(cls, db):
        if db <= cls._FADE_BREAK_DB:
            return db
        return cls._FADE_BREAK_DB + (db - cls._FADE_BREAK_DB) * cls._FADE_BOOST

    @classmethod
    def _weighted_to_db(cls, w):
        if w <= cls._FADE_BREAK_DB:
            return w
        return cls._FADE_BREAK_DB + (w - cls._FADE_BREAK_DB) / cls._FADE_BOOST

    def _unified_step(self):
        """Single timer callback -- steps ALL active fades in the same tick.

        Interpolates linearly in a WEIGHTED dB space, not raw dB: ticks are
        spent proportionally more on the -30..0dB range (see _FADE_BOOST)
        than on the -144..-30 range, since the latter is mostly inaudible
        anyway. This gives smoother, finer motion where it's actually
        noticed, without needing more total steps.

        (Linear-in-gain was tried and rejected: for a fade starting at -inf,
        gain is ~0 at the start, so even a small linear step in gain space
        corresponds to a huge dB swing -- e.g. the very first tick jumps
        straight to around -30dB, no matter how many steps are used. Plain
        linear-in-dB has no such discontinuity, so the weighting above is
        applied on top of that instead of switching to gain space.)

        All of this tick's values are sent as ONE BATCH_SET instead of one
        individual SET per fading parameter. With many parameters fading at
        once (e.g. every fader + every send set to fade together), sending
        one SET per parameter per tick (25ms at the default 40fps) means
        hundreds of individual writes per second for the whole fade -- easily overwhelming Wing's
        receive pipeline and causing dropped/reordered updates (seen as
        values jumping around or not landing on the right value). A single
        combined BATCH_SET per tick cuts that by roughly the number of
        simultaneously-fading parameters.
        """
        done = []
        batch = []   # (path, value) pairs to send this tick
        for job in self._fade_jobs:
            path, start_db, end_db, steps, n = job
            t = n / (steps - 1) if steps > 1 else 1.0
            if t >= 1.0:
                db_now = end_db   # exact target, no round-trip through weighting
            else:
                w_start = self._db_to_weighted(start_db)
                w_end   = self._db_to_weighted(end_db)
                w_now   = w_start + (w_end - w_start) * t
                db_now  = self._weighted_to_db(w_now)
            batch.append((path, db_now))
            job[4] = n + 1
            if n + 1 >= steps:
                done.append(job)

        if batch:
            self._send_params_batch(batch)

        for job in done:
            self._fade_jobs.remove(job)

        if not self._fade_jobs:
            self._unified_timer.stop()

    def _send_params_batch(self, pairs):
        """Send multiple (path, value) pairs to Wing in a single BATCH_SET,
        instead of one SET command per pair. Used by the fade engine so a
        tick with many simultaneously-fading parameters costs one write
        instead of many. Also updates _wing_state for each pair."""
        parts = []
        for path, value in pairs:
            if isinstance(value, str):
                try:    value = int(value)
                except ValueError:
                    try: value = float(value)
                    except ValueError: pass
            if isinstance(value, float) and value == int(value) and 0 <= value <= 1 and not self._is_float_path(path):
                value = int(value)
            with self._wing_state_lock:
                self._wing_state[path] = value
            if isinstance(value, float):
                vstr = f"{value:.6g}"
                if '.' not in vstr and 'e' not in vstr:
                    vstr += '.0'
            else:
                vstr = str(value)
            parts.append(f"{path}={vstr}")
        if parts:
            self._wingmon_stdin(f"BATCH_SET {','.join(parts)}")

    def _cancel_all_fades(self):
        for job in self._fade_jobs:
            self._fading_paths.pop(job[0], None)
        self._unified_timer.stop()
        self._fade_jobs.clear()








class SimpleToggleRow(QWidget):
    """Single labelled row with a green/hollow circle toggle button."""
    toggled = pyqtSignal(bool)

    def __init__(self, label, value=True):
        super().__init__()
        self.value = value
        l = QHBoxLayout(self)
        l.setContentsMargins(12, 4, 12, 4)
        l.setSpacing(14)
        self.circle = QPushButton()
        self.circle.setFixedSize(22, 22)
        self.circle.setCheckable(True)
        self.circle.setChecked(value)
        self.circle.clicked.connect(self._on_click)
        self._style_circle()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{C['text']};font-size:13px;")
        l.addWidget(self.circle)
        l.addWidget(lbl)
        l.addStretch()

    def _style_circle(self):
        if self.circle.isChecked():
            self.circle.setStyleSheet(
                f"background:{C['green']};border:1px solid {C['green_border']};"
                f"border-radius:11px;")
        else:
            self.circle.setStyleSheet(
                f"background:transparent;border:2px solid {C['border2']};"
                f"border-radius:11px;")

    def _on_click(self, checked):
        self.value = checked
        self._style_circle()
        self.toggled.emit(checked)

    def set_value(self, value):
        self.circle.blockSignals(True)
        self.circle.setChecked(value)
        self.value = value
        self._style_circle()
        self.circle.blockSignals(False)


class SimpleTogglePanel(QWidget):
    """
    A scrollable list of SimpleToggleRows for FX Slots or Console Config.
    Each item has a single green/hollow circle -- no per-parameter columns.
    """
    changed = pyqtSignal()

    def __init__(self, title, items, all_on_btn=True):
        """
        items: list of (key, label)
        """
        super().__init__()
        self._items = items
        self._scope_dict = None   # reference to snapshot.fx_scope or .cfg_scope
        self._rows = {}
        self._build(title, all_on_btn)

    def _build(self, title, show_bulk):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if show_bulk:
            bar = QWidget()
            bar.setStyleSheet(
                f"background:{C['bg3']};border-bottom:1px solid {C['border']};")
            bar.setFixedHeight(34)
            bl = QHBoxLayout(bar)
            bl.setContentsMargins(10, 0, 10, 0); bl.setSpacing(8)
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(
                f"color:{C['text3']};font-size:10px;letter-spacing:0.08em;")
            bl.addWidget(lbl); bl.addStretch()
            for text, val in [("All On", True), ("All Off", False)]:
                btn = QPushButton(text); btn.setFixedHeight(22)
                btn.clicked.connect(lambda _, v=val: self._set_all(v))
                bl.addWidget(btn)
            layout.addWidget(bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 4, 0, 4)
        cl.setSpacing(0)

        for key, label in self._items:
            row = SimpleToggleRow(label, value=True)
            row.toggled.connect(lambda v, k=key: self._on_toggle(k, v))
            self._rows[key] = row
            # Alternating row backgrounds
            idx = list(self._rows.keys()).index(key)
            bg = C['bg'] if idx % 2 == 0 else C['bg2']
            row.setStyleSheet(f"background:{bg};")
            cl.addWidget(row)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _on_toggle(self, key, value):
        if self._scope_dict is not None:
            self._scope_dict[key] = value
        self.changed.emit()

    def _set_all(self, value):
        for key, row in self._rows.items():
            row.set_value(value)
            if self._scope_dict is not None:
                self._scope_dict[key] = value
        self.changed.emit()

    def load(self, scope_dict):
        self._scope_dict = scope_dict
        for key, row in self._rows.items():
            row.set_value(scope_dict.get(key, True))


class OscSender:
    """
    Sends OSC messages from a snapshot to configured endpoints.
    Handles arg parsing (int, float, str) and endpoint routing.
    """

    @staticmethod
    def parse_args(args_str: str) -> list:
        """Parse 'addr arg1 arg2 ...' into typed Python values.
        Quoted strings are supported: "hello world" stays as one token.
        """
        if not args_str or not args_str.strip():
            return []
        import shlex
        try:
            tokens = shlex.split(args_str)
        except ValueError:
            tokens = args_str.strip().split()
        result = []
        for t in tokens:
            try:   result.append(int(t));   continue
            except ValueError: pass
            try:   result.append(float(t)); continue
            except ValueError: pass
            result.append(t)
        return result

    @staticmethod
    def send_messages(messages: list, osc_outputs: list) -> list:
        """
        Send a list of snapshot OSC messages.
        Each message dict: {"address": str, "args": str, "target": "All"|endpoint_name}

        Returns list of (ok: bool, endpoint_name: str, detail: str).
        """
        try:
            from pythonosc.udp_client import SimpleUDPClient
            from pythonosc.osc_message_builder import OscMessageBuilder
        except ImportError:
            return [(False, "--", "python-osc not installed  (pip3 install python-osc)")]

        enabled  = {ep.name: ep for ep in osc_outputs if ep.enabled}
        all_eps  = list(enabled.values())
        results  = []

        for msg in messages:
            address  = (msg.get("address") or "").strip()
            args_str = (msg.get("args")    or "").strip()
            target   = (msg.get("target")  or "All")
            if not address:
                continue
            args    = OscSender.parse_args(args_str)
            targets = all_eps if target == "All" else ([enabled[target]] if target in enabled else [])

            for ep in targets:
                try:
                    if getattr(ep, 'bind_ip', '') and ep.bind_ip.strip():
                        # Send via specific interface using raw socket
                        import socket as _socket
                        builder = OscMessageBuilder(address=address)
                        for a in args: builder.add_arg(a)
                        msg_bytes = builder.build().dgram
                        sock = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
                        sock.bind((ep.bind_ip.strip(), 0))
                        sock.sendto(msg_bytes, (ep.ip, ep.port))
                        sock.close()
                        results.append((True, ep.name, f"{address} → {ep.ip}:{ep.port} via {ep.bind_ip}"))
                        continue
                    client = SimpleUDPClient(ep.ip, ep.port)
                    if len(args) == 0:
                        client.send_message(address, None)
                    elif len(args) == 1:
                        client.send_message(address, args[0])
                    else:
                        client.send_message(address, args)
                    results.append((True,  ep.name, f"{address}  {args_str}".rstrip()))
                except Exception as e:
                    results.append((False, ep.name, f"{address} -> {e}"))

        return results


class SnapshotOscTab(QWidget):
    """
    Per-snapshot OSC messages shown as a tab in the Recall Scope widget.
    Sent to selected endpoint(s) on recall.
    """
    def __init__(self, show):
        super().__init__()
        self.show     = show      # ShowFile reference -- for endpoint list
        self.snapshot = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        hint = QLabel(
            "OSC messages sent on recall of this cue.\n"
            "Endpoint: choose 'All' to send to every enabled endpoint, "
            "or type an endpoint name to target it specifically.")
        hint.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # 3 columns: address, args, target endpoint
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["OSC Address", "Arguments", "Endpoint"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(2, 130)
        self.table.horizontalHeader().setDefaultSectionSize(110)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_context_menu)
        layout.addWidget(self.table)

        self.add_btn = QPushButton("+ Add Message")
        self.add_btn.setObjectName("green_btn")
        self.add_btn.clicked.connect(self._add)
        self.del_btn = QPushButton("Remove Selected")
        self.del_btn.setObjectName("danger_btn")
        self.del_btn.clicked.connect(self._remove)
        self.test_btn = QPushButton("▶  Send Test")
        self.test_btn.setToolTip(
            "Send all OSC messages for this cue now -- without triggering a full recall.")
        self.test_btn.clicked.connect(self._test)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.test_btn)
        layout.addLayout(btn_row)

        # Result log shown after Test
        self.result_log = QLabel("")
        self.result_log.setStyleSheet(
            f"color:{C['text3']};font-size:11px;font-family:'Courier New',monospace;"
            f"background:{C['bg']};border:1px solid {C['border']};"
            f"border-radius:4px;padding:6px;")
        self.result_log.setWordWrap(True)
        self.result_log.setVisible(False)
        layout.addWidget(self.result_log)

        self._set_enabled(False)

    def _endpoint_names(self):
        """Return ['All'] + names of all defined endpoints."""
        names = ["All"]
        for ep in self.show.osc_outputs:
            if ep.name and ep.name not in names:
                names.append(ep.name)
        return names

    def refresh_endpoints(self):
        """Update endpoint dropdowns in all rows — called when endpoints change."""
        ep_names = self._endpoint_names()
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 2)
            if cb and isinstance(cb, QComboBox):
                current = cb.currentText()
                cb.blockSignals(True)
                cb.clear()
                cb.addItems(ep_names)
                idx = cb.findText(current)
                cb.setCurrentIndex(idx if idx >= 0 else 0)
                cb.blockSignals(False)

    def tcp_set_running(self, running: bool, client_addr: str = ""):
        if not hasattr(self, 'tcp_status'): return
        if running:
            self.tcp_toggle_btn.setText("On")
            self.tcp_toggle_btn.setStyleSheet(
                f"background:#1a6b3a;color:#7fff9a;border:1px solid #2a9b5a;"
                f"border-radius:4px;padding:3px 8px;")
            if client_addr:
                self.tcp_status.setText(f"● Connected: {client_addr}")
                self.tcp_status.setStyleSheet("color:#7fff9a;font-size:11px;")
            else:
                self.tcp_status.setText(f"● Listening on port {self.tcp_port.value()}")
                self.tcp_status.setStyleSheet("color:#aaffaa;font-size:11px;")
        else:
            self.tcp_toggle_btn.setText("Off")
            self.tcp_toggle_btn.setStyleSheet(
                f"background:#1e2a2e;color:#7a9aaa;border:1px solid #2a4a5a;"
                f"border-radius:4px;padding:3px 8px;")
            self.tcp_status.setText("● Stopped")
            self.tcp_status.setStyleSheet("color:#7a9aaa;font-size:11px;")

    def _connect_table(self):
        try: self.table.itemChanged.disconnect()
        except Exception: pass
        self.table.itemChanged.connect(self._on_changed)

    def _set_enabled(self, enabled):
        self.table.setEnabled(enabled)
        self.add_btn.setEnabled(enabled)
        self.del_btn.setEnabled(enabled)
        self.test_btn.setEnabled(enabled)

    def _populate(self, snap):
        """Fill table -- disconnect signal first, reconnect after."""
        try: self.table.itemChanged.disconnect()
        except Exception: pass

        self.table.setRowCount(0)
        if not snap:
            self._connect_table()
            return

        ep_names = self._endpoint_names()
        for msg in snap.osc_messages:
            try:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(msg.get("address", ""))))
                self.table.setItem(r, 1, QTableWidgetItem(str(msg.get("args", ""))))

                # Target endpoint -- combobox in the cell
                cb = QComboBox()
                cb.addItems(ep_names)
                target = msg.get("target", "All")
                idx = cb.findText(target)
                cb.setCurrentIndex(idx if idx >= 0 else 0)
                cb.currentTextChanged.connect(
                    lambda text, row=r: self._on_target_changed(row, text))
                cb.setStyleSheet(
                    f"background:{C['bg3']};color:{C['text']};"
                    f"border:1px solid {C['border']};border-radius:3px;"
                    f"padding:2px 4px;font-size:12px;")
                self.table.setCellWidget(r, 2, cb)
            except Exception:
                import traceback; traceback.print_exc()

        self._connect_table()

    def load(self, snap):
        try:
            self.snapshot = snap
            self._populate(snap)
            self._set_enabled(snap is not None)
        except Exception:
            import traceback; traceback.print_exc()

    def _on_changed(self, item):
        try:
            if not self.snapshot or item is None:
                return
            r = item.row()
            if r < 0 or r >= len(self.snapshot.osc_messages):
                return
            msg = self.snapshot.osc_messages[r]
            col = item.column()
            if   col == 0: msg["address"] = item.text()
            elif col == 1: msg["args"]    = item.text()
            # col 2 is handled by _on_target_changed
        except Exception:
            import traceback; traceback.print_exc()

    def _on_target_changed(self, row, text):
        try:
            if not self.snapshot or row >= len(self.snapshot.osc_messages):
                return
            self.snapshot.osc_messages[row]["target"] = text
        except Exception:
            import traceback; traceback.print_exc()

    def _test(self):
        """Send all messages for this cue without triggering recall."""
        try:
            if not self.snapshot:
                return
            if not self.snapshot.osc_messages:
                self.result_log.setText("No messages defined.")
                self.result_log.setVisible(True)
                return

            results = OscSender.send_messages(
                self.snapshot.osc_messages, self.show.osc_outputs)

            if not results:
                self.result_log.setText("Nothing sent -- no enabled endpoints.")
                self.result_log.setVisible(True)
                return

            lines = []
            for ok, ep_name, detail in results:
                lines.append(f"{'✓' if ok else '✗'}  [{ep_name}]  {detail}")
            all_ok = all(r[0] for r in results)
            self.result_log.setText("\n".join(lines))
            self.result_log.setStyleSheet(
                f"color:{C['green'] if all_ok else C['amber']};"
                f"font-size:11px;font-family:'Courier New',monospace;"
                f"background:{C['bg']};border:1px solid {C['border']};"
                f"border-radius:4px;padding:6px;")
            self.result_log.setVisible(True)
            QTimer.singleShot(8000, lambda: self.result_log.setVisible(False))
        except Exception:
            import traceback; traceback.print_exc()

    def _table_context_menu(self, pos):
        """Right-click context menu on a table row -- send just that message."""
        try:
            row = self.table.rowAt(pos.y())
            if row < 0 or not self.snapshot:
                return
            if row >= len(self.snapshot.osc_messages):
                return
            menu = QMenu(self)
            msg = self.snapshot.osc_messages[row]
            addr = msg.get("address", "") or "(no address)"
            action = menu.addAction(f"▶  Send test: {addr}")
            action.triggered.connect(lambda: self._test_row(row))
            menu.exec(self.table.viewport().mapToGlobal(pos))
        except Exception:
            import traceback; traceback.print_exc()

    def _test_row(self, row):
        """Send a single OSC message (by row index) as a test."""
        try:
            if not self.snapshot or row >= len(self.snapshot.osc_messages):
                return
            msg = self.snapshot.osc_messages[row]
            results = OscSender.send_messages([msg], self.show.osc_outputs)

            if not results:
                self.result_log.setText("Nothing sent -- no enabled endpoints.")
                self.result_log.setVisible(True)
                return

            out = []
            for ok, ep_name, detail in results:
                out.append(f"{chr(10003) if ok else chr(10007)}  [{ep_name}]  {detail}")
            all_ok = all(r[0] for r in results)
            self.result_log.setText("\n".join(out))
            self.result_log.setStyleSheet(
                f"color:{C['green'] if all_ok else C['amber']};"
                f"font-size:11px;font-family:'Courier New',monospace;"
                f"background:{C['bg']};border:1px solid {C['border']};"
                f"border-radius:4px;padding:6px;")
            self.result_log.setVisible(True)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(8000, lambda: self.result_log.setVisible(False))
        except Exception:
            import traceback; traceback.print_exc()

    def _add(self):
        try:
            if not self.snapshot:
                return
            self.snapshot.osc_messages.append(
                {"address": "/address", "args": "", "target": "All"})
            self._populate(self.snapshot)
        except Exception:
            import traceback; traceback.print_exc()

    def _remove(self):
        try:
            if not self.snapshot:
                return
            r = self.table.currentRow()
            if 0 <= r < len(self.snapshot.osc_messages):
                self.snapshot.osc_messages.pop(r)
                self._populate(self.snapshot)
        except Exception:
            import traceback; traceback.print_exc()


class DefaultScopeDialog(QDialog):
    """
    Edit the global default recall scope -- uses the full RecallScopeWidget
    so group-level differences (e.g. Sends OFF for buses only) can be set.
    On save: extracts group-level effective values and stores them in DEFAULT_*.
    Right-click Default button in scope toolbar to open this dialog.
    """
    def __init__(self, show, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Default Recall Scope  (right-click Default to open)")
        self.resize(1100, 700)
        if parent:
            self.setStyleSheet(parent.styleSheet())

        # Temp snapshot pre-loaded with current defaults (via Snapshot.__init__)
        self._temp = Snapshot("_defaults_")
        # Snapshot.__init__ already copies DEFAULT_SCOPE/CHANNEL_SCOPES/FX/CFG/FADES

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        lbl = QLabel(
            "Set the default scope for new snapshots -- including per-group differences.  "
            "Changes are applied only when you explicitly press Default on a snapshot.  "
            "OSC messages are not included in defaults.")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # Full scope widget -- toolbar hidden, OSC tab removed
        self.scope_widget = RecallScopeWidget(show)
        self.scope_widget.set_toolbar_visible(False)
        self.scope_widget.load_snapshot(self._temp)
        osc_idx = self.scope_widget.tabs.count() - 1
        self.scope_widget.tabs.removeTab(osc_idx)
        layout.addWidget(self.scope_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Save as New Default")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self):
        """1-to-1 copy of temp snapshot state -> DEFAULT_* dicts."""
        try:
            DEFAULT_SCOPE.clear()
            DEFAULT_SCOPE.update(self._temp.scope)

            DEFAULT_CHANNEL_SCOPES.clear()
            # Only save channel scopes with actual overrides, per-send
            # customisation, or fade times
            non_empty = {k: v for k, v in self._temp.channel_scopes.items()
                         if v.overrides or v.send_overrides or v.fader_fade > 0 or v.sends_fade > 0}
            DEFAULT_CHANNEL_SCOPES.update(_copy_channel_scopes(non_empty))

            DEFAULT_FX_SCOPE.clear()
            DEFAULT_FX_SCOPE.update(self._temp.fx_scope)
            DEFAULT_CFG_SCOPE.clear()
            DEFAULT_CFG_SCOPE.update(self._temp.cfg_scope)

            for gk in list(DEFAULT_GROUP_FADES):
                fades = self._temp.group_fades.get(gk, {"fader": 0.0, "sends": 0.0})
                DEFAULT_GROUP_FADES[gk] = dict(fades)

        except Exception:
            import traceback
            traceback.print_exc()

        # Defer done(1) via QTimer to avoid deadlock on macOS + PyQt6 + Python 3.14
        QTimer.singleShot(0, lambda: self.done(1))


class CopyScopeDialog(QDialog):
    """Copy the recall scope from one snapshot to one or more others."""
    def __init__(self, source_snap, all_snapshots, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Copy Scope -- from '{source_snap.name}'")
        self.resize(380, 480)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        self.source = source_snap
        self.all_snaps = [s for s in all_snapshots if s is not source_snap]
        self._checks = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        hdr = QLabel(f"Copy scope from  <b>{self.source.name}</b>  to:")
        hdr.setStyleSheet(f"color:{C['text']};font-size:13px;")
        layout.addWidget(hdr)

        snaps_grp = QGroupBox("COPY TO")
        snaps_l = QVBoxLayout(snaps_grp)

        sel_row = QHBoxLayout()
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setFixedHeight(24)
        sel_all_btn.clicked.connect(lambda: [c.setChecked(True)  for c,_ in self._checks])
        sel_none_btn = QPushButton("Select None")
        sel_none_btn.setFixedHeight(24)
        sel_none_btn.clicked.connect(lambda: [c.setChecked(False) for c,_ in self._checks])
        sel_row.addWidget(sel_all_btn); sel_row.addWidget(sel_none_btn); sel_row.addStretch()
        snaps_l.addLayout(sel_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        cl = QVBoxLayout(content); cl.setSpacing(2)
        for snap in self.all_snaps:
            cb = QCheckBox(f"  {snap.number:03d}  {snap.name}")
            cb.setChecked(False)
            self._checks.append((cb, snap))
            cl.addWidget(cb)
        cl.addStretch()
        content.setLayout(cl)
        scroll.setWidget(content)
        snaps_l.addWidget(scroll)
        layout.addWidget(snaps_grp)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Copy Scope")
        buttons.accepted.connect(self._do_copy)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _do_copy(self):
        import copy
        for cb, snap in self._checks:
            if not cb.isChecked():
                continue
            snap.scope          = dict(self.source.scope)
            snap.channel_scopes = copy.deepcopy(self.source.channel_scopes)
            snap.fx_scope       = dict(self.source.fx_scope)
            snap.cfg_scope      = dict(self.source.cfg_scope)
            snap.group_fades    = copy.deepcopy(self.source.group_fades)
        self.accept()



class DoubleClickButton(QPushButton):
    """
    QPushButton with right-click support.
    Left-click  -> normal clicked signal (resets to default).
    Right-click: double_clicked signal after 100 ms delay --  (opens default settings).

    Uses mousePressEvent + mouseReleaseEvent instead of contextMenuEvent to avoid
    a macOS bug where intercepting contextMenuEvent without showing a menu leaves
    the window in a state where it stops receiving mouse events.
    """
    double_clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()   # intercept -- don't forward to Qt
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()   # intercept
            # 100ms delay: lets macOS fully process the right-click sequence
            # before we open a modal dialog
            QTimer.singleShot(100, self.double_clicked.emit)
        else:
            super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event):
        event.accept()   # suppress system context menu silently


# ─── Recall Scope Widget ──────────────────────────────────────────────────────

LABEL_COL   = 0
EXPAND_COL  = 1
FADE_F_COL  = 2    # Fader xFade -- first after expand button
FADE_S_COL  = 3    # Sends xFade
FIRST_SCOPE = 4    # Scope circle columns start here
TOTAL_COLS  = FIRST_SCOPE + len(WING_SCOPE_COLS)

# Per-bus send columns -- appended AFTER all existing scope columns so none
# of their fixed indices change. Hidden by default; shown (and visually
# moved next to the aggregate Sends column via header().moveSection()) only
# when the user expands Sends. Only meaningful for input channels (channel
# sends target buses 1-16) -- other row kinds show " --" same as DCAs do
# for the aggregate Sends column today.
# Per-bus/matrix send columns -- appended AFTER all existing scope columns
# so none of their fixed indices change. Hidden by default; shown (and
# visually moved next to the aggregate Sends column via header().moveSection())
# only when the user expands Sends. Meaningful for input channels AND buses
# -- both send to buses (channel->bus, bus->bus), and both send directly to
# matrix outputs too (confirmed live: channel sends to matrix arrive as
# /ch/N/send/MX1/lvl, not routed via a bus). Other row kinds show " --" same
# as DCAs do for the aggregate Sends column today.
SEND_BUS_COUNT  = 16
SEND_MTX_COUNT  = 8
# Destination key for each column, in the exact string form Wing itself
# uses on the wire -- "1".."16" for bus sends, "MX1".."MX8" for matrix sends.
SEND_DEST_KEYS  = [str(b) for b in range(1, SEND_BUS_COUNT + 1)] \
                 + [f"MX{m}" for m in range(1, SEND_MTX_COUNT + 1)]
SENDS_COL       = FIRST_SCOPE + next(
    i for i, (sk, _, _) in enumerate(WING_SCOPE_COLS) if sk == 'sends')
SEND_FIRST_COL  = TOTAL_COLS
SEND_TOTAL_COLS = TOTAL_COLS + len(SEND_DEST_KEYS)

# Circle state stored in UserRole on scope columns (cols FIRST_SCOPE+).
# Column 0 also uses UserRole for item metadata -- no conflict since different columns.
CIRCLE_ROLE = Qt.ItemDataRole.UserRole
CIRCLE_OFF  = 0
CIRCLE_PART = 1
CIRCLE_ON   = 2


class ScopeCircleDelegate(QStyledItemDelegate):
    """
    Paints dLive-style circles by reading CIRCLE_ROLE (Qt.ItemDataRole.UserRole)
    from each scope column. No CheckStateRole, no tristate flags.
    """
    R = 7

    def paint(self, painter, option, index):
        col = index.column()
        # Label, expand, and fade columns use default delegate rendering
        if col < FIRST_SCOPE:
            super().paint(painter, option, index)
            return

        # Read circle state from UserRole on this column
        raw = index.data(CIRCLE_ROLE)
        if raw is None:
            # Data not set yet -- draw dark background only
            painter.fillRect(option.rect, QColor(C['bg']))
            return
        try:
            state = int(raw)
        except (TypeError, ValueError):
            painter.fillRect(option.rect, QColor(C['bg']))
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Row background
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        painter.fillRect(option.rect,
                         QColor(bg) if isinstance(bg, QColor) else QColor(C['bg']))

        r  = self.R
        cx = option.rect.center().x()
        cy = option.rect.center().y()
        rect = QRect(cx - r, cy - r, r * 2, r * 2)

        if state == CIRCLE_ON:
            painter.setBrush(QBrush(QColor(C['green'])))
            painter.setPen(QPen(QColor(C['green_border']), 1))
            painter.drawEllipse(rect)
        elif state == CIRCLE_OFF:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(C['border2']), 1.5))
            painter.drawEllipse(rect)
        else:  # CIRCLE_PART -- left half green, right half hollow
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(C['green'])))
            painter.drawChord(rect, 90 * 16, 180 * 16)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(C['green']), 1.5))
            painter.drawEllipse(rect)

        painter.restore()

    def sizeHint(self, option, index):
        # Always return height 28 so rows never resize when data changes
        base = super().sizeHint(option, index)
        return QSize(base.width(), 28)

    def createEditor(self, parent, option, index):
        """Only allow editing in the fade time columns -- block all others."""
        col = index.column()
        if col in (FADE_F_COL, FADE_S_COL):
            return super().createEditor(parent, option, index)
        return None  # No editor -> column stays read-only

class RecallScopeWidget(QWidget):
    """
    Foldable recall scope tree.
    Uses Qt's native CheckStateRole on each column for reliable checkbox interaction.
    Column 0 = path label, Column 1 = expand button, Columns 2+ = scope params.
    """
    scope_changed = pyqtSignal()

    def __init__(self, show):
        super().__init__()
        self.show     = show
        self.snapshot = None
        self._build()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top toolbar (shared across all tabs) ──────────────────────────────
        tb = QWidget()
        tb.setStyleSheet(f"background:{C['bg3']};border-bottom:1px solid {C['border']};")
        tb.setFixedHeight(36)
        tbl = QHBoxLayout(tb)
        tbl.setContentsMargins(10, 0, 10, 0); tbl.setSpacing(6)
        lbl = QLabel("RECALL SCOPE")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:0.1em;")
        tbl.addWidget(lbl); tbl.addStretch()
        for text, slot in [
        ]:
            b = QPushButton(text); b.setFixedHeight(24)
            b.clicked.connect(slot); tbl.addWidget(b)

        # Select All / Unselect All -- quickly toggle the entire snapshot scope
        sel_all_btn = QPushButton("Select All")
        sel_all_btn.setFixedHeight(24)
        sel_all_btn.setStyleSheet("font-size:11px;")
        sel_all_btn.clicked.connect(lambda: self._set_all_scope(True))
        tbl.addWidget(sel_all_btn)

        sel_none_btn = QPushButton("Unselect All")
        sel_none_btn.setFixedHeight(24)
        sel_none_btn.setStyleSheet("font-size:11px;")
        sel_none_btn.clicked.connect(lambda: self._set_all_scope(False))
        tbl.addWidget(sel_none_btn)

        # Copy Scope To… button
        copy_btn = QPushButton("Copy Scope To…")
        copy_btn.setFixedHeight(24)
        copy_btn.setStyleSheet(f"font-size:11px;")
        copy_btn.clicked.connect(self._copy_scope_to)
        copy_btn.setToolTip("Copy this snapshot's scope to other snapshots")
        tbl.addWidget(copy_btn)

        # Default button: single-click resets scope; double-click opens settings dialog
        self.default_btn = DoubleClickButton("Default")
        self.default_btn.setFixedHeight(24)
        self.default_btn.setObjectName("amber_btn")
        self.default_btn.clicked.connect(self._reset_default)
        self.default_btn.double_clicked.connect(self._open_default_settings)
        self.default_btn.setToolTip(
            "Left-click: reset snapshot to defaults\n"
            "Right-click: edit what the defaults are")
        tbl.addWidget(self.default_btn)
        self._top_toolbar = tb   # stored so DefaultScopeDialog can hide it
        layout.addWidget(tb)

        # ── Tab widget ────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:5px 14px;font-size:11px;}"
            f"QTabBar::tab:selected{{color:{C['green']};border-bottom:2px solid {C['green']};}}"
        )

        # ── Tab 1: Channel Scope tree ─────────────────────────────────────────
        chan_tab = QWidget()
        chan_layout = QVBoxLayout(chan_tab)
        chan_layout.setContentsMargins(0, 0, 0, 0)
        chan_layout.setSpacing(0)

        total_cols = SEND_TOTAL_COLS
        self.tree = QTreeWidget()
        self.tree.setColumnCount(total_cols)
        self.tree.setAlternatingRowColors(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(0)
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(False)
        # Only allow editing on double-click, and only in fade columns (enforced by delegate)
        self.tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed)

        headers = (["Path", "▶", "Fdr xFade", "Snd xFade"]
                   + [short for _, short, _ in WING_SCOPE_COLS]
                   + [f"Bus{b}" for b in range(1, SEND_BUS_COUNT + 1)]
                   + [f"Mtx{m}" for m in range(1, SEND_MTX_COUNT + 1)])
        self.tree.setHeaderLabels(headers)
        self.tree.headerItem().setText(SENDS_COL, "▶ Sends")
        _sends_hdr_font = QFont(); _sends_hdr_font.setBold(True)
        self.tree.headerItem().setFont(SENDS_COL, _sends_hdr_font)
        hdr = self.tree.header()
        hdr.setDefaultSectionSize(52)
        hdr.setMinimumSectionSize(40)
        hdr.resizeSection(LABEL_COL,  180)
        hdr.resizeSection(EXPAND_COL,  28)
        hdr.resizeSection(FADE_F_COL,  70)
        hdr.resizeSection(FADE_S_COL,  70)
        hdr.setSectionResizeMode(LABEL_COL,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(EXPAND_COL, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(FADE_F_COL, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(FADE_S_COL, QHeaderView.ResizeMode.Fixed)
        # Hide the expand column header label -- it's visual-only
        self.tree.headerItem().setText(EXPAND_COL, "")
        for i in range(FIRST_SCOPE, SEND_TOTAL_COLS):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

        for i, (_, short, tip) in enumerate(WING_SCOPE_COLS):
            self.tree.headerItem().setToolTip(FIRST_SCOPE + i, f"{short}: {tip}")
        self.tree.headerItem().setToolTip(FADE_F_COL, "Fader crossfade time (seconds). Double-click to edit.")
        self.tree.headerItem().setToolTip(FADE_S_COL, "Sends crossfade time (seconds). Double-click to edit.")
        self.tree.headerItem().setToolTip(
            SENDS_COL, "Click to expand: recall-safe each bus/matrix send individually,\ninstead of all-or-nothing for the whole channel.")

        # Per-destination send columns start hidden and are visually placed
        # right after the Sends column (between Sends and Fader) -- logical
        # index never changes, only the on-screen order, so nothing that
        # reads these columns by their fixed index is affected either way.
        self._sends_expanded = False
        for i, dest in enumerate(SEND_DEST_KEYS):
            col = SEND_FIRST_COL + i
            hdr.resizeSection(col, 44)
            label = f"Bus {dest}" if dest.isdigit() else f"Matrix {dest[2:]}"
            self.tree.headerItem().setToolTip(col, f"Send level/mute to {label} (input channels and buses only)")
            self.tree.setColumnHidden(col, True)
            hdr.moveSection(hdr.visualIndex(col), SENDS_COL + 1 + i)

        self._delegate = ScopeCircleDelegate(self.tree)
        self.tree.setItemDelegate(self._delegate)

        hdr.setSectionsClickable(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        # itemClicked handles circle toggles; itemChanged handles fade text edits
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_fade_edited)

        chan_layout.addWidget(self.tree)

        # Legend
        leg = QWidget()
        leg.setStyleSheet(f"background:{C['bg3']};border-top:1px solid {C['border']};")
        leg.setFixedHeight(26)
        ll = QHBoxLayout(leg); ll.setContentsMargins(12, 0, 12, 0); ll.setSpacing(20)
        for color, circle, text in [
            (C['green'],   "●", "Included"),
            (C['border2'], "○", "Excluded"),
            (C['green'],   "◐", "Partial  --  click column header to toggle entire column"),
        ]:
            row_l = QHBoxLayout(); row_l.setSpacing(4)
            dot = QLabel(circle); dot.setStyleSheet(f"color:{color};font-size:14px;")
            txt = QLabel(text);   txt.setStyleSheet(f"color:{C['text3']};font-size:11px;")
            row_l.addWidget(dot); row_l.addWidget(txt)
            ll.addLayout(row_l)
        ll.addStretch()
        chan_layout.addWidget(leg)
        self.tabs.addTab(chan_tab, "Channel Scope")

        # ── Tab 2: FX Slots ───────────────────────────────────────────────────
        self.fx_panel = SimpleTogglePanel("FX Slots", FX_SLOTS)
        self.fx_panel.changed.connect(self.scope_changed.emit)
        self.tabs.addTab(self.fx_panel, "FX Slots  (1–16)")

        # ── Tab 3: Console Config ─────────────────────────────────────────────
        self.cfg_panel = SimpleTogglePanel("Console Config", CFG_ITEMS)
        self.cfg_panel.changed.connect(self.scope_changed.emit)
        self.tabs.addTab(self.cfg_panel, "Console Config")

        # ── Tab 4: OSC Messages ───────────────────────────────────────────────
        self.osc_tab = SnapshotOscTab(self.show)
        self.tabs.addTab(self.osc_tab, "OSC Messages")

        layout.addWidget(self.tabs)

    # ── Tree population ───────────────────────────────────────────────────────

    def set_toolbar_visible(self, visible: bool):
        """Show or hide the top toolbar -- used by DefaultScopeDialog for a cleaner embed."""
        self._top_toolbar.setVisible(visible)

    def load_snapshot(self, snap):
        self.snapshot = snap
        self._rebuild()
        if snap:
            self.fx_panel.load(snap.fx_scope)
            self.cfg_panel.load(snap.cfg_scope)
            self.osc_tab.load(snap)
        else:
            self.fx_panel.load({k: True  for k, _ in FX_SLOTS})
            self.cfg_panel.load({k: False for k, _ in CFG_ITEMS})
            self.osc_tab.load(None)

    def _rebuild(self, restore_expansion=True):
        """Rebuild tree. When restore_expansion=True, preserve exactly which
        groups the user had open. Never auto-expand anything."""
        snap_name = getattr(self.snapshot, 'name', None)
        ch_count  = len(getattr(self.snapshot, 'channel_scopes', {})) if self.snapshot else 0
        # Save expanded group keys before clearing
        expanded = set()
        if restore_expansion:
            for i in range(self.tree.topLevelItemCount()):
                g = self.tree.topLevelItem(i)
                if g.isExpanded():
                    d = g.data(LABEL_COL, Qt.ItemDataRole.UserRole)
                    if d:
                        expanded.add(d.get("key", ""))

        self.tree.blockSignals(True)
        self.tree.clear()

        if not self.snapshot:
            self.tree.blockSignals(False)
            return

        for group_key, group_label, children in SCOPE_PATH_GROUPS:
            group_item = self._make_group_item(group_label, group_key, children)
            self.tree.addTopLevelItem(group_item)
            for ch_key, ch_label in children:
                child = self._make_child_item(ch_label, ch_key)
                group_item.addChild(child)
            # Only expand if it was open before -- never auto-expand
            if group_key in expanded:
                group_item.setExpanded(True)

        self._update_expand_buttons()
        self.tree.blockSignals(False)

    def _make_group_item(self, label, group_key, children):
        item = QTreeWidgetItem()
        item.setData(LABEL_COL, Qt.ItemDataRole.UserRole,
                     {"type": "group", "key": group_key,
                      "children": [c for c, _ in children]})
        item.setText(LABEL_COL, f"  {label}")
        f = QFont(); f.setBold(True); item.setFont(LABEL_COL, f)
        item.setForeground(LABEL_COL, QColor(C['text2']))
        item.setBackground(LABEL_COL, QColor(C['bg3']))
        item.setText(EXPAND_COL, "▶")
        item.setTextAlignment(EXPAND_COL, Qt.AlignmentFlag.AlignCenter)
        item.setForeground(EXPAND_COL, QColor(C['text3']))
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                      | Qt.ItemFlag.ItemIsEditable)

        ch_keys  = [k for k, _ in children]
        is_dca_group = (group_key == "dcas")
        global_scope = self.snapshot.scope

        for col_i, (sk, _, _) in enumerate(WING_SCOPE_COLS):
            col = FIRST_SCOPE + col_i
            if is_dca_group and sk not in DCA_APPLICABLE:
                item.setText(col, " --")
                item.setForeground(col, QColor(C['text3']))
                item.setBackground(col, QColor(C['bg3']))
                continue
            global_val = global_scope.get(sk, True)
            # Read-only lookup -- do NOT use get_ch_scope() which would mutate channel_scopes
            vals = [(self.snapshot.channel_scopes[ck].overrides.get(sk, global_val)
                     if ck in self.snapshot.channel_scopes
                     else global_val)
                    for ck in ch_keys]
            if not vals:
                circle = CIRCLE_ON if global_val else CIRCLE_OFF
            elif all(vals):
                circle = CIRCLE_ON
            elif any(vals):
                circle = CIRCLE_PART
            else:
                circle = CIRCLE_OFF
            item.setData(col, CIRCLE_ROLE, circle)
            item.setBackground(col, QColor(C['bg3']))

        # Per-destination send columns -- both the input-channels group and
        # the buses group have real per-send data (channels/buses send to
        # buses AND directly to matrix outputs). Other groups (matrix,
        # mains, DCAs) show " --", same as their existing non-applicable columns.
        is_inputs_or_buses_group = group_key in ("inputs", "buses")
        global_sends_val = global_scope.get('sends', True)
        for i, dest in enumerate(SEND_DEST_KEYS):
            col = SEND_FIRST_COL + i
            if not is_inputs_or_buses_group:
                item.setText(col, " --")
                item.setForeground(col, QColor(C['text3']))
                item.setBackground(col, QColor(C['bg3']))
                continue
            vals = []
            for ck in ch_keys:
                cs = self.snapshot.channel_scopes.get(ck)
                fallback = (cs.overrides.get('sends', global_sends_val) if cs else global_sends_val)
                vals.append(cs.send_overrides.get(dest, fallback) if cs else fallback)
            if not vals:
                circle = CIRCLE_ON if global_sends_val else CIRCLE_OFF
            elif all(vals):
                circle = CIRCLE_ON
            elif any(vals):
                circle = CIRCLE_PART
            else:
                circle = CIRCLE_OFF
            item.setData(col, CIRCLE_ROLE, circle)
            item.setBackground(col, QColor(C['bg3']))

        # Fade time columns -- group headers always show "0.0" (never blank)
        ff = self.snapshot.get_group_fade(group_key, "fader")
        fs = self.snapshot.get_group_fade(group_key, "sends")
        item.setText(FADE_F_COL, f"{ff:.1f}" if ff > 0 else "0.0")
        item.setTextAlignment(FADE_F_COL, Qt.AlignmentFlag.AlignCenter)
        item.setForeground(FADE_F_COL, QColor(C['text2']))
        if is_dca_group:
            # DCAs cannot fade sends
            item.setText(FADE_S_COL, " --")
            item.setForeground(FADE_S_COL, QColor(C['text3']))
        else:
            item.setText(FADE_S_COL, f"{fs:.1f}" if fs > 0 else "0.0")
            item.setTextAlignment(FADE_S_COL, Qt.AlignmentFlag.AlignCenter)
            item.setForeground(FADE_S_COL, QColor(C['text2']))
        return item

    def _make_child_item(self, label, ch_key):
        item = QTreeWidgetItem()
        item.setData(LABEL_COL, Qt.ItemDataRole.UserRole,
                     {"type": "channel", "key": ch_key})
        item.setText(LABEL_COL, "    " + label)
        item.setForeground(LABEL_COL, QColor(C['text']))
        item.setText(EXPAND_COL, "")
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                      | Qt.ItemFlag.ItemIsEditable)

        is_dca = ch_key.startswith("dca_")
        # Read-only lookup -- do NOT use get_ch_scope() which would mutate channel_scopes
        cs = self.snapshot.channel_scopes.get(ch_key)
        global_scope = self.snapshot.scope

        # Fade columns -- blank means "inherit from group" (0 = no per-channel override)
        item.setText(FADE_F_COL, f"{cs.fader_fade:.1f}" if cs and cs.fader_fade > 0 else "")
        item.setTextAlignment(FADE_F_COL, Qt.AlignmentFlag.AlignCenter)
        if is_dca:
            item.setText(FADE_S_COL, " --")
            item.setForeground(FADE_S_COL, QColor(C['text3']))
        else:
            item.setText(FADE_S_COL, f"{cs.sends_fade:.1f}" if cs and cs.sends_fade > 0 else "")
            item.setTextAlignment(FADE_S_COL, Qt.AlignmentFlag.AlignCenter)

        for col_i, (sk, _, _) in enumerate(WING_SCOPE_COLS):
            col = FIRST_SCOPE + col_i
            if is_dca and sk not in DCA_APPLICABLE:
                item.setText(col, " --")
                item.setForeground(col, QColor(C['text3']))
            else:
                global_val = global_scope.get(sk, True)
                val = (cs.overrides.get(sk, global_val) if cs else global_val)
                item.setData(col, CIRCLE_ROLE, CIRCLE_ON if val else CIRCLE_OFF)

        # Per-destination send columns -- input channels send to buses AND
        # directly to matrix outputs; buses can send to other buses and to
        # matrix outputs too. Both row kinds get real data here. Other row
        # kinds (matrix/main/dca rows themselves) show " --".
        is_input = ch_key.startswith("input_")
        is_bus   = ch_key.startswith("bus_")
        global_sends_val = global_scope.get('sends', True)
        for i, dest in enumerate(SEND_DEST_KEYS):
            col = SEND_FIRST_COL + i
            if not (is_input or is_bus):
                item.setText(col, " --")
                item.setForeground(col, QColor(C['text3']))
                continue
            fallback = (cs.overrides.get('sends', global_sends_val) if cs else global_sends_val)
            val = (cs.send_overrides.get(dest, fallback) if cs else fallback)
            item.setData(col, CIRCLE_ROLE, CIRCLE_ON if val else CIRCLE_OFF)
        return item

    def _update_expand_buttons(self):
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            g.setText(EXPAND_COL, "▼" if g.isExpanded() else "▶")

    # ── All interaction goes through itemClicked ───────────────────────────────

    def _on_item_clicked(self, item, col):
        data = item.data(LABEL_COL, Qt.ItemDataRole.UserRole)
        if not data:
            return
        item_type = data.get("type", "?")

        if col == EXPAND_COL and data["type"] == "group":
            item.setExpanded(not item.isExpanded())
            self._update_expand_buttons()
            return

        if SEND_FIRST_COL <= col < SEND_TOTAL_COLS:
            self._on_send_cell_clicked(item, col, data)
            return

        if col < FIRST_SCOPE or col >= TOTAL_COLS or not self.snapshot:
            return

        sk = WING_SCOPE_COLS[col - FIRST_SCOPE][0]

        if data["type"] == "group":
            # Toggle: partial/off -> all on; all on -> all off
            current  = item.data(col, CIRCLE_ROLE)
            new_val  = (current != CIRCLE_ON)
            new_circ = CIRCLE_ON if new_val else CIRCLE_OFF
            ch_keys  = data.get("children", [])
            global_val = self.snapshot.scope.get(sk, True)
            for ck in ch_keys:
                if ck.startswith("dca_") and sk not in DCA_APPLICABLE:
                    continue
                cs = self.snapshot.get_ch_scope(ck)
                if new_val != global_val:
                    cs.overrides[sk] = new_val
                else:
                    cs.overrides.pop(sk, None)
            item.setData(col, CIRCLE_ROLE, new_circ)
            for i in range(item.childCount()):
                child = item.child(i)
                child_data = child.data(LABEL_COL, Qt.ItemDataRole.UserRole)
                ck = child_data.get("key", "") if child_data else ""
                if ck.startswith("dca_") and sk not in DCA_APPLICABLE:
                    continue
                child.setData(col, CIRCLE_ROLE, new_circ)

        elif data["type"] == "channel":
            ck = data["key"]
            if ck.startswith("dca_") and sk not in DCA_APPLICABLE:
                return
            cs      = self.snapshot.get_ch_scope(ck)
            current = item.data(col, CIRCLE_ROLE)
            new_val = (current != CIRCLE_ON)
            if new_val != self.snapshot.scope.get(sk, True):
                cs.overrides[sk] = new_val
            else:
                cs.overrides.pop(sk, None)
            item.setData(col, CIRCLE_ROLE, CIRCLE_ON if new_val else CIRCLE_OFF)
            self._refresh_group_col(item, col, sk)

        self.tree.viewport().update()
        self.scope_changed.emit()

    def _on_send_cell_clicked(self, item, col, data):
        """Click a single bus/matrix cell in the expanded Sends columns --
        same on/off toggle behaviour as the regular scope columns, scoped
        to send_overrides[dest] instead of overrides[sk]. Input channels
        and buses both have real data here (channels/buses send to buses
        AND directly to matrix outputs) -- other row kinds show ' --' and
        are not clickable."""
        if not self.snapshot:
            return
        dest = SEND_DEST_KEYS[col - SEND_FIRST_COL]
        global_val = self.snapshot.scope.get('sends', True)

        if data["type"] == "group":
            if data.get("key") not in ("inputs", "buses"):
                return   # " --" cells (matrix/DCA groups) aren't interactive
            current  = item.data(col, CIRCLE_ROLE)
            new_val  = (current != CIRCLE_ON)
            new_circ = CIRCLE_ON if new_val else CIRCLE_OFF
            for ck in data.get("children", []):
                cs = self.snapshot.get_ch_scope(ck)
                cs.send_overrides[dest] = new_val
            item.setData(col, CIRCLE_ROLE, new_circ)
            for i in range(item.childCount()):
                item.child(i).setData(col, CIRCLE_ROLE, new_circ)

        elif data["type"] == "channel":
            ck = data["key"]
            if not (ck.startswith("input_") or ck.startswith("bus_")):
                return
            cs      = self.snapshot.get_ch_scope(ck)
            current = item.data(col, CIRCLE_ROLE)
            new_val = (current != CIRCLE_ON)
            cs.send_overrides[dest] = new_val
            item.setData(col, CIRCLE_ROLE, CIRCLE_ON if new_val else CIRCLE_OFF)
            self._refresh_send_group_col(item, col, dest)

        self.tree.viewport().update()
        self.scope_changed.emit()

    def _refresh_send_group_col(self, child_item, col, dest):
        """After a channel-level send toggle, recompute the parent group's
        aggregate circle for that same destination column."""
        parent = child_item.parent()
        if not parent:
            return
        data = parent.data(LABEL_COL, Qt.ItemDataRole.UserRole)
        if not data or data.get("key") not in ("inputs", "buses"):
            return
        global_val = self.snapshot.scope.get('sends', True)
        vals = []
        for ck in data.get("children", []):
            cs = self.snapshot.channel_scopes.get(ck)
            fallback = (cs.overrides.get('sends', global_val) if cs else global_val)
            vals.append(cs.send_overrides.get(dest, fallback) if cs else fallback)
        if not vals:
            return
        if all(vals):   circle = CIRCLE_ON
        elif any(vals): circle = CIRCLE_PART
        else:           circle = CIRCLE_OFF
        parent.setData(col, CIRCLE_ROLE, circle)

    def _on_fade_edited(self, item, col):
        """Handle edits to the Fader/Sends fade time columns."""
        if col not in (FADE_F_COL, FADE_S_COL) or not self.snapshot:
            return
        data = item.data(LABEL_COL, Qt.ItemDataRole.UserRole)
        if not data:
            return
        try:
            val = max(0.0, float(item.text(col)))
        except (ValueError, TypeError):
            val = 0.0

        param = "fader" if col == FADE_F_COL else "sends"

        if data["type"] == "group":
            self.snapshot.set_group_fade(data["key"], param, val)
        elif data["type"] == "channel":
            cs = self.snapshot.get_ch_scope(data["key"])
            if col == FADE_F_COL:
                cs.fader_fade = val
            else:
                cs.sends_fade = val

        # Reformat to exactly 1 decimal place (e.g. "4" -> "4.0")
        self.tree.blockSignals(True)
        # Groups always show 0.0; channels show blank when zero (= inherit from group)
        is_group = data["type"] == "group"
        item.setText(col, f"{val:.1f}" if val > 0 or is_group else "")
        self.tree.blockSignals(False)
        self.scope_changed.emit()

    def _refresh_group_col(self, child_item, col, sk):
        parent = child_item.parent()
        if not parent:
            return
        data = parent.data(LABEL_COL, Qt.ItemDataRole.UserRole)
        if not data:
            return
        global_val = self.snapshot.scope.get(sk, True)
        # Read-only -- don't create channel scopes just for display
        vals = [(self.snapshot.channel_scopes[ck].overrides.get(sk, global_val)
                 if ck in self.snapshot.channel_scopes
                 else global_val)
                for ck in data.get("children", [])]
        if not vals:
            return
        if all(vals):   circle = CIRCLE_ON
        elif any(vals): circle = CIRCLE_PART
        else:           circle = CIRCLE_OFF
        parent.setData(col, CIRCLE_ROLE, circle)

    # ── Header column click -- toggle entire column ────────────────────────────

    def _on_header_clicked(self, col):
        if col == SENDS_COL:
            self._toggle_sends_expanded()
            return
        if SEND_FIRST_COL <= col < SEND_TOTAL_COLS:
            self._on_send_header_clicked(col)
            return
        if col < FIRST_SCOPE or col >= TOTAL_COLS or not self.snapshot:
            return
        sk = WING_SCOPE_COLS[col - FIRST_SCOPE][0]
        new_val = not self.snapshot.scope.get(sk, True)
        new_circle = CIRCLE_ON if new_val else CIRCLE_OFF
        self.snapshot.scope[sk] = new_val
        for cs in self.snapshot.channel_scopes.values():
            cs.overrides.pop(sk, None)
        for i in range(self.tree.topLevelItemCount()):
            grp = self.tree.topLevelItem(i)
            grp.setData(col, CIRCLE_ROLE, new_circle)
            for j in range(grp.childCount()):
                grp.child(j).setData(col, CIRCLE_ROLE, new_circle)
        self.tree.viewport().update()
        self.scope_changed.emit()

    def _toggle_sends_expanded(self):
        """Show/hide the per-bus send columns, positioned right after the
        aggregate Sends column. Logical column indices never change -- only
        visibility and on-screen order -- so this never touches how any
        other column's data is read or written."""
        self._sends_expanded = not self._sends_expanded
        for i in range(len(SEND_DEST_KEYS)):
            self.tree.setColumnHidden(SEND_FIRST_COL + i, not self._sends_expanded)
        self.tree.headerItem().setText(
            SENDS_COL, ("▼ Sends" if self._sends_expanded else "▶ Sends"))
        _f = QFont(); _f.setBold(True)
        self.tree.headerItem().setFont(SENDS_COL, _f)

    def _on_send_header_clicked(self, col):
        """Click a per-destination send sub-header -- toggle that one
        bus/matrix destination on/off for every input channel AND bus at
        once (same pattern as _on_header_clicked, scoped to send_overrides
        instead of the aggregate overrides dict)."""
        if not self.snapshot:
            return
        dest = SEND_DEST_KEYS[col - SEND_FIRST_COL]
        # Determine current aggregate state to decide on vs off, same
        # "any on -> turn all off, else all on" logic used for the regular
        # scope-key column headers.
        global_val = self.snapshot.scope.get('sends', True)
        any_on = False
        for i in range(self.tree.topLevelItemCount()):
            grp = self.tree.topLevelItem(i)
            for j in range(grp.childCount()):
                child = grp.child(j)
                d = child.data(LABEL_COL, Qt.ItemDataRole.UserRole)
                ck = d.get("key", "") if d else ""
                if not (ck.startswith("input_") or ck.startswith("bus_")):
                    continue
                cs = self.snapshot.channel_scopes.get(ck)
                val = (cs.send_overrides.get(dest, cs.overrides.get('sends', global_val))
                       if cs else global_val)
                if val:
                    any_on = True
                    break
            if any_on:
                break
        new_val = not any_on
        for ch_key, cs in self.snapshot.channel_scopes.items():
            if ch_key.startswith("input_") or ch_key.startswith("bus_"):
                cs.send_overrides[dest] = new_val
        self._rebuild(restore_expansion=True)
        self.scope_changed.emit()



    def _set_all_scope(self, value):
        """Set all scope keys on/off for the current snapshot.

        Also clears per-channel/group overrides -- otherwise an inherited
        exception (e.g. "Sends off for buses only", copied in from the
        Default scope) would keep showing as excluded even after Select All,
        since a per-channel override always takes priority over the global
        scope value when the grid renders each cell.
        """
        if not self.snapshot:
            return
        for k in WING_SCOPE_KEYS:
            self.snapshot.scope[k] = value
        for cs in self.snapshot.channel_scopes.values():
            cs.overrides.clear()
            cs.send_overrides.clear()
        self._rebuild(restore_expansion=True)
        self.scope_changed.emit()

    def _reset_default(self):
        """Left-click Default -- 1-to-1 copy of DEFAULT_* to this snapshot."""
        try:
            if not self.snapshot:
                return
            self.snapshot.scope          = dict(DEFAULT_SCOPE)
            self.snapshot.channel_scopes = _copy_channel_scopes(DEFAULT_CHANNEL_SCOPES)
            self.snapshot.fx_scope       = dict(DEFAULT_FX_SCOPE)
            self.snapshot.cfg_scope      = dict(DEFAULT_CFG_SCOPE)
            for gk, fades in DEFAULT_GROUP_FADES.items():
                self.snapshot.group_fades[gk] = dict(fades)
            self._rebuild(restore_expansion=True)
            self.fx_panel.load(self.snapshot.fx_scope)
            self.cfg_panel.load(self.snapshot.cfg_scope)
        except Exception:
            import traceback
            traceback.print_exc()

    def _open_default_settings(self):
        """Right-click Default -- open dialog to edit global default scope values."""
        dlg = DefaultScopeDialog(self.show, self.window())
        result = dlg.exec()
        del dlg  # force cleanup of dialog and its child widgets
        # Flush all pending events and restore macOS window focus
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        main = self.window()
        if main:
            main.activateWindow()
            main.raise_()

    def _copy_scope_to(self):
        """Copy Scope To… -- open dialog to copy scope to other snapshots."""
        if not self.snapshot:
            QMessageBox.information(
                self.window(), "No snapshot selected",
                "Please select a snapshot first.")
            return
        all_snaps = self.show.snapshots if self.show else []
        if len(all_snaps) < 2:
            QMessageBox.information(
                self.window(), "Only one snapshot",
                "There are no other snapshots to copy to.")
            return
        dlg = CopyScopeDialog(self.snapshot, all_snaps, self.window())
        dlg.exec()


# ─── Connection Panel ─────────────────────────────────────────────────────────

class ConnectionPanel(QWidget):
    connect_requested    = pyqtSignal(str, int, str)   # wing_ip, port, local_ip
    disconnect_requested = pyqtSignal()
    auto_update_changed  = pyqtSignal(bool)

    def __init__(self):
        super().__init__(); self._build()

    def _build(self):
        l = QHBoxLayout(self); l.setContentsMargins(8,6,8,6); l.setSpacing(8)

        # LIVE button -- first
        self.live_btn = QPushButton("LIVE")
        self.live_btn.setCheckable(True)
        self.live_btn.setFixedHeight(26)
        self.live_btn.setStyleSheet(
            f"font-size:10px;letter-spacing:0.1em;padding:0 12px;font-weight:bold;"
            f"color:{C['text3']};border:1px solid {C['border']};border-radius:4px;"
            f"background:{C['bg3']};")
        l.addWidget(self.live_btn)

        # AUTO UPDATE -- right next to LIVE
        self.au_btn = QPushButton("AUTO UPDATE")
        self.au_btn.setCheckable(True)
        self.au_btn.setFixedHeight(26)
        self.au_btn.setStyleSheet(
            f"font-size:10px;letter-spacing:0.08em;padding:0 10px;"
            f"color:{C['text3']};border:1px solid {C['border']};border-radius:4px;"
            f"background:{C['bg3']};")
        self.au_btn.clicked.connect(self._on_au)
        l.addWidget(self.au_btn)
        l.addSpacing(10)

        # Status dot + text (always visible)
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{C['red']};font-size:16px;")
        l.addWidget(self.dot)
        self.status = QLabel("Not connected")
        self.status.setStyleSheet(f"color:{C['text2']};font-size:12px;")
        l.addWidget(self.status)
        l.addSpacing(10)

        # Edit-mode-only widgets (hidden in live mode)
        self.ip_lbl = QLabel("Wing IP:")
        self.ip_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        l.addWidget(self.ip_lbl)
        self.ip_input = QLineEdit("192.168.1.1"); self.ip_input.setFixedWidth(130)
        l.addWidget(self.ip_input)

        # Local interface selector
        self.iface_lbl = QLabel("via:")
        self.iface_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        l.addWidget(self.iface_lbl)
        self.iface_combo = QComboBox(); self.iface_combo.setFixedWidth(160)
        self.iface_combo.setToolTip("Select the network interface connected to Wing")
        self._populate_interfaces()
        l.addWidget(self.iface_combo)

        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedSize(26, 26)
        refresh_btn.setToolTip("Refresh network interfaces")
        refresh_btn.clicked.connect(self._refresh_interfaces)
        l.addWidget(refresh_btn)

        self.conn_btn = QPushButton("Connect")
        self.conn_btn.setObjectName("green_btn"); self.conn_btn.setMinimumWidth(80)
        self.conn_btn.clicked.connect(self._on_connect); l.addWidget(self.conn_btn)
        l.addStretch()

        # Widgets to hide in live mode
        self._edit_widgets = [self.ip_lbl, self.ip_input,
                              self.iface_lbl, self.iface_combo, self.conn_btn]

    def set_live(self, live):
        """Show/hide edit-only widgets based on mode."""
        for w in self._edit_widgets:
            w.setVisible(not live)

    def _populate_interfaces(self):
        """List available IPv4 interfaces. Auto-selects the one matching Wing's subnet."""
        self.iface_combo.blockSignals(True)
        current = self.iface_combo.currentData()
        self.iface_combo.clear()
        self.iface_combo.addItem("Auto (0.0.0.0)", "0.0.0.0")
        wing_octets = self.ip_input.text().strip().split('.')
        best_match_idx = 0
        try:
            from PyQt6.QtNetwork import QNetworkInterface
            for iface in QNetworkInterface.allInterfaces():
                    for entry in iface.addressEntries():
                        ip = entry.ip().toString()
                        if '.' in ip and not ip.startswith('127.'):
                            name = iface.humanReadableName()
                            self.iface_combo.addItem(f"{ip}  ({name})", ip)
                            # Auto-select if first 2 octets match Wing IP
                            ip_octets = ip.split('.')
                            if (len(wing_octets) >= 2 and len(ip_octets) >= 2
                                    and wing_octets[0] == ip_octets[0]
                                    and wing_octets[1] == ip_octets[1]):
                                best_match_idx = self.iface_combo.count() - 1
        except Exception:
            pass
        # Restore previous selection or use best match
        restored = False
        if current:
            for i in range(self.iface_combo.count()):
                if self.iface_combo.itemData(i) == current:
                    self.iface_combo.setCurrentIndex(i); restored = True; break
        if not restored:
            self.iface_combo.setCurrentIndex(best_match_idx)
        self.iface_combo.blockSignals(False)

    def _refresh_interfaces(self):
        self._populate_interfaces()
        # Also refresh OSC endpoint interface dropdowns
        try:
            main = self.window()
            if hasattr(main, 'osc_settings_panel'):
                main.osc_settings_panel.refresh_interfaces()
        except Exception:
            pass

    def _on_connect(self):
        if self.conn_btn.text() == "Connect":
            local_ip = self.iface_combo.currentData() or "0.0.0.0"
            self.connect_requested.emit(self.ip_input.text().strip(), 2223, local_ip)
        else:
            self.disconnect_requested.emit()

    def _on_au(self, checked):
        if checked:
            self.au_btn.setStyleSheet(
                f"font-size:10px;letter-spacing:0.08em;padding:0 10px;"
                f"color:{C['green']};border:1px solid {C['green_border']};border-radius:4px;"
                f"background:{C['green_bg']};")
        else:
            self.au_btn.setStyleSheet(
                f"font-size:10px;letter-spacing:0.08em;padding:0 10px;"
                f"color:{C['text3']};border:1px solid {C['border']};border-radius:4px;"
                f"background:{C['bg3']};")
        self.auto_update_changed.emit(checked)

    def set_connected(self, connected, ip=""):
        if connected:
            self.dot.setStyleSheet(f"color:{C['green']};font-size:16px;")
            self.status.setText(f"Connected to {ip}")
            self.status.setStyleSheet(f"color:{C['green']};font-size:12px;")
            self.conn_btn.setText("Disconnect"); self.conn_btn.setObjectName("danger_btn")
        else:
            self.dot.setStyleSheet(f"color:{C['red']};font-size:16px;")
            self.status.setText("Not connected")
            self.status.setStyleSheet(f"color:{C['text2']};font-size:12px;")
            self.conn_btn.setText("Connect"); self.conn_btn.setObjectName("green_btn")
        self.conn_btn.setStyle(self.conn_btn.style())


# ─── Cue List Panel ───────────────────────────────────────────────────────────

class CueListDelegate(QStyledItemDelegate):
    """
    Preserves the active cue's green text even when it is selected.
    Strategy (paint-on-top):
      1. Call super().paint() -- draws selection background + white text (from stylesheet).
      2. Fill text area with the selection bg colour, erasing the white text.
      3. Redraw the text in the item's own foreground colour (green for active cue).
    _SEL_BG and _WHITE are lazy-initialised so QApplication exists when QColor is created.
    """
    _SEL_BG = None   # QColor("#1e3a5f") -- initialised on first paint
    _WHITE  = None   # QColor(C['text'])  -- initialised on first paint

    def paint(self, painter, option, index):
        try:
            if CueListDelegate._SEL_BG is None:
                CueListDelegate._SEL_BG = QColor("#1e3a5f")
            if CueListDelegate._WHITE is None:
                CueListDelegate._WHITE  = QColor(C['text'])

            is_selected = bool(option.state & QStyle.StateFlag.State_Selected)
            fg_data     = index.data(Qt.ItemDataRole.ForegroundRole)

            if not is_selected or not fg_data:
                super().paint(painter, option, index)
                return

            fg_color = (fg_data.color() if isinstance(fg_data, QBrush)
                        else QColor(str(fg_data)))

            if fg_color.name() == CueListDelegate._WHITE.name():
                super().paint(painter, option, index)
                return

            # Active cue + selected ─────────────────────────────────────────
            # Step 1: normal draw (selection bg + white text)
            super().paint(painter, option, index)

            painter.save()
            # Step 2: erase white text -- fill text area with selection bg
            # Keep 3 px on the left so the border-left from the stylesheet survives
            painter.fillRect(option.rect.adjusted(3, 1, -1, -1), CueListDelegate._SEL_BG)

            # Step 3: redraw text in the item's own colour (green)
            font_data = index.data(Qt.ItemDataRole.FontRole)
            if font_data:
                painter.setFont(font_data)
            painter.setPen(fg_color)
            painter.drawText(
                option.rect.adjusted(10, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                index.data(Qt.ItemDataRole.DisplayRole) or "")
            painter.restore()

        except Exception:
            import traceback; traceback.print_exc()
            super().paint(painter, option, index)   # fallback


class CueListWidget(QListWidget):
    """QListWidget with drag-reorder support. Emits reordered() after a drop.
    Converts OnItem drops to above/below based on cursor position."""
    reordered = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        event.accept()   # always accept -- we resolve OnItem in dropEvent

    def dropEvent(self, event):
        pos = event.position().toPoint()
        target_item = self.itemAt(pos)

        if (self.dropIndicatorPosition() ==
                QAbstractItemView.DropIndicatorPosition.OnItem
                and target_item):
            # Snap to above or below based on cursor vs item centre
            rect        = self.visualItemRect(target_item)
            target_row  = self.row(target_item)
            insert_row  = target_row if pos.y() < rect.center().y() else target_row + 1

            dragged = self.selectedItems()
            if dragged:
                drag_row = self.row(dragged[0])
                item = self.takeItem(drag_row)
                if drag_row < insert_row:
                    insert_row -= 1
                self.insertItem(insert_row, item)
                self.setCurrentItem(item)
                self.reordered.emit()
                event.accept()
                return

        super().dropEvent(event)
        self.reordered.emit()

class CueListPanel(QWidget):
    cue_selected    = pyqtSignal(int)
    go_pressed      = pyqtSignal()
    add_pressed     = pyqtSignal()
    snap_reordered  = pyqtSignal(list)
    snap_duplicate  = pyqtSignal(int)
    snaps_delete    = pyqtSignal(list)
    snaps_set_group = pyqtSignal(list, str)
    snaps_set_scope = pyqtSignal(list, dict)
    multi_selected  = pyqtSignal(int)   # number of selected cues (0 or 1 = normal)

    def __init__(self):
        super().__init__()
        self.current_index  = -1
        self.active_index   = -1
        self._snap_rows     = []
        self._build()

    def _build(self):
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        hdr = QWidget(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background:{C['bg3']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,0,8,0)
        t = QLabel("CUE LIST")
        t.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:0.1em;")
        hl.addWidget(t); hl.addStretch()
        self.add_snap_btn = QPushButton("Add Snap")
        self.add_snap_btn.setFixedHeight(24); self.add_snap_btn.setMinimumWidth(70)
        self.add_snap_btn.setStyleSheet("font-size:11px;")
        self.add_snap_btn.clicked.connect(self.add_pressed.emit)
        hl.addWidget(self.add_snap_btn); l.addWidget(hdr)

        self.list_widget = CueListWidget()
        self.list_widget.setItemDelegate(CueListDelegate())
        # Enable Cmd+click / Shift+click multi-selection
        self.list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.currentRowChanged.connect(self._on_row)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.reordered.connect(self._on_reordered)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        # Delete key shortcut
        del_sc = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.list_widget)
        del_sc.activated.connect(self._delete_selected)
        del_sc2 = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self.list_widget)
        del_sc2.activated.connect(self._delete_selected)
        l.addWidget(self.list_widget)

        self.live_notes = QLabel("")
        self.live_notes.setStyleSheet(
            f"color:{C['text2']};font-size:12px;font-style:italic;"
            f"background:{C['bg2']};border-top:1px solid {C['border']};"
            f"padding:6px 12px;")
        self.live_notes.setWordWrap(True)
        self.live_notes.setVisible(False)
        l.addWidget(self.live_notes)

        # Separator line above GO area (separate from button so hover affects full border)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(2)
        sep.setStyleSheet(f"background:{C['green_border']};border:none;")
        l.addWidget(sep)

        go_frame = QWidget()
        go_frame.setStyleSheet(f"background:{C['bg3']};")
        gl = QVBoxLayout(go_frame); gl.setContentsMargins(10, 10, 10, 10); gl.setSpacing(6)
        self.go_btn = QPushButton("GO"); self.go_btn.setObjectName("go_btn")
        self.go_btn.setFixedHeight(52); self.go_btn.clicked.connect(self.go_pressed.emit)
        gl.addWidget(self.go_btn); l.addWidget(go_frame)

    # ── Selection helpers ────────────────────────────────────────────────────

    def _selected_snap_indices(self):
        """Return list of snapshot indices for all selected rows."""
        indices = []
        for item in self.list_widget.selectedItems():
            si = item.data(Qt.ItemDataRole.UserRole)
            if si is not None and si >= 0:
                indices.append(si)
        return sorted(set(indices))

    def _delete_selected(self):
        indices = self._selected_snap_indices()
        if indices:
            self.snaps_delete.emit(indices)

    # ── Row events ──────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        """Emit multi_selected when more than one cue is selected."""
        self.multi_selected.emit(len(self._selected_snap_indices()))

    def _on_item_clicked(self, item):
        """Ensure cue_selected fires on plain click even if current row didn't change."""
        from PyQt6.QtGui import QGuiApplication
        mods = QGuiApplication.keyboardModifiers()
        if mods & (Qt.KeyboardModifier.ShiftModifier |
                   Qt.KeyboardModifier.ControlModifier |
                   Qt.KeyboardModifier.MetaModifier):
            return   # Shift/Cmd -- let extended selection handle it normally
        si = item.data(Qt.ItemDataRole.UserRole)
        if si is not None and si >= 0:
            self.current_index = si
            self.cue_selected.emit(si)

    def _on_row(self, row):
        if row < 0 or row >= len(self._snap_rows): return
        snap_idx = self._snap_rows[row]
        if snap_idx < 0: return
        self.current_index = snap_idx
        # Don't emit cue_selected if multiple items are selected
        # (detail panel should stay blanked for multi-select)
        if len(self._selected_snap_indices()) <= 1:
            self.cue_selected.emit(snap_idx)

    def _on_reordered(self):
        new_order = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            si = item.data(Qt.ItemDataRole.UserRole)
            if si is not None and si >= 0:
                new_order.append(si)
        self.snap_reordered.emit(new_order)

    def _on_context_menu(self, pos):
        indices = self._selected_snap_indices()
        if not indices: return
        multi = len(indices) > 1

        menu = QMenu(self)
        if not multi:
            menu.addAction("Duplicate").triggered.connect(
                lambda: self.snap_duplicate.emit(indices[0]))
            menu.addSeparator()

        del_act = menu.addAction(
            f"Delete {len(indices)} cues" if multi else "Delete cue")
        del_act.triggered.connect(lambda: self.snaps_delete.emit(indices))

        menu.addSeparator()
        tag_act = menu.addAction(
            f"Set group tag on {len(indices)} cues…" if multi else "Set group tag…")
        tag_act.triggered.connect(lambda: self._tag_group_dialog(indices))
        clear_act = menu.addAction("Clear group tag")
        clear_act.triggered.connect(lambda: self.snaps_set_group.emit(indices, ""))

        menu.addSeparator()
        scope_act = menu.addAction(
            f"Apply default scope to {len(indices)} cues" if multi else "Apply default scope")
        scope_act.triggered.connect(lambda: self.snaps_set_scope.emit(indices, dict(DEFAULT_SCOPE)))

        menu.exec(self.list_widget.mapToGlobal(pos))

    def _tag_group_dialog(self, indices):
        tag, ok = QInputDialog.getText(self, "Group tag",
            f"Tag for {len(indices)} cue(s):")
        if ok:
            self.snaps_set_group.emit(indices, tag.strip())

    def _snap_row_to_list_row(self, snap_idx):
        for i, si in enumerate(self._snap_rows):
            if si == snap_idx: return i
        return -1

    def go_next(self):
        next_snap = self.current_index + 1
        row = self._snap_row_to_list_row(next_snap)
        if row >= 0: self.list_widget.setCurrentRow(row)

    def go_prev(self):
        prev_snap = self.current_index - 1
        if prev_snap >= 0:
            row = self._snap_row_to_list_row(prev_snap)
            if row >= 0: self.list_widget.setCurrentRow(row)

    def set_current(self, snap_idx):
        row = self._snap_row_to_list_row(snap_idx)
        if row >= 0: self.list_widget.setCurrentRow(row)

    # ── Active cue marker (last GOed) ────────────────────────────────────────

    def mark_active(self, snap_idx):
        """Mark the most recently GOed cue green+bold; all others white."""
        self.active_index = snap_idx
        for row, si in enumerate(self._snap_rows):
            item = self.list_widget.item(row)
            if not item: continue
            if si < 0: continue   # header / separator -- leave as-is
            if si == snap_idx:
                item.setForeground(QColor(C['green']))
                f = item.font(); f.setBold(True); item.setFont(f)
            else:
                item.setForeground(QColor(C['text']))
                f = item.font(); f.setBold(False); item.setFont(f)

    # ── Populate ─────────────────────────────────────────────────────────────

    def populate(self, snapshots):
        """Rebuild the cue list. Snapshot rows store snap_idx in UserRole."""
        prev           = self.current_index
        active         = self.active_index
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self._snap_rows = []
        current_group   = None
        prev_was_grouped = False

        for snap_idx, snap in enumerate(snapshots):
            grp = snap.cue_group.strip() if snap.cue_group else ""

            if grp and grp != current_group:
                if snap_idx > 0:
                    sep = QListWidgetItem("")
                    sep.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    sep.setBackground(QColor(C['bg']))
                    sep.setSizeHint(sep.sizeHint().__class__(0, 6))
                    sep.setData(Qt.ItemDataRole.UserRole, -1)
                    self.list_widget.addItem(sep)
                    self._snap_rows.append(-1)
                header = QListWidgetItem(f"  ▸  {grp}")
                header.setForeground(QColor(C['amber']))
                header.setBackground(QColor(C['bg3']))
                f = header.font(); f.setBold(True)
                f.setPointSize(f.pointSize() - 1); header.setFont(f)
                header.setFlags(Qt.ItemFlag.ItemIsEnabled)
                header.setData(Qt.ItemDataRole.UserRole, -1)
                self.list_widget.addItem(header)
                self._snap_rows.append(-1)
                current_group = grp; prev_was_grouped = True
            elif not grp:
                if prev_was_grouped:
                    sep = QListWidgetItem("")
                    sep.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    sep.setBackground(QColor(C['bg']))
                    sep.setSizeHint(sep.sizeHint().__class__(0, 6))
                    sep.setData(Qt.ItemDataRole.UserRole, -1)
                    self.list_widget.addItem(sep)
                    self._snap_rows.append(-1)
                current_group = None; prev_was_grouped = False

            # Snapshot row
            label = (f"      {snap.number:03d}  {snap.name}" if grp
                     else f"  {snap.number:03d}  {snap.name}")
            row_item = QListWidgetItem(label)
            row_item.setData(Qt.ItemDataRole.UserRole, snap_idx)

            if grp:
                row_item.setBackground(QColor(C['bg2']))

            # Active cue: green + bold
            if snap_idx == active:
                row_item.setForeground(QColor(C['green']))
                f = row_item.font(); f.setBold(True); row_item.setFont(f)
            else:
                row_item.setForeground(QColor(C['text']))

            # Only snapshot rows are draggable
            row_item.setFlags(row_item.flags()
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsDropEnabled)
            self.list_widget.addItem(row_item)
            self._snap_rows.append(snap_idx)

        self.list_widget.blockSignals(False)

        # Restore selection and scroll to it
        if snapshots:
            target = min(prev, len(snapshots)-1) if prev >= 0 else 0
            for row, si in enumerate(self._snap_rows):
                if si == target:
                    self.list_widget.setCurrentRow(row)
                    # Defer scroll so the layout is fully updated first
                    item_ref = self.list_widget.item(row)
                    if item_ref:
                        QTimer.singleShot(0, lambda i=item_ref:
                            self.list_widget.scrollToItem(
                                i, QAbstractItemView.ScrollHint.PositionAtCenter))
                    break


# ─── Snapshot Detail Panel ────────────────────────────────────────────────────

class GroupTagsWidget(QWidget):
    """
    Framed row of toggle-chip buttons for assigning a snapshot to a group.
    Active group = filled amber chip with ✕ (click to untag).
    Available groups = outlined chips (click to assign).
    'Add group' text button creates a new group.
    """
    group_changed = pyqtSignal(str)
    group_added   = pyqtSignal(str)
    group_deleted  = pyqtSignal(str)   # group was completely removed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = None
        self._groups   = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {C['border']};
                border-radius: 6px;
                background: {C['bg2']};
            }}
        """)
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(7)

        lbl = QLabel("Group")
        lbl.setStyleSheet(
            f"color:{C['text3']};font-size:10px;letter-spacing:0.08em;"
            "border:none;background:transparent;")
        row.addWidget(lbl)

        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;border:none;")
        self._chips = QHBoxLayout(self._inner)
        self._chips.setContentsMargins(0, 0, 0, 0)
        self._chips.setSpacing(5)
        self._chips.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(self._inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setFixedHeight(24)
        scroll.setStyleSheet("background:transparent;border:none;")
        row.addWidget(scroll)

        add_btn = QPushButton("+ Add group")
        add_btn.setFixedHeight(22)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C['text3']};
                border: 1px solid {C['border']}; border-radius: 10px;
                padding: 0 10px; font-size: 11px;
            }}
            QPushButton:hover {{ color:{C['text']}; border-color:{C['text3']}; }}
            QPushButton:pressed {{ background:{C['bg3']}; }}
        """)
        add_btn.clicked.connect(self._on_add)
        row.addWidget(add_btn)

        outer.addWidget(frame)

        # Fixed height so it never expands when switching tabs in the scope widget
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def load(self, snapshot, groups):
        self._snapshot = snapshot
        self._groups   = list(groups)
        self._rebuild()

    def _rebuild(self):
        while self._chips.count():
            item = self._chips.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        current = (self._snapshot.cue_group or "").strip() if self._snapshot else ""

        for grp in self._groups:
            active = (grp == current)
            btn = QPushButton(f"✕  {grp}" if active else grp)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{C['amber']}; color:{C['bg']};
                        border:1px solid {C['amber']}; border-radius:10px;
                        padding:0 9px; font-size:11px; font-weight:bold;
                    }}
                    QPushButton:hover {{ background:{C['amber']}cc; }}
                    QPushButton:pressed {{ background:{C['amber']}99; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:transparent; color:{C['amber']};
                        border:1px solid {C['amber']}; border-radius:10px;
                        padding:0 9px; font-size:11px;
                    }}
                    QPushButton:hover {{ background:{C['amber']}33; }}
                    QPushButton:pressed {{ background:{C['amber']}55; }}
                """)
            btn.clicked.connect(lambda _c, g=grp: self._on_chip(g))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, g=grp, b=btn: self._on_chip_context(g, b.mapToGlobal(pos)))
            self._chips.addWidget(btn)

        self._chips.addStretch()

    def _on_chip_context(self, group_name, global_pos):
        """Right-click on a chip -> option to delete the group entirely."""
        menu = QMenu(self)
        del_action = menu.addAction(f'Delete group  \u201c{group_name}\u201d')
        del_action.setIcon(self.style().standardIcon(
            self.style().StandardPixmap.SP_TrashIcon))
        if menu.exec(global_pos) == del_action:
            self.group_deleted.emit(group_name)

    def _on_chip(self, group_name):
        if not self._snapshot:
            return
        current = (self._snapshot.cue_group or "").strip()
        new_group = "" if current == group_name else group_name
        self._snapshot.cue_group = new_group
        self._rebuild()
        self.group_changed.emit(new_group)

    def _on_add(self):
        name, ok = QInputDialog.getText(self, "New Group", "Group name:")
        if not ok or not name.strip():
            return
        gn = name.strip()
        if gn not in self._groups:
            self._groups.append(gn)
            self.group_added.emit(gn)
        if self._snapshot:
            self._snapshot.cue_group = gn
            self._rebuild()
            self.group_changed.emit(gn)


class SnapshotDetailPanel(QWidget):
    snapshot_updated = pyqtSignal()
    capture_pressed  = pyqtSignal()
    recall_pressed   = pyqtSignal()
    delete_pressed   = pyqtSignal()
    group_added      = pyqtSignal(str)
    group_deleted    = pyqtSignal(str)

    def __init__(self, show):
        super().__init__(); self.show = show; self.current_snapshot = None
        self._groups = []
        self._build()

    def _build(self):
        l = QVBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(0)
        hdr = QWidget(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background:{C['bg3']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,0,10,0)
        t = QLabel("SNAPSHOT DETAILS")
        t.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:0.1em;")
        hl.addWidget(t); l.addWidget(hdr)

        content = QWidget(); cl = QVBoxLayout(content)
        cl.setContentsMargins(14,10,14,10); cl.setSpacing(8)

        name_row = QHBoxLayout()
        self.num_lbl = QLabel("--")
        self.num_lbl.setStyleSheet(
            f"color:{C['text3']};font-size:22px;font-weight:bold;min-width:52px;")
        name_row.addWidget(self.num_lbl)
        self.name_edit = QLineEdit(); self.name_edit.setPlaceholderText("Snapshot name...")
        self.name_edit.setStyleSheet("font-size:15px;font-weight:bold;")
        self.name_edit.textChanged.connect(self._on_name); name_row.addWidget(self.name_edit)
        cl.addLayout(name_row)

        notes_row = QHBoxLayout()
        notes_row.addWidget(QLabel("Notes:"))
        self.notes_edit = QLineEdit()
        self.notes_edit.setPlaceholderText("Optional note for this cue...")
        self.notes_edit.textChanged.connect(self._on_notes)
        notes_row.addWidget(self.notes_edit)
        cl.addLayout(notes_row)

        # Group tag widget -- chip-based, no text field
        self.group_tags = GroupTagsWidget()
        self.group_tags.group_changed.connect(self._on_group_changed)
        self.group_tags.group_added.connect(self.group_added.emit)
        self.group_tags.group_deleted.connect(self.group_deleted.emit)
        cl.addWidget(self.group_tags)

        btn_row = QHBoxLayout()
        self.capture_btn = QPushButton("⬇  Update from Wing")
        self.capture_btn.setObjectName("green_btn"); self.capture_btn.clicked.connect(self.capture_pressed.emit)
        btn_row.addWidget(self.capture_btn)
        self.recall_btn = QPushButton("⬆  Recall to Wing")
        self.recall_btn.clicked.connect(self.recall_pressed.emit); btn_row.addWidget(self.recall_btn)
        self.delete_btn = QPushButton("Delete"); self.delete_btn.setObjectName("danger_btn")
        self.delete_btn.clicked.connect(self.delete_pressed.emit)
        btn_row.addWidget(self.delete_btn); cl.addLayout(btn_row)

        self.scope_widget = RecallScopeWidget(self.show)
        # scope_changed is NOT connected to snapshot_updated to prevent
        # the dangerous chain: scope_changed -> _refresh_cue_list -> populate ->
        # setCurrentRow -> _on_cue_selected -> load_snapshot -> _rebuild
        # which causes a fatal PyQt6 exception in Python 3.14.
        # Name/group changes already emit snapshot_updated directly from their own handlers.
        cl.addWidget(self.scope_widget)
        l.addWidget(content)

        self.empty_lbl = QLabel("Select a cue from the list")
        self.empty_lbl.setStyleSheet(f"color:{C['text3']};font-size:14px;")
        self.empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(self.empty_lbl)
        self._set_enabled(False)

    def set_groups(self, groups):
        """Update the available group chips (call from MainWindow after any group change)."""
        self._groups = list(groups)
        if self.current_snapshot:
            self.group_tags.load(self.current_snapshot, self._groups)

    def _set_enabled(self, e):
        for w in [self.name_edit, self.notes_edit, self.group_tags,
                  self.capture_btn, self.recall_btn, self.delete_btn, self.scope_widget]:
            w.setEnabled(e)
        self.empty_lbl.setVisible(not e)

    def load_snapshot(self, snap):
        self.current_snapshot = snap
        if not snap:
            self._set_enabled(False)
            self.scope_widget.load_snapshot(None)
            return
        self._set_enabled(True)
        self.num_lbl.setText(f"{snap.number:03d}")
        for w, v in [(self.name_edit, snap.name), (self.notes_edit, snap.notes)]:
            w.blockSignals(True); w.setText(v); w.blockSignals(False)
        self.group_tags.load(snap, self._groups)
        self.scope_widget.load_snapshot(snap)

    def load_multi(self, count):
        """Called when selection changes. Only blanks panel for true multi-select (>1)."""
        if count > 1:
            self._set_enabled(False)
            self.scope_widget.load_snapshot(None)
            self.empty_lbl.setText(f"{count} cues selected")
            self.empty_lbl.setVisible(True)
        # count == 0 or 1: do nothing -- let cue_selected / load_snapshot handle it

    def _on_name(self, t):
        if self.current_snapshot: self.current_snapshot.name = t; self.snapshot_updated.emit()
    def _on_group_changed(self, group_name):
        # Group was changed via the chip widget (snapshot already updated in-place).
        # Just trigger a cue list refresh so the group header updates.
        QTimer.singleShot(0, self.snapshot_updated.emit)
    def _on_notes(self, t):
        if self.current_snapshot: self.current_snapshot.notes = t


# ─── Sections & Auto-Update Panel ────────────────────────────────────────────

class SectionsPanel(QWidget):
    sections_changed = pyqtSignal()

    def __init__(self, show):
        super().__init__(); self.show = show; self.current_idx = -1; self._build()

    def _build(self):
        l = QHBoxLayout(self); l.setContentsMargins(0,0,0,0); l.setSpacing(0)

        # Left sidebar
        left = QWidget(); left.setFixedWidth(210)
        left.setStyleSheet(f"background:{C['bg']};border-right:1px solid {C['border']};")
        ll = QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        hdr = QWidget(); hdr.setFixedHeight(36)
        hdr.setStyleSheet(f"background:{C['bg3']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,0,8,0)
        lbl = QLabel("SECTIONS")
        lbl.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:0.1em;")
        hl.addWidget(lbl); hl.addStretch()
        add = QPushButton("Add Section"); add.setFixedHeight(24); add.setMinimumWidth(90)
        add.setStyleSheet("font-size:11px;"); add.clicked.connect(self._add_section)
        hl.addWidget(add); ll.addWidget(hdr)
        self.sec_list = QListWidget(); self.sec_list.currentRowChanged.connect(self._on_section)
        ll.addWidget(self.sec_list)
        no_sec = QWidget(); no_sec.setFixedHeight(44)
        no_sec.setStyleSheet(f"border-top:1px solid {C['border']};")
        nsl = QHBoxLayout(no_sec); nsl.setContentsMargins(10,0,10,0)
        nsl_lbl = QLabel("No sections ->\nAU writes nothing")
        nsl_lbl.setStyleSheet(f"color:{C['text3']};font-size:11px;"); nsl.addWidget(nsl_lbl)
        ll.addWidget(no_sec); l.addWidget(left)

        # Right content
        rs = QScrollArea(); rs.setWidgetResizable(True)
        rs.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right = QWidget(); rl = QVBoxLayout(right)
        rl.setContentsMargins(20,16,20,16); rl.setSpacing(14)

        nr = QHBoxLayout()
        self.name_edit = QLineEdit(); self.name_edit.setPlaceholderText("Section name...")
        self.name_edit.setStyleSheet("font-size:15px;font-weight:bold;")
        self.name_edit.textChanged.connect(self._on_name); nr.addWidget(self.name_edit)
        del_btn = QPushButton("Delete Section"); del_btn.setObjectName("danger_btn")
        del_btn.clicked.connect(self._delete_section); nr.addWidget(del_btn)
        rl.addLayout(nr)

        excl_grp = QGroupBox("AUTO-UPDATE EXCLUSIONS  --  where are changes written?")
        excl_l = QVBoxLayout(excl_grp)
        self.excl_table = QTableWidget(len(AU_PARAMS), 3)
        self.excl_table.setHorizontalHeaderLabels(
            ["Current Snapshot", "Current Group", "All Snapshots"])
        self.excl_table.setVerticalHeaderLabels([lbl for _,lbl in AU_PARAMS])
        self.excl_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        _ROW_H = 26
        self.excl_table.verticalHeader().setDefaultSectionSize(_ROW_H)
        self.excl_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.excl_table.setMinimumHeight(len(AU_PARAMS) * _ROW_H + 32)
        self.excl_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.excl_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.excl_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.excl_table.cellClicked.connect(self._on_excl_click)
        excl_l.addWidget(self.excl_table)
        excl_grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hint = QLabel(
            "Parameters set to 'Current Snapshot' only change the active cue (like a DiGiCo exclusion).\n"
            "'Current Group' writes to all snapshots in the same cue group -- "
            "if the active snapshot has no group, it falls back to 'Current Snapshot' behaviour.\n"
            "'All Snapshots' propagates through the entire show file.")
        hint.setStyleSheet(f"color:{C['text3']};font-size:11px;"); hint.setWordWrap(True)
        excl_l.addWidget(hint); rl.addWidget(excl_grp, stretch=1)

        ch_grp = QGroupBox("CHANNEL ASSIGNMENT  --  click to add / remove from this section")
        ch_l = QVBoxLayout(ch_grp)
        ch_tabs = QTabWidget()
        ch_tabs.setStyleSheet("QTabBar::tab{padding:4px 10px;font-size:11px;}")
        self._sel_btns = []
        self._ch_tabs  = ch_tabs   # store reference for _set_right_enabled

        # Select All / Select None -- live corner of the tab widget,
        # always affects whichever tab is currently visible
        corner = QWidget()
        cr = QHBoxLayout(corner); cr.setContentsMargins(4,2,4,2); cr.setSpacing(4)
        sel_all  = QPushButton("Select All")
        sel_none = QPushButton("Select None")
        for b in (sel_all, sel_none):
            b.setFixedHeight(22)
            b.setStyleSheet("font-size:11px;padding:0 8px;")
            self._sel_btns.append(b)
        cr.addWidget(sel_all); cr.addWidget(sel_none)
        ch_tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        self._ch_tabs_btns = []   # [(key_list, btn_list)] per tab -- for corner buttons
        self.ch_btns_input  = self._ch_grid(ch_tabs, "Inputs (1–48)", 48, "input_",  16)
        self.ch_btns_bus    = self._ch_grid(ch_tabs, "Buses (1–16)",  16, "bus_",     8)
        self.ch_btns_matrix = self._ch_grid(ch_tabs, "Matrix (1–8)",   8, "matrix_",  8)
        self.ch_btns_mains  = self._ch_grid(ch_tabs, "Mains (1–4)",    4, "main_",    4)
        self.ch_btns_dca    = self._ch_grid(ch_tabs, "DCAs (1–16)",   16, "dca_",     8)
        self.ch_btns_fx     = self._ch_grid(ch_tabs, "FX Racks (1–16)", 16, "fx_",   8)
        # Wire corner buttons to act on whichever tab is currently visible
        def _sel_current(enabled):
            tab_idx = self._ch_tabs.currentIndex()
            if 0 <= tab_idx < len(self._ch_tabs_btns):
                for k, _ in self._ch_tabs_btns[tab_idx]:
                    self._set_ch(k, enabled)
        sel_all.clicked.connect(lambda: _sel_current(True))
        sel_none.clicked.connect(lambda: _sel_current(False))

        ch_l.addWidget(ch_tabs)
        ch_grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rl.addWidget(ch_grp, stretch=0)
        rs.setWidget(right); l.addWidget(rs)

        self._refresh_list(); self._set_right_enabled(False)

    def _ch_grid(self, tabs, label, count, prefix, cols):
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        grid_w = QWidget(); g = QGridLayout(grid_w)
        g.setSpacing(4); g.setContentsMargins(0, 0, 0, 0)
        btns = []
        for i in range(count):
            key = f"{prefix}{i+1:02d}"; num = i+1
            btn = QPushButton(f"{num:02d}"); btn.setCheckable(True)
            btn.setFixedSize(40,26); btn.setStyleSheet("font-size:11px;padding:0;")
            btn.clicked.connect(lambda _,k=key: self._toggle_ch(k))
            btns.append((key,btn)); g.addWidget(btn, i//cols, i%cols)
        outer.addWidget(grid_w)

        # Register in _ch_tabs_btns so corner Select All/None can target this tab
        self._ch_tabs_btns.append(btns)

        tabs.addTab(tab, label); return btns

    def _set_right_enabled(self, e):
        self.name_edit.setEnabled(e); self.excl_table.setEnabled(e)
        if not e:
            self.excl_table.clearContents()
            self.excl_table.clearSelection()
        self._ch_tabs.setEnabled(e)
        for b in getattr(self, '_sel_btns', []):
            b.setEnabled(e)
        for lst in [self.ch_btns_input, self.ch_btns_bus, self.ch_btns_matrix,
                    self.ch_btns_mains, self.ch_btns_dca, self.ch_btns_fx]:
            for _,btn in lst: btn.setEnabled(e)

    def _refresh_list(self):
        self.sec_list.clear()
        for sec in self.show.sections:
            item = QListWidgetItem(sec.name); item.setForeground(QColor(sec.color))
            self.sec_list.addItem(item)

    def _on_section(self, idx):
        if idx < 0 or idx >= len(self.show.sections):
            self._set_right_enabled(False); return
        self.current_idx = idx; sec = self.show.sections[idx]
        self._set_right_enabled(True)
        self.name_edit.blockSignals(True); self.name_edit.setText(sec.name)
        self.name_edit.blockSignals(False)
        self._refresh_excl(sec); self._refresh_chs(sec)

    def _refresh_excl(self, sec):
        self.excl_table.clearContents()
        for row,(key,_) in enumerate(AU_PARAMS):
            state = sec.exclusions.get(key, "snap")
            for col, col_state in enumerate(AU_STATES):
                is_on = (state == col_state)
                cell = QLabel(" ✓ " if is_on else "")
                cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setStyleSheet(
                    f"background:{C['green_bg']};color:{C['green']};"
                    f"font-size:16px;font-weight:bold;border-radius:3px;" if is_on else
                    f"background:{C['bg3']};color:{C['text3']};border-radius:3px;")
                self.excl_table.setCellWidget(row,col,cell)


    def _refresh_chs(self, sec):
        for lst in [self.ch_btns_input, self.ch_btns_bus, self.ch_btns_matrix,
                    self.ch_btns_mains, self.ch_btns_dca, self.ch_btns_fx]:
            for key,btn in lst:
                in_sec = key in sec.channels; btn.setChecked(in_sec)
                btn.setStyleSheet(
                    f"font-size:11px;padding:0;background:{C['green_bg']};"
                    f"color:{C['green']};border:1px solid {C['green_border']};border-radius:4px;"
                    if in_sec else "font-size:11px;padding:0;")

    def _on_excl_click(self,row,col):
        if self.current_idx < 0: return
        key = AU_PARAMS[row][0]
        self.show.sections[self.current_idx].exclusions[key] = AU_STATES[col]
        self._refresh_excl(self.show.sections[self.current_idx])
        self.sections_changed.emit()

        self._refresh_excl(self.show.sections[self.current_idx])
        self.sections_changed.emit()

    def _on_name(self,t):
        if self.current_idx >= 0:
            self.show.sections[self.current_idx].name = t
            self._refresh_list(); self.sec_list.setCurrentRow(self.current_idx)
            self.sections_changed.emit()

    def _toggle_ch(self,key):
        if self.current_idx < 0: return
        sec = self.show.sections[self.current_idx]
        if key in sec.channels: sec.channels.remove(key)
        else: sec.channels.append(key)
        self._refresh_chs(sec); self.sections_changed.emit()

    def _set_ch(self, key, enabled):
        """Add or remove a channel from the current section (used by Select All/None)."""
        if self.current_idx < 0: return
        sec = self.show.sections[self.current_idx]
        if enabled and key not in sec.channels:
            sec.channels.append(key)
        elif not enabled and key in sec.channels:
            sec.channels.remove(key)
        self._refresh_chs(sec); self.sections_changed.emit()

    def _add_section(self):
        name,ok = QInputDialog.getText(self,"New Section","Section name:")
        if ok and name.strip():
            color = SECTION_COLORS[len(self.show.sections)%len(SECTION_COLORS)]
            self.show.sections.append(Section(name.strip(),color))
            self._refresh_list(); self.sec_list.setCurrentRow(len(self.show.sections)-1)
            self.sections_changed.emit()

    def _delete_section(self):
        if self.current_idx < 0: return
        name = self.show.sections[self.current_idx].name
        if QMessageBox.question(self,"Delete Section",f"Delete '{name}'?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.show.sections.pop(self.current_idx); self.current_idx = -1
            self._refresh_list()
            self._set_right_enabled(False)
            self.name_edit.blockSignals(True); self.name_edit.clear(); self.name_edit.blockSignals(False)
            self.excl_table.clearContents()
            self.sections_changed.emit()

    def refresh(self):
        prev_row = self.sec_list.currentRow()
        self._refresh_list()
        # _refresh_list() clears and rebuilds the list, which loses the
        # selection every time -- including right after loading a show file.
        # With nothing selected, _get_active_section() silently returns None
        # and Auto Update falls back to 'snap' mode for every parameter type,
        # ignoring any configured group/all write-mode AND any channel
        # restriction entirely (that check is skipped when section is None).
        # Restore the previous selection if still valid, otherwise default
        # to the first section so AU always has a well-defined active section
        # instead of silently losing custom exclusions/channel restrictions.
        if self.sec_list.count() > 0:
            row = prev_row if 0 <= prev_row < self.sec_list.count() else 0
            self.sec_list.setCurrentRow(row)


# ─── Main Window ──────────────────────────────────────────────────────────────


# ─── OSC Settings Panel ───────────────────────────────────────────────────────

class OscSettingsPanel(QWidget):
    """
    Configure external OSC output endpoints.
    Per-snapshot messages are configured in the 'OSC Messages' tab within Recall Scope.
    """
    changed              = pyqtSignal()
    tcp_toggle_requested = pyqtSignal(int)

    def __init__(self, show):
        super().__init__()
        self.show = show
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        hdr = QLabel("OSC OUTPUT ENDPOINTS")
        hdr.setStyleSheet(f"color:{C['text3']};font-size:10px;letter-spacing:0.1em;")
        layout.addWidget(hdr)

        hint = QLabel(
            "Add OSC targets here. When a snapshot is recalled, all OSC messages defined "
            "for that snapshot (see 'OSC Messages' tab in Recall Scope) are sent to every "
            "enabled endpoint below.")
        hint.setStyleSheet(f"color:{C['text3']};font-size:12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "IP Address", "Port", "Via (interface)", "Enabled"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setDefaultSectionSize(80)
        self.table.horizontalHeader().resizeSection(4, 64)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Endpoint")
        add_btn.setObjectName("green_btn")
        add_btn.clicked.connect(self._add)
        btn_row.addWidget(add_btn)
        del_btn = QPushButton("Remove Selected")
        del_btn.setObjectName("danger_btn")
        del_btn.clicked.connect(self._remove)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        # ── OSC Remote Control (incoming) ──────────────────────────────────
        rc_grp = QGroupBox("REMOTE CONTROL  --  incoming OSC to control Wing Theatre")
        rc_grp.setStyleSheet(f"QGroupBox {{ font-size:10px; letter-spacing:0.08em; "
                             f"color:{C['text3']}; border:1px solid {C['border']}; "
                             f"border-radius:6px; margin-top:8px; padding-top:8px; }}")
        rc_l = QVBoxLayout(rc_grp)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Listen port:"))
        self.rc_port = QSpinBox()
        self.rc_port.setRange(1024, 65535); self.rc_port.setValue(8765)
        self.rc_port.setFixedWidth(80)
        self.rc_port.lineEdit().setReadOnly(True)
        port_row.addWidget(self.rc_port)

        self.rc_toggle_btn = QPushButton("Off")
        self.rc_toggle_btn.setFixedHeight(26); self.rc_toggle_btn.setFixedWidth(90)
        self._rc_set_btn_off()
        self.rc_toggle_btn.clicked.connect(self._rc_toggle)
        port_row.addWidget(self.rc_toggle_btn)
        port_row.addStretch()
        rc_l.addLayout(port_row)

        self.rc_status = QLabel("● Stopped")
        self.rc_status.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        rc_l.addWidget(self.rc_status)

        cmds = QLabel(
            "Commands:\n"
            "  /wingtheatre/go                          -- fire GO (plays current cue)\n"
            "  /wingtheatre/previous/go                 -- play cue before last-fired\n"
            "  /wingtheatre/next/go                     -- play cue after last-fired\n"
            "  /wingtheatre/previous                    -- move selection up (no play)\n"
            "  /wingtheatre/next                        -- move selection down (no play)\n"
            "  /wingtheatre/snap/go  <number or name>   -- recall specific snapshot\n"
            "  /wingtheatre/store                       -- Store from Wing\n"
            "  /wingtheatre/autoupdate/on  |  /off       -- toggle Auto Update\n"
            "  /wingtheatre/addsnap  [name]              -- add new snapshot (optional name)")
        cmds.setStyleSheet(
            f"color:{C['text3']};font-size:11px;font-family:'Courier New',monospace;"
            f"background:{C['bg']};border:1px solid {C['border']};"
            f"border-radius:4px;padding:8px;")
        rc_l.addWidget(cmds)
        layout.addWidget(rc_grp)

        # ── TCP Companion Remote Control ─────────────────────────────────────────
        tcp_grp = QGroupBox("COMPANION / TCP REMOTE CONTROL  --  single client with feedback")
        tcp_grp.setStyleSheet(f"QGroupBox {{ font-size:10px; letter-spacing:0.08em; "
                             f"color:{C['text3']}; border:1px solid {C['border']}; "
                             f"border-radius:6px; margin-top:8px; padding-top:8px; }}")
        tcp_l = QVBoxLayout(tcp_grp)

        tcp_port_row = QHBoxLayout()
        tcp_port_row.addWidget(QLabel("Listen port:"))
        self.tcp_port = QSpinBox()
        self.tcp_port.setRange(1024, 65535); self.tcp_port.setValue(9001)
        self.tcp_port.setFixedWidth(80)
        tcp_port_row.addWidget(self.tcp_port)
        self.tcp_toggle_btn = QPushButton("Off")
        self.tcp_toggle_btn.setFixedHeight(26); self.tcp_toggle_btn.setFixedWidth(90)
        self.tcp_toggle_btn.setStyleSheet(
            f"background:{C['bg3']};color:{C['text3']};border:1px solid {C['border']};"
            f"border-radius:4px;padding:3px 8px;")
        self.tcp_toggle_btn.clicked.connect(
            lambda: self.tcp_toggle_requested.emit(self.tcp_port.value()))
        tcp_port_row.addWidget(self.tcp_toggle_btn)
        tcp_port_row.addStretch()
        tcp_l.addLayout(tcp_port_row)

        self.tcp_status = QLabel("● Stopped")
        self.tcp_status.setStyleSheet(f"color:{C['text3']};font-size:11px;")
        tcp_l.addWidget(self.tcp_status)

        tcp_hint = QLabel(
            "Commands (TCP, newline-delimited):\n"
            "  GO / NEXT_GO / PREV_GO  /  SNAP_GO <n|name>\n"
            "  AU_ON / AU_OFF / AU_TOGGLE  /  ADD_SNAP [name]  /  GET_STATE\n"
            "Feedback sent on change:\n"
            "  STATE current_cue_num=001  /  current_cue_name=Scene 1\n"
            "  STATE next_cue_num=002  /  autoupdate=true  /  wing_connected=true")
        tcp_hint.setStyleSheet(
            f"color:{C['text3']};font-size:11px;font-family:'Courier New',monospace;"
            f"background:{C['bg']};border:1px solid {C['border']};"
            f"border-radius:4px;padding:6px;")
        tcp_l.addWidget(tcp_hint)
        layout.addWidget(tcp_grp)

        self.refresh()

    def tcp_set_running(self, running: bool, client_addr: str = ""):
        if not hasattr(self, 'tcp_status'): return
        if running:
            self.tcp_toggle_btn.setText("On")
            self.tcp_toggle_btn.setStyleSheet(
                f"background:#1a6b3a;color:#7fff9a;border:1px solid #2a9b5a;"
                f"border-radius:4px;padding:3px 8px;")
            if client_addr:
                self.tcp_status.setText(f"● Connected: {client_addr}")
                self.tcp_status.setStyleSheet("color:#7fff9a;font-size:11px;")
            else:
                self.tcp_status.setText(f"● Listening on port {self.tcp_port.value()}")
                self.tcp_status.setStyleSheet("color:#aaffaa;font-size:11px;")
        else:
            self.tcp_toggle_btn.setText("Off")
            self.tcp_toggle_btn.setStyleSheet(
                f"background:#1e2a2e;color:#7a9aaa;border:1px solid #2a4a5a;"
                f"border-radius:4px;padding:3px 8px;")
            self.tcp_status.setText("● Stopped")
            self.tcp_status.setStyleSheet("color:#7a9aaa;font-size:11px;")

    def _connect_table(self):
        try: self.table.itemChanged.disconnect()
        except Exception: pass
        self.table.itemChanged.connect(self._on_changed)

    def _populate(self):
        try: self.table.itemChanged.disconnect()
        except Exception: pass
        self.table.setRowCount(0)
        for ep in self.show.osc_outputs:
            try:
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(ep.name)))
                self.table.setItem(r, 1, QTableWidgetItem(str(ep.ip)))
                self.table.setItem(r, 2, QTableWidgetItem(str(ep.port)))
                # Via interface dropdown
                via_cb = QComboBox()
                via_cb.setStyleSheet(f"background:{C['bg3']};color:{C['text']};")
                self._fill_iface_combo(via_cb, ep.bind_ip or "")
                via_cb.currentIndexChanged.connect(
                    lambda _, row=r, cb=via_cb: self._on_via_changed(row, cb))
                self.table.setCellWidget(r, 3, via_cb)
                en = QTableWidgetItem()
                en.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                en.setCheckState(Qt.CheckState.Checked if ep.enabled else Qt.CheckState.Unchecked)
                self.table.setItem(r, 4, en)
            except Exception:
                import traceback; traceback.print_exc()
        self._connect_table()

    def refresh(self):
        try:
            self._populate()
        except Exception:
            import traceback; traceback.print_exc()

    def _on_changed(self, item):
        try:
            if item is None: return
            r = item.row()
            if r < 0 or r >= len(self.show.osc_outputs): return
            ep = self.show.osc_outputs[r]
            col = item.column()
            if   col == 0: ep.name    = item.text()
            elif col == 1: ep.ip      = item.text()
            elif col == 2:
                try:   ep.port = int(item.text())
                except ValueError: pass
            elif col == 3: pass  # handled by _on_via_changed (QComboBox)
            elif col == 4:
                cs = item.checkState()
                ep.enabled = (cs == Qt.CheckState.Checked or
                              getattr(cs, 'value', cs) == 2)
        except Exception:
            import traceback; traceback.print_exc()

    def _get_interfaces(self):
        """Return list of (label, ip) for all available IPv4 interfaces."""
        ifaces = [("Auto (0.0.0.0)", "")]
        try:
            from PyQt6.QtNetwork import QNetworkInterface
            for iface in QNetworkInterface.allInterfaces():
                for entry in iface.addressEntries():
                    ip = entry.ip().toString()
                    if '.' in ip and not ip.startswith('127.'):
                        name = iface.humanReadableName()
                        ifaces.append((f"{ip}  ({name})", ip))
        except Exception:
            pass
        return ifaces

    def _fill_iface_combo(self, combo, current_ip=""):
        """Populate a QComboBox with available interfaces."""
        combo.blockSignals(True)
        combo.clear()
        for label, ip in self._get_interfaces():
            combo.addItem(label, ip)
        # Select matching IP
        if current_ip:
            for i in range(combo.count()):
                if combo.itemData(i) == current_ip:
                    combo.setCurrentIndex(i)
                    break
        combo.blockSignals(False)

    def _on_via_changed(self, row, combo):
        """Update endpoint bind_ip when interface dropdown changes."""
        if row < 0 or row >= len(self.show.osc_outputs):
            return
        self.show.osc_outputs[row].bind_ip = combo.currentData() or ""
        self.changed.emit()

    def refresh_interfaces(self):
        """Refresh all interface dropdowns — called when Wing interfaces are refreshed."""
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 3)
            if cb and isinstance(cb, QComboBox) and r < len(self.show.osc_outputs):
                self._fill_iface_combo(cb, self.show.osc_outputs[r].bind_ip or "")

    def _add(self):
        try:
            if len(self.show.osc_outputs) >= 10:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Max Endpoints", "Maximum 10 OSC endpoints allowed.")
                return
            self.show.osc_outputs.append(OscOutput(f"Output {len(self.show.osc_outputs)+1}"))
            self._populate()
            self.changed.emit()
        except Exception:
            import traceback; traceback.print_exc()

    def _remove(self):
        try:
            r = self.table.currentRow()
            if 0 <= r < len(self.show.osc_outputs):
                self.show.osc_outputs.pop(r)
                self._populate()
                self.changed.emit()
        except Exception:
            import traceback; traceback.print_exc()

    def set_osc_server(self, server: 'OscServer'):
        self._osc_server = server
        server.status_changed.connect(self._rc_on_status)

    def _rc_set_btn_off(self):
        self.rc_toggle_btn.setText("Off")
        self.rc_toggle_btn.setStyleSheet(
            f"background:{C['bg3']};color:{C['text3']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:12px;")

    def _rc_set_btn_on(self, port):
        self.rc_toggle_btn.setText(f"On  :{port}")
        self.rc_toggle_btn.setStyleSheet(
            f"background:{C['green_bg']};color:{C['green']};"
            f"border:1px solid {C['green_border']};border-radius:4px;font-size:12px;font-weight:bold;")

    def _rc_toggle(self):
        if not hasattr(self, '_osc_server'): return
        if self._osc_server.is_running():
            self._osc_server.stop()
        else:
            self._osc_server.start(self.rc_port.value())

    def _rc_on_status(self, running: bool, port: int):
        if running:
            self.rc_status.setText(f"● Listening on 0.0.0.0:{port}")
            self.rc_status.setStyleSheet(f"color:{C['green']};font-size:11px;")
            self._rc_set_btn_on(port)
            self.rc_port.setEnabled(False)
        else:
            self.rc_status.setText("● Stopped")
            self.rc_status.setStyleSheet(f"color:{C['text3']};font-size:11px;")
            self._rc_set_btn_off()
            self.rc_port.setEnabled(True)

class OscServer(QObject):
    """
    Incoming UDP/OSC server that lets external devices remote-control Wing Theatre.

    Runs python-osc's ThreadingOSCUDPServer in a daemon thread so it never blocks
    the Qt event loop. All handlers emit Qt signals so work always lands on the
    main thread (thread-safe).

    Supported commands
    ------------------
    /wingtheatre/snap/go  <number|name>   recall snapshot by 3-digit number or name
    /wingtheatre/previous/go              go to previous snapshot
    /wingtheatre/next/go                  go to next snapshot
    /wingtheatre/store                    trigger Store from Wing
    /wingtheatre/autoupdate/on            enable Auto Update
    /wingtheatre/autoupdate/off           disable Auto Update
    """

    snap_go         = pyqtSignal(object)
    go              = pyqtSignal()
    prev_go         = pyqtSignal()
    next_go         = pyqtSignal()
    prev_nav        = pyqtSignal()
    next_nav        = pyqtSignal()
    store_triggered = pyqtSignal()
    autoupdate_set  = pyqtSignal(bool)
    addsnap         = pyqtSignal(str)   # /wingtheatre/addsnap [name]
    status_changed  = pyqtSignal(bool, int)
    log             = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._server = None
        self._thread = None

    def start(self, port: int):
        self.stop()
        try:
            from pythonosc.dispatcher import Dispatcher
            try:
                from pythonosc.osc_server import ThreadingOSCUDPServer   # python-osc >= 1.7
            except ImportError:
                from pythonosc.server import ThreadingOSCUDPServer        # older versions

            d = Dispatcher()
            d.map("/wingtheatre/snap/go",        self._h_snap)
            d.map("/wingtheatre/go",             self._h_go)
            d.map("/wingtheatre/previous/go",    self._h_prev_go)
            d.map("/wingtheatre/next/go",        self._h_next_go)
            d.map("/wingtheatre/previous",       self._h_prev_nav)
            d.map("/wingtheatre/next",           self._h_next_nav)
            d.map("/wingtheatre/store",          self._h_store)
            d.map("/wingtheatre/autoupdate/on",  self._h_au_on)
            d.map("/wingtheatre/autoupdate/off", self._h_au_off)
            d.map("/wingtheatre/addsnap",        self._h_addsnap)

            self._server = ThreadingOSCUDPServer(("0.0.0.0", port), d)
            self._thread = threading.Thread(
                target=self._server.serve_forever, daemon=True)
            self._thread.start()
            self.status_changed.emit(True, port)
            self.log.emit(f"OSC remote: listening on 0.0.0.0:{port}")
        except Exception as e:
            self.log.emit(f"OSC remote failed to start: {e}")
            self.status_changed.emit(False, 0)

    def stop(self):
        if self._server:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
        self._thread = None
        self.status_changed.emit(False, 0)

    def is_running(self) -> bool:
        return self._server is not None

    # ── OSC handlers (run in OSC thread -> always emit signals, never touch Qt directly) ──

    def _h_snap(self, address, *args):
        if args: self.snap_go.emit(args[0])

    def _h_go(self, address, *args):
        self.go.emit()

    def _h_prev_go(self, address, *args):
        self.prev_go.emit()

    def _h_next_go(self, address, *args):
        self.next_go.emit()

    def _h_prev_nav(self, address, *args):
        self.prev_nav.emit()

    def _h_next_nav(self, address, *args):
        self.next_nav.emit()

    def _h_store(self, address, *args):
        self.store_triggered.emit()

    def _h_au_on(self, address, *args):
        self.autoupdate_set.emit(True)

    def _h_au_off(self, address, *args):
        self.autoupdate_set.emit(False)

    def _h_addsnap(self, address, *args):
        """Add a new snapshot. Optional string arg = name."""
        name = str(args[0]) if args and args[0] else ""
        self.addsnap.emit(name)


def _get_version():
    """Read version from version.txt (written by GitHub Actions) or return default."""
    import os
    # Check next to executable (PyInstaller) or script
    for base in [
        os.path.dirname(os.path.abspath(
            __import__('sys').executable if getattr(__import__('sys'), 'frozen', False)
            else __file__)),
        getattr(__import__('sys'), '_MEIPASS', None),
    ]:
        if base:
            p = os.path.join(base, 'version.txt')
            if os.path.exists(p):
                try: return open(p).read().strip()
                except: pass
    return "dev"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Wing Theatre Controller")
        self.setFixedSize(420, 320)
        self.setStyleSheet(f"background:{C['bg2']};color:{C['text']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(10)

        # Title
        title = QLabel("Wing Theatre Controller")
        title.setStyleSheet(f"font-size:18px;font-weight:bold;color:{C['text']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version = _get_version()
        ver_lbl = QLabel(f"Version {version}")
        ver_lbl.setStyleSheet(f"font-size:13px;color:{C['text3']};")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_lbl)

        layout.addSpacing(8)

        # Description
        desc = QLabel("Professional show-control software\nfor Behringer Wing mixer.")
        desc.setStyleSheet(f"font-size:12px;color:{C['text2']};")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addSpacing(8)

        # Credits
        credits = QLabel(
            "<b>Developers:</b><br>"
            "Mikkel Peter Larsen &amp; Claude (Anthropic)<br><br>"
            "<b>Credits:</b><br>"
            "wingmon built on <i>libwing</i> by dannyfiresnake<br>"
            "Protocol documentation by Patrick-Gilles Maillot<br>"
            "python-osc by attwad · PyQt6 by Riverbank Computing"
        )
        credits.setStyleSheet(f"font-size:11px;color:{C['text3']};")
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(credits)

        layout.addSpacing(8)

        # GitHub link
        link = QLabel('<a href="https://github.com/mikk3722/wing-theatre-controller" '
                     f'style="color:{C["green"]};">github.com/mikk3722/wing-theatre-controller</a>')
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(link)

        layout.addStretch()

        # Close button
        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.show_file = ShowFile(); self.osc = WingOSC()
        self.osc_server  = OscServer()             # incoming OSC remote control
        self.tcp_server  = RemoteTCPServer(self)    # Companion TCP feedback server
        self.active_cue_index = -1
        self._dirty = False
        self._autosave_timer = QTimer()
        self._autosave_timer.timeout.connect(self._autosave)
        # Persistent diagnostic log -- every status-bar message (connection
        # events, sync progress, propmap misses, model changes etc.) also
        # gets written here with a timestamp, so it can be captured and sent
        # for debugging without needing to watch the status bar live.
        base = os.path.dirname(os.path.abspath(
            sys.executable if getattr(sys, 'frozen', False) else __file__))
        self._log_file_path = os.path.join(base, 'wing_theatre_log.txt')
        try:
            with open(self._log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n=== Session started {datetime.datetime.now().isoformat()} ===\n")
        except Exception:
            pass
        self._setup_ui(); self._connect_signals(); self._new_show()
        # Wire OscServer to settings panel so Start/Stop buttons work
        self.osc_settings_panel.set_osc_server(self.osc_server)

    def _log_to_file(self, msg):
        """Append a timestamped line to wing_theatre_log.txt next to the
        app. Same file location/pattern as crash_log.txt, so both are easy
        to find together. Silently does nothing if the file can't be
        written (e.g. read-only install location) -- this must never be
        the reason something else breaks."""
        try:
            with open(self._log_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}  {msg}\n")
        except Exception:
            pass

    def eventFilter(self, obj, event):
        """Block mouse interaction on the autosave spinbox text field."""
        if obj is getattr(self, '_autosave_spin', None) and hasattr(self, '_autosave_spin'):
            obj = None  # not the spinbox itself
        if (hasattr(self, '_autosave_spin')
                and obj is self._autosave_spin.lineEdit()
                and event.type() in (
                    QEvent.Type.MouseButtonPress,
                    QEvent.Type.MouseButtonDblClick,
                    QEvent.Type.MouseButtonRelease,
                    QEvent.Type.MouseMove)):
            return True   # block -- swallow the event
        return super().eventFilter(obj, event)

    def _setup_ui(self):
        self.setWindowTitle("Wing Theatre Controller")
        self.resize(1400,860); self.setMinimumSize(1000,640)
        tb = QToolBar(); tb.setMovable(False); self.addToolBar(tb)

        # About button
        about_btn = QPushButton("?")
        about_btn.setFixedSize(26, 26)
        about_btn.setStyleSheet(
            f"background:{C['bg3']};color:{C['text3']};border:1px solid {C['border']};"
            f"border-radius:13px;font-weight:bold;")
        about_btn.setToolTip("About Wing Theatre Controller")
        about_btn.clicked.connect(lambda: AboutDialog(self).exec())
        tb.addWidget(about_btn)
        tb.addAction("New Show",    self._new_show)
        tb.addAction("Open...",     self._open_show)
        tb.addAction("Save",        self._save_show)
        tb.addAction("Save As...",  self._save_show_as)
        tb.addSeparator()
        # Autosave
        tb.addWidget(QLabel("  Autosave:"))
        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(0, 60); self._autosave_spin.setValue(0)
        self._autosave_spin.setSuffix(" min"); self._autosave_spin.setFixedWidth(80)
        self._autosave_spin.setToolTip("0 = disabled. Saves every N minutes to current file.")
        self._autosave_spin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        le = self._autosave_spin.lineEdit()
        le.setReadOnly(True)
        le.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # Make selection invisible -- same color as normal background/text
        le.setStyleSheet(
            f"selection-background-color: {C['bg2']};"
            f"selection-color: {C['text2']};")
        le.installEventFilter(self)
        self._autosave_spin.valueChanged.connect(self._on_autosave_changed)
        self._autosave_spin.valueChanged.connect(
            lambda: self._autosave_spin.lineEdit().deselect())
        tb.addWidget(self._autosave_spin)
        self.conn_panel = ConnectionPanel()
        self.conn_panel.setStyleSheet(f"border-bottom:1px solid {C['border']};")
        self.conn_panel.setFixedHeight(44)
        central = QWidget(); ml = QVBoxLayout(central)
        ml.setContentsMargins(0,0,0,0); ml.setSpacing(0)
        ml.addWidget(self.conn_panel)

        # Notes bar -- always visible between connection and cue list
        self.notes_bar = QLabel("")
        self.notes_bar.setStyleSheet(
            f"color:{C['text2']};font-size:12px;font-style:italic;"
            f"background:{C['bg2']};border-bottom:1px solid {C['border']};"
            f"padding:5px 14px;")
        self.notes_bar.setWordWrap(True)
        self.notes_bar.setFixedHeight(0)   # hidden until a snapshot with notes is selected
        self.notes_bar.setVisible(False)
        ml.addWidget(self.notes_bar)
        self.tabs = QTabWidget()
        cue_tab = QWidget(); ctl = QHBoxLayout(cue_tab)
        ctl.setContentsMargins(0,0,0,0); ctl.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.cue_panel = CueListPanel()
        self.cue_panel.setMinimumWidth(250); self.cue_panel.setMaximumWidth(320)
        splitter.addWidget(self.cue_panel)
        self.detail_panel = SnapshotDetailPanel(self.show_file); splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0,0); splitter.setStretchFactor(1,1)
        self._splitter = splitter   # keep reference for live mode
        ctl.addWidget(splitter); self.tabs.addTab(cue_tab,"Cue List")
        self.sections_panel = SectionsPanel(self.show_file)
        self.tabs.addTab(self.sections_panel, "Sections && Auto-Update")

        # OSC Settings tab
        self.osc_settings_panel = OscSettingsPanel(self.show_file)
        self.tabs.addTab(self.osc_settings_panel, "OSC Settings")
        ml.addWidget(self.tabs); self.setCentralWidget(central)
        self.status_bar = QStatusBar(); self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        QShortcut(QKeySequence("Space"),  self, self._go)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_show)
        QShortcut(QKeySequence("Ctrl+A"), self, self._add_snapshot)

    def _connect_signals(self):
        self.conn_panel.connect_requested.connect(
            lambda ip, p, lip: self.osc.connect(ip, p, lip))
        self.conn_panel.disconnect_requested.connect(self.osc.disconnect)
        self.osc.connected.connect(lambda c: self.conn_panel.set_connected(c, self.osc.ip))
        self.osc.connected.connect(self._on_connected)
        self.osc.sync_complete.connect(self._on_sync_complete)
        self.osc.log_message.connect(self.status_bar.showMessage)
        self.osc.log_message.connect(self._log_to_file)
        self.osc.capture_done.connect(self._on_capture_done)
        self.osc.parameter_received.connect(
            self._on_parameter_received,
            Qt.ConnectionType.QueuedConnection)  # safe for wingmon background thread
        self.osc.connection_lost.connect(self._on_connection_lost)
        self.conn_panel.auto_update_changed.connect(self._on_auto_update_changed)
        self.conn_panel.live_btn.clicked.connect(self._toggle_live_mode)
        self.cue_panel.cue_selected.connect(self._on_cue_selected)
        self.cue_panel.go_pressed.connect(self._go)
        self.cue_panel.add_pressed.connect(self._add_snapshot)
        self.cue_panel.snap_reordered.connect(self._on_snaps_reordered)
        self.cue_panel.snap_duplicate.connect(self._on_snap_duplicate)
        self.cue_panel.snaps_delete.connect(
            lambda idxs: self._delete_snapshots(idxs, confirm=True))
        self.cue_panel.multi_selected.connect(
            lambda n: self.detail_panel.load_multi(n) if n != 1 else None)
        self.cue_panel.snaps_set_group.connect(self._set_group_on_snapshots)
        self.cue_panel.snaps_set_scope.connect(self._set_scope_on_snapshots)
        self.detail_panel.snapshot_updated.connect(self._refresh_cue_list)
        self.detail_panel.snapshot_updated.connect(self._mark_dirty)
        self.detail_panel.scope_widget.scope_changed.connect(self._mark_dirty)
        self.detail_panel.group_added.connect(self._on_group_added)
        self.detail_panel.group_deleted.connect(self._on_group_deleted)
        self.detail_panel.capture_pressed.connect(self._capture)
        self.detail_panel.recall_pressed.connect(self._recall)
        self.detail_panel.delete_pressed.connect(self._delete_snapshot)
        self.sections_panel.sections_changed.connect(
            lambda: self.status_bar.showMessage("Sections updated"))
        self.sections_panel.sections_changed.connect(self._mark_dirty)
        self.osc_settings_panel.changed.connect(self._mark_dirty)
        self.osc_settings_panel.tcp_toggle_requested.connect(self._tcp_toggle)
        self.tcp_server.command_received.connect(self._on_tcp_command)
        self.osc_settings_panel.changed.connect(
            self.detail_panel.scope_widget.osc_tab.refresh_endpoints)
        # OSC remote control
        self.osc_server.snap_go.connect(self._osc_snap_go)
        self.osc_server.go.connect(self._go)
        self.osc_server.prev_go.connect(self._osc_prev_go)
        self.osc_server.next_go.connect(self._osc_next_go)
        self.osc_server.prev_nav.connect(self.cue_panel.go_prev)
        self.osc_server.next_nav.connect(self.cue_panel.go_next)
        self.osc_server.store_triggered.connect(self._capture)
        self.osc_server.autoupdate_set.connect(self._osc_autoupdate)
        self.osc_server.addsnap.connect(self._osc_addsnap)
        self.osc_server.log.connect(lambda m: self.status_bar.showMessage(m, 4000))

    # ── Dirty tracking & close ───────────────────────────────────────────────

    def _mark_dirty(self):
        self._dirty = True
        title = self.windowTitle()
        if not title.endswith(" *"):
            self.setWindowTitle(title + " *")

    def _mark_clean(self):
        self._dirty = False
        self.setWindowTitle(self.windowTitle().removesuffix(" *"))

    def _ask_save(self):
        """Ask user to save, discard or cancel. Returns True if OK to proceed."""
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Save:
            self._save_show(); return True
        if reply == QMessageBox.StandardButton.Discard:
            return True
        return False   # Cancel

    def closeEvent(self, event):
        if self._ask_save():
            try: self.tcp_server.stop()
            except: pass
            try: self.osc.disconnect()
            except: pass
            event.accept()
        else:
            event.ignore()

    # ── Autosave ─────────────────────────────────────────────────────────────

    def _on_autosave_changed(self, mins):
        self._autosave_timer.stop()
        if mins > 0:
            self._autosave_timer.start(mins * 60 * 1000)

    def _autosave(self):
        if self.show_file.filepath and self._dirty:
            try:
                self._collect_app_settings()
                self.show_file.save(self.show_file.filepath)
                self._mark_clean()
                self.status_bar.showMessage(
                    f"Autosaved -- {self.show_file.filepath}", 4000)
            except Exception as e:
                self.status_bar.showMessage(f"Autosave failed: {e}", 6000)

    # ── Snapshot reorder & duplicate ─────────────────────────────────────────

    def _on_snaps_reordered(self, new_order):
        """Called after drag-drop. Reorder show_file.snapshots then refresh."""
        self.show_file.snapshots = [
            self.show_file.snapshots[i] for i in new_order]
        self._mark_dirty()
        self._refresh_cue_list()

    def _on_snap_duplicate(self, snap_idx):
        """Duplicate the snapshot at snap_idx -- fully independent copy."""
        if snap_idx < 0 or snap_idx >= len(self.show_file.snapshots):
            return
        orig = self.show_file.snapshots[snap_idx]
        # Create fresh snapshot (calls __init__, sets defaults), then override each field
        dup = Snapshot(f"{orig.name} (copy)", len(self.show_file.snapshots) + 1)
        dup.notes          = orig.notes
        dup.cue_group      = orig.cue_group
        dup.data           = dict(orig.data)          # flat {path: value} dict
        dup.scope          = dict(orig.scope)
        dup.channel_scopes = _copy_channel_scopes(orig.channel_scopes)
        dup.fx_scope       = dict(orig.fx_scope)
        dup.cfg_scope      = dict(orig.cfg_scope)
        dup.group_fades    = {k: dict(v) for k, v in orig.group_fades.items()}
        dup.osc_messages   = [dict(m) for m in orig.osc_messages]
        self.show_file.snapshots.insert(snap_idx + 1, dup)
        self._mark_dirty()
        self._refresh_cue_list()
        self.cue_panel.set_current(snap_idx + 1)

    def _collect_app_settings(self):
        """Gather current UI/app-level settings into self.show_file.app_settings,
        called right before saving. Covers everything that isn't per-snapshot
        data: connection info, remote-control ports, autosave, and the
        customised Default Recall Scope (right-click Default to edit)."""
        try:
            osp = self.osc_settings_panel
            self.show_file.app_settings = {
                "wing_ip":    self.conn_panel.ip_input.text().strip(),
                "iface_ip":   self.conn_panel.iface_combo.currentData(),
                "osc_remote_port":    osp.rc_port.value(),
                "osc_remote_enabled": bool(getattr(osp, '_osc_server', None)
                                           and osp._osc_server.is_running()),
                "tcp_remote_port":    osp.tcp_port.value(),
                "tcp_remote_enabled": bool(self.tcp_server._running),
                "autosave_minutes":   self._autosave_spin.value(),
                "default_scope":        dict(DEFAULT_SCOPE),
                "default_channel_scopes": {k: v.to_dict() for k, v in DEFAULT_CHANNEL_SCOPES.items()},
                "default_fx_scope":      dict(DEFAULT_FX_SCOPE),
                "default_cfg_scope":     dict(DEFAULT_CFG_SCOPE),
                "default_group_fades":   {k: dict(v) for k, v in DEFAULT_GROUP_FADES.items()},
            }
        except Exception:
            import traceback
            traceback.print_exc()

    def _apply_app_settings(self):
        """Apply self.show_file.app_settings to the UI and DEFAULT_* globals
        after loading a show. Missing keys (older show files, or a fresh New
        Show) are left untouched -- current in-memory values are kept."""
        s = getattr(self.show_file, 'app_settings', None)
        if not s:
            return
        try:
            if "wing_ip" in s and s["wing_ip"]:
                self.conn_panel.ip_input.setText(s["wing_ip"])
            if "iface_ip" in s:
                idx = self.conn_panel.iface_combo.findData(s["iface_ip"])
                if idx >= 0:
                    self.conn_panel.iface_combo.setCurrentIndex(idx)

            osp = self.osc_settings_panel
            if "osc_remote_port" in s:
                osp.rc_port.setValue(int(s["osc_remote_port"]))
            if "tcp_remote_port" in s:
                osp.tcp_port.setValue(int(s["tcp_remote_port"]))
            if s.get("osc_remote_enabled") and hasattr(osp, '_osc_server') \
                    and not osp._osc_server.is_running():
                osp._rc_toggle()
            if s.get("tcp_remote_enabled") and not self.tcp_server._running:
                self._tcp_toggle(osp.tcp_port.value())

            if "autosave_minutes" in s:
                self._autosave_spin.setValue(int(s["autosave_minutes"]))

            if "default_scope" in s:
                DEFAULT_SCOPE.clear(); DEFAULT_SCOPE.update(s["default_scope"])
            if "default_channel_scopes" in s:
                DEFAULT_CHANNEL_SCOPES.clear()
                DEFAULT_CHANNEL_SCOPES.update(
                    {k: ChannelScope.from_dict(v) for k, v in s["default_channel_scopes"].items()})
            if "default_fx_scope" in s:
                DEFAULT_FX_SCOPE.clear(); DEFAULT_FX_SCOPE.update(s["default_fx_scope"])
            if "default_cfg_scope" in s:
                DEFAULT_CFG_SCOPE.clear(); DEFAULT_CFG_SCOPE.update(s["default_cfg_scope"])
            if "default_group_fades" in s:
                for gk, fades in s["default_group_fades"].items():
                    DEFAULT_GROUP_FADES[gk] = dict(fades)
        except Exception:
            import traceback
            traceback.print_exc()

    def _new_show(self):
        if not self._ask_save():
            return
        self.show_file = ShowFile()
        self._reload(); self._mark_clean()
        self.setWindowTitle("Wing Theatre Controller -- New Show")
        self.status_bar.showMessage("New show created -- add your first snapshot with +")

    def _reload(self):
        self.sections_panel.show     = self.show_file
        self.osc_settings_panel.show = self.show_file
        # Update show reference in the scope widget's OSC tab
        self.detail_panel.show = self.show_file
        self.detail_panel.scope_widget.show = self.show_file
        self.detail_panel.scope_widget.osc_tab.show = self.show_file
        self.sections_panel.refresh()
        self.osc_settings_panel.refresh()
        self._refresh_cue_list()
        self._apply_app_settings()

    def _open_show(self):
        if not self._ask_save(): return
        from PyQt6.QtWidgets import QFileDialog
        path,_ = QFileDialog.getOpenFileName(self,"Open Show","",
            "Wing Theatre Show (*.wts);;All Files (*)")
        if path:
            try:
                self.show_file = ShowFile.load(path); self._reload()
                self._mark_clean()
                self.setWindowTitle(f"Wing Theatre Controller -- {self.show_file.name}")
                self.status_bar.showMessage(f"Opened: {path}")
            except Exception as e: QMessageBox.critical(self,"Error",f"Could not open:\n{e}")

    def _save_show(self):
        self._collect_app_settings()
        if self.show_file.filepath:
            self.show_file.save(self.show_file.filepath)
            self._mark_clean()
            self.setWindowTitle(f"Wing Theatre Controller -- {self.show_file.name}")
            self.status_bar.showMessage(f"Saved: {self.show_file.filepath}")
        else: self._save_show_as()

    def _save_show_as(self):
        self._collect_app_settings()
        from PyQt6.QtWidgets import QFileDialog
        path,_ = QFileDialog.getSaveFileName(self,"Save Show As",
            f"{self.show_file.name}.wts","Wing Theatre Show (*.wts);;All Files (*)")
        if path:
            import os
            self.show_file.name = os.path.splitext(os.path.basename(path))[0]
            self.show_file.save(path); self._mark_clean()
            self.setWindowTitle(f"Wing Theatre Controller -- {self.show_file.name}")
            self.status_bar.showMessage(f"Saved as: {path}")

    def _add_snapshot(self):
        if not self.osc.is_connected:
            self.status_bar.showMessage(
                "Not connected to Wing — connect first before adding snapshots", 4000)
            return
        if not self.osc._wing_state:
            self.status_bar.showMessage(
                "Wing state not ready — wait for sync to complete", 4000)
            return
        try:
            name, ok = QInputDialog.getText(self, "New Snapshot", "Name:")
            if ok and name.strip():
                n = len(self.show_file.snapshots) + 1
                snap = Snapshot(name.strip(), n)
                with self.osc._wing_state_lock:
                    snap.data = dict(self.osc._wing_state)
                self.show_file.snapshots.append(snap)
                self._mark_dirty()
                self._refresh_cue_list()
                self.cue_panel.set_current(n - 1)
                self.status_bar.showMessage(
                    f"'{snap.name}' created with {len(snap.data)} parameters", 4000)
        except Exception:
            import traceback; traceback.print_exc()

    def _delete_snapshot(self):
        """Delete currently selected snapshot (from detail panel button)."""
        idx = self.cue_panel.current_index
        if idx >= 0:
            self._delete_snapshots([idx], confirm=True)

    def _delete_snapshots(self, indices, confirm=True):
        """Delete one or more snapshots by index, then select adjacent cue."""
        if not indices:
            return
        if confirm:
            names = [self.show_file.snapshots[i].name
                     for i in indices if i < len(self.show_file.snapshots)]
            if len(names) == 1:
                msg = f"Slet '{names[0]}'?"
            else:
                msg = f"Slet {len(names)} cues?\n" + "\n".join(f"  • {n}" for n in names[:5])
                if len(names) > 5: msg += f"\n  … og {len(names)-5} til"
            if QMessageBox.question(
                self, "Delete cues", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return

        # Find adjacent index before deleting
        current = self.cue_panel.current_index
        indices_set = set(indices)
        remaining = [i for i in range(len(self.show_file.snapshots))
                     if i not in indices_set]

        # Delete highest indices first to preserve lower indices
        for i in sorted(indices, reverse=True):
            if i < len(self.show_file.snapshots):
                self.show_file.snapshots.pop(i)

        self._refresh_cue_list()
        self.detail_panel.load_snapshot(None)
        self._mark_dirty()

        # Auto-select: pick nearest remaining snapshot
        if remaining:
            # Find the closest remaining index to where we were
            best = min(remaining, key=lambda r: abs(r - current))
            # Remap to new indices after deletion
            new_idx = sum(1 for i in indices if i < best)
            new_idx = best - new_idx  # adjust for removed items before it
            self.cue_panel.set_current(max(0, min(new_idx,
                                                   len(self.show_file.snapshots)-1)))

    def _set_group_on_snapshots(self, indices, tag):
        for i in indices:
            if i < len(self.show_file.snapshots):
                self.show_file.snapshots[i].cue_group = tag
        self._refresh_cue_list()
        self._mark_dirty()
        msg = f"Gruppe-tag '{tag}' sat på {len(indices)} cue(s)" if tag else f"Gruppe-tag fjernet fra {len(indices)} cue(s)"
        self.status_bar.showMessage(msg, 3000)

    def _set_scope_on_snapshots(self, indices, scope):
        """Apply full default scope reset to multiple snapshots at once."""
        import copy as _copy
        for i in indices:
            if i < len(self.show_file.snapshots):
                s = self.show_file.snapshots[i]
                s.scope          = dict(DEFAULT_SCOPE)
                s.channel_scopes = _copy_channel_scopes(DEFAULT_CHANNEL_SCOPES)
                s.fx_scope       = dict(DEFAULT_FX_SCOPE)
                s.cfg_scope      = dict(DEFAULT_CFG_SCOPE)
                for gk, fades in DEFAULT_GROUP_FADES.items():
                    s.group_fades[gk] = dict(fades)
        self._mark_dirty()
        self.status_bar.showMessage(
            f"Standard scope sat på {len(indices)} cue(s)", 3000)
        if self.cue_panel.current_index in indices:
            snap = self.show_file.snapshots[self.cue_panel.current_index]
            self.detail_panel.load_snapshot(snap)

    def _all_groups(self):
        """All group names: from show_file.groups + any in snapshots not yet listed."""
        groups = list(self.show_file.groups)
        for s in self.show_file.snapshots:
            g = (s.cue_group or "").strip()
            if g and g not in groups:
                groups.append(g)
        return groups

    def _on_group_added(self, group_name):
        if group_name not in self.show_file.groups:
            self.show_file.groups.append(group_name)
        self._mark_dirty()
        self._refresh_cue_list()

    def _on_group_deleted(self, group_name):
        """Remove group entirely -- clear it from all snapshots and from show.groups."""
        if group_name in self.show_file.groups:
            self.show_file.groups.remove(group_name)
        for snap in self.show_file.snapshots:
            if (snap.cue_group or "").strip() == group_name:
                snap.cue_group = ""
        self._mark_dirty()
        self._refresh_cue_list()

    def _refresh_cue_list(self):
        self.cue_panel.populate(self.show_file.snapshots)
        self.detail_panel.set_groups(self._all_groups())
        self._mark_dirty()

    def _toggle_live_mode(self, live):
        """Switch between Live Mode (compact) and Edit Mode (full UI)."""
        if live:
            # ── Enter Live Mode ───────────────────────────────────────────────
            self._pre_live_sizes = self._splitter.sizes()
            self._pre_live_size  = self.size()

            # Hide edit-only elements in connection panel
            self.conn_panel.set_live(True)

            # Hide detail panel + all tabs except cue list
            self.detail_panel.setVisible(False)
            self.tabs.tabBar().setVisible(False)
            self.tabs.setCurrentIndex(0)
            self._splitter.setSizes([460, 0])
            self._splitter.setHandleWidth(0)

            # Hide Add Snap button
            if hasattr(self.cue_panel, 'add_snap_btn'):
                self.cue_panel.add_snap_btn.setVisible(False)

            # Show notes bar in live mode (always -- even if empty)
            self.notes_bar.setVisible(True)
            self.notes_bar.setFixedHeight(36)

            # Remove live_notes label (was old approach -- notes_bar handles it now)
            self.cue_panel.live_notes.setVisible(False)

            # Resize to narrow live window (wide enough to show autosave control)
            self.resize(480, self._pre_live_size.height())
            self.setMinimumSize(280, 400)
            self.setMaximumWidth(480)

            # Style LIVE button -- green when active
            self.conn_panel.live_btn.setStyleSheet(
                f"font-size:10px;letter-spacing:0.1em;padding:0 12px;font-weight:bold;"
                f"color:{C['green']};border:1px solid {C['green_border']};border-radius:4px;"
                f"background:{C['green_bg']};")
            self.setWindowTitle(self.windowTitle().replace(" -- LIVE", "") + " -- LIVE")

        else:
            # ── Exit Live Mode ────────────────────────────────────────────────
            # Hide notes bar in edit mode
            self.notes_bar.setVisible(False)
            self.notes_bar.setFixedHeight(0)

            self.conn_panel.set_live(False)
            self.detail_panel.setVisible(True)
            self.tabs.tabBar().setVisible(True)

            if hasattr(self.cue_panel, 'add_snap_btn'):
                self.cue_panel.add_snap_btn.setVisible(True)

            self.setMaximumWidth(16777215)
            self.setMinimumSize(1000, 640)
            self.resize(self._pre_live_size)
            if hasattr(self, '_pre_live_sizes'):
                self._splitter.setSizes(self._pre_live_sizes)

            self.conn_panel.live_btn.setStyleSheet(
                f"font-size:10px;letter-spacing:0.1em;padding:0 12px;font-weight:bold;"
                f"color:{C['text3']};border:1px solid {C['border']};border-radius:4px;"
                f"background:{C['bg3']};")
            self.setWindowTitle(self.windowTitle().replace(" -- LIVE", ""))

    def _on_cue_selected(self, snap_idx):
        if 0 <= snap_idx < len(self.show_file.snapshots):
            snap = self.show_file.snapshots[snap_idx]
            self.detail_panel.load_snapshot(snap)
            # Update notes text -- only show bar if we're in live mode
            notes = snap.notes.strip() if snap.notes else ""
            self.notes_bar.setText(notes)
            # In live mode the bar is always visible (even if empty)
            # In edit mode it stays hidden regardless

    # ── TCP Companion remote control ─────────────────────────────────────────

    def _tcp_toggle(self, port: int):
        """Start or stop TCP Companion server."""
        if self.tcp_server._running:
            self.tcp_server.stop()
            self.osc_settings_panel.tcp_set_running(False)
            self.status_bar.showMessage("TCP remote: stopped", 3000)
        else:
            self.tcp_server.start(port)
            self.osc_settings_panel.tcp_set_running(True)
            self.status_bar.showMessage(f"TCP remote: listening on port {port}", 3000)

    def _tcp_cue_state(self) -> dict:
        """Build the cue-state dict sent to Companion.

        current  = the cue that was last fired (active_cue_index)
        next     = the cue that the next GO will fire (the cursor position)
        selected = the cursor position (same as next; named for clarity)
        """
        snaps  = self.show_file.snapshots
        count  = len(snaps)
        active = self.active_cue_index
        sel    = self.cue_panel.current_index

        def num(i):  return f"{snaps[i].number:03d}" if 0 <= i < count else ""
        def name(i): return snaps[i].name            if 0 <= i < count else ""

        return {
            "current_cue_num":   num(active),
            "current_cue_name":  name(active),
            "next_cue_num":      num(sel),
            "next_cue_name":     name(sel),
            "selected_cue_num":  num(sel),
            "selected_cue_name": name(sel),
            "cue_count":         str(count),
        }

    def _tcp_send_cue_state(self):
        """Send cue-related state (after GO, NEXT, PREV)."""
        self.tcp_server.send_full_state(self._tcp_cue_state())

    def _tcp_send_full_state(self):
        """Send all state — cue state plus connection/mode flags."""
        state = self._tcp_cue_state()
        state.update({
            "autoupdate":     str(self.osc._auto_update).lower(),
            "wing_connected": str(self.osc.is_connected).lower(),
            "fading":         str(bool(self.osc._fade_jobs)).lower(),
        })
        self.tcp_server.send_full_state(state)

    def _on_tcp_command(self, cmd: str):
        """Handle command from TCP Companion client."""
        # Connection events
        if cmd.startswith("__connected__"):
            addr = cmd[len("__connected__"):]
            self.osc_settings_panel.tcp_set_running(True, addr)
            self.status_bar.showMessage(f"TCP: Companion connected from {addr}", 3000)
            self._tcp_send_full_state()
            return
        if cmd == "__disconnected__":
            self.osc_settings_panel.tcp_set_running(True)  # still listening
            self.status_bar.showMessage("TCP: Companion disconnected", 3000)
            return

        cmd_raw = cmd.strip()
        self.status_bar.showMessage(f"TCP: received '{cmd_raw}'", 2000)

        # Split into verb + argument. Only the verb is case-normalised —
        # the argument keeps the user's original casing (cue names).
        parts = cmd_raw.split(" ", 1)
        verb  = parts[0].upper()
        arg   = parts[1].strip() if len(parts) > 1 else ""

        if verb == "GO":
            self._go()
        elif verb == "NEXT_GO":
            self._osc_next_go()
        elif verb == "PREV_GO":
            self._osc_prev_go()
        elif verb == "SNAP_GO":
            try:
                self._osc_snap_go(int(arg))
            except ValueError:
                for i, s in enumerate(self.show_file.snapshots):
                    if s.name.lower() == arg.lower():
                        self.cue_panel.set_current(i)
                        self._go()
                        break
        elif verb == "AU_ON":
            self._osc_autoupdate(True)
        elif verb == "AU_OFF":
            self._osc_autoupdate(False)
        elif verb == "AU_TOGGLE":
            self._osc_autoupdate(not self.osc._auto_update)
        elif verb == "ADD_SNAP":
            self._osc_addsnap(arg)          # arg keeps original casing
        elif verb == "NEXT":
            self.cue_panel.go_next()
            self._tcp_send_cue_state()
        elif verb == "PREV":
            self.cue_panel.go_prev()
            self._tcp_send_cue_state()
        elif verb == "GET_STATE":
            self._tcp_send_full_state()

    # ── OSC remote control handlers ──────────────────────────────────────────

    def _osc_prev_go(self):
        """Play the cue before the last-fired cue (based on active_index)."""
        active = self.cue_panel.active_index
        if active < 0:
            # Nothing played yet -- play the currently selected cue
            self._go(); return
        target = active - 1
        if target < 0: return
        row = self.cue_panel._snap_row_to_list_row(target)
        if row >= 0:
            self.cue_panel.list_widget.setCurrentRow(row)
            self._go()

    def _osc_next_go(self):
        """Play the cue after the last-fired cue (based on active_index)."""
        active = self.cue_panel.active_index
        if active < 0:
            self._go(); return
        target = active + 1
        if target >= len(self.show_file.snapshots): return
        row = self.cue_panel._snap_row_to_list_row(target)
        if row >= 0:
            self.cue_panel.list_widget.setCurrentRow(row)
            self._go()

    def _osc_snap_go(self, value):
        """Find snapshot by 3-digit number string ('002') or by name, then GO."""
        snaps = self.show_file.snapshots
        target = None
        # 1) Try as integer number (handles "002", "2", int 2, float 2.0)
        try:
            num = int(float(str(value).strip()))
            target = next((s for s in snaps if s.number == num), None)
        except (ValueError, TypeError):
            pass
        # 2) Try exact name match (case-insensitive)
        if target is None:
            name_lower = str(value).strip().lower()
            target = next(
                (s for s in snaps if s.name.strip().lower() == name_lower), None)
        # 3) Try partial name match
        if target is None:
            target = next(
                (s for s in snaps if name_lower in s.name.strip().lower()), None)

        if target:
            idx = snaps.index(target)
            self.cue_panel.set_current(idx)
            self._go()
        else:
            self.status_bar.showMessage(
                f"OSC: snapshot '{value}' not found", 4000)

    def _osc_autoupdate(self, enable: bool):
        """Enable or disable Auto Update via OSC."""
        try:
            btn = self.conn_panel.au_btn
            if btn.isChecked() != enable:
                btn.setChecked(enable)
                self.conn_panel._on_au(enable)
                self.tcp_server.send_state("autoupdate", str(enable).lower())
        except Exception as e:
            import sys; print(f"[TCP] _osc_autoupdate error: {e}", file=sys.stderr)

    def _osc_addsnap(self, name: str):
        """Add a new snapshot via OSC /wingtheatre/addsnap [name]"""
        n = len(self.show_file.snapshots) + 1
        snap_name = name.strip() if name.strip() else f"Scene {n:03d}"
        snap = Snapshot(snap_name, n)
        if self.osc._wing_state:
            with self.osc._wing_state_lock:
                snap.data = dict(self.osc._wing_state)
        self.show_file.snapshots.append(snap)
        self._mark_dirty()
        self._refresh_cue_list()
        self.cue_panel.set_current(n - 1)
        self.status_bar.showMessage(
            f"OSC: '{snap_name}' created with {len(snap.data)} parameters", 4000)

    def _go(self):
        idx = self.cue_panel.current_index
        if idx < 0 or idx >= len(self.show_file.snapshots): return
        snap = self.show_file.snapshots[idx]
        self.cue_panel.mark_active(idx); self.active_cue_index = idx
        self.status_bar.showMessage(f"▶  GO: {snap.number:03d}  {snap.name}")
        if self.osc.is_connected: self._recall_to_wing(snap)
        # Send per-snapshot OSC messages
        if snap.osc_messages:
            results = OscSender.send_messages(snap.osc_messages, self.show_file.osc_outputs)
            errors = [r for r in results if not r[0]]
            if errors:
                self.status_bar.showMessage(
                    f"▶ GO {snap.number:03d} -- OSC: {errors[0][2]}", 4000)
        self.cue_panel.go_next()
        # TCP feedback — send updated cue state
        self._tcp_send_cue_state()

    def _capture(self):
        """Update from Wing -- copies current live state instantly."""
        if not self.osc.is_connected:
            self.status_bar.showMessage(
                "Not connected -- cannot update from Wing", 4000)
            return
        idx = self.cue_panel.current_index
        if idx < 0 or idx >= len(self.show_file.snapshots):
            self.status_bar.showMessage(
                "No snapshot selected", 4000)
            return
        snap = self.show_file.snapshots[idx]
        if not self.osc._wing_state:
            self.status_bar.showMessage(
                "Wing state not ready -- wait for sync to complete", 4000)
            return
        with self.osc._wing_state_lock:
            snap.data = dict(self.osc._wing_state)
        self._mark_dirty()
        live_events = getattr(self.osc, '_live_event_count', 0)
        self.status_bar.showMessage(
            f"✓ Updated '{snap.name}' -- {len(snap.data)} params "
            f"({live_events} live events received since connect)", 6000)

    def _on_capture_done(self, data, target_idx):
        """Called when WingOSC finishes a full capture.
        target_idx is the snapshot index saved at capture START -- never stale."""
        if target_idx < 0 or target_idx >= len(self.show_file.snapshots):
            return
        snap = self.show_file.snapshots[target_idx]
        snap.data = data
        self._mark_dirty()
        if data:
            self.status_bar.showMessage(
                f"✓ Captured {len(data)} parameters -> '{snap.name}'", 6000)
        else:
            self.status_bar.showMessage(
                f"⚠ Capture returned 0 parameters -- check wingmon connection", 6000)

    def _on_connected(self, connected: bool):
        """Handle connection state change -- disable UI until sync completes."""
        self.tcp_server.send_state("wing_connected", str(connected).lower())
        if connected:
            # Connected but not yet synced -- show progress
            self.status_bar.showMessage(
                "⟳ Syncing Wing state -- please wait…")
            # Timeout: if SYNC_COMPLETE doesn't arrive within 15s, show error
            self._sync_timeout = QTimer(self)
            self._sync_timeout.setSingleShot(True)
            self._sync_timeout.timeout.connect(self._on_sync_timeout)
            self._sync_timeout.start(15000)
        else:
            if hasattr(self, '_sync_timeout'):
                self._sync_timeout.stop()
            self.status_bar.showMessage("Disconnected", 3000)

    def _on_sync_complete(self, param_count: int):
        """Wing state fully synced -- enable all UI."""
        if hasattr(self, '_sync_timeout'):
            self._sync_timeout.stop()
        self.status_bar.showMessage(
            f"✓ Wing connected -- {param_count} parameters synced", 5000)

    def _on_sync_timeout(self):
        """Sync didn't complete in time -- show error."""
        self.status_bar.showMessage(
            "⚠ Sync timeout -- Wing connected but state incomplete. "
            "Try 'Update from Wing' manually.", 8000)

    def _on_connection_lost(self):
        """Wing stopped responding -- show warning dialog."""
        self.osc.set_auto_update(False)
        QMessageBox.warning(
            self, "Forbindelse mistet",
            f"Forbindelsen til Behringer Wing på {self.osc.ip} er mistet.\n\n"
            "Programmet forsøger automatisk at genoprette forbindelsen\n"
            "hvert 10. sekund.")

    def _on_auto_update_changed(self, enabled):
        """Start/stop auto-update polling with scope-relevant paths."""
        try:
            if enabled:
                idx = self.cue_panel.active_index
                if idx < 0:
                    idx = self.cue_panel.current_index
                paths = None
                if 0 <= idx < len(self.show_file.snapshots):
                    snap = self.show_file.snapshots[idx]
                    if snap.data:
                        paths = [p for p in snap.data.keys()
                                 if self.osc._path_in_scope(p, snap)]
                        # Sort: faders+mutes first, then EQ, then rest
                        def _prio(p):
                            if p.endswith('/fdr') or p.endswith('/mute'): return 0
                            if '/eq/' in p or p.endswith('/eq/on'):        return 1
                            return 2
                        paths.sort(key=_prio)
                self.osc.set_auto_update(True, paths)
            else:
                self.osc.set_auto_update(False)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_bar.showMessage(f"⚠ Auto Update toggle error: {e}", 6000)

    def _get_active_section(self):
        """Return the currently selected Section from SectionsPanel, or None."""
        idx = self.sections_panel.sec_list.currentRow()
        if 0 <= idx < len(self.show_file.sections):
            return self.show_file.sections[idx]
        return None

    def _on_parameter_received(self, path, value):
        """Auto Update -- write to snapshots.
        Only runs when AU is ON. Guards against spurious calls.

        This runs as a Qt slot via a queued connection from the wingmon
        background thread. An unhandled exception raised here does not just
        get logged and skipped -- PyQt can treat it as fatal and bring down
        the whole application, since the exception has nowhere safe to go
        once it crosses back into Qt's event loop. So the entire body is
        guarded: on any error we log it and drop this one event, instead of
        risking a full crash of the app.
        """
        try:
            self._on_parameter_received_impl(path, value)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.status_bar.showMessage(f"⚠ Auto Update error (ignored): {e}", 6000)
            print(tb)  # full traceback for diagnostics, if a console is attached

    def _on_parameter_received_impl(self, path, value):
        # Explicit AU guard -- should never be called with AU off
        if not self.osc._auto_update:
            return

        # Ignore echoes from our own fade engine. When a cue recall fades a
        # fader/send over time, each step is sent to Wing via SET, and Wing
        # echoes every change back as a live event on the same connection.
        # Without this guard, Auto Update would treat those intermediate
        # fade steps as real console moves and write the mid-fade value
        # into the snapshot instead of the fade's actual target value.
        #
        # We know exactly what value the fade is heading to, so instead of
        # guessing a time window, we suppress writes for this path until we
        # actually SEE that target value arrive from Wing -- then release
        # the guard immediately. A safety deadline is a fallback only, so a
        # path can't stay stuck suppressed forever if the target is somehow
        # never reached (interrupted fade, connection hiccup, Wing rounding
        # to a slightly different step than requested).
        # _fade_jobs/_fading_paths live on self.osc (WingOSC), not on
        # MainWindow -- that's where _start_fade/_unified_step also live.
        info = self.osc._fading_paths.get(path)
        if info is not None:
            import time as _time
            now = _time.time()
            if self.osc._approx_equal(value, info["target"]):
                del self.osc._fading_paths[path]
                self.status_bar.showMessage(
                    f"AU: fade reached target for {path} -- resuming normal AU", 2000)
                return
            if now < info["deadline"]:
                self.status_bar.showMessage(
                    f"AU: suppressed {path} = {value} (mid-fade, target={info['target']:.3g})", 1500)
                return
            # Safety timeout -- give up waiting and process this as a real event
            del self.osc._fading_paths[path]
            self.status_bar.showMessage(
                f"AU: fade guard timed out for {path} -- resuming normal AU", 3000)

        scope_key = self.osc._path_to_scope_key(path)
        ch_key    = self.osc._path_to_ch_key(path)
        if not scope_key or not ch_key:
            return

        # Determine write mode
        if not self.show_file.sections:
            # No sections defined -> AU is disabled until sections are configured
            if not getattr(self, '_au_no_section_warned', False):
                self._au_no_section_warned = True
                self.status_bar.showMessage(
                    'Auto Update: create a section first to enable per-cue writing', 5000)
            return
        else:
            self._au_no_section_warned = False
            section = self._get_active_section()
            if section:
                mode = section.exclusions.get(scope_key, 'snap')
                if section.channels and ch_key not in section.channels:
                    return
            else:
                mode = 'snap'

        active_idx = self.cue_panel.active_index
        if active_idx < 0 or active_idx >= len(self.show_file.snapshots):
            if not getattr(self, '_au_no_cue_warned', False):
                self._au_no_cue_warned = True
                self.status_bar.showMessage(
                    'Auto Update: press GO on a cue first to enable writing', 5000)
            return
        self._au_no_cue_warned = False

        if mode == 'snap':
            targets = [active_idx]
        elif mode == 'group':
            group_tag = self.show_file.snapshots[active_idx].cue_group.strip()
            targets = ([i for i,s in enumerate(self.show_file.snapshots)
                        if s.cue_group.strip() == group_tag]
                       if group_tag else [active_idx])
        else:  # 'all'
            targets = range(len(self.show_file.snapshots))

        changed = False
        for idx in targets:
            snap = self.show_file.snapshots[idx]
            if self.osc._path_in_scope(path, snap):
                snap.data[path] = value
                changed = True
        if changed:
            if scope_key in ('fader', 'sends'):
                self.status_bar.showMessage(
                    f"AU: wrote {path} = {value} to {len(targets)} cue(s)", 1500)
            self._mark_dirty()

    def _recall(self):
        idx = self.cue_panel.current_index
        if idx < 0 or idx >= len(self.show_file.snapshots): return
        snap = self.show_file.snapshots[idx]
        if self.osc.is_connected: self._recall_to_wing(snap)
        else: self.status_bar.showMessage("Not connected -- recall simulated")

    def _recall_to_wing(self, snapshot):
        n = len(snapshot.data)
        if n == 0:
            self.status_bar.showMessage(
                f"▶ GO: {snapshot.name} -- NO DATA (run 'Update from Wing' first)", 5000)
            return
        self.status_bar.showMessage(
            f"▶ Recall: {snapshot.number:03d}  {snapshot.name}  ({n} params)")
        self.osc.recall_snapshot(snapshot)

# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    import traceback, datetime

    def _log_crash(exc_type, exc_value, exc_tb):
        """Catch-all safety net: on Windows especially, an unhandled exception
        in a Qt slot can otherwise kill the whole app with no visible error.
        Write full details to crash_log.txt next to the app so it can be
        sent back for diagnosis, and still print to stderr if a console
        happens to be attached."""
        try:
            base = os.path.dirname(os.path.abspath(
                sys.executable if getattr(sys, 'frozen', False) else __file__))
            log_path = os.path.join(base, 'crash_log.txt')
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"\n--- {datetime.datetime.now().isoformat()} ---\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        except Exception:
            pass
        try:
            traceback.print_exception(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _log_crash

    app = QApplication(sys.argv); app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(C['bg']))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(C['text']))
    pal.setColor(QPalette.ColorRole.Base,            QColor(C['bg2']))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(C['bg3']))
    pal.setColor(QPalette.ColorRole.Text,            QColor(C['text']))
    pal.setColor(QPalette.ColorRole.Button,          QColor(C['bg3']))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(C['text']))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(C['green']))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(C['bg']))
    app.setPalette(pal); app.setStyleSheet(STYLESHEET)
    w = MainWindow(); w.show(); sys.exit(app.exec())

if __name__ == "__main__":
    main()
