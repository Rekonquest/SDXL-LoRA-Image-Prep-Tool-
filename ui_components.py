
from pathlib import Path
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QSize, QRect, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QCursor
from PySide6.QtWidgets import QWidget, QListWidget, QListWidgetItem
from PIL import Image

class ThumbnailGallery(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setResizeMode(QListWidget.Adjust)
        self.setIconSize(QSize(180,180))
        self.setSpacing(8)
        self.setMovement(QListWidget.Static)
        self.setWordWrap(True)

    def populate(self, items: List[Dict]):
        self.clear()
        for it in items:
            li = QListWidgetItem()
            li.setText(it["name"])
            li.setToolTip(f"{it['name']}\n{it['status']}")
            pm = QPixmap.fromImage(it["thumbnail_qimage"])
            li.setIcon(pm)
            if it["status"] == "PASS":
                li.setBackground(QColor(0,64,0))
            elif it["status"] == "FAIL":
                li.setBackground(QColor(64,0,0))
            elif it["status"] == "DUPLICATE":
                li.setBackground(QColor(64,64,0))
            self.addItem(li)

    def add_thumb(self, it: Dict):
        li = QListWidgetItem()
        li.setText(it["name"])
        li.setToolTip(f"{it['name']}\n{it['status']}")
        pm = QPixmap.fromImage(it["thumbnail_qimage"])
        li.setIcon(pm)
        if it["status"] == "PASS":
            li.setBackground(QColor(0,64,0))
        elif it["status"] == "FAIL":
            li.setBackground(QColor(64,0,0))
        elif it["status"] == "DUPLICATE":
            li.setBackground(QColor(64,64,0))
        self.addItem(li)

class CropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.rect = QRect(50,50,200,200)
        self.dragging = False
        self.resizing = False
        self.handle = None
        self.handle_size = 10
        self.image = QPixmap()

    def set_pixmap(self, pm: QPixmap):
        self.image = pm
        iw, ih = pm.width(), pm.height()
        self.rect = QRect(iw//4, ih//4, iw//2, ih//2)
        self.update()

    def paintEvent(self, e):
        if self.image.isNull():
            return
        p = QPainter(self)
        p.drawPixmap(0,0,self.image)
        p.setPen(QPen(QColor(0,255,0), 2, Qt.SolidLine))
        p.drawRect(self.rect)
        hs = self.handle_size
        for pt in self.handle_points():
            p.fillRect(QRect(pt.x()-hs//2, pt.y()-hs//2, hs, hs), QColor(0,255,0))

    def sizeHint(self):
        return QSize(self.image.width(), self.image.height()) if not self.image.isNull() else super().sizeHint()

    def handle_points(self):
        r = self.rect
        return [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]

    def hit_handle(self, pos):
        hs = self.handle_size + 6
        for idx,pt in enumerate(self.handle_points()):
            if QRect(pt.x()-hs//2, pt.y()-hs//2, hs, hs).contains(pos):
                return idx
        return None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            pos = ev.position().toPoint()
            h = self.hit_handle(pos)
            if h is not None:
                self.resizing = True; self.handle = h; return
            if self.rect.contains(pos):
                self.dragging = True
                self.drag_off = pos - self.rect.topLeft()

    def mouseMoveEvent(self, ev):
        pos = ev.position().toPoint()
        if self.resizing:
            if self.handle == 0: self.rect.setTopLeft(pos)
            elif self.handle == 1: self.rect.setTopRight(pos)
            elif self.handle == 2: self.rect.setBottomLeft(pos)
            elif self.handle == 3: self.rect.setBottomRight(pos)
            self.rect = self.rect.normalized(); self.update(); return
        if self.dragging:
            tl = pos - self.drag_off
            self.rect.moveTopLeft(tl); self.update(); return
        h = self.hit_handle(pos)
        if h is not None or self.rect.contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, ev):
        self.dragging = False; self.resizing = False; self.handle = None

    def crop_rect_norm(self):
        return self.rect.normalized()
