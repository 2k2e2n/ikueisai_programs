#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COM9シリアルデバイスから情報を取得するプログラム
"""

import serial
import time
import logging
import sys
from datetime import datetime
import json
import argparse
import threading
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:
    tk = None
    ttk = None
    messagebox = None
import csv
import os
import queue

class QRCodeGUI:
    """QRコードデータを表示するGUIクラス"""
    
    def __init__(self, data_queue):
        """
        GUIの初期化
        
        Args:
            data_queue (queue.Queue): シリアルデータを受け取るキュー
        """
        self.data_queue = data_queue
        self.root = tk.Tk()
        self.root.title("QRコードスキャナー")
        self.root.geometry("800x600")
        
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(main_frame, text="QRコードスキャン結果", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # 統計情報フレーム
        stats_frame = ttk.LabelFrame(main_frame, text="統計情報", padding="5")
        stats_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.total_count_label = ttk.Label(stats_frame, text="総スキャン数: 0", font=("Arial", 12))
        self.total_count_label.grid(row=0, column=0, padx=(0, 20))
        
        self.qhurihuri_count_label = ttk.Label(stats_frame, text="Qhurihuri: 0回", font=("Arial", 12))
        self.qhurihuri_count_label.grid(row=0, column=1, padx=(0, 20))
        
        self.qkarambit_count_label = ttk.Label(stats_frame, text="Qkarambit: 0回", font=("Arial", 12))
        self.qkarambit_count_label.grid(row=0, column=2)
        
        # データ表示テーブル
        table_frame = ttk.LabelFrame(main_frame, text="スキャン履歴", padding="5")
        table_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Treeview（表）
        columns = ("日時", "データ", "備考")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # 列の設定
        self.tree.heading("日時", text="日時")
        self.tree.heading("データ", text="データ")
        self.tree.heading("備考", text="備考")
        
        self.tree.column("日時", width=200)
        self.tree.column("データ", width=150)
        self.tree.column("備考", width=200)
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # グリッドの重み設定
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        
        # クリアボタン
        clear_button = ttk.Button(button_frame, text="履歴をクリア", command=self.clear_history)
        clear_button.grid(row=0, column=0, padx=(0, 10))
        
        # エクスポートボタン
        export_button = ttk.Button(button_frame, text="CSVエクスポート", command=self.export_csv)
        export_button.grid(row=0, column=1)
        
        # カウンター
        self.total_count = 0
        self.qhurihuri_count = 0
        self.qkarambit_count = 0
        
        # データ更新のスケジューリング
        self.root.after(100, self.update_data)
    
    # def add_data(self, timestamp, data, remark="QRコードスキャン"):
        """
        テーブルにデータを追加
        
        Args:
            timestamp (str): 日時
            data (str): スキャンされたデータ
            remark (str): 備考
        """
        # テーブルに追加
        self.tree.insert("", 0, values=(timestamp, data, remark))
        
        # カウンター更新
        self.total_count += 1
        if data == "Qhurihuri":
            self.qhurihuri_count += 1
        elif data == "Qkarambit":
            self.qkarambit_count += 1
        
        # 統計情報更新
        self.update_stats()
        
        # テーブルが多くなりすぎた場合は古いデータを削除
        if self.tree.get_children():
            children = self.tree.get_children()
            if len(children) > 100:  # 最新100件まで保持
                self.tree.delete(children[-1])
    
    def update_stats(self):
        """統計情報を更新"""
        self.total_count_label.config(text=f"総スキャン数: {self.total_count}")
        self.qhurihuri_count_label.config(text=f"Qhurihuri: {self.qhurihuri_count}回")
        self.qkarambit_count_label.config(text=f"Qkarambit: {self.qkarambit_count}回")
    
    def clear_history(self):
        """履歴をクリア"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.total_count = 0
        self.qhurihuri_count = 0
        self.qkarambit_count = 0
        self.update_stats()
    
    def export_csv(self):
        """CSVファイルにエクスポート"""
        try:
            filename = f"qr_scan_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['日時', 'データ', '備考'])
                
                for item in self.tree.get_children():
                    values = self.tree.item(item)['values']
                    writer.writerow(values)
            
            messagebox.showinfo("エクスポート完了", f"データを {filename} に保存しました")
        except Exception as e:
            messagebox.showerror("エラー", f"CSVエクスポートエラー: {e}")
    
    def update_data(self):
        """キューからデータを取得してGUIを更新"""
        try:
            while True:
                data = self.data_queue.get_nowait()
                timestamp, qr_data = data
                self.add_data(timestamp, qr_data)
        except queue.Empty:
            pass
        
        # 100ms後に再度チェック
        self.root.after(100, self.update_data)
    
    def run(self):
        """GUIを実行"""
        self.root.mainloop()

