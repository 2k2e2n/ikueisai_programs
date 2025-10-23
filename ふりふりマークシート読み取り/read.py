import cv2
import numpy as np
from typing import List, Tuple, Optional

class OMRReader:
    def __init__(self):
        """OMRリーダーの初期化"""
        # ArUcoマーカーの辞書を定義（7x7のマーカー、ID 0,1,2,3 を端に配置）
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        
        # マークシートの設定
        self.marker_corners = []  # ArUcoマーカーの4つの角
        self.perspective_matrix = None
        
    def detect_aruco_markers(self, image: np.ndarray) -> Tuple[List, List]:
        """
        ArUcoマーカーを検出する
        
        Args:
            image: 入力画像
            
        Returns:
            corners: 検出されたマーカーの角の座標
            ids: 検出されたマーカーのID
        """
        # 入力がカラーでも白黒でも動作するように統一してグレースケール化
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        corners, ids, _ = self.detector.detectMarkers(gray)
        
        return corners, ids
    
    def find_marker_corners(self, corners: List, ids: List) -> Optional[np.ndarray]:
        """
        4つのArUcoマーカーから画像の4隅を特定する
        
        Args:
            corners: 検出されたマーカーの角の座標
            ids: 検出されたマーカーのID
            
        Returns:
            4隅の座標（左上、右上、右下、左下の順）
        """
        if ids is None or len(ids) < 4:
            return None
            
        # マーカーID 0, 1, 2, 3を想定
        marker_positions = {}
        for i, marker_id in enumerate(ids.flatten()):
            if marker_id in [0, 1, 2, 3]:
                # マーカーの中心座標を計算
                marker_corners = corners[i][0]
                center = np.mean(marker_corners, axis=0)
                marker_positions[marker_id] = center
        
        if len(marker_positions) != 4:
            return None
            
        # 画像の4隅を特定
        # 左上: ID 0, 右上: ID 1, 右下: ID 2, 左下: ID 3
        corners_coords = np.array([
            marker_positions[0],  # 左上
            marker_positions[1],  # 右上
            marker_positions[2],  # 右下
            marker_positions[3]   # 左下
        ], dtype=np.float32)
        
        return corners_coords
    
    def correct_perspective(self, image: np.ndarray, corners: np.ndarray, 
                          output_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
        """
        透視変換を使用して画像を補正する
        
        Args:
            image: 入力画像
            corners: 4隅の座標
            output_size: 出力画像のサイズ (width, height)。None の場合は比率を維持して自動計算
            
        Returns:
            補正された画像
        """
        # 入力の4隅から元の長辺・短辺を推定（台形の上下・左右の平均）
        top_width = float(np.linalg.norm(corners[1] - corners[0]))
        bottom_width = float(np.linalg.norm(corners[2] - corners[3]))
        left_height = float(np.linalg.norm(corners[3] - corners[0]))
        right_height = float(np.linalg.norm(corners[2] - corners[1]))
        estimated_width = (top_width + bottom_width) / 2.0
        estimated_height = (left_height + right_height) / 2.0

        # 出力サイズを決定（比率維持）
        if output_size is None:
            out_w = max(1, int(round(estimated_width)))
            out_h = max(1, int(round(estimated_height)))
        else:
            # 指定サイズがあっても元比率を維持するように一方を調整
            target_w, target_h = output_size
            source_ratio = estimated_width / max(estimated_height, 1e-6)
            # 幅を優先し、高さを比率に合わせて調整
            out_w = max(1, int(target_w))
            out_h = max(1, int(round(out_w / source_ratio)))

        # 出力画像の4隅を定義
        dst_points = np.array([
            [0, 0],                 # 左上
            [out_w, 0],             # 右上
            [out_w, out_h],         # 右下
            [0, out_h]              # 左下
        ], dtype=np.float32)
        
        # 透視変換行列を計算
        self.perspective_matrix = cv2.getPerspectiveTransform(corners, dst_points)
        
        # 透視変換を適用
        corrected_image = cv2.warpPerspective(image, self.perspective_matrix, (out_w, out_h))
        
        return corrected_image
    
    def crop_image_with_aruco(self, image_path: str, output_path: str = "crop.png", 
                            output_size: Optional[Tuple[int, int]] = None,
                            crop_rect: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """
        ArUcoマーカーを検出して画像をクロップする
        
        Args:
            image_path: 入力画像のパス
            output_path: 出力画像のパス
            output_size: 出力画像のサイズ (width, height)。None で比率維持の自動サイズ
            crop_rect: 透視補正後に切り出す絶対矩形 (x, y, X, Y)
            
        Returns:
            成功した場合True、失敗した場合False
        """
        # 画像を読み込み
        image = cv2.imread(image_path)
        if image is None:
            print(f"エラー: 画像を読み込めませんでした: {image_path}")
            return False
        
        print(f"画像サイズ: {image.shape}")
        
        # ArUcoマーカーを検出
        corners, ids = self.detect_aruco_markers(image)
        print(f"検出されたマーカー数: {len(ids) if ids is not None else 0}")
        
        if ids is not None:
            print(f"検出されたマーカーID: {ids.flatten().tolist()}")
        
        if ids is None or len(ids) < 4:
            print("エラー: 4つのArUcoマーカーが検出されませんでした")
            return False
        
        # マーカーの角を特定
        marker_corners = self.find_marker_corners(corners, ids)
        if marker_corners is None:
            print("エラー: マーカーの角を特定できませんでした")
            return False
        
        print(f"検出されたマーカー角の座標:")
        for i, corner in enumerate(marker_corners):
            print(f"  角{i}: ({corner[0]:.1f}, {corner[1]:.1f})")
        
        # 透視変換で画像を補正（比率維持。output_sizeがNoneなら自動）
        corrected_image = self.correct_perspective(image, marker_corners, output_size)

        # 必要に応じて絶対座標で追加クロップ
        if crop_rect is not None:
            x, y, X, Y = crop_rect
            h, w = corrected_image.shape[:2]
            # 座標を安全にクリップ
            x = max(0, min(int(x), w))
            X = max(0, min(int(X), w))
            y = max(0, min(int(y), h))
            Y = max(0, min(int(Y), h))
            # 左上/右下の正規化
            x1, x2 = sorted([x, X])
            y1, y2 = sorted([y, Y])
            if x2 - x1 <= 0 or y2 - y1 <= 0:
                print("エラー: crop_rect の範囲が無効です")
                return False
            corrected_image = corrected_image[y1:y2, x1:x2]
        
        # クロップした画像を保存
        success = cv2.imwrite(output_path, corrected_image)
        if success:
            print(f"クロップした画像を保存しました: {output_path}")
            print(f"出力画像サイズ: {corrected_image.shape[1]}x{corrected_image.shape[0]}")
            return True
        else:
            print(f"エラー: 画像の保存に失敗しました: {output_path}")
            return False
    

def main():
    """メイン処理"""
    omr_reader = OMRReader()
    
    # テスト画像のパス
    image_path = "image/marksheet_test.png"
    
    try:
        print("=== ArUcoマーカー検出とクロップ処理 ===")
        
        # ArUcoマーカーを検出して画像をクロップ（比率を維持）
        success = omr_reader.crop_image_with_aruco(
            image_path=image_path,
            output_path="crop.png",
            output_size=None,  # Noneで元比率を維持したサイズを自動計算
            # 絶対座標クロップ（必要に応じて変更）
            crop_rect=(180, 620, 2835, 1440)
        )
        
        if success:
            print("クロップ処理が完了しました！")
        else:
            print("クロップ処理に失敗しました。")
            return
        
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()
