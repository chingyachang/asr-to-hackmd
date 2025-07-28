
# 語音即時轉文字至 HackMD 筆記 (ASR-to-HackMD)

這是一個 Python 應用程式，它能夠即時地將您的語音轉化為文字，並透過 HackMD API 將這些文字即時同步到您指定的 HackMD 筆記中。此工具特別適用於會議記錄、口述筆記或任何需要將語音內容快速轉化為文字並共享的場景。

## 功能特色

* **即時語音轉文字 (ASR)**：利用台灣人工智慧實驗室 (Taiwan AI Labs) 的雅婷語音轉文字服務，提供高品質的語音識別。
* **HackMD 即時同步**：將識別到的文字內容即時更新到指定的 HackMD 筆記中，方便共編與共享。
* **智能斷句與換行**：在語音停頓（被識別為完整句子）後，自動在 HackMD 筆記中新增空行，使內容更易閱讀。
* **狀態顯示**：程式執行時會顯示重要的狀態資訊，包括網路連接狀態、使用的音源設備名稱，以及是否有收錄到聲音波形。
* **本地運行**：可在您的本機端（macOS）運行。

## 系統需求

* macOS 作業系統
* Python 3.9+
* 麥克風輸入裝置
* 網路連接

## 環境設定與安裝

請依照以下步驟設定您的開發環境並安裝必要的套件：

### 1. 安裝 Python 與 pip (若尚未安裝)

macOS 通常內建 Python，但建議安裝最新版本並使用 Homebrew 進行管理。

```bash
# 安裝 Homebrew (如果尚未安裝)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安裝 Python 3
brew install python

# 確認 Python 3 和 pip3 已安裝
python3 --version
pip3 --version
````

### 2\. 安裝 VS Code

若您尚未安裝 VS Code，請從 [Visual Studio Code 官方網站](https://code.visualstudio.com/) 下載並安裝。

安裝後，請在 VS Code 中設定 `code` 命令到 PATH：
開啟 VS Code -\> 按下 `Cmd + Shift + P` -\> 輸入 `shell command` -\> 選擇 `Shell Command: Install 'code' command in PATH`。完成後請重啟您的終端機。

### 3\. 安裝必要的 Python 套件

開啟終端機，切換到您的專案資料夾後，執行以下指令：

```bash
pip3 install websockets requests python-dotenv sounddevice numpy
```

### 4\. 取得 API 金鑰與設定 HackMD 筆記

您需要以下兩個 API 金鑰及一個 HackMD 筆記 ID：

  * **雅婷語音轉文字服務 API 金鑰 (Yating ASR API Key)**：從台灣人工智慧實驗室的雅婷語音轉文字服務平台申請。
  * **HackMD API Token**：登入您的 HackMD 帳號，前往 `設定` -\> `整合應用` -\> `個人存取令牌`，生成一個具有 `write` 權限的 Token。
  * **HackMD 筆記 ID**：打開您希望同步文字的 HackMD 筆記，網址中的末端路徑即為筆記 ID (例如：`https://hackmd.io/@username/NOTE_ID` 中的 `NOTE_ID`)。
[雅婷語音轉文字服務 API 金鑰](https://developer.yating.tw/zh-TW/doc/asr-ASR%20%E5%8D%B3%E6%99%82%E8%AA%9E%E9%9F%B3%E8%BD%89%E6%96%87%E5%AD%97)
### 5\. 配置 `.env` 環境變數檔案

在您的專案根目錄下（與 `main.py` 同一層），創建一個名為 `.env` 的檔案，並填入您取得的金鑰和筆記 ID：

```
YATING_ASR_API_KEY="您的雅婷語音轉文字服務 API 金鑰"
HACKMD_API_TOKEN="您的HackMD API Token"
HACKMD_NOTE_ID="您要寫入的HackMD筆記ID"
```

**請注意：`.env` 檔案包含敏感資訊，不應上傳到公共儲存庫。本專案的 `.gitignore` 已包含此設定。**

## 運行程式

1.  **開啟終端機**，切換到您的專案根目錄：

    ```bash
    cd /path/to/your/asr-to-hackmd-project
    ```

    (請將 `/path/to/your/asr-to-hackmd-project` 替換為您專案的實際路徑，例如 `cd ~/asr-to-hackmd`)

2.  **執行 Python 程式：**

    ```bash
    python3 main.py
    ```

程式啟動後，您將在終端機看到即時狀態更新。對著麥克風說話，語音將被即時識別並同步到您的 HackMD 筆記中。

## 注意事項

  * 首次運行程式時，macOS 會彈出麥克風權限請求，請務必允許。
  * 確保您的網路連接穩定。
  * 雅婷語音轉文字服務的 `pipeline` 預設為 `asr-zh-en-std` (國語與英文混雜)，您可以在 `main.py` 中根據需求修改此設定。
  * HackMD API 的頻繁寫入可能會受到速率限制，但本程式已內建一些緩衝與檢查機制以減少不必要的請求。

## 貢獻

歡迎任何形式的貢獻！如果您有任何建議或發現 Bug，請隨時提出 Issue 或提交 Pull Request。

