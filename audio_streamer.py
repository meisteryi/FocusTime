"""
FocusTime - Audio Streaming Module
Features:
- Official YouTube Algorithm Endless Radio Mix (`list=RD{VIDEO_ID}`)
- Real-time Loudness Normalization (Web Audio API DynamicsCompressorNode)
- Precision Zero-Ad Engine (0ms Mute + Gain 0 + 16x Warp + Auto Skip)
- Queue Management (Jump to track, Remove unwanted upcoming tracks)
- Self-Healing Supervisor Injection & Watchdog
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
    window.__ft_normalize = (typeof window.__ft_normalize !== 'undefined') ? window.__ft_normalize : true;

    function attachNormalizer(v) {
        if (!v || v.__ft_norm_attached) return;
        try {
            var AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            var ctx = window.__ft_audio_ctx || new AudioCtx();
            var src = ctx.createMediaElementSource(v);

            // Loudness normalizer (DynamicsCompressor)
            var comp = ctx.createDynamicsCompressor();
            comp.threshold.value = -22;
            comp.knee.value = 24;
            comp.ratio.value = 6;
            comp.attack.value = 0.005;
            comp.release.value = 0.25;

            // Makeup gain to keep quiet tracks audible
            var makeup = ctx.createGain();
            makeup.gain.value = 1.45;

            // Master volume & ad-mute gain
            var masterGain = ctx.createGain();
            masterGain.gain.value = window.__ft_target_volume;

            src.connect(comp);
            comp.connect(makeup);
            makeup.connect(masterGain);
            masterGain.connect(ctx.destination);

            if (ctx.state === 'suspended') {
                ctx.resume().catch(function(e){});
            }

            window.__ft_audio_ctx = ctx;
            window.__ft_comp = comp;
            window.__ft_makeup = makeup;
            window.__ft_master_gain = masterGain;
            v.__ft_norm_attached = true;
        } catch (e) {
            // Fallback gracefully to native video volume if WebAudio fails
        }
    }

    function applyVolumeAndMute(v, isAd) {
        if (!v) return;
        if (isAd) {
            v.muted = true;
            v.volume = 0;
            if (window.__ft_master_gain) window.__ft_master_gain.gain.value = 0;
            v.playbackRate = 16.0;
            if (!isNaN(v.duration) && v.duration > 0) {
                try { v.currentTime = v.duration; } catch(e) {}
            }
        } else {
            if (v.playbackRate !== 1.0) v.playbackRate = 1.0;
            if (v.muted) v.muted = false;

            if (window.__ft_master_gain && v.__ft_norm_attached) {
                v.volume = 1.0; // Master gain handles volume cleanly
                window.__ft_master_gain.gain.value = window.__ft_target_volume;
                if (window.__ft_makeup) {
                    window.__ft_makeup.gain.value = window.__ft_normalize ? 1.45 : 1.0;
                }
                if (window.__ft_comp) {
                    window.__ft_comp.ratio.value = window.__ft_normalize ? 6 : 1;
                }
            } else {
                v.volume = window.__ft_target_volume;
            }

            if (!window.__ft_is_paused && v.paused && !v.ended) {
                v.play().catch(function(e){});
            }
        }
    }

    function initObserver() {
        var player = document.querySelector('#movie_player');
        if (!player) {
            setTimeout(initObserver, 150);
            return;
        }
        if (player.__ft_observed) return;
        player.__ft_observed = true;

        var observer = new MutationObserver(function() {
            var isAd = player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting');
            var v = document.querySelector('video');
            if (v) {
                attachNormalizer(v);
                applyVolumeAndMute(v, isAd);
            }
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

    if (window.__ft_timer) clearInterval(window.__ft_timer);
    window.__ft_timer = setInterval(function() {
        var player = document.querySelector('#movie_player');
        var v = document.querySelector('video');
        if (!v) return;

        if (!v.__ft_norm_attached) {
            attachNormalizer(v);
        }
        if (!v.__ft_vol_guarded) {
            v.__ft_vol_guarded = true;
            v.addEventListener('volumechange', function() {
                var p = document.querySelector('#movie_player');
                var adNow = p && (p.classList.contains('ad-showing') || p.classList.contains('ad-interrupting'));
                if (adNow) {
                    v.muted = true;
                    v.volume = 0;
                    if (window.__ft_master_gain) window.__ft_master_gain.gain.value = 0;
                }
            });
        }

        var isAd = player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'));
        applyVolumeAndMute(v, isAd);

        if (isAd) {
            var skip = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern, .ytp-ad-overlay-close-button');
            if (skip) {
                try { skip.click(); } catch(e) {}
            }
        }
    }, 120);

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
        var player = document.querySelector('#movie_player');
        var isAd = player && (player.classList.contains('ad-showing') || player.classList.contains('ad-interrupting'));
        if (isAd) return;

        var v = document.querySelector('video');
        if (window.__ft_master_gain && v && v.__ft_norm_attached) {
            window.__ft_master_gain.gain.value = val;
        } else if (v && !v.muted) {
            v.volume = val;
        }
    };

    window.__ft_set_normalize = function(enabled) {
        window.__ft_normalize = enabled;
    };

    window.__ft_play = function() {
        window.__ft_is_paused = false;
        if (window.__ft_audio_ctx && window.__ft_audio_ctx.state === 'suspended') {
            window.__ft_audio_ctx.resume().catch(function(e){});
        }
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
    normalize_changed = pyqtSignal(bool)   # loudness normalization active

    def __init__(self, parent_widget=None):
        super().__init__(parent_widget)

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
        self.normalize_audio = True
        self.is_playing = False
        self._is_handling_end = False
        self._connection_watchdog_count = 0
        self._last_loaded_url = ""
        self._removed_ids = set()

        self.search_thread = None

        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self._monitor_playback)
        self.monitor_timer.start(400)

    def _on_page_loaded(self, ok: bool):
        self.web_view.page().runJavaScript(IN_PAGE_SUPERVISOR_JS)
        self.set_volume(self.volume)
        self.web_view.page().runJavaScript(f"if (window.__ft_set_normalize) window.__ft_set_normalize({'true' if self.normalize_audio else 'false'});")

    def search(self, query: str, callback, error_callback=None):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()

        self.search_thread = SearchThread(query)
        self.search_thread.results_ready.connect(callback)
        if error_callback:
            self.search_thread.search_error.connect(error_callback)
        self.search_thread.start()

    def set_queue_and_play(self, track_list: list, start_index: int = 0):
        self._removed_ids.clear()
        self.queue = list(track_list)
        self.current_index = start_index
        self.queue_updated.emit(self.queue, self.current_index)
        self._play_current(enable_radio_mix=True)

    def play_url(self, url: str, title: str = "YouTube BGM"):
        self._removed_ids.clear()
        track_info = {'title': title, 'url': url, 'uploader': 'Custom URL', 'duration': ''}
        self.queue = [track_info]
        self.current_index = 0
        self.queue_updated.emit(self.queue, self.current_index)
        self._play_current(enable_radio_mix=True)

    def play_queue_index(self, index: int):
        """Jumps directly to a specific track in the queue"""
        if 0 <= index < len(self.queue):
            self.current_index = index
            self.queue_updated.emit(self.queue, self.current_index)
            self._play_current(enable_radio_mix=True)

    def remove_from_queue(self, index: int):
        """Removes an unwanted track from the upcoming queue"""
        if 0 <= index < len(self.queue) and index != self.current_index:
            removed = self.queue.pop(index)
            if removed.get('id'):
                self._removed_ids.add(removed.get('id'))
            if index < self.current_index:
                self.current_index -= 1
            self.queue_updated.emit(self.queue, self.current_index)

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
                track['id'] = vid_id

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

        if status == 'need_inject':
            self.web_view.page().runJavaScript(IN_PAGE_SUPERVISOR_JS)
            vol = self.volume / 100.0
            self.web_view.page().runJavaScript(f"if (window.__ft_set_volume) window.__ft_set_volume({vol});")
            return

        if status == 'no_video':
            self._connection_watchdog_count += 1
            if self._connection_watchdog_count > 15:
                self.status_updated.emit("스트림 지연 - 다음 알고리즘 추천 곡으로 전환합니다...")
                self._connection_watchdog_count = 0
                self.next_track()
            return
        else:
            self._connection_watchdog_count = 0

        # Sync title & current index when YouTube transitions
        current_url = res.get('currentUrl', '')
        current_title = res.get('currentTitle')
        current_uploader = res.get('currentUploader')

        if current_url:
            m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', current_url)
            if m:
                playing_id = m.group(1)
                for idx, t in enumerate(self.queue):
                    if t.get('id') == playing_id and idx != self.current_index:
                        self.current_index = idx
                        self.current_track = t
                        self.queue_updated.emit(self.queue, self.current_index)
                        break

        if current_title and self.current_track:
            if current_title != self.current_track.get('title'):
                self.current_track['title'] = current_title
                if current_uploader:
                    self.current_track['uploader'] = current_uploader
                self.title_updated.emit(current_title, current_uploader or '')
                self.queue_updated.emit(self.queue, self.current_index)

        # Sync YouTube Mix queue (excluding user-removed tracks)
        mix_tracks = res.get('mixTracks')
        if mix_tracks and len(mix_tracks) > 1:
            existing_ids = {t.get('id') for t in self.queue}
            new_additions = [
                t for t in mix_tracks
                if t.get('id') not in existing_ids and t.get('id') not in self._removed_ids
            ]
            if new_additions:
                self.queue.extend(new_additions)
                self.queue_updated.emit(self.queue, self.current_index)

        is_paused = res.get('paused', False)
        actual_playing = (not is_paused) and (status == 'playing')
        if actual_playing != self.is_playing:
            self.is_playing = actual_playing
            self.state_changed.emit(self.is_playing)

        if res.get('isAd'):
            self.status_updated.emit("광고 음소거 & 초고속 스킵 중...")
            return

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
        self._is_handling_end = False

        # If next track in our curated queue differs from YouTube's immediate next (e.g., user deleted tracks),
        # jump cleanly to our curated next track
        if self.current_index + 1 < len(self.queue):
            self.current_index += 1
            self.queue_updated.emit(self.queue, self.current_index)
            self._play_current(enable_radio_mix=True)
            return

        def on_next_result(success):
            if not success and len(self.queue) > 0:
                self.current_index = 0
                self._play_current(enable_radio_mix=True)

        self.web_view.page().runJavaScript(
            "window.__ft_next_video ? window.__ft_next_video() : false;",
            on_next_result
        )

    def prev_track(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.queue_updated.emit(self.queue, self.current_index)
            self._play_current(enable_radio_mix=True)
            return

        def on_prev_result(success):
            if not success:
                self.web_view.page().runJavaScript("var v = document.querySelector('video'); if (v) v.currentTime = 0;")

        self.web_view.page().runJavaScript(
            "window.__ft_prev_video ? window.__ft_prev_video() : false;",
            on_prev_result
        )

    def toggle_autoplay(self):
        self.autoplay = not self.autoplay
        self.autoplay_changed.emit(self.autoplay)

    def toggle_normalize(self):
        self.normalize_audio = not self.normalize_audio
        self.web_view.page().runJavaScript(
            f"if (window.__ft_set_normalize) window.__ft_set_normalize({'true' if self.normalize_audio else 'false'});"
        )
        self.normalize_changed.emit(self.normalize_audio)

    def set_volume(self, value: int):
        self.volume = max(0, min(100, value))
        vol = self.volume / 100.0
        js = f"""
        (function() {{
            window.__ft_target_volume = {vol};
            if (typeof window.__ft_set_volume === 'function') {{
                window.__ft_set_volume({vol});
            }} else {{
                var v = document.querySelector('video');
                if (v) v.volume = {vol};
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js)

    def stop(self):
        self.is_playing = False
        self.web_view.setUrl(QUrl("about:blank"))
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
