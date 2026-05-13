import sys
import json
import uuid
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QPushButton,
    QVBoxLayout, QHBoxLayout, QFileDialog, QScrollArea, QFrame, QLabel,
    QMenu, QGraphicsTextItem, QGraphicsItem, QGraphicsPathItem, QMessageBox,
    QMenuBar, QToolBar, QStatusBar, QSlider, QCheckBox, QComboBox,
    QGroupBox, QRadioButton, QButtonGroup, QColorDialog, QGraphicsDropShadowEffect,
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit
)
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QFont, QPainter, QLinearGradient, QAction,
    QPainterPath, QImage, QPixmap, QKeySequence, QShortcut, QTransform
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, QSettings, QLineF, QPoint


def exception_hook(exctype, value, tb):
    print(''.join(traceback.format_exception(exctype, value, tb)))
    sys.__excepthook__(exctype, value, tb)


sys.excepthook = exception_hook


class Port(QGraphicsEllipseItem):
    def __init__(self, parent, x, y, is_output=False, name=""):
        super().__init__(-6, -6, 12, 12, parent)
        self.setPos(x, y)
        self.is_output = is_output
        self.state = False
        self.id = str(uuid.uuid4())
        self.wires = []
        self.name = name
        self.parent_node = parent
        self.normal_color = QColor(100, 100, 120)
        self.active_color = QColor(80, 200, 80)
        self.hover_color = QColor(150, 150, 200)
        self.setBrush(QBrush(self.normal_color))
        self.setPen(QPen(QColor(50, 50, 70), 1.5))
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(2)
        if name:
            self.label = QGraphicsTextItem(name, parent)
            self.label.setDefaultTextColor(QColor(150, 150, 150))
            self.label.setFont(QFont("Arial", 7))
            self.label.setZValue(2)
            if is_output:
                self.label.setPos(x + 8, y - 5)
            else:
                self.label.setPos(x - 20, y - 5)

    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(self.hover_color))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(self.active_color if self.state else self.normal_color))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if self.is_output and self.scene():
            self.scene().start_wire(self)
        super().mousePressEvent(event)

    def set_state(self, state):
        self.state = state
        self.setBrush(QBrush(self.active_color if state else self.normal_color))
        if hasattr(self, 'label'):
            self.label.setDefaultTextColor(QColor(200, 200, 100) if state else QColor(150, 150, 150))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "is_output": self.is_output,
            "x": self.x(),
            "y": self.y()
        }


