import sys
from typing import Tuple

import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Failed to read image at '{path}'")
    return image


def generate_grid_edges(width: int, height: int, cols: int, rows: int) -> Tuple[np.ndarray, np.ndarray]:
    # Use linspace to ensure the last edges land exactly on image borders
    x_edges = np.linspace(0, width, num=cols + 1, dtype=np.int32)
    y_edges = np.linspace(0, height, num=rows + 1, dtype=np.int32)
    # Guarantee boundary coverage in case of rounding quirks
    x_edges[0], x_edges[-1] = 0, width
    y_edges[0], y_edges[-1] = 0, height
    return x_edges, y_edges


def draw_grid_rectangles(image: np.ndarray, cols: int, rows: int, color=(0, 0, 255), thickness: int = 1) -> np.ndarray:
    height, width = image.shape[:2]
    x_edges, y_edges = generate_grid_edges(width, height, cols, rows)

    marked = image.copy()
    for r in range(rows):
        y1, y2 = int(y_edges[r]), int(y_edges[r + 1]) - 1
        for c in range(cols):
            x1, x2 = int(x_edges[c]), int(x_edges[c + 1]) - 1
            # Clamp to image bounds to avoid potential -1 for very small dimensions
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width - 1, x2)
            y2 = min(height - 1, y2)
            cv2.rectangle(marked, (x1, y1), (x2, y2), color, thickness)
    return marked


def analyze_and_highlight_black_cells(
    image: np.ndarray,
    cols: int,
    rows: int,
    thickness: int = 2,
    black_ratio_threshold: float = 0.1,
    gray_threshold: int | None = None,
) -> np.ndarray:
    height, width = image.shape[:2]
    x_edges, y_edges = generate_grid_edges(width, height, cols, rows)

    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    marked = image.copy()

    for r in range(rows):
        y1, y2 = int(y_edges[r]), int(y_edges[r + 1]) - 1
        for c in range(cols):
            x1, x2 = int(x_edges[c]), int(x_edges[c + 1]) - 1
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width - 1, x2)
            y2 = min(height - 1, y2)

            roi = grayscale[y1:y2 + 1, x1:x2 + 1]
            if roi.size == 0:
                continue

            # Thresholding per cell: fixed threshold if provided, otherwise local Otsu
            if gray_threshold is not None:
                _t, binary = cv2.threshold(roi, int(gray_threshold), 255, cv2.THRESH_BINARY)
            else:
                _t, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            total_pixels = binary.size
            black_pixels = total_pixels - int(cv2.countNonZero(binary))
            black_ratio = black_pixels / float(total_pixels)

            if black_ratio >= black_ratio_threshold:
                cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 255, 0), thickness)
            else:
                # Draw a thin red outline for non-black-dominant cells to keep the full grid visible
                cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 0, 255), 1)

    return marked


def compute_black_matrix(
    image: np.ndarray,
    cols: int,
    rows: int,
    black_ratio_threshold: float = 0.5,
    gray_threshold: int | None = None,
) -> np.ndarray:
    height, width = image.shape[:2]
    x_edges, y_edges = generate_grid_edges(width, height, cols, rows)

    grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    black_matrix = np.zeros((rows, cols), dtype=np.uint8)

    for r in range(rows):
        y1, y2 = int(y_edges[r]), int(y_edges[r + 1]) - 1
        for c in range(cols):
            x1, x2 = int(x_edges[c]), int(x_edges[c + 1]) - 1
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(width - 1, x2)
            y2 = min(height - 1, y2)

            roi = grayscale[y1:y2 + 1, x1:x2 + 1]
            if roi.size == 0:
                continue

            if gray_threshold is not None:
                _t, binary = cv2.threshold(roi, int(gray_threshold), 255, cv2.THRESH_BINARY)
            else:
                _t, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            total_pixels = binary.size
            black_pixels = total_pixels - int(cv2.countNonZero(binary))
            black_ratio = black_pixels / float(total_pixels)

            black_matrix[r, c] = 1 if black_ratio >= black_ratio_threshold else 0

    return black_matrix


def export_black_matrix_as_binary_bytes(black_matrix: np.ndarray, export_path: str) -> None:
    rows, cols = black_matrix.shape
    # Expecting rows=8, cols=32; but handle generically where rows<=8
    lines = []
    for c in range(cols):
        value = 0
        # Map row 0 (top) to MSB (bit 7), row 7 (bottom) to LSB (bit 0)
        for r in range(rows):
            bit_pos = 7 - r  # assumes rows <= 8
            if black_matrix[r, c]:
                value |= (1 << bit_pos)
        lines.append(f"0b{value:08b},")

    # Group by 8 columns with a comma-only separator line, matching the requested format
    grouped_lines = []
    for i in range(0, len(lines), 8):
        grouped_lines.extend(lines[i:i + 8])
        if i + 8 < len(lines):
            grouped_lines.append(",")

    with open(export_path, "w", encoding="utf-8") as f:
        for line in grouped_lines:
            f.write(line + "\n")


def main() -> int:
    input_path = "crop.png"
    output_path = "marked.png"

    try:
        image = load_image(input_path)
    except FileNotFoundError as e:
        print(str(e))
        return 1

    # 32 columns (x-direction), 8 rows (y-direction)
    cols, rows = 32, 8
    marked = analyze_and_highlight_black_cells(image, cols=cols, rows=rows, thickness=2, black_ratio_threshold=0.5)

    black_matrix = compute_black_matrix(image, cols=cols, rows=rows, black_ratio_threshold=0.5)
    export_black_matrix_as_binary_bytes(black_matrix, export_path="export.txt")

    if not cv2.imwrite(output_path, marked):
        print(f"Failed to write output image to '{output_path}'")
        return 1

    print(f"Saved '{output_path}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())


