# 安装包体积（TongSheng 1.1.2，仅 Default_Voice）

由 `tools/build_package.py --stage` 实测（磁盘占用，未压缩）。

## 分项

| 组成 | MB |
|---|---:|
| Python 运行时（torch 4.19 / PySide6 / onnxruntime / scipy …） | 5888 |
| 语音识别模型（paraformer-zh + ct-punc + whisper small） | 2681 |
| LLM 权重（Qwen3-1.7B Q8 + Index-Translate-2B Q4） | 2995 |
| GPT-SoVITS 代码 + v4 预训练权重（s1v3 / s2Gv4 / vocoder / roberta / hubert / langdetect / G2PW） | 2527 |
| Default_Voice 音色（GPT ckpt 148 + LoRA 72 + 参考音频 1） | 221 |
| llama-server + DLL | 168 |
| 应用代码、工具与 NLTK 数据 | 40 |
| **合计** | **14448（约 14.1 GB）** |

## 口径

| 方案 | 已安装 | 实测安装包（LZMA2，1.9 GB 分卷） |
|---|---:|---:|
| **标准（2B 翻译，当前构建）** | 14.14 GB | **10.67 GB**（1 exe + 7 bin） |
| 标点换 small | 13.3 GB | ≈ 9.9 GB |
| 翻译换 9B | 18.3 GB | ≈ 13.6 GB |

> 实测压缩率 **0.74**（比预估的 0.86 好）：运行时 DLL 压缩率很高，GGUF 几乎压不动但占比只有 21%。

## 打包必须排除

```text
logs/  results/  .git/  __pycache__/
GPT-SoVITS/logs/  GPT-SoVITS/TEMP/
GPT-SoVITS/GPT_weights_v3/        （训练产物，3.1 GB）
GPT-SoVITS/SoVITS_weights_v3/     （训练产物）
GPT-SoVITS/SoVITS_weights_v4/     （训练产物，1.6 GB）
GPT-SoVITS/G2PWModel.zip          （已解压到 GPT_SoVITS/text/G2PWModel，562 MB）
pretrained_models/models--nvidia--bigvgan_v2_24khz_100band_256x/  （v3 专用，429 MB）
pretrained_models/s2Gv3.pth       （v3 专用，733 MB）
models_cache/models/              （与 modelscope/ 重复的 paraformer，953 MB）
config.yaml                       （个人配置）
```

## 生成方式

```bat
python tools\build_package.py --stage --iss     :: 收集文件 + 生成 Inno Setup 脚本
python tools\build_package.py --archive         :: 装好 7-Zip 后直接出分卷
```

注意：`--stage` 使用硬链接，**打包时请先退出正在运行的同声**——运行中的进程会锁住
torch 的 `.pyd`，导致旧的 dist 目录删不掉（表现为目录里多出一层嵌套）。
