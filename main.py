import sys
import asyncio
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont
from playwright.async_api import async_playwright
import threading

# --------------------------
# シグナル定義
# --------------------------
class WorkerSignals(QObject):
    progress = pyqtSignal(int, int)  # 完了数, 総数
    result = pyqtSignal(str, bool)   # channel_id, 成功か

# --------------------------
# PlaywrightでチャンネルID取得
# --------------------------
async def fetch_channel(browser, url):
    try:
        page = await browser.new_page()
        await page.goto("https://seostudio.tools/ja/youtube-channel-id")
        await page.fill("input[placeholder='https://...']", url)
        await page.click("button:has-text('今すぐ検索')")
        await page.wait_for_selector("div.alert.alert-important.alert-success", timeout=10000)
        text = await page.inner_text("div.alert.alert-important.alert-success")
        await page.close()
        channel_id = text.split("チャンネルID:")[-1].strip() if "チャンネルID:" in text else "取得失敗"
        success = channel_id != "取得失敗"
    except Exception:
        channel_id = "取得失敗"
        success = False
    return channel_id, success

async def fetch_all(urls, signals: WorkerSignals):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        tasks = [fetch_channel(browser, url.strip()) for url in urls if url.strip()]
        results = await asyncio.gather(*tasks)
        for (cid, success) in results:
            signals.result.emit(cid, success)
            signals.progress.emit(1, len(urls))
        await browser.close()

# --------------------------
# GUI
# --------------------------
class YouTubeIDTool(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube チャンネルID 並行取得ツール")
        self.resize(700, 650)
        self.signals = WorkerSignals()
        self.signals.progress.connect(self.update_progress)
        self.signals.result.connect(self.add_result)
        self.total = 0
        self.done = 0
        self.font16 = QFont("Arial", 14)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("background-color: #1E1E1E; color: white;")
        layout = QVBoxLayout()

        self.label = QLabel("複数チャンネルURLを改行区切りで入力:")
        self.label.setFont(self.font16)
        layout.addWidget(self.label)

        self.text_area = QTextEdit()
        self.text_area.setFixedHeight(150)
        self.text_area.setStyleSheet("background-color: #2C2C2C; color: white;")
        self.text_area.setFont(self.font16)
        layout.addWidget(self.text_area)

        self.search_button = QPushButton("一括検索")
        self.search_button.setFont(self.font16)
        self.search_button.setStyleSheet("""
            QPushButton {background-color: #00BFFF; color: white; font-weight: bold; height:40px;}
            QPushButton:hover {background-color: #1E90FF;}
        """)
        self.search_button.clicked.connect(self.run_scraping)
        layout.addWidget(self.search_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {background-color: #2C2C2C; color: white; border: 1px solid #00BFFF;}
            QProgressBar::chunk {background-color: #00BFFF;}
        """)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("0/0 件完了…")
        self.progress_label.setFont(self.font16)
        layout.addWidget(self.progress_label)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {background-color: #2C2C2C; color: white;}
            QListWidget::item:selected {background-color: #00BFFF; color: white;}
        """)
        self.list_widget.setFont(self.font16)
        self.list_widget.itemDoubleClicked.connect(self.copy_selected)
        layout.addWidget(self.list_widget)

        self.copy_button = QPushButton("選択IDをコピー")
        self.copy_button.setFont(self.font16)
        self.copy_button.setStyleSheet("""
            QPushButton {background-color: #00BFFF; color: white; font-weight: bold; height:40px;}
            QPushButton:hover {background-color: #1E90FF;}
        """)
        self.copy_button.clicked.connect(self.copy_selected)
        layout.addWidget(self.copy_button)

        self.setLayout(layout)

    # --------------------------
    # 並行処理開始
    # --------------------------
    def run_scraping(self):
        urls = self.text_area.toPlainText().strip().split("\n")
        urls = [u for u in urls if u.strip()]
        if not urls:
            QMessageBox.warning(self, "注意", "URLを入力してください！")
            return

        self.list_widget.clear()
        self.total = len(urls)
        self.done = 0
        self.progress_bar.setMaximum(self.total)
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"0/{self.total} 件完了…")

        threading.Thread(target=self.worker_thread, args=(urls,), daemon=True).start()

    def worker_thread(self, urls):
        asyncio.run(fetch_all(urls, self.signals))

    # --------------------------
    # GUI更新
    # --------------------------
    def update_progress(self, done_increment, total):
        self.done += done_increment
        self.progress_bar.setValue(self.done)
        self.progress_label.setText(f"{self.done}/{total} 件完了…")

    def add_result(self, channel_id, success):
        item = QListWidgetItem(channel_id)
        item.setForeground(Qt.GlobalColor.cyan if success else Qt.GlobalColor.red)
        self.list_widget.addItem(item)

    def copy_selected(self):
        selected = self.list_widget.currentItem()
        if not selected:
            QMessageBox.warning(self, "注意", "コピーするIDを選択してください！")
            return
        QApplication.clipboard().setText(selected.text())
        QMessageBox.information(self, "コピー", f"チャンネルID '{selected.text()}' をコピーしました！")

# --------------------------
# 実行
# --------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeIDTool()
    window.show()
    sys.exit(app.exec())
