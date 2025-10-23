#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COM9シリアルデバイス読み取りの簡単実行スクリプト
"""

from serial_reader import SerialReader
import time

def simple_read():
    """シンプルな読み取り実行"""
    print("COM9シリアルデバイス読み取りプログラム")
    print("=" * 50)
    
    # シリアルリーダーを作成（デフォルト設定）
    reader = SerialReader(port='COM9', baudrate=9600, timeout=1)
    
    try:
        # 接続
        print("COM9に接続中...")
        if not reader.connect():
            print("エラー: COM9に接続できませんでした")
            return
        
        print("接続成功！データ読み取りを開始します...")
        print("終了するには Ctrl+C を押してください")
        print("-" * 50)
        
        # 連続読み取り
        reader.read_continuous()
        
    except KeyboardInterrupt:
        print("\nプログラムを終了します...")
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    finally:
        reader.disconnect()

if __name__ == "__main__":
    simple_read()
