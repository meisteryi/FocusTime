"""
FocusTime - Audio Streaming Module
Features:
- YouTube In-App Search (SearchThread using yt-dlp)
- Real-time Chromium Audio Streaming Engine (using hidden QWebEngineView)
- 100% Reliable playback without GoogleVideo 403 header block
- Auto ad-skipper and zero visible UI (Pure Audio Mode)
- Seamless Endless Queue & Autoplay of Related Tracks
"""

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QUrl, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
import yt_dlp
import re


class SearchThread(QThread):
    results_ready = pyqtSignal(list)
    search_error = pyqtSignal(str)

    def __init__(self, query: str, limit: int = 8):
        super().__init__()
        self.query = query
        self.limit = limit

    def run(self):
        try:
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_query = f"ytsearch{self.limit}:{self.query}"
                res = ydl.extract_info(search_query, download=False)
                entries = res.get('entries', [])
                items = []
                for e in entries:
                    if not e:
                        continue
                    duration_sec = e.get('duration')
                    if duration_sec:
                        m = int(duration_sec // 60)
                        s = int(duration_sec % 60)
                        dur_str = f"{m}:{s:02d}"
                    else:
                        dur_str = "LIVE"

                    vid_id = e.get('id')
                    url = e.get('url') or f"https://www.youtube.com/watch?v={vid_id}"

                    items.append({
                        'title': e.get('title', 'Unknown Track'),
                        'url': url,
                        'uploader': e.get('uploader', 'Unknown Artist'),
                        'duration': dur_str,
                        'id': vid_id
                    })
                self.results_ready.emit(items)
        except Exception as e:
            self.search_error.emit(f"검색 실패: {str(e)}")


class AudioPlayer(QObject):
    state_changed = pyqtSignal(bool)        # is_playing
    title_updated = pyqtSignal(str, str)    # title, uploader
    status_updated = pyqtSignal(str)       # status message
    queue_updated = pyqtSignal(list, int)  # queue list, current_index
    autoplay_changed = pyqtSignal(bool)    # autoplay active

    def __init__(self, parent_widget=None):
        super().__init__(parent_widget)

        # Hidden WebEngine for background audio streaming
        self.web_view = QWebEngineView(parent_widget)
        self.web_view.setVisible(False)
        self.web_view.resize(1, 1)

        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

        self.current_track = None
        self.queue = []
        self.current_index = -1
        self.volume = 70
        self.autoplay = True
        self.is_playing = False
        self._is_handling_end = False

        self.search_thread = None

        # Watcher timer to ensure playback, auto-skip ads, and detect end of media
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_playback)
        self.monitor_timer.start(800)

    def search(self, query: str, callback, error_callback=None):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()

        self.search_thread = SearchThread(query)
        self.search_thread.results_ready.connect(callback)
        if error_callback:
            self.search_thread.search_error.connect(error_callback)
        self.search_thread.start()

    def set_queue_and_play(self, track_list: list, start_index: int = 0):
        self.queue = track_list
        self.current_index = start_index
        self.queue_updated.emit(self.queue, self.current_index)
        self._play_current()

    def play_url(self, url: str, title: str = "YouTube BGM"):
        track_info = {'title': title, 'url': url, 'uploader': 'Custom URL', 'duration': ''}
        self.queue = [track_info]
        self.current_index = 0
        self.queue_updated.emit(self.queue, self.current_index)
        self._play_current()

    def _play_current(self):
        if not (0 <= self.current_index < len(self.queue)):
            return

        self._is_handling_end = False
        track = self.queue[self.current_index]
        self.current_track = track

        url = track.get('url', '')
        # Ensure clean watch url
        if 'youtu.be/' in url:
            vid_id = url.split('youtu.be/')[-1].split('?')[0]
            url = f"https://www.youtube.com/watch?v={vid_id}"
        elif 'watch?v=' not in url and track.get('id'):
            url = f"https://www.youtube.com/watch?v={track['id']}"

        self.status_updated.emit("음악 스트림 연결 중...")
        self.title_updated.emit(track.get('title', '재생 중'), track.get('uploader', ''))

        self.web_view.setUrl(QUrl(url))
        self.is_playing = True
        self.state_changed.emit(True)

    def _monitor_playback(self):
        if not self.is_playing or not self.current_track:
            return

        js_script = f"""
        (function() {{
            // Auto click ad skip buttons if any
            var skipBtns = document.querySelectorAll('.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-overlay-close-button');
            for (var i = 0; i < skipBtns.length; i++) {{
                try {{ skipBtns[i].click(); }} catch(e) {{}}
            }}

            var video = document.querySelector('video');
            if (!video) return {{ status: 'no_video' }};

            // Set volume
            video.volume = {self.volume / 100.0};

            // Ensure playing
            if (video.paused && !video.ended) {{
                video.play();
            }}

            return {{
                status: 'playing',
                paused: video.paused,
                currentTime: video.currentTime,
                duration: video.duration,
                ended: video.ended
            }};
        }})();
        """

        self.web_view.page().runJavaScript(js_script, self._on_monitor_result)

    def _on_monitor_result(self, res):
        if not res or not isinstance(res, dict):
            return

        status = res.get('status')
        if status == 'playing':
            if res.get('ended') or (res.get('duration') and res.get('currentTime', 0) >= res.get('duration', 0) - 1.5):
                if not self._is_handling_end:
                    self._is_handling_end = True
                    if self.autoplay:
                        self.status_updated.emit("곡 종료 - 다음 연관곡으로 넘어갑니다...")
                        self.next_track()
            else:
                self.status_updated.emit("재생 중")

    def toggle_play(self):
        self.is_playing = not self.is_playing
        self.state_changed.emit(self.is_playing)
        js = "var v = document.querySelector('video'); if (v) { if (v.paused) v.play(); else v.pause(); }"
        self.web_view.page().runJavaScript(js)

    def next_track(self):
        if self.current_index + 1 < len(self.queue):
            self.current_index += 1
            self._play_current()
        elif self.autoplay and self.current_track:
            self._fetch_related_and_continue()

    def prev_track(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._play_current()
        else:
            self.web_view.page().runJavaScript("var v = document.querySelector('video'); if (v) v.currentTime = 0;")

    def _fetch_related_and_continue(self):
        query = self.current_track.get('title', '')
        query_words = " ".join([w for w in query.split() if len(w) > 1][:4])
        self.status_updated.emit("다음 연관 곡 검색 중...")

        def on_related_found(new_tracks):
            existing_urls = {t.get('url') for t in self.queue}
            fresh_tracks = [t for t in new_tracks if t.get('url') not in existing_urls]
            if fresh_tracks:
                self.queue.extend(fresh_tracks)
                self.current_index += 1
                self.queue_updated.emit(self.queue, self.current_index)
                self._play_current()
            else:
                self.status_updated.emit("재생 목록 종료")

        self.search(f"{query_words} playlist", on_related_found)

    def get_current_url(self) -> str:
        if self.current_track:
            return self.current_track.get('url', '')
        return ""

    def toggle_autoplay(self):
        self.autoplay = not self.autoplay
        self.autoplay_changed.emit(self.autoplay)

    def set_volume(self, value: int):
        self.volume = max(0, min(100, value))
        js = f"var v = document.querySelector('video'); if (v) v.volume = {self.volume / 100.0};"
        self.web_view.page().runJavaScript(js)

    def stop(self):
        self.is_playing = False
        self.web_view.setUrl(QUrl("about:blank"))
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
