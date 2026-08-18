# 🚀 CyDrive

<div align="center">

![CyDrive Banner](https://raw.githubusercontent.com/icynetx/CyDrive/main/assets/banner.png)

### **Infinite Cloud Storage Engine & Virtual Drive for Windows via Telegram**
Developed with ❤️ by **[Cynet Security Team](https://cynetx.ir)**

[![GitHub Repo](https://img.shields.io/badge/GitHub-CyDrive-181717?logo=github&style=for-the-badge)](https://github.com/icynetx/CyDrive)
[![Python Version](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white&style=for-the-badge)](https://python.org)
[![Telegram MTProto](https://img.shields.io/badge/Telegram-MTProto%20(Telethon)-26A5E4?logo=telegram&logoColor=white&style=for-the-badge)](https://telegram.org)
[![WebDAV](https://img.shields.io/badge/Protocol-WebDAV-FFA500?style=for-the-badge)](https://en.wikipedia.org/wiki/WebDAV)
[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg?style=for-the-badge)](LICENSE)

[English](#-about-cydrive) • [فارسی](#-درباره-cydrive) • [Installation](#-installation--quick-start) • [Map Windows Drive](#-how-to-map-as-a-windows-drive) • [Troubleshooting](#-windows-webdav-size-limit-fix)

</div>

---

## 📖 About CyDrive

**CyDrive** is a two-way synchronization bridge and virtual cloud drive engine. It connects your local Windows environment directly to Telegram's unlimited cloud storage infrastructure and exposes it as a **Native Windows Network Drive (e.g. `Y:` or `Z:`)** using the **WebDAV** protocol.

No complex virtual file system drivers (like Dokany or WinFsp) required! Windows natively connects to CyDrive's WebDAV engine.

---

## ✨ Features

- 🔄 **Real-Time Two-Way Sync:**
  - Files dropped into your local Windows Drive are uploaded instantly to your private Telegram storage.
  - Files and media sent to your Telegram Bot are automatically downloaded directly to your local drive.
- 📁 **Native Windows Explorer Drive:** Mount your Telegram storage directly as `Y:` or `Z:` drive in **This PC**.
- 🚀 **2GB Single File Limit:** Powered by Telethon and Telegram MTProto (bypassing standard HTTP Bot API limitations).
- 🧩 **Zero Driver Dependencies:** Uses standard HTTP/WebDAV protocol supported out-of-the-box by Windows Explorer.
- 🔒 **Private & Isolated:** Direct client-to-Telegram communication without third-party middleman servers.
- ⚙️ **Interactive Setup:** Automatically generates configuration and remembers bot credentials securely.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Telegram Cloud
        TG["Telegram Bot / Private Chat\n(Unlimited Cloud Storage)"]
    end

    subgraph CyDrive Engine
        SYNC["Telethon MTProto Engine\n(Two-Way Async Sync)"]
        LOCAL["Local Cache\n(./Telegram_Drive)"]
        WEBDAV["WsgiDAV + Cheroot Server\n(http://127.0.0.1:8080)"]
    end

    subgraph Windows System
        EXPLORER["Windows File Explorer\n(Network Drive Y:)"]
    end

    TG <-->|MTProto (Up to 2GB)| SYNC
    SYNC <-->|Auto Sync| LOCAL
    LOCAL <-->|File Provider| WEBDAV
    WEBDAV <-->|WebDAV Protocol| EXPLORER
```

---

## 📦 Installation & Quick Start

### 1. Prerequisites
- **Python 3.8+** installed on your system.
- A Telegram account and a Telegram Bot Token (from [@BotFather](https://t.me/BotFather)).
- Your Telegram User ID or Chat ID (obtainable from [@userinfobot](https://t.me/userinfobot)).

### 2. Clone the Repository
```bash
git clone https://github.com/icynetx/CyDrive.git
cd CyDrive
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run CyDrive
```bash
python tgdrive.py
```
> On the first run, the interactive wizard will ask for your **Bot Token** and **Target Chat ID**, then save them in `config.json`.

---

## 🖥️ How to Map as a Windows Drive

Once CyDrive is running, map it as a persistent drive in Windows:

### Method 1: Using Windows Explorer (GUI)
1. Open **This PC** (File Explorer).
2. Click the **three dots (`...`)** on the top menu (or right-click *This PC*) and select **Map network drive**.
3. Choose a Drive Letter (e.g. `Y:` or `Z:`).
4. In the **Folder** field, enter:
   ```text
   http://127.0.0.1:8080
   ```
5. Check **Reconnect at sign-in** and click **Finish**.

### Method 2: Using Command Prompt / PowerShell
Run this command in terminal:
```cmd
net use Y: http://127.0.0.1:8080 /persistent:yes
```

---

## ⚙️ Windows WebDAV File Size Limit Fix

By default, Windows WebDAV client limits single file transfers to **50 MB**. To allow large files (up to 2GB/4GB), adjust the registry:

### Quick PowerShell Fix (Run as Administrator):
```powershell
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\WebClient\Parameters" -Name "FileSizeLimitInBytes" -Value 4294967295 -Type DWord
Restart-Service WebClient
```
*(Or manually navigate in `regedit` to `HKLM\SYSTEM\CurrentControlSet\Services\WebClient\Parameters`, change `FileSizeLimitInBytes` to `ffffffff` Hexadecimal / `4294967295` Decimal, and restart the `WebClient` service).*

---

## 📁 Project Structure

```text
CyDrive/
├── tgdrive.py              # Main application entry point (Telegram Sync + WebDAV)
├── requirements.txt        # Python package dependencies
├── config.example.json     # Configuration template
├── .gitignore              # Files & directories to ignore in Git
├── LICENSE                 # MIT License
└── README.md               # Project documentation
```

---

## 🇮🇷 درباره CyDrive (فارسی)

پروژه **CyDrive** یک سیستم درایو ابری نامحدود و امن بر بستر تلگرام برای ویندوز است. با استفاده از این ابزار:
- فضای چت یا ربات تلگرام شما به صورت مستقیم به یک **درایو تحت شبکه (مانند درایو `Y:`)** در ویندوز اکسپلورر تبدیل می‌شود.
- انتقال فایل‌ها به صورت دوطرفه (Two-Way) انجام می‌شود؛ یعنی با کشیدن فایل در درایو ویندوز، فایل بلافاصله در تلگرام آپلود می‌شود و هر فایلی که در تلگرام بفرستید درون درایو ویندوز شما دانلود می‌شود.
- این ابزار بر پایه کلاینت MTProto تلگرام توسعه یافته و از فایل‌های با حجم حداکثر ۲ گیگابایت پشتیبانی می‌کند.

---

## 🤝 Contributing

Contributions, bug reports, and feature requests are welcome!
Feel free to open an issue or submit a pull request on GitHub.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 🛡️ License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

## 🌐 Connect with Us

- **Organization:** [Cynet Security Team](https://cynetx.ir)
- **GitHub:** [@icynetx](https://github.com/icynetx)
- **Repository:** [https://github.com/icynetx/CyDrive](https://github.com/icynetx/CyDrive)
- **Contact:** [heyfiranam@gmail.com](mailto:heyfiranam@gmail.com)
