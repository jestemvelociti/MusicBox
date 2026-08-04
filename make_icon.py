import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen

SIZE = 256


def render_icon():
    img = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setBrush(QColor("#3d7bff"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(8, 8, SIZE - 16, SIZE - 16, 48, 48)

    font = QFont("Segoe UI Symbol")
    font.setPixelSize(190)
    font.setBold(True)
    p.setFont(font)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(img.rect().adjusted(0, 4, 0, 0), Qt.AlignmentFlag.AlignCenter, "♪")

    p.end()
    return img


def main():
    _app = QGuiApplication(sys.argv)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(out_dir, exist_ok=True)

    img = render_icon()
    png = os.path.join(out_dir, "icon.png")
    ico = os.path.join(out_dir, "icon.ico")
    if not img.save(png, "PNG"):
        print("Nie udało się zapisać PNG")
        sys.exit(1)
    if not img.save(ico, "ICO"):
        print("Nie udało się zapisać ICO")
        sys.exit(1)
    print(f"OK: {png}")
    print(f"OK: {ico}")


if __name__ == "__main__":
    main()
