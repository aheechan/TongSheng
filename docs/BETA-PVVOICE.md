# 直接使用 PrivateVoice 的音色（beta）

同声会读取 `PrivateVoice\characters\*`，不需要导入、不复制权重。

## 使用

1. 打开主窗口或「声音模型训练」窗口的音色列表；
2. PrivateVoice 的角色会以 `名称 · PV` 出现（内部 id 为 `pv:<角色目录名>`）；
3. 选中即可用于合成，选择会写入 `config.yaml` 的 `tts.voice`。

## 路径解析

| 项 | 规则 |
|---|---|
| GPT / SoVITS 权重 | profile 中的绝对路径（存在则用）→ 该角色 `checkpoints\<同名文件>` |
| 参考音频 | `<角色>\reference.wav` → `<角色>\dataset\reference.wav` |
| 参考文本 | profile 的 `voice.reference_text` → `reference.txt` → `dataset/reference.txt` |

## 注意

- `pv:` 音色只读：音色库里的删除按钮会提示去 PrivateVoice 管理，避免误删 A 的角色目录。
- 训练新音色仍写入同声自己的 `voice-repository`，两套来源并存。
- PrivateVoice 里的角色若缺权重或参考音频，会以 zero-shot 或不出现在列表中呈现。
