import sys  # 標準ライブラリ（終了コードなど）

import cv2  # OpenCV（画像処理）
import numpy as np  # 画像データ読み込み（日本語パス対策で使用）
import tkinter as tk  # GUI本体
from tkinter import ttk, filedialog, messagebox  # GUI部品、ファイルダイアログ、メッセージ
from typing import Dict, Any  # 設定の型注釈

from read import OMRReader  # ArUco検出と透視補正のロジック
from mark_grid import (
    analyze_and_highlight_black_cells,  # セル判定と枠描画
    compute_black_matrix,  # セル判定の0/1行列化
    export_black_matrix_as_binary_bytes,  # 指定フォーマットでexport.txtに保存
)


"""GUI起動時に初期表示するデフォルト設定（画面上で変更可能）"""
DEFAULTS = {
    "image_path": "image/marksheet_test4.jpg",
    "crop_output": "debug/crop.png",
    "marked_output": "debug/marked.png",
    "export_path": "output/export.txt",
    "grid_cols": 32,
    "grid_rows": 8,
    "black_ratio_threshold": 0.3,
    "gray_threshold": None,  # e.g., 140 to force fixed threshold; None -> Otsu per cell
    "aruco_dict": "DICT_7X7_50",
    "roi_window_title": "Select crop (Enter/Space=OK, Esc=Cancel)",
}

ARUCO_DICT_OPTIONS = [  # GUIで選択可能なマーカー辞書
    "DICT_7X7_50",
    "DICT_6X6_50",
    "DICT_5X5_50",
    "DICT_4X4_50",
]


def resolve_aruco_dict(name: str) -> int:
    """GUIで選ばれた辞書名からOpenCV定数に変換する"""
    mapping = {
        "DICT_7X7_50": cv2.aruco.DICT_7X7_50,
        "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
        "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
        "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    }
    return mapping.get(name, cv2.aruco.DICT_7X7_50)


def imread_unicode(path: str, flags: int) -> np.ndarray:
    """日本語などのUnicodeパスでも読み込めるcv2.imdecodeベースの読込"""
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        img = cv2.imdecode(data, flags)
        return img
    except Exception:
        return None


def select_roi_custom(window_title: str, image: np.ndarray, color=(0, 0, 255), thickness: int = 3) -> tuple:
    """カスタムROI選択（赤枠・太線）。
    マウスでドラッグして矩形を選択。Enter/Spaceで確定、Escでキャンセル。
    Returns: (x, y, w, h)
    """
    clone = image.copy()
    display = image.copy()
    start_pt = None
    end_pt = None
    selecting = False
    roi = (0, 0, 0, 0)

    def on_mouse(event, x, y, flags, param):
        nonlocal start_pt, end_pt, selecting, display, roi
        if event == cv2.EVENT_LBUTTONDOWN:
            selecting = True
            start_pt = (x, y)
            end_pt = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and selecting:
            end_pt = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and selecting:
            selecting = False
            end_pt = (x, y)
            x1, y1 = start_pt
            x2, y2 = end_pt
            x_min, x_max = sorted([x1, x2])
            y_min, y_max = sorted([y1, y2])
            roi = (x_min, y_min, max(0, x_max - x_min), max(0, y_max - y_min))

    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_title, on_mouse)

    while True:

        # ウィンドウが閉じられたかチェック
        if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
            roi = (0, 0, 0, 0)
            break


        display[:] = clone
        if start_pt is not None and (selecting or end_pt is not None):
            x1, y1 = start_pt
            x2, y2 = end_pt if end_pt is not None else start_pt
            cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
        cv2.imshow(window_title, display)
        key = cv2.waitKey(16) & 0xFF
        if key in (13, 32):  # Enter or Space to confirm
            break
        if key == 27:  # Esc to cancel
            roi = (0, 0, 0, 0)
            break

    cv2.destroyWindow(window_title)
    return roi


