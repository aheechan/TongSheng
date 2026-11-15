# Changelog

## 1.1.8 - 2026-11-15 (完全按项目 A 的调用方式，重新出完整安装包)

### 复盘：为什么 1.1.6/1.1.7 还是失败

- 1.1.6 把打标换成 faster-whisper → RTX 50 上 CTranslate2 首次推理直接阻塞，每片卡 45 秒
- 1.1.7 改回 FunASR，但**我给它套了一个“子线程 + 45 秒超时”的包装**。FunASR 的 CUDA
  上下文在加载线程里，换线程调用就会卡死——这和项目 A 的调用方式不一致，是我的错

### 现在（与项目 A 完全一致）

- `AutoModel(model=<本地目录>, device="cuda", disable_update=True)`
- `model.generate(input=audio16k, batch_size_s=300)` **在同一条线程里同步调用**
- 不再有子线程、超时包装、whisper 兜底或探针
- 训练打标唯一使用 FunASR（中文引擎），与项目 A 的 ASRA 打标路径一致

### 交付

- 重新构建**完整安装包** `TongSheng-1.1.8-Setup.exe` + 分卷（不再发覆盖包/升级包）

## 1.1.7 - 2026-11-15 (训练打标回到 FunASR，完全照项目 A 的做法)

日志证据：打标阶段每个片段都在 **whisper 上整 45 秒超时**——

```
labelling clip 0001.wav (2.3s audio) with faster-whisper
ASR timed out after 45s; skipping this clip      ← 每片都一样
```

结论：`faster-whisper` 的 CTranslate2 内核在 RTX 50（Blackwell）上跑不起来，
首次推理直接阻塞；FunASR 本身在那台机器是好的（`FunASR ready on cuda`）。

### Changed
- **打标改用实时引擎 FunASR**（和项目 A 完全一致：`AutoModel(model=<本地目录>,
  device="cuda", disable_update=True)` 逐片段识别）
- **默认关闭 whisper 兜底**（`asr.gpu_fallback: ""`）：它就是会在 50 系上卡住的引擎，
  只有在需要时才手动打开
- **whisper 加载后加 20 秒探针**：跑不起来立刻报“此卡不支持 CTranslate2”，
  而不是在真正识别时静默卡 45 秒
- 升级统一为**覆盖式**：只发 `TongSheng-<版本>-update.zip`，解压后运行
  `apply_update.bat`；不再生成升级安装包

## 升级方式变更：覆盖式更新（2026-11-15）

从 1.1.6 起不再使用“升级安装包”，改为**目录覆盖**：

```
TongSheng-1.1.6-update.zip
 └─ 解压到 <安装目录>\TongSheng-1.1.6-update\  → 运行 apply_update.bat
```

- 只包含代码、工具、文档，以及缺失时补回的 `Default_Voice`
- `apply_update.bat` 用 robocopy 覆盖**已改动的文件**，跳过 `voice-repository`、
  `logs`、`results`、`config.yaml`，不会删除任何东西
- 全部完成后打印实际版本号；`Default_Voice` 只在缺失时补
- 若不想用脚本，直接把解压出来的内容拖进安装目录也可以（`voice-repository`
  建议手动判断是否覆盖）

## 1.1.6 - 2026-11-15 (训练打标改用 whisper，逐片段超时与日志)

1.1.5 已修复 50 系显卡上 FunASR 启动失败（日志确认 `using bundled FunASR model at …`
→ `FunASR ready on cuda`），但训练在“分段/打标”阶段仍可能长时间无输出。

### Changed
- **训练打标不再用实时 ASR**：几十个短片段连打标是一个批量任务，改用随包的
  faster-whisper（同一块 GPU）。它不参与 FunASR 的模型解析，失败面更小；实时识别仍用
  Paraformer，两者互不影响。
- **逐片段超时 45 秒**：某一段卡住就跳过并记日志，不会让整次训练无限等待
- **每个片段都有日志**：`labelling clip 0003 (4.2s audio) with faster-whisper`，
  卡在哪一片一眼可见