class Wire(QGraphicsLineItem):
    def __init__(self, out_port, in_port=None):
        super().__init__()
        self.out_port = out_port
        self.in_port = in_port
        self.id = str(uuid.uuid4())
        self.setPen(QPen(QColor(120, 120, 140), 2))
        self.setZValue(0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_pos()

    def update_pos(self, mouse_pos=None):
        try:
            if not self.out_port or self.out_port.scene() is None:
                return
            p1 = self.out_port.scenePos()
            if self.in_port and self.in_port.scene() is not None:
                p2 = self.in_port.scenePos()
            elif mouse_pos:
                p2 = mouse_pos
            else:
                return
            self.setLine(p1.x(), p1.y(), p2.x(), p2.y())
        except (RuntimeError, AttributeError):
            pass

    def finalize(self, in_port):
        self.in_port = in_port
        if self not in self.out_port.wires:
            self.out_port.wires.append(self)
        if self not in self.in_port.wires:
            self.in_port.wires.append(self)
        self.update_pos()

    def propagate(self):
        if self.in_port and self.out_port:
            self.in_port.set_state(self.out_port.state)
            color = QColor(255, 80, 80) if self.out_port.state else QColor(120, 120, 140)
            self.setPen(QPen(color, 2.5))

    def remove(self):
        try:
            if self.out_port and self in self.out_port.wires:
                self.out_port.wires.remove(self)
            if self.in_port:
                if self in self.in_port.wires:
                    self.in_port.wires.remove(self)
                if not self.in_port.wires:
                    self.in_port.set_state(False)
            if self.scene():
                self.scene().removeItem(self)
        except (RuntimeError, AttributeError):
            pass


class ShapeNode(QGraphicsPathItem):
    def __init__(self, x, y, width, height, node_type, color=QColor(60, 60, 80)):
        super().__init__()
        self.setPos(x, y)
        self.type = node_type
        self.id = str(uuid.uuid4())
        self.ports = []
        self.width = width
        self.height = height
        self.node_color = color
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)
        self.setCacheMode(QGraphicsItem.CacheMode.NoCache)
        self.create_shape()
        self.add_shadow()
        self.title_text = QGraphicsTextItem(node_type, self)
        self.title_text.setDefaultTextColor(QColor(200, 200, 220))
        self.title_text.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.title_text.setPos(width / 2 - self.title_text.boundingRect().width() / 2, height - 18)
        self.title_text.setZValue(2)

    def create_shape(self):
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 8, 8)
        self.setPath(path)
        self.update_gradient()

    def update_gradient(self):
        gradient = QLinearGradient(0, 0, 0, self.height)
        gradient.setColorAt(0, self.node_color.lighter(120))
        gradient.setColorAt(1, self.node_color.darker(110))
        self.setBrush(QBrush(gradient))
        if self.isSelected():
            self.setPen(QPen(QColor(80, 160, 255), 2.5))
        else:
            self.setPen(QPen(QColor(100, 100, 130), 1.5))

    def add_shadow(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setOffset(3, 3)
        shadow.setColor(QColor(0, 0, 0, 100))
        self.setGraphicsEffect(shadow)

    def remove_shadow(self):
        self.setGraphicsEffect(None)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.ports:
                for wire in port.wires[:]:
                    try:
                        if wire.scene() is not None:
                            wire.update_pos()
                    except (RuntimeError, AttributeError):
                        pass
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update_gradient()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        self.show_properties()

    def show_properties(self):
        dialog = QDialog()
        dialog.setWindowTitle(f"Свойства - {self.type}")
        dialog.setStyleSheet("""
            QDialog { background-color: #2a2a2e; color: white; }
            QLabel { color: white; }
            QLineEdit, QSpinBox, QDoubleSpinBox { background-color: #3a3a40; color: white; border: 1px solid #4a4a50; padding: 3px; }
            QDialogButtonBox QPushButton { background-color: #3a3a40; color: white; border: none; padding: 5px 15px; border-radius: 3px; }
            QDialogButtonBox QPushButton:hover { background-color: #4a9eff; }
        """)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        name_edit = QLineEdit(self.type)
        form.addRow("Название:", name_edit)
        x_spin = QDoubleSpinBox()
        x_spin.setRange(0, 3000)
        x_spin.setValue(self.x())
        form.addRow("X:", x_spin)
        y_spin = QDoubleSpinBox()
        y_spin.setRange(0, 2000)
        y_spin.setValue(self.y())
        form.addRow("Y:", y_spin)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.type = name_edit.text()
            self.title_text.setPlainText(self.type)
            self.setPos(x_spin.value(), y_spin.value())
            self.title_text.setPos(self.width / 2 - self.title_text.boundingRect().width() / 2, self.height - 18)

    def add_port(self, port):
        self.ports.append(port)

    def get_port_by_id(self, port_id):
        for port in self.ports:
            if port.id == port_id:
                return port
        return None


class InputSwitch(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 70, "INPUT", QColor(60, 80, 60))
        self.state = False
        self.out = Port(self, 74, 35, True, "Q")
        self.add_port(self.out)
        self.button_rect = QGraphicsRectItem(5, 12, 40, 30, self)
        self.button_rect.setBrush(QBrush(QColor(80, 80, 100)))
        self.button_rect.setPen(QPen(QColor(120, 120, 140), 1.5))
        self.button_rect.setAcceptHoverEvents(True)
        self.button_rect.setZValue(2)
        self.button_text = QGraphicsTextItem("OFF", self)
        self.button_text.setDefaultTextColor(QColor(200, 200, 200))
        self.button_text.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        self.button_text.setPos(10, 18)
        self.button_text.setZValue(3)
        self.status_indicator = QGraphicsEllipseItem(52, 18, 10, 10, self)
        self.status_indicator.setBrush(QBrush(QColor(80, 80, 100)))
        self.status_indicator.setPen(QPen(QColor(120, 120, 140), 1))
        self.status_indicator.setZValue(2)
        self.status_text = QGraphicsTextItem("0", self)
        self.status_text.setDefaultTextColor(QColor(200, 200, 200))
        self.status_text.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.status_text.setPos(64, 16)
        self.status_text.setZValue(3)
        self.label = QGraphicsTextItem("Toggle", self)
        self.label.setDefaultTextColor(QColor(150, 150, 150))
        self.label.setFont(QFont("Arial", 7))
        self.label.setPos(15, 50)
        self.label.setZValue(2)

    def mousePressEvent(self, event):
        local_pos = self.mapFromScene(event.scenePos())
        if self.button_rect.contains(local_pos):
            self.toggle_state()
            event.accept()
            return
        super().mousePressEvent(event)

    def toggle_state(self):
        self.state = not self.state
        self.out.set_state(self.state)
        self.status_text.setPlainText("1" if self.state else "0")
        self.button_text.setPlainText("ON" if self.state else "OFF")
        if self.state:
            self.button_rect.setBrush(QBrush(QColor(100, 200, 100)))
            self.status_indicator.setBrush(QBrush(QColor(100, 255, 100)))
            self.node_color = QColor(80, 120, 80)
            self.button_text.setDefaultTextColor(QColor(0, 0, 0))
        else:
            self.button_rect.setBrush(QBrush(QColor(80, 80, 100)))
            self.status_indicator.setBrush(QBrush(QColor(80, 80, 100)))
            self.node_color = QColor(60, 80, 60)
            self.button_text.setDefaultTextColor(QColor(200, 200, 200))
        self.update_gradient()
        if self.scene():
            self.scene().update()

    def evaluate(self):
        pass


class ClockSource(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 90, "CLOCK", QColor(100, 80, 60))
        self.state = False
        self.enabled = False
        self.interval_ms = 10  # Интервал в миллисекундах (по умолчанию 10 мс)
        self.timer = QTimer()
        self.timer.timeout.connect(self.toggle_clock)
        self.out = Port(self, 74, 45, True, "OUT")
        self.add_port(self.out)

        # Кнопка включения/выключения
        self.button_rect = QGraphicsRectItem(5, 12, 70, 25, self)
        self.button_rect.setBrush(QBrush(QColor(80, 80, 100)))
        self.button_rect.setPen(QPen(QColor(120, 120, 140), 1.5))
        self.button_rect.setAcceptHoverEvents(True)
        self.button_rect.setZValue(2)
        self.button_text = QGraphicsTextItem("START", self)
        self.button_text.setDefaultTextColor(QColor(200, 200, 200))
        self.button_text.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.button_text.setPos(18, 18)
        self.button_text.setZValue(3)

        # Статус генератора
        self.status_indicator = QGraphicsEllipseItem(5, 45, 10, 10, self)
        self.status_indicator.setBrush(QBrush(QColor(80, 80, 100)))
        self.status_indicator.setPen(QPen(QColor(120, 120, 140), 1))
        self.status_indicator.setZValue(2)

        self.status_text = QGraphicsTextItem("STOP", self)
        self.status_text.setDefaultTextColor(QColor(200, 200, 200))
        self.status_text.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.status_text.setPos(18, 45)
        self.status_text.setZValue(3)

        self.value_text = QGraphicsTextItem("0", self)
        self.value_text.setDefaultTextColor(QColor(150, 150, 150))
        self.value_text.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.value_text.setPos(55, 42)
        self.value_text.setZValue(3)

        self.freq_label = QGraphicsTextItem(f"{self.interval_ms}ms", self)
        self.freq_label.setDefaultTextColor(QColor(150, 150, 150))
        self.freq_label.setFont(QFont("Arial", 7))
        self.freq_label.setPos(30, 72)
        self.freq_label.setZValue(2)

    def mousePressEvent(self, event):
        local_pos = self.mapFromScene(event.scenePos())
        if self.button_rect.contains(local_pos):
            self.toggle_enabled()
            event.accept()
            return
        super().mousePressEvent(event)

    def toggle_enabled(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.timer.start(self.interval_ms)
            self.button_text.setPlainText("STOP")
            self.button_rect.setBrush(QBrush(QColor(100, 200, 100)))
            self.status_text.setPlainText("RUN")
            self.status_indicator.setBrush(QBrush(QColor(100, 255, 100)))
        else:
            self.timer.stop()
            self.state = False
            self.out.set_state(False)
            self.value_text.setPlainText("0")
            self.button_text.setPlainText("START")
            self.button_rect.setBrush(QBrush(QColor(80, 80, 100)))
            self.status_text.setPlainText("STOP")
            self.status_indicator.setBrush(QBrush(QColor(80, 80, 100)))
        self.update_gradient()

    def toggle_clock(self):
        if self.enabled:
            self.state = not self.state
            self.out.set_state(self.state)
            self.value_text.setPlainText("1" if self.state else "0")
            self.node_color = QColor(130, 100, 80) if self.state else QColor(100, 80, 60)
            self.update_gradient()

    def evaluate(self):
        pass

    def set_interval_ms(self, interval_ms):
        """Установка интервала в миллисекундах (от 5 до 1000 мс)"""
        self.interval_ms = max(5, min(1000, interval_ms))
        self.freq_label.setPlainText(f"{self.interval_ms}ms")
        # Если генератор запущен, перезапускаем таймер с новым интервалом
        if self.enabled:
            self.timer.stop()
            self.timer.start(self.interval_ms)

    def show_properties(self):
        dialog = QDialog()
        dialog.setWindowTitle(f"Свойства - {self.type}")
        dialog.setStyleSheet("""
            QDialog { background-color: #2a2a2e; color: white; }
            QLabel { color: white; }
            QLineEdit, QSpinBox, QDoubleSpinBox { background-color: #3a3a40; color: white; border: 1px solid #4a4a50; padding: 3px; }
            QDialogButtonBox QPushButton { background-color: #3a3a40; color: white; border: none; padding: 5px 15px; border-radius: 3px; }
            QDialogButtonBox QPushButton:hover { background-color: #4a9eff; }
        """)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        name_edit = QLineEdit(self.type)
        form.addRow("Название:", name_edit)

        # Настройка интервала в миллисекундах (5-1000 мс)
        interval_spin = QSpinBox()
        interval_spin.setRange(5, 1000)
        interval_spin.setSingleStep(5)
        interval_spin.setValue(self.interval_ms)
        interval_spin.setSuffix(" мс")
        form.addRow("Время тика (мс):", interval_spin)

        x_spin = QDoubleSpinBox()
        x_spin.setRange(0, 3000)
        x_spin.setValue(self.x())
        form.addRow("X:", x_spin)

        y_spin = QDoubleSpinBox()
        y_spin.setRange(0, 2000)
        y_spin.setValue(self.y())
        form.addRow("Y:", y_spin)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.type = name_edit.text()
            self.title_text.setPlainText(self.type)
            self.set_interval_ms(interval_spin.value())
            self.setPos(x_spin.value(), y_spin.value())
            self.title_text.setPos(self.width / 2 - self.title_text.boundingRect().width() / 2, self.height - 18)


class AndGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 60, "AND", QColor(70, 80, 120))
        self.create_gate_shape()
        self.in_a = Port(self, 0, 15, False, "A")
        self.in_b = Port(self, 0, 45, False, "B")
        self.out = Port(self, 80, 30, True, "Q")
        self.add_port(self.in_a)
        self.add_port(self.in_b)
        self.add_port(self.out)

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.lineTo(w - h / 2, 0)
        path.quadTo(w, h / 2, w - h / 2, h)
        path.lineTo(0, h)
        path.closeSubpath()
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(self.in_a.state and self.in_b.state)
        self.node_color = QColor(100, 130, 100) if self.out.state else QColor(70, 80, 120)
        self.update_gradient()


class OrGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 60, "OR", QColor(120, 70, 70))
        self.create_gate_shape()
        self.in_a = Port(self, 0, 15, False, "A")
        self.in_b = Port(self, 0, 45, False, "B")
        self.out = Port(self, 80, 30, True, "Q")
        self.add_port(self.in_a)
        self.add_port(self.in_b)
        self.add_port(self.out)

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.quadTo(w * 0.4, h * 0.3, w, h / 2)
        path.quadTo(w * 0.4, h * 0.7, 0, h)
        path.quadTo(h / 3, h / 2, 0, 0)
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(self.in_a.state or self.in_b.state)
        self.node_color = QColor(130, 100, 100) if self.out.state else QColor(120, 70, 70)
        self.update_gradient()


class NotGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 70, 50, "NOT", QColor(100, 100, 70))
        self.create_gate_shape()
        self.in_port = Port(self, 0, 25, False, "A")
        self.out = Port(self, 62, 25, True, "Q")
        self.add_port(self.in_port)
        self.add_port(self.out)
        self.bubble = QGraphicsEllipseItem(58, 21, 8, 8, self)
        self.bubble.setBrush(QBrush(QColor(100, 100, 70)))
        self.bubble.setPen(QPen(QColor(100, 100, 130), 1))

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.lineTo(w - 8, h / 2)
        path.lineTo(0, h)
        path.closeSubpath()
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(not self.in_port.state)
        self.node_color = QColor(100, 100, 100) if self.out.state else QColor(100, 100, 70)
        self.update_gradient()


class NandGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 60, "NAND", QColor(80, 80, 100))
        self.create_gate_shape()
        self.in_a = Port(self, 0, 15, False, "A")
        self.in_b = Port(self, 0, 45, False, "B")
        self.out = Port(self, 80, 30, True, "Q")
        self.add_port(self.in_a)
        self.add_port(self.in_b)
        self.add_port(self.out)
        self.bubble = QGraphicsEllipseItem(76, 26, 8, 8, self)
        self.bubble.setBrush(QBrush(QColor(80, 80, 100)))
        self.bubble.setPen(QPen(QColor(100, 100, 130), 1))

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.lineTo(w - h / 2 - 4, 0)
        path.quadTo(w - 4, h / 2, w - h / 2 - 4, h)
        path.lineTo(0, h)
        path.closeSubpath()
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(not (self.in_a.state and self.in_b.state))
        self.node_color = QColor(100, 130, 100) if self.out.state else QColor(80, 80, 100)
        self.update_gradient()


class NorGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 60, "NOR", QColor(100, 70, 70))
        self.create_gate_shape()
        self.in_a = Port(self, 0, 15, False, "A")
        self.in_b = Port(self, 0, 45, False, "B")
        self.out = Port(self, 80, 30, True, "Q")
        self.add_port(self.in_a)
        self.add_port(self.in_b)
        self.add_port(self.out)
        self.bubble = QGraphicsEllipseItem(76, 26, 8, 8, self)
        self.bubble.setBrush(QBrush(QColor(100, 70, 70)))
        self.bubble.setPen(QPen(QColor(100, 100, 130), 1))

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.quadTo(w * 0.4, h * 0.3, w - 4, h / 2)
        path.quadTo(w * 0.4, h * 0.7, 0, h)
        path.quadTo(h / 3, h / 2, 0, 0)
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(not (self.in_a.state or self.in_b.state))
        self.node_color = QColor(130, 100, 100) if self.out.state else QColor(100, 70, 70)
        self.update_gradient()


class XorGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 60, "XOR", QColor(70, 100, 100))
        self.create_gate_shape()
        self.in_a = Port(self, 0, 15, False, "A")
        self.in_b = Port(self, 0, 45, False, "B")
        self.out = Port(self, 80, 30, True, "Q")
        self.add_port(self.in_a)
        self.add_port(self.in_b)
        self.add_port(self.out)

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.quadTo(w * 0.3, h * 0.3, w * 0.7, h / 2)
        path.quadTo(w * 0.3, h * 0.7, 0, h)
        path.quadTo(h / 3, h / 2, 0, 0)
        path2 = QPainterPath()
        path2.moveTo(w * 0.15, 0)
        path2.quadTo(w * 0.5, h / 2, w * 0.15, h)
        path.addPath(path2)
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(self.in_a.state != self.in_b.state)
        self.node_color = QColor(100, 130, 130) if self.out.state else QColor(70, 100, 100)
        self.update_gradient()


class BufferGate(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 70, 50, "BUFFER", QColor(80, 80, 100))
        self.create_gate_shape()
        self.in_port = Port(self, 0, 25, False, "A")
        self.out = Port(self, 70, 25, True, "Q")
        self.add_port(self.in_port)
        self.add_port(self.out)

    def create_gate_shape(self):
        path = QPainterPath()
        w, h = self.width, self.height
        path.moveTo(0, 0)
        path.lineTo(w - 5, h / 2)
        path.lineTo(0, h)
        path.closeSubpath()
        self.setPath(path)

    def evaluate(self):
        self.out.set_state(self.in_port.state)
        self.node_color = QColor(100, 130, 100) if self.out.state else QColor(80, 80, 100)
        self.update_gradient()


class LedOutput(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 60, 70, "LED", QColor(60, 60, 80))
        self.input = Port(self, 0, 35, False, "IN")
        self.add_port(self.input)
        self.led = QGraphicsEllipseItem(12, 12, 36, 36, self)
        self.led.setBrush(QBrush(QColor(40, 40, 60)))
        self.led.setPen(QPen(QColor(100, 100, 130), 2))
        self.led.setZValue(2)
        self.reflection = QGraphicsEllipseItem(18, 16, 10, 10, self)
        self.reflection.setBrush(QBrush(QColor(255, 255, 255, 50)))
        self.reflection.setPen(QPen(Qt.PenStyle.NoPen))  # Исправлено: QPen() оборачивает NoPen
        self.reflection.setZValue(3)
        self.value_text = QGraphicsTextItem("0", self)
        self.value_text.setDefaultTextColor(QColor(150, 150, 150))
        self.value_text.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.value_text.setPos(24, 22)
        self.value_text.setZValue(4)

    def update_display(self):
        if self.input.state:
            self.led.setBrush(QBrush(QColor(255, 50, 50)))
            self.value_text.setPlainText("1")
            self.value_text.setDefaultTextColor(QColor(255, 255, 255))
        else:
            self.led.setBrush(QBrush(QColor(40, 40, 60)))
            self.value_text.setPlainText("0")
            self.value_text.setDefaultTextColor(QColor(150, 150, 150))

    def evaluate(self):
        self.update_display()


class SevenSegment(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 110, "7-SEG", QColor(50, 50, 70))
        self.inputs = []
        for i, name in enumerate(["A", "B", "C", "D"]):
            port = Port(self, 0, 15 + i * 20, False, name)
            self.inputs.append(port)
            self.add_port(port)
        self.segments = []
        self.draw_segments()
        self.digits = {
            0: [1, 1, 1, 1, 1, 1, 0], 1: [0, 1, 1, 0, 0, 0, 0],
            2: [1, 1, 0, 1, 1, 0, 1], 3: [1, 1, 1, 1, 0, 0, 1],
            4: [0, 1, 1, 0, 0, 1, 1], 5: [1, 0, 1, 1, 0, 1, 1],
            6: [1, 0, 1, 1, 1, 1, 1], 7: [1, 1, 1, 0, 0, 0, 0],
            8: [1, 1, 1, 1, 1, 1, 1], 9: [1, 1, 1, 1, 0, 1, 1]
        }

    def draw_segments(self):
        positions = [
            (20, 12, 40, 6), (55, 18, 6, 30), (55, 62, 6, 30),
            (20, 92, 40, 6), (10, 62, 6, 30), (10, 18, 6, 30),
            (20, 50, 40, 6),
        ]
        for x, y, w, h in positions:
            seg = QGraphicsRectItem(x, y, w, h, self)
            seg.setBrush(QBrush(QColor(40, 40, 60)))
            seg.setPen(QPen(QColor(80, 80, 100), 1))
            self.segments.append(seg)

    def evaluate(self):
        value = 0
        for i, port in enumerate(self.inputs[:4]):
            if port.state:
                value |= (1 << i)
        pattern = self.digits.get(value, [0, 0, 0, 0, 0, 0, 0])
        for seg, state in zip(self.segments, pattern):
            seg.setBrush(QBrush(QColor(255, 50, 50) if state else QColor(40, 40, 60)))


class RSLatch(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 90, 80, "RS LATCH", QColor(80, 70, 100))
        self.q_state = False
        self.s = Port(self, 0, 20, False, "S")
        self.r = Port(self, 0, 60, False, "R")
        self.q = Port(self, 90, 30, True, "Q")
        self.q_not = Port(self, 90, 55, True, "Q'")
        self.add_port(self.s)
        self.add_port(self.r)
        self.add_port(self.q)
        self.add_port(self.q_not)
        self.state_label = QGraphicsTextItem("Q=0", self)
        self.state_label.setDefaultTextColor(QColor(150, 150, 150))
        self.state_label.setFont(QFont("Arial", 8))
        self.state_label.setPos(35, 70)

    def evaluate(self):
        if self.s.state and not self.r.state:
            self.q_state = True
        elif self.r.state and not self.s.state:
            self.q_state = False
        self.q.set_state(self.q_state)
        self.q_not.set_state(not self.q_state)
        self.state_label.setPlainText(f"Q={1 if self.q_state else 0}")
        self.node_color = QColor(100, 100, 130) if self.q_state else QColor(80, 70, 100)
        self.update_gradient()


