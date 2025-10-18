from PySide6.QtWidgets import (QLabel, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                                 QLineEdit, QSlider, QDialogButtonBox, QGraphicsView,
                                 QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem,
                                 QGraphicsItem)
from PySide6.QtGui import QIntValidator, QPen, QBrush, QColor, QPixmap
from PySide6.QtCore import Qt, Signal, QRectF, QPointF

class ClickableLabel(QLabel):
    clicked = Signal(str)

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path

    def mousePressEvent(self, event):
        self.clicked.emit(self.image_path)

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.min_res_input = QLineEdit(str(settings["min_resolution"]))
        self.min_res_input.setValidator(QIntValidator(0, 9999))
        form_layout.addRow("Minimum Resolution:", self.min_res_input)

        self.min_aspect_input = QLineEdit(str(settings["min_aspect_ratio"]))
        form_layout.addRow("Min Aspect Ratio (e.g., 0.5):", self.min_aspect_input)

        self.max_aspect_input = QLineEdit(str(settings["max_aspect_ratio"]))
        form_layout.addRow("Max Aspect Ratio (e.g., 2.0):", self.max_aspect_input)

        self.blur_slider = QSlider(Qt.Horizontal)
        self.blur_slider.setRange(0, 200)
        self.blur_slider.setValue(settings["blur_threshold"])
        self.blur_label = QLabel(f'{settings["blur_threshold"]}')
        self.blur_slider.valueChanged.connect(lambda v: self.blur_label.setText(str(v)))

        blur_layout = QHBoxLayout()
        blur_layout.addWidget(self.blur_slider)
        blur_layout.addWidget(self.blur_label)
        form_layout.addRow("Blurriness Threshold:", blur_layout)

        self.layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_settings(self):
        return {
            "min_resolution": int(self.min_res_input.text()),
            "min_aspect_ratio": float(self.min_aspect_input.text()),
            "max_aspect_ratio": float(self.max_aspect_input.text()),
            "blur_threshold": self.blur_slider.value()
        }

class CropRectItem(QGraphicsRectItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.handle_size = 10.0
        self.handles = {}
        self.selected_handle = None
        self.mouse_press_pos = None
        self.mouse_press_rect = None
        self.updateHandlesPos()

    def handleAt(self, point):
        for handle, rect in self.handles.items():
            if rect.contains(point):
                return handle
        return None

    def hoverMoveEvent(self, event):
        handle = self.handleAt(event.pos())
        if handle:
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self.selected_handle = self.handleAt(event.pos())
        if self.selected_handle:
            self.mouse_press_pos = event.pos()
            self.mouse_press_rect = self.rect()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selected_handle:
            self.interactiveResize(event.pos())
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.selected_handle = None
        super().mouseReleaseEvent(event)

    def updateHandlesPos(self):
        s = self.handle_size
        r = self.rect()
        self.handles[Qt.TopLeftCorner] = QRectF(r.left(), r.top(), s, s)
        self.handles[Qt.TopRightCorner] = QRectF(r.right() - s, r.top(), s, s)
        self.handles[Qt.BottomLeftCorner] = QRectF(r.left(), r.bottom() - s, s, s)
        self.handles[Qt.BottomRightCorner] = QRectF(r.right() - s, r.bottom() - s, s, s)

    def interactiveResize(self, mouse_pos):
        rect = self.rect()
        diff = mouse_pos - self.mouse_press_pos

        self.prepareGeometryChange()

        if self.selected_handle == Qt.TopLeftCorner:
            rect.setTopLeft(self.mouse_press_rect.topLeft() + diff)
        elif self.selected_handle == Qt.TopRightCorner:
            rect.setTopRight(self.mouse_press_rect.topRight() + diff)
        elif self.selected_handle == Qt.BottomLeftCorner:
            rect.setBottomLeft(self.mouse_press_rect.bottomLeft() + diff)
        elif self.selected_handle == Qt.BottomRightCorner:
            rect.setBottomRight(self.mouse_press_rect.bottomRight() + diff)

        self.setRect(rect)
        self.updateHandlesPos()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setRenderHint(painter.Antialiasing)
        painter.setBrush(QBrush(QColor(0, 255, 0, 100)))
        painter.setPen(QPen(QColor(0, 0, 0), 1.0, Qt.SolidLine))
        for handle, rect in self.handles.items():
            painter.drawRect(rect)

class CropWidget(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        self.crop_rect = CropRectItem()
        self.crop_rect.setPen(QPen(QColor(0, 255, 0), 2))
        self.crop_rect.setBrush(QBrush(QColor(0, 255, 0, 50)))
        self.scene.addItem(self.crop_rect)

    def set_image(self, pixmap):
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())

    def set_crop_rect(self, rect):
        self.crop_rect.setRect(rect)

    def get_crop_rect(self):
        return self.crop_rect.rect()
