#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QRコードレジシステム
シリアルポートからQRコードを読み取り、商品を管理し、合計金額を表示するGUIアプリケーション
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
import queue
import csv
import os
from datetime import datetime
import json

class ProductManager:
    """商品管理クラス"""
    
    def __init__(self):
        self.products = {
            "001": {"qr_string": "Qhurihuri", "name": "ふりふり", "price": 1000},
            "002": {"qr_string": "Qkarambit", "name": "カラムビット", "price": 400},
            "003": {"qr_string": "Qkatipotikun", "name": "かちぽちくん", "price": 500},
            "004": {"qr_string": "Qspiral", "name": "スパイラル", "price": 300},
            # 他の商品も追加可能
        }
    
    def get_product_by_qr_string(self, qr_string):
        """QRコード文字列から商品情報を取得"""
        for product_id, product in self.products.items():
            if product["qr_string"] == qr_string:
                return product
        return None
    
    def get_product(self, product_id):
        """商品IDから商品情報を取得"""
        return self.products.get(product_id)
    
    def add_product(self, product_id, qr_string, name, price):
        """新しい商品を追加"""
        self.products[product_id] = {"qr_string": qr_string, "name": name, "price": price}
    
    def get_all_products(self):
        """全商品のリストを取得"""
        return self.products

