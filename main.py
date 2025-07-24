import asyncio
import websockets
import requests
import json
import sounddevice as sd
import numpy as np
import threading
import time
import queue
import os
from dotenv import load_dotenv

# --- 載入環境變數 ---
load_dotenv()
YATING_ASR_API_KEY = os.getenv("YATING_ASR_API_KEY")
HACKMD_API_TOKEN = os.getenv("HACKMD_API_TOKEN")
HACKMD_NOTE_ID = os.getenv("HACKMD_NOTE_ID")

if not all([YATING_ASR_API_KEY, HACKMD_API_TOKEN, HACKMD_NOTE_ID]):
    print("錯誤：請檢查 .env 檔案，確保所有金鑰和筆記 ID 都已設定。")
    exit()

# --- 全域變數和設定 ---
ASR_TOKEN_URL = "https://asr.api.yating.tw/v1/token"
ASR_WS_URL = "wss://asr.api.yating.tw/ws/v1/"
HACKMD_API_URL = f"https://api.hackmd.io/v1/notes/{HACKMD_NOTE_ID}"

SAMPLE_RATE = 16000  # 音頻採樣率 (Hz)
CHANNELS = 1         # 單聲道
DTYPE = 'int16'      # 每個樣本 16 bits
BUFFER_SIZE = 2000   # 每個音頻塊大小 (bytes)
CHUNK_DURATION = BUFFER_SIZE / (SAMPLE_RATE * CHANNELS * (np.dtype(DTYPE).itemsize)) # 大約 1/16 秒

# 狀態資訊
network_status = "連線中..."
audio_device_name = "未偵測到"
audio_waveform_present = False
latest_transcript = ""

# 音頻數據緩衝區
audio_queue = queue.Queue()

# --- 新增 HackMD 相關變數 ---
# 用於儲存所有已完成的句子，這就是我們 HackMD 筆記的真實內容
full_hackmd_transcript = ""
# 用於臨時儲存未 final 的語音轉文字結果，方便顯示在終端機
current_sentence_buffer = ""
# 上次更新 HackMD 的時間戳
last_hackmd_update_time = time.time()
# 更新 HackMD 的頻率 (秒)
HACKMD_UPDATE_INTERVAL = 5 # 每隔 5 秒更新一次 HackMD 筆記，避免頻繁寫入

# --- 輔助函數 ---
def update_status_display():
    """更新並顯示程式狀態"""
    os.system('cls' if os.name == 'nt' else 'clear') # 清空終端機畫面
    print("--- ASR 即時語音轉文字至 HackMD ---")
    print(f"網路連線狀態: {network_status}")
    print(f"使用音源名稱: {audio_device_name}")
    print(f"是否有收錄到聲音波形: {'有' if audio_waveform_present else '無'}")
    print("\n--- 語音轉文字結果 (即時顯示，未確定句子) ---")
    # 顯示目前正在識別的句子，如果已經有確定句子，則顯示確定句子
    print(latest_transcript if latest_transcript else current_sentence_buffer)
    print("\n--- HackMD 筆記內容 (已確定句子) ---")
    # 這裡顯示的是準備寫入 HackMD 的完整內容（或者至少是已確定的部分）
    print(full_hackmd_transcript[-500:]) # 為了避免顯示過長，只顯示最後 500 字
    print("\n-------------------------------------")
    print("按下 Ctrl+C 結束程式...")

async def get_asr_token():
    """獲取雅婷 ASR 服務的一次性 Token"""
    global network_status
    headers = {
        "Content-Type": "application/json",
        "key": YATING_ASR_API_KEY
    }
    # 根據文件，pipeline 是 "asr-zh-en-std" (國語與英文混雜)
    # 您可以根據需求選擇其他語言代碼，例如 "asr-zh-tw-std" (國語與台語混雜)
    payload = {
        "pipeline": "asr-zh-en-std",
        "options": {} # 可以加入客製化語言模型 ID，如果有的話
    }
    try:
        response = requests.post(ASR_TOKEN_URL, headers=headers, json=payload, timeout=5)
        response.raise_for_status() # 檢查 HTTP 錯誤
        token_data = response.json()
        if token_data.get("success"):
            network_status = "連線正常"
            return token_data.get("auth_token")
        else:
            network_status = f"Token 獲取失敗: {token_data.get('message', '未知錯誤')}"
            return None
    except requests.exceptions.RequestException as e:
        network_status = f"網路連線錯誤: {e}"
        return None

