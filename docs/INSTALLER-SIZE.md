# 安装包体积（TongSheng 1.1.1，仅 Default_Voice）

由 `tools/build_package.py --stage` 实测（磁盘占用，未压缩）。

## 分项

| 组成 | MB |
|---|---:|
| Python 运行时 | 5888 |
| LLM 权重 | 3001 |
| 语音识别模型 | 2676 |
| v4 预训练权重 | 1863 |
| GPT-SoVITS 代码 | 663 |
| Default_Voice 音色 | 221 |
| llama-server | 101 |
| TongSheng 代码与文档 | 0 |
| **合计** | **14413（14.08 GB）** |

## 口径

| 方案 | 已安装 | 安装包（LZMA ≈0.86，分卷 4 GB） |
|---|---:|---:|
| 标准（2B 翻译，大标点） | 14.1 GB | **≈ 12.1 GB（3 卷）** |
| 标点换 small | −0.83 GB | ≈ 11.4 GB |
| 翻译换 9B | +4.16 GB | ≈ 15.7 GB |

## 打包必须排除

```
logs/  results/  .git/  __pycache__/
GPT-SoVITS/logs/  GPT-SoVITS/TEMP/
GPT-SoVITS/GPT_weights_v3/        （训练产物，3.1 GB）
GPT-SoVITS/SoVITS_weights_v3/     （训练产物）
GPT-SoVITS/SoVITS_weights_v4/     （训练产物，1.6 GB）
GPT-SoVITS/G2PWModel.zip          （已解压到 GPT_SoVITS/text/G2PWModel，562 MB）
pretrained_models/models--nvidia--bigvgan_v2_24khz_100band_256x/  （v3 专用，429 MB）
pretrained_models/s2Gv3.pth       （v3 专用，733 MB）
models_cache/models/              （与 modelscope/ 重复的 paraformer，953 MB）
```

## 生成方式

```bat
python tools\build_package.py --stage --iss     :: 收集 + 生成 Inno Setup 脚本
python tools\build_package.py --archive         :: 装好 7-Zip 后直接出分卷
```
