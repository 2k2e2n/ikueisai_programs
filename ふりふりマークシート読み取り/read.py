import cv2
import numpy as np
from typing import List, Tuple, Optional

class OMRReader:
    def __init__(self):
        """OMRリーダーの初期化"""
        # ArUcoマーカーの辞書を定義（7x7のマーカー、ID 0,1,2,3 を端に配置）
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_7X7_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        
        # 歪みに強い検出パラメータを設定
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 23
        self.aruco_params.adaptiveThreshWinSizeStep = 10
        self.aruco_params.adaptiveThreshConstant = 7
        
        # 歪みに対応するため、より柔軟な形状検出パラメータ
        self.aruco_params.minMarkerPerimeterRate = 0.02  # より小さなマーカーも検出
        self.aruco_params.maxMarkerPerimeterRate = 6.0    # より大きなマーカーも検出
        self.aruco_params.polygonalApproxAccuracyRate = 0.05  # より柔軟な多角形近似
        self.aruco_params.minCornerDistanceRate = 0.03    # より近いコーナーも許可
        self.aruco_params.minDistanceToBorder = 1         # 境界に近いマーカーも検出
        self.aruco_params.minMarkerDistanceRate = 0.03     # より近いマーカー間距離も許可
        
        # コーナー検出の精度向上（歪み補正）
        self.aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.aruco_params.cornerRefinementWinSize = 7     # より大きなウィンドウサイズ
        self.aruco_params.cornerRefinementMaxIterations = 50  # より多くの反復
        self.aruco_params.cornerRefinementMinAccuracy = 0.05  # より低い精度閾値
        
        # マーカー内部の処理（歪み対応）
        self.aruco_params.markerBorderBits = 1
        self.aruco_params.perspectiveRemovePixelPerCell = 6  # より大きなセルサイズ
        self.aruco_params.perspectiveRemoveIgnoredMarginPerCell = 0.2  # より大きなマージン
        self.aruco_params.maxErroneousBitsInBorderRate = 0.5  # より多くのエラーを許可
        self.aruco_params.minOtsuStdDev = 3.0              # より低い標準偏差閾値
        self.aruco_params.errorCorrectionRate = 0.8        # より高いエラー訂正率
        
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        
        # マークシートの設定
        self.marker_corners = []  # ArUcoマーカーの4つの角
        self.perspective_matrix = None
        
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        画像の前処理を行い、ArUcoマーカーの検出精度を向上させる（歪み対応版）
        
        Args:
            image: 入力画像
            
        Returns:
            前処理された画像
        """
        # グレースケール変換
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # ノイズ除去（歪みがある場合、より強力なノイズ除去）
        denoised = cv2.medianBlur(gray, 5)  # カーネルサイズを大きく
        
        # コントラスト調整（CLAHE）- 歪みによる不均一な照明に対応
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))  # clipLimitを上げる
        enhanced = clahe.apply(denoised)
        
        # ガウシアンブラーで微細なノイズを除去
        blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
        
        # 歪み補正のための追加処理
        # 1. モルフォロジー演算でマーカーの形状を改善
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        morphed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, kernel)
        
        # 2. エッジ強調でマーカーの境界を明確化
        edges = cv2.Canny(morphed, 50, 150)
        
        # 3. エッジと元画像を組み合わせて最終画像を作成
        final = cv2.addWeighted(morphed, 0.8, edges, 0.2, 0)
        
        return final

    def detect_aruco_markers(self, image: np.ndarray, use_preprocessing: bool = True) -> Tuple[List, List]:
        """
        ArUcoマーカーを検出する（回転対応版）
        
        Args:
            image: 入力画像
            use_preprocessing: 前処理を使用するかどうか
            
        Returns:
            corners: 検出されたマーカーの角の座標
            ids: 検出されたマーカーのID
        """
        # 前処理を適用
        if use_preprocessing:
            processed_image = self.preprocess_image(image)
        else:
            processed_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        
        # 複数の回転角度で検出を試行
        best_corners = None
        best_ids = None
        max_detected = 0
        
        # 0度、90度、180度、270度で回転させて検出
        for angle in [0, 90, 180, 270]:
            if angle == 0:
                rotated_image = processed_image
            else:
                h, w = processed_image.shape
                center = (w // 2, h // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated_image = cv2.warpAffine(processed_image, rotation_matrix, (w, h))
            
            corners, ids, _ = self.detector.detectMarkers(rotated_image)
            
            if ids is not None and len(ids) > max_detected:
                max_detected = len(ids)
                best_corners = corners
                best_ids = ids
                
                # 4つ検出できたら即座に返す
                if len(ids) >= 4:
                    break
        
        return best_corners, best_ids



    def detect_aruco_markers_flexible(self, image: np.ndarray) -> Tuple[List, List]:
        """
        柔軟なパラメータでArUcoマーカーを検出する（歪み対応）
        
        Args:
            image: 入力画像
            
        Returns:
            corners: 検出されたマーカーの角の座標
            ids: 検出されたマーカーのID
        """
        # より柔軟なパラメータを設定
        flexible_params = cv2.aruco.DetectorParameters()
        
        # 非常に柔軟な設定
        flexible_params.adaptiveThreshWinSizeMin = 3
        flexible_params.adaptiveThreshWinSizeMax = 31
        flexible_params.adaptiveThreshWinSizeStep = 14
        flexible_params.adaptiveThreshConstant = 5
        flexible_params.minMarkerPerimeterRate = 0.01
        flexible_params.maxMarkerPerimeterRate = 8.0
        flexible_params.polygonalApproxAccuracyRate = 0.08
        flexible_params.minCornerDistanceRate = 0.01
        flexible_params.minDistanceToBorder = 0
        flexible_params.minMarkerDistanceRate = 0.01
        flexible_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        flexible_params.cornerRefinementWinSize = 9
        flexible_params.cornerRefinementMaxIterations = 100
        flexible_params.cornerRefinementMinAccuracy = 0.01
        flexible_params.markerBorderBits = 1
        flexible_params.perspectiveRemovePixelPerCell = 8
        flexible_params.perspectiveRemoveIgnoredMarginPerCell = 0.3
        flexible_params.maxErroneousBitsInBorderRate = 0.7
        flexible_params.minOtsuStdDev = 1.0
        flexible_params.errorCorrectionRate = 0.9
        
        # 前処理された画像で検出
        processed_image = self.preprocess_image(image)
        
        best_corners = None
        best_ids = None
        max_detected = 0
        
        # 複数の辞書とスケールで試行
        dict_options = [cv2.aruco.DICT_7X7_50, cv2.aruco.DICT_6X6_50, cv2.aruco.DICT_5X5_50, cv2.aruco.DICT_4X4_50]
        scales = [0.3, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
        
        for dict_type in dict_options:
            temp_dict = cv2.aruco.getPredefinedDictionary(dict_type)
            temp_detector = cv2.aruco.ArucoDetector(temp_dict, flexible_params)
            
            for scale in scales:
                if scale == 1.0:
                    scaled_image = processed_image
                else:
                    h, w = processed_image.shape
                    new_h, new_w = int(h * scale), int(w * scale)
                    scaled_image = cv2.resize(processed_image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                
                corners, ids, _ = temp_detector.detectMarkers(scaled_image)
                
                if ids is not None and len(ids) > max_detected:
                    max_detected = len(ids)
                    
                    if scale != 1.0:
                        adjusted_corners = []
                        for corner in corners:
                            adjusted_corner = corner[0] / scale
                            adjusted_corners.append([adjusted_corner])
                        best_corners = adjusted_corners
                    else:
                        best_corners = corners
                    
                    best_ids = ids
                    
                    if len(ids) >= 4:
                        return best_corners, best_ids
        
        return best_corners, best_ids

    def visualize_detection(self, image: np.ndarray, corners: List, ids: List, 
                           output_path: str = "debug/detection_result.png") -> bool:
        """
        検出結果を可視化してデバッグ画像を保存する
        
        Args:
            image: 元画像
            corners: 検出されたマーカーの角の座標
            ids: 検出されたマーカーのID
            output_path: 出力画像のパス
            
        Returns:
            保存に成功した場合True
        """
        try:
            # 画像をコピー
            vis_image = image.copy()
            
            if ids is not None and len(ids) > 0:
                # 検出されたマーカーを描画（型を適切に変換）
                try:
                    # cornersをnumpy配列に変換
                    if corners is not None:
                        corners_array = np.array(corners, dtype=np.float32)
                        cv2.aruco.drawDetectedMarkers(vis_image, corners_array, ids)
                except Exception as e:
                    print(f"マーカー描画中にエラーが発生しました: {e}")
                    # エラーが発生した場合は描画をスキップ
                    pass
                
                # 各マーカーのIDと中心座標を表示
                try:
                    for i, marker_id in enumerate(ids.flatten()):
                        if corners is not None and i < len(corners):
                            marker_corners = corners[i][0]
                            center = np.mean(marker_corners, axis=0)
                            center = (int(center[0]), int(center[1]))
                            
                            # IDを表示
                            cv2.putText(vis_image, f"ID:{marker_id}", 
                                       (center[0] - 20, center[1] - 20),
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                except Exception as e:
                    print(f"マーカー情報表示中にエラーが発生しました: {e}")
            
            # 検出結果の情報を画像に追加
            info_text = f"Detected: {len(ids) if ids is not None else 0} markers"
            cv2.putText(vis_image, info_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 2)
            
            # 画像を保存
            import os
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            success = cv2.imwrite(output_path, vis_image)
            
            if success:
                print(f"検出結果を保存しました: {output_path}")
            else:
                print(f"検出結果の保存に失敗しました: {output_path}")
                
            return success
            
        except Exception as e:
            print(f"可視化中にエラーが発生しました: {e}")
            return False
    
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