def audio_callback(indata, frames, time, status):
    """sounddevice 的回調函數，將音頻數據放入佇列"""
    global audio_waveform_present
    if status:
        print(f"錄音警告: {status}")
    # 檢查是否有音量，簡單判斷是否有波形
    if np.max(np.abs(indata)) > 0.01: # 設定一個閾值來判斷是否有聲音
        audio_waveform_present = True
    else:
        audio_waveform_present = False
    audio_queue.put(indata.tobytes())

async def send_audio_to_asr(websocket):
    """從佇列中取出音頻數據並發送到 ASR 服務"""
    while True:
        try:
            audio_chunk = await asyncio.to_thread(audio_queue.get, timeout=1) # 等待音頻數據，最長等待1秒
            await websocket.send(audio_chunk)
        except queue.Empty:
            # 如果佇列為空，可以稍微等待，避免過度佔用 CPU
            await asyncio.sleep(0.01)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket 連線已關閉，停止發送音頻。")
            break
        except Exception as e:
            print(f"發送音頻時發生錯誤: {e}")
            break

async def receive_asr_results(websocket):
    """從 ASR 服務接收語音轉文字結果"""
    global latest_transcript, full_hackmd_transcript, current_sentence_buffer, last_hackmd_update_time
    try:
        async for message in websocket:
            data = json.loads(message)
            # print(f"接收到 ASR 訊息: {data}") # 用於偵錯

            if "pipe" in data:
                pipe_data = data["pipe"]
                if "asr_sentence" in pipe_data:
                    current_sentence_buffer = pipe_data["asr_sentence"] # 這是即時變動的結果
                    latest_transcript = current_sentence_buffer # 用於顯示在終端機

                    if pipe_data.get("asr_final"):
                        # 句子結束，將最終結果追加到 full_hackmd_transcript
                        full_hackmd_transcript += current_sentence_buffer + "\n"
                        latest_transcript = "" # 清空即時顯示，等待下一個句子
                        current_sentence_buffer = "" # 清空當前句子緩衝
                        print(f"偵測到完整句子並加入 HackMD 緩衝: {full_hackmd_transcript.strip()}")
                        # 立即嘗試更新 HackMD 確保最終句子寫入
                        await update_hackmd_note()
                        last_hackmd_update_time = time.time() # 更新時間戳，避免短時間內重複更新
                elif pipe_data.get("asr_state") == "utterance_end":
                    # 偵測到句子結束，但可能 asr_final 已處理
                    # 如果 asr_final 沒有觸發，但 utterance_end 觸發了，我們也應該把當前緩衝加入
                    if current_sentence_buffer and not pipe_data.get("asr_final"):
                         full_hackmd_transcript += current_sentence_buffer + "\n"
                         latest_transcript = ""
                         current_sentence_buffer = ""
                         print(f"偵測到句子結束並加入 HackMD 緩衝: {full_hackmd_transcript.strip()}")
                         await update_hackmd_note()
                         last_hackmd_update_time = time.time()


            elif "status" in data and data["status"] == "ok":
                print("ASR WebSocket 連線成功，可以開始傳送音頻。")
            elif "status" in data and data["status"] == "error":
                print(f"ASR 服務錯誤: {data.get('detail', '未知錯誤')}")
                break

            # 定時更新 HackMD，即使沒有 asr_final 的結果（可以減少空白行）
            current_time = time.time()
            if current_time - last_hackmd_update_time >= HACKMD_UPDATE_INTERVAL:
                # 在這裡，我們只會傳送已經確定為 final 的內容
                # 因為 asr_final 時會立即觸發更新，所以這裡的定時更新更多是作為 fallback
                # 或者用於定期清空 full_hackmd_transcript 以免過長
                if full_hackmd_transcript.strip(): # 只有在有內容時才更新
                    await update_hackmd_note()
                    last_hackmd_update_time = current_time

    except websockets.exceptions.ConnectionClosed as e:
        print(f"ASR WebSocket 連線關閉: {e}")
    except json.JSONDecodeError as e:
        print(f"解析 ASR 訊息失敗: {e}, 訊息內容: {message}")
    except Exception as e:
        print(f"接收 ASR 結果時發生錯誤: {e}")

