import sys
import json
import pyautogui
from pynput import keyboard
from pynput import mouse
import time
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings, QPropertyAnimation, QRect, QEasingCurve, QDate, QPoint, QSize, QObject, QRectF, QDateTime, QPointF
from PyQt6.QtGui import QCursor, QKeySequence, QColor, QIcon, QPainter, QBrush, QPainterPath, QFont, QPen
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QHBoxLayout, 
                             QWidget, QMessageBox, QComboBox, QMenu, QSpinBox, QRadioButton, 
                             QLineEdit, QCheckBox, QMenuBar, QStyleFactory, QColorDialog, QGroupBox,
                             QScrollArea, QGridLayout, QFileDialog, QDoubleSpinBox, QSlider, QButtonGroup,
                             QFormLayout, QListWidget, QInputDialog, QTextEdit, QFrame)
import ctypes
import logging
import win32api
import win32con
import random
import math
import win32gui
import traceback
from functools import lru_cache  # Para mejorar rendimiento con caché
from concurrent.futures import ThreadPoolExecutor  # Para operaciones asíncronas

# Configuración de logging mejorada
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)

# Desactivar mensajes de debug para librerías de terceros (reduce ruido en el log)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('pynput').setLevel(logging.WARNING)

# Configurar pyautogui para no activar failsafe (mejorar rendimiento)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0  # Eliminar pausas entre comandos para mayor velocidad

# Constantes globales
VERSION = "0.0.7"
DEFAULT_CPS = 10
DEFAULT_REPLAY_COUNT = 1
DEFAULT_REPLAY_SPEED = 1.0
CONFIG_ORGANIZATION = "NikoHuman Solution"
CONFIG_APP_NAME = "AutoClickerz"

# Estilos centralizados para reutilización - MANTENIDOS IGUAL

# Pool para operaciones asíncronas
thread_pool = ThreadPoolExecutor(max_workers=2)

# Caché para operaciones frecuentes
@lru_cache(maxsize=32)
def get_window_info(hwnd):
    """Obtiene información de una ventana y la almacena en caché"""
    if not hwnd or not win32gui.IsWindow(hwnd):
        return None
    
    try:
        rect = win32gui.GetWindowRect(hwnd)
        title = win32gui.GetWindowText(hwnd)
        return {
            'hwnd': hwnd,
            'title': title,
            'x': rect[0],
            'y': rect[1],
            'width': rect[2] - rect[0],
            'height': rect[3] - rect[1],
            'rect': rect
        }
    except Exception:
        return None

class GlobalHotKeys(QObject):
    f6_pressed = pyqtSignal()
    f7_pressed = pyqtSignal()  # Nueva señal para F7 (grabación)
    f8_pressed = pyqtSignal()  # Nueva señal para F8 (reproducción)
    f11_pressed = pyqtSignal()
    key_pressed = pyqtSignal(str)  # Nueva señal para cualquier tecla (para grabación)

    def __init__(self):
        super().__init__()
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        logger.debug("GlobalHotKeys inicializado")

    def on_press(self, key):
        if key == keyboard.Key.f6:
            logger.debug("F6 presionado - Emitiendo señal")
            self.f6_pressed.emit()
        elif key == keyboard.Key.f7:  # Detectar F7 para grabación
            logger.debug("F7 presionado - Emitiendo señal")
            self.f7_pressed.emit()
        elif key == keyboard.Key.f8:  # Detectar F8 para reproducción
            logger.debug("F8 presionado - Emitiendo señal")
            self.f8_pressed.emit()
        elif key == keyboard.Key.f11:
            logger.debug("F11 presionado - Emitiendo señal")
            self.f11_pressed.emit()
        else:
            # Emitir cualquier otra tecla para grabación
            try:
                key_char = key.char if hasattr(key, 'char') else str(key)
                self.key_pressed.emit(key_char)
            except:
                pass