class CashRegisterApp:
    """レジシステムのメインアプリケーション"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("QRレジプログラム")
        self.root.geometry("1000x700")
        
        # 商品管理
        self.product_manager = ProductManager()
        
        # データキュー（シリアル通信用）
        self.data_queue = queue.Queue()
        
        # 現在のカート（商品リスト）
        self.cart = []
        
        # GUIの初期化
        self.setup_gui()
        
        # シリアルリーダーの初期化
        self.serial_reader = None
        self.serial_thread = None
        
        # データ更新のスケジューリング
        self.root.after(100, self.update_data)
    
    def setup_gui(self):
        """GUIの設定"""
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # タイトル
        title_label = ttk.Label(main_frame, text="お会計", 
                               font=("Arial", 20, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 左側：商品管理エリア
        left_frame = ttk.LabelFrame(main_frame, text="商品管理", padding="10")
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 商品追加フォーム
        ttk.Label(left_frame, text="新しい商品を追加:").grid(row=0, column=0, columnspan=4, pady=(0, 10))
        
        ttk.Label(left_frame, text="商品ID:").grid(row=1, column=0, sticky=tk.W)
        self.product_id_entry = ttk.Entry(left_frame, width=15)
        self.product_id_entry.grid(row=1, column=1, padx=(5, 10))
        
        ttk.Label(left_frame, text="QRコード文字列:").grid(row=2, column=0, sticky=tk.W)
        self.qr_string_entry = ttk.Entry(left_frame, width=15)
        self.qr_string_entry.grid(row=2, column=1, padx=(5, 10))
        
        ttk.Label(left_frame, text="商品名:").grid(row=3, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(left_frame, width=15)
        self.name_entry.grid(row=3, column=1, padx=(5, 10))
        
        ttk.Label(left_frame, text="価格:").grid(row=4, column=0, sticky=tk.W)
        self.price_entry = ttk.Entry(left_frame, width=15)
        self.price_entry.grid(row=4, column=1, padx=(5, 10))
        
        add_product_btn = ttk.Button(left_frame, text="商品追加", command=self.add_product)
        add_product_btn.grid(row=5, column=0, columnspan=2, pady=10)
        
        # 既存商品リスト
        ttk.Label(left_frame, text="登録済み商品:").grid(row=6, column=0, columnspan=3, pady=(20, 5))
        
        # 商品リストとボタン用のフレーム
        product_list_frame = ttk.Frame(left_frame)
        product_list_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.product_tree = ttk.Treeview(product_list_frame, columns=("id", "qr_string", "name", "price"), show="headings", height=8)
        self.product_tree.heading("id", text="商品ID")
        self.product_tree.heading("qr_string", text="QR文字列")
        self.product_tree.heading("name", text="商品名")
        self.product_tree.heading("price", text="価格")
        self.product_tree.column("id", width=60)
        self.product_tree.column("qr_string", width=80)
        self.product_tree.column("name", width=80)
        self.product_tree.column("price", width=60)
        self.product_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 手動追加ボタン
        add_to_cart_btn = ttk.Button(product_list_frame, text="カートに追加", command=self.add_selected_to_cart)
        add_to_cart_btn.grid(row=0, column=1, padx=(5, 0), sticky=(tk.N, tk.S))
        
        # フレームの重み設定
        product_list_frame.grid_rowconfigure(0, weight=1)
        product_list_frame.grid_columnconfigure(0, weight=1)
        
        # 右側：レジエリア
        right_frame = ttk.LabelFrame(main_frame, text="レジ", padding="10")
        right_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # カートテーブル
        self.cart_tree = ttk.Treeview(right_frame, columns=("name", "price"), show="headings", height=6)
        self.cart_tree.heading("name", text="商品名")
        self.cart_tree.heading("price", text="価格")
        self.cart_tree.column("name", width=350)
        self.cart_tree.column("price", width=350)
        self.cart_tree.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # カートテーブル専用のカスタムスタイルを作成
        style = ttk.Style()
        style.configure("Cart.Treeview", font=("DIN1451ALT", 28, "bold"), rowheight=40)  # カートテーブル専用スタイル
        style.configure("Cart.Treeview.Heading", font=("DIN1451ALT", 18, "bold"))  # ヘッダー専用スタイル

        # カートテーブルにカスタムスタイルを適用
        self.cart_tree.configure(style="Cart.Treeview")


        # 合計金額表示
        total_frame = ttk.Frame(right_frame)
        total_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        self.total_label = ttk.Label(total_frame, text="合計金額: ¥0", 
                                   font=("Arial", 32, "bold"), foreground="red")
        self.total_label.grid(row=0, column=0)
        
        # ボタンエリア
        button_frame = ttk.Frame(right_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        delete_btn = ttk.Button(button_frame, text="選択商品を削除", command=self.delete_selected_item)
        delete_btn.grid(row=0, column=0, padx=(0, 10))
        
        clear_btn = ttk.Button(button_frame, text="カートをクリア", command=self.clear_cart)
        clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        checkout_btn = ttk.Button(button_frame, text="会計完了", command=self.checkout)
        checkout_btn.grid(row=0, column=2)
        
        # シリアル接続エリア
        serial_frame = ttk.LabelFrame(main_frame, text="シリアル接続", padding="10")
        serial_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Label(serial_frame, text="ポート:").grid(row=0, column=0, sticky=tk.W)
        self.port_entry = ttk.Entry(serial_frame, width=10)
        self.port_entry.insert(0, "COM6")
        self.port_entry.grid(row=0, column=1, padx=(5, 10))
        
        ttk.Label(serial_frame, text="ボーレート:").grid(row=0, column=2, sticky=tk.W)
        self.baudrate_entry = ttk.Entry(serial_frame, width=10)
        self.baudrate_entry.insert(0, "9600")
        self.baudrate_entry.grid(row=0, column=3, padx=(5, 10))
        
        self.connect_btn = ttk.Button(serial_frame, text="接続", command=self.toggle_serial_connection)
        self.connect_btn.grid(row=0, column=4, padx=(10, 0))
        
        self.status_label = ttk.Label(serial_frame, text="未接続", foreground="red")
        self.status_label.grid(row=0, column=5, padx=(10, 0))
        
        # グリッドの重み設定
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)
        left_frame.grid_rowconfigure(7, weight=1)
        left_frame.grid_columnconfigure(1, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # 初期商品リストの表示
        self.update_product_list()
    
    def add_product(self):
        """新しい商品を追加"""
        product_id = self.product_id_entry.get().strip()
        qr_string = self.qr_string_entry.get().strip()
        name = self.name_entry.get().strip()
        price_str = self.price_entry.get().strip()
        
        if not all([product_id, qr_string, name, price_str]):
            messagebox.showerror("エラー", "すべてのフィールドを入力してください")
            return
        
        # 商品IDの重複チェック
        if product_id in self.product_manager.get_all_products():
            messagebox.showerror("エラー", f"商品ID '{product_id}' は既に存在します")
            return
        
        # QRコード文字列の重複チェック
        if self.product_manager.get_product_by_qr_string(qr_string):
            messagebox.showerror("エラー", f"QRコード文字列 '{qr_string}' は既に使用されています")
            return
        
        try:
            price = int(price_str)
            if price <= 0:
                raise ValueError("価格は正の数である必要があります")
        except ValueError as e:
            messagebox.showerror("エラー", f"価格は正の整数で入力してください: {e}")
            return
        
        self.product_manager.add_product(product_id, qr_string, name, price)
        self.update_product_list()
        
        # フォームをクリア
        self.product_id_entry.delete(0, tk.END)
        self.qr_string_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        
        messagebox.showinfo("成功", f"商品 '{name}' を追加しました")
    
    def add_selected_to_cart(self):
        """選択された商品をカートに追加"""
        selected_items = self.product_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "カートに追加する商品を選択してください")
            return
        
        # 選択されたアイテムのインデックスを取得
        for item in selected_items:
            index = self.product_tree.index(item)
            if 0 <= index < len(self.product_manager.get_all_products()):
                # 商品リストから商品IDを取得
                product_ids = list(self.product_manager.get_all_products().keys())
                product_id = product_ids[index]
                product = self.product_manager.get_product(product_id)
                
                if product:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cart_item = {
                        "qr_string": product["qr_string"],
                        "name": product["name"],
                        "price": product["price"],
                        "timestamp": timestamp
                    }
                    
                    self.cart.append(cart_item)
        
        self.update_cart_display()
        self.save_cart_to_csv()
        # messagebox.showinfo("成功", "選択された商品をカートに追加しました")
    
    def update_product_list(self):
        """商品リストを更新"""
        # 既存のアイテムをクリア
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        
        # 商品を追加
        for product_id, product in self.product_manager.get_all_products().items():
            self.product_tree.insert("", tk.END, values=(
                product_id,
                product["qr_string"], 
                product["name"], 
                f"¥{product['price']}"
            ))
    
    def add_to_cart(self, qr_string):
        """カートに商品を追加"""
        product = self.product_manager.get_product_by_qr_string(qr_string)
        if not product:
            messagebox.showwarning("警告", f"未登録のQRコード文字列です: {qr_string}")
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cart_item = {
            "qr_string": qr_string,
            "name": product["name"],
            "price": product["price"],
            "timestamp": timestamp
        }
        
        self.cart.append(cart_item)
        self.update_cart_display()
        self.save_cart_to_csv()
    
    def update_cart_display(self):
        """カートの表示を更新"""
        # 既存のアイテムをクリア
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        
        # カートのアイテムを追加
        total = 0
        for item in self.cart:
            self.cart_tree.insert("", tk.END, values=(
                item["name"], 
                f"¥{item['price']}"
            ))
            total += item["price"]
        
        # 合計金額を更新
        self.total_label.config(text=f"合計金額: ¥{total}")
    
    def delete_selected_item(self):
        """選択された商品を削除"""
        selected_items = self.cart_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "削除する商品を選択してください")
            return
        
        # 選択されたアイテムのインデックスを取得
        for item in selected_items:
            index = self.cart_tree.index(item)
            if 0 <= index < len(self.cart):
                del self.cart[index]
        
        self.update_cart_display()
        self.save_cart_to_csv()
    
    def clear_cart(self):
        """カートをクリア"""
        if not self.cart:
            messagebox.showinfo("情報", "カートは既に空です")
            return
        
        if messagebox.askyesno("確認", "カートをクリアしますか？"):
            self.cart = []
            self.update_cart_display()
    
    def checkout(self):
        """会計完了"""
        if not self.cart:
            messagebox.showwarning("警告", "カートが空です")
            return
        
        total = sum(item["price"] for item in self.cart)
        item_count = len(self.cart)
        
        # 商品の集計
        item_summary = self.get_cart_summary()
        
        # 会計完了の記録をCSVに保存
        self.save_checkout_to_csv(item_count, total, item_summary)
        
        messagebox.showinfo("会計完了", f"合計金額: ¥{total}\n購入物品数: {item_count}個\n\nありがとうございました！")
        
        # カートをクリア
        self.cart = []
        self.update_cart_display()
    
    def save_cart_to_csv(self):
        """カートの内容をCSVファイルに保存"""
        try:
            filename = "会計.csv"
            file_exists = os.path.exists(filename)
            
            # 全商品のリストを取得（ヘッダー用）
            all_products = self.product_manager.get_all_products()
            product_names = [product["name"] for product in all_products.values()]
            
            with open(filename, 'a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # ファイルが新規作成の場合はヘッダーを書き込み
                if not file_exists:
                    header = ['日時', 'データ', '備考', '物品数', '売上金額'] + product_names
                    writer.writerow(header)
                
                # カートの内容を追加
                for item in self.cart:
                    # QRコードスキャンの場合は商品列を空にする
                    empty_product_counts = [""] * len(product_names)
                    # writer.writerow([item["timestamp"], item["qr_string"], "QRコードスキャン", "", ""] + empty_product_counts)
        except Exception as e:
            print(f"CSV保存エラー: {e}")
    
    def get_cart_summary(self):
        """カート内の商品を集計して返す"""
        summary = {}
        for item in self.cart:
            name = item["name"]
            if name in summary:
                summary[name] += 1
            else:
                summary[name] = 1
        return summary
    
    def save_checkout_to_csv(self, item_count, total_amount, item_summary):
        """会計完了の記録をCSVファイルに保存"""
        try:
            filename = "会計.csv"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # ファイルが存在するかチェック
            file_exists = os.path.exists(filename)
            
            # 全商品のリストを取得（ヘッダー用）
            all_products = self.product_manager.get_all_products()
            product_names = [product["name"] for product in all_products.values()]
            
            with open(filename, 'a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # ファイルが新規作成の場合はヘッダーを書き込み
                if not file_exists:
                    header = ['日時', 'データ', '備考', '物品数', '売上金額'] + product_names
                    writer.writerow(header)
                
                # 各商品の数量を配列で作成
                item_counts = []
                for product_name in product_names:
                    count = item_summary.get(product_name, 0)
                    item_counts.append(count)
                
                # 会計完了の記録を追加
                row = [timestamp, "会計完了", "会計処理", item_count, f"{total_amount}"] + item_counts
                writer.writerow(row)
                
        except Exception as e:
            print(f"会計記録CSV保存エラー: {e}")
    
    def toggle_serial_connection(self):
        """シリアル接続の切り替え"""
        if self.serial_reader is None:
            # 接続
            port = self.port_entry.get().strip()
            try:
                baudrate = int(self.baudrate_entry.get().strip())
            except ValueError:
                messagebox.showerror("エラー", "ボーレートは整数で入力してください")
                return
            
            try:
                self.serial_reader = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=1.0
                )
                
                # シリアル読み取りスレッドを開始
                self.serial_thread = threading.Thread(target=self.serial_read_loop, daemon=True)
                self.serial_thread.start()
                
                self.connect_btn.config(text="切断")
                self.status_label.config(text="接続中", foreground="green")
                
            except Exception as e:
                messagebox.showerror("接続エラー", f"シリアルポートに接続できません: {e}")
                self.serial_reader = None
        else:
            # 切断
            if self.serial_reader:
                self.serial_reader.close()
                self.serial_reader = None
            
            self.connect_btn.config(text="接続")
            self.status_label.config(text="未接続", foreground="red")
    
    def serial_read_loop(self):
        """シリアル読み取りループ"""
        while self.serial_reader and self.serial_reader.is_open:
            try:
                if self.serial_reader.in_waiting > 0:
                    line = self.serial_reader.readline()
                    if line:
                        try:
                            decoded_line = line.decode('utf-8').strip()
                            if decoded_line:
                                # GUIスレッドで処理するためにキューに追加
                                self.data_queue.put(decoded_line)
                        except UnicodeDecodeError:
                            pass
            except Exception as e:
                print(f"シリアル読み取りエラー: {e}")
                break
    
    def update_data(self):
        """キューからデータを取得してGUIを更新"""
        try:
            while True:
                qr_string = self.data_queue.get_nowait()
                self.add_to_cart(qr_string)
        except queue.Empty:
            pass
        
        # 100ms後に再度チェック
        self.root.after(100, self.update_data)
    
    def run(self):
        """アプリケーションを実行"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("アプリケーションを終了します...")
        finally:
            if self.serial_reader:
                self.serial_reader.close()

def main():
    """メイン関数"""
    app = CashRegisterApp()
    app.run()

if __name__ == "__main__":
    main()
