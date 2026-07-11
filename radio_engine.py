"""Core audio, metadata, and recording logic."""

from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime
import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

import config


class AlbumArtWorker(QObject):
    image_ready = pyqtSignal(QPixmap)
    image_failed = pyqtSignal()

    def __init__(self, save_path_target=None):
        super().__init__()
        self.save_path_target = save_path_target
        self.nam = QNetworkAccessManager()
        self.nam.setRedirectPolicy(QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        self.nam.finished.connect(self.handle_response)

    def fetch(self, url):
        if not url or not url.startswith("http"):
            self.image_failed.emit()
            return
        if url.startswith("http://") and not (
            ":8040" in url or ":8000" in url or "bauerhosting" in url or "musicradio" in url or "thisisdax" in url
        ):
            url = url.replace("http://", "https://", 1)

        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        self.nam.get(request)

    def handle_response(self, reply):
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.image_failed.emit()
            reply.deleteLater()
            return
        data = reply.readAll().data()
        img = QImage()
        if img.loadFromData(data):
            pixmap = QPixmap.fromImage(img)
            if self.save_path_target:
                try:
                    img.save(self.save_path_target, "PNG")
                except Exception as exc:
                    print(f"DEBUG Cache Sync Error: {exc}")
            self.image_ready.emit(pixmap)
        else:
            self.image_failed.emit()
        reply.deleteLater()


class ArtworkSearchWorker(QObject):
    art_found = pyqtSignal(str)
    search_failed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._last_term = ""

    def search_track(self, term):
        term = term.strip()
        if not term or term == self._last_term or term.lower() == "connecting...":
            return
        self._last_term = term

        if " - " in term:
            parts = term.split(" - ")
            search_query = f"{parts[0]} {parts[1]}"
        else:
            search_query = term
        threading.Thread(target=self._fetch_itunes_art, args=(search_query,), daemon=True).start()

    def _fetch_itunes_art(self, query):
        try:
            url = "https://itunes.apple.com/search"
            params = {"term": query, "media": "music", "limit": 1}
            request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=4) as response:
                data = json.load(response)
            if data.get("resultCount", 0) > 0:
                artwork_url = data["results"][0]["artworkUrl100"]
                high_res_url = artwork_url.replace("100x100bb.jpg", "600x600bb.jpg")
                self.art_found.emit(high_res_url)
                return
            self.search_failed.emit()
        except Exception:
            self.search_failed.emit()


class MetadataWorker(QObject):
    metadata_updated = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.running = False
        self._current_url = ""
        self._lock = threading.Lock()

    def update_url(self, url):
        with self._lock:
            self._current_url = url

    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:
            with self._lock:
                url = self._current_url
            if not url or ".m3u8" in url or os.path.exists(url):
                time.sleep(1)
                continue
            try:
                headers = {"Icy-MetaData": "1", "User-Agent": "Mozilla/5.0"}
                request = Request(url, headers=headers)
                response = urlopen(request, timeout=5)
                metaint = int(response.headers.get("icy-metaint", 0))
                if metaint > 0:
                    buffer = response
                    while self.running:
                        with self._lock:
                            if url != self._current_url:
                                break
                        buffer.read(metaint)
                        len_byte = buffer.read(1)
                        if not len_byte:
                            break
                        meta_len = int(len_byte[0]) * 16
                        if meta_len > 0:
                            meta_data = buffer.read(meta_len).decode("utf-8", errors="ignore")
                            title = ""
                            img = ""
                            if "StreamTitle='" in meta_data:
                                title = meta_data.split("StreamTitle='")[1].split("';")[0].strip()
                            if "StreamUrl='" in meta_data:
                                img = meta_data.split("StreamUrl='")[1].split("';")[0].strip()
                            if title or img:
                                self.metadata_updated.emit(title, img)
            except Exception:
                time.sleep(3)
            time.sleep(1)


class LiveStreamRecorder:
    def __init__(self):
        self.is_recording = False
        self._thread = None
        self._stop_event = threading.Event()
        self.current_filename = ""

    def start_recording(self, url, station_name):
        if self.is_recording:
            return
        self.is_recording = True
        self._stop_event.clear()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", station_name)
        self.current_filename = os.path.join(config.RECORDINGS_DIR, f"{safe_name}_{timestamp}.mp3")
        self._thread = threading.Thread(target=self._download_loop, args=(url,), daemon=True)
        self._thread.start()

    def _download_loop(self, url):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            response = urlopen(request, timeout=10)
            with open(self.current_filename, "wb") as handle:
                while True:
                    chunk = response.read(8192)
                    if self._stop_event.is_set():
                        break
                    if chunk:
                        handle.write(chunk)
                    else:
                        break
        except Exception as exc:
            print(f"DEBUG Recording Stream Write Engine Dropout: {exc}")
        finally:
            self.is_recording = False

    def stop_recording(self):
        if not self.is_recording:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.is_recording = False


class RadioEngine(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)

        self.metadata_worker = MetadataWorker()
        self.recorder = LiveStreamRecorder()
        self._volume = 0.7

    def set_volume(self, value: int) -> None:
        self._volume = max(0.0, min(1.0, value / 100.0))
        self.audio_output.setVolume(self._volume)

    def set_muted(self, muted: bool) -> None:
        self.audio_output.setMuted(bool(muted))

    def toggle_muted(self) -> bool:
        muted = not self.audio_output.isMuted()
        self.audio_output.setMuted(muted)
        return muted

    def load_stream(self, url: str) -> None:
        self.media_player.setSource(QUrl(url))

    def load_local_file(self, path: str) -> None:
        self.media_player.setSource(QUrl.fromLocalFile(path))

    def play(self) -> None:
        self.media_player.play()

    def stop(self) -> None:
        self.media_player.stop()

    def start_metadata(self, url: str) -> None:
        self.metadata_worker.update_url(url)
        self.metadata_worker.start()

    def stop_metadata(self) -> None:
        self.metadata_worker.stop()

    def toggle_recording(self, url: str, station_name: str) -> bool:
        if self.recorder.is_recording:
            self.recorder.stop_recording()
            return False
        self.recorder.start_recording(url, station_name)
        return True

    def cleanup(self) -> None:
        self.stop_metadata()
        if self.recorder.is_recording:
            self.recorder.stop_recording()
