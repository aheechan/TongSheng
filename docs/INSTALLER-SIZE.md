# 安装包体积（仅 Default_Voice，1.1.1 单管线）

实测环境：Windows 10 / Python 3.12 嵌入式运行时 / GPT-SoVITS v4 单管线。

## 分项

| 组成 | MB | 说明 |
|---|---:|---|
| TongSheng 代码 + 资源 | 5 | src/ assets/ config.example.yaml |
| Python 运行时（含 torch 4.19、PySide6 0.31） | 6018 | torch 4188 / PySide6 309 / onnxruntime 228 / 其余 |
| GPT-SoVITS 代码（含 G2PW 中文音素） | 664 |  |
| v4 预训练权重 | 1714 | s2Gv4 733 + vocoder 55 + roberta 621 + hubert 180 + langdetect 125 |
| 中文 ASR（paraformer） | 953 |  |
| 标点模型（ct-punc large） | 1132 | 换 small 约 290 |
| 英文 ASR（faster-whisper small） | 564 |  |
| 声纹（campplus） | 28 | 仅说话人校验 |
| 纠错 LLM（Qwen3-1.7B Q8） | 1749 |  |
| 翻译 LLM（Index-Translate-2B Q4） | 1251 | 换 9B 为 5512 |
| llama-server + DLL | 101 |  |
| Default_Voice 音色 | 221 | GPT ckpt 148 + LoRA 72 + 参考音频 1 |
| **合计（已安装）** | **14400** | ≈ 14.1 GB |

## 三种打包口径

| 方案 | 已安装 | 安装包（LZMA ≈0.86） |
|---|---:|---:|
| 标准（2B 翻译，大标点） | 14.1 GB | **12.1 GB** |
| 精简（2B，标点换 small） | 13.2 GB | **11.4 GB** |
| 中文版（再去掉英文 ASR） | 12.7 GB | **10.9 GB** |
| 高保真（9B 翻译，大标点） | 18.2 GB | **15.7 GB** |

> 说明：GGUF / .pth / .pt 已经是压缩格式，几乎压不动；真正能压缩的是运行时 DLL，
> 所以整体压缩率取 0.86 比较保守（项目 A 的 11.5 GB 分卷大致也是这个比例）。

## 打包时必须排除

```
GPT-SoVITS/logs/           训练日志
GPT-SoVITS/GPT_weights_v3/ 3.1 GB 训练产物
GPT-SoVITS/SoVITS_weights_v3/ SoVITS_weights_v4/ 1.8 GB 训练产物
GPT-SoVITS/TEMP/           0.21 GB 临时文件
GPT_SoVITS/pretrained_models/models--nvidia--bigvgan_v2_24khz_100band_256x/ 0.43 GB（v3 专用，单管线已不需要）
results/  logs/  __pycache__/  .git/
models_cache/models/       与 modelscope/ 重复的一份 paraformer
```