async def update_hackmd_note():
    """更新 HackMD 筆記內容"""
    global network_status, full_hackmd_transcript
    if not full_hackmd_transcript.strip(): # 如果緩衝區為空，不進行更新
        return

    headers = {
        "Authorization": f"Bearer {HACKMD_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        # 將所有已經確定的句子發送給 HackMD API
        "content": full_hackmd_transcript.strip()
    }
    try:
        response = requests.patch(HACKMD_API_URL, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        print(f"HackMD 更新成功！ 已寫入: \n{full_hackmd_transcript.strip()}") # 用於偵錯
        # HackMD PATCH API 會替換整個內容。因此，每次成功更新後，
        # 我們已經將 full_hackmd_transcript 的內容寫入，所以不再需要清空。
        # 這樣下次更新時，full_hackmd_transcript 會持續增長。
        network_status = "連線正常"
    except requests.exceptions.RequestException as e:
        network_status = f"HackMD API 錯誤: {e}"
        print(f"HackMD API 錯誤: {e}")

# --- 主程式 ---
async def main():
    global audio_device_name, network_status

    # 顯示預設狀態
    update_status_display()

    # 獲取音頻設備資訊
    try:
        devices = sd.query_devices()
        input_devices = [d for d in devices if d['max_input_channels'] > 0]
        if input_devices:
            default_input_device_index = sd.default.device[0]
            if default_input_device_index is not None and default_input_device_index < len(devices):
                audio_device_name = devices[default_input_device_index]['name']
            else:
                audio_device_name = "預設音源" # 如果找不到具體名稱
        else:
            audio_device_name = "無輸入音源"
            print("錯誤：未偵測到任何音頻輸入設備。請檢查麥克風連接。")
            return
    except Exception as e:
        audio_device_name = f"偵測失敗: {e}"
        print(f"偵測音頻設備時發生錯誤: {e}")
        return

    # 定時更新狀態顯示
    status_display_task = asyncio.create_task(
        asyncio.to_thread(lambda: [time.sleep(0.5) or update_status_display() for _ in iter(int, 1)])
    ) # 每 0.5 秒更新一次顯示

    while True:
        token = await get_asr_token()
        if not token:
            print("無法取得 ASR Token，請檢查您的金鑰或網路連線。5 秒後重試...")
            await asyncio.sleep(5)
            continue

        try:
            # 建立 WebSocket 連線
            uri = f"{ASR_WS_URL}?token={token}"
            async with websockets.connect(uri, ping_interval=None) as websocket: # 禁用 ping_interval 讓服務器端控制心跳包
                print("ASR WebSocket 連線成功，開始錄音並傳送音頻...")

                # 啟動錄音串流
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
                                    blocksize=int(BUFFER_SIZE / np.dtype(DTYPE).itemsize), # sounddevice 的 blocksize 是指樣本數
                                    callback=audio_callback):
                    send_task = asyncio.create_task(send_audio_to_asr(websocket))
                    receive_task = asyncio.create_task(receive_asr_results(websocket))

                    # 等待兩個任務完成，或者直到手動停止
                    await asyncio.gather(send_task, receive_task)

        except websockets.exceptions.ConnectionClosedOK:
            print("ASR WebSocket 連線正常關閉。")
        except websockets.exceptions.WebSocketException as e:
            print(f"ASR WebSocket 連線錯誤: {e}。5 秒後重試...")
            network_status = f"WebSocket 連線錯誤: {e}"
            await asyncio.sleep(5)
        except Exception as e:
            print(f"主程式發生未預期錯誤: {e}。5 秒後重試...")
            network_status = f"未預期錯誤: {e}"
            await asyncio.sleep(5)

# 執行主程式
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程式已終止。")
    except Exception as e:
        print(f"程式執行時發生錯誤: {e}")