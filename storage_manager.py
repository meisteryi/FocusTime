"""
FocusTime - Local Storage Manager
Persists user favorites (playlists/tracks) and daily focus statistics in local JSON (`focus_data.json`).
"""

import json
import os
import re
from datetime import datetime, timedelta


class StorageManager:
    def __init__(self, filepath: str = None):
        if filepath is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(base_dir, "focus_data.json")
        self.filepath = filepath
        self.data = {
            "favorites": [],
            "daily_focus": {}
        }
        self.load()

    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self.data["favorites"] = loaded.get("favorites", [])
                        self.data["daily_focus"] = loaded.get("daily_focus", {})
            except Exception:
                pass

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def _extract_id(track: dict) -> str:
        if track.get("id"):
            return track["id"]
        url = track.get("url", "")
        m = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', url)
        return m.group(1) if m else url

    # --- Favorites Management ---
    def get_favorites(self) -> list:
        return list(self.data.get("favorites", []))

    def is_favorite(self, track: dict) -> bool:
        if not track:
            return False
        target_id = self._extract_id(track)
        if not target_id:
            return False
        return any(self._extract_id(f) == target_id for f in self.data["favorites"])

    def add_favorite(self, track: dict) -> bool:
        if not track:
            return False
        if self.is_favorite(track):
            return False
        vid_id = self._extract_id(track)
        entry = {
            "id": vid_id,
            "title": track.get("title", "Unknown Track"),
            "url": track.get("url") or (f"https://www.youtube.com/watch?v={vid_id}" if len(vid_id) == 11 else ""),
            "uploader": track.get("uploader", "Unknown Artist"),
            "duration": track.get("duration", "")
        }
        self.data["favorites"].insert(0, entry)
        self.save()
        return True

    def remove_favorite(self, track: dict) -> bool:
        if not track:
            return False
        target_id = self._extract_id(track)
        before = len(self.data["favorites"])
        self.data["favorites"] = [f for f in self.data["favorites"] if self._extract_id(f) != target_id]
        if len(self.data["favorites"]) != before:
            self.save()
            return True
        return False

    def toggle_favorite(self, track: dict) -> bool:
        """Toggles favorite state and returns new state (True if added, False if removed)"""
        if self.is_favorite(track):
            self.remove_favorite(track)
            return False
        else:
            self.add_favorite(track)
            return True

    # --- Daily Focus Statistics ---
    @staticmethod
    def _today_key() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _yesterday_key() -> str:
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    def add_focus_second(self, seconds: int = 1):
        key = self._today_key()
        self.data["daily_focus"][key] = self.data["daily_focus"].get(key, 0) + seconds

    def get_today_seconds(self) -> int:
        return int(self.data["daily_focus"].get(self._today_key(), 0))

    def get_yesterday_seconds(self) -> int:
        return int(self.data["daily_focus"].get(self._yesterday_key(), 0))

    @staticmethod
    def format_duration(total_seconds: int) -> str:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        if h > 0:
            return f"{h}시간 {m:02d}분"
        elif m > 0:
            return f"{m}분 {s:02d}초"
        else:
            return f"{s}초"

    def get_today_summary_text(self) -> str:
        today_sec = self.get_today_seconds()
        yest_sec = self.get_yesterday_seconds()
        today_str = self.format_duration(today_sec)

        if yest_sec == 0:
            return f"📊 오늘 총 {today_str} 집중 중"

        diff_sec = today_sec - yest_sec
        diff_min = abs(diff_sec) // 60
        if diff_sec >= 60:
            return f"📊 오늘 총 {today_str} 집중 (어제보다 +{diff_min}분 ▲)"
        elif diff_sec <= -60:
            return f"📊 오늘 총 {today_str} 집중 (어제보다 -{diff_min}분)"
        else:
            return f"📊 오늘 총 {today_str} 집중 (어제와 비슷)"
