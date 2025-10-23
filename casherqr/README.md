# QRコードスキャナー - シリアルデバイス読み取りプログラム

このプログラムは、COM6に接続されたシリアルデバイスからQRコード情報を取得し、GUIで表示するためのPythonプログラムです。

## 必要な環境

- Python 3.6以上
- pyserial ライブラリ
- tkinter（Python標準ライブラリ）

## インストール

1. 必要なライブラリをインストール：
```bash
pip install -r requirements.txt
```

## 使用方法

### 1. GUIモード（推奨）

QRコードスキャン結果をGUIで表示：

```bash
python serial_reader.py --gui
```

GUI機能：
- QRコードスキャン結果のリアルタイム表示
- 統計情報（総スキャン数、Qhurihuri回数、Qkarambit回数）
- スキャン履歴の表形式表示
- 履歴のクリア機能
- CSVエクスポート機能

### 2. コマンドラインモード

従来のコマンドライン形式で実行：

```bash
# 基本的な読み取り
python serial_reader.py

# 特定のポートとボーレートを指定
python serial_reader.py --port COM6 --baudrate 115200

# 10行だけ読み取る
python serial_reader.py --lines 10

# 30秒間読み取る
python serial_reader.py --duration 30

# データをファイルに保存
python serial_reader.py --save --lines 100

# カスタム設定で読み取り
python serial_reader.py --port COM6 --baudrate 9600 --timeout 2.0 --duration 60 --save
```

### 3. 簡単な実行

最もシンプルな方法でCOM6からデータを読み取る：

```bash
python run_serial.py
```

## コマンドライン引数

- `--port`: シリアルポート名（デフォルト: COM6）
- `--baudrate`: ボーレート（デフォルト: 9600）
- `--timeout`: タイムアウト時間（秒）（デフォルト: 1.0）
- `--lines`: 読み取る最大行数
- `--duration`: 読み取り時間（秒）
- `--save`: データをJSONファイルに保存
- `--gui`: GUIモードで実行

## 出力

### GUIモード
- QRコードスキャン結果がリアルタイムでGUIの表に表示されます
- 統計情報がリアルタイムで更新されます
- ログファイル（`serial_reader.log`）に詳細なログが記録されます
- 会計.csvファイルにスキャン結果が自動保存されます

### コマンドラインモード
- コンソールにリアルタイムでデータが表示されます
- ログファイル（`serial_reader.log`）に詳細なログが記録されます
- `--save`オプションを使用すると、データがJSONファイルに保存されます

## 特別なQRコード

プログラムは以下のQRコードを特別に認識します：
- **Qhurihuri**: 特別検出として表示され、カウンターが増加します
- **Qkarambit**: 特別検出として表示され、カウンターが増加します

## テスト

GUI機能をテストするには：

```bash
python test_gui.py
```

## 注意事項

- COM6ポートが他のアプリケーションで使用されていないことを確認してください
- デバイスのボーレート設定と一致するように`--baudrate`を設定してください
- GUIモードでは、プログラムを終了するにはウィンドウを閉じるか Ctrl+C を押してください
- コマンドラインモードでは、Ctrl+C で終了できます

## トラブルシューティング

1. **接続エラー**: COM6ポートが存在するか、他のアプリケーションで使用されていないか確認してください
2. **データが表示されない**: ボーレート設定を確認し、デバイスがデータを送信しているか確認してください
3. **文字化け**: デバイスの文字エンコーディング設定を確認してください
4. **GUIが表示されない**: tkinterがインストールされているか確認してください