class DFlipFlop(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 90, 90, "D FLIP-FLOP", QColor(80, 70, 100))
        self.q_state = False
        self.last_clk = False
        self.d = Port(self, 0, 25, False, "D")
        self.clk = Port(self, 0, 50, False, "CLK")
        self.q = Port(self, 90, 30, True, "Q")
        self.q_not = Port(self, 90, 60, True, "Q'")
        self.add_port(self.d)
        self.add_port(self.clk)
        self.add_port(self.q)
        self.add_port(self.q_not)
        self.state_label = QGraphicsTextItem("Q=0", self)
        self.state_label.setDefaultTextColor(QColor(150, 150, 150))
        self.state_label.setFont(QFont("Arial", 8))
        self.state_label.setPos(35, 75)
        rect = QGraphicsRectItem(60, 40, 25, 25, self)
        rect.setPen(QPen(QColor(100, 100, 130), 1))
        rect.setBrush(QBrush(QColor(60, 60, 80)))

    def evaluate(self):
        if self.clk.state and not self.last_clk:
            self.q_state = self.d.state
        self.last_clk = self.clk.state
        self.q.set_state(self.q_state)
        self.q_not.set_state(not self.q_state)
        self.state_label.setPlainText(f"Q={1 if self.q_state else 0}")
        self.node_color = QColor(100, 100, 130) if self.q_state else QColor(80, 70, 100)
        self.update_gradient()


class JKFlipFlop(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 90, 100, "JK FLIP-FLOP", QColor(80, 70, 100))
        self.q_state = False
        self.last_clk = False
        self.j = Port(self, 0, 20, False, "J")
        self.clk = Port(self, 0, 50, False, "CLK")
        self.k = Port(self, 0, 80, False, "K")
        self.q = Port(self, 90, 35, True, "Q")
        self.q_not = Port(self, 90, 65, True, "Q'")
        self.add_port(self.j)
        self.add_port(self.clk)
        self.add_port(self.k)
        self.add_port(self.q)
        self.add_port(self.q_not)
        self.state_label = QGraphicsTextItem("Q=0", self)
        self.state_label.setDefaultTextColor(QColor(150, 150, 150))
        self.state_label.setFont(QFont("Arial", 8))
        self.state_label.setPos(35, 85)

    def evaluate(self):
        if self.clk.state and not self.last_clk:
            if self.j.state and self.k.state:
                self.q_state = not self.q_state
            elif self.j.state and not self.k.state:
                self.q_state = True
            elif not self.j.state and self.k.state:
                self.q_state = False
        self.last_clk = self.clk.state
        self.q.set_state(self.q_state)
        self.q_not.set_state(not self.q_state)
        self.state_label.setPlainText(f"Q={1 if self.q_state else 0}")
        self.node_color = QColor(100, 100, 130) if self.q_state else QColor(80, 70, 100)
        self.update_gradient()


class TFlipFlop(ShapeNode):
    def __init__(self, x, y):
        super().__init__(x, y, 80, 80, "T FLIP-FLOP", QColor(80, 70, 100))
        self.q_state = False
        self.last_clk = False
        self.t = Port(self, 0, 25, False, "T")
        self.clk = Port(self, 0, 55, False, "CLK")
        self.q = Port(self, 80, 30, True, "Q")
        self.q_not = Port(self, 80, 55, True, "Q'")
        self.add_port(self.t)
        self.add_port(self.clk)
        self.add_port(self.q)
        self.add_port(self.q_not)
        self.state_label = QGraphicsTextItem("Q=0", self)
        self.state_label.setDefaultTextColor(QColor(150, 150, 150))
        self.state_label.setFont(QFont("Arial", 8))
        self.state_label.setPos(30, 70)

    def evaluate(self):
        if self.clk.state and not self.last_clk:
            if self.t.state:
                self.q_state = not self.q_state
        self.last_clk = self.clk.state
        self.q.set_state(self.q_state)
        self.q_not.set_state(not self.q_state)
        self.state_label.setPlainText(f"Q={1 if self.q_state else 0}")
        self.node_color = QColor(100, 100, 130) if self.q_state else QColor(80, 70, 100)
        self.update_gradient()


