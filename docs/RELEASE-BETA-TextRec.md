# TongSheng 1.1.11-beta — Text-to-Audio mode / 文字录音模式

**Beta branch:** `TongSheng-1.1.11-beta-TextRec_mode` (commit `dc0d0ac`)
**Package:** `TongSheng-1.1.11-beta-TextRec_mode-update.zip` — 0.49 MB, code-only overlay
**Base requirement:** an installed **TongSheng 1.1.11** (full package)
**SHA256:** `1096cd909501110000ff7241b241e53e4a54fc033a50f889b87bf982a4b0ae69`

---

## English

### What this beta adds

A second working mode: type text instead of speaking it, and get the translated speech saved as a WAV file.

- **Mode switch in the header** — one button, right of *Voice model training* (`声音模型训练`). It shows the current mode; click it to switch. The caption below reads *Switch mode*.
- **Visual mode cue** — voice mode keeps the original blue-tinted dark theme; text mode shifts to a subtle emerald dark theme, so the active mode is recognisable at a glance without leaving the dark palette.
- **Text input instead of the record switch** — the *Save synthesised audio* row becomes a three-line, scrollable text box (same styling as the transcript). `Ctrl+Enter` submits, `Enter` inserts a newline.
- **Automatic input-language detection** — Kana → Japanese, Hangul → Korean, Han → Chinese, otherwise English. The speech front-end accepts zh / en / ja / ko / yue.
- **开始录转译音 (Start text recording)** replaces *Start talking*; the result is written to `results\rec-text\YYYYmmdd-HHMMSS-48k.wav` (48 kHz PCM WAV) and played back in your cloned voice.
- **输入语言 → 界面语言** — in text mode this toggle only switches the interface language (zh / en); it no longer touches the recogniser.
- **ASR is released while in text mode** (engine closed, CUDA cache emptied) and reloaded + warmed automatically when you switch back to voice mode.
- The microphone level meter and the warm-up button are hidden in text mode (no capture is involved).

### Fixed in this beta

- **Output language was ignored for Chinese** — with *Output language = 中文* and Chinese input, the text was force-translated to English and spoken in English. An explicit output language now always wins; only an empty setting falls back to the opposite language.
- **Upgrade guard was too broad** — the overlay aborted if *any* `pythonw.exe` was running. It now only checks for a process started from **this** installation directory.

### How to install

1. Quit TongSheng from the tray.
2. Extract `TongSheng-1.1.11-beta-TextRec_mode-update.zip` into a subfolder of the install directory, for example:
   `D:\TongSheng\TongSheng-1.1.11-beta-TextRec_mode\`
3. Run `apply_update.bat` inside that folder. It prints `Installed version: 1.1.11`.
4. Start TongSheng and open **Self-test** from the Start menu — all ten checks must pass.

The overlay replaces program code, tools and documentation only. Models, `config.yaml`, recordings and your trained voices (`voice-repository`) are left untouched, and nothing is deleted.

### Known limitations

- Text mode has no speech recognition at all; the ASR model is unloaded on purpose.
- Translation still goes through the bundled local llama.cpp servers, which the app starts automatically when needed.
- Language detection is script based, so mixed-language text may be attributed to the dominant script.
- The beta is distributed as a code overlay only — do not use it to set up a fresh machine; install 1.1.11 first.

---

## 中文

### 这个 beta 增加什么

第二个工作模式：不打字说话，而是**输入文字**，得到译文的语音并保存为 WAV 文件。

- **头部模式切换**——「声音模型训练」右侧只有一个按钮，按钮上显示当前模式，点击即切换；下方标注「模式切换」。
- **配色即状态**——语音输入模式保持原来的蓝调暗色；文字录音模式整体微偏翠绿，不看文字也能感知当前模式，两者都仍是暗色主题。
- **录音开关变文字框**——「保存合成音频（录音）」这一行变成 **3 行高、可滚动**的文字输入框（与下方文字呈现区同款样式）。`Ctrl+Enter` 提交，`Enter` 换行。
- **自动识别输入语种**——假名→日文、谚文→韩文、汉字→中文、其余→英文；语音前端支持 中文 / English / 日本語 / 한국어 / 粤语。
- **「开始录转译音」** 取代「开始说话」，结果写入 `results\rec-text\YYYYmmdd-HHMMSS-48k.wav`（48 kHz PCM），并用克隆音色播放。
- **「输入语言」改为「界面语言」**——文字模式下该开关只切换界面语言（中 / 英），不再动识别引擎。
- **进入文字模式即释放 ASR**（关闭引擎 + 清 CUDA 缓存），切回语音模式自动重新加载并预热。
- 文字模式下隐藏麦克风电平表与「模型预热」按钮（此时不涉及采集）。

### 本 beta 修复

- **输出语言为中文时仍念英文**——此前当「输入 == 输出语言」时会被强制翻成另一种语言并朗读英文。现在**显式选择的输出语言优先**，只有输出语言留空才自动取反。
- **升级守卫过宽**——原来只要机器上有任意 `pythonw.exe` 在跑就拒绝升级；现在只检查**本安装目录**启动的进程。

### 安装方法

1. 托盘退出同声；
2. 把 `TongSheng-1.1.11-beta-TextRec_mode-update.zip` 解压到安装目录下的子文件夹，例如
   `D:\TongSheng\TongSheng-1.1.11-beta-TextRec_mode\`；
3. 双击其中的 `apply_update.bat`，看到 `Installed version: 1.1.11` 即成功；
4. 启动同声，运行开始菜单的 **Self-test**，10 项需全部 PASS。

覆盖包只替换程序代码、工具与文档；**模型、`config.yaml`、录音与已训练音色（`voice-repository`）都不会被覆盖或删除**。

### 已知限制

- 文字模式下没有语音识别，ASR 模型是故意卸载的。
- 翻译仍走随包的本地 llama.cpp 服务，需要时程序会自动拉起。
- 语种判断基于字符区间，中英混排等文本可能被归到主要字符所属语种。
- 本 beta 只发布覆盖包，不能用于全新安装；请先装 1.1.11 完整版。
