# voices/ — 克隆音色目录

每个子目录是一个音色：

```
voices/<id>/
├─ profile.json        # 元数据（名称、权重相对路径、参考文本）
├─ reference.wav       # 5–10 秒参考音频
├─ reference.txt       # 参考音频对应文本
└─ checkpoints/        # s1 GPT ckpt + SoVITS LoRA（v3 / v4）
```

权重文件体积较大且含个人声纹，**不要提交到仓库**（`.gitignore` 已排除）。

## 导入已有音色

```bat
run.bat voices import --from "..\PrivateVoice\characters\<音色目录>"
```

## 训练新音色

```bat
run.bat train --audio D:\我的录音.wav --name 我的声音
```

训练会调用项目 A（PrivateVoice）的 GPT-SoVITS 训练管线：
切分 → 逐句识别打标 → LoRA（v4，48 kHz）→ 自检 → 安装到本目录。