class ThemeSwitch(QWidget):
    """Widget personalizado para cambiar entre tema claro y oscuro"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 30)
        self._is_checked = False
        # Eliminar la animación para optimizar rendimiento
        self._hover = False
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Área del switch
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 15, 15)
        
        # Color de fondo según estado
        if self._is_checked:
            bg_color = QColor(52, 199, 89)  # Verde para encendido
        else:
            bg_color = QColor(200, 200, 200)  # Gris para apagado
            
        # Cambiar sutilmente el color si hay hover
        if self._hover:
            if self._is_checked:
                bg_color = bg_color.lighter(110)
            else:
                bg_color = bg_color.darker(110)
                
        painter.fillPath(path, bg_color)

        # Dibujar el círculo deslizante
        circle_rect = QRectF(2 if not self._is_checked else self.width() - 28, 2, 26, 26)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(circle_rect)

    def set_checked(self, checked):
        if self._is_checked != checked:
            self._is_checked = checked
            self.update()

    def is_checked(self):
        return self._is_checked

    def mousePressEvent(self, event):
        self.set_checked(not self._is_checked)
        super().mousePressEvent(event)
        
    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

class OverlayWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.parent_app = parent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)  # Márgenes para el texto

        self.label = QLabel(
            "Haz clic en cualquier lugar para seleccionar\n"
            "Presiona ESC para cancelar\n\n"
            "F6: Iniciar/Detener clicker\n"
            "F11: Cerrar aplicación",
            self
        )
        self.label.setStyleSheet("""
            color: #FFFFFF; 
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 14px; 
            background-color: rgba(0, 0, 0, 150); 
            padding: 15px;
            border-radius: 5px;
        """)
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self.label, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(255, 0, 0, 50))  # Fondo rojo semitransparente

    def mousePressEvent(self, event):
        # Obtener las coordenadas globales del mouse usando mapToGlobal
        global_pos = self.mapToGlobal(event.pos())
        self.parent_app.on_overlay_click(global_pos)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()



class AutoClickerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Clicker AutoUpdate v{VERSION}")
        self.setGeometry(100, 100, 700, 500)
        self.setMinimumSize(600, 400)
        
        self.init_variables()
        self.init_ui()
        self.load_config()
        
        self.click_timer = QTimer(self)
        self.click_timer.timeout.connect(self.perform_click)
        
        self.cursor_update_timer = QTimer(self)
        self.cursor_update_timer.timeout.connect(self.update_current_cursor_position)
        self.cursor_update_timer.start(500)

        self.setup_hotkeys()
        self.apply_theme()
        self.init_menu()
        self.load_window_position()
        self.set_tooltips()
        
        # Ejecutar diagnóstico después de inicializar todo
        QTimer.singleShot(1000, self.run_diagnostics)
        
        logger.debug(f"Aplicación iniciada (versión {VERSION})")
        
    def run_diagnostics(self):
        """Ejecuta diagnósticos básicos para detectar problemas en la aplicación"""
        try:
            logger.debug("Ejecutando diagnósticos de la aplicación...")
            problems_found = []
            
            # Comprobar estado del botón de selección de ventana
            if self.use_window_checkbox.isChecked() and not self.select_window_button.isEnabled():
                problems_found.append("El botón 'Seleccionar Ventana' está deshabilitado a pesar de que el checkbox está activado")
                # Intentar corregir automáticamente
                self.select_window_button.setEnabled(True)
                self.select_window_button.show()
                self.select_window_button.raise_()
                logger.warning("Corregido automáticamente: habilitado botón de selección de ventana")
            
            # Verificar si hay módulos opcionales instalados
            try:
                import psutil
                logger.debug("Módulo psutil encontrado, información detallada del sistema disponible")
            except ImportError:
                problems_found.append("Módulo psutil no encontrado. La información detallada del sistema no estará disponible")
                logger.warning("Módulo psutil no encontrado (módulo opcional)")
            
            # Imprimir resultado del diagnóstico
            if problems_found:
                logger.warning(f"Diagnóstico completado. Se encontraron {len(problems_found)} problemas:")
                for i, problem in enumerate(problems_found, 1):
                    logger.warning(f"{i}. {problem}")
            else:
                logger.debug("Diagnóstico completado. No se encontraron problemas.")
                
        except Exception as e:
            logger.error(f"Error durante el diagnóstico: {str(e)}")

    def init_variables(self):
        # Configuración general
        self.settings = QSettings(CONFIG_ORGANIZATION, CONFIG_APP_NAME)
        self.theme = self.settings.value("theme", "light")
        self.custom_color = self.settings.value("custom_color", "#FFFFFF")
        
        # Estado del autoclicker
        self.is_clicking = False
        self.click_count = 0
        self.total_clicks = int(self.settings.value("total_clicks", 0))
        self.session_clicks = 0
        self.today_clicks = int(self.settings.value("today_clicks", 0))
        
        # Fecha del último clic
        self.last_click_date = QDate.fromString(
            self.settings.value("last_click_date", QDate.currentDate().toString(Qt.DateFormat.ISODate)), 
            Qt.DateFormat.ISODate
        )
        
        # Resetear contador diario si es un nuevo día
        if self.last_click_date != QDate.currentDate():
            self.today_clicks = 0
        
        # Inicializar interval_spinboxes (se crearán en init_ui)
        self.interval_spinboxes = []
        
        # Variables para la grabación y reproducción de secuencias
        self.recording = False
        self.sequence = []
        self.sequence_start_time = 0
        self.replay_index = 0
        self.replay_running = False
        self.replay_count = 0
        self.replay_total = 0
        self.replay_speed = DEFAULT_REPLAY_SPEED
        self.mouse_listener = None
        
        # Lista de secuencias guardadas
        self.saved_sequences = []
        self.sequence_dates = {}
        self.current_sequence_name = ""
        
        # Validar las secuencias guardadas
        self.validate_saved_sequences()
        
        # Ventana objetivo para clics relativos
        self.target_window = None
        self.target_window_hwnd = None
        
        # Caché de posición del cursor para optimizar actualizaciones
        self._last_cursor_pos = None
        
    def validate_saved_sequences(self):
        """Verifica que todas las secuencias guardadas sean válidas."""
        saved_sequences = self.settings.value("saved_sequences", [])
        valid_sequences = []
        sequence_dates = self.settings.value("sequence_dates", {})
        
        for name in saved_sequences:
            sequence_data = self.settings.value(f"sequence_{name}", None)
            if sequence_data and isinstance(sequence_data, list) and len(sequence_data) > 0:
                # Secuencia válida
                valid_sequences.append(name)
            else:
                # Secuencia inválida, eliminarla
                self.settings.remove(f"sequence_{name}")
                if name in sequence_dates:
                    del sequence_dates[name]
                logger.debug(f"Secuencia inválida '{name}' eliminada")
        
        self.saved_sequences = valid_sequences
        self.sequence_dates = sequence_dates
        self.settings.setValue("saved_sequences", valid_sequences)
        self.settings.setValue("sequence_dates", sequence_dates)
        self.settings.sync()

    def init_ui(self):
        """Inicializa la interfaz de usuario con diseño compacto y eficiente"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal sin scroll para mejor redimensionamiento
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(6, 6, 6, 6)
        
        # Aplicar tema moderno
        self.apply_modern_theme()
        
        # ===== SECCIÓN 1: CONTROL PRINCIPAL Y VELOCIDAD (HORIZONTAL) =====
        top_section = self.create_top_section()
        main_layout.addWidget(top_section)
        
        # ===== SECCIÓN 2: POSICIÓN Y VENTANA =====
        position_section = self.create_position_section()
        main_layout.addWidget(position_section)
        
        # ===== SECCIÓN 3: SECUENCIAS (HORIZONTAL) =====
        sequence_section = self.create_sequence_section()
        main_layout.addWidget(sequence_section)
        
        # ===== SECCIÓN 4: BARRA INFERIOR =====
        bottom_section = self.create_bottom_section()
        main_layout.addWidget(bottom_section)
        
        # Inicializar el selector de secuencias después de que todos los controles estén creados
        self.update_sequence_selector()

    def apply_modern_theme(self):
        """Aplica el tema unificado y compacto"""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2D2D30;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 9px;
            }
            QGroupBox {
                background-color: #2D2D30;
                border: 1px solid #555555;
                border-radius: 3px;
                margin-top: 0.3em;
                font-weight: bold;
                color: #FFFFFF;
                padding-top: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #FFFFFF;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #007ACC;
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 2px;
                font-weight: bold;
                font-size: 9px;
                min-height: 16px;
            }
            QPushButton:hover {
                background-color: #1C97EA;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            QPushButton#danger {
                background-color: #D13438;
            }
            QPushButton#danger:hover {
                background-color: #E81123;
            }
            QPushButton#success {
                background-color: #107C10;
            }
            QPushButton#success:hover {
                background-color: #13A10E;
            }
            QPushButton#small {
                padding: 2px 4px;
                font-size: 8px;
                min-height: 12px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #555555;
                padding: 3px 4px;
                border-radius: 2px;
                min-height: 16px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border: 1px solid #007ACC;
            }
            QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                width: 12px;
                border: none;
                background-color: #555555;
                border-radius: 1px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #777777;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid #555555;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E1E;
                color: #FFFFFF;
                selection-background-color: #007ACC;
                border: 1px solid #555555;
            }
            QRadioButton, QCheckBox {
                color: #FFFFFF;
                spacing: 4px;
                font-size: 9px;
            }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 12px;
                height: 12px;
                border-radius: 6px;
                border: 1px solid #555555;
            }
            QRadioButton::indicator:checked, QCheckBox::indicator:checked {
                background-color: #007ACC;
                border: 1px solid #007ACC;
            }
            QSlider::groove:horizontal {
                height: 2px;
                background: #555555;
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background: #007ACC;
                width: 12px;
                height: 12px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #007ACC;
                border-radius: 1px;
            }
            QLabel {
                color: #FFFFFF;
                font-size: 9px;
            }
            QLabel#title {
                font-size: 10px;
                font-weight: bold;
                color: #FFFFFF;
            }
            QLabel#subtitle {
                font-size: 8px;
                color: #CCCCCC;
            }
            QLabel#status {
                background-color: #1E1E1E;
                border-radius: 2px;
                padding: 2px 4px;
                color: #FFFFFF;
            }
        """)

    def create_top_section(self):
        """Crea la sección superior con control principal y velocidad en horizontal"""
        group = QGroupBox("Control Principal y Velocidad")
        layout = QHBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 10, 6, 6)
        
        # Panel izquierdo: Control principal
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setSpacing(4)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Botón principal de inicio/parada
        self.start_stop_button = QPushButton("▶ Iniciar (F6)")
        self.start_stop_button.setMinimumHeight(20)
        self.start_stop_button.clicked.connect(self.safe_toggle_clicking)
        control_layout.addWidget(self.start_stop_button)
        
        # Botón de selección de posición
        self.choose_position_button = QPushButton("🎯 Posición")
        self.choose_position_button.setObjectName("danger")
        self.choose_position_button.setMinimumHeight(20)
        self.choose_position_button.clicked.connect(self.choose_cursor_position)
        control_layout.addWidget(self.choose_position_button)
        
        layout.addWidget(control_panel)
        
        # Separador vertical
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: #555555; }")
        layout.addWidget(separator)
        
        # Panel derecho: Configuración de velocidad
        speed_panel = QWidget()
        speed_layout = QVBoxLayout(speed_panel)
        speed_layout.setSpacing(4)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        
        # CPS
        cps_layout = QHBoxLayout()
        cps_label = QLabel("CPS:")
        cps_label.setObjectName("subtitle")
        self.cps_spinbox = QSpinBox()
        self.cps_spinbox.setRange(1, 1000)
        self.cps_spinbox.setValue(int(self.settings.value("cps", 10)))
        self.cps_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.cps_spinbox.valueChanged.connect(self.update_interval)
        self.cps_spinbox.setFixedWidth(45)
        cps_layout.addWidget(cps_label)
        cps_layout.addWidget(self.cps_spinbox)
        cps_layout.addStretch()
        speed_layout.addLayout(cps_layout)
        
        # Intervalo personalizado
        interval_label = QLabel("Intervalo:")
        interval_label.setObjectName("subtitle")
        speed_layout.addWidget(interval_label)
        
        interval_layout = QHBoxLayout()
        interval_labels = ["H:", "M:", "S:", "MS:"]
        self.interval_spinboxes = [self.create_spinbox(label) for label in interval_labels]
        
        for i, (label, spinbox) in enumerate(zip(interval_labels, self.interval_spinboxes)):
            label_widget = QLabel(label)
            label_widget.setObjectName("subtitle")
            spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spinbox.valueChanged.connect(self.update_interval)
            spinbox.setFixedWidth(35)
            
            interval_layout.addWidget(label_widget)
            interval_layout.addWidget(spinbox)
            if i < len(interval_labels) - 1:
                interval_layout.addSpacing(5)
        
        interval_layout.addStretch()
        speed_layout.addLayout(interval_layout)
        
        layout.addWidget(speed_panel)
        
        return group



    def create_position_section(self):
        """Crea la sección de posición y ventana objetivo de forma compacta"""
        group = QGroupBox("Posición y Ventana")
        layout = QHBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 10, 6, 6)
        
        # Panel izquierdo: Modo de cursor y coordenadas
        cursor_panel = QWidget()
        cursor_layout = QVBoxLayout(cursor_panel)
        cursor_layout.setSpacing(4)
        cursor_layout.setContentsMargins(0, 0, 0, 0)
        
        # Modo de cursor
        cursor_mode_label = QLabel("Modo:")
        cursor_mode_label.setObjectName("subtitle")
        cursor_layout.addWidget(cursor_mode_label)
        
        cursor_layout_h = QHBoxLayout()
        self.current_cursor_radio = QRadioButton("Actual")
        self.chosen_cursor_radio = QRadioButton("Seleccionada")
        self.current_cursor_radio.setChecked(True)
        
        cursor_layout_h.addWidget(self.current_cursor_radio)
        cursor_layout_h.addWidget(self.chosen_cursor_radio)
        cursor_layout_h.addStretch()
        cursor_layout.addLayout(cursor_layout_h)
        
        # Coordenadas
        coords_layout = QHBoxLayout()
        coords_label = QLabel("Coords:")
        coords_label.setObjectName("subtitle")
        self.cursor_x_input = QLineEdit()
        self.cursor_y_input = QLineEdit()
        self.cursor_x_input.setPlaceholderText("X")
        self.cursor_y_input.setPlaceholderText("Y")
        self.cursor_x_input.setFixedWidth(40)
        self.cursor_y_input.setFixedWidth(40)
        
        coords_layout.addWidget(coords_label)
        coords_layout.addWidget(self.cursor_x_input)
        coords_layout.addWidget(self.cursor_y_input)
        coords_layout.addStretch()
        cursor_layout.addLayout(coords_layout)
        
        # Información de coordenadas actuales
        self.coordinates_label = QLabel("Actual: X: 0, Y: 0")
        self.coordinates_label.setObjectName("status")
        cursor_layout.addWidget(self.coordinates_label)
        
        layout.addWidget(cursor_panel)
        
        # Separador vertical
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: #555555; }")
        layout.addWidget(separator)
        
        # Panel derecho: Ventana objetivo
        window_panel = QWidget()
        window_layout = QVBoxLayout(window_panel)
        window_layout.setSpacing(4)
        window_layout.setContentsMargins(0, 0, 0, 0)
        
        # Ventana objetivo
        window_label = QLabel("Ventana:")
        window_label.setObjectName("subtitle")
        window_layout.addWidget(window_label)
        
        window_layout_h = QHBoxLayout()
        self.use_window_checkbox = QCheckBox("Específica")
        self.use_window_checkbox.setToolTip("Realizar clics relativos a una ventana específica")
        self.use_window_checkbox.stateChanged.connect(self.toggle_window_targeting)
        
        self.select_window_button = QPushButton("Seleccionar")
        self.select_window_button.setObjectName("small")
        self.select_window_button.clicked.connect(self.open_window_selector)
        self.select_window_button.setEnabled(False)
        
        window_layout_h.addWidget(self.use_window_checkbox)
        window_layout_h.addWidget(self.select_window_button)
        window_layout_h.addStretch()
        window_layout.addLayout(window_layout_h)
        
        # Información de la ventana
        self.window_info_label = QLabel("Ninguna ventana seleccionada")
        self.window_info_label.setObjectName("status")
        self.window_info_label.setEnabled(False)
        window_layout.addWidget(self.window_info_label)
        
        window_layout.addStretch()
        layout.addWidget(window_panel)
        
        return group

    def create_sequence_section(self):
        """Crea la sección de secuencias de forma compacta"""
        group = QGroupBox("Secuencias")
        layout = QHBoxLayout(group)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 10, 6, 6)
        
        # Panel de grabación
        record_panel = self.create_record_panel()
        layout.addWidget(record_panel)
        
        # Separador vertical
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: #555555; }")
        layout.addWidget(separator)
        
        # Panel de reproducción
        replay_panel = self.create_replay_panel()
        layout.addWidget(replay_panel)
        
        return group

    def create_record_panel(self):
        """Crea el panel de grabación compacto"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        # Título
        title = QLabel("GRABACIÓN")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # Botón de grabación
        self.record_button = QPushButton("⏺️ Iniciar (F7)")
        self.record_button.setMinimumHeight(18)
        self.record_button.clicked.connect(self.safe_toggle_recording)
        layout.addWidget(self.record_button)
        
        # Opciones de grabación
        options_label = QLabel("Opciones:")
        options_label.setObjectName("subtitle")
        layout.addWidget(options_label)
        
        self.record_all_radio = QRadioButton("Todo")
        self.record_clicks_radio = QRadioButton("Solo clics")
        self.record_all_radio.setChecked(True)
        self.record_options_group = QButtonGroup(self)
        self.record_options_group.addButton(self.record_all_radio)
        self.record_options_group.addButton(self.record_clicks_radio)
        
        options_layout = QHBoxLayout()
        options_layout.addWidget(self.record_all_radio)
        options_layout.addWidget(self.record_clicks_radio)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        # Nombre de secuencia
        name_label = QLabel("Nombre:")
        name_label.setObjectName("subtitle")
        layout.addWidget(name_label)
        
        name_layout = QHBoxLayout()
        self.sequence_name_input = QLineEdit()
        self.sequence_name_input.setPlaceholderText("Nueva secuencia")
        self.rename_button = QPushButton("Renombrar")
        self.rename_button.setObjectName("small")
        self.rename_button.clicked.connect(self.rename_sequence)
        
        name_layout.addWidget(self.sequence_name_input)
        name_layout.addWidget(self.rename_button)
        layout.addLayout(name_layout)
        
        layout.addStretch()
        return panel

    def create_replay_panel(self):
        """Crea el panel de reproducción compacto"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        
        # Título
        title = QLabel("REPRODUCCIÓN")
        title.setObjectName("title")
        layout.addWidget(title)
        
        # Selector de secuencias
        selector_label = QLabel("Secuencia:")
        selector_label.setObjectName("subtitle")
        layout.addWidget(selector_label)
        
        selector_layout = QHBoxLayout()
        self.sequence_selector = QComboBox()
        self.sequence_selector.setMinimumWidth(100)
        self.sequence_selector.currentIndexChanged.connect(self.load_selected_sequence)
        
        self.delete_sequence_button = QPushButton("🗑️")
        self.delete_sequence_button.setObjectName("danger")
        self.delete_sequence_button.setFixedWidth(25)
        self.delete_sequence_button.clicked.connect(self.delete_sequence)
        
        selector_layout.addWidget(self.sequence_selector)
        selector_layout.addWidget(self.delete_sequence_button)
        layout.addLayout(selector_layout)
        
        # Repeticiones y velocidad en horizontal
        reps_speed_layout = QHBoxLayout()
        
        # Repeticiones
        reps_layout = QVBoxLayout()
        reps_label = QLabel("Repeticiones:")
        reps_label.setObjectName("subtitle")
        reps_layout.addWidget(reps_label)
        
        reps_input_layout = QHBoxLayout()
        self.replay_count_spinbox = QSpinBox()
        self.replay_count_spinbox.setRange(0, 999999)
        self.replay_count_spinbox.setValue(int(self.settings.value("replay_count", 1)))
        self.replay_count_spinbox.setSpecialValueText("∞")
        self.replay_count_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.replay_count_spinbox.setFixedWidth(40)
        
        infinite_label = QLabel("(0=∞)")
        infinite_label.setObjectName("subtitle")
        
        reps_input_layout.addWidget(self.replay_count_spinbox)
        reps_input_layout.addWidget(infinite_label)
        reps_input_layout.addStretch()
        reps_layout.addLayout(reps_input_layout)
        
        reps_speed_layout.addLayout(reps_layout)
        
        # Velocidad
        speed_layout = QVBoxLayout()
        speed_label = QLabel("Velocidad:")
        speed_label.setObjectName("subtitle")
        speed_layout.addWidget(speed_label)
        
        # Botones de velocidad rápida
        speed_buttons_layout = QHBoxLayout()
        speed_button_style = """
            QPushButton {
                background-color: #3C3C3C;
                color: #FFFFFF;
                border: none;
                padding: 1px 3px;
                border-radius: 1px;
                font-size: 8px;
                min-width: 25px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:checked {
                background-color: #007ACC;
                color: white;
            }
        """
        
        self.slow_button = QPushButton("0.25x")
        self.slow_button.setCheckable(True)
        self.slow_button.clicked.connect(lambda: self.set_quick_speed(0.25))
        self.slow_button.setStyleSheet(speed_button_style)
        
        self.normal_button = QPushButton("1.0x")
        self.normal_button.setCheckable(True)
        self.normal_button.setChecked(True)
        self.normal_button.clicked.connect(lambda: self.set_quick_speed(1.0))
        self.normal_button.setStyleSheet(speed_button_style)
        
        self.fast_button = QPushButton("3.0x")
        self.fast_button.setCheckable(True)
        self.fast_button.clicked.connect(lambda: self.set_quick_speed(3.0))
        self.fast_button.setStyleSheet(speed_button_style)
        
        self.super_fast_button = QPushButton("10x")
        self.super_fast_button.setCheckable(True)
        self.super_fast_button.clicked.connect(lambda: self.set_quick_speed(10.0))
        self.super_fast_button.setStyleSheet(speed_button_style)
        
        self.speed_button_group = QButtonGroup(self)
        self.speed_button_group.addButton(self.slow_button)
        self.speed_button_group.addButton(self.normal_button)
        self.speed_button_group.addButton(self.fast_button)
        self.speed_button_group.addButton(self.super_fast_button)
        self.speed_button_group.setExclusive(True)
        
        speed_buttons_layout.addWidget(self.slow_button)
        speed_buttons_layout.addWidget(self.normal_button)
        speed_buttons_layout.addWidget(self.fast_button)
        speed_buttons_layout.addWidget(self.super_fast_button)
        speed_buttons_layout.addStretch()
        speed_layout.addLayout(speed_buttons_layout)
        
        reps_speed_layout.addLayout(speed_layout)
        layout.addLayout(reps_speed_layout)
        
        # Slider y valor exacto en horizontal
        slider_exact_layout = QHBoxLayout()
        
        # Slider de velocidad
        slider_layout = QVBoxLayout()
        slider_layout.addWidget(QLabel("0.1x"))
        
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 100)
        self.speed_slider.setValue(int(float(self.settings.value("replay_speed", 1.0)) * 10))
        self.speed_slider.setMinimumWidth(60)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setTickInterval(10)
        self.speed_slider.valueChanged.connect(self.update_speed_from_slider)
        
        slider_layout.addWidget(self.speed_slider)
        slider_layout.addWidget(QLabel("10x"))
        slider_exact_layout.addLayout(slider_layout)
        
        # Valor exacto
        exact_layout = QVBoxLayout()
        exact_layout.addWidget(QLabel("Valor:"))
        
        self.speed_spinbox = QDoubleSpinBox()
        self.speed_spinbox.setRange(0.1, 10.0)
        self.speed_spinbox.setValue(float(self.settings.value("replay_speed", 1.0)))
        self.speed_spinbox.setSingleStep(0.1)
        self.speed_spinbox.setDecimals(2)
        self.speed_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.speed_spinbox.setFixedWidth(40)
        self.speed_spinbox.valueChanged.connect(self.update_slider_from_spinbox)
        
        self.speed_label = QLabel("(1.0x)")
        self.speed_spinbox.valueChanged.connect(self.update_speed_label)
        
        exact_layout.addWidget(self.speed_spinbox)
        exact_layout.addWidget(self.speed_label)
        slider_exact_layout.addLayout(exact_layout)
        
        layout.addLayout(slider_exact_layout)
        
        # Botón de reproducción
        self.replay_button = QPushButton("▶️ Reproducir (F8)")
        self.replay_button.setMinimumHeight(18)
        self.replay_button.clicked.connect(self.safe_toggle_replay)
        layout.addWidget(self.replay_button)
        
        # Estado
        self.sequence_status_label = QLabel("Estado: Listo")
        self.sequence_status_label.setObjectName("status")
        layout.addWidget(self.sequence_status_label)
        
        layout.addStretch()
        return panel

    def create_bottom_section(self):
        """Crea la barra inferior ultra compacta"""
        group = QGroupBox("Info")
        layout = QHBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # Contadores de clics en horizontal
        counters_layout = QHBoxLayout()
        counters_layout.setSpacing(10)
        
        self.total_clicks_label = QLabel("T:0")
        self.last_24h_clicks_label = QLabel("24h:0")
        self.today_clicks_label = QLabel("H:0")
        self.session_clicks_label = QLabel("S:0")
        
        for label in [self.total_clicks_label, self.last_24h_clicks_label, 
                     self.today_clicks_label, self.session_clicks_label]:
            label.setObjectName("subtitle")
            counters_layout.addWidget(label)
        
        layout.addLayout(counters_layout)
        
        # Separador vertical
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { background-color: #555555; }")
        layout.addWidget(separator)
        
        # Controles adicionales
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Checkbox de ayuda
        self.help_checkbox = QCheckBox("Ayuda")
        self.help_checkbox.setChecked(True)
        self.help_checkbox.stateChanged.connect(self.toggle_tooltips)

        # ThemeSwitch
        self.theme_switch = ThemeSwitch(self)
        self.theme_switch.set_checked(self.theme == "dark")
        self.theme_switch.mousePressEvent = lambda event: self.toggle_theme(event)
        
        # Versión
        self.version_label = QLabel("v0.0.6")
        self.version_label.setObjectName("subtitle")
        
        controls_layout.addWidget(self.help_checkbox)
        controls_layout.addWidget(self.theme_switch)
        controls_layout.addWidget(self.version_label)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        return group

    def create_spinbox(self, label):
        """Crea un spinbox con configuración específica"""
        spinbox = QSpinBox()
        spinbox.setRange(0, 999 if label == "MS:" else 59)
        spinbox.setFixedWidth(50)
        spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        return spinbox

    def update_version(self, version=None):
        """Actualiza la etiqueta de versión"""
        version_text = version if version else VERSION
        self.version_label.setText(f"v{version_text}")

    def load_config(self):
        """Carga la configuración guardada de manera más eficiente"""
        # Usar diccionario para agrupar valores predeterminados
        default_values = {
            "cps": 10,
            "chosen_x": "0",
            "chosen_y": "0",
            "cursor_mode": "current",
            "show_help": "true",
            "replay_count": 1,
            "replay_speed": 1.0,
            "use_window": "false"
        }
        
        # Cargar valores en una operación
        config_values = {}
        for key, default in default_values.items():
            config_values[key] = self.settings.value(key, default)
        
        # Aplicar valores a los controles
        self.cps_spinbox.setValue(int(config_values["cps"]))
        self.cursor_x_input.setText(config_values["chosen_x"])
        self.cursor_y_input.setText(config_values["chosen_y"])
        
        # Configurar modo de cursor
        if config_values["cursor_mode"] == "chosen":
            self.chosen_cursor_radio.setChecked(True)
        else:
            self.current_cursor_radio.setChecked(True)
        
        # Cargar intervalos usando un bucle
        interval_keys = ["hours", "minutes", "seconds", "milliseconds"]
        for i, key in enumerate(interval_keys):
            self.interval_spinboxes[i].setValue(int(self.settings.value(f"interval_{key}", 0)))
        
        # Configurar ayuda
        show_help = config_values["show_help"] == "true"
        self.help_checkbox.setChecked(show_help)
        self.toggle_tooltips(Qt.CheckState.Checked if show_help else Qt.CheckState.Unchecked)
        
        # Cargar configuración de secuencias
        self.replay_count_spinbox.setValue(int(config_values["replay_count"]))
        self.speed_spinbox.setValue(float(config_values["replay_speed"]))
        self.replay_speed = float(config_values["replay_speed"])
        
        # Cargar secuencias guardadas en un solo paso
        self.saved_sequences = self.settings.value("saved_sequences", [])
        self.sequence_dates = self.settings.value("sequence_dates", {})
        self.update_sequence_selector()
        
        # Configurar ventana objetivo
        use_window = config_values["use_window"] == "true"
        self.use_window_checkbox.setChecked(use_window)
        self.select_window_button.setEnabled(use_window)
        
    def save_config(self):
        """Guarda la configuración de manera más eficiente"""
        # Agrupar valores relacionados en un diccionario
        config = {
            "theme": self.theme,
            "custom_color": self.custom_color,
            "window_position": self.pos(),
            "chosen_x": self.cursor_x_input.text(),
            "chosen_y": self.cursor_y_input.text(),
            "cursor_mode": "chosen" if self.chosen_cursor_radio.isChecked() else "current",
            "cps": self.cps_spinbox.value(),
            "total_clicks": self.total_clicks,
            "today_clicks": self.today_clicks,
            "last_click_date": self.last_click_date.toString(Qt.DateFormat.ISODate),
            "show_help": self.help_checkbox.isChecked(),
            "replay_count": self.replay_count_spinbox.value(),
            "replay_speed": self.speed_spinbox.value(),
            "saved_sequences": self.saved_sequences,
            "sequence_dates": self.sequence_dates,
            "use_window": self.use_window_checkbox.isChecked()
        }
        
        # Guardar todo el diccionario de una vez
        for key, value in config.items():
            self.settings.setValue(key, value)
        
        # Guardar intervalos
        interval_keys = ["hours", "minutes", "seconds", "milliseconds"]
        for i, key in enumerate(interval_keys):
            self.settings.setValue(f"interval_{key}", self.interval_spinboxes[i].value())
        
        # Guardar cada secuencia (esto no se puede optimizar mucho más)
        saved_sequences_data = {}
        for name in self.saved_sequences:
            saved_sequences_data[name] = self.settings.value(f"sequence_{name}", [])
        self.settings.setValue("saved_sequences_data", saved_sequences_data)
        
        # Sincronizar al final para mejorar rendimiento
        self.settings.sync()

    def set_tooltips(self):
        self.start_stop_button.setToolTip("Inicia o detiene el autoclicker. También puedes usar F6 como atajo de teclado.")
        self.cps_spinbox.setToolTip("Ajusta los clics por segundo.")
        for i, spinbox in enumerate(self.interval_spinboxes):
            spinbox.setToolTip(f"Ajusta los {'horas' if i == 0 else 'minutos' if i == 1 else 'segundos' if i == 2 else 'milisegundos'} entre clics.")
        self.current_cursor_radio.setToolTip("El clic se realizará en la posición actual del cursor en cada intervalo.")
        self.chosen_cursor_radio.setToolTip("El clic se realizará siempre en la posición fija que hayas elegido.")
        self.cursor_x_input.setToolTip("Coordenada X de la posición elegida.")
        self.cursor_y_input.setToolTip("Coordenada Y de la posición elegida.")
        self.choose_position_button.setToolTip("Haz clic aquí y luego en cualquier parte de la pantalla para elegir la posición fija.")
        self.help_checkbox.setToolTip("Activa o desactiva estos mensajes de ayuda.")
        self.theme_switch.setToolTip("Cambia entre el tema claro y oscuro de la interfaz.")
        self.total_clicks_label.setToolTip("Número total de clics realizados desde que se instaló la aplicación.")
        self.session_clicks_label.setToolTip("Número de clics realizados en esta sesión de uso.")
        self.today_clicks_label.setToolTip("Número de clics realizados hoy.")
        self.coordinates_label.setToolTip("Muestra la posición actual del cursor en la pantalla.")
        
        # Tooltips para los nuevos controles
        self.record_button.setToolTip("Inicia o detiene la grabación de una secuencia de movimientos y clics. Tecla de atajo: F7")
        self.sequence_name_input.setToolTip("Nombre de la secuencia actual. Se guarda automáticamente al detener la grabación.")
        self.rename_button.setToolTip("Cambia el nombre de la secuencia actual.")
        self.sequence_selector.setToolTip("Selecciona una secuencia guardada para cargarla.")
        self.delete_sequence_button.setToolTip("Elimina la secuencia seleccionada permanentemente.")
        self.replay_count_spinbox.setToolTip("Número de veces que se reproducirá la secuencia.")

        
        # Tooltips para controles de velocidad
        self.speed_spinbox.setToolTip("Factor de velocidad para la reproducción: 0.1 (muy lento) a 10.0 (muy rápido). 1.0 = velocidad original.")
        self.speed_slider.setToolTip("Ajusta la velocidad de reproducción con este deslizador. De izquierda a derecha: más lento a más rápido.")
        self.speed_label.setToolTip("Indica cómo de rápida será la reproducción comparada con la grabación original.")
        self.slow_button.setToolTip("Establece la velocidad al 25% de la original (más lento).")
        self.normal_button.setToolTip("Establece la velocidad a la original (100%).")
        self.fast_button.setToolTip("Establece la velocidad al triple de la original (300%).")
        self.super_fast_button.setToolTip("Establece la velocidad a diez veces la original (1000%).")
        
        # Tooltips para opciones de grabación
        self.record_all_radio.setToolTip("Graba todo: teclado, movimientos del ratón y clics.")
        self.record_clicks_radio.setToolTip("Graba solo los clics, ignorando el teclado y los movimientos del ratón.")
        
        self.replay_button.setToolTip("Inicia o detiene la reproducción de la secuencia cargada. Tecla de atajo: F8")
        self.sequence_status_label.setToolTip("Muestra el estado actual de la grabación o reproducción de secuencias.")
        
        # Tooltips para características de ventana objetivo
        self.use_window_checkbox.setToolTip("Activa esta opción para hacer clics relativos a una ventana específica. Útil para juegos que cambian de posición.")
        self.select_window_button.setToolTip("Selecciona la ventana objetivo desde una lista de ventanas abiertas.")
        self.window_info_label.setToolTip("Muestra información sobre la ventana objetivo seleccionada.")

    def toggle_tooltips(self, state):
        duration = -1 if state == Qt.CheckState.Checked else 0
        for widget in self.findChildren(QWidget):
            if hasattr(widget, 'setToolTipDuration'):
                widget.setToolTipDuration(duration)
        # Asegúrate de que el checkbox mantenga su estado
        self.help_checkbox.setChecked(state == Qt.CheckState.Checked)

    def init_menu(self):
        menu_bar = self.menuBar()
        
        file_menu = QMenu("Archivo", self)
        
        # Añadir opciones para secuencias
        save_sequence_item = file_menu.addAction("Guardar Secuencia")
        save_sequence_item.triggered.connect(self.save_sequence)
        
        load_sequence_item = file_menu.addAction("Cargar Secuencia")
        load_sequence_item.triggered.connect(self.load_sequence)
        
        file_menu.addSeparator()
        
        close_item = file_menu.addAction("Cerrar")
        close_item.triggered.connect(self.close)
        menu_bar.addMenu(file_menu)
        
        # Menú de secuencia
        sequence_menu = QMenu("Secuencia", self)
        
        record_item = sequence_menu.addAction("Iniciar Grabación")
        record_item.triggered.connect(self.safe_toggle_recording)
        
        replay_item = sequence_menu.addAction("Reproducir Secuencia")
        replay_item.triggered.connect(self.safe_toggle_replay)
        
        menu_bar.addMenu(sequence_menu)

        # Menú de herramientas con consola de depuración
        tools_menu = QMenu("Herramientas", self)
        
        console_item = tools_menu.addAction("Consola de Depuración")
        console_item.triggered.connect(self.open_debug_console)
        
        menu_bar.addMenu(tools_menu)

        help_menu = QMenu("Ayuda", self)
        about_item = help_menu.addAction("Acerca de")
        about_item.triggered.connect(self.show_about)
        menu_bar.addMenu(help_menu)

    def show_about(self):
        about_text = ("¡Bienvenido a Clicker AutoUpdate!\n\n"
                      "Esta es una herramienta avanzada de automatización diseñada para simplificar tareas repetitivas "
                      "y mejorar la eficiencia en diversas aplicaciones y juegos.\n\n"
                      "Características principales:\n"
                      "- Clics automáticos en posición fija o siguiendo el cursor\n"
                      "- Grabación completa: teclado, movimientos y clics\n" 
                      "- Opción de grabar solo clics para secuencias simplificadas\n"
                      "- Selección rápida de velocidades: lento, normal, rápido, ultra\n"
                      "- Reproducción a velocidad variable (0.1x a 10.0x)\n"
                      "- Repetición infinita o un número específico de veces\n\n"
                      "Atajos de teclado:\n"
                      "F6: Iniciar/Detener clicker\n"
                      "F7: Iniciar/Detener grabación de secuencia\n"
                      "F8: Iniciar/Detener reproducción de secuencia\n"
                      "F11: Cerrar aplicación\n\n"
                      "Optimiza tu experiencia en juegos como Cookie Clicker, Adventure Capitalist y Clicker Heroes, "
                      "realizando clics automáticos de manera eficiente.\n\n"
                      "Esta aplicación está en constante desarrollo para ofrecerte nuevas funcionalidades y mejoras.\n\n"
                      "Desarrollada por xThreeh.\n"
                      "Versión: 0.0.6")
        QMessageBox.about(self, "Acerca de Clicker AutoUpdate", about_text)  # Cambiado el título de la ventana
    
    def open_debug_console(self):
        """Abre la consola de depuración para simular errores y analizar la aplicación"""
        try:
            if not hasattr(self, 'debug_console') or not self.debug_console.isVisible():
                self.debug_console = DebugConsole(self)
                self.debug_console.show()
            else:
                self.debug_console.raise_()
                self.debug_console.activateWindow()
                
            logger.debug("Consola de depuración abierta")
        except Exception as e:
            logger.error(f"Error al abrir la consola de depuración: {str(e)}")
            QMessageBox.critical(self, "Error", f"No se pudo abrir la consola de depuración: {str(e)}")

    def load_window_position(self):
        pos = self.settings.value("window_position")
        if pos:
            self.move(pos)

    def closeEvent(self, event):
        self.save_config()
        
        # Detener todas las actividades
        if self.is_clicking:
            self.stop_clicking()
        
        if self.recording:
            self.stop_recording()
            
        if self.replay_running:
            self.stop_replay()
            
        if hasattr(self, 'global_hotkeys'):
            self.global_hotkeys.listener.stop()
            
        super().closeEvent(event)

    def safe_toggle_clicking(self):
        logger.debug("safe_toggle_clicking llamado")
        QTimer.singleShot(0, self.toggle_clicking)

    def safe_toggle_recording(self):
        logger.debug("safe_toggle_recording llamado")
        QTimer.singleShot(0, self.toggle_recording)

    def safe_toggle_replay(self):
        logger.debug("safe_toggle_replay llamado")
        QTimer.singleShot(0, self.toggle_replay)

    def toggle_clicking(self):
        self.is_clicking = not self.is_clicking
        if self.is_clicking:
            self.start_clicking()
            self.start_stop_button.setText("Detener (F6)")
        else:
            self.stop_clicking()
            self.start_stop_button.setText("Iniciar (F6)")
        self.update_ui_state()
        logger.debug(f"Clicking {'iniciado' if self.is_clicking else 'detenido'}")

    def start_clicking(self):
        interval = self.get_interval()
        self.click_timer.start(interval)
        logger.debug(f"Clicking iniciado con intervalo de {interval}ms")

    def stop_clicking(self):
        self.click_timer.stop()
        logger.debug("Clicking detenido")
        
    def perform_click(self):
        """Realiza un clic en la posición configurada"""
        try:
            # Determinar las coordenadas de clic según el modo seleccionado
            if self.chosen_cursor_radio.isChecked():
                try:
                    x = int(self.cursor_x_input.text())
                    y = int(self.cursor_y_input.text())
                    # Mover el cursor a la posición especificada
                    win32api.SetCursorPos((x, y))
                except ValueError:
                    logger.error("Coordenadas de clic inválidas")
                    return
            else:  # Usar posición actual del cursor
                x, y = pyautogui.position()
            
            # Realizar el clic - Optimizado para usar directamente win32api
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN | win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            
            # Incrementar contadores de clics en una sola operación
            self.click_count += 1
            self.total_clicks += 1
            self.session_clicks += 1
            self.today_clicks += 1
            
            # Actualizar la UI solo cada 5 clics para mejorar rendimiento
            if self.click_count % 5 == 0:
                self.update_click_count()
            
            # Logging solo para depuración detallada
            if self.click_count % 100 == 0:
                logger.debug(f"Clic #{self.click_count} ejecutado en posición ({x}, {y})")
                
        except Exception as e:
            logger.error(f"Error al realizar clic: {str(e)}")

    def update_click_count(self):
        self.update_click_labels()
        self.save_config()

    def update_click_labels(self):
        self.total_clicks_label.setText(f"Total: {self.total_clicks}")
        self.session_clicks_label.setText(f"Sesión: {self.session_clicks}")
        self.today_clicks_label.setText(f"Hoy: {self.today_clicks}")

    def get_interval(self):
        cps = self.cps_spinbox.value()
        if cps > 0:
            return max(1, int(1000 / cps))
        else:
            hours, minutes, seconds, milliseconds = [spinbox.value() for spinbox in self.interval_spinboxes]
            return max(1, (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds)

    def update_interval(self):
        interval = self.get_interval()
        if self.is_clicking:
            self.click_timer.setInterval(interval)
        logger.debug(f"Intervalo actualizado a {interval} ms")

    def update_current_cursor_position(self):
        """Actualiza la posición actual del cursor de manera optimizada"""
        # Obtener posición actual del cursor utilizando win32api en lugar de pyautogui
        try:
            x, y = win32api.GetCursorPos()
            
            # Verificar si la posición ha cambiado antes de actualizar UI
            if not hasattr(self, '_last_cursor_pos') or self._last_cursor_pos != (x, y):
                self._last_cursor_pos = (x, y)
                self.coordinates_label.setText(f"X: {x}, Y: {y}")
                
                # Solo actualizar los campos de entrada si el modo de cursor actual está seleccionado
                if self.current_cursor_radio.isChecked():
                    self.cursor_x_input.setText(str(x))
                    self.cursor_y_input.setText(str(y))
        except Exception as e:
            # Silenciosamente ignorar errores temporales
            pass

    def choose_cursor_position(self):
        print("Iniciando selección de posición")
        self.is_selecting = True
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.close()
        self.overlay = OverlayWidget(self)
        self.overlay.showFullScreen()
        print("Overlay creado y mostrado en pantalla completa")

    def on_overlay_click(self, pos):
        self.cursor_x_input.setText(str(pos.x()))
        self.cursor_y_input.setText(str(pos.y()))
        self.chosen_cursor_radio.setChecked(True)
        self.update_cursor_mode()
        self.overlay.close()
        self.is_selecting = False
        print(f"Posición seleccionada: X={pos.x()}, Y={pos.y()}")

    def update_cursor_mode(self):
        is_chosen_mode = self.chosen_cursor_radio.isChecked()
        self.cursor_x_input.setEnabled(is_chosen_mode)
        self.cursor_y_input.setEnabled(is_chosen_mode)
        self.choose_position_button.setEnabled(is_chosen_mode)

    def toggle_theme(self, event):
        self.theme = "dark" if self.theme == "light" else "light"
        self.theme_switch.set_checked(self.theme == "dark")
        self.apply_theme()
        
        # Actualizar estilo del botón infinito

            
        self.update_ui_state()
        self.save_config()

    def apply_theme(self):
        """Aplica el tema actual (dark/light)"""
        if self.theme == "dark":
            # Usar el tema moderno que ya está aplicado en apply_modern_theme
            self.apply_modern_theme()
        else:
            # Tema claro (más simple)
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #F5F5F5;
                    color: #333333;
                }
                QWidget {
                    background-color: #F5F5F5;
                    color: #333333;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 11px;
                }
                QGroupBox {
                    background-color: #FFFFFF;
                    border: 1px solid #CCCCCC;
                    border-radius: 8px;
                    margin-top: 1em;
                    font-weight: bold;
                    color: #333333;
                    padding-top: 10px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 15px;
                    padding: 0 8px;
                    color: #666666;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton {
                    background-color: #007ACC;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                    min-height: 20px;
                }
                QPushButton:hover {
                    background-color: #005A9E;
                }
                QPushButton:pressed {
                    background-color: #004578;
                }
                QPushButton:disabled {
                    background-color: #CCCCCC;
                    color: #888888;
                }
                QPushButton#danger {
                    background-color: #DC3545;
                }
                QPushButton#danger:hover {
                    background-color: #C82333;
                }
                QPushButton#success {
                    background-color: #28A745;
                }
                QPushButton#success:hover {
                    background-color: #218838;
                }
                QPushButton#small {
                    padding: 4px 8px;
                    font-size: 10px;
                    min-height: 16px;
                }
                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                    background-color: #FFFFFF;
                    color: #333333;
                    border: 1px solid #CCCCCC;
                    padding: 6px 8px;
                    border-radius: 4px;
                    min-height: 20px;
                }
                QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                    border: 2px solid #007ACC;
                }
                QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                    width: 16px;
                    border: none;
                    background-color: #E9ECEF;
                    border-radius: 2px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover, QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                    background-color: #DEE2E6;
                }
                QComboBox::drop-down {
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #CCCCCC;
                }
                QComboBox QAbstractItemView {
                    background-color: #FFFFFF;
                    color: #333333;
                    selection-background-color: #007ACC;
                    border: 1px solid #CCCCCC;
                }
                QRadioButton, QCheckBox {
                    color: #333333;
                    spacing: 8px;
                    font-size: 11px;
                }
                QRadioButton::indicator, QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 8px;
                    border: 2px solid #CCCCCC;
                }
                QRadioButton::indicator:checked, QCheckBox::indicator:checked {
                    background-color: #007ACC;
                    border: 2px solid #007ACC;
                }
                QSlider::groove:horizontal {
                    height: 4px;
                    background: #E9ECEF;
                    border-radius: 2px;
                }
                QSlider::handle:horizontal {
                    background: #007ACC;
                    width: 16px;
                    height: 16px;
                    margin: -6px 0;
                    border-radius: 8px;
                }
                QSlider::sub-page:horizontal {
                    background: #007ACC;
                    border-radius: 2px;
                }
                QLabel {
                    color: #333333;
                    font-size: 11px;
                }
                QLabel#title {
                    font-size: 13px;
                    font-weight: bold;
                    color: #666666;
                }
                QLabel#subtitle {
                    font-size: 10px;
                    color: #888888;
                }
                QLabel#status {
                    background-color: #E9ECEF;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #333333;
                }
            """)
            
            # Estilo específico para el grupo de secuencias
            if hasattr(self, 'sequence_group'):
                self.sequence_group.setStyleSheet("""
                    QGroupBox {
                        background-color: #252526;
                        border: 1px solid #3E3E3E;
                        border-radius: 5px;
                        margin-top: 1em;
                        font-weight: bold;
                        color: #E0E0E0;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 5px;
                    }
                """)
            
            # Configurar estilos específicos para los paneles de secuencias en tema oscuro
            if hasattr(self, 'record_panel'):
                self.record_panel.setStyleSheet("""
                    QWidget {
                        background-color: #2D2D30;
                        border-radius: 4px;
                    }
                    QPushButton {
                        background-color: #0E639C;
                        color: white;
                        border: none;
                        padding: 8px 12px;
                        border-radius: 3px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #1177BB;
                    }
                    QPushButton:disabled {
                        background-color: #555555;
                        color: #888888;
                    }
                    QLineEdit {
                        background-color: #3C3C3C;
                        color: #E0E0E0;
                        border: 1px solid #555555;
                        padding: 5px;
                        border-radius: 3px;
                    }
                    QRadioButton {
                        color: #E0E0E0;
                        spacing: 8px;
                    }
                    QRadioButton::indicator {
                        width: 14px;
                        height: 14px;
                        border-radius: 7px;
                        border: 1px solid #555555;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #0E639C;
                        border: 1px solid #0E639C;
                    }
                    QLabel {
                        color: #E0E0E0;
                    }
                """)
                
            if hasattr(self, 'replay_panel'):
                self.replay_panel.setStyleSheet("""
                    QWidget {
                        background-color: #2D2D30;
                        border-radius: 4px;
                    }
                    QPushButton {
                        background-color: #0E639C;
                        color: white;
                        border: none;
                        padding: 8px 12px;
                        border-radius: 3px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #1177BB;
                    }
                    QPushButton#delete_button {
                        background-color: #A72145;
                    }
                    QPushButton#delete_button:hover {
                        background-color: #BF2E5A;
                    }
                    QPushButton:disabled {
                        background-color: #555555;
                        color: #888888;
                    }
                    QComboBox {
                        background-color: #3C3C3C;
                        color: #E0E0E0;
                        border: 1px solid #555555;
                        padding: 5px;
                        border-radius: 3px;
                        min-height: 25px;
                    }
                    QComboBox::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 20px;
                        border-left: 1px solid #555555;
                    }
                    QComboBox QAbstractItemView {
                        background-color: #3C3C3C;
                        color: #E0E0E0;
                        selection-background-color: #0E639C;
                    }
                    QSpinBox, QDoubleSpinBox {
                        background-color: #3C3C3C;
                        color: #E0E0E0;
                        border: 1px solid #555555;
                        padding: 5px;
                        border-radius: 3px;
                    }
                    QCheckBox {
                        color: #E0E0E0;
                        spacing: 8px;
                    }
                    QCheckBox::indicator {
                        width: 16px;
                        height: 16px;
                        border-radius: 3px;
                        border: 1px solid #555555;
                    }
                    QCheckBox::indicator:checked {
                        background-color: #0E639C;
                        border: 1px solid #0E639C;
                    }
                    QRadioButton {
                        color: #E0E0E0;
                        spacing: 8px;
                    }
                    QRadioButton::indicator {
                        width: 14px;
                        height: 14px;
                        border-radius: 7px;
                        border: 1px solid #555555;
                    }
                    QRadioButton::indicator:checked {
                        background-color: #0E639C;
                        border: 1px solid #0E639C;
                    }
                    QSlider::groove:horizontal {
                        height: 4px;
                        background: #555555;
                        margin: 0px;
                        border-radius: 2px;
                    }
                    QSlider::handle:horizontal {
                        background: #0E639C;
                        width: 14px;
                        height: 14px;
                        margin: -5px 0;
                        border-radius: 7px;
                    }
                    QSlider::sub-page:horizontal {
                        background: #007ACC;
                        border-radius: 2px;
                    }
                    QLabel {
                        color: #E0E0E0;
                    }
                """)
                


    def update_ui_state(self):
        # Estado del botón Iniciar/Detener
        if self.is_clicking:
            self.start_stop_button.setText("Detener (F6)")
            self.start_stop_button.setStyleSheet("background-color: #FF4136;")
        else:
            self.start_stop_button.setText("Iniciar (F6)")
            self.start_stop_button.setStyleSheet("")
        
        # Deshabilitar configuración durante el clicking
        clicking_active = self.is_clicking or self.replay_running
        self.cps_spinbox.setEnabled(not clicking_active)
        for spinbox in self.interval_spinboxes:
            spinbox.setEnabled(not clicking_active)
            
        # Deshabilitar controles de grabación durante el replay
        recording_controls_enabled = not self.replay_running
        self.record_button.setEnabled(recording_controls_enabled)
        
        # Deshabilitar opciones de grabación durante la grabación
        recording_options_enabled = not self.replay_running
        self.record_all_radio.setEnabled(recording_options_enabled)
        self.record_clicks_radio.setEnabled(recording_options_enabled)
        
        # Verificar si hay una secuencia cargada o seleccionada
        has_sequence_loaded = len(self.sequence) > 0 or self.sequence_selector.currentText() != ""
        replay_controls_enabled = not self.recording and has_sequence_loaded
        self.replay_button.setEnabled(replay_controls_enabled)
        self.replay_count_spinbox.setEnabled(replay_controls_enabled and not self.replay_running)
        self.speed_spinbox.setEnabled(replay_controls_enabled and not self.replay_running)

        self.speed_slider.setEnabled(replay_controls_enabled and not self.replay_running)
        
        # Habilitar/deshabilitar botones de velocidad rápida
        speed_buttons_enabled = replay_controls_enabled and not self.replay_running
        self.slow_button.setEnabled(speed_buttons_enabled)
        self.normal_button.setEnabled(speed_buttons_enabled)
        self.fast_button.setEnabled(speed_buttons_enabled)
        self.super_fast_button.setEnabled(speed_buttons_enabled)
        
        # Estado de los controles de secuencias - Permitir modificar nombre durante grabación
        self.sequence_name_input.setEnabled(has_sequence_loaded and not self.replay_running)
        self.sequence_selector.setEnabled(not self.recording and not self.replay_running)
        
        # Habilitar el botón de eliminar si hay una secuencia seleccionada
        delete_enabled = not self.recording and not self.replay_running
        delete_enabled = delete_enabled and (self.current_sequence_name != "" or self.sequence_selector.currentText() != "")
        self.delete_sequence_button.setEnabled(delete_enabled)
        
        # Estado del botón de renombrar - Permitir renombrar durante grabación
        rename_enabled = has_sequence_loaded and not self.replay_running
        rename_enabled = rename_enabled and self.current_sequence_name != ""
        rename_enabled = rename_enabled and self.current_sequence_name != self.sequence_name_input.text().strip()
        self.rename_button.setEnabled(rename_enabled)
        

    

    
    def set_quick_speed(self, speed):
        """Establece una velocidad predefinida"""
        self.speed_spinbox.setValue(speed)
        self.update_slider_from_spinbox(speed)
    
    def update_speed_from_slider(self, value):
        """Actualiza el valor del spinbox según el slider"""
        speed = value / 10.0
        self.speed_spinbox.blockSignals(True)
        self.speed_spinbox.setValue(speed)
        self.speed_spinbox.blockSignals(False)
        self.replay_speed = speed
        self.update_speed_label(speed)
        
        # Actualizar botones de velocidad preestablecida
        self.slow_button.setChecked(abs(speed - 0.25) < 0.01)
        self.normal_button.setChecked(abs(speed - 1.0) < 0.01)
        self.fast_button.setChecked(abs(speed - 3.0) < 0.01)
        self.super_fast_button.setChecked(abs(speed - 10.0) < 0.01)
        
        # Guardar la configuración
        self.settings.setValue("replay_speed", speed)
    
    def update_slider_from_spinbox(self, value):
        """Actualiza el valor del slider según el spinbox"""
        self.speed_slider.blockSignals(True)
        self.speed_slider.setValue(int(value * 10))
        self.speed_slider.blockSignals(False)
        self.replay_speed = value
        self.update_speed_label(value)
        
        # Actualizar botones de velocidad preestablecida
        self.slow_button.setChecked(abs(value - 0.25) < 0.01)
        self.normal_button.setChecked(abs(value - 1.0) < 0.01)
        self.fast_button.setChecked(abs(value - 3.0) < 0.01)
        self.super_fast_button.setChecked(abs(value - 10.0) < 0.01)
        
        # Guardar la configuración
        self.settings.setValue("replay_speed", value)
    
    def update_speed_label(self, value):
        """Actualiza la etiqueta de velocidad"""
        self.speed_label.setText(f"({value:.1f}x)")
    
    def toggle_window_targeting(self, state):
        """Alterna el uso de una ventana objetivo para clics relativos"""
        is_checked = self.use_window_checkbox.isChecked()
        
        # Habilitar o deshabilitar el botón de selección de ventana
        self.select_window_button.setEnabled(is_checked)
        
        # Resetear si se desmarca la casilla
        if not is_checked:
            # Limpiar datos de ventana objetivo
            self.target_window = None
            self.target_window_hwnd = None
            self.window_info_label.setText("Ninguna ventana seleccionada")
        else:
            # Abrir el selector si se marca la casilla
            self.open_window_selector()
    
    def open_window_selector(self):
        """Abre el selector de ventanas para elegir la ventana objetivo"""
        try:
            logger.debug("Abriendo selector de ventanas")
            
            self.window_selector = WindowSelector(self)
            self.window_selector.windowSelected.connect(self.set_target_window)
            self.window_selector.show()
        except Exception as e:
            logger.error(f"Error al abrir el selector de ventanas: {str(e)}")

    def setup_hotkeys(self):
        self.global_hotkeys = GlobalHotKeys()
        self.global_hotkeys.f6_pressed.connect(self.safe_toggle_clicking)
        self.global_hotkeys.f7_pressed.connect(self.safe_toggle_recording)  # Conectar F7 para grabación
        self.global_hotkeys.f8_pressed.connect(self.safe_toggle_replay)  # Conectar F8 para reproducción
        self.global_hotkeys.f11_pressed.connect(self.close)
        self.global_hotkeys.key_pressed.connect(self.record_key)

    def start_recording(self):
        if self.recording:
            return
            
        self.recording = True
        self.sequence = []
        self.sequence_start_time = time.time()
        
        # Iniciar listener para eventos del ratón
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click
        )
        self.mouse_listener.start()
        
        self.record_button.setText("Detener Grabación (F7)")
        self.record_button.setStyleSheet("background-color: #FF4136;")
        self.sequence_status_label.setText("Estado: Grabando secuencia...")
        self.update_ui_state()
        logger.debug("Grabación iniciada")
        
    def stop_recording(self):
        if not self.recording:
            return
            
        self.recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
            
        self.record_button.setText("Iniciar Grabación (F7)")
        self.record_button.setStyleSheet("")
        self.sequence_status_label.setText(f"Estado: {len(self.sequence)} eventos grabados")
        
        # Si hay secuencia y tiene nombre, guardarla
        if len(self.sequence) > 0 and self.sequence_name_input.text().strip():
            self.save_sequence()
            
        self.update_ui_state()
        logger.debug(f"Grabación detenida. {len(self.sequence)} eventos grabados")
    
    def toggle_recording(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()
            
    def on_move(self, x, y):
        """Manejador para eventos de movimiento durante la grabación"""
        if not self.recording or not self.record_all_radio.isChecked():
            return
            
        # Mejora: aumentar intervalo entre grabaciones para reducir eventos
        current_time = time.time()
        if not hasattr(self, 'last_move_time') or (current_time - self.last_move_time) > 0.1:  # 100ms entre eventos (reducido de 50ms)
            self.last_move_time = current_time
            event_time = current_time - self.sequence_start_time
            
            # Si estamos usando una ventana objetivo, guardar posición relativa
            if self.use_window_checkbox.isChecked() and self.target_window:
                # Calcular posición relativa a la ventana
                relative_x = x - self.target_window['x']
                relative_y = y - self.target_window['y']
                
                # Solo guardar información relevante
                self.sequence.append({
                    'type': 'move',
                    'x': relative_x,
                    'y': relative_y,
                    'time': event_time,
                    'relative_to_window': True,
                    'window_hwnd': self.target_window['hwnd'],
                    'window_title': self.target_window['title'],
                    'window_width': self.target_window['width'],
                    'window_height': self.target_window['height'],
                    'window_fullscreen': self.target_window.get('is_fullscreen', False)
                })
            else:
                self.sequence.append({
                    'type': 'move',
                    'x': x,
                    'y': y,
                    'time': event_time
                })
            
            # Mejorar rendimiento actualizando UI con menos frecuencia
            if len(self.sequence) % 20 == 0:  # Actualizar cada 20 movimientos (antes era 10)
                self.sequence_status_label.setText(f"Estado: Grabando... ({len(self.sequence)} eventos)")
    
    def on_click(self, x, y, button, pressed):
        """Manejador para eventos de clic durante la grabación"""
        if not self.recording:
            return
            
        current_time = time.time()
        event_time = current_time - self.sequence_start_time
        
        # Si estamos usando una ventana objetivo, guardar posición relativa
        if self.use_window_checkbox.isChecked() and self.target_window:
            relative_x = x - self.target_window['x']
            relative_y = y - self.target_window['y']
            
            # Guardar información adicional de la ventana para mejor ajuste posterior
            is_fullscreen = self.target_window.get('is_fullscreen', False)
            
            self.sequence.append({
                'type': 'click',
                'x': relative_x,
                'y': relative_y,
                'button': str(button),
                'pressed': pressed,
                'time': event_time,
                'relative_to_window': True,
                'window_hwnd': self.target_window['hwnd'],
                'window_title': self.target_window['title'],
                'window_width': self.target_window['width'],
                'window_height': self.target_window['height'],
                'window_fullscreen': is_fullscreen
            })
        else:
            self.sequence.append({
                'type': 'click',
                'x': x,
                'y': y,
                'button': str(button),
                'pressed': pressed,
                'time': event_time
            })
        
        self.sequence_status_label.setText(f"Estado: Grabando... ({len(self.sequence)} eventos)")
        logger.debug(f"Clic {'presionado' if pressed else 'liberado'} en ({x}, {y}) con botón {button}")
    
    def record_key(self, key):
        """Graba eventos de teclado durante la grabación"""
        if not self.recording or not self.record_all_radio.isChecked():
            return
            
        current_time = time.time()
        event_time = current_time - self.sequence_start_time
        
        self.sequence.append({
            'type': 'key',
            'key': key,
            'time': event_time
        })
        
        self.sequence_status_label.setText(f"Estado: Grabando... ({len(self.sequence)} eventos)")
        logger.debug(f"Tecla grabada: {key}")
    
    def toggle_replay(self):
        """Inicia o detiene la reproducción de la secuencia cargada"""
        if self.replay_running:
            self.stop_replay()
        else:
            self.start_replay()
    
    def start_replay(self):
        """Inicia la reproducción de la secuencia cargada"""
        # Si no hay secuencia cargada, intentar cargar la seleccionada
        if not self.sequence or len(self.sequence) == 0:
            selected_name = self.sequence_selector.currentText()
            if selected_name and selected_name in self.saved_sequences:
                self.sequence = self.settings.value(f"sequence_{selected_name}", [])
                self.current_sequence_name = selected_name
                self.sequence_name_input.setText(selected_name)
                logger.debug(f"Cargando secuencia automáticamente: '{selected_name}' ({len(self.sequence)} eventos)")
            else:
                QMessageBox.warning(self, "Error", "No hay secuencia cargada o seleccionada para reproducir.")
                return
            
        if self.recording:
            self.stop_recording()
            
        if self.is_clicking:
            self.stop_clicking()
            
        self.replay_running = True
        self.replay_index = 0
        self.replay_count = 0
        self.replay_total = self.replay_count_spinbox.value()
        
        # Si es infinito (valor 0), mantener como 0 para indicar infinito
        if self.replay_total == 0:
            self.replay_total = 0  # Infinito
            
        # Inicializar variables de tiempo
        self.last_event_time = time.time()
        
        # Iniciar el primer evento inmediatamente
        QTimer.singleShot(0, self._process_replay)
        
        # Actualizar UI
        self.replay_button.setText("⏹️ Detener reproducción (F8)")
        self.replay_button.setStyleSheet("background-color: #A72145;")
        total_display = "∞" if self.replay_total == 0 else self.replay_total
        self.sequence_status_label.setText(f"Estado: Reproduciendo secuencia (0/{total_display})")
        self.update_ui_state()
        total_display = "∞" if self.replay_total == 0 else self.replay_total
        logger.debug(f"Reproducción iniciada. Secuencia: {len(self.sequence)} eventos. Repeticiones: {total_display}")
        
    def stop_replay(self):
        """Detiene la reproducción de la secuencia"""
        if not self.replay_running:
            return
            
        self.replay_running = False
            
        # Actualizar UI
        self.replay_button.setText("▶️ Reproducir secuencia (F8)")
        self.replay_button.setStyleSheet("")
        self.sequence_status_label.setText(f"Estado: Reproducción detenida")
        self.update_ui_state()
        logger.debug("Reproducción detenida")
        
    def _process_replay(self):
        """Procesa la reproducción de la secuencia grabada"""
        if not self.replay_running or not self.sequence:
            return
        
        # Calcular tiempo efectivo teniendo en cuenta la velocidad
        if self.replay_index < len(self.sequence):
            event = self.sequence[self.replay_index]
            effective_speed = self.replay_speed
            
            # Ejecutar el evento actual
            self._execute_event(event, effective_speed)
            
            # Avanzar al siguiente evento
            self.replay_index += 1
            
            # Calcular el tiempo de espera para el siguiente evento basado en la velocidad
            if self.replay_index < len(self.sequence):
                next_event = self.sequence[self.replay_index]
                current_event = self.sequence[self.replay_index - 1]
                
                # Calcular el tiempo original entre eventos
                original_delay = next_event['time'] - current_event['time']
                
                # Aplicar la velocidad (tiempo más corto = más rápido)
                adjusted_delay = original_delay / effective_speed
                
                # Programar el siguiente evento
                QTimer.singleShot(int(adjusted_delay * 1000), self._process_replay)
            else:
                # Se completó la secuencia
                self.replay_count += 1
                
                # Actualizar información de estado
                if self.replay_total > 0 and self.replay_count >= self.replay_total:
                    # Finalizar reproducción (no infinito)
                    self.stop_replay()
                    return
                else:
                    # Reiniciar para la siguiente repetición
                    self.replay_index = 0
                    QTimer.singleShot(500, self._process_replay)  # Pausa entre repeticiones
                    # Actualizar etiqueta de estado con menos frecuencia
                    if self.replay_count % 5 == 0 or self.replay_count == 1:
                        count_display = self.replay_count
                        total_display = "∞" if self.replay_total == 0 else self.replay_total
                        self.sequence_status_label.setText(f"Estado: Completado {count_display}/{total_display} - Esperando para continuar...")
        else:
            # No debería ocurrir, pero por si acaso
            self.stop_replay()
    

    
    def stop_window_monitoring(self):
        """Detiene el monitoreo de cambios en la ventana objetivo"""
        if hasattr(self, 'window_monitor_timer') and self.window_monitor_timer is not None:
            self.window_monitor_timer.stop()
            self.window_monitor_timer = None
            logger.debug("Monitoreo de ventana objetivo detenido")
            
    def _execute_event(self, event, effective_speed):
        """Ejecuta un evento de la secuencia grabada"""
        if event['type'] == 'move':
            x, y = event['x'], event['y']
            
            # Ajustar para eventos relativos a una ventana
            if event.get('relative_to_window', False):
                x, y = self._get_window_adjusted_coordinates(x, y, event)
            
            win32api.SetCursorPos((int(x), int(y)))
            logger.debug(f"Moviendo cursor a ({x}, {y}) a velocidad {effective_speed}x")
        elif event['type'] == 'click' and event['pressed']:
            x, y = event['x'], event['y']
            
            # Ajustar para eventos relativos a una ventana
            if event.get('relative_to_window', False):
                x, y = self._get_window_adjusted_coordinates(x, y, event)
            
            win32api.SetCursorPos((int(x), int(y)))
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            logger.debug(f"Clic en ({x}, {y}) a velocidad {effective_speed}x")
            
            # Incrementar contadores de clics
            self.click_count += 1
            self.total_clicks += 1
            self.session_clicks += 1
            self.today_clicks += 1
            self.update_click_count()
        elif event['type'] == 'key':
            # Simular presión de tecla
            logger.debug(f"Simulando tecla: {event['key']} a velocidad {effective_speed}x")
            try:
                # Para teclas especiales usar pynput
                key_to_press = event['key']
                if key_to_press.startswith("Key."):
                    # Para teclas especiales como Enter, Shift, etc.
                    special_key = getattr(keyboard.Key, key_to_press.split(".")[1])
                    controller = keyboard.Controller()
                    controller.press(special_key)
                    controller.release(special_key)
                else:
                    # Para teclas normales
                    pyautogui.press(key_to_press)
            except Exception as e:
                logger.error(f"Error al simular tecla: {str(e)}")

    def _get_window_adjusted_coordinates(self, x, y, event):
        """Ajusta coordenadas según la posición actual de la ventana objetivo.
        Funciona correctamente con múltiples monitores y cambios de posición de ventana.
        """
        # Intentar encontrar la ventana por handle o título
        hwnd = event.get('window_hwnd')
        title = event.get('window_title', '')
        
        # Usar handle si está disponible y es válido
        if hwnd and win32gui.IsWindow(hwnd):
            try:
                # Obtener la posición actual de la ventana
                rect = win32gui.GetWindowRect(hwnd)
                window_x, window_y = rect[0], rect[1]
                
                # Verificar si la ventana está minimizada
                if window_x == -32000 and window_y == -32000:
                    # Restaurar ventana minimizada
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    # Esperar un momento para que la ventana se restaure
                    time.sleep(0.2)
                    # Volver a obtener la posición
                    rect = win32gui.GetWindowRect(hwnd)
                    window_x, window_y = rect[0], rect[1]
                    window_width = rect[2] - rect[0]
                    window_height = rect[3] - rect[1]
                
                # Verificar si la ventana está en pantalla completa
                is_fullscreen = self._check_if_fullscreen(hwnd, rect)
                
                # Comparar dimensiones con las originales para escalar si es necesario
                orig_width = event.get('window_width', window_width)
                orig_height = event.get('window_height', window_height)
                
                # Si la ventana cambió de tamaño, aplicar escala a las coordenadas
                scale_x = window_width / orig_width if orig_width > 0 else 1
                scale_y = window_height / orig_height if orig_height > 0 else 1
                
                # Solo aplicar escala si hay diferencia significativa
                if abs(scale_x - 1) > 0.01 or abs(scale_y - 1) > 0.01:
                    x = int(x * scale_x)
                    y = int(y * scale_y)
                    logger.debug(f"Escalando coordenadas: factor X={scale_x:.2f}, factor Y={scale_y:.2f}")
                
                # Traer la ventana al frente para asegurar que los clics lleguen correctamente
                if not win32gui.IsWindowVisible(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                
                # Activar la ventana si no está activa
                foreground_hwnd = win32gui.GetForegroundWindow()
                if foreground_hwnd != hwnd:
                    # SetForegroundWindow puede fallar si la aplicación no está respondiendo
                    try:
                        win32gui.SetForegroundWindow(hwnd)
                        time.sleep(0.1)  # Pequeña pausa para permitir que la ventana responda
                    except Exception as e:
                        logger.warning(f"No se pudo activar la ventana: {str(e)}")
                
                adjusted_x = window_x + x
                adjusted_y = window_y + y
                
                logger.debug(f"Ventana encontrada por handle. Ajustando ({x},{y}) -> ({adjusted_x},{adjusted_y})")
                if is_fullscreen:
                    logger.debug(f"La ventana está en pantalla completa")
                
                return adjusted_x, adjusted_y
            except Exception as e:
                logger.error(f"Error al ajustar coordenadas por handle: {str(e)}")
        
        # Si no se encontró por handle, intentar por título
        if title:
            try:
                # Buscar todas las ventanas con ese título
                matching_windows = []
                
                def find_all_windows_callback(hwnd, extra):
                    if (win32gui.IsWindowVisible(hwnd) and 
                        title.lower() in win32gui.GetWindowText(hwnd).lower()):
                        rect = win32gui.GetWindowRect(hwnd)
                        matching_windows.append({
                            'hwnd': hwnd,
                            'rect': rect,
                            'title': win32gui.GetWindowText(hwnd)
                        })
                    return True
                
                win32gui.EnumWindows(find_all_windows_callback, None)
                
                if matching_windows:
                    # Usar la primera ventana encontrada (o se podría implementar una lógica para elegir la mejor)
                    window = matching_windows[0]
                    rect = window['rect']
                    
                    # Intentar activar la ventana
                    try:
                        win32gui.SetForegroundWindow(window['hwnd'])
                        time.sleep(0.1)
                    except:
                        pass
                    
                    adjusted_x = rect[0] + x
                    adjusted_y = rect[1] + y
                    
                    logger.debug(f"Ventana encontrada por título. Ajustando ({x},{y}) -> ({adjusted_x},{adjusted_y})")
                    return adjusted_x, adjusted_y
            except Exception as e:
                logger.error(f"Error al ajustar coordenadas por título: {str(e)}")
        
        logger.warning(f"No se pudo encontrar la ventana objetivo. Usando coordenadas originales ({x},{y})")
        return x, y
        
    def _check_if_fullscreen(self, hwnd, rect=None):
        """Detecta si una ventana está en modo pantalla completa"""
        try:
            if rect is None:
                rect = win32gui.GetWindowRect(hwnd)
            
            # Obtener dimensiones del monitor donde está la ventana
            monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST))
            monitor_rect = monitor_info['Monitor']
            
            # Una ventana está en pantalla completa si ocupa exactamente todo el espacio del monitor
            is_fullscreen = (rect[0] == monitor_rect[0] and 
                            rect[1] == monitor_rect[1] and 
                            rect[2] == monitor_rect[2] and 
                            rect[3] == monitor_rect[3])
            
            return is_fullscreen
        except Exception as e:
            logger.error(f"Error al comprobar si la ventana está en pantalla completa: {str(e)}")
            return False
    
    def open_window_selector(self):
        """Abre el selector de ventanas para elegir la ventana objetivo"""
        try:
            # Asegurar que el checkbox esté activado y el botón habilitado
            self.use_window_checkbox.setChecked(True)
            self.toggle_window_targeting(True)  # Asegurar que el botón esté habilitado
            
            logger.debug("Abriendo selector de ventanas")
            
            # Crear el selector de ventanas si no existe o recrearlo si está cerrado
            if not hasattr(self, 'window_selector') or self.window_selector.isHidden():
                self.window_selector = WindowSelector(self)
                self.window_selector.show()
            else:
                # Si ya está abierto, solo traerlo al frente
                self.window_selector.raise_()
                self.window_selector.activateWindow()
                
        except Exception as e:
            error_msg = f"Error al abrir selector de ventanas: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
    
    def set_target_window(self, window_data):
        """Establece la ventana objetivo seleccionada"""
        if window_data:
            self.target_window = window_data
            self.target_window_hwnd = window_data.get('hwnd')
            
            # Formatear texto para mostrar información de la ventana
            window_title = window_data.get('title', 'Desconocida')
            window_width = window_data.get('width', 0)
            window_height = window_data.get('height', 0)
            
            window_info = f"Ventana: {window_title} ({window_width}x{window_height})"
            self.window_info_label.setText(window_info)
            
            logger.debug(f"Ventana objetivo establecida: {window_title}")
        else:
            self.target_window = None
            self.target_window_hwnd = None
            self.window_info_label.setText("Ninguna ventana seleccionada")
            
    def check_target_window_changes(self):
        """Verifica si la ventana objetivo ha cambiado de tamaño o posición"""
        if not self.target_window or not self.use_window_checkbox.isChecked():
            return
        
        try:
            hwnd = self.target_window['hwnd']
            if win32gui.IsWindow(hwnd):
                # Obtener la posición actual de la ventana
                current_rect = win32gui.GetWindowRect(hwnd)
                current_x = current_rect[0]
                current_y = current_rect[1]
                current_width = current_rect[2] - current_rect[0]
                current_height = current_rect[3] - current_rect[1]
                
                # Detectar si la ventana cambió a pantalla completa
                is_fullscreen = self._check_if_fullscreen(hwnd, current_rect)
                was_fullscreen = self.target_window.get('is_fullscreen', False)
                
                # Comprobar si ha cambiado la posición, tamaño o estado de pantalla completa
                if (current_x != self.target_window['x'] or 
                    current_y != self.target_window['y'] or 
                    current_width != self.target_window['width'] or 
                    current_height != self.target_window['height'] or
                    is_fullscreen != was_fullscreen):
                    
                    # Actualizar información de la ventana objetivo
                    old_x = self.target_window['x']
                    old_y = self.target_window['y']
                    old_width = self.target_window['width']
                    old_height = self.target_window['height']
                    
                    self.target_window['x'] = current_x
                    self.target_window['y'] = current_y
                    self.target_window['width'] = current_width
                    self.target_window['height'] = current_height
                    self.target_window['is_fullscreen'] = is_fullscreen
                    
                    # Actualizar la información mostrada
                    window_info = f"Ventana: {self.target_window['title']} ({current_width}x{current_height})"
                    if is_fullscreen:
                        window_info += " [Pantalla Completa]"
                        
                    if 'monitor' in self.target_window:
                        # Actualizar info del monitor si es necesario
                        current_monitor = self.get_monitor_info_for_window(current_rect)
                        if current_monitor != self.target_window['monitor']:
                            self.target_window['monitor'] = current_monitor
                        window_info += f" - {current_monitor}"
                    
                    self.window_info_label.setText(window_info)
                    
                    # Registrar el cambio
                    logger.debug(f"Cambio en ventana objetivo: Posición ({old_x},{old_y}) -> ({current_x},{current_y}), "
                                f"Tamaño ({old_width}x{old_height}) -> ({current_width}x{current_height}), "
                                f"Pantalla Completa: {was_fullscreen} -> {is_fullscreen}")
            else:
                # La ventana ha sido cerrada
                logger.warning("La ventana objetivo ya no existe")
                self.window_info_label.setText("⚠️ Ventana cerrada o no disponible")
                self.window_info_label.setStyleSheet("color: #FF5252; font-weight: bold;")
                self.target_window = None
                self.stop_window_monitoring()
        except Exception as e:
            logger.error(f"Error al comprobar cambios en la ventana objetivo: {str(e)}")
            
    def start_window_monitoring(self):
        """Inicia el monitoreo de cambios en la ventana objetivo"""
        # Detener timer anterior si existe
        self.stop_window_monitoring()
        
        # Crear nuevo timer para monitorear la ventana
        self.window_monitor_timer = QTimer(self)
        self.window_monitor_timer.timeout.connect(self.check_target_window_changes)
        self.window_monitor_timer.start(1000)  # Verificar cada segundo
        logger.debug("Monitoreo de ventana objetivo iniciado")
    
    def get_monitor_info_for_window(self, rect):
        """Determina en qué monitor se encuentra una ventana"""
        try:
            x_center = (rect[0] + rect[2]) // 2
            y_center = (rect[1] + rect[3]) // 2
            
            # Obtener información de monitores
            monitors = []
            
            # Modificar la forma de llamar a EnumDisplayMonitors para evitar el error
            def callback(monitor, dc, rect, data):
                info = win32api.GetMonitorInfo(monitor)
                monitor_rect = info['Monitor']
                work_rect = info['Work']
                is_primary = (info['Flags'] == 1)  # MONITORINFOF_PRIMARY
                
                monitors.append({
                    'index': len(monitors),
                    'rect': monitor_rect,
                    'work_rect': work_rect,
                    'is_primary': is_primary
                })
                return True
            
            # CORRECCIÓN: Usar directamente win32gui para la enumeración
            try:
                win32gui.EnumDisplayMonitors(None, None, callback)
            except Exception as e:
                logger.error(f"Error específico en EnumDisplayMonitors: {str(e)}")
                # Plan B: intentar obtener al menos información básica del monitor principal
                self.monitors.append({
                    'index': 0,
                    'rect': (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)),
                    'work_rect': (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)),
                    'is_primary': True
                })
                
            logger.debug(f"Detectados {len(self.monitors)} monitores")
        except Exception as e:
            logger.error(f"Error al obtener información de monitores: {str(e)}")
            self.monitors = []
    
    def toggle_window_targeting(self):
        """Toggle the window targeting mode."""
        if self.target_window_hwnd:
            self.target_window_hwnd = None
            self.target_window = None
            self.select_window_button.setText("Seleccionar Ventana")
            self.window_info_label.setText("Ninguna ventana seleccionada")
            self.statusBar().showMessage("Modo de ventana objetivo desactivado")
            logger.debug("Desactivó el modo de ventana objetivo")
            # Detener monitoreo si está activo
            self.stop_window_monitoring()
        else:
            self.open_window_selector()

    def open_window_selector(self):
        """Opens a window selector to choose the target window."""
        logger.debug("Abriendo selector de ventanas")
        if not self.select_window_button.isEnabled():
            return
            
        # Disable the button while the window selector is open
        self.select_window_button.setEnabled(False)
        
        try:
            self.window_selector = WindowSelector(self)
            # COMENTADO: Esta línea causa el error porque windowSelected no existe
            # self.window_selector.windowSelected.connect(self.set_target_window)
            self.window_selector.show()
            self.window_selector.activateWindow()  # Bring to front
            
            # Position the window selector in the center of the main window
            main_geo = self.geometry()
            selector_geo = self.window_selector.geometry()
            x = main_geo.x() + (main_geo.width() - selector_geo.width()) // 2
            y = main_geo.y() + (main_geo.height() - selector_geo.height()) // 2
            self.window_selector.move(x, y)
            
        except Exception as e:
            logger.error(f"Error al abrir el selector de ventanas: {e}")
            self.select_window_button.setEnabled(True)
            QMessageBox.critical(self, "Error", f"No se pudo abrir el selector de ventanas: {e}")

    def rename_sequence(self):
        """Rename the currently loaded sequence."""
        if not self.current_sequence_name:
            QMessageBox.information(self, "Renombrar Secuencia", 
                                   "Primero debes cargar una secuencia para renombrarla.")
            return
            
        new_name, ok = QInputDialog.getText(
            self, "Renombrar Secuencia", 
            f"Ingresa un nuevo nombre para '{self.current_sequence_name}':",
            text=self.current_sequence_name
        )
        
        if not ok or not new_name or new_name == self.current_sequence_name:
            return
            
        # Verificar si ya existe una secuencia con ese nombre
        if new_name in self.saved_sequences:
            reply = QMessageBox.question(
                self, 
                "Confirmar Reemplazo", 
                f"Ya existe una secuencia con el nombre '{new_name}'. ¿Deseas reemplazarla?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                return
        
        # Guardar la secuencia con el nuevo nombre
        old_name = self.current_sequence_name
        
        # Si la lista es un diccionario
        if isinstance(self.saved_sequences, dict):
            self.saved_sequences[new_name] = self.saved_sequences.pop(old_name)
        else:
            # Si es una lista, eliminar el nombre anterior y añadir el nuevo
            if old_name in self.saved_sequences:
                self.saved_sequences.remove(old_name)
            if new_name not in self.saved_sequences:
                self.saved_sequences.append(new_name)
            
            # Guardar la secuencia con el nuevo nombre
            sequence_data = self.settings.value(f"sequence_{old_name}", [])
            self.settings.setValue(f"sequence_{new_name}", sequence_data)
            self.settings.remove(f"sequence_{old_name}")
        
        # Actualizar el diccionario de fechas si existe
        if hasattr(self, 'sequence_dates') and old_name in self.sequence_dates:
            self.sequence_dates[new_name] = self.sequence_dates.pop(old_name)
        
        # Actualizar la interfaz
        self.current_sequence_name = new_name
        self.update_sequence_selector()
        
        # Seleccionar la secuencia renombrada
        index = self.sequence_selector.findText(new_name)
        if index >= 0:
            self.sequence_selector.setCurrentIndex(index)
            
        # Actualizar la etiqueta de estado
        self.sequence_status_label.setText(f"Estado: Secuencia renombrada a '{new_name}'")
        self.statusBar().showMessage(f"Secuencia renombrada a '{new_name}'")
        logger.debug(f"Secuencia renombrada de '{old_name}' a '{new_name}'")
        
        # Guardar los cambios
        self.settings.setValue("saved_sequences", self.saved_sequences)
        self.settings.setValue("sequence_dates", self.sequence_dates)
        self.settings.sync()

    def update_sequence_selector(self):
        """Actualiza el selector de secuencias de forma optimizada"""
        # Guardar la selección actual
        current_selection = self.sequence_selector.currentText()
        
        # Bloquear señales durante la actualización para evitar activaciones innecesarias
        self.sequence_selector.blockSignals(True)
        
        # Limpiar y actualizar de una vez
        self.sequence_selector.clear()
        
        if self.saved_sequences:
            # Ordenar secuencias por fecha, más recientes primero
            sorted_sequences = sorted(
                self.saved_sequences,
                key=lambda x: self.sequence_dates.get(x, QDateTime.currentDateTime().toString()),
                reverse=True
            )
            
            # Añadir todas las secuencias
            self.sequence_selector.addItems(sorted_sequences)
            
            # Restaurar la selección anterior si es posible
            if current_selection in self.saved_sequences:
                index = self.sequence_selector.findText(current_selection)
                if index >= 0:
                    self.sequence_selector.setCurrentIndex(index)
        
        # Restaurar señales
        self.sequence_selector.blockSignals(False)
        
        # Actualizar estado de la UI
        self.update_ui_state()

    def load_selected_sequence(self, index):
        """Carga la secuencia seleccionada del combo box"""
        if not self.saved_sequences or index < 0:
            self.sequence = []
            self.current_sequence_name = ""
            self.sequence_status_label.setText("Estado: No hay secuencia seleccionada")
            self.update_ui_state()
            return
            
        name = self.sequence_selector.currentText()
        if name in self.saved_sequences:
            self.sequence = self.settings.value(f"sequence_{name}", [])
            self.current_sequence_name = name
            self.sequence_name_input.setText(name)
            self.sequence_status_label.setText(f"Estado: Secuencia '{name}' cargada ({len(self.sequence)} eventos)")
            self.update_ui_state()
            logger.debug(f"Secuencia '{name}' cargada ({len(self.sequence)} eventos)")
        else:
            self.sequence = []
            self.current_sequence_name = ""
            self.sequence_status_label.setText("Estado: Secuencia no encontrada")
            self.update_ui_state()
    
    def save_sequence(self):
        """Guarda la secuencia actual con el nombre especificado"""
        if not self.sequence:
            QMessageBox.warning(self, "Error", "No hay secuencia para guardar.")
            return
            
        name = self.sequence_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Por favor, ingrese un nombre para la secuencia.")
            return
            
        # Guardar la secuencia
        self.settings.setValue(f"sequence_{name}", self.sequence)
        
        # Actualizar lista de secuencias guardadas
        if name not in self.saved_sequences:
            self.saved_sequences.append(name)
            self.settings.setValue("saved_sequences", self.saved_sequences)
            
        # Guardar la fecha de creación/modificación
        self.sequence_dates[name] = QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
        self.settings.setValue("sequence_dates", self.sequence_dates)
        
        self.current_sequence_name = name
        self.update_sequence_selector()
        
        # Seleccionar la secuencia recién guardada en el combo
        index = self.sequence_selector.findText(name)
        if index >= 0:
            self.sequence_selector.setCurrentIndex(index)
            
        self.sequence_status_label.setText(f"Estado: Secuencia '{name}' guardada ({len(self.sequence)} eventos)")
        self.update_ui_state()
        logger.debug(f"Secuencia '{name}' guardada ({len(self.sequence)} eventos)")
    
    def load_sequence(self):
        """Muestra un diálogo para cargar una secuencia guardada"""
        if not self.saved_sequences:
            QMessageBox.information(self, "Información", "No hay secuencias guardadas para cargar.")
            return
            
        items = list(self.saved_sequences)
        current_item = self.current_sequence_name if self.current_sequence_name in items else items[0]
        
        dialog = QInputDialog(self)
        dialog.setComboBoxItems(items)
        dialog.setComboBoxEditable(False)
        dialog.setWindowTitle("Cargar secuencia")
        dialog.setLabelText("Seleccione una secuencia para cargar:")
        dialog.setTextValue(current_item)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_sequence = dialog.textValue()
            index = self.sequence_selector.findText(selected_sequence)
            if index >= 0:
                self.sequence_selector.setCurrentIndex(index)
    
    def delete_sequence(self):
        """Elimina la secuencia seleccionada"""
        name = self.sequence_selector.currentText()
        
        if not name or name not in self.saved_sequences:
            return
            
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Está seguro de que desea eliminar la secuencia '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Eliminar la secuencia
            self.settings.remove(f"sequence_{name}")
            
            # Actualizar lista de secuencias guardadas
            self.saved_sequences.remove(name)
            self.settings.setValue("saved_sequences", self.saved_sequences)
            
            # Eliminar la fecha de creación
            if name in self.sequence_dates:
                del self.sequence_dates[name]
                self.settings.setValue("sequence_dates", self.sequence_dates)
            
            # Si la secuencia eliminada era la actual, limpiarla
            if name == self.current_sequence_name:
                self.sequence = []
                self.current_sequence_name = ""
                self.sequence_name_input.clear()
            
            self.update_sequence_selector()
            self.sequence_status_label.setText(f"Estado: Secuencia '{name}' eliminada")
            self.update_ui_state()
            logger.debug(f"Secuencia '{name}' eliminada")
    
    def rename_sequence(self):
        """Renombra la secuencia actual"""
        if not self.current_sequence_name:
            return
            
        new_name = self.sequence_name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Error", "Por favor, ingrese un nombre válido para la secuencia.")
            return
            
        if new_name == self.current_sequence_name:
            return
            
        if new_name in self.saved_sequences:
            reply = QMessageBox.question(
                self,
                "Confirmar reemplazo",
                f"Ya existe una secuencia con el nombre '{new_name}'. ¿Desea reemplazarla?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                self.sequence_name_input.setText(self.current_sequence_name)
                return
        
        # Guardar la secuencia con el nuevo nombre
        self.settings.setValue(f"sequence_{new_name}", self.sequence)
        
        # Si el nuevo nombre no estaba en la lista, añadirlo
        if new_name not in self.saved_sequences:
            self.saved_sequences.append(new_name)
        
        # Copiar la fecha de creación o usar la fecha actual
        if self.current_sequence_name in self.sequence_dates:
            self.sequence_dates[new_name] = self.sequence_dates[self.current_sequence_name]
        else:
            self.sequence_dates[new_name] = QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
        
        # Si es un nombre nuevo (no reemplazo), eliminar la secuencia anterior
        if self.current_sequence_name != new_name and self.current_sequence_name in self.saved_sequences:
            self.saved_sequences.remove(self.current_sequence_name)
            self.settings.remove(f"sequence_{self.current_sequence_name}")
            
            if self.current_sequence_name in self.sequence_dates:
                del self.sequence_dates[self.current_sequence_name]
        
        # Actualizar todo
        self.current_sequence_name = new_name
        self.settings.setValue("saved_sequences", self.saved_sequences)
        self.settings.setValue("sequence_dates", self.sequence_dates)
        
        self.update_sequence_selector()
        
        # Seleccionar la secuencia recién renombrada en el combo
        index = self.sequence_selector.findText(new_name)
        if index >= 0:
            self.sequence_selector.setCurrentIndex(index)
            
        self.sequence_status_label.setText(f"Estado: Secuencia renombrada a '{new_name}'")
        self.update_ui_state()
        logger.debug(f"Secuencia renombrada a '{new_name}'")

class WindowSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
            self.setWindowTitle("Seleccionar Ventana")
            self.setGeometry(100, 100, 600, 400)
            
            layout = QVBoxLayout(self)
            
            # Instrucciones
            instruction_label = QLabel("Seleccione una aplicación o ventana para capturar sus dimensiones:")
            instruction_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(instruction_label)
            
            # Contenedor principal (lista y detalles)
            main_container = QHBoxLayout()
            
            # Lista de ventanas con buscador
            list_container = QVBoxLayout()
            search_layout = QHBoxLayout()
            search_label = QLabel("Buscar:")
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Filtrar por nombre...")
            self.search_input.textChanged.connect(self.filter_windows)
            search_layout.addWidget(search_label)
            search_layout.addWidget(self.search_input)
            list_container.addLayout(search_layout)
            
            # Lista de ventanas
            self.window_list = QListWidget()
            self.window_list.setMinimumHeight(200)
            self.window_list.setMinimumWidth(350)
            self.window_list.currentItemChanged.connect(self.on_window_selected)
            list_container.addWidget(self.window_list)
            
            # Botones de acción
            list_buttons = QHBoxLayout()
            self.refresh_button = QPushButton("Actualizar Lista")
            self.refresh_button.clicked.connect(self.refresh_window_list)
            list_buttons.addWidget(self.refresh_button)
            list_buttons.addStretch()
            list_container.addLayout(list_buttons)
            
            # Panel de información
            info_panel = QGroupBox("Información de la ventana")
            info_layout = QVBoxLayout(info_panel)
            
            # Propiedades principales
            self.title_label = QLabel("Título: --")
            self.process_label = QLabel("Proceso: --")
            self.pos_label = QLabel("Posición: --")
            self.size_label = QLabel("Tamaño: --")
            self.res_label = QLabel("Resolución: --")
            self.monitor_label = QLabel("Monitor: --")  # Nueva etiqueta para monitor
            
            # Agregar las propiedades al panel
            info_layout.addWidget(self.title_label)
            info_layout.addWidget(self.process_label)
            info_layout.addWidget(self.pos_label)
            info_layout.addWidget(self.size_label)
            info_layout.addWidget(self.res_label)
            info_layout.addWidget(self.monitor_label)  # Agregar la nueva etiqueta
            
            # Imagen de vista previa
            preview_label = QLabel("Vista previa:")
            info_layout.addWidget(preview_label)
            self.preview_image = QLabel("No disponible")
            self.preview_image.setMinimumSize(150, 100)
            self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_image.setStyleSheet("background-color: #EEEEEE; border: 1px solid #CCCCCC;")
            info_layout.addWidget(self.preview_image)
            
            info_layout.addStretch()
            
            # Botones de acción principal
            button_layout = QHBoxLayout()
            self.select_button = QPushButton("Seleccionar Ventana")
            self.select_button.clicked.connect(self.select_window)
            self.select_button.setStyleSheet("background-color: #007ACC; color: white; font-weight: bold;")
            self.select_button.setMinimumWidth(150)
            
            self.cancel_button = QPushButton("Cancelar")
            self.cancel_button.clicked.connect(self.close)
            
            button_layout.addWidget(self.cancel_button)
            button_layout.addStretch()
            button_layout.addWidget(self.select_button)
            
            # Agregar todo al layout principal
            main_container.addLayout(list_container, 2)
            main_container.addWidget(info_panel, 1)
            
            layout.addLayout(main_container)
            layout.addLayout(button_layout)
            
            # Variables para almacenar los datos de la ventana seleccionada
            self.selected_window = None
            self.window_data = {}
            
            # Obtener información de monitores
            if parent:
                # Usar la información de monitores del padre si está disponible
                if hasattr(parent, 'monitors'):
                    self.monitors = parent.monitors
                else:
                    self.get_monitor_info()
            else:
                self.get_monitor_info()
            
            # Llenar la lista de ventanas al inicio
            self.refresh_window_list()
            
            # Centrar la ventana con respecto a la ventana principal
            if parent:
                parent_geometry = parent.geometry()
                parent_center = parent_geometry.center()
                
                # Calcular la posición para centrar esta ventana
                geometry = self.geometry()
                geometry.moveCenter(parent_center)
                self.setGeometry(geometry)
            
            logger.debug("WindowSelector inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar WindowSelector: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error al inicializar el selector de ventanas: {str(e)}")

    def get_monitor_info(self):
        """Obtiene información sobre los monitores conectados al sistema"""
        try:
            self.monitors = []
            
            # Obtener dimensiones de la pantalla principal
            screen_width = win32api.GetSystemMetrics(0)  # SM_CXSCREEN
            screen_height = win32api.GetSystemMetrics(1)  # SM_CYSCREEN
            
            # Crear un monitor con datos básicos
            self.monitors.append({
                'index': 0,
                'rect': (0, 0, screen_width, screen_height),
                'work_rect': (0, 0, screen_width, screen_height),
                'is_primary': True
            })
            
        except Exception as e:
            logger.error(f"Error al obtener información de monitores: {str(e)}")
            self.monitors = []
    
    def get_monitor_for_window(self, rect):
        """Determina en qué monitor se encuentra una ventana"""
        if not self.monitors:
            return "Desconocido"
            
        x_center = (rect[0] + rect[2]) // 2
        y_center = (rect[1] + rect[3]) // 2
        
        for i, monitor in enumerate(self.monitors):
            m_rect = monitor['rect']
            if (m_rect[0] <= x_center <= m_rect[2] and 
                m_rect[1] <= y_center <= m_rect[3]):
                primary = " (Principal)" if monitor['is_primary'] else ""
                return f"Monitor {i+1}{primary}"
        
        return "Fuera de pantalla"
        
    def filter_windows(self, text):
        """Filtra la lista de ventanas según el texto ingresado"""
        for i in range(self.window_list.count()):
            item = self.window_list.item(i)
            if text.lower() in item.text().lower():
                item.setHidden(False)
            else:
                item.setHidden(True)
    
    def on_window_selected(self, current, previous):
        """Actualiza la información al seleccionar una ventana de la lista"""
        if current:
            self.update_window_info(current.text())
    
    def refresh_window_list(self):
        """Actualiza la lista de ventanas y procesos activos"""
        self.window_list.clear()
        self.window_data = {}
        
        def enum_windows_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title not in ["Program Manager", "Windows Shell Experience Host"]:
                    # Obtener información del proceso (si es posible)
                    try:
                        import win32process
                        import psutil
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        process = psutil.Process(pid)
                        process_name = process.name()
                    except (ImportError, Exception):
                        process_name = "Unknown"
                        
                    # Obtener el rectángulo de la ventana
                    rect = win32gui.GetWindowRect(hwnd)
                    
                    # Guardar los datos
                    display_name = f"{title} ({process_name})"
                    self.window_list.addItem(display_name)
                    self.window_data[display_name] = {
                        'title': title,
                        'process': process_name,
                        'hwnd': hwnd,
                        'rect': rect,
                        'x': rect[0],
                        'y': rect[1],
                        'width': rect[2] - rect[0],
                        'height': rect[3] - rect[1],
                        'monitor': self.get_monitor_for_window(rect)
                    }
            return True
            
        win32gui.EnumWindows(enum_windows_callback, None)
        
        # Ordenar por nombre de proceso
        self.window_list.sortItems()
    
    def update_window_info(self, window_name):
        """Actualiza la información de la ventana seleccionada"""
        if window_name in self.window_data:
            data = self.window_data[window_name]
            rect = data['rect']
            
            self.title_label.setText(f"Título: {data['title']}")
            self.process_label.setText(f"Proceso: {data['process']}")
            self.pos_label.setText(f"Posición: X={rect[0]}, Y={rect[1]}")
            self.size_label.setText(f"Tamaño: Ancho={data['width']}, Alto={data['height']}")
            self.res_label.setText(f"Resolución: {data['width']}x{data['height']} px")
            self.monitor_label.setText(f"Monitor: {data['monitor']}")
            
            # Actualizar la ventana seleccionada
            self.selected_window = {
                'title': data['title'],
                'process': data['process'],
                'hwnd': data['hwnd'],
                'x': rect[0],
                'y': rect[1],
                'width': data['width'],
                'height': data['height'],
                'monitor': data['monitor']
            }
            
            # Mensaje de ayuda en lugar de vista previa (para evitar problemas con PIL)
            self.preview_image.setText(f"Ventana: {data['title']}\nDimensiones: {data['width']}x{data['height']}")
            self.preview_image.setStyleSheet("background-color: #007ACC; color: white; padding: 5px; border-radius: 3px;")
    
    def select_window(self):
        if self.selected_window:
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "No ha seleccionado ninguna ventana.")
    
    def accept(self):
        self.parent().set_target_window(self.selected_window)
        self.close()

class DebugConsole(QWidget):
    """Consola de depuración para probar errores y analizar el programa durante su ejecución"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Consola de Depuración")
        self.setGeometry(100, 100, 700, 500)  # Ventana más grande para mejor visibilidad
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Banner informativo
        info_label = QLabel("Consola de Depuración - Ingrese texto para cerrar la aplicación con feedback")
        info_label.setStyleSheet("""
            background-color: #2D2D30;
            color: #E0E0E0;
            font-weight: bold;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        """)
        layout.addWidget(info_label)
        
        # Área de texto para mostrar logs
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("""
            background-color: #1E1E1E;
            color: #D4D4D4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            border: 1px solid #3E3E3E;
        """)
        layout.addWidget(self.log_area)
        
        # Panel de comandos
        cmd_layout = QHBoxLayout()
        
        self.cmd_input = QLineEdit()
        self.cmd_input.setStyleSheet("""
            background-color: #3C3C3C;
            color: #E0E0E0;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            padding: 5px;
            border: 1px solid #555555;
        """)
        self.cmd_input.setPlaceholderText("Ingrese cualquier texto para cerrar la aplicación con su feedback")
        cmd_layout.addWidget(self.cmd_input)
        
        self.execute_btn = QPushButton("Ejecutar")
        self.execute_btn.setStyleSheet("""
            background-color: #0E639C;
            color: white;
            border: none;
            padding: 8px 12px;
            font-weight: bold;
        """)
        cmd_layout.addWidget(self.execute_btn)
        
        layout.addLayout(cmd_layout)
        
        # Panel de botones predefinidos para errores comunes
        buttons_layout = QHBoxLayout()
        
        self.error_btn = QPushButton("Error Simple")
        self.exception_btn = QPushButton("Excepción")
        self.crash_btn = QPushButton("Crash")
        self.memory_btn = QPushButton("Fuga de Memoria")
        
        buttons = [self.error_btn, self.exception_btn, self.crash_btn, self.memory_btn]
        for btn in buttons:
            btn.setStyleSheet("""
                background-color: #A72145;
                color: white;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
            """)
            buttons_layout.addWidget(btn)
        
        layout.addLayout(buttons_layout)
        
        # Panel de información del sistema
        info_group = QGroupBox("Información del Sistema")
        info_layout = QVBoxLayout(info_group)
        
        self.system_info = QTextEdit()
        self.system_info.setReadOnly(True)
        self.system_info.setStyleSheet("""
            background-color: #252526;
            color: #D4D4D4;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 12px;
            border: 1px solid #3E3E3E;
        """)
        info_layout.addWidget(self.system_info)
        
        layout.addWidget(info_group)
        
        # Conectar eventos
        self.execute_btn.clicked.connect(self.execute_command)
        self.error_btn.clicked.connect(lambda: self.simulate_error("Error simple de prueba"))
        self.exception_btn.clicked.connect(self.simulate_exception)
        self.crash_btn.clicked.connect(self.simulate_crash)
        self.memory_btn.clicked.connect(self.simulate_memory_leak)
        
        # Permitir enviar feedback con Enter
        self.cmd_input.returnPressed.connect(self.execute_command)
        
        # Inicializar información del sistema
        self.update_system_info()
        
        # Handler para capturar logs
        self.log_handler = QTextEditLogger(self.log_area)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(self.log_handler)
        
        # Mostrar instrucciones iniciales
        self.log_area.append("==== CONSOLA DE DEPURACIÓN ====")
        self.log_area.append("Esta consola es una herramienta para depuración y pruebas.")
        self.log_area.append("Puede ingresar cualquier texto para cerrar la aplicación con ese feedback.")
        self.log_area.append("\nErrores detectados durante la ejecución:")
        
    def execute_command(self):
        """Ejecuta un comando ingresado por el usuario"""
        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
            
        self.log_area.append(f"> {cmd}")
        
        # Interpretar el comando
        if cmd.startswith("error "):
            msg = cmd[6:] or "Error personalizado de prueba"
            self.simulate_error(msg)
        elif cmd.startswith("exception "):
            msg = cmd[10:] or "Excepción personalizada de prueba"
            self.simulate_exception(msg)
        elif cmd == "crash":
            self.simulate_crash()
        elif cmd == "memory":
            self.simulate_memory_leak()
        elif cmd == "clear":
            self.log_area.clear()
        elif cmd == "info":
            self.update_system_info()
        elif cmd.startswith("cerrar ") or cmd.startswith("feedback "):
            # Nuevo comando para cerrar con feedback personalizado
            if cmd.startswith("cerrar "):
                msg = cmd[7:]
            else:
                msg = cmd[9:]
            self.close_with_feedback(msg)
        else:
            # Si no es un comando conocido, tratarlo como feedback para cerrar la aplicación
            self.log_area.append(f"Cerrando aplicación con feedback: {cmd}")
            self.close_with_feedback(cmd)
            
        self.cmd_input.clear()
        
    def close_with_feedback(self, msg):
        """Cierra la aplicación con un mensaje de feedback personalizado"""
        if not msg:
            msg = "Cierre solicitado desde la consola de depuración."
            
        reply = QMessageBox.question(
            self,
            "Confirmar Cierre con Feedback",
            f"¿Está seguro de que desea cerrar la aplicación con el siguiente feedback?\n\n\"{msg}\"",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.critical(f"FEEDBACK DEL USUARIO: {msg}")
            print(f"\n[FEEDBACK DEL USUARIO] {msg}\n")
            # Mostrar mensaje final
            QMessageBox.critical(None, "Cierre por Feedback", f"La aplicación se cerrará con el siguiente feedback:\n\n{msg}")
            sys.exit(1)
        
    def simulate_error(self, msg="Error de prueba"):
        """Simula un error simple y lo registra"""
        logger.error(msg)
        self.log_area.append(f"ERROR: {msg}")
        QMessageBox.critical(self, "Error", msg)
        
    def simulate_exception(self, msg="Excepción de prueba"):
        """Simula una excepción"""
        try:
            raise Exception(msg)
        except Exception as e:
            logger.exception(f"Excepción: {str(e)}")
            self.log_area.append(f"EXCEPCIÓN: {str(e)}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Excepción", f"{str(e)}\n\n{traceback.format_exc()}")
            
    def simulate_crash(self):
        """Simula un crash de la aplicación"""
        reply = QMessageBox.question(
            self,
            "Confirmar Crash",
            "¿Está seguro de que desea simular un crash? Esto cerrará la aplicación inmediatamente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.critical("¡CRASH SIMULADO! La aplicación se cerrará ahora.")
            sys.exit(1)
            
    def simulate_memory_leak(self):
        """Simula una fuga de memoria controlada (solo para pruebas)"""
        try:
            # Este código crea una lista grande en memoria
            # ¡NO ejecutar esto en producción!
            leak_size = 100 * 1024 * 1024  # ~100MB
            logger.warning(f"Simulando fuga de memoria de aproximadamente {leak_size/1024/1024:.2f} MB")
            self.log_area.append(f"Creando lista grande en memoria ({leak_size/1024/1024:.2f} MB)...")
            
            # Crear una referencia global para evitar que el GC lo limpie
            global _memory_leak_test
            _memory_leak_test = [0] * leak_size
            
            self.log_area.append("Fuga de memoria simulada completada")
            QMessageBox.warning(self, "Fuga de Memoria", f"Se ha simulado una fuga de memoria de aproximadamente {leak_size/1024/1024:.2f} MB")
        except Exception as e:
            logger.exception(f"Error al simular fuga de memoria: {str(e)}")
            
    def update_system_info(self):
        """Actualiza la información del sistema"""
        try:
            import platform
            
            # Información básica del sistema que no requiere psutil
            system_info = f"Sistema: {platform.system()} {platform.release()}\n"
            system_info += f"Versión de Python: {platform.python_version()}\n"
            system_info += f"Procesador: {platform.processor()}\n\n"
            
            # Información que requiere psutil
            try:
                import psutil
                
                # Información de memoria
                mem = psutil.virtual_memory()
                system_info += f"Memoria Total: {mem.total/1024/1024/1024:.2f} GB\n"
                system_info += f"Memoria Disponible: {mem.available/1024/1024/1024:.2f} GB\n"
                system_info += f"Memoria Usada: {mem.used/1024/1024/1024:.2f} GB ({mem.percent}%)\n\n"
                
                # Información del proceso actual
                process = psutil.Process()
                process_info = process.memory_info()
                system_info += f"Proceso actual (PID {process.pid}):\n"
                system_info += f"  Memoria RSS: {process_info.rss/1024/1024:.2f} MB\n"
                system_info += f"  Memoria VMS: {process_info.vms/1024/1024:.2f} MB\n"
                system_info += f"  CPU: {process.cpu_percent()}%\n"
            except ImportError:
                system_info += "Información detallada no disponible. Instale psutil:\n"
                system_info += "pip install psutil\n\n"
                system_info += "psutil es opcional y se usa solo para mostrar\n"
                system_info += "información detallada del sistema."
            
            self.system_info.setText(system_info)
        except Exception as e:
            self.system_info.setText(f"Error al obtener información del sistema: {str(e)}")

class QTextEditLogger(logging.Handler):
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self.text_edit.setReadOnly(True)
        
        # Mejorar el formato para mayor claridad
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Limitar el buffer de log a 1000 líneas para evitar problemas de memoria
        self.max_lines = 1000
        
    def emit(self, record):
        msg = self.format(record)
        self.text_edit.append(msg)
        
        # Limitar cantidad de líneas para evitar consumo excesivo de memoria
        document = self.text_edit.document()
        if document.blockCount() > self.max_lines:
            cursor = self.text_edit.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor, 
                                document.blockCount() - self.max_lines)
            cursor.removeSelectedText()

def main():
    try:
        # Configurar manejo de excepciones
        def exception_hook(exctype, value, tb):
            logger.critical(f"Excepción no capturada: {exctype.__name__}: {value}")
            logger.critical("Traceback:", exc_info=(exctype, value, tb))
            sys.__excepthook__(exctype, value, tb)
        
        sys.excepthook = exception_hook
        
        # Iniciar la aplicación con configuraciones básicas
        # Nota: Eliminamos las configuraciones que causaban problemas
        app = QApplication(sys.argv)
        app.setStyle("Fusion")  # Estilo consistente en todas las plataformas
        
        # Crear y mostrar la ventana principal
        logger.debug("Iniciando aplicación...")
        window = AutoClickerApp()
        window.show()
        
        # Iniciar el bucle de eventos
        exit_code = app.exec()
        
        # Limpiar recursos antes de salir
        if hasattr(thread_pool, 'shutdown'):
            thread_pool.shutdown(wait=False)
            
        logger.debug(f"Aplicación finalizando con código: {exit_code}")
        return exit_code
        
    except Exception as e:
        # Capturar cualquier excepción durante la inicialización
        print(f"Error crítico al iniciar la aplicación: {str(e)}")
        logger.critical(f"Error crítico al iniciar la aplicación: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())