- 自检新增 **Voice library** 一项：列出已安装音色，并提示 `Default_Voice` 是否缺失
- 升级包继续携带 `Default_Voice`（`onlyifdoesntexist`，不会覆盖自训音色）

## 1.1.5 - 2026-11-15 (FunASR 真正修复：按目录加载；升级包定位原安装目录)

### Fixed
- **`'NoneType' object is not callable` 的真正原因**：FunASR 的 `build_model()` 里
  `model_class = tables.model_classes.get(kwargs["model"])` 取不到值时就是 None，
  下一行 `model_class(...)` 必然报这个错。之前的代码把 **模型名**（`paraformer-zh`）
  交给 FunASR，它会先走“名称 → 本地目录”的解析；只要解析出来的目录里没有
  `config.yaml`（缓存布局不同、缺文件、或走了 Hub 分支），`kwargs["model"]` 就还是名字，
  注册表里查不到 → None。
  现在**直接把本地模型目录传给 FunASR**（`.../snapshots/master`），跳过名称解析；
  目录里没有 `config.yaml` 时明确报错并说明缺哪个文件。
- **升级包装错位置**：升级包原来固定装到 `%ProgramFiles%\TongSheng`，而安装在
  `D:\TongSheng` 的用户完全没被更新。现在从卸载注册表读取原安装目录，找不到才回退。
- **默认音色丢失无法恢复**：升级包现在附带 `Default_Voice`，用 `onlyifdoesntexist`
  写入——缺就补，已有的（包括自己训练的音色）绝不覆盖。
- 自检里 ASR 项在“引擎兜底”包装下会误报 `fell back to ?`，已修正为报告真实引擎与设备。

## 1.1.4 - 2026-11-15 (50 系显卡的语音识别兜底，不再卡死)

### Fixed
- **RTX 50 系上 FunASR 起不来导致“预热卡住、识别中不动、训练卡在分段”**：
  FunASR 在 `cuda` / `cuda:0` / lazy 三种方式下都抛 `'NoneType' object is not callable`，
  而 1.1.3 取消了 CPU 兜底，于是 ASR 永远加载不出来。
  现在改为**同一块 GPU 上的引擎兜底**：
  1. 先试 FunASR（Paraformer）
  2. 失败则自动切到 faster-whisper（同一块显卡，已随包分发）
  3. 仍然失败才报错，并给出驱动/引擎指引
  可用 `asr.gpu_fallback: ""` 关闭兜底；`asr.allow_cpu_fallback` 依旧默认关闭。
- FunASR 每次加载失败都会把**完整堆栈**写进 `logs/app.log`（之前只有一行摘要）。

### Added
- `tools/asr_probe.py`：一键诊断——打印 torch/CUDA 能力、FunASR 三种加载方式的完整
  traceback、whisper 兜底是否可用，最后给出结论。
- **升级包** `TongSheng-1.1.4-Update.exe`（2.2 MB）：只替换代码、工具与文档，
  不动模型/音色/配置，装在已有安装目录上即可。

## 1.1.3 - 2026-11-15 (合成与训练在安装版可用，新增安装后自检)

### Fixed
- **英文合成失败**：打包时 `nltk_data` 用了硬链接，NLTK 3.9 的安全检查发现
  `st_nlink=2`，直接抛 `Security Violation [pathsec.open]`，所有英文合成全部失败。
  现在 `nltk_data` 与 `app/` 一律**复制**打包（不再链接）。
- **训练报错「未找到项目A训练模块」**：安装包缺少 `app/core/train.py`。
  现在随包分发项目 A 的 `app/` 训练后端（几百 KB），`CloneTrainer` 开箱可用。
- **安装目录不可写**：`%ProgramFiles%\TongSheng` 对普通用户只读，导致日志、
  配置、训练数据集写不进去。新增 `paths.user_root()`：安装目录可写就用它，
  否则自动落到 `%LOCALAPPDATA%\TongSheng`（配置、日志、录音、自训音色都在那里）。
- **训练在“文本/音素提取”阶段失败**：打包版缺 `tools\run_upstream.py` 与
  `tools\s1shim/`，项目 A 的上游启动器找不到，`1-get-text.py` 里的
  `from text.cleaner import ...` 直接 `ModuleNotFoundError`。现在这两个文件随包分发，
  训练子进程按 A 的方式补 `sys.path` 并加载 Lightning 垫片。
