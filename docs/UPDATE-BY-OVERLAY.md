# 覆盖式升级（推荐）

不再使用升级安装包。所有升级都以“覆盖目录”的方式完成。

## 1. 准备

1. 托盘 → 退出同声（`pythonw.exe` 会占用 `.pyd/.dll`，不退出会覆盖失败）
2. 找到安装目录（通常是 `D:\TongSheng` 或 `C:\Program Files\TongSheng`）

## 2. 覆盖

把 `TongSheng-<版本>-update.zip` 解压到安装目录下的一个子文件夹：

```
D:\TongSheng\
├─ runtime\            ← 已存在
├─ models\             ← 已存在
├─ tongsheng\          ← 会被覆盖更新
├─ voice-repository\   ← 不会被动
└─ TongSheng-1.1.6-update\   ← 解压到这里
```

双击 `TongSheng-1.1.6-update\apply_update.bat`，它会：

- 校验目标目录确实是同声安装目录
- 检查同声没有在运行
- 用 robocopy 覆盖代码、工具、文档
- 跳过 `voice-repository`、`logs`、`results`、`config.yaml`
- 若 `voice-repository\Default_Voice` 缺失则补回
- 打印升级后的版本号

## 3. 验证

```
开始菜单 → Self-test
```

必须看到（10 项全 PASS）：

```
[PASS] ASR engine loads: funasr-paraformer loaded on cuda
[PASS] Voice library: N voice(s): Default_Voice, …
RESULT: OK
```

## 手动覆盖（不用脚本）

直接解压并全选复制到安装目录，遇到同名文件选择“替换”。唯一要小心的是
`voice-repository`：里面是你训练的音色，**不要整个删除**；`Default_Voice` 缺失时
再从更新包里复制进去即可。

## 为什么不用安装包

- 安装包固定写 `%ProgramFiles%`，装在 `D:\` 的用户会更新到错误位置（1.1.5 已修，
  但覆盖方式更省心）
- 覆盖包只有约 200 MB，且不重新安装 Python 运行时与模型
