# journal_app.py — line-by-line annotated walkthrough
# (Reading version — heavy inline comments; not intended to be executed)

# Requires: pip install tksheet

# --- Standard library imports ---
import tkinter as tk                 # Tkinter base GUI toolkit (widgets, window)
from tkinter import ttk, messagebox, simpledialog, filedialog  # dialogs + ttk widgets
from datetime import datetime        # for timestamps on bars/session rows
import csv                           # for saving/loading CSV data
import tkinter.font as tkfont        # to measure text line height for auto row sizing
from typing import Optional          # type hints for readability

# --- Third-party library ---
from tksheet import Sheet            # grid widget with rich features (per-cell style, selection, etc.)

# --- Local modules (your own files) ---
from constants import (
    BULL_POINTS, BEAR_POINTS, TR_POINTS, BIAS_POINTS,  # preset button labels per category
    COLUMNS, COL_INDEX, KINDS_BY_COL, BAR_ORDER        # table layout, index maps, row order
)
from tooltip import _Tooltip                            # small helper class to show hover tooltips
from scrollable_buttons import _ScrollableButtons       # scrollable Panels with buttons
from autosave import AutosaveMixin                      # mixin adding autosave/load methods
import json, os
from pathlib import Path
import constants as CONST  # runtime-editable presets



