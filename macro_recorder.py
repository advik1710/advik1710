import sys
import time
import json
import random
import math
import threading

from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton, QVBoxLayout, 
                             QLabel, QTextEdit, QHBoxLayout, QFileDialog, 
                             QKeySequenceEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QSystemTrayIcon, QMenu)
from PyQt5.QtCore import pyqtSignal, QObject, Qt
from PyQt5.QtGui import QKeySequence, QIcon
from pynput import mouse, keyboard
import win32gui, win32ui, win32con, win32api

class SignalEmitter(QObject):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    events_updated_signal = pyqtSignal()

class UltimateMacroApp(QWidget):
    def __init__(self):
        super().__init__()
        self.events = []
        self.is_recording = False
        self.is_playing = False
        self.is_paused = False
        self.last_event_time = 0
        
        self.mouse_listener = None
        self.keyboard_listener = None
        self.hotkey_listener = None
        
        # Default Hotkeys
        self.rec_key_str = '<f8>'
        self.play_key_str = '<f9>'
        
        self.emitter = SignalEmitter()
        self.emitter.log_signal.connect(self.append_log)
        self.emitter.status_signal.connect(self.update_status)
        self.emitter.events_updated_signal.connect(self.refresh_table)
        
        self.init_ui()
        self.start_global_hotkeys()

    def init_ui(self):
        self.setWindowTitle('Ultimate Humanized Macro Automator')
        self.setGeometry(200, 150, 800, 700)

        main_layout = QVBoxLayout()

        self.status_label = QLabel('Status: Idle | Emergency Stop: ESC', self)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        main_layout.addWidget(self.status_label)

        # Hotkeys & Controls Row
        hk_layout = QHBoxLayout()
        hk_layout.addWidget(QLabel("Record Key:"))
        self.rec_key_input = QKeySequenceEdit(QKeySequence("F8"), self)
        self.rec_key_input.editingFinished.connect(self.update_hotkeys)
        hk_layout.addWidget(self.rec_key_input)

        hk_layout.addWidget(QLabel("Play/Pause Key:"))
        self.play_key_input = QKeySequenceEdit(QKeySequence("F9"), self)
        self.play_key_input.editingFinished.connect(self.update_hotkeys)
        hk_layout.addWidget(self.play_key_input)
        main_layout.addLayout(hk_layout)

        # Loop & Speed Configuration Row
        cfg_layout = QHBoxLayout()
        
        cfg_layout.addWidget(QLabel("Loops:"))
        self.loop_count_spin = QSpinBox(self)
        self.loop_count_spin.setRange(1, 9999)
        self.loop_count_spin.setValue(1)
        cfg_layout.addWidget(self.loop_count_spin)

        self.infinite_loop_cb = QCheckBox("Infinite", self)
        cfg_layout.addWidget(self.infinite_loop_cb)

        cfg_layout.addWidget(QLabel("Loop Pause (s):"))
        self.loop_pause_spin = QDoubleSpinBox(self)
        self.loop_pause_spin.setRange(0.0, 300.0)
        self.loop_pause_spin.setValue(2.0)
        cfg_layout.addWidget(self.loop_pause_spin)

        cfg_layout.addWidget(QLabel("Pause Variance (±s):"))
        self.loop_var_spin = QDoubleSpinBox(self)
        self.loop_var_spin.setRange(0.0, 60.0)
        self.loop_var_spin.setValue(0.5)
        cfg_layout.addWidget(self.loop_var_spin)

        cfg_layout.addWidget(QLabel("Speed:"))
        self.speed_spin = QDoubleSpinBox(self)
        self.speed_spin.setRange(0.1, 5.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        cfg_layout.addWidget(self.speed_spin)

        main_layout.addLayout(cfg_layout)

        # Stealth & Humanization Toggles Row
        stealth_layout = QHBoxLayout()
        
        stealth_layout.addWidget(QLabel("Click Variance (px):"))
        self.click_var_spin = QSpinBox(self)
        self.click_var_spin.setRange(0, 20)
        self.click_var_spin.setValue(3)
        stealth_layout.addWidget(self.click_var_spin)

        self.typo_cb = QCheckBox("Enable Typo Simulation", self)
        self.typo_cb.setChecked(True)
        stealth_layout.addWidget(self.typo_cb)

        self.fidget_cb = QCheckBox("Enable Hand Idle Fidgets", self)
        self.fidget_cb.setChecked(True)
        stealth_layout.addWidget(self.fidget_cb)

        main_layout.addLayout(stealth_layout)

        # Action Buttons Row
        btn_layout = QHBoxLayout()
        self.btn_record = QPushButton('Start Recording', self)
        self.btn_record.clicked.connect(self.toggle_recording)
        btn_layout.addWidget(self.btn_record)

        self.btn_play = QPushButton('Play Macro', self)
        self.btn_play.clicked.connect(self.toggle_playback)
        btn_layout.addWidget(self.btn_play)

        self.btn_save = QPushButton('Save Macro...', self)
        self.btn_save.clicked.connect(self.save_macro)
        btn_layout.addWidget(self.btn_save)

        self.btn_load = QPushButton('Load Macro...', self)
        self.btn_load.clicked.connect(self.load_macro)
        btn_layout.addWidget(self.btn_load)
        main_layout.addLayout(btn_layout)

        # Interactive Event Editor Table
        self.event_table = QTableWidget(0, 5, self)
        self.event_table.setHorizontalHeaderLabels(['Type', 'Key / Button', 'X Pos', 'Y Pos', 'Delay (s)'])
        self.event_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.event_table.itemChanged.connect(self.on_table_cell_changed)
        main_layout.addWidget(self.event_table)

        # Table Control Buttons
        table_btn_layout = QHBoxLayout()
        self.btn_delete_row = QPushButton('Delete Selected Step', self)
        self.btn_delete_row.clicked.connect(self.delete_selected_step)
        table_btn_layout.addWidget(self.btn_delete_row)

        self.btn_add_pixel_wait = QPushButton('+ Add Pixel Color Trigger Step', self)
        self.btn_add_pixel_wait.clicked.connect(self.add_pixel_wait_step)
        table_btn_layout.addWidget(self.btn_add_pixel_wait)
        main_layout.addLayout(table_btn_layout)

        # Execution Logs
        self.log_area = QTextEdit(self)
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(120)
        main_layout.addWidget(self.log_area)

        self.setLayout(main_layout)

        # System Tray Support
        self.init_tray_icon()

    def init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().SP_ComputerIcon))
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show Automator")
        show_action.triggered.connect(self.show)
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def append_log(self, text):
        self.log_area.append(text)

    def update_status(self, text):
        self.status_label.setText(text)

    # --- Hotkeys Management ---
    def update_hotkeys(self):
        rec_seq = self.rec_key_input.keySequence().toString().lower()
        play_seq = self.play_key_input.keySequence().toString().lower()

        if rec_seq:
            self.rec_key_str = f"<{rec_seq}>" if len(rec_seq) > 1 else rec_seq
        if play_seq:
            self.play_key_str = f"<{play_seq}>" if len(play_seq) > 1 else play_seq

        self.start_global_hotkeys()
        self.append_log(f"Hotkeys updated: Record={self.rec_key_str}, Play={self.play_key_str}")

    def start_global_hotkeys(self):
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        hotkey_map = {
            self.rec_key_str: self.toggle_recording,
            self.play_key_str: self.toggle_playback,
            '<esc>': self.emergency_stop
        }

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
        except Exception as e:
            self.append_log(f"Hotkey Binding Error: {e}")

    def emergency_stop(self):
        if self.is_playing or self.is_recording:
            self.is_playing = False
            self.is_paused = False
            self.is_recording = False
            if self.mouse_listener:
                self.mouse_listener.stop()
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            self.btn_record.setText('Start Recording')
            self.btn_play.setText('Play Macro')
            self.emitter.status_signal.emit("Status: EMERGENCY STOP TRIGGERED!")
            self.emitter.log_signal.emit("--- Emergency Stop (ESC) Triggered ---")

    # --- Win32 Pixel Utility ---
    def get_pixel_color(self, x, y):
        hdc = win32gui.GetDC(0)
        color = win32gui.GetPixel(hdc, x, y)
        win32gui.ReleaseDC(0, hdc)
        r = color & 0xff
        g = (color >> 8) & 0xff
        b = (color >> 16) & 0xff
        return (r, g, b)

    # --- Physics & Human Engine ---
    def human_move_mouse(self, mouse_ctrl, target_x, target_y):
        start_x, start_y = mouse_ctrl.position
        distance = math.hypot(target_x - start_x, target_y - start_y)
        
        if distance < 3:
            mouse_ctrl.position = (target_x, target_y)
            return

        will_overshoot = random.random() < 0.35 and distance > 40
        actual_target_x, actual_target_y = target_x, target_y
        
        if will_overshoot:
            angle = math.atan2(target_y - start_y, target_x - start_x)
            overshoot_dist = random.uniform(3.0, 12.0)
            actual_target_x = target_x + math.cos(angle) * overshoot_dist
            actual_target_y = target_y + math.sin(angle) * overshoot_dist

        # Cubic Bézier Curves
        angle = math.atan2(actual_target_y - start_y, actual_target_x - start_x)
        perp_angle = angle + (math.pi / 2) * random.choice([-1, 1])
        distortion = random.uniform(0.05, 0.20) * distance
        
        p1_x = start_x + (actual_target_x - start_x) * (1/3) + math.cos(perp_angle) * distortion
        p1_y = start_y + (actual_target_y - start_y) * (1/3) + math.sin(perp_angle) * distortion

        p2_x = start_x + (actual_target_x - start_x) * (2/3) + math.cos(perp_angle) * (distortion * 0.5)
        p2_y = start_y + (actual_target_y - start_y) * (2/3) + math.sin(perp_angle) * (distortion * 0.5)

        steps = max(15, int(distance / 5))

        for i in range(1, steps + 1):
            if not self.is_playing:
                return
            linear_t = i / float(steps)
            t = (1 - math.cos(linear_t * math.pi)) / 2.0

            one_minus_t = 1 - t
            curr_x = (
                (one_minus_t ** 3) * start_x +
                3 * (one_minus_t ** 2) * t * p1_x +
                3 * one_minus_t * (t ** 2) * p2_x +
                (t ** 3) * actual_target_x
            )
            curr_y = (
                (one_minus_t ** 3) * start_y +
                3 * (one_minus_t ** 2) * t * p1_y +
                3 * one_minus_t * (t ** 2) * p2_y +
                (t ** 3) * actual_target_y
            )

            jitter_scale = (1.0 - t) * 1.8
            jitter_x = random.uniform(-jitter_scale, jitter_scale)
            jitter_y = random.uniform(-jitter_scale, jitter_scale)

            mouse_ctrl.position = (int(curr_x + jitter_x), int(curr_y + jitter_y))

            speed_factor = self.speed_spin.value()
            base_delay = (0.001 + (1.0 - math.sin(linear_t * math.pi)) * 0.003) / speed_factor
            time.sleep(max(0.0001, base_delay + random.uniform(0.0001, 0.0003)))

        if will_overshoot:
            time.sleep(random.uniform(0.010, 0.035))
            flick_steps = random.randint(3, 6)
            current_pos_x, current_pos_y = mouse_ctrl.position
            for j in range(1, flick_steps + 1):
                ft = j / float(flick_steps)
                fx = current_pos_x + (target_x - current_pos_x) * ft
                fy = current_pos_y + (target_y - current_pos_y) * ft
                mouse_ctrl.position = (int(fx), int(fy))
                time.sleep(random.uniform(0.002, 0.005))

        mouse_ctrl.position = (target_x, target_y)

    def perform_idle_fidget(self, mouse_ctrl, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            if not self.is_playing:
                return
            # 15% chance to perform small hand drift during long pauses
            if random.random() < 0.15:
                cx, cy = mouse_ctrl.position
                dx = random.randint(-5, 5)
                dy = random.randint(-5, 5)
                mouse_ctrl.position = (cx + dx, cy + dy)
            time.sleep(0.5)

    # --- Recording Handlers ---
    def _get_delta(self):
        now = time.perf_counter()
        delta = now - self.last_event_time if self.last_event_time > 0 else 0
        self.last_event_time = now
        return delta

    def on_click(self, x, y, button, pressed):
        if not self.is_recording:
            return
        delta = self._get_delta()
        action = 'mouse_down' if pressed else 'mouse_up'
        self.events.append({'type': action, 'x': x, 'y': y, 'button': button.name, 'delay': round(delta, 3)})
        self.emitter.log_signal.emit(f"Mouse {action} at ({x}, {y})")
        self.emitter.events_updated_signal.emit()

    def on_key_action(self, key, is_press):
        if not self.is_recording:
            return
        delta = self._get_delta()
        action = 'key_press' if is_press else 'key_release'
        key_str = key.char if hasattr(key, 'char') and key.char else str(key)
        
        if key_str in (self.rec_key_str, self.play_key_str):
            return

        self.events.append({'type': action, 'key': key_str, 'delay': round(delta, 3)})
        self.emitter.log_signal.emit(f"{action}: {key_str}")
        self.emitter.events_updated_signal.emit()

    def toggle_recording(self):
        if self.is_playing:
            return

        if not self.is_recording:
            self.events.clear()
            self.log_area.clear()
            self.is_recording = True
            self.last_event_time = time.perf_counter()
            self.emitter.status_signal.emit(f'Status: Recording... (Hotkey: {self.rec_key_str})')
            self.btn_record.setText('Stop Recording')

            self.mouse_listener = mouse.Listener(on_click=self.on_click)
            self.keyboard_listener = keyboard.Listener(
                on_press=lambda k: self.on_key_action(k, True),
                on_release=lambda k: self.on_key_action(k, False)
            )
            self.mouse_listener.start()
            self.keyboard_listener.start()
        else:
            self.is_recording = False
            self.emitter.status_signal.emit('Status: Recording stopped')
            self.btn_record.setText('Start Recording')
            if self.mouse_listener:
                self.mouse_listener.stop()
            if self.keyboard_listener:
                self.keyboard_listener.stop()

    # --- Playback Logic ---
    def toggle_playback(self):
        if self.is_recording or not self.events:
            return

        if not self.is_playing:
            self.is_playing = True
            self.is_paused = False
            self.btn_play.setText('Pause Macro')
            events_snapshot = list(self.events)
            threading.Thread(target=self._run_playback, args=(events_snapshot,), daemon=True).start()
        elif self.is_playing and not self.is_paused:
            self.is_paused = True
            self.btn_play.setText('Resume Macro')
            self.emitter.status_signal.emit("Status: Playback Paused")
        elif self.is_playing and self.is_paused:
            self.is_paused = False
            self.btn_play.setText('Pause Macro')
            self.emitter.status_signal.emit("Status: Playing macro...")

    def _run_playback(self, events):
        self.emitter.status_signal.emit("Status: Playing macro...")
        self.emitter.log_signal.emit("--- Starting Advanced Playback ---")
        
        mouse_ctrl = mouse.Controller()
        key_ctrl = keyboard.Controller()

        total_loops = 99999999 if self.infinite_loop_cb.isChecked() else self.loop_count_spin.value()
        current_loop = 0

        while current_loop < total_loops and self.is_playing:
            current_loop += 1
            self.emitter.log_signal.emit(f"--- Executing Loop {current_loop}/{'∞' if self.infinite_loop_cb.isChecked() else total_loops} ---")

            for event in events:
                while self.is_paused:
                    time.sleep(0.1)
                    if not self.is_playing:
                        return

                if not self.is_playing:
                    break

                # Scaled Delay
                adjusted_delay = event.get('delay', 0) / self.speed_spin.value()
                
                if adjusted_delay > 1.0 and self.fidget_cb.isChecked():
                    self.perform_idle_fidget(mouse_ctrl, adjusted_delay)
                elif adjusted_delay > 0:
                    time.sleep(adjusted_delay)

                ev_type = event['type']

                # Pixel Wait Condition Trigger
                if ev_type == 'pixel_wait':
                    px, py = event['x'], event['y']
                    target_color = tuple(event['target_color'])
                    self.emitter.log_signal.emit(f"Waiting for pixel ({px}, {py}) to match RGB{target_color}...")
                    while self.is_playing:
                        curr_color = self.get_pixel_color(px, py)
                        if curr_color == target_color:
                            break
                        time.sleep(0.1)
                    continue

                if ev_type in ('mouse_down', 'mouse_up'):
                    btn = getattr(mouse.Button, event['button'])
                    
                    # Apply Dynamic Click Variance
                    var = self.click_var_spin.value()
                    vx = event['x'] + random.randint(-var, var) if var > 0 else event['x']
                    vy = event['y'] + random.randint(-var, var) if var > 0 else event['y']

                    self.human_move_mouse(mouse_ctrl, vx, vy)
                    time.sleep(random.uniform(0.015, 0.045) / self.speed_spin.value())
                    
                    if ev_type == 'mouse_down':
                        mouse_ctrl.press(btn)
                    else:
                        mouse_ctrl.release(btn)
                        
                elif ev_type in ('key_press', 'key_release'):
                    raw_key = event['key']
                    k = getattr(keyboard.Key, raw_key.split('.')[1]) if raw_key.startswith('Key.') else raw_key
                    
                    # Typo Simulation (1% chance during key press)
                    if ev_type == 'key_press' and self.typo_cb.isChecked() and isinstance(k, str) and len(k) == 1 and random.random() < 0.01:
                        typo_char = chr(ord(k) + random.choice([-1, 1]))
                        key_ctrl.press(typo_char)
                        time.sleep(random.uniform(0.05, 0.1))
                        key_ctrl.release(typo_char)
                        time.sleep(random.uniform(0.1, 0.25))
                        key_ctrl.press(keyboard.Key.backspace)
                        time.sleep(random.uniform(0.04, 0.08))
                        key_ctrl.release(keyboard.Key.backspace)
                        time.sleep(random.uniform(0.08, 0.15))

                    time.sleep(random.uniform(0.040, 0.110) / self.speed_spin.value())

                    if ev_type == 'key_press':
                        key_ctrl.press(k)
                    else:
                        key_ctrl.release(k)

            # Randomized Pause Between Loops
            if current_loop < total_loops and self.is_playing:
                base_pause = self.loop_pause_spin.value()
                var_pause = self.loop_var_spin.value()
                actual_pause = max(0.0, base_pause + random.uniform(-var_pause, var_pause))
                self.emitter.log_signal.emit(f"Loop finished. Pausing {actual_pause:.2f}s before next iteration...")
                time.sleep(actual_pause)

        self.emitter.log_signal.emit("--- Macro Playback Finished ---")
        self.emitter.status_signal.emit("Status: Idle")
        self.is_playing = False
        self.is_paused = False
        self.btn_play.setText('Play Macro')

    # --- Table Event Editor Logic ---
    def refresh_table(self):
        self.event_table.blockSignals(True)
        self.event_table.setRowCount(len(self.events))
        for idx, ev in enumerate(self.events):
            self.event_table.setItem(idx, 0, QTableWidgetItem(str(ev.get('type', ''))))
            self.event_table.setItem(idx, 1, QTableWidgetItem(str(ev.get('key', ev.get('button', '')))))
            self.event_table.setItem(idx, 2, QTableWidgetItem(str(ev.get('x', ''))))
            self.event_table.setItem(idx, 3, QTableWidgetItem(str(ev.get('y', ''))))
            self.event_table.setItem(idx, 4, QTableWidgetItem(str(ev.get('delay', 0.0))))
        self.event_table.blockSignals(False)

    def on_table_cell_changed(self, item):
        row = item.row()
        col = item.column()
        val = item.text()
        if row >= len(self.events):
            return

        ev = self.events[row]
        try:
            if col == 0:
                ev['type'] = val
            elif col == 1:
                if 'key' in ev:
                    ev['key'] = val
                else:
                    ev['button'] = val
            elif col == 2:
                ev['x'] = int(val)
            elif col == 3:
                ev['y'] = int(val)
            elif col == 4:
                ev['delay'] = float(val)
        except ValueError:
            pass

    def delete_selected_step(self):
        curr_row = self.event_table.currentRow()
        if curr_row >= 0 and curr_row < len(self.events):
            del self.events[curr_row]
            self.refresh_table()

    def add_pixel_wait_step(self):
        # Capture current mouse position color as template condition
        mouse_ctrl = mouse.Controller()
        cx, cy = mouse_ctrl.position
        color = self.get_pixel_color(cx, cy)
        
        wait_event = {
            'type': 'pixel_wait',
            'x': cx,
            'y': cy,
            'target_color': color,
            'delay': 0.1
        }
        self.events.append(wait_event)
        self.refresh_table()
        self.append_log(f"Added Pixel Condition: Target RGB{color} at ({cx}, {cy})")

    # --- File I/O Persistence ---
    def save_macro(self):
        if not self.events:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Macro", "", "JSON Files (*.json)")
        if path:
            with open(path, 'w') as f:
                json.dump(self.events, f, indent=2)
            self.append_log(f"Saved: {path}")

    def load_macro(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Macro", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r') as f:
                self.events = json.load(f)
            self.refresh_table()
            self.append_log(f"Loaded {len(self.events)} events.")

    def closeEvent(self, event):
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = UltimateMacroApp()
    ex.show()
    sys.exit(app.exec_())