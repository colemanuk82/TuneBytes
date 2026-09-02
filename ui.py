"""PyQt6 user interface for the radio player."""

from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import threading
import time

from PyQt6.QtCore import (
    QByteArray,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    QUrl,
    QMimeData,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QDesktopServices,
    QDrag,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGridLayout,
    QFileDialog,
    QGraphicsOpacityEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import DEFAULT_SETTINGS, LOGOS_DIR, PREDEFINED_CATALOGUE, RECORDINGS_DIR, SCRIPT_DIR, STATIONS, THEME_PRESETS
from radio_engine import AlbumArtWorker, ArtworkSearchWorker, RadioEngine
from utils import (
    load_persistent_settings,
    load_persisted_station_order,
    sanitize_filename,
    save_persistent_settings,
    save_persisted_station_order,
)


FX_MODES = ["Warp Speed", "Kinetic Sparks", "Beat Fireworks", "Crackling Fire", "Digital Rain"]
APP_MIN_WIDTH = 760
APP_MIN_HEIGHT = 460
PANEL_VISIBILITY_MODES = ["both", "left", "right"]


class StationListButton(QPushButton):
    def __init__(self, parent_widget, *args, **kwargs):
        super().__init__(parent_widget, *args, **kwargs)
        self.parent_widget = parent_widget
        self.drag_start_position = QPoint()
        
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_right_click_menu)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            if (event.position().toPoint() - self.drag_start_position).manhattanLength() >= QApplication.startDragDistance():
                try:
                    source_idx = self.parent_widget.main_app.station_buttons.index(self)
                except ValueError:
                    return
                self.setDown(False)
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(str(source_idx))
                drag.setMimeData(mime_data)
                drag.setPixmap(self.grab())
                drag.setHotSpot(event.position().toPoint())
                drag.exec(Qt.DropAction.MoveAction)
                return
        super().mouseMoveEvent(event)

    def show_right_click_menu(self, pos):
        try:
            station_idx = self.parent_widget.main_app.station_buttons.index(self)
        except ValueError:
            return

        context_menu = QMenu(self)
        context_menu.setStyleSheet("""
            QMenu { background-color: #111111; color: #ffffff; border: 1px solid #45f3ff; border-radius: 8px; }
            QMenu::item:selected { background-color: #45f3ff; color: #000000; }
        """)
        
        change_logo_action = QAction("Change Station Logo (.png)", self)
        change_logo_action.triggered.connect(lambda: self.trigger_logo_change(station_idx))
        context_menu.addAction(change_logo_action)
        
        context_menu.exec(self.mapToGlobal(pos))

    def trigger_logo_change(self, index):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select Custom PNG Station Logo")
        file_dialog.setNameFilter("Image Files (*.png)")
        file_dialog.setViewMode(QFileDialog.ViewMode.Detail)
        
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                source_png_path = selected_files[0]
                station_name = STATIONS[index]["name"]
                
                filename = sanitize_filename(station_name)
                dest_png_path = os.path.join(LOGOS_DIR, filename)
                
                try:
                    shutil.copy2(source_png_path, dest_png_path)
                    STATIONS[index]["logo"] = dest_png_path
                    save_persisted_station_order()
                    
                    if hasattr(self.parent_widget.main_app, 'refresh_scroll_picker_list'):
                        self.parent_widget.main_app.refresh_scroll_picker_list()
                    
                    if getattr(self.parent_widget.main_app, 'current_index', -1) == index:
                        if hasattr(self.parent_widget.main_app, 'apply_scaled_artwork'):
                            self.parent_widget.main_app.current_pixmap = QPixmap(dest_png_path)
                            self.parent_widget.main_app.apply_scaled_artwork()
                            
                except Exception as e:
                    print(f"DEBUG Custom Station Logo Assignment Error: {e}")


