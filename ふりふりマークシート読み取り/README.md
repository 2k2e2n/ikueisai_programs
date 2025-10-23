# 簡易OMR（Optical Mark Recognition）システム

PythonとOpenCVを使用した、ArUcoマーカーを利用した簡易的なOMRシステムです。

## 機能

- ArUcoマーカー（ID: 0, 1, 2, 3）を使用した画像の4隅検出
- 透視変換による画像の歪み補正
- マークシートのマーク検出と読み取り
- JSON形式での結果出力
- デバッグ用画像の生成

## 必要な環境

- Python 3.7以上
- OpenCV 4.8.0以上
- NumPy 1.21.0以上

## インストール

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本的な使用方法

```python
from read import OMRReader

# OMRリーダーを初期化
omr_reader = OMRReader()

# 画像を処理
results = omr_reader.process_image("image/writingsheet.png", num_questions=5, num_choices=4)

# 結果を表示
print(results)
```

### コマンドライン実行

```bash
python read.py
```

## ArUcoマーカーの配置

マークシートの4隅に以下のIDのArUcoマーカーを配置してください：

- 左上: ID 0
- 右上: ID 1  
- 右下: ID 2
- 左下: ID 3

マーカーファイルは `marker/` ディレクトリに配置されています。

## 出力形式

```json
{
  "success": true,
  "detected_markers": 4,
  "marker_ids": [0, 1, 2, 3],
  "questions": [
    {
      "question_number": 1,
      "choices": [
        {"choice": "A", "marked": false},
        {"choice": "B", "marked": true},
        {"choice": "C", "marked": false},
        {"choice": "D", "marked": false}
      ],
      "selected": ["B"],
      "answer": "B"
    }
  ]
}
```

## パラメータ調整

- `num_questions`: 問題数（デフォルト: 5）
- `num_choices`: 選択肢数（デフォルト: 4）
- マーク検出の閾値: `detect_mark_regions`メソッド内の`black_ratio > 0.1`を調整

## デバッグ

実行後、`debug_markers.png`ファイルが生成され、検出されたArUcoマーカーが可視化されます。

## 注意事項

- マークシートは十分な照明で撮影してください
- ArUcoマーカーが完全に見えるように配置してください
- マークは濃い色（黒など）で塗りつぶしてください
