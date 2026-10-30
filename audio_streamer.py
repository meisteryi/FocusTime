"""
FocusTime - Audio Streaming Module
Features:
- Official YouTube Algorithm Endless Radio Mix (`list=RD{VIDEO_ID}`):
  - Streams real YouTube recommendations based on the selected song (Just like native YouTube)
  - Seamless in-player navigation (Instant track change without full page reloads)
- Precision Zero-Ad Engine:
  - Exact active ad detection (`ad-showing` / `ad-interrupting` on player)
  - Auto-mute during ads (Zero ad audio leaks)
  - 16x fast-forward on active ads
  - Instant auto-click for skip buttons
  - Clean restoration of 1.0x speed and un-muted volume for the actual music
- Robust Playback State Management:
  - Explicit user pause flag (`__ft_is_paused`)
  - True play/pause toggle synchronization
- Self-Healing Supervisor Injection & Direct Volume Control
- In-App YouTube Search with yt-dlp
"""

from PyQt5.QtCore import QObject, pyqtSignal, QThread, QUrl, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
import yt_dlp
import re


IN_PAGE_SUPERVISOR_JS = """
(function() {
    window.__ft_target_volume = (typeof window.__ft_target_volume !== 'undefined') ? window.__ft_target_volume : 0.7;
    window.__ft_is_paused = (typeof window.__ft_is_paused !== 'undefined') ? window.__ft_is_paused : false;

    function applyAdState(isAd) {
        var v = document.querySelector('video');
        if (!v) return;

        if (isAd) {
            // ZERO AUDIO LEAK: Instantly set volume to 0 AND mute
            v.muted = true;
            v.volume = 0;
            v.playbackRate = 16.0;
            if (!isNaN(v.duration) && v.duration > 0) {
                try { v.currentTime = v.duration; } catch(e) {}
            }
        } else {
            if (v.playbackRate !== 1.0) v.playbackRate = 1.0;
            if (v.muted) v.muted = false;
            v.volume = window.__ft_target_volume;

            // Only auto-play if the user HAS NOT explicitly paused
            if (!window.__ft_is_paused && v.paused && !v.ended) {
                v.play().catch(function(e){});
            }
        }
    }

    // 1. MutationObserver on #movie_player
    function initObserver() {
        var player = document.querySelector('#movie_player');
        if (!player) {
            setTimeout(initObserver, 150);
            return;
        }

        var observer = new MutationObserver(function(mutations) {
            var isAd = player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting');
            applyAdState(isAd);
            if (isAd) {
                var skip = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-overlay-close-button');
                if (skip) {
                    try { skip.click(); } catch(e) {}
                }
            }
        });
        observer.observe(player, { attributes: true, attributeFilter: ['class'] });
    }
    initObserver();

    // 2. High-frequency supervision interval
    if (window.__ft_timer) clearInterval(window.__ft_timer);
    window.__ft_timer = setInterval(function() {
        var player = document.querySelector('#movie_player');
        var v = document.querySelector('video');
        if (!v) return;

        var isAd = player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'));
        applyAdState(isAd);

        if (isAd) {
            var skip = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-overlay-close-button');
            if (skip) {
                try { skip.click(); } catch(e) {}
            }
        }
    }, 120);

    // Extract YouTube Algorithm's Recommended Mix Tracks
    window.__ft_get_mix_tracks = function() {
        var tracks = [];
        var items = document.querySelectorAll('ytd-playlist-panel-video-renderer');
        items.forEach(function(el) {
            var titleEl = el.querySelector('#video-title');
            var bylineEl = el.querySelector('#byline');
            var a = el.querySelector('a');
            if (a) {
                var href = a.getAttribute('href') || '';
                var m = href.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
                if (m) {
                    var vidId = m[1];
                    var title = titleEl ? titleEl.innerText.trim() : '';
                    var uploader = bylineEl ? bylineEl.innerText.trim() : '';
                    if (title && !tracks.some(function(t){ return t.id === vidId; })) {
                        tracks.push({
                            id: vidId,
                            title: title,
                            uploader: uploader,
                            url: 'https://www.youtube.com/watch?v=' + vidId
                        });
                    }
                }
            }
        });
        return tracks;
    };

    window.__ft_get_status = function() {
        var v = document.querySelector('video');
        if (!v) return { status: 'no_video' };
        var player = document.querySelector('#movie_player');
        var isAd = player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'));

        // Current track meta from YouTube player or DOM
        var currentTitle = "";
        var currentUploader = "";
        if (player && typeof player.getVideoData === 'function') {
            var data = player.getVideoData();
            if (data) {
                currentTitle = data.title || "";
                currentUploader = data.author || "";
            }
        }
        if (!currentTitle) {
            var tEl = document.querySelector('h1.ytd-watch-metadata, #title h1');
            if (tEl) currentTitle = tEl.innerText.trim();
        }

        var mixTracks = window.__ft_get_mix_tracks();

        return {
            status: 'playing',
            isAd: !!isAd,
            time: v.currentTime,
            duration: v.duration,
            ended: v.ended,
            paused: v.paused,
            userPaused: window.__ft_is_paused,
            currentTitle: currentTitle,
            currentUploader: currentUploader,
            currentUrl: window.location.href,
            mixTracks: mixTracks
        };
    };

    window.__ft_set_volume = function(val) {
        window.__ft_target_volume = val;
        var v = document.querySelector('video');
        if (v && !v.muted) v.volume = val;
    };

    window.__ft_play = function() {
        window.__ft_is_paused = false;
        var v = document.querySelector('video');
        if (v) v.play().catch(function(e){});
    };

    window.__ft_pause = function() {
        window.__ft_is_paused = true;
        var v = document.querySelector('video');
        if (v) v.pause();
    };

    window.__ft_toggle = function() {
        var v = document.querySelector('video');
        if (!v) return;
        if (v.paused) {
            window.__ft_play();
        } else {
            window.__ft_pause();
        }
    };

    window.__ft_next_video = function() {
        window.__ft_is_paused = false;
        var nextBtn = document.querySelector('.ytp-next-button');
        if (nextBtn) {
            nextBtn.click();
            return true;
        }
        var player = document.querySelector('#movie_player');
        if (player && typeof player.nextVideo === 'function') {
            player.nextVideo();
            return true;
        }
        return false;
    };

    window.__ft_prev_video = function() {
        window.__ft_is_paused = false;
        var prevBtn = document.querySelector('.ytp-prev-button');
        if (prevBtn) {
            prevBtn.click();
            return true;
        }
        var player = document.querySelector('#movie_player');
        if (player && typeof player.previousVideo === 'function') {
            player.previousVideo();
            return true;
        }
        return false;
    };
})();
"""


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

        self.web_view.loadFinished.connect(self._on_page_loaded)

        self.current_track = None
        self.queue = []
        self.current_index = -1
        self.volume = 70
        self.autoplay = True
        self.is_playing = False
        self._is_handling_end = False
        self._connection_watchdog_count = 0
        self._last_loaded_url = ""

        self.search_thread = None

        # Watcher timer (every 400ms)
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_playback)
        self.monitor_timer.start(400)

    def _on_page_loaded(self, ok: bool):
        self.web_view.page().runJavaScript(IN_PAGE_SUPERVISOR_JS)
        self.set_volume(self.volume)

    def search(self, query: str, callback, error_callback=None):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()

        self.search_thread = SearchThread(query)
        self.search_thread.results_ready.connect(callback)
        if error_callback:
            self.search_thread.search_error.connect(error_callback)
        self.search_thread.start()

    def set_queue_and_play(self, track_list: list, start_index: int = 0):
        """Starts playback and activates the YouTube Algorithm Endless Radio Mix for the chosen song"""
        self.queue = list(track_list)
        self.current_index = start_index
        self.queue_updated.emit(self.queue, self.current_index)
        self._play_current(enable_radio_mix=True)

    def play_url(self, url: str, title: str = "YouTube BGM"):
        track_info = {'title': title, 'url': url, 'uploader': 'Custom URL', 'duration': ''}
        self.queue = [track_info]
        self.current_index = 0
        self.queue_updated.emit(self.queue, self.current_index)
        self._play_current(enable_radio_mix=True)

    def _play_current(self, enable_radio_mix: bool = True):
        if not (0 <= self.current_index < len(self.queue)):
            return

        self._is_handling_end = False
        self._connection_watchdog_count = 0
        track = self.queue[self.current_index]
        self.current_track = track

        url = track.get('url', '')
        vid_id = track.get('id')
        if not vid_id:
            match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
            if match:
                vid_id = match.group(1)

        # Official YouTube Endless Radio Mix param (&list=RD{VIDEO_ID})
        if vid_id and enable_radio_mix:
            target_url = f"https://www.youtube.com/watch?v={vid_id}&list=RD{vid_id}"
        elif vid_id:
            target_url = f"https://www.youtube.com/watch?v={vid_id}"
        else:
            target_url = url

        self.status_updated.emit("YouTube 추천 알고리즘 믹스 연결 중...")
        self.title_updated.emit(track.get('title', '재생 중'), track.get('uploader', ''))

        self._last_loaded_url = target_url
        self.web_view.setUrl(QUrl(target_url))
        self.is_playing = True
        self.state_changed.emit(True)

    def _monitor_playback(self):
        if not self.current_track:
            return

        poll_js = """
        (function() {
            if (typeof window.__ft_get_status === 'function') {
                return window.__ft_get_status();
            }
            return { status: 'need_inject' };
        })();
        """
        self.web_view.page().runJavaScript(poll_js, self._on_monitor_result)

    def _on_monitor_result(self, res):
        if not res or not isinstance(res, dict):
            return

        status = res.get('status')

        # 1. Re-inject supervisor if missing
        if status == 'need_inject':
            self.web_view.page().runJavaScript(IN_PAGE_SUPERVISOR_JS)
            vol = self.volume / 100.0
            self.web_view.page().runJavaScript(f"if (window.__ft_set_volume) window.__ft_set_volume({vol});")
            return

        # 2. Connection watchdog
        if status == 'no_video':
            self._connection_watchdog_count += 1
            if self._connection_watchdog_count > 15:  # ~6 seconds timeout
                self.status_updated.emit("스트림 지연 - 다음 알고리즘 추천 곡으로 전환합니다...")
                self._connection_watchdog_count = 0
                self.next_track()
            return
        else:
            self._connection_watchdog_count = 0

        # 3. Dynamic Title & Track Synchronization from YouTube
        current_title = res.get('currentTitle')
        current_uploader = res.get('currentUploader')
        if current_title and self.current_track:
            if current_title != self.current_track.get('title'):
                self.current_track['title'] = current_title
                if current_uploader:
                    self.current_track['uploader'] = current_uploader
                self.title_updated.emit(current_title, current_uploader or '')

        # 4. Integrate YouTube's Algorithm Recommended Mix Queue into our player
        mix_tracks = res.get('mixTracks')
        if mix_tracks and len(mix_tracks) > 1:
            # Sync algorithm mix tracks into self.queue if they aren't already populated
            existing_ids = {t.get('id') for t in self.queue}
            new_additions = [t for t in mix_tracks if t.get('id') not in existing_ids]
            if new_additions:
                self.queue.extend(new_additions)
                self.queue_updated.emit(self.queue, self.current_index)

        # 5. Synchronize actual playing state with UI
        is_paused = res.get('paused', False)
        actual_playing = (not is_paused) and (status == 'playing')
        if actual_playing != self.is_playing:
            self.is_playing = actual_playing
            self.state_changed.emit(self.is_playing)

        # 6. Handle Ad State
        if res.get('isAd'):
            self.status_updated.emit("광고 자동 스킵 중...")
            return

        # 7. Handle Track End and YouTube Continuous Autoplay
        if res.get('ended') or (res.get('duration') and res.get('currentTime', 0) >= res.get('duration', 0) - 1.5):
            if not self._is_handling_end:
                self._is_handling_end = True
                if self.autoplay:
                    self.status_updated.emit("다음 추천 곡으로 자동 전환 중...")
                    self.next_track()
        elif is_paused:
            self.status_updated.emit("일시 정지됨")
        else:
            self.status_updated.emit("YouTube 알고리즘 믹스 재생 중")

    def get_current_url(self) -> str:
        if self.current_track:
            return self.current_track.get('url', '')
        return ""

    def toggle_play(self):
        """Toggle playback cleanly with guaranteed execution"""
        if self.is_playing:
            self.is_playing = False
            self.state_changed.emit(False)
            self.web_view.page().runJavaScript("if (window.__ft_pause) window.__ft_pause(); else { var v = document.querySelector('video'); if (v) v.pause(); }")
            self.status_updated.emit("일시 정지됨")
        else:
            self.is_playing = True
            self.state_changed.emit(True)
            self.web_view.page().runJavaScript("if (window.__ft_play) window.__ft_play(); else { var v = document.querySelector('video'); if (v) v.play(); }")
            self.status_updated.emit("YouTube 알고리즘 믹스 재생 중")

    def next_track(self):
        """Advances to the next track using YouTube's in-player navigation (Instant & seamless)"""
        self._is_handling_end = False

        # Try fast in-player next first
        def on_next_result(success):
            if not success:
                # Fallback to queue index progression
                if self.current_index + 1 < len(self.queue):
                    self.current_index += 1
                    self._play_current(enable_radio_mix=False)
                elif len(self.queue) > 0:
                    self.current_index = 0
                    self._play_current(enable_radio_mix=True)

        self.web_view.page().runJavaScript(
            "window.__ft_next_video ? window.__ft_next_video() : false;",
            on_next_result
        )

    def prev_track(self):
        """Returns to previous track"""
        def on_prev_result(success):
            if not success:
                if self.current_index > 0:
                    self.current_index -= 1
                    self._play_current(enable_radio_mix=False)
                else:
                    self.web_view.page().runJavaScript("var v = document.querySelector('video'); if (v) v.currentTime = 0;")

        self.web_view.page().runJavaScript(
            "window.__ft_prev_video ? window.__ft_prev_video() : false;",
            on_prev_result
        )

    def toggle_autoplay(self):
        self.autoplay = not self.autoplay
        self.autoplay_changed.emit(self.autoplay)

    def set_volume(self, value: int):
        self.volume = max(0, min(100, value))
        vol = self.volume / 100.0
        js = f"""
        (function() {{
            window.__ft_target_volume = {vol};
            if (typeof window.__ft_set_volume === 'function') {{
                window.__ft_set_volume({vol});
            }}
            var v = document.querySelector('video');
            if (v) {{
                v.volume = {vol};
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def stop(self):
        self.is_playing = False
        self.web_view.setUrl(QUrl("about:blank"))
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