def run_pipeline(config: Dict[str, Any]) -> int:
    # Step 1: マーカー検出と透視補正（read.pyの機能を使用）
    omr_reader = OMRReader()
    # GUI設定に合わせてArUco辞書を上書き
    omr_reader.aruco_dict = cv2.aruco.getPredefinedDictionary(resolve_aruco_dict(config["aruco_dict"]))
    omr_reader.detector = cv2.aruco.ArucoDetector(omr_reader.aruco_dict, omr_reader.aruco_params)

    # 入力画像を白黒で読み込み（検出精度向上）
    src_gray = imread_unicode(config["image_path"], cv2.IMREAD_GRAYSCALE)
    if src_gray is None:
        messagebox.showerror("Error", f"Failed to read input image:\n{config['image_path']}")
        return 1
    # 後段処理の互換性のため3チャンネルBGRへ拡張
    src = cv2.cvtColor(src_gray, cv2.COLOR_GRAY2BGR)

    # ArUcoマーカーの検出
    corners, ids = omr_reader.detect_aruco_markers(src)
    if ids is None or len(ids) < 4:
        print("Could not detect 4 ArUco markers; aborting.")
        return 1

    # 左上,右上,右下,左下の順で4隅を同定
    marker_corners = omr_reader.find_marker_corners(corners, ids)
    if marker_corners is None:
        print("Failed to determine marker corners; aborting.")
        return 1

    # 透視補正を適用（シートをフラット化）
    corrected = omr_reader.correct_perspective(src, marker_corners, output_size=None)

    # Step 2: ROIをGUI上で手動選択（ドラッグ→Enter/Spaceで決定、Escでキャンセル）
    roi = select_roi_custom(config["roi_window_title"], corrected, color=(0, 0, 255), thickness=3)

    x, y, w_roi, h_roi = map(int, roi)
    if w_roi == 0 or h_roi == 0:
        print("No ROI selected; aborting.")
        return 1

    # 選択された矩形でクロップ
    cropped = corrected[y:y + h_roi, x:x + w_roi]
    if config.get("export_crop", False):
        if not cv2.imwrite(config["crop_output"], cropped):
            print(f"Failed to write '{config['crop_output']}'")
            return 1

    # Step 3: セル解析と出力生成（mark_grid.pyの機能を使用）
    # 解析用入力は、ファイル保存の有無に関わらずメモリ上のcroppedを使用
    image = cropped

    # グリッド設定（列×行）
    cols, rows = int(config["grid_cols"]), int(config["grid_rows"])
    # セル毎に二値化＋黒率で判定し、黒セルは緑枠で強調
    marked = None
    if config.get("export_marked", False):
        marked = analyze_and_highlight_black_cells(
            image,
            cols=cols,
            rows=rows,
            thickness=2,
            black_ratio_threshold=float(config["black_ratio_threshold"]),
            gray_threshold=None if config["gray_threshold"] in (None, "") else int(config["gray_threshold"]),
        )

    # 0/1の行列（白=0, 黒=1）を作成
    black_matrix = compute_black_matrix(
        image,
        cols=cols,
        rows=rows,
        black_ratio_threshold=float(config["black_ratio_threshold"]),
        gray_threshold=None if config["gray_threshold"] in (None, "") else int(config["gray_threshold"]),
    )
    # 指定フォーマットのバイナリ表現でexport.txtに保存
    export_black_matrix_as_binary_bytes(black_matrix, export_path=config["export_path"])

    # 緑枠付きの確認画像を保存
    if config.get("export_marked", False):
        if marked is None:
            print("Marked image was not generated")
            return 1
        if not cv2.imwrite(config["marked_output"], marked):
            print(f"Failed to write '{config['marked_output']}'")
            return 1

    # Export成功メッセージを表示
    messagebox.showinfo("Success", f"Export completed successfully!\nSaved to: {config['export_path']}")

    print(
        f"Pipeline completed: "
        f"{'(crop saved)' if config.get('export_crop', False) else '(crop skipped)'} / "
        f"{'(marked saved)' if config.get('export_marked', False) else '(marked skipped)'} / "
        f"export -> {config['export_path']}"
    )
    return 0