- **训练最后一步报 PermissionError**：训练完成、音色安装时把 `reference.wav`
  复制到它自己身上（项目 A 的 character 目录被指到了 `voice-repository`，与安装目标同名），
  Windows 直接抛 `WinError 32`。现在：
  - 训练工作区独立到 `<数据目录>\training\characters`，不再污染音色库
  - 所有权重/参考音频拷贝改走 `_copy_file()`：同路径自动跳过，被占用时重试 8 次
- **多占 950 MB**：`MODELSCOPE_CACHE` 被设成了 `models\asr`（父目录），ModelScope 找不到
  模型就复制了一份 paraformer。现在指向 `models\asr\modelscope`，不再重复占盘。
- **不再静默退回 CPU**：FunASR 在 CUDA 上失败时会按 `cuda` → `cuda:0` → `cuda`(LAZY 模块加载)
  依次重试（参照项目 A 的加载方式，只增加新卡兼容层）；全部失败才报错，并给出驱动/换引擎
  的明确指引。要允许 CPU 兜底需显式打开 `asr.allow_cpu_fallback: true`。
  自检里 ASR 项现在要求真的跑在 GPU 上。
- FunASR 在 CUDA 上失败时保留完整堆栈（`--verbose` / 日志 debug），便于定位
  50 系显卡上的 `'NoneType' object is not callable`。

### Added
- **主界面状态提示**：`语速` 滑块下方新增一行常驻状态——
  “模型加载中…／可以开始了…／正在听你说…／正在识别与翻译…／正在播放译文…”，
  后面跟随录音开关状态；任何状态变化都会立即更新。
- **安装后自检 `tools/selftest.py`**（参照项目 A）：
  Python/torch、GPU 与显存、模型目录与 v4 权重、llama-server、音频端点、
  英文音素（NLTK）、ASR 加载、英文合成、训练后端，逐项 PASS/FAIL，
  报告写到 `logs\selftest.txt`，退出码非 0 表示有故障。
  安装向导结束页提供「Run the self-test now」，开始菜单也有 **Self-test**。

## 1.1.2 - 2026-11-15 (安装版无法启动)

**打包版根本起不来**：模型发现只认开发机的同级仓库（PrivateVoice / ALT-VoiceType），
安装到 `%ProgramFiles%\TongSheng` 后找不到 GPT-SoVITS 与模型，于是启动即失败。

### Fixed
- `paths.discover()` 优先识别**打包布局**：`<安装目录>\GPT-SoVITS`、
  `<安装目录>\models\asr`、`<安装目录>\models\llm`，其次才回退到同级仓库
- `resolve_llama_binary()` 优先使用随包分发的 `<安装目录>\llama\llama-server.exe`
- FunASR 缓存改为标准的 `models\asr\modelscope\models\<模型>` 结构，
  `MODELSCOPE_CACHE` 指向 `models\asr\modelscope`
- `run.bat` 优先使用包内的 `runtime\python.exe`（以前只找 PrivateVoice 的运行时，
  安装版必然失败）；失败时打印退出码与日志路径
- 启动失败不再静默：缺失模型时弹出英文错误框（`pythonw` 没有控制台），
  未捕获异常写入 `logs\crash.log` 并同样弹框
