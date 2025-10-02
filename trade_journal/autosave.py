# autosave.py — line-by-line annotated walkthrough
# (Mixin that adds autosave/restore of session data to a JSON file.)
# Now portable: saves to ./sessions/session.json (project-relative) by default,
# with an environment-variable override and a safe fallback to the OS temp folder.

import os
import json
import tempfile
from pathlib import Path


class AutosaveMixin:
    """Provides session autosave/restore for JournalApp.

    Expects the consuming class to provide:
      - self.after(...) and self.after_cancel(...)  (Tk scheduling)
      - self.data (dict-like mapping bar_key -> dict with lists)
    """

    def _autosave_path(self) -> str:
        """
        Resolve the autosave JSON path.

        Priority:
          1) TRADE_JOURNAL_SESSION_PATH (env var) — absolute or relative; dirs auto-created
          2) ./sessions/session.json — project-relative (next to this file)
          3) OS temp dir — fallback, same as the original behavior
        """
        # 1) Explicit override via environment variable
        env = os.getenv("TRADE_JOURNAL_SESSION_PATH")
        if env:
            p = Path(env).expanduser().resolve()
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                return str(p)
            except Exception:
                # if parent can't be created, fall through to next options
                pass

        # 2) Project-relative default: ./sessions/session.json (portable with git)
        try:
            base_dir = Path(__file__).resolve().parent
            sess_dir = base_dir / "sessions"
            sess_dir.mkdir(parents=True, exist_ok=True)
            return str(sess_dir / "session.json")
        except Exception:
            # if project path isn't writable (e.g., read-only media), fall back
            pass

        # 3) Fallback: OS temp directory (original behavior)
        return os.path.join(tempfile.gettempdir(), "pa_click_journal_autosave.json")

    def _schedule_autosave(self, delay_ms: int = 500):
        # Debounce: cancel prior timer and set a new one so rapid changes don't spam disk.
        try:
            if hasattr(self, "_autosave_after_id") and self._autosave_after_id:
                self.after_cancel(self._autosave_after_id)
        except Exception:
            pass
        self._autosave_after_id = self.after(delay_ms, self._save_session_json)

    def _save_session_json(self):
        # Persist the entire self.data dict to JSON. Any error is ignored silently.
        try:
            with open(self._autosave_path(), "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_session_json(self, BAR_ORDER):
        # Attempt to read the saved JSON and merge into current self.data.
        try:
            p = self._autosave_path()
            if not os.path.exists(p):
                return False
            with open(p, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            # Ensure all bars exist, then copy lists/timestamps if present.
            for key in BAR_ORDER:
                if key not in self.data:
                    self.data[key] = {"ts": "", "bull": [], "bear": [], "tr": [], "bias": []}
                # handle both string and int keys
                rec = loaded.get(str(key), loaded.get(key, None))
                if isinstance(rec, dict):
                    for k in ("bull", "bear", "tr", "bias"):
                        if isinstance(rec.get(k), list):
                            self.data[key][k] = list(rec[k])
                    if isinstance(rec.get("ts"), str):
                        self.data[key]["ts"] = rec["ts"]
            return True
        except Exception:
            return False
