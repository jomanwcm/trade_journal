# scrollable_buttons.py — line-by-line annotated walkthrough
# (Reusable scrollable panel that renders a grid of buttons)

import tkinter as tk
from tkinter import ttk

class _ScrollableButtons(ttk.LabelFrame):  # A titled frame with a scrollable button area

    # parameter explanation:
    # master: parent widget
    # title: text shown in the LabelFrame's title area
    # kind: category key ("bull"| "bear"|"tr"|"bias"), carried through to callbacks
    # items: list of button labels to render
    # on_button_press(kind, text): callback when a preset button is clicked
    # on_add_custom(kind): callback when "+ 自定義" is clicked.
    # height: visible height of the scrollable area (not the total content height)
    # grid_cols: how many columns of buttons in the inner grid
    # bg_color: optional accent color for the panel's title bar/background (via ttk Styles)
    def __init__(self, master, title, kind, items, on_button_press, on_add_custom,
                 height=260, grid_cols=2, bg_color=None):
        self.kind = kind                             # category id: 'bull' | 'bear' | 'tr' | 'bias'
        style_name  = f"{kind}.TLabelframe"          # unique ttk style name per panel
        label_style = f"{kind}.TLabelframe.Label"    # style for the title label

        self._btn_by_label = {}                      # New: map label text -> button widget
        self._btn_default_bg = {}                    # New: per-button original background (for reset)   


        style = ttk.Style()
        #if bg_color is provided, then use the custom color, otherwise just use default ttk theme colors
        if bg_color:
            style.configure(style_name, background=bg_color)                 # panel background
            style.configure(label_style, background=bg_color, foreground="white")  # title text color

        # Build the labeled frame container itself.
        super().__init__(master, text=title, style=style_name)
        self.on_button_press = on_button_press        # callback for preset buttons
        self.on_add_custom  = on_add_custom           # callback for the "+ 自定義…" button
        self.grid_cols = max(1, int(grid_cols))       # how many columns inside the panel grid

        # Canvas + vertical scrollbar (classic scrollable-frame pattern).
        #joman: create a Canvas (Canvas is used, together with scrollbars for scrollable regions)
        self._canvas = tk.Canvas(self, highlightthickness=0, background=bg_color)
        self._vsb    = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        #joman: canvas in column 0, scrollbar in the column besides
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)               # allow canvas to expand
        self.columnconfigure(0, weight=1)

        # Real inner frame that holds the grid of buttons.
        self._inner = ttk.Frame(self._canvas, style=style_name)
        self._win   = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")

        # Create each preset button and place it in a grid (r, c) based on index.
        for i, txt in enumerate(items):
            r, c = divmod(i, self.grid_cols)
            #btn = ttk.Button(self._inner, text=txt,
            #                 command=lambda t=txt: self.on_button_press(self.kind, t))
            btn = tk.Button(self._inner, text = txt, command=lambda t=txt: self.on_button_press(self.kind, t), wraplength=220, relief="raised")
            btn.grid(row=r, column=c, sticky="ew", padx=4, pady=4)
            self._btn_by_label[txt] = btn
            try:
                self._btn_default_bg[txt] = btn.cget("bg")
            except:
                self._btn_default_bg[txt] = None

        # Make columns inside the inner frame stretch evenly.
        for c in range(self.grid_cols):
            self._inner.columnconfigure(c, weight=1, uniform="btncols")

        # A full-width "+ 自定義…" button to add user-defined items.
        last_row = (len(items) + self.grid_cols - 1) // self.grid_cols
        self._custom_btn = tk.Button(self._inner, text="＋ 自定義…",
                   command=lambda: self._add_custom(), relief="raised"
        )
        self._custom_btn.grid(row=last_row, column=0, columnspan=self.grid_cols, sticky="ew", padx=4, pady=(6, 8))

        self._custom_default_bg = self._custom_btn.cget("bg")

        # Fix the panel's visible height; scrollbar appears if content exceeds this.
        self._canvas.configure(height=height)

        # Keep scrollregion and inner width synchronized with content and canvas size.
        self._inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Mouse wheel scrolling (Windows/macOS: <MouseWheel>; Linux: Button-4/5).
        self._canvas.bind("<Enter>", lambda e: self._canvas.focus_set())
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>",   self._on_mousewheel)
        self._canvas.bind("<Button-5>",   self._on_mousewheel)

    def _on_inner_configure(self, _e):
        # Update the scrollable region to include the entire inner frame.
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        # Make the inner frame match the canvas width so buttons fill horizontally.
        self._canvas.itemconfigure(self._win, width=event.width)

    def _add_custom(self):
        # Delegate to the app, informing which kind this panel represents.
        self.on_add_custom(self.kind)

    def _on_mousewheel(self, event):
        # Normalize different OS wheel events into canvas yview scroll.
        if getattr(event, "num", None) == 4:   # Linux scroll up
            self._canvas.yview_scroll(-3, "units"); return "break"
        if getattr(event, "num", None) == 5:   # Linux scroll down
            self._canvas.yview_scroll(3, "units");  return "break"
        step = -1 if event.delta > 0 else 1    # Windows/macOS sign
        self._canvas.yview_scroll(step * 3, "units")
        return "break"


    def set_highlighted_labels(self, labels_to_highlight: set[str], color: str = "yellow"):
        #Highlight only the given labels; reset others. labels_to_highlight are exact button texts
        # Reset all first
        for text, btn in self._btn_by_label.items():
            self._reset_button_bg(btn, text)
        # Then apply highlight
        for text in labels_to_highlight:
            btn = self._btn_by_label.get(text)
            if btn:
                self._set_button_bg(btn, color)

    def _set_button_bg(self, btn, color: str):
        """Best-effort background change for tk/ttk buttons."""
        try:
            btn.configure(bg=color, activebackground=color, highlightbackground=color)
            return
        except Exception:
            pass
        # ttk fallback: try style
        try:
            import tkinter.ttk as ttk
            style = ttk.Style(btn)
            style_name = f"{str(id(btn))}.TButton"
            style.configure(style_name, background=color, fieldbackground=color)
            btn.configure(style=style_name)
        except Exception:
            # last resort: change text marker
            try:
                if not btn.cget("text").startswith("⭐ "):
                    btn.configure(text="⭐ " + btn.cget("text"))
            except Exception:
                pass

    def _reset_button_bg(self, btn, text: str):
        """Reset to original background or remove star marker."""
        default = self._btn_default_bg.get(text)
        try:
            if default is not None:
                btn.configure(bg=default, activebackground=default, highlightbackground=default)
            # remove any accidental star marker
            t = btn.cget("text")
            if t.startswith("⭐ "):
                btn.configure(text=t[2:])
        except Exception:
            # ttk style fallback: leave as-is (or you could re-assign a default style)
            pass


    def set_custom_highlight(self, active: bool, color: str = "yellow"):
        """Turn highlight on/off for the '+ 自定義' button."""
        if not hasattr(self, "_custom_btn") or self._custom_btn is None:
            return
        try:
            if active:
                self._custom_btn.configure(bg=color, activebackground=color, highlightbackground=color)
            else:
                self._custom_btn.configure(
                    bg=self._custom_default_bg,
                    activebackground=self._custom_default_bg,
                    highlightbackground=self._custom_default_bg
                )
        except Exception:
            pass

    def set_highlighted_labels(self, labels_to_highlight: set[str], color: str = "yellow"):
        # Reset all presets
        for text, btn in self._btn_by_label.items():
            self._reset_button_bg(btn, text)
        # Default: custom off (caller can turn it on after)
        self.set_custom_highlight(False)
        # Highlight matches
        for text in labels_to_highlight:
            btn = self._btn_by_label.get(text)
            if btn:
                self._set_button_bg(btn, color)