class LogicScene(QGraphicsScene):
    def __init__(self):
        super().__init__(0, 0, 3000, 2000)
        self.temp_wire = None
        self.clipboard = None
        self.show_grid = True
        self.snap_to_grid = False
        self.setBackgroundBrush(QBrush(QColor(35, 35, 40)))
        self.draw_grid()
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 50
        self.eval_timer = QTimer()
        self.eval_timer.timeout.connect(self.evaluate_all)
        self.eval_timer.start(50)

    def draw_grid(self):
        if self.show_grid:
            pen = QPen(QColor(45, 45, 50), 0.5)
            for x in range(0, 3000, 50):
                line = self.addLine(x, 0, x, 2000, pen)
                line.setZValue(-10)
            for y in range(0, 2000, 50):
                line = self.addLine(0, y, 3000, y, pen)
                line.setZValue(-10)
            pen_bold = QPen(QColor(55, 55, 65), 0.8)
            for x in range(0, 3000, 250):
                line = self.addLine(x, 0, x, 2000, pen_bold)
                line.setZValue(-10)
            for y in range(0, 2000, 250):
                line = self.addLine(0, y, 3000, y, pen_bold)
                line.setZValue(-10)

    def draw_grid(self):
        # Мы не создаем линии как объекты, а переопределяем отрисовку фона
        self.update()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        if not self.show_grid:
            return

        painter.setPen(QPen(QColor(45, 45, 50), 0.5))
        left = int(rect.left()) - (int(rect.left()) % 50)
        top = int(rect.top()) - (int(rect.top()) % 50)

        lines = []
        for x in range(left, int(rect.right()), 50):
            lines.append(QLineF(x, rect.top(), x, rect.bottom()))
        for y in range(top, int(rect.bottom()), 50):
            lines.append(QLineF(rect.left(), y, rect.right(), y))

        painter.drawLines(lines)

        # Жирные линии каждые 250 пикселей
        painter.setPen(QPen(QColor(55, 55, 65), 0.8))
        bold_lines = []
        for x in range(left - (left % 250), int(rect.right()), 250):
            bold_lines.append(QLineF(x, rect.top(), x, rect.bottom()))
        for y in range(top - (top % 250), int(rect.bottom()), 250):
            bold_lines.append(QLineF(rect.left(), y, rect.right(), y))
        painter.drawLines(bold_lines)

    def toggle_grid(self, show):
        self.show_grid = show
        self.update()

    def start_wire(self, port):
        if self.temp_wire:
            self.removeItem(self.temp_wire)
        self.temp_wire = Wire(port)
        self.addItem(self.temp_wire)

    def mouseMoveEvent(self, event):
        if self.temp_wire and self.temp_wire.scene() is not None:
            self.temp_wire.update_pos(event.scenePos())
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if self.temp_wire:
            items = self.items(event.scenePos())
            for item in items:
                if isinstance(item, Port) and not item.is_output:
                    self.temp_wire.finalize(item)
                    self.temp_wire = None
                    self.save_state()
                    return
            if self.temp_wire and self.temp_wire.scene() is not None:
                self.removeItem(self.temp_wire)
            self.temp_wire = None
        super().mousePressEvent(event)

    def remove_node(self, node):
        try:
            self.save_state()
            for port in node.ports:
                for wire in list(port.wires):
                    wire.remove()
            if node.scene():
                self.removeItem(node)
            self.update()
        except Exception as e:
            print(f"Ошибка при удалении узла: {e}")

    def evaluate_all(self):
        nodes = []
        for item in self.items():
            if isinstance(item, ShapeNode) and hasattr(item, 'evaluate') and item.scene() is not None:
                nodes.append(item)
        for item in self.items():
            if isinstance(item, Port) and not item.is_output:
                if not item.wires:
                    item.set_state(False)

            if isinstance(item, Wire) and item.scene() is not None and item.in_port:
                try:
                    item.propagate()
                except:
                    pass
        for _ in range(20):
            changed = False
            for node in nodes:
                try:
                    if hasattr(node, 'out'):
                        old = node.out.state if node.out else None
                        node.evaluate()
                        if node.out and node.out.state != old:
                            changed = True
                    else:
                        node.evaluate()
                except Exception as e:
                    print(f"Ошибка при оценке узла {node.type}: {e}")
            if not changed:
                break
        for item in self.items():
            if isinstance(item, Wire) and item.scene() is not None and item.in_port:
                try:
                    item.propagate()
                except Exception as e:
                    print(f"Ошибка при обновлении провода: {e}")

    def save_state(self):
        data = self.serialize()
        self.undo_stack.append(data)
        self.redo_stack.clear()
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            current = self.serialize()
            self.redo_stack.append(current)
            last_state = self.undo_stack.pop()
            self.deserialize(last_state)

    def redo(self):
        if self.redo_stack:
            current = self.serialize()
            self.undo_stack.append(current)
            next_state = self.redo_stack.pop()
            self.deserialize(next_state)

    def serialize(self):
        data = {"nodes": [], "wires": [], "node_port_map": {}}
        for item in self.items():
            if isinstance(item, ShapeNode) and item.scene() is not None:
                ports_data = {}
                for port in item.ports:
                    ports_data[port.name] = port.id
                data["nodes"].append({
                    "id": item.id,
                    "type": item.type,
                    "x": item.x(),
                    "y": item.y(),
                    "ports": ports_data
                })
                data["node_port_map"][item.id] = ports_data
        for item in self.items():
            if isinstance(item, Wire) and item.in_port and item.scene() is not None:
                data["wires"].append({
                    "from_node": item.out_port.parent_node.id,
                    "from_port": item.out_port.name,
                    "to_node": item.in_port.parent_node.id,
                    "to_port": item.in_port.name
                })
        for item in self.items():
            if isinstance(item, InputSwitch) and item.scene() is not None:
                data["input_states"] = data.get("input_states", {})
                data["input_states"][item.id] = item.state
        return data

    def deserialize(self, data):
        self.clear()
        self.draw_grid()
        node_classes = {
            "AND": AndGate, "OR": OrGate, "NOT": NotGate,
            "NAND": NandGate, "NOR": NorGate, "XOR": XorGate,
            "BUFFER": BufferGate, "INPUT": InputSwitch, "LED": LedOutput,
            "7-SEG": SevenSegment, "RS LATCH": RSLatch, "CLOCK": ClockSource,
            "D FLIP-FLOP": DFlipFlop, "JK FLIP-FLOP": JKFlipFlop, "T FLIP-FLOP": TFlipFlop
        }
        nodes_map = {}
        for node_data in data["nodes"]:
            if node_data["type"] in node_classes:
                try:
                    node = node_classes[node_data["type"]](node_data["x"], node_data["y"])
                    node.id = node_data["id"]
                    node.type = node_data["type"]
                    node.title_text.setPlainText(node.type)
                    if isinstance(node, InputSwitch) and "input_states" in data:
                        if node.id in data["input_states"]:
                            if data["input_states"][node.id] != node.state:
                                node.toggle_state()
                    self.addItem(node)
                    nodes_map[node.id] = node
                except Exception as e:
                    print(f"Ошибка загрузки узла {node_data['type']}: {e}")
        for wire_data in data["wires"]:
            from_node = nodes_map.get(wire_data["from_node"])
            to_node = nodes_map.get(wire_data["to_node"])
            if from_node and to_node:
                out_port = None
                in_port = None
                for port in from_node.ports:
                    if port.name == wire_data["from_port"] and port.is_output:
                        out_port = port
                for port in to_node.ports:
                    if port.name == wire_data["to_port"] and not port.is_output:
                        in_port = port
                if out_port and in_port:
                    wire = Wire(out_port, in_port)
                    self.addItem(wire)

    def save(self, path):
        data = self.serialize()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.deserialize(data)

    def export_image(self, path):
        rect = self.itemsBoundingRect()
        image = QImage(rect.size().toSize(), QImage.Format.Format_ARGB32)
        image.fill(QColor(35, 35, 40))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.render(painter)
        painter.end()
        image.save(path)


