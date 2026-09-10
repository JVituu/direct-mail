from pathlib import Path
import sys

from PySide6.QtGui import QColor, QImage


def main() -> int:
    if len(sys.argv) != 3:
        print("Uso: prepare_header_logo.py <entrada.png> <saida.png>")
        return 2

    source_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    image = QImage(str(source_path)).convertToFormat(QImage.Format.Format_RGBA8888)
    if image.isNull():
        print(f"Nao foi possivel abrir a imagem: {source_path}")
        return 1

    transparent_pixel = QColor(0, 0, 0, 0).rgba()
    min_x = image.width()
    min_y = image.height()
    max_x = -1
    max_y = -1
    kept_pixels = 0

    for y in range(image.height()):
        for x in range(image.width()):
            color = QColor.fromRgba(image.pixel(x, y))
            red = color.red()
            green = color.green()
            blue = color.blue()
            average = (red + green + blue) // 3
            neutral_delta = max(red, green, blue) - min(red, green, blue)

            is_checker_background = neutral_delta <= 18 and 80 <= average <= 235
            if is_checker_background:
                image.setPixel(x, y, transparent_pixel)
                continue

            kept_pixels += 1
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if kept_pixels and min_x <= max_x and min_y <= max_y:
        padding = 18
        min_x = max(min_x - padding, 0)
        min_y = max(min_y - padding, 0)
        max_x = min(max_x + padding, image.width() - 1)
        max_y = min(max_y + padding, image.height() - 1)
        image = image.copy(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output_path), "PNG"):
        print(f"Nao foi possivel salvar a imagem: {output_path}")
        return 1

    print(f"Logo preparada: {output_path} ({image.width()}x{image.height()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
