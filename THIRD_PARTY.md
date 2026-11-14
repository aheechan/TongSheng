# 第三方组件与模型 / Third-party components

TongSheng 只是把下面这些组件串起来。它们的许可**不会**因为本项目而改变；
分发整合包前请逐项核对。

## 代码

| 组件 | 用途 | 许可 | 说明 |
|---|---|---|---|
| [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) | 音色克隆 / 语音合成 | MIT | 以源码形式引用，需要单独部署 |
| [FunASR](https://github.com/modelscope/FunASR) | 中文语音识别 | MIT | pip 依赖 |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) + CTranslate2 | 英文语音识别 | MIT | pip 依赖 |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | 本地 LLM 推理（`llama-server`） | MIT | 外部可执行文件 |
| [PySide6](https://www.qt.io/qt-for-python) | 系统托盘界面 | LGPLv3 | 动态链接，允许闭源分发 |
| [NumPy](https://numpy.org) / [SciPy](https://scipy.org) / [soundfile](https://python-soundfile.readthedocs.io) / [sounddevice](https://python-sounddevice.readthedocs.io) | 音频与数值计算 | BSD / MIT | pip 依赖 |
| [PyYAML](https://pyyaml.org) | 配置 | MIT | pip 依赖 |

## 模型权重（不随仓库分发）

| 模型 | 用途 | 来源 |
|---|---|---|
| GPT-SoVITS `s1v3.ckpt` / `s2Gv3.pth` / `s2Gv4.pth` / `vocoder.pth` | 合成底模 | huggingface `lj1995/GPT-SoVITS` |
| `chinese-roberta-wwm-ext-large` | 文本前端 | huggingface `hfl` |
| `chinese-hubert-base` | 语义特征 | huggingface `TencentGameMate` |
| Paraformer-zh（含 ct-punc、campplus） | 中文 ASR | ModelScope `iic` |
| faster-whisper-small | 英文 ASR | huggingface `Systran` |
| Qwen3-1.7B（GGUF） | 纠错 | Qwen 官方发布 |
| Index-Translate-9B / 2B（GGUF） | 翻译 | IndexTeam 发布 |

**注意**：Index-Translate 等模型的许可可能包含商用限制（例如仅限非商业或需授权），
在对外分发整合包、SaaS 化或商业使用前，请自行确认每一项的许可条款。

## 上游项目来源

TongSheng 整合了两个已完成的本地项目：

- **Project A — PrivateVoice**（`app/`）：GPT-SoVITS v3/v4 推理封装、LoRA 训练流程、
  音频质检/切分/打标工具、音色存储。MIT。
- **Project B — ALT-VoiceType**（`altvoice/`）：ASR 适配层、纠错与翻译 prompt 设计、
  llama-server 进程托管、Windows 文本注入思路。Apache-2.0。

对应代码在 TongSheng 中被重写/裁剪为 `tongsheng/llm/`、`tongsheng/correct/`、
`tongsheng/translate/`、`tongsheng/tts/`，文件头保留了来源说明。