class AntigravityStationListWidget(QWidget):
    order_changed = pyqtSignal()

    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setObjectName("scroll_content")
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(4)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        self.accent_color = QColor("#45f3ff")
        self.mouse_pos = QPointF(-1000.0, -1000.0)
        
        # Warp Space Parameters
        self.target_mx = 0.0
        self.target_my = 0.0
        self.current_mx = 0.0
        self.current_my = 0.0
        self.max_stars = 120
        self.stars = []
        
        # Spark Engine Parameters
        self.max_particles = 40
        self.particles = []
        self.fireworks = []
        self.fire_embers = []
        self.rain_columns = []
        self.last_firework_beat = 0.0
        self.next_firework_interval = 0.55
        self.last_fx_tick = time.time()
        
        self.init_animations()
        
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(16)
        self.refresh_timer.timeout.connect(self.update_physics_loop)
        self.refresh_timer.start()

    def init_animations(self):
        self.stars.clear()
        for _ in range(self.max_stars):
            self.stars.append({
                'x': random.uniform(-1.0, 1.0),
                'y': random.uniform(-1.0, 1.0),
                'z': random.uniform(0.1, 1.0),
                'brightness': random.uniform(0.3, 1.0)
            })
            
        self.particles.clear()
        for _ in range(self.max_particles // 2):
            self.spawn_particle()
            
        self.fireworks.clear()
        self.fire_embers.clear()
        self.rain_columns.clear()
        self.last_firework_beat = time.time()
        self.next_firework_interval = random.uniform(0.42, 0.82)
        self.last_fx_tick = time.time()
        self.init_digital_rain()

    def init_digital_rain(self):
        self.rain_columns.clear()
        w = max(self.width(), 320)
        columns = max(12, int(w / 22))
        glyphs = "01RADIOSTREAMLIVE"
        for i in range(columns):
            self.rain_columns.append({
                'x': i * 22 + random.uniform(-3, 3),
                'y': random.uniform(-400, 0),
                'speed': 120.0,
                'length': random.randint(8, 22),
                'glyphs': [random.choice(glyphs) for _ in range(26)],
                'flicker': random.random(),
                'mutate_at': random.uniform(0.0, 1.2),
            })

    def spawn_firework_burst(self):
        w = max(self.width(), 240)
        h = max(self.height(), 180)
        cx = random.uniform(w * 0.18, w * 0.82)
        cy = random.uniform(h * 0.16, h * 0.62)
        count = random.randint(34, 58)
        hue_colors = [
            QColor(self.accent_color),
            QColor("#ff4d4d"),
            QColor("#ffd166"),
            QColor("#64faff"),
            QColor("#ff5fd7"),
            QColor("#f8f7ff"),
        ]
        for i in range(count):
            angle = (math.tau * i / count) + random.uniform(-0.14, 0.14)
            speed = random.uniform(2.6, 8.4)
            color = QColor(random.choice(hue_colors))
            self.fireworks.append({
                'x': cx,
                'y': cy,
                'px': cx,
                'py': cy,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed,
                'life': random.uniform(0.82, 1.0),
                'decay': random.uniform(0.012, 0.018),
                'radius': random.uniform(1.8, 3.5),
                'color': color,
                'twinkle': random.uniform(0.7, 1.35),
            })

    def spawn_fire_ember(self):
        w = max(self.width(), 240)
        h = max(self.height(), 180)
        x = random.uniform(0, w)
        flame_band = random.uniform(0.0, 1.0)
        kind = "smoke" if random.random() < 0.14 else ("flame" if random.random() < 0.62 else "ember")
        self.fire_embers.append({
            'x': x,
            'y': h + random.uniform(-8, 28),
            'vx': random.uniform(-0.65, 0.65),
            'vy': random.uniform(-4.6, -1.1) if kind != "smoke" else random.uniform(-1.8, -0.45),
            'life': random.uniform(0.58, 1.0),
            'radius': random.uniform(4.0, 16.0) if kind == "flame" else random.uniform(2.0, 8.0),
            'heat': flame_band,
            'kind': kind,
            'phase': random.uniform(0, math.tau),
        })

    def spawn_particle(self, x=None, y=None, energetic=False):
        w = max(self.width(), 400)
        h = max(self.height(), 400)
        radius = random.uniform(3.0, 6.0)
        speed_mult = random.uniform(2.0, 4.0) if energetic else random.uniform(0.5, 1.5)
        angle = random.uniform(0, 2 * math.pi)
        
        self.particles.append({
            'x': float(x) if x is not None else random.uniform(radius, w - radius),
            'y': float(y) if y is not None else random.uniform(radius, h - radius),
            'vx': math.cos(angle) * speed_mult,
            'vy': math.sin(angle) * speed_mult,
            'radius': radius,
            'mass': radius * radius,
            'life': 1.0,
            'is_spark': energetic
        })

    def update_accent_color(self, qcolor):
        self.accent_color = qcolor

    def mouseMoveEvent(self, event):
        self.mouse_pos = event.position()
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        if cx > 0 and cy > 0:
            self.target_mx = (event.position().x() - cx) / cx
            self.target_my = (event.position().y() - cy) / cy
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.mouse_pos = QPointF(-1000.0, -1000.0)
        self.target_mx = 0.0
        self.target_my = 0.0
        super().leaveEvent(event)

    def resolve_collisions(self):
        num_p = len(self.particles)
        for i in range(num_p):
            p1 = self.particles[i]
            for j in range(i + 1, num_p):
                p2 = self.particles[j]
                dx = p2['x'] - p1['x']
                dy = p2['y'] - p1['y']
                dist = math.hypot(dx, dy)
                min_dist = p1['radius'] + p2['radius']
                
                if dist < min_dist:
                    overlap = min_dist - dist
                    if dist == 0:
                        continue
                    nx = dx / dist
                    ny = dy / dist
                    
                    p1['x'] -= nx * overlap * 0.5
                    p1['y'] -= ny * overlap * 0.5
                    p2['x'] += nx * overlap * 0.5
                    p2['y'] += ny * overlap * 0.5
                    
                    kx = p1['vx'] - p2['vx']
                    ky = p1['vy'] - p2['vy']
                    p = 2 * (nx * kx + ny * ky) / (p1['mass'] + p2['mass'])
                    
                    p1['vx'] -= p * p2['mass'] * nx
                    p1['vy'] -= p * p2['mass'] * ny
                    p2['vx'] += p * p1['mass'] * nx
                    p2['vy'] += p * p1['mass'] * ny

    def update_physics_loop(self):
        if not self.main_app.app_settings.get("star_animation_enabled", True):
            if self.particles:
                self.particles.clear()
            self.update()
            return

        anim_type = self.main_app.app_settings.get("animation_type", "Warp Speed")
        is_playing = self.main_app.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        audio_level = self.main_app.audio_reactive_level()
        w, h = self.width(), self.height()
        now_tick = time.time()
        dt = max(0.008, min(0.05, now_tick - self.last_fx_tick))
        self.last_fx_tick = now_tick

        if anim_type == "Warp Speed":
            self.current_mx += (self.target_mx - self.current_mx) * 0.08
            self.current_my += (self.target_my - self.current_my) * 0.08
            base_speed = 0.015 if is_playing else 0.003
            
            for s in self.stars:
                s['z'] -= base_speed
                if s['z'] <= 0.01:
                    s['z'] = 1.0
                    s['x'] = random.uniform(-1.0, 1.0)
                    s['y'] = random.uniform(-1.0, 1.0)
                    s['brightness'] = random.uniform(0.5, 1.0)
        
        elif anim_type == "Kinetic Sparks":
            if w < 10 or h < 10:
                return
            if is_playing:
                if random.random() < 0.06 + audio_level * 0.22 and len(self.particles) < self.max_particles:
                    self.spawn_particle(x=w / 2, y=h / 2, energetic=True)
            else:
                if len(self.particles) > self.max_particles // 2:
                    self.particles = [p for p in self.particles if not p['is_spark'] or random.random() > 0.1]

            for p in self.particles:
                mdx = p['x'] - self.mouse_pos.x()
                mdy = p['y'] - self.mouse_pos.y()
                m_dist = math.hypot(mdx, mdy)
                if m_dist < 120 and m_dist > 0:
                    push = (120 - m_dist) * 0.15
                    p['vx'] += (mdx / m_dist) * push
                    p['vy'] += (mdy / m_dist) * push

                p['vx'] *= 0.99
                p['vy'] *= 0.99
                p['x'] += p['vx']
                p['y'] += p['vy']

                if p['x'] < p['radius']:
                    p['x'] = p['radius']
                    p['vx'] = abs(p['vx']) * 0.95
                elif p['x'] > w - p['radius']:
                    p['x'] = w - p['radius']
                    p['vx'] = -abs(p['vx']) * 0.95

                if p['y'] < p['radius']:
                    p['y'] = p['radius']
                    p['vy'] = abs(p['vy']) * 0.95
                elif p['y'] > h - p['radius']:
                    p['y'] = h - p['radius']
                    p['vy'] = -abs(p['vy']) * 0.95
                    
                if p['is_spark']:
                    p['life'] -= 0.005
                    
            self.particles = [p for p in self.particles if p['life'] > 0]
            self.resolve_collisions()

        elif anim_type == "Beat Fireworks":
            if w < 10 or h < 10:
                return
            now = time.time()
            if is_playing and now - self.last_firework_beat >= self.next_firework_interval:
                self.spawn_firework_burst()
                self.last_firework_beat = now
                self.next_firework_interval = random.uniform(0.55, 1.05)

            for p in self.fireworks:
                p['px'] = p['x']
                p['py'] = p['y']
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['vy'] += 0.074
                p['vx'] *= 0.982
                p['vy'] *= 0.99
                p['life'] -= p['decay']
            self.fireworks = [
                p for p in self.fireworks
                if p['life'] > 0 and -40 <= p['x'] <= w + 40 and -40 <= p['y'] <= h + 40
            ]

        elif anim_type == "Crackling Fire":
            if w < 10 or h < 10:
                return
            spawn_chance = (0.35 + audio_level * 0.75) if is_playing else 0.48
            max_embers = 170 if is_playing else 95
            if random.random() < spawn_chance and len(self.fire_embers) < max_embers:
                burst_count = random.randint(2, 4) if is_playing and random.random() < 0.38 else 1
                for _ in range(burst_count):
                    self.spawn_fire_ember()

            for ember in self.fire_embers:
                sway = math.sin((time.time() * 7.0) + ember['phase']) * (0.55 if ember['kind'] == "flame" else 0.22)
                ember['x'] += ember['vx'] + sway
                ember['y'] += ember['vy']
                ember['vy'] -= 0.010 if ember['kind'] != "smoke" else 0.002
                ember['vx'] *= 0.992
                ember['life'] -= random.uniform(0.008, 0.018) if ember['kind'] != "smoke" else random.uniform(0.004, 0.010)
                ember['radius'] *= 0.996 if ember['kind'] != "smoke" else 1.004
                if random.random() < 0.055:
                    ember['vx'] += random.uniform(-0.95, 0.95)

            self.fire_embers = [
                ember for ember in self.fire_embers
                if ember['life'] > 0 and -40 <= ember['x'] <= w + 40 and ember['y'] > -60
            ]

        elif anim_type == "Digital Rain":
            if w < 10 or h < 10:
                return
            desired_cols = max(12, int(w / 22))
            if not self.rain_columns or abs(len(self.rain_columns) - desired_cols) > 8:
                self.init_digital_rain()
            glyphs = "01RADIOSTREAMLIVE"
            for col in self.rain_columns:
                col['y'] += col['speed'] * dt
                col['flicker'] = (col['flicker'] + dt * 0.8) % 1.0
                col['mutate_at'] -= dt
                if col['mutate_at'] <= 0:
                    col['glyphs'][random.randrange(len(col['glyphs']))] = random.choice(glyphs)
                    col['mutate_at'] = random.uniform(0.18, 0.55)
                if col['y'] - (col['length'] * 16) > h + 80:
                    col['y'] = random.uniform(-360, -24)
                    col['speed'] = 120.0
                    col['length'] = random.randint(8, 24)
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#000000"))
        
        if not self.main_app.app_settings.get("star_animation_enabled", True):
            return
            
        anim_type = self.main_app.app_settings.get("animation_type", "Warp Speed")
        w, h = self.width(), self.height()
        is_playing = self.main_app.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        
        if anim_type == "Warp Speed":
            cx, cy = w / 2.0, h / 2.0
            for s in self.stars:
                px = cx + (s['x'] - self.current_mx * 0.15) * (cx / s['z'])
                py = cy + (s['y'] - self.current_my * 0.15) * (cy / s['z'])
                
                if 0 <= px <= w and 0 <= py <= h:
                    size = max(1.4, min(5.8, 2.2 / s['z']))
                    alpha = int(315 * (1.0 - s['z']) * max(0.55, s['brightness']))
                    alpha = max(72, min(255, alpha))
                    
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(self.accent_color.red(), self.accent_color.green(), self.accent_color.blue(), alpha))
                    
                    if is_playing and size > 1:
                        prev_z = s['z'] + 0.035
                        ppx = cx + (s['x'] - self.current_mx * 0.15) * (cx / prev_z)
                        ppy = cy + (s['y'] - self.current_my * 0.15) * (cy / prev_z)
                        
                        streak_color = QColor(self.accent_color)
                        streak_color.setAlpha(max(96, int(alpha * 0.78)))
                        painter.setPen(QPen(streak_color, max(1.2, size * 0.42)))
                        painter.drawLine(QPointF(ppx, ppy), QPointF(px, py))
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(QColor(245, 255, 255, min(255, alpha + 30)))
                        painter.drawEllipse(QRectF(px - size/3.0, py - size/3.0, size * 0.66, size * 0.66))
                    else:
                        painter.drawEllipse(QRectF(px - size/2.0, py - size/2.0, size, size))
                        
        elif anim_type == "Kinetic Sparks":
            for p in self.particles:
                alpha = int(p['life'] * 255)
                color = QColor(self.accent_color)
                
                if p['is_spark']:
                    color = QColor(255, int(100 + p['life'] * 155), int(p['life'] * 255))
                
                color.setAlpha(alpha)
                gradient = QRadialGradient(QPointF(p['x'], p['y']), p['radius'] * 2.0)
                gradient.setColorAt(0.0, color)
                gradient.setColorAt(1.0, QColor(0, 0, 0, 0))
                
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(p['x'], p['y']), p['radius'] * 1.8, p['radius'] * 1.8)

        elif anim_type == "Beat Fireworks":
            for p in self.fireworks:
                flicker = 0.72 + (math.sin(time.time() * 18.0 * p['twinkle']) * 0.28)
                alpha = max(0, min(255, int(p['life'] * 255 * flicker)))
                color = QColor(p['color'])
                color.setAlpha(alpha)
                trail = QColor(color)
                trail.setAlpha(int(alpha * 0.58))

                painter.setPen(QPen(trail, max(1.6, p['radius'] * 1.05)))
                painter.drawLine(
                    QPointF(p['px'], p['py']),
                    QPointF(p['x'], p['y'])
                )

                gradient = QRadialGradient(QPointF(p['x'], p['y']), p['radius'] * 4.6)
                gradient.setColorAt(0.0, QColor(255, 255, 255, alpha))
                gradient.setColorAt(0.22, color)
                gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(p['x'], p['y']), p['radius'] * 4.6, p['radius'] * 4.6)
                painter.setBrush(QColor(255, 255, 255, min(255, alpha + 30)))
                painter.drawEllipse(QPointF(p['x'], p['y']), max(1.4, p['radius'] * 0.65), max(1.4, p['radius'] * 0.65))

        elif anim_type == "Crackling Fire":
            base_glow = QRadialGradient(QPointF(w / 2.0, h + 18), max(w * 0.68, 160))
            base_glow.setColorAt(0.0, QColor(255, 86, 18, 120 if is_playing else 74))
            base_glow.setColorAt(0.42, QColor(255, 168, 32, 52 if is_playing else 30))
            base_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(QBrush(base_glow))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(w / 2.0, h + 18), max(w * 0.68, 160), max(h * 0.42, 90))

            for ember in self.fire_embers:
                heat = ember['heat']
                life = max(0.0, min(1.0, ember['life']))
                kind = ember.get('kind', 'ember')
                if kind == "smoke":
                    alpha = int(life * 58)
                    smoke = QColor(96, 88, 82, alpha)
                    gradient = QRadialGradient(QPointF(ember['x'], ember['y']), ember['radius'] * 3.2)
                    gradient.setColorAt(0.0, smoke)
                    gradient.setColorAt(1.0, QColor(80, 70, 64, 0))
                    painter.setBrush(QBrush(gradient))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(ember['x'], ember['y']), ember['radius'] * 3.0, ember['radius'] * 1.8)
                    continue

                if heat < 0.28:
                    color = QColor(188, 28, 6)
                elif heat < 0.68:
                    color = QColor(255, 116, 18)
                else:
                    color = QColor(255, 218, 92)
                alpha = int(life * (235 if is_playing else 170))
                color.setAlpha(alpha)

                if kind == "flame":
                    flame_h = ember['radius'] * (4.4 + heat * 2.2)
                    flame_w = ember['radius'] * (1.2 + heat)
                    wobble = math.sin(time.time() * 9.0 + ember['phase']) * flame_w * 0.55
                    path = QPainterPath()
                    path.moveTo(QPointF(ember['x'], ember['y'] - flame_h))
                    path.cubicTo(
                        QPointF(ember['x'] - flame_w + wobble, ember['y'] - flame_h * 0.66),
                        QPointF(ember['x'] - flame_w * 0.9, ember['y'] - flame_h * 0.22),
                        QPointF(ember['x'], ember['y'])
                    )
                    path.cubicTo(
                        QPointF(ember['x'] + flame_w * 0.9, ember['y'] - flame_h * 0.22),
                        QPointF(ember['x'] + flame_w + wobble, ember['y'] - flame_h * 0.66),
                        QPointF(ember['x'], ember['y'] - flame_h)
                    )
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawPath(path)
                else:
                    gradient = QRadialGradient(QPointF(ember['x'], ember['y']), ember['radius'] * 2.5)
                    gradient.setColorAt(0.0, QColor(255, 240, 180, alpha))
                    gradient.setColorAt(0.34, color)
                    gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
                    painter.setBrush(QBrush(gradient))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(ember['x'], ember['y']), ember['radius'] * 1.6, ember['radius'] * 2.4)

        elif anim_type == "Digital Rain":
            font = painter.font()
            font.setFamily("Consolas")
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            line_h = 16
            for col in self.rain_columns:
                x = int(col['x'])
                for i in range(col['length']):
                    y = int(col['y'] - i * line_h)
                    if y < -line_h or y > h + line_h:
                        continue
                    fade = max(0.0, 1.0 - (i / max(1, col['length'])))
                    if i == 0:
                        color = QColor(226, 255, 226, 235)
                    else:
                        color = QColor(30, 255, 98, int(34 + fade * 170))
                    painter.setPen(color)
                    glyph = col['glyphs'][i % len(col['glyphs'])]
                    painter.drawText(QPointF(x, y), glyph)
                
        painter.end()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasText(): return
        try:
            source_idx = int(event.mimeData().text())
        except:
            return
        drop_pos = event.position().toPoint()
        target_idx = 0
        view_mode = getattr(self.main_app, "view_mode", "list")
        
        for i in range(self.layout.count()):
            widget = self.layout.itemAt(i).widget()
            if widget and source_idx < len(self.main_app.station_buttons) and widget != self.main_app.station_buttons[source_idx]:
                geom = widget.geometry()
                if view_mode == "list":
                    if drop_pos.y() > widget.pos().y() + widget.height() / 2: target_idx = i + 1
                    else: target_idx = i; break
                else:
                    if drop_pos.y() > geom.bottom(): target_idx = i + 1
                    elif geom.top() <= drop_pos.y() <= geom.bottom():
                        if drop_pos.x() > geom.center().x(): target_idx = i + 1
                        else: target_idx = i; break
                    else: target_idx = i; break

        if source_idx == target_idx or source_idx == target_idx - 1:
            event.acceptProposedAction()
            return

        rendered_stations = [s for s in STATIONS if s.get("enabled", True)]
        if source_idx >= len(rendered_stations) or source_idx >= len(self.main_app.station_buttons):
            return

        station_data = rendered_stations[source_idx]
        master_idx = STATIONS.index(station_data)
        STATIONS.pop(master_idx)
        button_widget = self.main_app.station_buttons.pop(source_idx)
        
        if target_idx > source_idx: target_idx -= 1
        
        if target_idx < len(rendered_stations):
            target_station_data = rendered_stations[target_idx]
            master_target_idx = STATIONS.index(target_station_data)
        else:
            master_target_idx = len(STATIONS)
            
        STATIONS.insert(master_target_idx, station_data)
        self.main_app.station_buttons.insert(target_idx, button_widget)
        
        if self.main_app.current_index == master_idx: self.main_app.current_index = master_target_idx

        self.main_app.app_settings["last_station_index"] = self.main_app.current_index
        save_persistent_settings(self.main_app.app_settings)
        self.refresh_layout_indices()
        save_persisted_station_order()
        event.acceptProposedAction()

    def rearrange_layout(self):
        widgets = []
        for i in range(self.layout.count()):
            w = self.layout.itemAt(i).widget()
            if w: widgets.append(w)
        for w in widgets: self.layout.removeWidget(w)
            
        for r in range(self.layout.rowCount()):
            self.layout.setRowStretch(r, 0)
        for c in range(self.layout.columnCount()):
            self.layout.setColumnStretch(c, 0)

        view_mode = getattr(self.main_app, "view_mode", "list")
        if view_mode == "list":
            self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.layout.setSpacing(4)
            for i, btn in enumerate(self.main_app.station_buttons):
                btn.show()
                self.layout.addWidget(btn, i, 0)
            if self.main_app.sidebar_picker_container.isVisible():
                self.main_app.sidebar_picker_container.setFixedWidth(190)
        elif view_mode == "coverflow":
            self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main_app.sidebar_picker_container.setMinimumWidth(560)
            self.main_app.sidebar_picker_container.setMaximumWidth(99999)
            self.layout.setSpacing(0)
            if self.main_app.cover_flow_widget:
                self.layout.addWidget(self.main_app.cover_flow_widget, 0, 0, Qt.AlignmentFlag.AlignCenter)
                self.main_app.cover_flow_widget.show()
                self.main_app.cover_flow_widget.sync_to_current_station()
        else:
            self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            self.main_app.sidebar_picker_container.setMinimumWidth(40)
            self.main_app.sidebar_picker_container.setMaximumWidth(99999)
            
            width = self.width()
            if self.main_app.scroll_area.viewport().width() > 10:
                width = self.main_app.scroll_area.viewport().width()
            elif self.main_app.workspace_splitter.sizes()[1] > 10:
                width = self.main_app.workspace_splitter.sizes()[1]
                
            margin_left, _, margin_right, _ = self.layout.getContentsMargins()
            available_width = max(10, width - margin_left - margin_right)
            
            total_items = len(self.main_app.station_buttons)

            gap = 8
            min_tile_size = 70
            max_tile_size = 82
            target_tile_size = 76
            cols = max(1, int((available_width + gap) // (target_tile_size + gap)))
            cols = min(max(1, total_items), cols)
            tile_size = int((available_width - (gap * max(0, cols - 1))) / cols)
            tile_size = max(min_tile_size, min(max_tile_size, tile_size))

            self.layout.setSpacing(gap)
            for i, btn in enumerate(self.main_app.station_buttons):
                btn.show()
                btn.setText("")
                btn.setFixedSize(tile_size, tile_size)
                icon_sz = max(16, tile_size - 10)
                btn.setIconSize(QSize(icon_sz, icon_sz))
                r_idx = i // cols
                c_idx = i % cols
                self.layout.addWidget(btn, r_idx, c_idx, Qt.AlignmentFlag.AlignCenter)

    def refresh_layout_indices(self):
        self.rearrange_layout()
        if getattr(self.main_app, "view_mode", "list") == "coverflow":
            self.main_app.update_active_station_highlight()
            return
        rendered_stations = [s for s in STATIONS if s.get("enabled", True)]
        for i, btn in enumerate(self.main_app.station_buttons):
            try: btn.clicked.disconnect()
            except: pass
            if i < len(rendered_stations):
                master_idx = STATIONS.index(rendered_stations[i])
                btn.clicked.connect(lambda _, idx=master_idx: self.main_app.load_station(idx))
        self.main_app.update_active_station_highlight()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self.main_app, "view_mode", "list") in ("tile", "coverflow"):
            self.rearrange_layout()


class HoverPickerContainer(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.main_app.set_view_mode_button_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.main_app.set_view_mode_button_visible(False)
        super().leaveEvent(event)


class ClickableArtLabel(QLabel):
    clicked_signal = pyqtSignal()
    right_clicked_signal = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_signal.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            self.right_clicked_signal.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class CoverFlowStationWidget(QWidget):
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.selected_index = self._current_enabled_position()
        self.hovered_offset = None
        self.snap_offset = 0.0
        self.snap_velocity = 0.0
        self.setMinimumSize(560, 280)
        self.snap_timer = QTimer(self)
        self.snap_timer.setInterval(16)
        self.snap_timer.timeout.connect(self.process_snap_motion)

    def _enabled_stations(self):
        return [s for s in STATIONS if s.get("enabled", True)]

    def _current_enabled_position(self):
        enabled = self._enabled_stations()
        if not enabled:
            return 0
        for i, station in enumerate(enabled):
            if STATIONS.index(station) == self.main_app.current_index:
                return i
        return 0

    def sync_to_current_station(self):
        self.selected_index = self._current_enabled_position()
        self.update()

    def select_relative(self, delta):
        enabled = self._enabled_stations()
        if not enabled:
            return
        self.selected_index = (self.selected_index + delta) % len(enabled)
        self.snap_offset += -delta
        self.snap_velocity += -delta * 0.16
        if not self.snap_timer.isActive():
            self.snap_timer.start()
        self.update()

    def process_snap_motion(self):
        self.snap_velocity += (0.0 - self.snap_offset) * 0.18
        self.snap_velocity *= 0.70
        self.snap_offset += self.snap_velocity
        if abs(self.snap_offset) < 0.01 and abs(self.snap_velocity) < 0.01:
            self.snap_offset = 0.0
            self.snap_velocity = 0.0
            self.snap_timer.stop()
        self.update()

    def activate_selected(self):
        enabled = self._enabled_stations()
        if not enabled:
            return
        self.main_app.load_station(STATIONS.index(enabled[self.selected_index]))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.select_relative(-1 if delta > 0 else 1)
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.select_relative(-1)
            event.accept()
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.select_relative(1)
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activate_selected()
            event.accept()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            offset = self._offset_for_position(event.position())
            if offset is None or offset == 0:
                self.activate_selected()
            else:
                self.select_relative(offset)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.hovered_offset = self._offset_for_position(event.position())
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered_offset = None
        self.update()
        super().leaveEvent(event)

    def _offset_for_position(self, pos):
        center_x = self.width() / 2.0
        if pos.y() < self.height() * 0.18 or pos.y() > self.height() * 0.78:
            return None
        if pos.x() < center_x * 0.55:
            return -1
        if pos.x() > self.width() - (center_x * 0.55):
            return 1
        return 0

    def _station_pixmap(self, station):
        return self.main_app.station_logo_pixmap_for(station)

    def _fallback_pixmap(self, station, size):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor(self.main_app.current_accent_color)
        painter.setBrush(QColor(8, 10, 13, 235))
        painter.setPen(QPen(accent, max(2, size // 32)))
        painter.drawRoundedRect(2, 2, size - 4, size - 4, 10, 10)
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(11, size // 7))
        painter.setFont(font)
        text = station.get("art") or station.get("name", "?")[:1].upper()
        painter.drawText(QRect(8, 8, size - 16, size - 16), Qt.AlignmentFlag.AlignCenter, text)
        painter.end()
        return pixmap

    def _draw_reflection(self, painter, pixmap, rect, alpha):
        reflection_h = max(14, int(rect.height() * 0.34))
        reflection = pixmap.scaled(rect.width(), rect.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        reflection = reflection.transformed(QTransform().scale(1, -1))
        target = QRect(rect.left(), rect.bottom() + 4, rect.width(), reflection_h)
        painter.setOpacity(alpha * 0.22)
        painter.drawPixmap(target, reflection, QRect(0, 0, reflection.width(), reflection_h))
        painter.setOpacity(1.0)
        fade = QRadialGradient(QPointF(target.center()), max(target.width(), target.height()))
        fade.setColorAt(0.0, QColor(0, 0, 0, 30))
        fade.setColorAt(1.0, QColor(0, 0, 0, 220))
        painter.fillRect(target, QColor(0, 0, 0, 80))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        enabled = self._enabled_stations()
        if not enabled:
            painter.setPen(QColor("#ffffff"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No stations enabled")
            painter.end()
            return

        self.selected_index %= len(enabled)
        center_x = self.width() / 2.0
        top_y = max(18, int(self.height() * 0.12))
        base_size = max(82, min(int(self.width() * 0.32), int(self.height() * 0.54), 190))
        side_size = int(base_size * 0.68)
        accent = QColor(self.main_app.current_accent_color)

        visible_offsets = [-2, 2, -1, 1, 0]
        for offset in visible_offsets:
            if len(enabled) == 1 and offset != 0:
                continue
            station = enabled[(self.selected_index + offset) % len(enabled)]
            size = base_size if offset == 0 else side_size
            distance = abs(offset)
            animated_offset = offset + self.snap_offset
            x_shift = animated_offset * (base_size * 0.62)
            y_shift = distance * 14
            rect = QRect(
                int(center_x - size / 2 + x_shift),
                int(top_y + y_shift),
                size,
                size,
            )

            pixmap = self._station_pixmap(station)
            if not pixmap or pixmap.isNull():
                pixmap = self._fallback_pixmap(station, size)

            scaled = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            draw_rect = QRect(
                rect.left() + int((rect.width() - scaled.width()) / 2),
                rect.top() + int((rect.height() - scaled.height()) / 2),
                scaled.width(),
                scaled.height(),
            )

            painter.save()
            opacity = 1.0 if offset == 0 else max(0.34, 0.72 - distance * 0.18)
            painter.setOpacity(opacity)
            if offset != 0:
                transform = QTransform()
                transform.translate(draw_rect.center().x(), draw_rect.center().y())
                transform.shear(-0.16 if offset > 0 else 0.16, 0)
                transform.translate(-draw_rect.center().x(), -draw_rect.center().y())
                painter.setTransform(transform, True)
            painter.drawPixmap(draw_rect, scaled)
            painter.restore()

            if offset == 0:
                glow_rect = draw_rect.adjusted(-5, -5, 5, 5)
                painter.setPen(QPen(accent, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(glow_rect, 8, 8)
                self._draw_reflection(painter, scaled, draw_rect, 1.0)

        selected_station = enabled[self.selected_index]
        title_rect = QRect(12, int(self.height() * 0.76), self.width() - 24, 44)
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        station_name = metrics.elidedText(selected_station["name"], Qt.TextElideMode.ElideRight, title_rect.width())
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, station_name)

        painter.end()


class ElidedCatalogueLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.full_text = text

    def set_full_text(self, text):
        self.full_text = text
        self.update_elided_text()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_elided_text()

    def update_elided_text(self):
        metrics = QFontMetrics(self.font())
        elided = metrics.elidedText(self.full_text, Qt.TextElideMode.ElideRight, self.width() - 4)
        super().setText(elided)


class AnimatedTitleIconButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        
        self.rotation_angle = 0.0
        self._hovered = False
        self.ring_glow = 1.0
        
        self.spin_timer = QTimer(self)
        self.spin_timer.setInterval(10)
        self.spin_timer.timeout.connect(self._process_spin)
        
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(10000)
        self.pulse_timer.timeout.connect(self._process_pulse)
        self.pulse_timer.start()

    def _process_spin(self):
        if self._hovered:
            self.rotation_angle = (self.rotation_angle + 1.5) % 360.0
            self.update()
        else:
            if self.rotation_angle != 0.0:
                self.rotation_angle = 0.0
                self.update()
            self.spin_timer.stop()

    def _process_pulse(self):
        if self.main_app.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            t = time.time() * 7.5
            self.ring_glow = 1.0 + (math.sin(t) * 0.4) + (math.cos(t * 1.5) * 0.1)
            self.ring_glow = max(0.5, min(1.8, self.ring_glow))
        else:
            self.ring_glow = 1.0
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.spin_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        
        ring_radius = 18.0
        glow_alpha = int(max(70, min(255, 140 * self.ring_glow)))
        pen = QPen(QColor(self.main_app.current_accent_color.red(), self.main_app.current_accent_color.green(), self.main_app.current_accent_color.blue(), glow_alpha), 1.5)
        painter.setPen(pen)
        painter.drawEllipse(QPoint(int(cx), int(cy)), int(ring_radius), int(ring_radius))
        
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.rotation_angle)
        painter.translate(-cx, -cy)
        
        target_pix = self.main_app.default_pixmap
        if target_pix and not target_pix.isNull():
            draw_w = 30
            draw_h = 30
            dx = int(cx - draw_w / 2.0)
            dy = int(cy - draw_h / 2.0)
            painter.drawPixmap(QRect(dx, dy, draw_w, draw_h), target_pix)
        else:
            painter.setPen(QColor(self.main_app.current_accent_color))
            font = painter.font()
            font.setPointSize(16)
            painter.setFont(font)
            painter.drawText(QRect(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, "📻")
            
        painter.restore()
        painter.end()


class ModernRadioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app_settings = load_persistent_settings()
        if "custom_themes" not in self.app_settings:
            self.app_settings["custom_themes"] = {}
        if "animation_type" not in self.app_settings:
            self.app_settings["animation_type"] = "Warp Speed"
            
        self.current_index = self.app_settings.get("last_station_index", 0)
        if self.current_index >= len(STATIONS) or self.current_index < 0:
            self.current_index = 0
            
        # Custom Radio Attributes
        self.custom_tracks = []
        self.custom_track_index = -1
        self.custom_station_last_track = {}
        
        self.drag_position = QPoint()
        self.border_width = 6
        self.overlay_is_visible = False
        self.current_pixmap = None
        self.station_logo_pixmap = None
        self.current_accent_color = QColor("#45f3ff")
        self.show_loading_logo = True
        self.cycle_timer = QTimer()
        self.cycle_timer.setSingleShot(True)
        self.cycle_timer.timeout.connect(self.handle_artwork_cycle)
        self.rotation_angle = 0.0
        self.spin_timer = QTimer()
        self.spin_timer.setInterval(16)
        self.spin_timer.timeout.connect(self.rotate_image)
        
        self.fade_timer = QTimer()
        self.fade_timer.setInterval(25)
        self.fade_timer.timeout.connect(self.process_audio_fade_loop)
        self.target_volume = self.app_settings["volume"]
        self.fade_step = 0.0
        self.fading_out_for_swap = False
        self.pending_station_index = -1
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        self.setMinimumSize(APP_MIN_WIDTH, APP_MIN_HEIGHT)
        
        self.default_icon_path = os.path.join(SCRIPT_DIR, "icon.png")
        self.default_pixmap = QPixmap(self.default_icon_path) if os.path.exists(self.default_icon_path) else None
        self.engine = RadioEngine(self)
        self.media_player = self.engine.media_player
        self.audio_output = self.engine.audio_output
        self.audio_output.setVolume(self.app_settings["volume"] / 100.0)
        self.audio_output.setMuted(self.app_settings["muted"])
        self.media_player.errorOccurred.connect(self.on_player_error)
        self.media_player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.metadata_worker = self.engine.metadata_worker
        self.metadata_worker.update_url("")
        self.metadata_worker.metadata_updated.connect(self.on_metadata_received)
        self.metadata_worker.start()
        self.art_worker = AlbumArtWorker()
        self.art_worker.image_ready.connect(self.on_image_ready)
        self.art_worker.image_failed.connect(self.on_image_load_failed)
        self.art_search_worker = ArtworkSearchWorker()
        self.art_search_worker.art_found.connect(self.art_worker.fetch)
        self.art_search_worker.search_failed.connect(self.on_image_load_failed)
        self.list_workers = []
        self.recorder = self.engine.recorder
        self.station_buttons = []
        self.cover_flow_widget = None
        self.catalogue_buttons = {}
        self.is_mini_player = False
        self.pre_mini_geometry = None
        self.view_mode = self.app_settings["view_mode"]
        if self.view_mode == "list" or self.view_mode not in ("tile", "coverflow"):
            self.view_mode = "tile"
            self.app_settings["view_mode"] = self.view_mode
        self.panel_visibility_mode = self.app_settings.get("panel_visibility_mode")
        if self.panel_visibility_mode not in PANEL_VISIBILITY_MODES:
            self.panel_visibility_mode = "both" if self.app_settings.get("sidebar_visible", True) else "left"
            self.app_settings["panel_visibility_mode"] = self.panel_visibility_mode
        self.artwork_mode = self.app_settings["artwork_mode"]
        
        self.metadata_hide_timer = QTimer(self)
        self.metadata_hide_timer.setSingleShot(True)
        self.metadata_hide_timer.setInterval(10000)
        self.metadata_hide_timer.timeout.connect(self.fade_out_track_info)

        self.init_user_interface()
        self.load_station(self.current_index)

    def init_user_interface(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        
        if not self.default_pixmap or self.default_pixmap.isNull():
            self.default_pixmap = QPixmap(64, 64)
            self.default_pixmap.fill(Qt.GlobalColor.transparent)
            p = QPainter(self.default_pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setBrush(QColor("#000000"))
            p.setPen(QPen(QColor("#45f3ff"), 3))
            p.drawRoundedRect(2, 2, 60, 60, 14, 14)
            p.setPen(QPen(QColor("#ffffff"), 2))
            p.drawText(QRect(0, 0, 64, 64), Qt.AlignmentFlag.AlignCenter, "📻")
            p.end()
            
        central = QWidget(self)
        central.setObjectName("central")
        central.setMouseTracking(True)
        self.setCentralWidget(central)
        
        self.window_main_layout = QVBoxLayout(central)
        self.window_main_layout.setContentsMargins(self.border_width, self.border_width, self.border_width, self.border_width)
        self.window_main_layout.setSpacing(0)
        
        self.custom_title_bar = QWidget()
        self.custom_title_bar.setObjectName("custom_title_bar")
        self.custom_title_bar.setFixedHeight(56)
        self.custom_title_bar.setMouseTracking(True)
        
        title_layout = QHBoxLayout(self.custom_title_bar)
        title_layout.setContentsMargins(8, 0, 4, 0)
        
        self.title_icon_btn = AnimatedTitleIconButton(main_app=self)
        self.title_icon_btn.clicked.connect(self.toggle_options_plane)
        title_layout.addWidget(self.title_icon_btn)
        title_layout.addStretch()
        
        self.window_buttons_container = QWidget()
        self.window_buttons_container.setMouseTracking(True)
        self.buttons_container_opacity = QGraphicsOpacityEffect(self.window_buttons_container)
        self.window_buttons_container.setGraphicsEffect(self.buttons_container_opacity)
        self.buttons_container_opacity.setOpacity(0.0)
        
        buttons_layout = QHBoxLayout(self.window_buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(4)
        
        self.min_btn = QPushButton("—")
        self.min_btn.setProperty("class", "title_bar_btn")
        self.min_btn.clicked.connect(self.showMinimized)
        buttons_layout.addWidget(self.min_btn)
        
        self.max_btn = QPushButton("⬜")
        self.max_btn.setProperty("class", "title_bar_btn")
        self.max_btn.clicked.connect(self.toggle_maximize_restore)
        buttons_layout.addWidget(self.max_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("close_btn")
        self.close_btn.setProperty("class", "title_bar_btn")
        self.close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_btn)
        
        title_layout.addWidget(self.window_buttons_container)
        self.window_main_layout.addWidget(self.custom_title_bar)
        
        self.content_stack_engine = QStackedWidget()
        self.window_main_layout.addWidget(self.content_stack_engine, 1)
        
        self.player_workspace_widget = QWidget()
        workspace_container_layout = QVBoxLayout(self.player_workspace_widget)
        workspace_container_layout.setContentsMargins(0, 0, 0, 0)
        workspace_container_layout.setSpacing(0)
        
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setMouseTracking(True)
        self.workspace_splitter.setChildrenCollapsible(False)
        workspace_container_layout.addWidget(self.workspace_splitter, 1)
        
        self.content_stack_engine.addWidget(self.player_workspace_widget)

        self.mini_player_widget = QWidget()
        self.mini_player_widget.setObjectName("mini_player_widget")
        mini_layout = QHBoxLayout(self.mini_player_widget)
        mini_layout.setContentsMargins(10, 8, 10, 8)
        mini_layout.setSpacing(8)
        self.mini_art_label = QLabel()
        self.mini_art_label.setFixedSize(58, 58)
        self.mini_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mini_layout.addWidget(self.mini_art_label)
        self.mini_station_label = QLabel("Radio")
        self.mini_station_label.setStyleSheet("color:#ffffff; font-size:12px; font-weight:800;")
        self.mini_station_label.setWordWrap(True)
        mini_layout.addWidget(self.mini_station_label, 1)
        self.mini_mute_btn = QPushButton("M")
        self.mini_mute_btn.setToolTip("Mute")
        self.mini_mute_btn.clicked.connect(self.toggle_audio_mute)
        mini_layout.addWidget(self.mini_mute_btn)
        self.mini_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.mini_volume_slider.setRange(0, 100)
        self.mini_volume_slider.setValue(self.target_volume)
        self.mini_volume_slider.setFixedWidth(86)
        self.mini_volume_slider.valueChanged.connect(self.on_volume_slider_moved)
        mini_layout.addWidget(self.mini_volume_slider)
        self.mini_prev_station_btn = QPushButton("◀")
        self.mini_prev_station_btn.setToolTip("Previous Station")
        self.mini_prev_station_btn.clicked.connect(self.load_previous_station)
        mini_layout.addWidget(self.mini_prev_station_btn)
        self.mini_next_station_btn = QPushButton("▶")
        self.mini_next_station_btn.setToolTip("Next Station")
        self.mini_next_station_btn.clicked.connect(self.load_next_station)
        mini_layout.addWidget(self.mini_next_station_btn)
        self.mini_restore_btn = QPushButton("▣")
        self.mini_restore_btn.setToolTip("Restore")
        self.mini_restore_btn.clicked.connect(self.toggle_mini_player_mode)
        mini_layout.addWidget(self.mini_restore_btn)
        self.content_stack_engine.addWidget(self.mini_player_widget)
        
        self.player_container = QWidget()
        self.player_container.setObjectName("player_container")
        self.player_container.setMinimumWidth(80)
        player_layout = QVBoxLayout(self.player_container)
        player_layout.setContentsMargins(6, 6, 6, 6)
        player_layout.setSpacing(6)
        self.player_layout = player_layout
        self.workspace_container_layout = workspace_container_layout
        
        self.art_display = ClickableArtLabel()
        self.art_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.art_display.clicked_signal.connect(self.toggle_artwork_presentation_mode)
        self.art_display.right_clicked_signal.connect(self.cycle_animation_fx_mode)
        
        text_layout = QVBoxLayout(self.art_display)
        text_layout.setContentsMargins(12, 12, 12, 12)
        
        self.track_info = QLabel("Connecting...")
        self.track_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.track_info.setWordWrap(True)
        self.track_info.setStyleSheet("color:#ffffff; font-size:10px; font-weight:bold; background-color:rgba(0,0,0,0.85); border-radius:8px; padding:4px;")
        
        self.track_info_opacity = QGraphicsOpacityEffect(self.track_info)
        self.track_info.setGraphicsEffect(self.track_info_opacity)
        self.track_info_opacity.setOpacity(1.0)
        
        self.track_info_anim = QPropertyAnimation(self.track_info_opacity, b"opacity")
        self.track_info_anim.setDuration(500)
        
        text_layout.addWidget(self.track_info)
        text_layout.addStretch()
        player_layout.addWidget(self.art_display, 1, Qt.AlignmentFlag.AlignCenter)
        
        self.playback_controls_tray = QWidget()
        self.playback_controls_tray.setMouseTracking(True)
        
        tray_layout = QHBoxLayout(self.playback_controls_tray)
        tray_layout.setContentsMargins(10, 0, 10, 6)
        tray_layout.setSpacing(6)
        
        self.btn_rec = QPushButton("⏺")
        self.btn_rec.setToolTip("Record Live Feed to Local Disk")
        self.btn_rec.clicked.connect(self.toggle_stream_recording)
        tray_layout.addWidget(self.btn_rec)
        tray_layout.addStretch()
        
        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setToolTip("Previous Local Custom Track")
        self.btn_prev.clicked.connect(self.play_previous_custom_track)
        self.btn_prev.setVisible(False)
        tray_layout.addWidget(self.btn_prev)
        
        self.btn_next = QPushButton("⏭")
        self.btn_next.setToolTip("Skip Local Custom Track")
        self.btn_next.clicked.connect(self.play_next_custom_track)
        self.btn_next.setVisible(False)
        tray_layout.addWidget(self.btn_next)
        
        self.btn_mute = QPushButton("🔇" if self.app_settings.get("muted", False) else "🔊")
        self.btn_mute.clicked.connect(self.toggle_audio_mute)
        tray_layout.addWidget(self.btn_mute)
        
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.target_volume)
        self.volume_slider.setFixedWidth(70)
        self.volume_slider.valueChanged.connect(self.on_volume_slider_moved)
        tray_layout.addWidget(self.volume_slider)
        tray_layout.addStretch()
        
        self.btn_hide = QPushButton("⇋")
        self.btn_hide.setToolTip("Cycle Panel Visibility")
        self.btn_hide.clicked.connect(self.toggle_sidebar_visibility)
        tray_layout.addWidget(self.btn_hide)

        self.btn_mini = QPushButton("MINI")
        self.btn_mini.setObjectName("mini_popout_btn")
        self.btn_mini.setToolTip("Mini Player")
        self.btn_mini.setFixedSize(40, 24)
        self.btn_mini.clicked.connect(self.toggle_mini_player_mode)
        tray_layout.addWidget(self.btn_mini)
        
        player_layout.addWidget(self.playback_controls_tray)
        self.workspace_splitter.addWidget(self.player_container)
        
        self.sidebar_picker_container = HoverPickerContainer(main_app=self)
        sidebar_v_layout = QGridLayout(self.sidebar_picker_container)
        sidebar_v_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_v_layout.setSpacing(0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.scroll_content = AntigravityStationListWidget(main_app=self)
        self.scroll_area.setWidget(self.scroll_content)
        sidebar_v_layout.addWidget(self.scroll_area, 0, 0)
        
        self.btn_view_mode = QPushButton()
        self.btn_view_mode.setFixedSize(22, 22)
        self.btn_view_mode.setText(self.view_mode_button_text())
        self.btn_view_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_mode.clicked.connect(self.toggle_view_mode)
        
        self.view_mode_effect = QGraphicsOpacityEffect(self.btn_view_mode)
        self.btn_view_mode.setGraphicsEffect(self.view_mode_effect)
        self.view_mode_effect.setOpacity(0.0)
        
        view_mode_box_layout = QHBoxLayout()
        view_mode_box_layout.setContentsMargins(0, 0, 4, 4)
        view_mode_box_layout.addStretch()
        view_mode_box_layout.addWidget(self.btn_view_mode)
        
        self.overlay_widget_wrapper = QWidget()
        self.overlay_widget_wrapper.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.overlay_widget_wrapper.setStyleSheet("background: transparent;")
        self.overlay_widget_wrapper.setLayout(view_mode_box_layout)
        
        sidebar_v_layout.addWidget(self.overlay_widget_wrapper, 0, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        self.workspace_splitter.addWidget(self.sidebar_picker_container)

        self.cover_controls_host = QWidget()
        self.cover_controls_host.setObjectName("cover_controls_host")
        self.cover_controls_host.setVisible(False)
        cover_controls_layout = QHBoxLayout(self.cover_controls_host)
        cover_controls_layout.setContentsMargins(16, 4, 16, 8)
        cover_controls_layout.setSpacing(0)
        cover_controls_layout.addStretch()
        cover_controls_layout.addStretch()
        self.cover_controls_layout = cover_controls_layout
        self.workspace_container_layout.addWidget(self.cover_controls_host)
        
        # --- CONFIGURATION INTERFACE ---
        self.options_plane = QWidget()
        self.options_plane.setObjectName("options_plane")
        
        options_main_layout = QVBoxLayout(self.options_plane)
        options_main_layout.setContentsMargins(12, 6, 12, 12)
        options_main_layout.setSpacing(4)
        
        lbl_opt_title = QLabel("SYSTEM CONFIGURATION CONTROL")
        lbl_opt_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #45f3ff; padding-top: 2px; padding-bottom: 2px;")
        options_main_layout.addWidget(lbl_opt_title)
        
        self.options_scroll_wrapper = QScrollArea()
        self.options_scroll_wrapper.setWidgetResizable(True)
        self.options_scroll_wrapper.setStyleSheet("background-color: transparent; border: none;")
        
        options_scroll_content_widget = QWidget()
        options_scroll_content_widget.setStyleSheet("background-color: transparent;")
        options_scroll_vertical_layout = QVBoxLayout(options_scroll_content_widget)
        options_scroll_vertical_layout.setContentsMargins(0, 0, 0, 0)
        options_scroll_vertical_layout.setSpacing(6)
        options_scroll_vertical_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        columns_layout_wrapper = QHBoxLayout()
        columns_layout_wrapper.setSpacing(10)
        columns_layout_wrapper.setContentsMargins(0, 0, 0, 0)
        
        # --- LEFT COLUMN PANELS ---
        left_column_container = QWidget()
        left_column_layout = QVBoxLayout(left_column_container)
        left_column_layout.setContentsMargins(0, 0, 0, 0)
        left_column_layout.setSpacing(6)
        left_column_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        grp_add_station = QGroupBox("Add Custom Station")
        grp_add_layout = QVBoxLayout(grp_add_station)
        grp_add_layout.setSpacing(6)
        grp_add_layout.setContentsMargins(10, 10, 10, 10)
        
        self.txt_add_name = QLineEdit()
        self.txt_add_name.setPlaceholderText("Station Label...")
        grp_add_layout.addWidget(self.txt_add_name)
        
        self.txt_add_url = QLineEdit()
        self.txt_add_url.setPlaceholderText("Streaming Endpoint Target URL...")
        grp_add_layout.addWidget(self.txt_add_url)
        
        btn_append_station = QPushButton("Add to Registry")
        btn_append_station.setStyleSheet("background-color: #0e151e; font-size:11px; font-weight:bold; min-width:100%; height:26px;")
        btn_append_station.clicked.connect(self.append_custom_station_to_catalogue)
        grp_add_layout.addWidget(btn_append_station)
        left_column_layout.addWidget(grp_add_station)
        
        # --- LOCAL MP3 AUDIO FOLDER PLAYER PANEL ---
        grp_custom_folder_station = QGroupBox("Create MP3 Folder Radio")
        grp_folder_layout = QVBoxLayout(grp_custom_folder_station)
        grp_folder_layout.setSpacing(6)
        grp_folder_layout.setContentsMargins(10, 10, 10, 10)
        
        self.txt_folder_station_name = QLineEdit()
        self.txt_folder_station_name.setPlaceholderText("Custom Radio Name...")
        grp_folder_layout.addWidget(self.txt_folder_station_name)
        
        btn_select_mp3_folder = QPushButton("Select Folder & Build")
        btn_select_mp3_folder.setStyleSheet("background-color: #111a16; font-size:11px; font-weight:bold; min-width:100%; height:26px;")
        btn_select_mp3_folder.clicked.connect(self.create_custom_folder_radio_station)
        grp_folder_layout.addWidget(btn_select_mp3_folder)
        left_column_layout.addWidget(grp_custom_folder_station)
        
        grp_visuals = QGroupBox("Preferences & Themes")
        grp_vis_layout = QGridLayout(grp_visuals)
        grp_vis_layout.setSpacing(8)
        grp_vis_layout.setContentsMargins(10, 10, 10, 10)
        
        grp_vis_layout.addWidget(QLabel("Theme Palette:"), 0, 0)
        self.theme_selector = QComboBox()
        self.rebuild_theme_combobox_items()
        self.theme_selector.currentTextChanged.connect(self.on_theme_selection_changed)
        grp_vis_layout.addWidget(self.theme_selector, 0, 1)
        
        custom_color_tools_panel = QHBoxLayout()
        custom_color_tools_panel.setSpacing(6)
        
        btn_pick_color = QPushButton("🎨 Custom Color")
        btn_pick_color.setStyleSheet("font-size: 10px; height: 22px; background-color: #111115; font-weight: bold; min-width: 105px;")
        btn_pick_color.clicked.connect(self.trigger_custom_color_picker_dialog)
        custom_color_tools_panel.addWidget(btn_pick_color)
        
        self.btn_delete_preset = QPushButton("✕ Delete")
        self.btn_delete_preset.setStyleSheet("font-size: 10px; height: 22px; background-color: #210d10; color: #ff4d4d; font-weight: bold; min-width: 65px;")
        self.btn_delete_preset.clicked.connect(self.delete_current_user_theme_preset)
        custom_color_tools_panel.addWidget(self.btn_delete_preset)
        custom_color_tools_panel.addStretch()
        
        grp_vis_layout.addLayout(custom_color_tools_panel, 1, 0, 1, 2)
        
        grp_vis_layout.addWidget(QLabel("FX Engine Core:"), 2, 0)
        self.anim_type_selector = QComboBox()
        self.anim_type_selector.addItems(FX_MODES)
        self.anim_type_selector.setCurrentText(self.app_settings.get("animation_type", "Warp Speed"))
        self.anim_type_selector.currentTextChanged.connect(self.on_animation_type_changed)
        grp_vis_layout.addWidget(self.anim_type_selector, 2, 1)

        self.star_anim_checkbox = QCheckBox("Enable Interactive FX Engine")
        self.star_anim_checkbox.setChecked(self.app_settings.get("star_animation_enabled", True))
        self.star_anim_checkbox.stateChanged.connect(self.on_star_anim_toggle_changed)
        grp_vis_layout.addWidget(self.star_anim_checkbox, 3, 0, 1, 2)
        left_column_layout.addWidget(grp_visuals)
        
        columns_layout_wrapper.addWidget(left_column_container, 1)
        
        # --- RIGHT COLUMN PANEL ---
        grp_registry = QGroupBox("Station Registry Visibility Manager")
        grp_reg_layout = QVBoxLayout(grp_registry)
        grp_reg_layout.setContentsMargins(10, 10, 10, 10)
        
        self.options_scroll = QScrollArea()
        self.options_scroll.setWidgetResizable(True)
        self.options_scroll.setStyleSheet("background-color: transparent;")
        self.options_scroll_content = QWidget()
        self.options_scroll_content.setStyleSheet("background-color: transparent;")
        self.options_list_layout = QVBoxLayout(self.options_scroll_content)
        self.options_list_layout.setContentsMargins(0, 0, 0, 0)
        self.options_list_layout.setSpacing(4)
        self.options_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.options_scroll.setWidget(self.options_scroll_content)
        grp_reg_layout.addWidget(self.options_scroll)
        
        columns_layout_wrapper.addWidget(grp_registry, 1)
        options_scroll_vertical_layout.addLayout(columns_layout_wrapper, 1)

        library_layout_wrapper = QHBoxLayout()
        library_layout_wrapper.setSpacing(10)

        grp_history = QGroupBox("Now Playing History")
        history_layout = QVBoxLayout(grp_history)
        history_layout.setContentsMargins(10, 10, 10, 10)
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(120)
        history_layout.addWidget(self.history_list)
        library_layout_wrapper.addWidget(grp_history, 1)

        grp_recordings = QGroupBox("Recordings Library")
        recordings_layout = QVBoxLayout(grp_recordings)
        recordings_layout.setContentsMargins(10, 10, 10, 10)
        self.recordings_list = QListWidget()
        self.recordings_list.setMinimumHeight(120)
        recordings_layout.addWidget(self.recordings_list)
        recordings_controls = QHBoxLayout()
        btn_play_recording = QPushButton("Play")
        btn_play_recording.clicked.connect(self.play_selected_recording)
        recordings_controls.addWidget(btn_play_recording)
        btn_delete_recording = QPushButton("Delete")
        btn_delete_recording.clicked.connect(self.delete_selected_recording)
        recordings_controls.addWidget(btn_delete_recording)
        btn_open_recordings = QPushButton("Folder")
        btn_open_recordings.clicked.connect(self.open_recordings_folder)
        recordings_controls.addWidget(btn_open_recordings)
        recordings_layout.addLayout(recordings_controls)
        library_layout_wrapper.addWidget(grp_recordings, 1)
        options_scroll_vertical_layout.addLayout(library_layout_wrapper)
        
        self.options_scroll_wrapper.setWidget(options_scroll_content_widget)
        options_main_layout.addWidget(self.options_scroll_wrapper, 1)
        
        utilities_panel = QHBoxLayout()
        utilities_panel.setSpacing(6)
        btn_export = QPushButton("📤 Backup")
        btn_export.setStyleSheet("background-color:#0d1b1e; font-size:10px; height:24px; font-weight:bold; min-width:80px; max-width:120px;")
        btn_export.clicked.connect(self.export_user_configuration_backup)
        utilities_panel.addWidget(btn_export)
        
        btn_import = QPushButton("📥 Restore")
        btn_import.setStyleSheet("background-color:#1c1e0d; font-size:10px; height:24px; font-weight:bold; min-width:80px; max-width:120px;")
        btn_import.clicked.connect(self.import_user_configuration_backup)
        utilities_panel.addWidget(btn_import)
        options_main_layout.addLayout(utilities_panel)
        
        self.content_stack_engine.addWidget(self.options_plane)
        
        self.controls_effect = QGraphicsOpacityEffect(self.playback_controls_tray)
        self.playback_controls_tray.setGraphicsEffect(self.controls_effect)
        self.controls_effect.setOpacity(0.0)
        
        self.controls_anim = QPropertyAnimation(self.controls_effect, b"opacity")
        self.controls_anim.setDuration(400)
        
        self.window_btn_anim = QPropertyAnimation(self.buttons_container_opacity, b"opacity")
        self.window_btn_anim.setDuration(250)

        self.view_btn_anim = QPropertyAnimation(self.view_mode_effect, b"opacity")
        self.view_btn_anim.setDuration(250)

        self.refresh_scroll_picker_list()
        self.rebuild_options_catalog_view()
        self.refresh_history_list()
        self.refresh_recordings_list()
        self.evaluate_preset_deletion_button_state()
        self.restore_saved_window_geometry()
        self.apply_view_mode_layout()

    def restore_saved_window_geometry(self):
        saved_w = max(APP_MIN_WIDTH, self.app_settings.get("window_width", APP_MIN_WIDTH))
        saved_h = max(APP_MIN_HEIGHT, self.app_settings.get("window_height", APP_MIN_HEIGHT))
        saved_x = self.app_settings.get("window_x", -1)
        saved_y = self.app_settings.get("window_y", -1)
        
        if not self.app_settings.get("sidebar_visible", True):
            self.resize(APP_MIN_WIDTH, saved_h)
        else:
            self.resize(saved_w, saved_h)
            
        if saved_x != -1 and saved_y != -1:
            self.move(saved_x, saved_y)

        saved_splitter = self.app_settings.get("splitter_state", "")
        if saved_splitter:
            self.workspace_splitter.restoreState(QByteArray.fromHex(saved_splitter.encode()))
        else:
            self.workspace_splitter.setSizes([312, 208])

    def move_controls_to_player_panel(self):
        self.cover_controls_layout.removeWidget(self.playback_controls_tray)
        self.player_layout.removeWidget(self.playback_controls_tray)
        self.player_layout.addWidget(self.playback_controls_tray)
        self.cover_controls_host.setVisible(False)

    def move_controls_to_bottom_bar(self):
        self.player_layout.removeWidget(self.playback_controls_tray)
        self.cover_controls_layout.removeWidget(self.playback_controls_tray)
        self.cover_controls_layout.insertWidget(1, self.playback_controls_tray)
        self.cover_controls_host.setVisible(True)

    def update_artwork_square_constraints(self):
        if self.view_mode == "coverflow" or not self.player_container.isVisible():
            self.art_display.setMinimumSize(0, 0)
            self.art_display.setMaximumSize(16777215, 16777215)
            return

        available_w = max(120, self.player_container.width() - 22)
        available_h = max(120, self.workspace_splitter.height() - self.playback_controls_tray.sizeHint().height() - 28)
        square_size = max(150, min(available_w, available_h, 420))
        self.art_display.setFixedSize(square_size, square_size)

    def apply_view_mode_layout(self):
        is_coverflow = self.view_mode == "coverflow"
        self.art_display.setVisible(not is_coverflow)
        self.track_info.setVisible(not is_coverflow)
        self.btn_hide.setVisible(not is_coverflow)

        if is_coverflow:
            self.sidebar_picker_container.setVisible(True)
            self.app_settings["sidebar_visible"] = True
            self.move_controls_to_bottom_bar()
            self.player_container.setVisible(False)
            self.player_container.setMinimumWidth(0)
            self.player_container.setMaximumWidth(0)
            self.sidebar_picker_container.setMinimumWidth(560)
            self.sidebar_picker_container.setMaximumWidth(99999)

            target_w = max(self.width(), APP_MIN_WIDTH)
            target_h = max(self.height(), APP_MIN_HEIGHT)
            if self.width() < target_w or self.height() < target_h:
                self.resize(target_w, target_h)
            self.workspace_splitter.setSizes([0, max(560, target_w)])
        else:
            mode = self.panel_visibility_mode if self.panel_visibility_mode in PANEL_VISIBILITY_MODES else "both"
            left_visible = mode in ("both", "left")
            right_visible = mode in ("both", "right")

            if left_visible:
                self.move_controls_to_player_panel()
            else:
                self.move_controls_to_bottom_bar()

            self.player_container.setVisible(left_visible)
            self.sidebar_picker_container.setVisible(right_visible)
            self.app_settings["sidebar_visible"] = right_visible
            self.player_container.setMinimumWidth(80)
            self.player_container.setMaximumWidth(16777215)
            self.sidebar_picker_container.setMaximumWidth(99999)

            if left_visible and right_visible:
                self.sidebar_picker_container.setMinimumWidth(260)
                player_w = max(260, min(380, int(self.width() * 0.34)))
                picker_w = max(300, self.width() - player_w)
                self.workspace_splitter.setSizes([player_w, picker_w])
            elif left_visible:
                self.workspace_splitter.setSizes([max(360, self.width()), 0])
            else:
                self.sidebar_picker_container.setMinimumWidth(360)
                self.workspace_splitter.setSizes([0, max(360, self.width())])

        self.update_artwork_square_constraints()
        self.scroll_content.rearrange_layout()
        self.apply_scaled_artwork()

    def resize_coverflow_stage(self):
        if self.view_mode != "coverflow":
            return
        available_w = max(APP_MIN_WIDTH - (self.border_width * 2), self.width() - (self.border_width * 2))
        self.workspace_splitter.setSizes([0, available_w])
        self.scroll_content.rearrange_layout()
        if self.cover_flow_widget:
            self.cover_flow_widget.update()

    def enterEvent(self, event):
        self.window_btn_anim.stop()
        self.window_btn_anim.setStartValue(self.buttons_container_opacity.opacity())
        self.window_btn_anim.setEndValue(1.0)
        self.window_btn_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.window_btn_anim.stop()
        self.window_btn_anim.setStartValue(self.buttons_container_opacity.opacity())
        self.window_btn_anim.setEndValue(0.0)
        self.window_btn_anim.start()
        self.set_overlay_visible(False)
        super().leaveEvent(event)

    def set_view_mode_button_visible(self, visible):
        self.view_btn_anim.stop()
        self.view_btn_anim.setStartValue(self.view_mode_effect.opacity())
        self.view_btn_anim.setEndValue(1.0 if visible else 0.0)
        self.view_btn_anim.start()

    def show_track_info_transiently(self, text):
        self.metadata_hide_timer.stop()
        self.track_info_anim.stop()
        self.track_info.setText(text)
        self.track_info_opacity.setOpacity(1.0)
        self.metadata_hide_timer.start()

    def fade_out_track_info(self):
        self.track_info_anim.stop()
        self.track_info_anim.setStartValue(self.track_info_opacity.opacity())
        self.track_info_anim.setEndValue(0.0)
        self.track_info_anim.start()

    def apply_theme_styles(self):
        h = self.current_accent_color.name()
        rec_bg = "#ff4d4d" if (hasattr(self, 'recorder') and self.recorder.is_recording) else "transparent"
        rec_fg = "#000000" if (hasattr(self, 'recorder') and self.recorder.is_recording) else h
        
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #000000; }}
            QWidget#central {{ background-color: #000000; border: 1px solid #1f2833; border-radius: 12px; }}
            QLabel {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; }}
            
            QPushButton.title_bar_btn {{ background-color: transparent; color: {h}; font-size: 11px; min-width: 24px; max-width: 24px; height: 20px; border-radius: 4px; }}
            QPushButton.title_bar_btn:hover {{ background-color: #1f2833; }}
            QPushButton#close_btn:hover {{ background-color: #ff4d4d; color: #ffffff; }}
            
            QPushButton {{ background-color: #000000; color: {h}; border: 1px solid rgba(31,40,51,0.5); border-radius: 8px; font-size: 14px; font-weight: 900; }}
            QPushButton:hover {{ background-color: {h}; color: #000000; border: 1px solid {h}; }}
            
            QWidget#player_container QPushButton {{ min-width: 28px; max-width: 28px; height: 24px; }}
            QWidget#player_container QPushButton#mini_popout_btn {{ min-width: 40px; max-width: 40px; height: 24px; font-size: 9px; border: 2px solid {h}; background-color: rgba({int(self.current_accent_color.red())}, {int(self.current_accent_color.green())}, {int(self.current_accent_color.blue())}, 0.18); }}
            
            QScrollArea {{ border: none; background-color: #000000; border-radius: 8px; }}
            
            QWidget#scroll_content QPushButton {{ background-color: rgba(14, 21, 30, 0.28); color: #e1e2e4; border: 1px solid rgba(69, 243, 255, 0.12); border-radius: 8px; }}
            QWidget#scroll_content QPushButton[viewMode=\"tile\"] {{ min-width: 0px; max-width: 9999px; min-height: 0px; max-height: 9999px; }}
            QWidget#scroll_content QPushButton:hover {{ background-color: rgba({int(self.current_accent_color.red())}, {int(self.current_accent_color.green())}, {int(self.current_accent_color.blue())}, 0.75); color: #000000; }}
            QWidget#scroll_content QPushButton[active=\"true\"] {{ background-color: rgba({int(self.current_accent_color.red())}, {int(self.current_accent_color.green())}, {int(self.current_accent_color.blue())}, 0.9); color: #000000; font-weight: bold; border: 1px solid {h}; }}
            
            QWidget#custom_title_bar {{ background-color: transparent; }}
            QWidget#player_container {{ background-color: #000000; }}
            QWidget#options_plane {{ background-color: #050505; border: none; border-radius: 12px; }}
            QGroupBox {{ border: 1px solid #1f2833; border-radius: 8px; margin-top: 6px; padding-top: 4px; font-weight: bold; color: #a1a1aa; font-size: 11px; }}
            QLineEdit {{ background-color: #000000; color: #ffffff; border: 1px solid #1f2833; border-radius: 6px; font-size: 11px; padding: 4px; font-weight: 600; }}
            QLineEdit:focus {{ border: 1px solid {h}; }}
            QGroupBox QLineEdit {{ min-width: 0px; max-width: 9999px; }}
            QComboBox {{ background-color: #000000; color: #ffffff; border: 1px solid #1f2833; border-radius: 6px; font-size: 11px; padding: 3px; font-weight: 600; }}
            QComboBox:focus {{ border: 1px solid {h}; }}
            QCheckBox {{ color: #ffffff; font-size: 11px; }}
            QPushButton#record_active_btn {{ background-color: {rec_bg}; color: {rec_fg}; }}
            QPushButton#record_active_btn:hover {{ background-color: #ff3333; color: #ffffff; }}
            QPushButton.catalogue_check_glyph_btn {{ font-size: 13px; font-weight: bold; min-width: 22px; max-width: 22px; height: 22px; background: transparent; border: none; }}
            QPushButton.catalogue_check_glyph_btn:hover {{ background-color: rgba({int(self.current_accent_color.red())}, {int(self.current_accent_color.green())}, {int(self.current_accent_color.blue())}, 0.2); color: {h}; }}
            QSlider::groove:horizontal {{ border: 1px solid #1f2833; height: 4px; background: #000000; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {h}; border: none; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }}
            QSlider::sub-page:horizontal {{ background: {h}; border-radius: 2px; }}
            QSplitter::handle {{ background-color: #0a0f14; }}
        """)

    def block_signals_wrapper(self, target, items):
        target.blockSignals(True)
        target.clear()
        target.addItems(items)
        target.setCurrentText(self.app_settings.get("theme_mode", "Auto"))
        target.blockSignals(False)

    def rebuild_theme_combobox_items(self):
        items = ["Auto", "Cyan Neon", "Emerald Matrix", "Amber Retro", "Hot Pink", "Sunset Orange", "Purple Velvet", "Midnight Blue", "Slime Green"]
        user_saved_keys = self.app_settings.get("custom_themes", {}).keys()
        if user_saved_keys:
            items.extend(list(user_saved_keys))
        self.block_signals_wrapper(self.theme_selector, items)

    def trigger_custom_color_picker_dialog(self):
        initial_color = self.current_accent_color
        chosen_color = QColorDialog.getColor(initial_color, self, "Select Custom Interface Accent Color")
        
        if chosen_color.isValid():
            from PyQt6.QtWidgets import QInputDialog
            preset_name, ok = QInputDialog.getText(self, "Save Theme Preset", "Enter a name for your custom preset:")
            if ok and preset_name.strip():
                clean_name = preset_name.strip()
                if clean_name in ["Auto", "Cyan Neon", "Emerald Matrix", "Amber Retro", "Hot Pink", "Sunset Orange", "Purple Velvet", "Midnight Blue", "Slime Green"]:
                    return
                
                self.app_settings["custom_themes"][clean_name] = chosen_color.name()
                self.app_settings["theme_mode"] = clean_name
                save_persistent_settings(self.app_settings)
                
                self.rebuild_theme_combobox_items()
                self.update_dynamic_accent_color_from_pixmap(self.current_pixmap)
                self.evaluate_preset_deletion_button_state()

    def delete_current_user_theme_preset(self):
        current_theme = self.theme_selector.currentText()
        if current_theme in self.app_settings.get("custom_themes", {}):
            del self.app_settings["custom_themes"][current_theme]
            self.app_settings["theme_mode"] = "Auto"
            save_persistent_settings(self.app_settings)
            
            self.rebuild_theme_combobox_items()
            self.update_dynamic_accent_color_from_pixmap(self.current_pixmap)
            self.evaluate_preset_deletion_button_state()

    def evaluate_preset_deletion_button_state(self):
        current_theme = self.theme_selector.currentText()
        is_user_preset = current_theme in self.app_settings.get("custom_themes", {})
        self.btn_delete_preset.setEnabled(is_user_preset)

    def update_dynamic_accent_color_from_pixmap(self, pixmap):
        mode = self.app_settings.get("theme_mode", "Auto")
        
        if mode in THEME_PRESETS:
            self.current_accent_color = QColor(THEME_PRESETS[mode])
        elif mode in self.app_settings.get("custom_themes", {}):
            self.current_accent_color = QColor(self.app_settings["custom_themes"][mode])
        else:
            if not pixmap or pixmap.isNull():
                self.current_accent_color = QColor("#45f3ff")
            else:
                img = pixmap.toImage().scaled(16, 16, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                r, g, b, count = 0, 0, 0, 0
                for x in [4, 8, 12]:
                    for y in [4, 8, 12]:
                        c = QColor(img.pixelColor(x, y))
                        if c.value() > 40 and c.hslSaturation() > 30:
                            r += c.red(); g += c.green(); b += c.blue(); count += 1
                if count > 0:
                    extracted = QColor(int(r/count), int(g/count), int(b/count))
                    if extracted.value() < 130:
                        extracted = extracted.lighter(150)
                    self.current_accent_color = extracted
                else:
                    self.current_accent_color = QColor("#45f3ff")
            
        self.scroll_content.update_accent_color(self.current_accent_color)
        if self.cover_flow_widget:
            self.cover_flow_widget.update()
        self.apply_theme_styles()

    def on_theme_selection_changed(self, selected_text):
        if not selected_text:
            return
        self.app_settings["theme_mode"] = selected_text
        save_persistent_settings(self.app_settings)
        self.update_dynamic_accent_color_from_pixmap(self.current_pixmap)
        self.evaluate_preset_deletion_button_state()

    def on_animation_type_changed(self, value):
        self.app_settings["animation_type"] = value
        save_persistent_settings(self.app_settings)
        self.scroll_content.init_animations()
        self.scroll_content.update()

    def cycle_animation_fx_mode(self):
        current_mode = self.app_settings.get("animation_type", "Warp Speed")
        try:
            next_mode = FX_MODES[(FX_MODES.index(current_mode) + 1) % len(FX_MODES)]
        except ValueError:
            next_mode = FX_MODES[0]
        self.anim_type_selector.setCurrentText(next_mode)
        self.show_track_info_transiently(f"FX Mode: {next_mode}")

    def audio_reactive_level(self):
        if self.media_player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            return 0.15
        volume = max(0.05, self.volume_slider.value() / 100.0)
        t = time.time()
        pulse = (
            0.48
            + 0.28 * math.sin(t * 8.2)
            + 0.17 * math.sin(t * 13.7 + 1.3)
            + 0.10 * random.random()
        )
        return max(0.0, min(1.0, pulse * volume))

    def refresh_mini_player(self):
        station_name = STATIONS[self.current_index]["name"] if 0 <= self.current_index < len(STATIONS) else "Radio"
        self.mini_station_label.setText(station_name)
        pixmap = self.current_pixmap if self.current_pixmap and not self.current_pixmap.isNull() else self.station_logo_pixmap
        if not pixmap or pixmap.isNull():
            pixmap = self.default_pixmap
        if pixmap and not pixmap.isNull():
            self.mini_art_label.setPixmap(pixmap.scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.mini_mute_btn.setText("M" if self.audio_output.isMuted() else "♪")
        self.mini_volume_slider.blockSignals(True)
        self.mini_volume_slider.setValue(self.volume_slider.value())
        self.mini_volume_slider.blockSignals(False)

    def toggle_mini_player_mode(self):
        self.is_mini_player = not self.is_mini_player
        if self.is_mini_player:
            self.pre_mini_geometry = self.geometry()
            self.refresh_mini_player()
            self.setMinimumSize(320, 96)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            self.content_stack_engine.setCurrentWidget(self.mini_player_widget)
            self.custom_title_bar.setVisible(False)
            mini_w = max(320, self.app_settings.get("mini_window_width", 420))
            mini_h = max(96, self.app_settings.get("mini_window_height", 96))
            self.resize(mini_w, mini_h)
            self.show()
        else:
            self.app_settings["mini_window_width"] = max(320, self.width())
            self.app_settings["mini_window_height"] = max(96, self.height())
            save_persistent_settings(self.app_settings)
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
            self.custom_title_bar.setVisible(True)
            self.setMinimumSize(APP_MIN_WIDTH, APP_MIN_HEIGHT)
            self.content_stack_engine.setCurrentWidget(self.player_workspace_widget)
            if self.pre_mini_geometry:
                self.setGeometry(self.pre_mini_geometry)
            self.show()
            self.apply_view_mode_layout()

    def on_star_anim_toggle_changed(self, state):
        self.app_settings["star_animation_enabled"] = self.star_anim_checkbox.isChecked()
        save_persistent_settings(self.app_settings)
        self.scroll_content.init_animations()
        self.scroll_content.update()

    def view_mode_button_text(self):
        if self.view_mode == "tile":
            return "◫"
        return "☰"

    def station_logo_pixmap_for(self, station):
        local_filename = sanitize_filename(station["name"])
        local_path = os.path.join(LOGOS_DIR, local_filename)
        logo_value = station.get("logo", "")
        candidate_paths = [local_path]

        if logo_value and not logo_value.startswith("http"):
            if os.path.isabs(logo_value):
                candidate_paths.append(logo_value)
            else:
                candidate_paths.append(os.path.join(LOGOS_DIR, logo_value))
                candidate_paths.append(os.path.join(SCRIPT_DIR, "logos", logo_value))
                candidate_paths.append(os.path.join(SCRIPT_DIR, logo_value))

        for path in candidate_paths:
            if path and os.path.exists(path):
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    return pixmap
        return QPixmap()

    def process_audio_fade_loop(self):
        if self.fading_out_for_swap:
            self.fade_step -= 0.08
            if self.fade_step <= 0.0:
                self.fade_step = 0.0
                self.fade_timer.stop()
                self.fading_out_for_swap = False
                self.execute_station_stream_swap(self.pending_station_index)
            else:
                self.audio_output.setVolume(self.fade_step * (self.target_volume / 100.0))
        else:
            self.fade_step += 0.08
            if self.fade_step >= 1.0:
                self.fade_step = 1.0
                self.fade_timer.stop()
            self.audio_output.setVolume(self.fade_step * (self.target_volume / 100.0))

    def trigger_crossfade_to_index(self, index):
        if self.recorder.is_recording:
            self.toggle_stream_recording()
        self.fade_timer.stop()
        self.pending_station_index = index
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.fading_out_for_swap = True
            self.fade_step = 1.0
            self.fade_timer.start()
        else:
            self.execute_station_stream_swap(index)

    def execute_station_stream_swap(self, index):
        self.current_index = index
        self.app_settings["last_station_index"] = index
        save_persistent_settings(self.app_settings)
        
        station = STATIONS[index]
        is_custom_folder = station.get("is_custom", False)
        
        self.btn_prev.setVisible(is_custom_folder)
        self.btn_next.setVisible(is_custom_folder)
        
        if is_custom_folder:
            self.custom_tracks = list(station.get("tracks", []))
            if self.custom_tracks:
                last_idx = self.custom_station_last_track.get(index)
                if len(self.custom_tracks) > 1:
                    candidate_indices = [i for i in range(len(self.custom_tracks)) if i != last_idx]
                    self.custom_track_index = random.choice(candidate_indices)
                else:
                    self.custom_track_index = 0
                self.custom_station_last_track[index] = self.custom_track_index
                track_path = self.custom_tracks[self.custom_track_index]
                self.metadata_worker.update_url(track_path)
                self.media_player.setSource(QUrl.fromLocalFile(track_path))
                filename_label = os.path.splitext(os.path.basename(track_path))[0]
                self.show_track_info_transiently(f"[{station['name']}] {filename_label}")
            else:
                self.custom_track_index = -1
                self.show_track_info_transiently("Empty Custom Folder Station")
        else:
            self.custom_tracks = []
            self.custom_track_index = -1
            self.metadata_worker.update_url(station["url"])
            self.media_player.setSource(QUrl(station["url"]))
            self.show_track_info_transiently(f"Connecting to {station['name']}...")
            
        self.update_active_station_highlight()
        self.cycle_timer.stop()
        self.show_loading_logo = True
        
        local_filename = sanitize_filename(station["name"])
        local_path = os.path.join(LOGOS_DIR, local_filename)
        bundled_path = os.path.join(SCRIPT_DIR, "logos", station.get("logo", ""))
        
        if os.path.exists(local_path):
            self.station_logo_pixmap = QPixmap(local_path)
            self.current_pixmap = self.station_logo_pixmap
            self.update_dynamic_accent_color_from_pixmap(self.current_pixmap)
            self.apply_scaled_artwork()
        elif os.path.isfile(bundled_path):
            self.station_logo_pixmap = QPixmap(bundled_path)
            self.current_pixmap = self.station_logo_pixmap
            self.update_dynamic_accent_color_from_pixmap(self.current_pixmap)
            self.apply_scaled_artwork()
        elif station.get("logo", "").startswith("http"):
            self.station_logo_pixmap = None
            self.current_pixmap = QPixmap()
            worker = AlbumArtWorker(save_path_target=local_path)
            worker.image_ready.connect(self.on_primary_logo_ready)
            worker.image_failed.connect(self.on_primary_logo_failed)
            worker.fetch(station["logo"])
        else:
            self.station_logo_pixmap = None
            self.current_pixmap = QPixmap()
            self.update_dynamic_accent_color_from_pixmap(None)
            self.apply_scaled_artwork()
            
        self.media_player.play()
        self.fading_out_for_swap = False
        self.fade_timer.start()
        self.refresh_mini_player()

    def play_next_custom_track(self):
        if not self.custom_tracks:
            return
        self.custom_track_index = (self.custom_track_index + 1) % len(self.custom_tracks)
        track_path = self.custom_tracks[self.custom_track_index]
        self.media_player.setSource(QUrl.fromLocalFile(track_path))
        filename_label = os.path.splitext(os.path.basename(track_path))[0]
        station_name = STATIONS[self.current_index]["name"]
        self.show_track_info_transiently(f"[{station_name}] {filename_label}")
        self.media_player.play()

    def play_previous_custom_track(self):
        if not self.custom_tracks:
            return
        self.custom_track_index = (self.custom_track_index - 1) % len(self.custom_tracks)
        track_path = self.custom_tracks[self.custom_track_index]
        self.media_player.setSource(QUrl.fromLocalFile(track_path))
        filename_label = os.path.splitext(os.path.basename(track_path))[0]
        station_name = STATIONS[self.current_index]["name"]
        self.show_track_info_transiently(f"[{station_name}] {filename_label}")
        self.media_player.play()

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if STATIONS[self.current_index].get("is_custom", False):
                self.play_next_custom_track()

    def rotate_image(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.rotation_angle = (self.rotation_angle + 1.8) % 360.0
            if self.artwork_mode == "vinyl":
                self.apply_scaled_artwork()

    def on_primary_logo_ready(self, pixmap):
        self.station_logo_pixmap = pixmap
        if self.show_loading_logo:
            self.current_pixmap = pixmap
            self.update_dynamic_accent_color_from_pixmap(pixmap)
            self.apply_scaled_artwork()
            self.refresh_mini_player()

    def on_primary_logo_failed(self):
        if self.show_loading_logo:
            self.apply_scaled_artwork()
            self.refresh_mini_player()

    def on_metadata_received(self, title, stream_url):
        if not title:
            return
        self.show_track_info_transiently(title)
        self.add_track_history(title)
        
        station = STATIONS[self.current_index]
        if station["name"] != "GB News Radio" and not station.get("is_custom", False):
            self.art_search_worker.search_track(title)

    def add_track_history(self, title):
        station_name = STATIONS[self.current_index]["name"] if 0 <= self.current_index < len(STATIONS) else "Radio"
        history = self.app_settings.setdefault("track_history", [])
        if history and history[0].get("title") == title and history[0].get("station") == station_name:
            return
        history.insert(0, {
            "time": time.strftime("%H:%M"),
            "station": station_name,
            "title": title,
        })
        del history[20:]
        save_persistent_settings(self.app_settings)
        self.refresh_history_list()

    def refresh_history_list(self):
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear()
        for item in self.app_settings.get("track_history", []):
            self.history_list.addItem(f"{item.get('time', '--:--')}  {item.get('station', 'Radio')}  -  {item.get('title', '')}")

    def refresh_recordings_list(self):
        if not hasattr(self, "recordings_list"):
            return
        self.recordings_list.clear()
        if not os.path.isdir(RECORDINGS_DIR):
            return
        for filename in sorted(os.listdir(RECORDINGS_DIR), reverse=True):
            if not filename.lower().endswith(".mp3"):
                continue
            path = os.path.join(RECORDINGS_DIR, filename)
            item = QListWidgetItem(filename)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.recordings_list.addItem(item)

    def selected_recording_path(self):
        item = self.recordings_list.currentItem() if hasattr(self, "recordings_list") else None
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def play_selected_recording(self):
        path = self.selected_recording_path()
        if not path or not os.path.exists(path):
            return
        self.metadata_worker.update_url(path)
        self.media_player.setSource(QUrl.fromLocalFile(path))
        self.show_track_info_transiently(os.path.splitext(os.path.basename(path))[0])
        self.media_player.play()

    def delete_selected_recording(self):
        path = self.selected_recording_path()
        if not path or not os.path.exists(path):
            return
        try:
            os.remove(path)
            self.refresh_recordings_list()
            self.show_track_info_transiently("Recording deleted.")
        except Exception as exc:
            self.show_track_info_transiently(f"Delete failed: {exc}")

    def open_recordings_folder(self):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(RECORDINGS_DIR))
        except Exception as exc:
            self.show_track_info_transiently(f"Open folder failed: {exc}")

    def on_image_ready(self, pixmap):
        self.pending_track_pixmap = pixmap
        self.handle_artwork_cycle()

    def on_image_load_failed(self):
        self.handle_artwork_cycle()

    def handle_artwork_cycle(self):
        if hasattr(self, 'pending_track_pixmap') and self.pending_track_pixmap:
            self.current_pixmap = self.pending_track_pixmap
            self.pending_track_pixmap = None
        else:
            self.current_pixmap = self.station_logo_pixmap if self.station_logo_pixmap else QPixmap()
            
        self.update_dynamic_accent_color_from_pixmap(self.current_pixmap)
        self.apply_scaled_artwork()

    def apply_scaled_artwork(self):
        w = max(4, int(self.art_display.width() * 0.90))
        h = max(4, int(self.art_display.height() * 0.90))
        if w < 6 or h < 6:
            return
            
        target_pixmap = self.current_pixmap if (self.current_pixmap and not self.current_pixmap.isNull()) else self.default_pixmap
        
        if target_pixmap and not target_pixmap.isNull():
            scaled = target_pixmap.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            canvas = QPixmap(self.art_display.size())
            canvas.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            
            dx = (self.art_display.width() - scaled.width()) / 2.0
            dy = (self.art_display.height() - scaled.height()) / 2.0
            
            if self.artwork_mode == "vinyl":
                clip_path = QPainterPath()
                clip_path.addEllipse(dx, dy, scaled.width(), scaled.height())
                painter.setClipPath(clip_path)
                
                transform = QTransform()
                transform.translate(self.art_display.width() / 2.0, self.art_display.height() / 2.0).rotate(self.rotation_angle).translate(-self.art_display.width() / 2.0, -self.art_display.height() / 2.0)
                painter.setTransform(transform)
                
            painter.drawPixmap(int(dx), int(dy), scaled)
            painter.end()
            self.art_display.setPixmap(canvas)

    def refresh_scroll_picker_list(self):
        for worker in self.list_workers:
            try: worker.disconnect()
            except: pass
        self.list_workers.clear()
        
        if self.cover_flow_widget:
            self.scroll_content.layout.removeWidget(self.cover_flow_widget)
            self.cover_flow_widget.deleteLater()
            self.cover_flow_widget = None

        for btn in self.station_buttons:
            self.scroll_content.layout.removeWidget(btn)
            btn.deleteLater()
        self.station_buttons.clear()
        
        self.scroll_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.scroll_content.setProperty("view_mode", self.view_mode)

        if self.view_mode == "coverflow":
            self.cover_flow_widget = CoverFlowStationWidget(self, self.scroll_content)
            self.scroll_content.layout.addWidget(self.cover_flow_widget, 0, 0)
            for station in STATIONS:
                if not station.get("enabled", True):
                    continue
                local_filename = sanitize_filename(station["name"])
                local_path = os.path.join(LOGOS_DIR, local_filename)
                bundled_path = os.path.join(SCRIPT_DIR, "logos", station.get("logo", ""))
                if not os.path.exists(local_path) and not os.path.isfile(bundled_path) and station.get("logo", "").startswith("http"):
                    worker = AlbumArtWorker(save_path_target=local_path)
                    worker.image_ready.connect(self.on_cover_flow_logo_ready)
                    worker.fetch(station["logo"])
                    self.list_workers.append(worker)
            self.scroll_content.refresh_layout_indices()
            return
        
        for i, station in enumerate(STATIONS):
            if not station.get("enabled", True):
                continue
                
            btn = StationListButton(self.scroll_content)
            btn.setProperty("viewMode", self.view_mode)
            
            if self.view_mode == "list":
                btn.setText(f"   {station['name']}")
                btn.setIconSize(QSize(18, 18))
            else:
                btn.setText("")
                btn.setIconSize(QSize(50, 50))
                
            local_filename = sanitize_filename(station["name"])
            local_path = os.path.join(LOGOS_DIR, local_filename)
            bundled_path = os.path.join(SCRIPT_DIR, "logos", station.get("logo", ""))
            
            if os.path.exists(local_path):
                pix = QPixmap(local_path)
                if not pix.isNull():
                    btn.setIcon(QIcon(pix))
                elif self.view_mode == "tile":
                    btn.setText(station["art"])
            elif os.path.isfile(bundled_path):
                pix = QPixmap(bundled_path)
                if not pix.isNull():
                    btn.setIcon(QIcon(pix))
                elif self.view_mode == "tile":
                    btn.setText(station["art"])
            elif station.get("logo", "").startswith("http"):
                if self.view_mode == "tile":
                    btn.setText(station["art"])
                worker = AlbumArtWorker(save_path_target=local_path)
                worker.image_ready.connect(lambda pix, b=btn: self.on_list_logo_ready(b, pix))
                worker.image_failed.connect(lambda b=btn, s=station: self.on_list_logo_failed(b, s))
                worker.fetch(station["logo"])
                self.list_workers.append(worker)
            else:
                if self.view_mode == "tile":
                    btn.setText(station["art"])
                    
            self.station_buttons.append(btn)
            
        self.scroll_content.refresh_layout_indices()

    def on_list_logo_ready(self, button, pixmap):
        button.setIcon(QIcon(pixmap))
        if self.view_mode == "tile":
            button.setText("")

    def on_list_logo_failed(self, button, station):
        if self.view_mode == "tile":
            button.setText(station["art"])

    def on_cover_flow_logo_ready(self, pixmap):
        if self.cover_flow_widget:
            self.cover_flow_widget.update()

    def rebuild_options_catalog_view(self):
        for i in reversed(range(self.options_list_layout.count())):
            w = self.options_list_layout.itemAt(i).widget()
            if w:
                self.options_list_layout.removeWidget(w)
                w.deleteLater()
        self.catalogue_buttons.clear()
        
        seen = set()
        combined = []
        for item in STATIONS + PREDEFINED_CATALOGUE:
            if item["name"] not in seen:
                seen.add(item["name"])
                combined.append(item)
                
        for station in combined:
            is_active = station.get("enabled", True)
            prefix = "☑" if is_active else "☐"
            
            row = QHBoxLayout()
            row.setContentsMargins(4, 0, 4, 0)
            row.setSpacing(4)
            
            btn_glyph = QPushButton(prefix)
            btn_glyph.setProperty("class", "catalogue_check_glyph_btn")
            btn_glyph.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_glyph.clicked.connect(lambda _, st=station: self.toggle_station_activation(st))
            row.addWidget(btn_glyph)
            
            lbl_text = ElidedCatalogueLabel(station["name"])
            lbl_text.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 600; padding: 4px 0px; background-color: transparent;")
            row.addWidget(lbl_text, 1)
            
            btn_d = QPushButton("✕")
            btn_d.setStyleSheet("background-color:#2e1216; color:#ff4d4d; min-width:22px; max-width:22px; font-size:9px; height:22px; border-radius:4px; font-weight:bold;")
            btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_d.clicked.connect(lambda _, st=station: self.purge_station_permanently(st))
            row.addWidget(btn_d)
            
            container_widget = QWidget()
            container_widget.setLayout(row)
            self.options_list_layout.addWidget(container_widget)

    def append_custom_station_to_catalogue(self):
        name = self.txt_add_name.text().strip()
        url = self.txt_add_url.text().strip()
        if not name or not url:
            return
            
        new_station = {"name": name, "url": url, "logo": "📻", "art": "📻", "enabled": True, "is_custom": False}
        STATIONS.append(new_station)
        
        save_persisted_station_order()
        self.txt_add_name.clear()
        self.txt_add_url.clear()
        
        self.refresh_scroll_picker_list()
        self.rebuild_options_catalog_view()

    def create_custom_folder_radio_station(self):
        name = self.txt_folder_station_name.text().strip()
        if not name:
            self.show_track_info_transiently("Please set a Radio Name first!")
            return
            
        folder_selected = QFileDialog.getExistingDirectory(self, "Select Local Custom MP3 Audio Directory")
        if not folder_selected:
            return
            
        mp3_files = []
        for file in os.listdir(folder_selected):
            if file.lower().endswith(".mp3"):
                mp3_files.append(os.path.join(folder_selected, file))
                
        if not mp3_files:
            self.show_track_info_transiently("No MP3 files found inside directory!")
            return
            
        random.shuffle(mp3_files)
        
        new_folder_station = {
            "name": name,
            "url": folder_selected,
            "logo": "📻",
            "art": "🎵",
            "enabled": True,
            "is_custom": True,
            "tracks": mp3_files
        }
        
        STATIONS.append(new_folder_station)
        save_persisted_station_order()
        self.txt_folder_station_name.clear()
        
        self.refresh_scroll_picker_list()
        self.rebuild_options_catalog_view()
        self.show_track_info_transiently(f"Custom MP3 Radio '{name}' Built!")

    def toggle_station_activation(self, station_blueprint):
        for s in STATIONS:
            if s["name"] == station_blueprint["name"]:
                s["enabled"] = not s.get("enabled", True)
                break
                
        save_persisted_station_order()
        self.refresh_scroll_picker_list()
        self.rebuild_options_catalog_view()

    def purge_station_permanently(self, station_blueprint):
        global PREDEFINED_CATALOGUE
        match_idx = -1
        for i, s in enumerate(STATIONS):
            if s["name"] == station_blueprint["name"]:
                match_idx = i
                break
        if match_idx != -1:
            if len(STATIONS) <= 1:
                return
            STATIONS.pop(match_idx)
            if self.current_index >= len(STATIONS):
                self.current_index = 0
                
        PREDEFINED_CATALOGUE = [s for s in PREDEFINED_CATALOGUE if s["name"] != station_blueprint["name"]]
        save_persisted_station_order()
        self.refresh_scroll_picker_list()
        self.rebuild_options_catalog_view()

    def export_user_configuration_backup(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Radio Backup", "", "JSON Files (*.json)")
        if file_path:
            try:
                backup_data = {"stations": STATIONS, "catalogue": PREDEFINED_CATALOGUE}
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(backup_data, f, ensure_ascii=False, indent=4)
                self.show_track_info_transiently("Backup configuration exported successfully!")
            except Exception as e:
                self.show_track_info_transiently(f"Export failed: {str(e)}")

    def import_user_configuration_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Radio Backup", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    backup_data = json.load(f)
                if isinstance(backup_data, dict) and "stations" in backup_data:
                    loaded_stations = backup_data.get("stations", STATIONS)
                    loaded_catalogue = backup_data.get("catalogue", PREDEFINED_CATALOGUE)

                    STATIONS.clear()
                    STATIONS.extend(loaded_stations)
                    PREDEFINED_CATALOGUE.clear()
                    PREDEFINED_CATALOGUE.extend(loaded_catalogue)

                    for s in STATIONS:
                        if "enabled" not in s:
                            s["enabled"] = True
                        if "is_custom" not in s:
                            s["is_custom"] = False

                    save_persisted_station_order()
                    self.current_index = 0
                    self.refresh_scroll_picker_list()
                    self.rebuild_options_catalog_view()
                    self.load_station(0)
                    self.show_track_info_transiently("Backup imported successfully!")
                else:
                    self.show_track_info_transiently("Invalid backup file format.")
            except Exception as e:
                self.show_track_info_transiently(f"Import failed: {str(e)}")

    def toggle_options_plane(self):
        is_options_view = self.content_stack_engine.currentWidget() == self.options_plane
        if not is_options_view:
            if self.sidebar_picker_container.isVisible():
                self.app_settings["window_width"] = self.width()
            elif hasattr(self, '_cached_expanded_width') and self._cached_expanded_width > 260:
                self.app_settings["window_width"] = self._cached_expanded_width
            self.app_settings["window_height"] = self.height()
            save_persistent_settings(self.app_settings)

            self.content_stack_engine.setCurrentWidget(self.options_plane)
            self.rebuild_options_catalog_view()
            self.refresh_history_list()
            self.refresh_recordings_list()

            opt_w = max(APP_MIN_WIDTH, self.app_settings.get("options_window_width", APP_MIN_WIDTH))
            opt_h = max(APP_MIN_HEIGHT, self.app_settings.get("options_window_height", APP_MIN_HEIGHT))
            self.resize(opt_w, opt_h)
        else:
            self.app_settings["options_window_width"] = self.width()
            self.app_settings["options_window_height"] = self.height()
            save_persistent_settings(self.app_settings)

            self.content_stack_engine.setCurrentWidget(self.player_workspace_widget)
            panel_mode = self.app_settings.get("panel_visibility_mode", self.panel_visibility_mode)
            sidebar_visible = panel_mode in ("both", "right")
            self.sidebar_picker_container.setVisible(sidebar_visible)

            player_h = max(APP_MIN_HEIGHT, self.app_settings.get("window_height", APP_MIN_HEIGHT))
            if sidebar_visible:
                player_w = max(APP_MIN_WIDTH, self.app_settings.get("window_width", APP_MIN_WIDTH))
                self.resize(player_w, player_h)
            else:
                self.resize(APP_MIN_WIDTH, player_h)
            self.scroll_content.rearrange_layout()
            self.apply_view_mode_layout()

    def toggle_sidebar_visibility(self):
        if self.content_stack_engine.currentWidget() == self.options_plane:
            self.content_stack_engine.setCurrentWidget(self.player_workspace_widget)

        if self.view_mode == "coverflow":
            self.apply_view_mode_layout()
            return

        try:
            next_idx = (PANEL_VISIBILITY_MODES.index(self.panel_visibility_mode) + 1) % len(PANEL_VISIBILITY_MODES)
        except ValueError:
            next_idx = 0
        self.panel_visibility_mode = PANEL_VISIBILITY_MODES[next_idx]
        self.app_settings["panel_visibility_mode"] = self.panel_visibility_mode
        self.app_settings["sidebar_visible"] = self.panel_visibility_mode in ("both", "right")
        save_persistent_settings(self.app_settings)
        self.apply_view_mode_layout()

    def toggle_view_mode(self):
        modes = ("tile", "coverflow")
        try:
            next_idx = (modes.index(self.view_mode) + 1) % len(modes)
        except ValueError:
            next_idx = 0
        self.view_mode = modes[next_idx]
        self.app_settings["view_mode"] = self.view_mode
        save_persistent_settings(self.app_settings)
        self.btn_view_mode.setText(self.view_mode_button_text())
        
        self.refresh_scroll_picker_list()
        self.apply_view_mode_layout()

    def toggle_artwork_presentation_mode(self):
        self.artwork_mode = "normal" if self.artwork_mode == "vinyl" else "vinyl"
        self.app_settings["artwork_mode"] = self.artwork_mode
        save_persistent_settings(self.app_settings)
        self.apply_scaled_artwork()

    def load_station(self, index):
        if 0 <= index < len(STATIONS):
            self.trigger_crossfade_to_index(index)

    def load_adjacent_station(self, direction):
        enabled_indices = [i for i, station in enumerate(STATIONS) if station.get("enabled", True)]
        if not enabled_indices:
            return
        if self.current_index in enabled_indices:
            pos = enabled_indices.index(self.current_index)
        else:
            pos = 0
        self.load_station(enabled_indices[(pos + direction) % len(enabled_indices)])

    def load_previous_station(self):
        self.load_adjacent_station(-1)

    def load_next_station(self):
        self.load_adjacent_station(1)

    def on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.spin_timer.start()
        else:
            self.spin_timer.stop()

    def on_player_error(self, error, error_string):
        print(f"DEBUG Media Player Drop/Error: {error_string}")
        if error != QMediaPlayer.Error.NoError:
            if STATIONS[self.current_index].get("is_custom", False):
                self.play_next_custom_track()
            else:
                self.show_track_info_transiently("Streaming connection dropped. Retrying...")
                QTimer.singleShot(2500, lambda: self.load_station(self.current_index))

    def toggle_audio_mute(self):
        m = not self.audio_output.isMuted()
        self.audio_output.setMuted(m)
        self.app_settings["muted"] = m
        save_persistent_settings(self.app_settings)
        self.btn_mute.setText("🔇" if m else ("🔉" if self.volume_slider.value() < 50 else "🔊"))

        self.refresh_mini_player()

    def on_volume_slider_moved(self, value):
        if hasattr(self, "volume_slider") and self.volume_slider.value() != value:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setValue(value)
            self.volume_slider.blockSignals(False)
        self.target_volume = value
        self.app_settings["volume"] = value
        save_persistent_settings(self.app_settings)
        if not self.fade_timer.isActive():
            self.audio_output.setVolume(value / 100.0)
        if self.audio_output.isMuted() and value > 0:
            self.audio_output.setMuted(False)
            self.app_settings["muted"] = False
        self.btn_mute.setText("🔇" if (value == 0 or self.audio_output.isMuted()) else ("🔉" if value < 50 else "🔊"))

        if hasattr(self, "mini_volume_slider"):
            self.mini_volume_slider.blockSignals(True)
            self.mini_volume_slider.setValue(value)
            self.mini_volume_slider.blockSignals(False)
        self.refresh_mini_player()

    def toggle_stream_recording(self):
        station = STATIONS[self.current_index]
        if station.get("is_custom", False):
            self.show_track_info_transiently("Recording local folder player is disabled.")
            return
        if self.recorder.is_recording:
            self.recorder.stop_recording()
            self.btn_rec.setText("⏺")
            self.btn_rec.setObjectName("")
            self.show_track_info_transiently("Recording Saved successfully!")
            self.refresh_recordings_list()
        else:
            if ".m3u8" in station["url"]:
                self.show_track_info_transiently("Recording not supported for HLS streams.")
                return
            self.recorder.start_recording(station["url"], station["name"])
            self.btn_rec.setText("🔴")
            self.btn_rec.setObjectName("record_active_btn")
            

    def update_active_station_highlight(self):
        if self.cover_flow_widget:
            self.cover_flow_widget.sync_to_current_station()
        rendered_stations = [s for s in STATIONS if s.get("enabled", True)]
        for i, btn in enumerate(self.station_buttons):
            if i < len(rendered_stations):
                master_idx = STATIONS.index(rendered_stations[i])
                btn.setProperty("active", "true" if master_idx == self.current_index else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def set_overlay_visible(self, visible):
        if self.overlay_is_visible == visible:
            return
        self.overlay_is_visible = visible
        self.controls_anim.stop()
        self.controls_anim.setStartValue(self.controls_effect.opacity())
        self.controls_anim.setEndValue(1.0 if visible else 0.0)
        self.controls_anim.start()

    def evaluate_resize_location(self, pos):
        w = self.width()
        h = self.height()
        b = self.border_width
        x = pos.x()
        y = pos.y()
        
        if x < b and y < b: return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if x > w - b and y < b: return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if x < b and y > h - b: return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if x > w - b and y > h - b: return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        if x < b: return Qt.Edge.LeftEdge
        if x > w - b: return Qt.Edge.RightEdge
        if y < b: return Qt.Edge.TopEdge
        if y > h - b: return Qt.Edge.BottomEdge
        return None

    def update_cursor_shape(self, edge):
        if edge in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        elif edge in (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
            self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
        elif edge in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
        elif edge in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.cycle_animation_fx_mode()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            resize_direction = self.evaluate_resize_location(pos)
            if resize_direction:
                self.windowHandle().startSystemResize(resize_direction)
            elif self.custom_title_bar.geometry().contains(pos):
                if pos.x() > 60:
                    self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    event.accept()

    def mouseMoveEvent(self, event):
        self.set_overlay_visible(True)
        pos = event.position().toPoint()
        if event.buttons() == Qt.MouseButton.NoButton:
            self.update_cursor_shape(self.evaluate_resize_location(pos))
        elif event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = QPoint()
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        event.accept()

    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("⬜")
        else:
            self.showMaximized()
            self.max_btn.setText("𗗗")
        self.scroll_content.rearrange_layout()
        self.resize_coverflow_stage()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_artwork_square_constraints()
        self.apply_scaled_artwork()
        if self.view_mode == "tile":
            self.scroll_content.rearrange_layout()
        self.resize_coverflow_stage()

    def closeEvent(self, event):
        self.metadata_worker.stop()
        if self.recorder.is_recording:
            self.recorder.stop_recording()

        if self.content_stack_engine.currentWidget() == self.options_plane:
            self.app_settings["options_window_width"] = self.width()
            self.app_settings["options_window_height"] = self.height()
        elif self.is_mini_player and self.pre_mini_geometry:
            self.app_settings["mini_window_width"] = max(320, self.width())
            self.app_settings["mini_window_height"] = max(96, self.height())
            self.app_settings["window_width"] = max(APP_MIN_WIDTH, self.pre_mini_geometry.width())
            self.app_settings["window_height"] = max(APP_MIN_HEIGHT, self.pre_mini_geometry.height())
        else:
            if self.sidebar_picker_container.isVisible():
                self.app_settings["window_width"] = self.width()
            elif hasattr(self, '_cached_expanded_width') and self._cached_expanded_width > 260:
                self.app_settings["window_width"] = self._cached_expanded_width
            else:
                self.app_settings["window_width"] = APP_MIN_WIDTH

            self.app_settings["window_height"] = max(APP_MIN_HEIGHT, self.height())

        self.app_settings["window_x"] = self.x()
        self.app_settings["window_y"] = self.y()
        if self.view_mode != "coverflow":
            self.app_settings["splitter_state"] = self.workspace_splitter.saveState().toHex().data().decode()
        save_persistent_settings(self.app_settings)
        save_persisted_station_order()
        event.accept()