- 安装包补上 `tools\`（启动器 `dev_run.py` 就在这里，之前漏打包导致快捷方式无效）

## 1.1.1 - 2026-11-14 (转录显示重复)

### Fixed
- **同一句话显示两遍**：当译文与原文相同（同语种、或翻译返回原句）时，显示框会把
  `EN xxx` 打印两次。现在相同内容只显示一行，译文与原文一致时不再重复。
- **语言标签错位**：whisper 实际听到中文但输入语言选的是英文时，显示框却标成 `EN`。
  现在使用识别器返回的真实语种，并据此重新决定翻译目标语言。

## 1.1.0 - 2026-11-14 (取消双档，录音开关)

### Changed
- **合成只保留一套参数**：LIVE 档废弃，全部改用原“录音模式”的参数
  （v4 · 48 kHz · 12 步 · 整段渲染 · 80 ms 句间停顿）
- 主界面「输出品质」改为「录音」，只有一个开关：**保存合成音频（录音）**
  - 开：每段合成写入 `results/rec`
  - 关：写入的缓存**超过 3 分钟自动删除**（每分钟清扫一次，启动时也扫）
- 托盘菜单同步换成「保存合成音频（录音）」勾选项

### Removed
- LIVE/REC 双档切换与相关的时间参数（live_chunk_chars、live_first_chunk_chars 不再生效）

## 1.0.8 - 2026-11-14 (自适应分块 + 批量推理)

### Changed
- **自适应分块**：第一块 24 字（最快出声），后续块默认 96 字（2–4 句语境、更顺）。
  播放时下一块已经在渲染，缓冲越用越厚。
- **批量推理 batch_size 4**：同一块内部的文本切片并行合成，实测合成速度提升约 2.2 倍
  （音质参数不变，只是并行）。

### Measured（10 句、15.4 秒音频，同一段话）
| 配置 | 首次出声 | 第二块渲染 | 渲染/音频 |
|---|---:|---:|---:|
| batch=1 | 2.26 s | 6.77 s | 1.79× 实时 |
| batch=2 | 1.34 s | 4.19 s | 2.80× 实时 |
| **batch=4（默认）** | **1.32 s** | **3.02 s** | **3.95× 实时** |

首块 1.3 秒出声，整段 15 秒音频 4.3 秒渲染完，播放期间缓冲只增不减。

## 1.0.7 - 2026-11-14 (LIVE 向 REC 的合成质量看齐)

### Changed
- **LIVE 的采样步数 4 → 12**，与 REC 完全一致；两档现在只差“分块方式”，
  不再靠降低步数换速度（那正是拖音/破音的来源）
- **LIVE 按 32 字分块渲染**（约 1–2 句一块），保留前文语境，块间 80 ms 停顿
- **两档共用同一个引擎实例**：以前按档位缓存会导致切档重新加载模型（9 秒 + 显存翻倍），
  现在同一音色的 LIVE/REC 直接复用

### Measured（同一段 5 句、8.5 秒音频）
| | 首次出声 | 分块数 | 总耗时 |
|---|---:|---:|---:|
| LIVE | **3.1 s** | 3 | 5.3 s |
| REC | 4.8 s | 1 | 4.8 s |

LIVE 比 REC 早约 1.6 秒出声，句子渲染参数与 REC 相同。

## 1.0.6 - 2026-11-14 (LIVE 用回训练好的 v4 音色)

### Fixed
- **LIVE 档其实一直在用 v3 零样本**：低档被配置成 GPT-SoVITS v3（24 kHz），但训练出来的
  音色只有 v4 LoRA，于是运行时回退成“v3 底模 + 参考音频零样本”——听起来像换了个人，
  也是单音延音的主要来源之一。
  现在两档都用**训练好的 v4 音色**（48 kHz），区别只剩采样步数：
  - LIVE：4 步，低延迟
  - REC：12 步，高保真
  旧配置里的 `tiers.live.version: v3` / `24 kHz` 会自动迁移。
- **参考文本语种**：不再信任 profile 里可能过期的 `reference_lang`，改为按参考文本
  自动判断（英文参考音频配中文提示词会把发音前端口音搞错）。

## 1.0.5 - 2026-11-14 (同声传译更稳：参照项目 A 的合成时序)

用一点响应速度换播放的连贯性，参数全部对齐项目 A 的 TTS 时序。

### Changed
- **整句渲染再播放**：LIVE 档不再把碎片拼起来，逐句合成完整句子后播放
- **句子切分**：上限 40 字、下限 6 字；1–2 字的碎片会并到相邻句，避免断气
- **句间停顿 80 ms**：每句话之间有明确呼吸，不再粘连
- **边缘淡入淡出 12 / 25 ms**：消除句首句尾的爆音与突兀起音
- **异常结果重试**：合成结果过轻（峰值 < 0.02）或异常过长（> 0.55 秒/字 × 1.8）
  时自动用 top_k=15 / temperature=0.7 重合成一次（项目 A 的做法）
- 新增配置：`tts.sentence_gap_ms`、`fade_in_ms`、`fade_out_ms`、
  `min_chars_per_sentence`、`max_sec_per_char`、`retry_bad_sentence`

## 1.0.4 - 2026-11-14 (快捷键停止后不处理语音)

### Fixed
- **快捷键结束录音后不分析**：1.0.2 里把 `_toggle_talk` 的"聆听中"分支改成了 `cancel()`，
  于是用快捷键停止会把这段音频**直接丢弃**（鼠标点主界面按钮走的是另一条 `end()` 路径，
  所以按钮正常）。现在：
  - 聆听中 → `end()`：正常收尾、进入识别/翻译/合成
  - 处理中 / 播放中 → `cancel()`：停下当前这一段
- 系统代理豁免：注册表 `ProxyOverride` 已加入 `127.0.0.1;localhost;<local>` 并广播刷新，
  配合代码里的无代理 opener，双保险（其他 Python 程序也不会再被劫持）

## 1.0.3 - 2026-11-14 (启动卡住 / 翻译失效修复)

### Fixed
- **系统代理劫持 localhost**：开启了系统代理（Clash/V2Ray/公司 VPN 等）时，
  Python urllib 会把 `127.0.0.1` 的请求也发给代理，代理直接断连，表现为
  - llama-server 健康检查一直失败 → 每次启动都重复拉起新的服务进程 → 显存被吃满 →
    "加载模型卡住"
  - 纠错/翻译请求全部失败
  现在所有本地 LLM 请求都走**绕过代理**的 opener。
- **端口与 ALT-VoiceType 冲突**：默认端口改为 8093（纠错）/ 8094（翻译），
  配置里的旧地址 8091/8092 会自动迁移。
- **重复的 llama-server 进程**：启动时读取 `logs/llama-servers.json`，清理上次
  遗留的本项目服务进程；端口被占用时先等待健康检查，绝不重复起服务。
- 服务启动超时 90s → 180s（9B 模型在显存吃紧时加载更慢）。

## 1.0.2 - 2026-11-14 (1.0.1 的稳定性修复)

只修 bug，不加新功能；beta1 / beta2 的实验内容不在这个版本里。

### Fixed
- **停止键 / ESC 失效**：上一段还在处理时，新的录音会被静默拒绝、状态停在 WORKING，
  之后快捷键和 ESC 看起来都"死了"。现在：
  - cancel() 强制回到 IDLE，ESC 无条件取消（去掉"看起来空闲就忽略"的早退）
  - 处理中按快捷键 = 取消当前这段，而不是被拒绝
  - 上一段线程卡住时会放弃它并接受新的一段（turn id 守卫，旧线程结束时不再改状态）
  - 录音流与状态不一致时 end() 也会回到 IDLE，不会卡在"聆听中"
- **播放可能永久阻塞**：player.wait() 增加超时（音频时长 x2 + 15 秒），超时强制停流
- **键盘钩子生命期**：stop() 循环重发 WM_QUIT 直到线程退出；旧监听对象保留引用，
  避免回调跳板被回收；新增 3 秒健康检查，钩子失效自动重连
- 手势复位：回到 idle、按 ESC、取消时清空"已按下"状态，避免 release 丢失后死锁

## 1.0.1 - 2026-11-14 (冻结版本, git tag v1.0.1)

- 双档合成：LIVE 24 kHz（整句合成后连续播放）/ REC 48 kHz（v4 + LoRA，自动存盘）
- 输入语言 中/英，输出语言 15 种（中英日韩可朗读，其余仅文字）
- GPT-SoVITS 音色克隆训练窗口（音色库 + 新建音色）
- 模型预热、输入电平表、ESC 取消、翻译粘贴、常驻麦克风流
- 键盘钩子原型修正（LPARAM 溢出）、TTS 生成与预热互斥

## 0.1.0 - 初始整合

- 从 PrivateVoice / ALT-VoiceType 整合出 TongSheng 骨架