class SerialReader:
    def __init__(self, port='COM6', baudrate=9600, timeout=1, gui_queue=None):
        """
        シリアルリーダーの初期化
        
        Args:
            port (str): シリアルポート名（デフォルト: COM6）
            baudrate (int): ボーレート（デフォルト: 9600）
            timeout (float): タイムアウト時間（秒）
            gui_queue (queue.Queue): GUIにデータを送信するキュー
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.qhurihuri_count = 0  # Qhurihuri検出回数のカウンター
        self.csv_filename = "会計.csv"  # CSVファイル名
        self.gui_queue = gui_queue  # GUIキュー
        self.running = False  # 実行状態フラグ
        
        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('serial_reader.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """シリアルポートに接続"""
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS
            )
            self.logger.info(f"シリアルポート {self.port} に接続しました (ボーレート: {self.baudrate})")
            return True
        except serial.SerialException as e:
            self.logger.error(f"シリアルポート接続エラー: {e}")
            return False
        except Exception as e:
            self.logger.error(f"予期しないエラー: {e}")
            return False
    
    def disconnect(self):
        """シリアルポートを切断"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            self.logger.info("シリアルポートを切断しました")
        
        # Qhurihuri検出回数を表示
        if self.qhurihuri_count > 0:
            print(f"\n📈 総計: Qhurihuri を {self.qhurihuri_count} 回検出しました")
            print("=" * 50)
    
    def read_data(self, max_lines=None):
        """
        シリアルポートからデータを読み取り
        
        Args:
            max_lines (int): 読み取る最大行数（Noneの場合は無制限）
        
        Returns:
            list: 読み取ったデータのリスト
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            self.logger.error("シリアルポートが接続されていません")
            return []
        
        data_lines = []
        line_count = 0
        
        try:
            self.logger.info("データ読み取りを開始します...")
            
            while True:
                if max_lines and line_count >= max_lines:
                    break
                
                # データが利用可能かチェック
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline()
                    if line:
                        # バイト列を文字列に変換（エンコーディングエラーを無視）
                        try:
                            decoded_line = line.decode('utf-8').strip()
                        except UnicodeDecodeError:
                            decoded_line = line.decode('utf-8', errors='ignore').strip()
                        
                        if decoded_line:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            data_entry = {
                                'timestamp': timestamp,
                                'data': decoded_line
                            }
                            data_lines.append(data_entry)
                            
                            # Qhurihuriが検出された場合の特別表示
                            if decoded_line.strip() == "Qhurihuri":
                                self.qhurihuri_count += 1
                                print(f"\n🎯 特別検出: Qhurihuri が検出されました！ [{timestamp}]")
                                print(f"📊 検出回数: {self.qhurihuri_count}回目")
                                print("=" * 50)
                                
                                # CSVファイルに記録
                                self.write_to_accounting_csv(timestamp, decoded_line.strip())
                                
                                # GUIキューにデータを送信
                                if self.gui_queue:
                                    self.gui_queue.put((timestamp, decoded_line.strip()))
                            
                            elif decoded_line.strip() == "Qkarambit":
                                self.qhurihuri_count += 1
                                print(f"\n🎯 特別検出: Qkarambit が検出されました！ [{timestamp}]")
                                print(f"📊 検出回数: {self.qhurihuri_count}回目")
                                print("=" * 50)
                                
                                # CSVファイルに記録
                                self.write_to_accounting_csv(timestamp, decoded_line.strip())
                                
                                # GUIキューにデータを送信
                                if self.gui_queue:
                                    self.gui_queue.put((timestamp, decoded_line.strip()))
                            
                            self.logger.info(f"[{timestamp}] {decoded_line}")
                            line_count += 1
                
                # 短い間隔でチェック
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("ユーザーによって中断されました")
        except Exception as e:
            self.logger.error(f"データ読み取りエラー: {e}")
        
        return data_lines
    
    def read_continuous(self, duration=None):
        """
        連続的にデータを読み取り
        
        Args:
            duration (float): 読み取り時間（秒）、Noneの場合は無制限
        """
        start_time = time.time()
        
        try:
            while True:
                if duration and (time.time() - start_time) >= duration:
                    break
                
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline()
                    if line:
                        try:
                            decoded_line = line.decode('utf-8').strip()
                        except UnicodeDecodeError:
                            decoded_line = line.decode('utf-8', errors='ignore').strip()
                        
                        if decoded_line:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Qhurihuriが検出された場合の特別表示
                            if decoded_line.strip() == "Qhurihuri":
                                self.qhurihuri_count += 1
                                print(f"\n🎯 特別検出: Qhurihuri が検出されました！ [{timestamp}]")
                                print(f"📊 検出回数: {self.qhurihuri_count}回目")
                                print("=" * 50)
                                
                                # CSVファイルに記録
                                self.write_to_accounting_csv(timestamp, decoded_line.strip())
                                
                                # GUIキューにデータを送信
                                if self.gui_queue:
                                    self.gui_queue.put((timestamp, decoded_line.strip()))
                            
                            self.logger.info(f"[{timestamp}] {decoded_line}")
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            self.logger.info("連続読み取りを停止しました")
    
    def save_data_to_file(self, data, filename=None):
        """
        読み取ったデータをファイルに保存
        
        Args:
            data (list): 保存するデータ
            filename (str): ファイル名（Noneの場合は自動生成）
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"serial_data_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"データを {filename} に保存しました")
        except Exception as e:
            self.logger.error(f"ファイル保存エラー: {e}")
    
    def write_to_accounting_csv(self, timestamp, data="Qhurihuri"):
        """
        会計.csvファイルにスキャン日時を書き込む
        
        Args:
            timestamp (str): スキャン日時
            data (str): スキャンされたデータ（デフォルト: Qhurihuri）
        """
        try:
            # CSVファイルが存在するかチェック
            file_exists = os.path.exists(self.csv_filename)
            
            # CSVファイルに追記モードで書き込み
            with open(self.csv_filename, 'a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # ファイルが存在しない場合はヘッダーを書き込み
                if not file_exists:
                    writer.writerow(['日時', 'データ', '備考'])
                
                # データを書き込み
                writer.writerow([timestamp, data, 'QRコードスキャン'])
                
            self.logger.info(f"会計.csvに記録しました: {timestamp}")
            
        except Exception as e:
            self.logger.error(f"CSVファイル書き込みエラー: {e}")

    def remove_from_accounting_csv(self, timestamp, data):
        """CSVから指定の行を削除する（日時とデータが一致する行を削除）。"""
        try:
            if not os.path.exists(self.csv_filename):
                return
            rows = []
            with open(self.csv_filename, newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.reader(csvfile)
                header = next(reader, None)
                for r in reader:
                    # r: [日時, データ, 備考]
                    if len(r) >= 2 and not (r[0] == timestamp and r[1] == data):
                        rows.append(r)
            # 上書き
            with open(self.csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                if header:
                    writer.writerow(header)
                for r in rows:
                    writer.writerow(r)
            self.logger.info(f"会計.csvから削除しました: {timestamp}, {data}")
        except Exception as e:
            self.logger.error(f"CSV削除エラー: {e}")

def run_gui_app():
    """GUIアプリケーションを実行"""
    if tk is None:
        print("tkinterが利用できません。GUIモードは使用できません。")
        return
    
    # データキューを作成
    data_queue = queue.Queue()
    
    # GUIを作成
    gui = QRCodeGUI(data_queue)
    
    # シリアルリーダーを作成
    reader = SerialReader(
        port='COM6',
        baudrate=9600,
        timeout=1.0,
        gui_queue=data_queue
    )
    
    def serial_thread():
        """シリアル読み取りスレッド"""
        try:
            if not reader.connect():
                return
            
            reader.read_continuous()  # 無制限で連続読み取り
            
        except Exception as e:
            reader.logger.error(f"シリアル読み取りエラー: {e}")
        finally:
            reader.disconnect()
    
    # シリアル読み取りを別スレッドで開始
    serial_thread_obj = threading.Thread(target=serial_thread, daemon=True)
    serial_thread_obj.start()
    
    # GUIを実行
    try:
        gui.run()
    except KeyboardInterrupt:
        print("\nアプリケーションを終了します...")
    finally:
        reader.disconnect()

def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='COM6シリアルデバイスから情報を取得')
    parser.add_argument('--port', default='COM6', help='シリアルポート名 (デフォルト: COM6)')
    parser.add_argument('--baudrate', type=int, default=9600, help='ボーレート (デフォルト: 9600)')
    parser.add_argument('--timeout', type=float, default=1.0, help='タイムアウト時間 (デフォルト: 1.0秒)')
    parser.add_argument('--lines', type=int, help='読み取る最大行数')
    parser.add_argument('--duration', type=float, help='読み取り時間（秒）')
    parser.add_argument('--save', action='store_true', help='データをファイルに保存')
    parser.add_argument('--gui', action='store_true', help='GUIモードで実行')
    
    args = parser.parse_args()
    
    # GUIモードが指定された場合
    if args.gui:
        run_gui_app()
        return
    
    # シリアルリーダーを作成
    reader = SerialReader(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout
    )
    
    try:
        # シリアルポートに接続
        if not reader.connect():
            sys.exit(1)
        
        # データ読み取り
        if args.duration:
            reader.read_continuous(duration=args.duration)
        else:
            data = reader.read_data(max_lines=args.lines)
            
            if args.save and data:
                reader.save_data_to_file(data)
    
    except Exception as e:
        reader.logger.error(f"実行エラー: {e}")
        sys.exit(1)
    
    finally:
        # シリアルポートを切断
        reader.disconnect()

if __name__ == "__main__":
    main()