class ToolPanel(QFrame):
    def __init__(self, scene, main_window):
        super().__init__()
        self.scene = scene
        self.main_window = main_window
        self.setFixedWidth(240)
        self.setStyleSheet("""
            QFrame { background-color: #252528; border-right: 1px solid #3a3a40; }
            QPushButton { background-color: #3a3a40; color: white; border: none; padding: 8px; margin: 3px; border-radius: 5px; font-size: 11px; text-align: left; }
            QPushButton:hover { background-color: #4a9eff; }
            QPushButton:pressed { background-color: #2a6eff; }
            QLabel { color: #4a9eff; padding: 5px; font-weight: bold; font-size: 11px; }
            QScrollArea { border: none; }
            QGroupBox { color: #aaa; border: 1px solid #3a3a40; border-radius: 5px; margin-top: 10px; font-size: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; }
            QCheckBox { color: white; }
        """)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(5, 10, 5, 10)
        layout.setSpacing(5)
        title = QLabel("🎛 LOGIC DESIGNER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a9eff;")
        layout.addWidget(title)
        layout.addWidget(self.make_sep())
        categories = [
            ("📥 ВХОДЫ", [("🔘 Переключатель", InputSwitch), ("⏰ Тактовый генератор", ClockSource)]),
            ("🎮 ЛОГИКА", [("AND (И)", AndGate), ("OR (ИЛИ)", OrGate), ("NOT (НЕ)", NotGate),
                          ("NAND (И-НЕ)", NandGate), ("NOR (ИЛИ-НЕ)", NorGate),
                          ("XOR", XorGate), ("BUFFER", BufferGate)]),
            ("💾 ПАМЯТЬ", [("RS Триггер", RSLatch), ("D Триггер", DFlipFlop),
                          ("JK Триггер", JKFlipFlop), ("T Триггер", TFlipFlop)]),
            ("📤 ВЫХОДЫ", [("💡 Светодиод", LedOutput), ("🔢 7-Сегментный", SevenSegment)]),
        ]
        for cat_name, items in categories:
            label = QLabel(cat_name)
            label.setStyleSheet("color: #00bcd4; margin-top: 10px; font-size: 10px;")
            layout.addWidget(label)
            for name, node_class in items:
                btn = QPushButton(f"  {name}")
                btn.clicked.connect(lambda checked, c=node_class: self.add_node(c))
                layout.addWidget(btn)
        layout.addStretch()
        layout.addWidget(self.make_sep())

        file_group = QGroupBox("Файл")
        file_layout = QVBoxLayout(file_group)
        for name, action in [("💾 Сохранить", "save"), ("📂 Загрузить", "load"), ("📸 Экспорт PNG", "export")]:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, a=action: self.do_action(a))
            file_layout.addWidget(btn)
        layout.addWidget(file_group)
        edit_group = QGroupBox("Редактирование")
        edit_layout = QVBoxLayout(edit_group)
        del_btn = QPushButton("🗑 Удалить (Del)")
        del_btn.clicked.connect(lambda: self.do_action("del"))
        edit_layout.addWidget(del_btn)
        clear_btn = QPushButton("🧹 Очистить всё")
        clear_btn.clicked.connect(lambda: self.do_action("clear"))
        edit_layout.addWidget(clear_btn)
        layout.addWidget(edit_group)
        scroll.setWidget(content)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll)
        hint = QLabel("💡 Подсказки:\n• Выход → Вход\n• Двойной клик - свойства\n• Ctrl+Z - отменить\n• Ctrl+колёсико - масштаб")
        hint.setStyleSheet("color: #666; font-size: 9px; margin-top: 5px;")
        hint.setWordWrap(True)
        main_layout.addWidget(hint)

    def make_sep(self):
        sep = QLabel("────────────────")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("color: #444; font-size: 10px;")
        return sep

    def add_node(self, node_class):
        view = self.scene.views()[0] if self.scene.views() else None
        if view:
            center = view.mapToScene(view.viewport().rect().center())
            x, y = center.x() - 40, center.y() - 30
        else:
            x, y = 300, 200
        node = node_class(x, y)
        self.scene.addItem(node)
        self.scene.save_state()

    def toggle_grid(self, state):
        self.scene.toggle_grid(state == Qt.CheckState.Checked.value)

    def toggle_snap(self, state):
        self.scene.snap_to_grid = state == Qt.CheckState.Checked.value

    def toggle_shadow(self, state):
        for item in self.scene.items():
            if isinstance(item, ShapeNode):
                if state == Qt.CheckState.Checked.value:
                    item.add_shadow()
                else:
                    item.remove_shadow()

    def do_action(self, action):
        if action == "del":
            for item in self.scene.selectedItems():
                if isinstance(item, ShapeNode):
                    self.scene.remove_node(item)
                elif isinstance(item, Wire):
                    item.remove()
            self.scene.save_state()
        elif action == "clear":
            reply = QMessageBox.question(self, "Очистка", "Очистить всю схему?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.scene.clear()
                self.scene.draw_grid()
                self.scene.save_state()
        elif action == "save":
            path, _ = QFileDialog.getSaveFileName(self, "Сохранить схему", "", "JSON (*.json)")
            if path:
                self.scene.save(path)
                QMessageBox.information(self, "Успех", "Схема сохранена!")
        elif action == "load":
            path, _ = QFileDialog.getOpenFileName(self, "Загрузить схему", "", "JSON (*.json)")
            if path:
                self.scene.load(path)
                QMessageBox.information(self, "Успех", "Схема загружена!")
        elif action == "export":
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт изображения", "", "PNG (*.png)")
            if path:
                self.scene.export_image(path)
                QMessageBox.information(self, "Успех", "Изображение сохранено!")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Logic Circuit Designer - Professional Edition")
        self.resize(1400, 800)
        self.scene = LogicScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Добавь это в __init__ после создания self.view
        self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.view.setInteractive(True)
        self.view.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.create_menu()
        self.create_toolbar()
        self.tool_panel = ToolPanel(self.scene, self)
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готов", 3000)
        self.view.setMouseTracking(True)
        self.view.viewport().installEventFilter(self)
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.tool_panel)
        layout.addWidget(self.view)
        self.setCentralWidget(central)
        self.setup_shortcuts()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.MouseMove and obj == self.view.viewport():
            pos = self.view.mapToScene(event.position().toPoint())
            self.statusBar.showMessage(f"Позиция: ({int(pos.x())}, {int(pos.y())})")
        return super().eventFilter(obj, event)

    def create_menu(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar { background-color: #2a2a2e; color: white; border-bottom: 1px solid #3a3a40; }
            QMenuBar::item { background-color: transparent; padding: 5px 10px; }
            QMenuBar::item:selected { background-color: #3a3a40; }
            QMenu { background-color: #2a2a2e; color: white; border: 1px solid #3a3a40; }
            QMenu::item { padding: 5px 25px; }
            QMenu::item:selected { background-color: #4a9eff; }
        """)
        file_menu = menubar.addMenu("Файл")
        new_action = QAction("📄 Новая схема", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_circuit)
        file_menu.addAction(new_action)
        file_menu.addSeparator()
        open_action = QAction("📂 Открыть...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(lambda: self.tool_panel.do_action("load"))
        file_menu.addAction(open_action)
        save_action = QAction("💾 Сохранить", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(lambda: self.tool_panel.do_action("save"))
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        export_action = QAction("📸 Экспорт в PNG...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(lambda: self.tool_panel.do_action("export"))
        file_menu.addAction(export_action)
        file_menu.addSeparator()
        exit_action = QAction("❌ Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        edit_menu = menubar.addMenu("Правка")
        undo_action = QAction("↩ Отменить", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(self.scene.undo)
        edit_menu.addAction(undo_action)
        redo_action = QAction("↪ Повторить", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(self.scene.redo)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        del_action = QAction("🗑 Удалить", self)
        del_action.setShortcut("Delete")
        del_action.triggered.connect(lambda: self.tool_panel.do_action("del"))
        edit_menu.addAction(del_action)
        edit_menu.addSeparator()
        select_all_action = QAction("✨ Выделить всё", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.select_all)
        edit_menu.addAction(select_all_action)
        view_menu = menubar.addMenu("Вид")
        zoom_in = QAction("🔍 Увеличить", self)
        zoom_in.setShortcut("Ctrl++")
        zoom_in.triggered.connect(lambda: self.view.scale(1.1, 1.1))
        view_menu.addAction(zoom_in)
        zoom_out = QAction("🔍 Уменьшить", self)
        zoom_out.setShortcut("Ctrl+-")
        zoom_out.triggered.connect(lambda: self.view.scale(0.9, 0.9))
        view_menu.addAction(zoom_out)
        zoom_fit = QAction("◻ Сбросить масштаб", self)
        zoom_fit.setShortcut("Ctrl+0")
        zoom_fit.triggered.connect(lambda: self.view.resetTransform())
        view_menu.addAction(zoom_fit)
        help_menu = menubar.addMenu("Помощь")
        about_action = QAction("ℹ О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        toolbar = QToolBar("Основная панель")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar { background-color: #2a2a2e; border: none; padding: 2px; }
            QToolButton { background-color: #3a3a40; color: white; border: none; padding: 5px; margin: 1px; border-radius: 3px; }
            QToolButton:hover { background-color: #4a9eff; }
        """)
        new_btn = QAction("📄", self)
        new_btn.setToolTip("Новая схема")
        new_btn.triggered.connect(self.new_circuit)
        toolbar.addAction(new_btn)
        open_btn = QAction("📂", self)
        open_btn.setToolTip("Открыть")
        open_btn.triggered.connect(lambda: self.tool_panel.do_action("load"))
        toolbar.addAction(open_btn)
        save_btn = QAction("💾", self)
        save_btn.setToolTip("Сохранить")
        save_btn.triggered.connect(lambda: self.tool_panel.do_action("save"))
        toolbar.addAction(save_btn)
        toolbar.addSeparator()
        undo_btn = QAction("↩", self)
        undo_btn.setToolTip("Отменить")
        undo_btn.triggered.connect(self.scene.undo)
        toolbar.addAction(undo_btn)
        redo_btn = QAction("↪", self)
        redo_btn.setToolTip("Повторить")
        redo_btn.triggered.connect(self.scene.redo)
        toolbar.addAction(redo_btn)
        toolbar.addSeparator()
        zoom_in_btn = QAction("🔍+", self)
        zoom_in_btn.setToolTip("Увеличить")
        zoom_in_btn.triggered.connect(lambda: self.view.scale(1.1, 1.1))
        toolbar.addAction(zoom_in_btn)
        zoom_out_btn = QAction("🔍-", self)
        zoom_out_btn.setToolTip("Уменьшить")
        zoom_out_btn.triggered.connect(lambda: self.view.scale(0.9, 0.9))
        toolbar.addAction(zoom_out_btn)
        zoom_fit_btn = QAction("◻", self)
        zoom_fit_btn.setToolTip("Сбросить масштаб")
        zoom_fit_btn.triggered.connect(lambda: self.view.resetTransform())
        toolbar.addAction(zoom_fit_btn)
        toolbar.addSeparator()
        delete_btn = QAction("🗑", self)
        delete_btn.setToolTip("Удалить")
        delete_btn.triggered.connect(lambda: self.tool_panel.do_action("del"))
        toolbar.addAction(delete_btn)
        self.addToolBar(toolbar)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Delete"), self).activated.connect(lambda: self.tool_panel.do_action("del"))
        QShortcut(QKeySequence("Backspace"), self).activated.connect(lambda: self.tool_panel.do_action("del"))

    def new_circuit(self):
        reply = QMessageBox.question(self, "Новая схема", "Создать новую схему? Все несохранённые изменения будут потеряны.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.scene.clear()
            self.scene.draw_grid()
            self.scene.save_state()

    def select_all(self):
        for item in self.scene.items():
            if isinstance(item, ShapeNode):
                item.setSelected(True)

    def show_about(self):
        QMessageBox.about(self, "О программе",
            "Симулятор Логических Схем - Professional Edition\n\nВерсия 1.0\n\nПрограмма для создания и симуляции логических схем.\n\nОсновные возможности:\n• Логические элементы (AND, OR, NOT, NAND, NOR, XOR, BUFFER)\n• Входные устройства (Переключатель, Тактовый генератор)\n• Выходные устройства (Светодиод, 7-сегментный индикатор)\n• Триггеры (RS, D, JK, T -триггеры)\n• Undo/Redo (Ctrl+Z/Ctrl+Y)\n• Сохранение/загрузка схем в JSON\n• Экспорт в PNG\n• Двойной клик для редактирования свойств\n\n© 2026 Rapid Racoons Original")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet("""
        QToolTip { background-color: #2a2a2e; color: white; border: 1px solid #3a3a40; }
        QMessageBox { background-color: #2a2a2e; color: white; }
        QMessageBox QLabel { color: white; }
    """)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())            