def build_gui() -> Dict[str, Any]:
    """設定GUIを構築し、Startで設定辞書を返す。CancelでNoneを返す。"""
    root = tk.Tk()
    root.title("ふりふりコンバーター")
    root.geometry("700x450")

    # 画面バインド用の変数群
    v_image = tk.StringVar(value=DEFAULTS["image_path"])
    # debugタブで使用する出力先（Crop/Marked）も先に定義しておく
    v_crop = tk.StringVar(value=DEFAULTS["crop_output"])
    v_marked = tk.StringVar(value=DEFAULTS["marked_output"])

    v_export = tk.StringVar(value=DEFAULTS["export_path"])
    v_cols = tk.IntVar(value=DEFAULTS["grid_cols"])
    v_rows = tk.IntVar(value=DEFAULTS["grid_rows"])
    v_black = tk.DoubleVar(value=DEFAULTS["black_ratio_threshold"])
    v_gray = tk.StringVar(value="" if DEFAULTS["gray_threshold"] is None else str(DEFAULTS["gray_threshold"]))
    v_aruco = tk.StringVar(value=DEFAULTS["aruco_dict"])
    v_roi_title = tk.StringVar(value=DEFAULTS["roi_window_title"])

    # レイアウト用パディング
    pad = {"padx": 6, "pady": 4}


    #=========================
    # rowの設定
    #=========================
    def row(parent, r, label, widget):
        """ラベル+ウィジェットを1行で配置するヘルパー"""
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", **pad)
        widget.grid(row=r, column=1, sticky="we", **pad)

    # Notebook（タブ）を配置し、左の設定タブと右の[debug]タブを用意
    notebook = ttk.Notebook(root)
    notebook.grid(row=0, column=0, sticky="nsew")
    root.columnconfigure(0, weight=1)

    settings_tab = ttk.Frame(notebook)
    debug_tab = ttk.Frame(notebook)
    notebook.add(settings_tab, text="Settings")
    notebook.add(debug_tab, text="debug")

    # Settingsタブのレイアウト
    settings_tab.columnconfigure(3, weight=2)


    # 画像パス（参照ボタン付き）
    # e_image = ttk.Entry(settings_tab, textvariable=v_image)
    # row(settings_tab, 0, "画像のパス", e_image)
    ttk.Label(settings_tab, text="画像パス").grid(row=0, column=0, sticky="w", **pad)
    ttk.Entry(settings_tab, textvariable=v_image).grid(row=0, column=1, sticky="w", **pad)
    ttk.Button(settings_tab, text="Browse...", command=lambda: v_image.set(filedialog.askopenfilename(title="Select image"))).grid(row=0, column=2, columnspan = 2 ,**pad)
    #ttk.Label(settings_tab, text="画像のパスを選択してください！", foreground="#666").grid(row=0, column=1, sticky="w", **pad)


    #  ===============================================
    #       画面中央の分割線（セパレーター）
    #  ===============================================
    sep = ttk.Separator(settings_tab, orient="horizontal")
    sep.grid(row=10, column=0, columnspan=4, sticky="ew", **pad)
    #sep = ttk.Separator(settings_tab, orient="vertical")
    #sep.grid(row=0, column=2, rowspan=20, sticky="ns", padx=6, pady=4)


    # 画像のプレビュー（選択画像のサムネイル） - セパレーターの下に表示
    preview_label = ttk.Label(settings_tab, text="(No preview)")
    preview_label.grid(row=11, column=0, columnspan=1, sticky="n", **pad)

    # 出力パス群
    row(settings_tab, 3, "出力先", ttk.Entry(settings_tab, textvariable=v_export))
    #ttk.Label(settings_tab, text="書き出すテキストの保存先。", foreground="#666").grid(row=3, column=3, sticky="w", **pad)



    # グリッド設定
    #row(settings_tab, 4, "列数", ttk.Spinbox(settings_tab, textvariable=v_cols, from_=1, to=256, width=8))
    ttk.Label(settings_tab, text="列数").grid(row=4, column=0, sticky="w", **pad)
    ttk.Spinbox(settings_tab, textvariable=v_cols, from_=1, to=256, width=8).grid(row=4, column=1, sticky="w", **pad)
    #ttk.Label(settings_tab, text="グリッドの列数（横方向、例: 32）。", foreground="#666").grid(row=4, column=3, sticky="w", **pad)
    #row(settings_tab, 5, "行数", ttk.Spinbox(settings_tab, textvariable=v_rows, from_=1, to=256, width=8))
    #ttk.Label(settings_tab, text="グリッドの行数（縦方向、例: 8）。", foreground="#666").grid(row=5, column=3, sticky="w", **pad)
    ttk.Label(settings_tab, text="行数").grid(row=4, column=2, sticky="w", **pad)
    ttk.Spinbox(settings_tab, textvariable=v_rows, from_=1, to=256, width=8).grid(row=4, column=3, sticky="w", **pad)



    # しきい値設定（黒率/固定グレースケール）
    row(settings_tab, 6, "マークの閾値(0~1)", ttk.Spinbox(settings_tab, textvariable=v_black, from_=0.0, to=1.0, increment=0.01, width=8))
    #ttk.Label(settings_tab, text="セルを黒とみなす黒画素割合の閾値 [0〜1]。", foreground="#666").grid(row=6, column=3, sticky="w", **pad)
    row(settings_tab, 7, "固定二値化の閾値 (0-255 or blank)", ttk.Entry(settings_tab, textvariable=v_gray))
    #ttk.Label(settings_tab, text="固定二値化の閾値 [0〜255]。空欄ならセル毎にOtsu。", foreground="#666").grid(row=7, column=3, sticky="w", **pad)





    # ArUco辞書選択
    row(settings_tab, 8, "ArUco設定（端のマーク）", ttk.Combobox(settings_tab, textvariable=v_aruco, values=ARUCO_DICT_OPTIONS, state="readonly"))
    #ttk.Label(settings_tab, text="四隅に配置するArUcoマーカー辞書の種類。", foreground="#666").grid(row=8, column=3, sticky="w", **pad)

    # ROI選択ウィンドウのタイトル
    row(settings_tab, 9, "ROI window title", ttk.Entry(settings_tab, textvariable=v_roi_title))
    #ttk.Label(settings_tab, text="ROI選択ダイアログのタイトル。", foreground="#666").grid(row=9, column=3, sticky="w", **pad)



    def update_preview(*_args):
        path = v_image.get().strip()
        if not path:
            preview_label.configure(text="(No preview)", image="")
            preview_label.image = None
            return
        img = imread_unicode(path, cv2.IMREAD_COLOR)
        if img is None:
            preview_label.configure(text="(Failed to load)", image="")
            preview_label.image = None
            return
        # サムネイル作成（最大幅/高さ 320px）
        h, w = img.shape[:2]
        scale = min(150 / max(w, 1), 150 / max(h, 1), 1.0)
        if scale < 1.0:
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        ok, buf = cv2.imencode('.png', img)
        if not ok:
            preview_label.configure(text="(Preview encode failed)", image="")
            preview_label.image = None
            return
        import base64
        b64 = base64.b64encode(buf.tobytes())
        tkimg = tk.PhotoImage(data=b64)
        preview_label.configure(image=tkimg, text="")
        preview_label.image = tkimg  # 参照保持

    # 画像パス変更でプレビュー更新
    v_image.trace_add('write', update_preview)
    # 初期プレビュー
    update_preview()

    # 実行/キャンセルボタン列
    btn_frame = ttk.Frame(settings_tab)
    btn_frame.grid(row=12, column=0, columnspan=3, sticky="e", **pad)

    def on_start():
        # GUI値を辞書に集約してパイプラインへ渡す
        config = {
            "image_path": v_image.get(),
            "crop_output": v_crop.get(),
            "marked_output": v_marked.get(),
            "export_path": v_export.get(),
            "grid_cols": v_cols.get(),
            "grid_rows": v_rows.get(),
            "black_ratio_threshold": v_black.get(),
            "gray_threshold": None if v_gray.get().strip() == "" else v_gray.get().strip(),
            "aruco_dict": v_aruco.get(),
            "roi_window_title": v_roi_title.get(),
            "export_crop": bool(v_export_crop.get()),
            "export_marked": bool(v_export_marked.get()),
        }
        root._config_result = config
        root.destroy()

    def on_cancel():
        # GUIを閉じて終了
        root._config_result = None
        root.destroy()

    ttk.Button(btn_frame, text="Start", command=on_start).grid(row=0, column=0, **pad)
    ttk.Button(btn_frame, text="Cancel", command=on_cancel).grid(row=0, column=1, **pad)


    #   ===============================================
    #   debug タブの内容（必要に応じて拡張）
    #   ===============================================
    dbg_pad = {"padx": 6, "pady": 4}
    v_debug_verbose = tk.BooleanVar(value=False)
    v_debug_overlay = tk.BooleanVar(value=False)
    ttk.Checkbutton(debug_tab, text="Verbose logs", variable=v_debug_verbose).grid(row=0, column=0, sticky="w", **dbg_pad)
    ttk.Checkbutton(debug_tab, text="Show overlay grid (preview only)", variable=v_debug_overlay).grid(row=1, column=0, sticky="w", **dbg_pad)


    row(debug_tab, 1, "Crop output", ttk.Entry(debug_tab, textvariable=v_crop))
    v_export_crop = tk.BooleanVar(value=False)

    ttk.Checkbutton(debug_tab, text="Export", variable=v_export_crop).grid(row=1, column=2, sticky="w", **pad)
    ttk.Label(debug_tab, text="透視補正後のクロップ画像の保存先。（デバッグ用）", foreground="#666").grid(row=1, column=3, sticky="w", **pad)
    row(debug_tab, 2, "Marked output", ttk.Entry(debug_tab, textvariable=v_marked))
    v_export_marked = tk.BooleanVar(value=False)
    
    ttk.Checkbutton(debug_tab, text="Export", variable=v_export_marked).grid(row=2, column=2, sticky="w", **pad)
    ttk.Label(debug_tab, text="塗りつぶした所を緑枠で示した結果画像の保存先。（デバッグ用）", foreground="#666").grid(row=2, column=3, sticky="w", **pad)






    def finalize_config():
        cfg = getattr(root, "_config_result", None)
        if cfg is not None:
            cfg["debug_verbose"] = bool(v_debug_verbose.get())
            cfg["debug_overlay_preview"] = bool(v_debug_overlay.get())
        return cfg

    root.mainloop()
    return finalize_config()


def main() -> int:
    while True:
        config = build_gui()
        if not config:
            return 0
        result = run_pipeline(config)
        if result != 0:
            return result
        # パイプラインが成功した場合、再度GUIを表示


if __name__ == "__main__":
    sys.exit(main())


