# 安装包体积评估（1.0.1）

实测环境：Windows 10 22H2 / RTX 3090 / Python 3.12 运行时（来自 PrivateVoice 打包版）。
所有数字为磁盘占用（未压缩），单位 GB。

## 一、分项实测

| 组成 | 大小 | 说明 | 能否裁 |
|---|---:|---|---|
| TongSheng 代码 | 0.001 | `tongsheng/` 全部源码 | 不可裁 |
| Python 运行时 | **6.02** | 含 torch 4.19 / PySide6 0.31 / onnxruntime 0.23 / scipy 0.10 / llvmlite 0.12 … | 部分可裁 |
| GPT-SoVITS 代码 + 预训练 | **3.70** | 2.95 权重（s1v3 0.15、s2Gv3 0.73、s2Gv4 0.73、vocoder 0.05、bert 0.62、hubert 0.18、langdetect 0.13）+ 0.75 代码/G2PW | 不可裁（合成必需） |
| 中文 ASR（paraformer） | 0.95 | `speech_seaco_paraformer_large …` | 中文版必需 |
| 标点模型（ct-punc large） | **1.13** | `punc_ct-transformer_cn-en-common-vocab471067-large` | 可换 small（约 −0.85） |
| 声纹（campplus） | 0.03 | 说话人校验 | 可裁 |
| 英文 ASR（faster-whisper small） | 0.56 | CTranslate2 格式 | 英文版必需 |
| llama-server + CUDA DLL | 0.10 | `llama.cpp` 可执行 | 不可裁 |
| 纠错模型 Qwen3-1.7B Q8 | 1.75 | GGUF | 可换 Q4（约 −0.75） |
| 翻译模型 Index-Translate-9B Q4 | **5.51** | GGUF | 可换 2B（−4.26） |
| 默认音色（Default_Voice + Ahee EN） | 0.44 | s1 ckpt + LoRA + 参考音频 | 可不打包 |

## 二、三种打包方案

| 方案 | 组成 | 未压缩 | 预计安装包（LZMA，约 0.82 压缩率） |
|---|---|---:|---:|
| **完整版** | 全量 + 9B 翻译 + 两个音色 | **20.2 GB** | **≈ 16.5 GB** |
| **标准版**（推荐） | 2B 翻译 + small 标点 + 只带默认音色 | **14.0 GB** | **≈ 11.5 GB** |
| **按需版** | 只带运行时 + 权重，LLM/音色首次运行下载 | **6.5 GB** | **≈ 5.2 GB**（+首次下载 3–5 GB） |

参考：项目 A 的安装包是 11.5 GB / 8 个分卷，它没有内置翻译 LLM，这也是我们多出来的主要部分。

## 三、体积构成占比（完整版）

```
torch + 运行时   6.0 GB  30%
翻译/纠错 GGUF   7.3 GB  36%   ← 最大头
GPT-SoVITS 权重  3.0 GB  15%
ASR + 标点       2.7 GB  13%
GPT-SoVITS 代码  0.7 GB   4%
音色             0.4 GB   2%
```

## 四、可优化项（按性价比排序）

| 动作 | 节省 | 代价 |
|---|---:|---|
| 翻译模型 9B → 2B | 4.26 GB | 长句/术语准确率下降 |
| 标点模型 large → small | 0.85 GB | 中文长句断句略差 |
| 纠错模型 Q8 → Q4 | 0.75 GB | 纠错略弱 |
| 不打包音色（用户自训） | 0.44 GB | 首次使用需训练或导入 |
| 裁掉 gradio / pandas / 韩日前端 | 0.3 GB | 失去 ja/ko 合成能力 |
| 安装包分卷（Inno 7 卷） | 不省体积 | 便于分发下载 |
| 首次运行下载模型 | 安装包 → 5.2 GB | 需要网络，首启等待 |

## 五、结论

- **不裁剪直接打包，安装包约 16–17 GB**（完整版）
- **推荐首发用「标准版」：约 11–12 GB**，和项目 A 的 11.5 GB 同一量级，用户接受度最好
- 真正的大头是翻译 LLM（7.3 GB），如果首发只带 2B，整体立刻降到 11 GB 出头
- 若想控制在 6 GB 以内，只能走「基础包 + 模型按需下载」

## 六、打包清单（标准版）

```
TongSheng/                   代码 + assets + config.example.yaml
runtime/                     Python 3.12 + torch-cu128 + PySide6 + funasr + faster-whisper
GPT-SoVITS/                  code + GPT_SoVITS/pretrained_models（不含 logs / *_weights）
models/asr/                  paraformer-zh + ct-punc(small) + camplus
models/asr/whisper/          faster-whisper-small
models/llm/                  Qwen3-1.7B-Q8 + Index-Translate-2B-Q4
llama/                       llama-server.exe + DLL
voice-repository/            仅 Default_Voice
```

不要打包：`.git/`、`logs/`、`results/`、`GPT-SoVITS/TEMP/`、`GPT_weights_v3/`、`SoVITS_weights_v*/`（训练产物）、`__pycache__/`。