class JournalApp(tk.Tk, AutosaveMixin):
    def __init__(self):
        super().__init__()
        self.title("Price Action Click-Journal")
        self.geometry("800x720")


        # In-memory data
        self.data = {}
        self.history = []

        self.shift_held = False
        self._resizing_columns = False
        self._last_selected_row = 0
        self._select_after_id = None
        self._last_click_time = 0  # For click debouncing

        # Pre-create empty rows
        for key in BAR_ORDER:
            self._ensure_bar_exists(key)

        # Row height behavior controls
        self.row_height = tk.IntVar(value=28)
        self.auto_row_height = tk.BooleanVar(value=True)

        # Selected/active bar indicator (combobox shows this value)
        self.current_bar = tk.StringVar(value=str(BAR_ORDER[0]))

        self._build_ui()

        # Tooltip helper
        self._tooltip = _Tooltip(self)
        self._tip_visible_for = None

        # Targeting helpers
        self._click_row = None   # Start with row 0 selected
        self._hover_row = None   # last hovered row (for tooltips)

        # Global key bindings
        self.bind_all("<KeyPress-Shift_L>",  lambda e: self._set_shift(True))
        self.bind_all("<KeyRelease-Shift_L>",lambda e: self._set_shift(False))
        self.bind_all("<KeyPress-Shift_R>",  lambda e: self._set_shift(True))
        self.bind_all("<KeyRelease-Shift_R>",lambda e: self._set_shift(False))

        self.bind("<Control-s>", lambda e: self.save_csv())
        self.bind("<Control-z>", lambda e: self.undo_last())
        self.bind("<Return>",    lambda e: self.next_bar())
        self.bind("<Control-minus>",       lambda e: self.nudge_alpha(-0.05))
        self.bind("<Control-underscore>",  lambda e: self.nudge_alpha(-0.05))
        self.bind("<Control-equal>",       lambda e: self.nudge_alpha(+0.05))
        self.bind("<Control-plus>",        lambda e: self.nudge_alpha(+0.05))
        self.bind("<Control-t>",           lambda e: self.toggle_topmost())

        self.bind_all("<Up>",   self._on_up_arrow)
        self.bind_all("<Down>", self._on_down_arrow)
        self.bind_all("<Delete>", self._on_delete_key)

        # Try load autosaved session from disk (if exists)
        self._load_session_json(BAR_ORDER)

        # First paint of the table; also selects the first row
        self.refresh_table(select_bar=BAR_ORDER[0])

        self.after_idle(self._auto_row_heights)



    # --- Small helper to set Shift state ---
    def _set_shift(self, val: bool):
        self.shift_held = bool(val)

    # --- Window transparency helpers ---
    def _get_alpha(self) -> float:
        try: return float(self.attributes("-alpha"))
        except Exception: return 1.0

    def set_alpha(self, value: float):
        value = max(0.30, min(1.0, float(value)))
        try: self.attributes("-alpha", value)
        except Exception: pass

    def nudge_alpha(self, delta: float):
        self.set_alpha(self._get_alpha() + delta)

    def toggle_topmost(self, force: Optional[bool] = None):
        try: current = bool(self.attributes("-topmost"))
        except Exception: current = False
        new_val = (not current) if force is None else bool(force)
        try: self.attributes("-topmost", new_val)
        except Exception: pass

    # --- Build the entire UI ---
    def _build_ui(self):
        self.style = ttk.Style(self)

        # Top toolbar
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)

        # --- “詞庫” Menubutton in the gray toolbar ---
        style = ttk.Style(self)
        frame_bg = style.lookup("TFrame", "background") or "#f0f0f0"  # fallback gray

        # Create the shared dropdown menu
        self.preset_menu = tk.Menu(self, tearoff=False,
                                bg=frame_bg, activebackground="#d9d9d9",
                                bd=0, relief="flat")
        self.preset_menu.add_command(label="編輯 牛方論點（BULL）…", command=lambda: self._open_preset_editor("bull"))
        self.preset_menu.add_command(label="編輯 熊方論點（BEAR）…", command=lambda: self._open_preset_editor("bear"))
        self.preset_menu.add_command(label="編輯 TR 論點（TR）…",   command=lambda: self._open_preset_editor("tr"))
        self.preset_menu.add_command(label="編輯 Bias 論點（BIAS）…", command=lambda: self._open_preset_editor("bias"))
        self.preset_menu.add_separator()
        self.preset_menu.add_command(label="重設為原廠預設", command=self._reset_presets_confirm)

        # Place a Menubutton inside the gray frame so it visually matches the frame
        self.preset_btn = ttk.Menubutton(top, text="詞庫", direction="below")
        # attach the menu to the button
        self.preset_btn["menu"] = self.preset_menu
        self.preset_btn.pack(side="left", padx=(12, 6))









        ttk.Label(top, text="Bar").pack(side="left")

        values = [str(x) for x in BAR_ORDER]
        self.bar_entry = ttk.Combobox(top, width=8, textvariable=self.current_bar,
                                      values=values, state="readonly")
        self.bar_entry.pack(side="left", padx=6)

        ttk.Button(top, text="清空當前Bar", command=self.clear_current_bar).pack(side="left", padx=4)
        ttk.Button(top, text="上一Bar",     command=self.prev_bar).pack(side="left", padx=4)
        ttk.Button(top, text="下一Bar (Enter)", command=self.next_bar).pack(side="left", padx=4)
        ttk.Button(top, text="Undo (Ctrl+Z)", command=self.undo_last).pack(side="left", padx=12)

        # Second toolbar
        top2 = ttk.Frame(self); top2.pack(fill="x", padx=8, pady=(0,6))
        ttk.Button(top2, text="存CSV (Ctrl+S)", command=self.save_csv).pack(side="left", padx=4)
        ttk.Button(top2, text="載入 CSV",        command=self.load_csv).pack(side="left", padx=4)
        ttk.Button(top2, text="Autofit columns", command=self._autofit_columns).pack(side="left", padx=12)

        ttk.Button(top2, text="Opacity −", width=10,
                   command=lambda: self.nudge_alpha(-0.05)).pack(side="left", padx=(12, 2))
        ttk.Button(top2, text="Opacity ＋", width=10,
                   command=lambda: self.nudge_alpha(+0.05)).pack(side="left", padx=2)

        try: initial_topmost = bool(self.attributes("-topmost"))
        except Exception: initial_topmost = False
        topmost_var = tk.BooleanVar(value=initial_topmost)
        def _on_topmost(): self.toggle_topmost(force=topmost_var.get())
        ttk.Checkbutton(top2, text="Always on top",
                        variable=topmost_var, command=_on_topmost).pack(side="left", padx=(12, 4))

        # Row height controls
        heightf = ttk.Frame(self); heightf.pack(fill="x", padx=8, pady=(0,6))
        ttk.Label(heightf, text="Row height").pack(side="left")
        ttk.Scale(heightf, from_=18, to=72, orient="horizontal",
                  variable=self.row_height, command=lambda _e: self._apply_row_height()
        ).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(heightf, text="Compact",  command=lambda: self._set_row_height(22)).pack(side="left", padx=4)
        ttk.Button(heightf, text="Comfort",  command=lambda: self._set_row_height(28)).pack(side="left", padx=4)
        ttk.Button(heightf, text="Expanded", command=lambda: self._set_row_height(40)).pack(side="left", padx=4)
        ttk.Checkbutton(heightf, text="Auto row height",
                        variable=self.auto_row_height,
                        command=self._apply_row_height).pack(side="left", padx=(12, 4))
        

        ttk.Button(heightf, text="自動行高 (Auto-fit row heights)", command=self._manual_autofit_rows).pack(side=tk.LEFT, padx=6)

        # Scrollable button panels
        btns = ttk.Frame(self); btns.pack(fill="x", expand=False, padx=8, pady=6)
        for col in range(3):
            btns.columnconfigure(col, weight=1, uniform="points")
        btns.rowconfigure(0, weight=0); btns.rowconfigure(1, weight=0)

        # load user presets before building panels
        self._presets_path = Path(os.getcwd()) / "presets.json"
        self._load_presets_and_apply()
        
        bull = _ScrollableButtons(btns, "🐂 牛方論點", "bull", BULL_POINTS,
        on_button_press=self.handle_point_button,
        on_add_custom=lambda kind="bull": self.add_custom_point(kind),
        height=170, grid_cols=2, bg_color="#2e8b57")
        bear = _ScrollableButtons(btns, "🐻 熊方論點", "bear", BEAR_POINTS,
                                  on_button_press=self.handle_point_button,
                                  on_add_custom=lambda kind="bear": self.add_custom_point(kind),
                                  height=170, grid_cols=2, bg_color="#b22222")
        tr   = _ScrollableButtons(btns, "〰️ TR 論點",  "tr",   TR_POINTS,
                                  on_button_press=self.handle_point_button,
                                  on_add_custom=lambda kind="tr": self.add_custom_point(kind),
                                  height=170, grid_cols=2, bg_color="#1e90ff")

        bull.grid(row=0, column=0, sticky="ew", padx=6)
        bear.grid(row=0, column=1, sticky="ew", padx=6)
        tr.grid(row=0, column=2, sticky="ew", padx=6)

      
        bias = _ScrollableButtons(btns, "🎯 Bias 論點", "bias", BIAS_POINTS,
                                  on_button_press=self.handle_point_button,
                                  on_add_custom=lambda kind="bias": self.add_custom_point(kind),
                                  height=80, grid_cols=5, bg_color="#6a5acd")
        bias.grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(8, 0))

        self.bull_panel = bull
        self.bear_panel = bear
        self.tr_panel = tr
        self.bias_panel = bias





        # The main table/grid area (tksheet)
        tablef = ttk.Frame(self); tablef.pack(fill="both", expand=True, padx=8, pady=6)
        self.sheet = Sheet(
            tablef,
            headers=list(COLUMNS),
            data=[[""] * len(COLUMNS) for _ in BAR_ORDER],
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            width=1, height=1
        )

        self.sheet.enable_bindings((
            "single_select", "row_select", "column_select",
            "copy", "select_all",
        ))
        self.sheet.grid(row=0, column=0, sticky="nsew")
        tablef.rowconfigure(0, weight=1); tablef.columnconfigure(0, weight=1)

        # Re-equalize column widths on resize
        self.sheet.bind("<Configure>", lambda e: self._equalize_columns_to_viewport())
        self.bind("<Configure>",      lambda e: self._equalize_columns_to_viewport())

        # Selection events (fires on keyboard and mouse)
        self.sheet.extra_bindings([("cell_select", self._on_sheet_select),
                                   ("row_select",  self._on_sheet_select),
                                   ("column_select", self._on_sheet_select)])

        # Improved click handling with debouncing
        def on_sheet_click(event):
            # Debounce rapid clicks
            current_time = self.tk.call('clock', 'milliseconds')
            if current_time - self._last_click_time < 100:
                return
            self._last_click_time = current_time
            
            # Force selection update after a short delay
            self.after(50, self._process_sheet_click)
        
        # Bind to the main sheet and its components
        bind_targets = [
            self.sheet, 
            getattr(self.sheet, "MT", None), #Main Table
            getattr(self.sheet, "RI", None), #Row Index
            getattr(self.sheet, "CH", None)  #Column Headers
        ]
        
        for target in bind_targets:
            if target is not None:
                target.bind("<Button-1>", on_sheet_click, add="+")
                target.bind("<ButtonRelease-1>", 
                           lambda e: self.after(10, self._process_sheet_click), add="+")

        # Arrow keys & delete inside sheet
        self.sheet.bind("<Up>",   self._on_up_arrow)
        self.sheet.bind("<Down>", self._on_down_arrow)
        self.sheet.bind("<Delete>", self._on_delete_key)

        # Tooltip triggers
        self.sheet.bind("<Motion>", self._on_sheet_motion)
        self.sheet.bind("<Leave>",  lambda e: self._hide_sheet_tooltip())

    # --- Data initialization helper ---
    def _ensure_bar_exists(self, bar_key):
        if bar_key not in self.data:
            self.data[bar_key] = {
                "ts":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bull": [], "bear": [], "tr": [],
                "bias": []
            }

    # --- Template label helpers for buttons like "Decent bull bar()" ---
    def _is_templated_label(self, label: str) -> bool:
        return "()" in label

    def _button_base(self, label: str) -> str:
        return label.replace("()", "", 1).rstrip()

    def _format_templated_entry(self, label: str, user_text: str) -> str:
        if "()" in label:
            return label.replace("()", f"({user_text})", 1)
        return f"{label} ({user_text})"

    def _find_latest_templated_match(self, bucket, base: str):
        import re
        pattern = re.compile(rf"^{re.escape(base)}\s*\([^()]*\)\s*$")
        for idx in range(len(bucket) - 1, -1, -1):
            txt = bucket[idx]
            if isinstance(txt, str) and pattern.match(txt):
                return idx, txt
        return None

    def _any_templated_for_base_exists(self, bucket, base: str) -> bool:
        return self._find_latest_templated_match(bucket, base) is not None

    # --- Helper: force-sync last clicked/selected row from tksheet ---
    def _refresh_click_row_from_sheet(self):
        """Force-sync _click_row from the sheet's current selection immediately."""
        row = self._get_current_selected_row()
        if row is not None and 0 <= row < len(BAR_ORDER):
            self._click_row = row
            self._last_selected_row = row
            return True
        return False

    def _get_current_selected_row(self) -> int | None:
        """Get the currently selected row from multiple sources."""
        # Method 1: Get from current selection
        row = self._row_from_sheet_selection()
        
        # Method 2: If that fails, try to get from selected rows
        if row is None:
            try:
                selected_rows = self.sheet.get_selected_rows()
                if selected_rows:
                    row = int(selected_rows[0])
            except Exception:
                pass
        
        return row

    # --- Improved click processing ---
    def _process_sheet_click(self):
        """Process sheet click with robust selection detection"""
        try:
            row = self._get_current_selected_row()
            
            if row is None:
                # If no selection found, use the last known row
                row = getattr(self, '_last_selected_row', 0)
            
            # Ensure row is within valid range
            row = max(0, min(len(BAR_ORDER) - 1, int(row)))
            
            # Update both tracking variables
            self._click_row = row
            self._last_selected_row = row

            self._update_all_button_highlights_from_selection()
            
            # Update the bar combobox to reflect selection
            try:
                bar_key = BAR_ORDER[row]
                self.current_bar.set(str(bar_key))
            except Exception as e:
                print(f"[DEBUG click] error: {e}")
                    
        except Exception as e:
            print(f"[DEBUG] Error processing sheet click: {e}")

    # --- Main button handler (add vs erase with Shift) ---
    def handle_point_button(self, kind, text):
        """
        Shift = erase; normal click = add.
        For templated labels (with "()"), prompt once for extra text; prevent duplicates per base.
        """
        # Ensure we target the row most recently clicked/selected
        if not self._refresh_click_row_from_sheet():
            # If we can't get current selection, use last known
            self._click_row = self._last_selected_row

        print(f"[DEBUG handle_point_button] _click_row={self._click_row}, _target_row_index={self._target_row_index()}, bar={self._target_bar_key()}")

        templated = self._is_templated_label(text)
        bar = self._target_bar_key()
        self._ensure_bar_exists(bar)
        bucket = self.data[bar][kind]

        if self.shift_held:  # ERASE mode
            if templated:
                base = self._button_base(text)
                found = self._find_latest_templated_match(bucket, base)
                if found is None:
                    self.bell(); return
                idx, exact_txt = found
                try:
                    bucket.pop(idx)
                    self.history.append(("remove", bar, kind, exact_txt, idx))
                except Exception:
                    pass
            else:
                if text in bucket:
                    idx = bucket.index(text)
                    bucket.pop(idx)
                    self.history.append(("remove", bar, kind, text, idx))
                else:
                    self.bell(); return

            self.refresh_table(select_bar=bar)
            self._autofit_columns()
            self._schedule_autosave()
            return

        # ADD mode
        if templated:
            base = self._button_base(text)
            if self._any_templated_for_base_exists(bucket, base):
                self.bell(); return
            user_input = simpledialog.askstring("輸入內容", "請輸入補充內容：", parent=self)
            if user_input is None:
                return
            user_input = user_input.strip()
            if not user_input:
                return
            final_text = self._format_templated_entry(text, user_input)
        else:
            final_text = text

        if final_text in bucket:
            self.bell(); return

        bucket.append(final_text)
        self.history.append((bar, kind, final_text))
        self.refresh_table(select_bar=bar)
        self._autofit_columns()
        self._schedule_autosave()
        self._update_all_button_highlights_from_selection()

        print(f"[DEBUG after add] target row={self._target_row_index()}, bar={self._target_bar_key()}")

    # --- Which row are we targeting ---
    def _target_row_index(self) -> int:
        """Get the currently targeted row index."""
        # Try the live selection first (works even if _click_row hasn't updated yet)
        row = self._get_current_selected_row()
        if row is None:
            # Then fall back to last click row
            row = self._click_row
        if row is None:
            # Finally, fall back to last known selected row
            row = self._last_selected_row
        return max(0, min(len(BAR_ORDER) - 1, int(row)))


    def _target_bar_key(self) -> str:
        return BAR_ORDER[self._target_row_index()]

    # --- Simple add/remove helpers ---
    def add_point(self, kind, text):
        bar = self._target_bar_key(); self._ensure_bar_exists(bar)
        bucket = self.data[bar][kind]
        if text not in bucket:
            bucket.append(text); self.history.append((bar, kind, text))
            self.refresh_table(select_bar=bar); self._autofit_columns(); self._schedule_autosave()
        else:
            self.bell()

    def remove_point(self, kind, text):
        bar = self._target_bar_key(); self._ensure_bar_exists(bar)
        bucket = self.data[bar][kind]
        if text in bucket:
            idx = bucket.index(text); bucket.remove(text)
            self.history.append(("remove", bar, kind, text, idx))
            self.refresh_table(select_bar=bar); self._autofit_columns(); self._schedule_autosave()
        else:
            self.bell()

    def add_custom_point(self, kind):
        prompt_map = {"bull": "自定義 牛方論點", "bear": "自定義 熊方論點",
                      "tr":   "自定義 TR 論點",   "bias": "自定義 Bias"}
        text = simpledialog.askstring(prompt_map.get(kind, "自定義論點"), "輸入文字：", parent=self)
        if text: self.handle_point_button(kind, text.strip())

    def clear_current_bar(self):
        bar = self._target_bar_key()
        if bar in self.data:
            prev = self.data[bar]
            self.history.append(("clear_bar", bar, prev))
            self.data[bar] = {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bull": [], "bear": [], "tr": [], "bias": []
            }
            self.refresh_table(select_bar=bar); self._autofit_columns(); self._schedule_autosave()

    def undo_last(self):
        if not self.history:
            messagebox.showinfo("Undo", "無可撤銷紀錄。"); return
        event = self.history.pop()

        if isinstance(event, tuple) and len(event) == 3 and event[0] == "clear_bar":
            _, bar, prev = event; self.data[bar] = prev
        elif isinstance(event, tuple) and len(event) == 3:
            bar, kind, text = event
            if bar in self.data:
                bucket = self.data[bar][kind]
                if bucket and bucket[-1] == text: bucket.pop()
        elif isinstance(event, tuple) and len(event) == 5 and event[0] == "remove":
            _, bar, kind, text, idx = event
            if bar in self.data:
                bucket = self.data[bar][kind]
                idx = max(0, min(len(bucket), int(idx))); bucket.insert(idx, text)
        elif isinstance(event, tuple) and len(event) == 4 and event[0] == "clear_cell":
            _, bar, kind, prev_list = event
            if bar in self.data: self.data[bar][kind] = list(prev_list)

        self.refresh_table(select_bar=BAR_ORDER[self._last_selected_row])
        self._autofit_columns(); self._schedule_autosave()

    def new_session(self):
        if messagebox.askyesno("新 Session", "確定開始新 Session？現有未存資料將被清空。"):
            self.data.clear(); self.history.clear()
            for key in BAR_ORDER: self._ensure_bar_exists(key)
            self._last_selected_row = 0; self._click_row = 0; self.current_bar.set(str(BAR_ORDER[0]))
            self.refresh_table(select_bar=BAR_ORDER[0]); self._autofit_columns(); self._save_session_json()

    def save_csv(self):
        if not self.data: messagebox.showinfo("儲存", "沒有資料可儲存。"); return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV files", "*.csv")], title="儲存為 CSV")
        if not path: return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f); writer.writerow(COLUMNS)
            for bar in self._iter_bar_order():
                writer.writerow(self._row_of(bar))
        messagebox.showinfo("儲存", f"已儲存：{path}")

    def load_csv(self):
        path = filedialog.askopenfilename(title="載入 CSV", filetypes=[("CSV files", "*.csv")])
        if not path: return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if not row: continue
                    bar_cell = row[0].strip() if len(row) > 0 else ""
                    bar_key = self._parse_bar_key(bar_cell)
                    self._ensure_bar_exists(bar_key)
                    def split_lines(i):
                        if i < len(row) and row[i].strip():
                            return [x for x in row[i].split("\n") if x.strip()]
                        return []
                    self.data[bar_key]["bull"] = split_lines(1)
                    self.data[bar_key]["bear"] = split_lines(2)
                    self.data[bar_key]["tr"]   = split_lines(3)
                    self.data[bar_key]["bias"] = split_lines(4)
            self.history.clear()
            self.refresh_table(select_bar=BAR_ORDER[0]); self._autofit_columns(); self._schedule_autosave()
            messagebox.showinfo("載入", f"已載入：{path}")
        except Exception as e:
            messagebox.showerror("載入失敗", f"無法載入 CSV：\n{e}")
        self._update_all_button_highlights_from_selection()

    # --- Row height sizing logic ---
    def _apply_row_height(self):
        if self.auto_row_height.get():
            self._auto_row_heights()
        else:
            h = int(self.row_height.get())
            total_rows = len(BAR_ORDER)
            for r in range(total_rows):
                try: self.sheet.set_row_height(r, height=h)
                except Exception: pass
            self.sheet.refresh(); self._equalize_columns_to_viewport()

    def _set_row_height(self, h):
        self.row_height.set(h); self._apply_row_height()

    def _get_line_height_px(self) -> int:
        try:
            f = tkfont.nametofont("TkDefaultFont")
            return max(14, f.metrics("linespace") + 2)
        except Exception:
            return 16

    def _auto_row_heights(self):
        i_bull = COL_INDEX["Bull"]; i_bear = COL_INDEX["Bear"]; i_tr = COL_INDEX["TR"]; i_bias = COL_INDEX["Bias"]
        line_h = self._get_line_height_px()
        pad_top_bottom = 6; min_h = 22; max_h = 320

        for r, bar in enumerate(self._iter_bar_order()):
            row = self._row_of(bar)
            n_bull = row[i_bull].count("\n") + 1 if row[i_bull] else 1
            n_bear = row[i_bear].count("\n") + 1 if row[i_bear] else 1
            n_tr   = row[i_tr].count("\n")   + 1 if row[i_tr]   else 1
            n_bias = row[i_bias].count("\n") + 1 if row[i_bias] else 1
            n = max(n_bull, n_bear, n_tr, n_bias)
            height = min(max_h, max(min_h, pad_top_bottom + n * line_h))
            try: self.sheet.set_row_height(r, height=height)
            except Exception: pass

        self.sheet.refresh(); self._equalize_columns_to_viewport()

    # --- Bar id parsing + iteration helpers ---
    def _parse_bar_key(self, s):
        if isinstance(s, str):
            s_up = s.strip().upper()
            if s_up in ("RTH", "ETH"): return s_up
            try:
                n = int(s_up); return max(1, min(81, n))
            except ValueError:
                return "RTH"
        elif isinstance(s, int):
            return max(1, min(81, s))
        return "RTH"

    def _get_bar(self): return self._parse_bar_key(self.current_bar.get())
    def _set_bar(self, bar_key): self.current_bar.set(str(bar_key)); self._ensure_bar_exists(bar_key)
    def _iter_bar_order(self):
        for b in BAR_ORDER: yield b

    def _index_in_order(self, bar_key):
        try: return BAR_ORDER.index(bar_key)
        except ValueError:
            try: return BAR_ORDER.index(int(bar_key))
            except Exception: return 0

    # --- Selection helpers ---
    def _select_row(self, row_index: int):
        row_index = max(0, min(len(BAR_ORDER) - 1, int(row_index)))
        try:
            self.sheet.select_row(row_index, redraw=True)
            self.sheet.see(row_index, 0)
        except Exception:
            pass
        self._last_selected_row = row_index
        self._click_row = row_index  # Also update click row
        try: self.current_bar.set(str(BAR_ORDER[row_index]))
        except Exception: pass

    def _force_row_selection(self, row: int):
        if row == getattr(self, "_last_selected_row", None): return
        try: self.sheet.deselect("all")
        except Exception: pass
        try:
            self.sheet.select_row(row, redraw=True)
            try:    self.sheet.set_currently_selected(row=row, column=0, type_="row")
            except TypeError: self.sheet.set_currently_selected(("row", row))
        except Exception: pass
        self._last_selected_row = row
        self._click_row = row  # Also update click row
        try: self.current_bar.set(str(BAR_ORDER[row]))
        except Exception: pass

    def prev_bar(self):
        idx = self._target_row_index(); self._select_row(idx - 1)

    def next_bar(self):
        idx = self._target_row_index(); self._select_row(idx + 1)

    # --- Keyboard handlers for arrows ---
    def _on_up_arrow(self, event):
        self.prev_bar(); return "break"

    def _on_down_arrow(self, event):
        self.next_bar(); return "break"

    # --- Delete-key handler: clear selected cells in editable columns ---
    def _on_delete_key(self, event=None):
        cells = []
        try: cells = list(self.sheet.get_selected_cells())
        except Exception: pass

        if not cells:
            cur = self.sheet.get_currently_selected()
            if isinstance(cur, tuple) and cur and cur[0] == "cell" and len(cur) >= 3:
                cells = [(int(cur[1]), int(cur[2]))]

        if not cells:
            self.bell(); return "break"

        changed_any = False
        touched = set()
        for (r, c) in cells:
            if (r, c) in touched: continue
            touched.add((r, c))
            if c not in KINDS_BY_COL: continue
            if r < 0 or r >= len(BAR_ORDER): continue

            bar_key = BAR_ORDER[r]; kind = KINDS_BY_COL[c]
            self._ensure_bar_exists(bar_key)
            bucket = self.data[bar_key][kind]
            if not bucket: continue

            prev_snapshot = list(bucket)
            self.history.append(("clear_cell", bar_key, kind, prev_snapshot))
            self.data[bar_key][kind] = []
            changed_any = True

        if changed_any:
            self.refresh_table(select_bar=BAR_ORDER[self._last_selected_row])
            self._autofit_columns(); self._schedule_autosave()
        else:
            self.bell()
        return "break"

    # --- Convert internal data to a row tuple for the grid ---
    def _row_of(self, bar):
        item = self.data[bar]
        bull = "\n".join(item["bull"])
        bear = "\n".join(item["bear"])
        tr   = "\n".join(item["tr"])
        bias = "\n".join(item["bias"])
        return (bar, bull, bear, tr, bias)

    def refresh_table(self, select_bar=None):
        rows = [list(self._row_of(bar)) for bar in self._iter_bar_order()]
        self.sheet.set_sheet_data(rows, reset_col_positions=True, reset_row_positions=True)

        # Colorize non-empty columns
        i_bull = COL_INDEX["Bull"]; i_bear = COL_INDEX["Bear"]; i_tr = COL_INDEX["TR"]
        self.sheet.dehighlight_all()
        for r, row in enumerate(rows):
            if row[i_bull]: self.sheet.highlight_cells(row=r, column=i_bull, fg="green")
            if row[i_bear]: self.sheet.highlight_cells(row=r, column=i_bear, fg="red")
            if row[i_tr]:   self.sheet.highlight_cells(row=r, column=i_tr,   fg="blue")

        #self._apply_row_height()
        self._autofit_columns()

        # Restore selection
        if select_bar is None:
            row_index = self._last_selected_row
        else:
            try: row_index = self._index_in_order(select_bar)
            except Exception: row_index = 0
        self._select_row(row_index)
        self._update_all_button_highlights_from_selection()


    def _on_sheet_select(self, event=None):
        """Handle selection changes from keyboard or mouse"""
        row = self._row_from_sheet_selection()
        if row is not None:
            self._click_row = int(row)
            self._last_selected_row = int(row)
            self._update_all_button_highlights_from_selection()
            
            # Update UI to reflect new selection
            try:
                bar_key = BAR_ORDER[self._click_row]    #looks up the bar identifier 

                self.current_bar.set(str(bar_key))  # update the bounding UI to point to the selection

            except Exception as e:
                print(f"[DEBUG select] error: {e}")

    def _row_from_sheet_selection(self) -> int | None:
        cur = self.sheet.get_currently_selected()
        # New style: Selected object with attributes
        if cur and hasattr(cur, "row"):
            try:
                return int(cur.row)
            except Exception:
                pass

    # --- Column sizing helpers ---
    def _autofit_columns(self):
        try: self.sheet.set_all_cell_sizes_to_text(redraw=False)
        except Exception: pass
        self.sheet.refresh(); self._equalize_columns_to_viewport()


    def _visible_data_area_width(self) -> int:
        try: self.sheet.update_idletasks()
        except Exception: pass
        w = max(0, int(self.sheet.winfo_width()))
        idx_w = 0
        try: idx_w = int(getattr(self.sheet.MT, "index_width", 0))
        except Exception: pass
        vsb_w = 0
        try:
            if hasattr(self.sheet, "v_scrollbar") and self.sheet.v_scrollbar.winfo_ismapped():
                vsb_w = int(self.sheet.v_scrollbar.winfo_width())
        except Exception: pass
        padding = 4
        return max(0, w - idx_w - vsb_w - padding)

    def _equalize_columns_to_viewport(self,
                                      min_other=80,
                                      bar_ratio=0.5,
                                      min_bar=40):
        if self._resizing_columns: return
        self._resizing_columns = True
        try:
            data_w = self._visible_data_area_width()
            n = len(COLUMNS)
            if n <= 0 or data_w <= 0: return

            other_count = n - 1
            if other_count <= 0: return

            denom = other_count + bar_ratio
            unit = max(1, int(data_w // denom))

            bar_w = max(min_bar, int(unit * bar_ratio))
            bar_w = min(bar_w, max(1, data_w - other_count))
            try: self.sheet.column_width(0, width=bar_w)
            except Exception: pass

            remaining_w = max(0, data_w - bar_w)
            base = max(min_other, remaining_w // other_count)
            if base * other_count > remaining_w:
                base = max(1, remaining_w // other_count)

            for idx in range(1, n - 1):
                try: self.sheet.column_width(idx, width=base)
                except Exception: pass

            try: self.sheet.column_width(n - 1, width=max(1, remaining_w - base * (other_count - 1)))
            except Exception: pass

            self.sheet.refresh()
        finally:
            self._resizing_columns = False

    # --- Tooltip show/hide ---
    def _hide_sheet_tooltip(self):
        self._tooltip.hide()
        self._tip_visible_for = None

    def _on_sheet_motion(self, event):
        try:
            r, c = self.sheet.identify_row(event.y), self.sheet.identify_col(event.x)
        except Exception:
            return

        if r is not None and 0 <= int(r) < len(BAR_ORDER):
            self._hover_row = int(r)

        if r is None or c is None:
            self._hide_sheet_tooltip(); return
        if c not in (COL_INDEX["Bull"], COL_INDEX["Bear"], COL_INDEX["TR"], COL_INDEX["Bias"]):
            self._hide_sheet_tooltip(); return

        try: text = self.sheet.get_cell_data(r, c) or ""
        except Exception: text = ""
        if not text.strip():
            self._hide_sheet_tooltip(); return

        key = (r, c)
        if self._tip_visible_for == key: return

        x_root = self.sheet.winfo_rootx() + event.x
        y_root = self.sheet.winfo_rooty() + event.y
        self._tooltip.schedule(x_root, y_root, key, text)
        self._tip_visible_for = key

    #def _match_labels_generic(self, points_list: list[str], lines: list[str]) -> set[str]:
    ##Given list of strings from the Bull cell, return the set of button labels (from BULL_POINTS)
    ##that are considered 'present'. Template labels like 'Decent bull bar()' match any line
    ##starting with the base and a (...) suffix."""
        
    #    present = set()
    #    # Precompute bases for templated bull labels
    #    templated = {}
    #    for lbl in points_list:
    ##        if "()" in lbl:
    #            base = lbl.replace("()", "").strip()
    #            templated[lbl] = base

        # Normalize each line from the cell
    #    for raw in lines:
    #        s = (raw or "").strip()
    #        if not s:
    #            continue
    #        # 1) Exact match to any bull label
    #        if s in points_list:
    #            present.add(s); continue
    #        # 2) Template match: line begins with base and has (...) at the end
    #        for lbl, base in templated.items():
    #            if s.startswith(base) and s.endswith(")") and "(" in s:
    #                present.add(lbl)
    #                break
    #    return present

    def _match_labels_generic(self, points_list: list[str], lines: list[str]) -> tuple[set[str], bool]:
        """
        Returns (matched_labels, has_custom).
        - matched_labels: set of button labels from points_list that are considered present.
        - has_custom: True if there exists any non-empty line that does NOT match any button (including templates).
        """
        matched = set()
        has_custom = False

        # Precompute templated bases: "X()" -> "X"
        templated = {}
        for lbl in points_list:
            if "()" in lbl:
                templated[lbl] = lbl.replace("()", "").strip()

        for raw in lines:
            s = (raw or "").strip()
            if not s:
                continue

            # Exact match?
            if s in points_list:
                matched.add(s)
                continue

            # Template match?  e.g., "Decent bear bar(inside)" matches "Decent bear bar()"
            hit = False
            for lbl, base in templated.items():
                if s.startswith(base) and "(" in s and s.endswith(")"):
                    matched.add(lbl)
                    hit = True
                    break

            if not hit:
                # Non-empty line that didn't match any label → custom
                has_custom = True

        return matched, has_custom


    # --- Helper: map kind → (points_list, panel_attr_name, data_key) ---
    def _kind_spec(self, kind: str):
        from constants import BULL_POINTS, BEAR_POINTS, TR_POINTS, BIAS_POINTS
        if kind == "bull": return (BULL_POINTS, "bull_panel", "bull")
        if kind == "bear": return (BEAR_POINTS, "bear_panel", "bear")
        if kind == "tr":   return (TR_POINTS,   "tr_panel",   "tr")
        if kind == "bias": return (BIAS_POINTS, "bias_panel", "bias")
        return (None, None, None)



    # --- Update highlights on the Bull buttons based on current selection ---
#    def _update_button_highlights_for_kind(self, kind: str):
#        try:
#            from constants import BAR_ORDER
#            points, panel_attr, data_key = self._kind_spec(kind)
#            if not points or not panel_attr or not data_key:
#                return
#
#            # Which row?
#            row = self._get_current_selected_row()
#            if row is None:
#                row = getattr(self, "_last_selected_row", None)
#            if row is None:
#                return

#            row = max(0, min(len(BAR_ORDER) - 1, int(row)))
#            bar_key = BAR_ORDER[row]
#            self._ensure_bar_exists(bar_key)

#            # Lines in that cell (model is already list[str])
#            bucket = self.data[bar_key][data_key]
#            lines  = [str(x) for x in bucket]

#            labels = self._match_labels_generic(points, lines)

#            panel = getattr(self, panel_attr, None)
#            if panel is not None:
#                panel.set_highlighted_labels(labels, color="yellow")

#        except Exception as e:
#            print(f"[DEBUG] highlight update ({kind}) error: {e}")

    def _update_button_highlights_for_kind(self, kind: str):
        try:
            from constants import BAR_ORDER, BULL_POINTS, BEAR_POINTS, TR_POINTS, BIAS_POINTS
            def kind_spec(k):
                return {
                    "bull": (BULL_POINTS, "bull_panel", "bull"),
                    "bear": (BEAR_POINTS, "bear_panel", "bear"),
                    "tr":   (TR_POINTS,   "tr_panel",   "tr"),
                    "bias": (BIAS_POINTS, "bias_panel", "bias"),
                }.get(k, (None, None, None))

            points, panel_attr, data_key = kind_spec(kind)
            if not points or not panel_attr or not data_key:
                return

            # Which row?
            row = self._get_current_selected_row()
            if row is None:
                row = getattr(self, "_last_selected_row", None)
            if row is None:
                return

            row = max(0, min(len(BAR_ORDER) - 1, int(row)))
            bar_key = BAR_ORDER[row]
            self._ensure_bar_exists(bar_key)

            bucket = self.data[bar_key][data_key]   # list[str]
            lines  = [str(x) for x in bucket]

            matched_labels, has_custom = self._match_labels_generic(points, lines)

            panel = getattr(self, panel_attr, None)
            if panel is not None:
                # Reset + highlight matches
                panel.set_highlighted_labels(matched_labels, color="yellow")
                # Illuminate "+ 自定義" if there are unmatched lines
                panel.set_custom_highlight(has_custom, color="yellow")

        except Exception as e:
            print(f"[DEBUG] highlight update ({kind}) error: {e}")




    # --- Update all four kinds at once (called after selection or data change) ---
    def _update_all_button_highlights_from_selection(self):
        for kind in ("bull", "bear", "tr", "bias"):
            self._update_button_highlights_for_kind(kind)



    def _manual_autofit_rows(self):
        self._autofit_columns()

    def _open_preset_editor(self, kind: str):
        mapping = {
            "bull": ("編輯 牛方論點（BULL）", CONST.BULL_POINTS),
            "bear": ("編輯 熊方論點（BEAR）", CONST.BEAR_POINTS),
            "tr":   ("編輯 TR 論點（TR）",   CONST.TR_POINTS),
            "bias": ("編輯 Bias 論點（BIAS）", CONST.BIAS_POINTS),
        }
        title, store = mapping[kind]
        dlg = PresetEditor(self, title, list(store))
        self.wait_window(dlg)
        if dlg.result is not None:
            store[:] = dlg.result
            self._save_presets()
            self._rebuild_point_panels(kind)
            messagebox.showinfo("已更新", f"{title} 已更新。")

        # --- Preset persistence helpers ---
    def _load_presets_and_apply(self):
        """Load presets.json if it exists and overwrite constants lists."""
        try:
            if hasattr(self, "_presets_path") and self._presets_path.exists():
                data = json.loads(self._presets_path.read_text(encoding="utf-8"))
                bull = data.get("bull_points")
                bear = data.get("bear_points")
                tr   = data.get("tr_points")
                bias = data.get("bias_points")
                if isinstance(bull, list):
                    CONST.BULL_POINTS[:] = [str(x) for x in bull]
                if isinstance(bear, list):
                    CONST.BEAR_POINTS[:] = [str(x) for x in bear]
                if isinstance(tr, list):
                    CONST.TR_POINTS[:] = [str(x) for x in tr]
                if isinstance(bias, list):
                    CONST.BIAS_POINTS[:] = [str(x) for x in bias]
        except Exception as e:
            print(f"[WARN] failed to load presets.json: {e}")

    def _save_presets(self):
        """Save current constants lists into presets.json."""
        data = {
            "bull_points": list(CONST.BULL_POINTS),
            "bear_points": list(CONST.BEAR_POINTS),
            "tr_points":   list(CONST.TR_POINTS),
            "bias_points": list(CONST.BIAS_POINTS),
        }
        try:
            self._presets_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            return True
        except Exception as e:
            messagebox.showerror("Save failed", f"Could not write presets.json:\n{e}")
            return False
        
    def _rebuild_point_panels(self, kind: str):
        """
        依照 kind (bull/bear/tr/bias) 重建對應的按鈕面板：
        - 保留原來的 grid 位置
        - 使用目前 constants (CONST.*_POINTS) 的清單
        """
        mapping = {
            "bull": ("bull_panel", "🐂 牛方論點", CONST.BULL_POINTS, 170, 2, "#2e8b57"),
            "bear": ("bear_panel", "🐻 熊方論點", CONST.BEAR_POINTS, 170, 2, "#b22222"),
            "tr":   ("tr_panel",   "〰️ TR 論點",  CONST.TR_POINTS,   170, 2, "#1e90ff"),
            "bias": ("bias_panel", "🎯 Bias 論點", CONST.BIAS_POINTS,  80, 5, "#6a5acd"),
        }
        panel_attr, title, items, height, grid_cols, bg = mapping[kind]

        # 取出舊面板
        old_panel = getattr(self, panel_attr, None)
        if old_panel is None:
            # 若面板尚未建立（理論上不會發生），直接略過
            return

        info = old_panel.grid_info()
        parent = old_panel.master
        old_panel.destroy()

        # 建立新面板
        new_panel = _ScrollableButtons(
            parent, title, kind, items,
            on_button_press=self.handle_point_button,
            on_add_custom=lambda kind=kind: self.add_custom_point(kind),
            height=height, grid_cols=grid_cols, bg_color=bg
        )
        new_panel.grid(**info)

        # 回寫屬性
        setattr(self, panel_attr, new_panel)

    def _reset_presets_confirm(self):
        """恢復 constants.py 原廠詞庫，並重建四個面板。"""
        if messagebox.askyesno("重設詞庫", "把詞庫恢復到 constants.py 的原始預設？"):
            from importlib import reload
            import constants as _C
            reload(_C)
            # 覆寫目前運行中的清單（就地更新）
            CONST.BULL_POINTS[:] = list(_C.BULL_POINTS)
            CONST.BEAR_POINTS[:] = list(_C.BEAR_POINTS)
            CONST.TR_POINTS[:]   = list(_C.TR_POINTS)
            CONST.BIAS_POINTS[:] = list(_C.BIAS_POINTS)
            self._save_presets()
            for k in ("bull", "bear", "tr", "bias"):
                self._rebuild_point_panels(k)
            messagebox.showinfo("已重設", "詞庫已恢復為原始預設。")






# ===== Preset Editor Dialog =====
class PresetEditor(tk.Toplevel):
    def __init__(self, master, title: str, items: list[str]):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.items = list(items)

        frm = ttk.Frame(self); frm.pack(fill="both", expand=True, padx=10, pady=10)
        self.listbox = tk.Listbox(frm, height=12)
        self.listbox.grid(row=0, column=0, rowspan=6, sticky="nsew")
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, rowspan=6, sticky="ns")

        btns = ttk.Frame(frm); btns.grid(row=0, column=2, rowspan=6, sticky="ns", padx=(8,0))
        ttk.Button(btns, text="新增…", command=self._add).pack(fill="x", pady=2)
        ttk.Button(btns, text="編輯…", command=self._edit).pack(fill="x", pady=2)
        ttk.Button(btns, text="刪除", command=self._delete).pack(fill="x", pady=2)
        ttk.Separator(btns, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(btns, text="上移", command=lambda: self._move(-1)).pack(fill="x", pady=2)
        ttk.Button(btns, text="下移", command=lambda: self._move(+1)).pack(fill="x", pady=2)
        ttk.Separator(btns, orient="horizontal").pack(fill="x", pady=6)
        action = ttk.Frame(frm); action.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(8,0))
        ttk.Button(action, text="取消", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(action, text="儲存", command=self._ok).pack(side="right")

        frm.columnconfigure(0, weight=1)
        self._refresh()

        self.result = None
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

    def _refresh(self):
        self.listbox.delete(0, tk.END)
        for it in self.items:
            self.listbox.insert(tk.END, it)

    def _ask_text(self, title, initial=""):
        from tkinter import simpledialog
        return simpledialog.askstring(title, "輸入文字（可包含 () 作為提示輸入模板）:", initialvalue=initial, parent=self)

    def _add(self):
        s = self._ask_text("新增詞條")
        if s:
            self.items.append(s); self._refresh()

    def _edit(self):
        i = self.listbox.curselection()
        if not i: return
        idx = i[0]
        s = self._ask_text("編輯詞條", self.items[idx])
        if s:
            self.items[idx] = s
            self._refresh(); self.listbox.selection_set(idx)

    def _delete(self):
        i = self.listbox.curselection()
        if not i: return
        idx = i[0]
        del self.items[idx]
        self._refresh()

    def _move(self, delta):
        i = self.listbox.curselection()
        if not i: return
        idx = i[0]; j = idx + delta
        if j < 0 or j >= len(self.items): return
        self.items[idx], self.items[j] = self.items[j], self.items[idx]
        self._refresh()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(j)

    def _ok(self):
        self.result = list(self.items); self.destroy()

    def _cancel(self):
        self.result = None; self.destroy()