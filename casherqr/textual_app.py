#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Textual を使った簡易 QR 管理 TUI

機能:
- QR 文字列を入力して表に追加
- 選択行を削除するボタン
- 追加/削除のたびに `会計.csv` を更新

使い方:
  python textual_app.py

"""
from datetime import datetime
import os
import csv

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Header, Footer, Button, Input, DataTable, Static


CSV_FILENAME = "会計.csv"


class QRApp(App):
    CSS_PATH = None
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("QRコード文字列を入力して [Add] を押すと表に追加されます。行を選択して [Delete Selected] で削除できます。", id="help")
        with Horizontal():
            yield Input(placeholder="ここにQR文字列を入力", id="qr_input")
            yield Button("Add", id="add_btn")
            yield Button("Delete Selected", id="del_btn")
        yield DataTable(id="table")
        yield Footer()

    def on_mount(self) -> None:
        self.table: DataTable = self.query_one("#table")
        # 列定義
        self.table.add_column("日時", key="timestamp", width=24)
        self.table.add_column("データ", key="data")

        # 内部データ保持（テーブル行の順序を同期するため）
        self.rows: list[dict] = []

        # CSV を読み込んで初期表示
        if os.path.exists(CSV_FILENAME):
            try:
                with open(CSV_FILENAME, newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        timestamp = r.get("日時") or r.get("timestamp") or ""
                        data = r.get("データ") or r.get("data") or ""
                        if timestamp or data:
                            self._append_row(timestamp, data, write_csv=False)
            except Exception:
                # 読み込み失敗しても TUI は起動させる
                pass

    # ユーティリティ: テーブルと内部リストに行を追加
    def _append_row(self, timestamp: str, data: str, write_csv: bool = True) -> None:
        self.rows.append({"timestamp": timestamp, "data": data})
        # DataTable.add_row は内部で行キーを振る。index を使って削除できる。
        self.table.add_row(timestamp, data)
        if write_csv:
            self._write_csv()

    # CSV を上書きして現在の rows を保存
    def _write_csv(self) -> None:
        try:
            with open(CSV_FILENAME, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["日時", "データ", "備考"])
                for r in self.rows:
                    writer.writerow([r.get("timestamp", ""), r.get("data", ""), "QRコードスキャン"])
        except Exception as e:
            # ファイル書き込み失敗はログとし、UI 上には簡易メッセージ表示
            self.notify(f"CSV書き込みエラー: {e}")

    # ボタン押下イベント
    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "add_btn":
            input_widget: Input = self.query_one("#qr_input")
            text = (input_widget.value or "").strip()
            if not text:
                self.notify("追加するQR文字列を入力してください。")
                return
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._append_row(timestamp, text, write_csv=True)
            input_widget.value = ""
        elif btn_id == "del_btn":
            # 現在ハイライトされている行の index を取得
            # DataTable では cursor_row を使って現在行 index を得られる
            try:
                cursor = self.table.cursor_row
            except Exception:
                cursor = None

            if cursor is None or cursor < 0 or cursor >= len(self.rows):
                self.notify("削除する行を表で選択してください。")
                return

            # 内部リストから削除し、テーブルの同じ index の行を削除
            try:
                del self.rows[cursor]
                self.table.remove_row(cursor)
                self._write_csv()
            except Exception as e:
                self.notify(f"削除エラー: {e}")

    def notify(self, message: str) -> None:
        # 画面下部に一時メッセージを表示するために Footer のメッセージを変更
        footer: Footer = self.query_one(Footer)
        footer.update(message)


if __name__ == "__main__":
    app = QRApp()
    app.run()
