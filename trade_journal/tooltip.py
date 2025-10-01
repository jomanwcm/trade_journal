# tooltip.py — line-by-line annotated walkthrough
# (Tiny helper class that shows a delayed tooltip near the mouse pointer)

import tkinter as tk
from tkinter import ttk

class _Tooltip:
    """Simple delayed tooltip balloon for widgets."""
    def __init__(self, widget, delay_ms=400, wrap_px=520, padx=10, pady=8):
        self.widget = widget                # parent widget for scheduling with .after(...)
        self.delay_ms = delay_ms            # delay before showing tooltip (ms)
        self.wrap_px = wrap_px              # wrap width for long text
        self.padx = padx; self.pady = pady  # padding inside tooltip
        self._tip = None                    # Toplevel window when visible
        self._after_id = None               # timer id for pending show
        self._current_key = None            # track (row, col) to avoid re-showing same
        self._last_text = None              # cache last text

    def schedule(self, x_root, y_root, key, text):
        # Ask to show a tooltip (after delay). If it's already showing the same one, do nothing.
        if self._current_key == key and self._tip and self._last_text == text:
            return
        self.cancel()                       # cancel any previous pending show
        self._current_key = key
        self._last_text = text
        self._after_id = self.widget.after(self.delay_ms, lambda: self._show(x_root, y_root, text))

    def _show(self, x_root, y_root, text):
        # Create a small borderless window near (x_root, y_root) and put a wrapped label inside.
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)        # no OS window decorations
        tw.wm_geometry(f"+{x_root + 12}+{y_root + 18}")  # offset a bit from cursor
        frame = ttk.Frame(tw, borderwidth=1, relief="solid")
        frame.pack(fill="both", expand=True)
        label = ttk.Label(frame, text=text, justify="left", wraplength=self.wrap_px)
        label.pack(padx=self.padx, pady=self.pady)

    def cancel(self):
        # Cancel a scheduled show if it hasn't happened yet.
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def hide(self):
        # Hide and destroy the tooltip window, and reset keys.
        self.cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
        self._current_key = None
        self._last_text = None
