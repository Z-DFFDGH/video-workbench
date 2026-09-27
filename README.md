# 自媒体剪辑辅助工具

本项目是面向 Windows 的本地桌面剪辑辅助工具。程序只进行素材准备、项目文件管理和 FFmpeg 媒体处理，正式剪辑仍由用户在剪映或 Premiere Pro 中手动完成。

当前阶段已完成第九阶段“项目笔记和敏感词检查”的实现，等待人工验收。

第九阶段新增：

- 项目根目录 `notes.md` 纯文本/Markdown 笔记，输入后定时自动保存
- 项目切换、删除和关闭窗口前统一保存笔记与脚本
- 程序目录预置 `sensitive_words.txt` 本地词库，一行一个词并忽略空行
- 初始词库参考 ToolGood.Words 的非法关键词数据，规范化后包含 10,220 条
- 中英文普通字符串检查，英文不区分大小写，高亮并列出命中的行、列位置
- 每次检查重新读取词库，词库缺失或编码错误时显示可处理提示

第八阶段新增：

- 格式转换、音频提取、片段裁剪、分辨率处理与音量调整
- 所有媒体处理均通过 `subprocess` 调用 FFmpeg，不手写编解码
- 串行后台任务、统一任务抽屉、失败状态和取消后输出清理
- 有项目时默认输出到“输出成品”并可选加入素材库
- 无项目时选择输出目录并在本地配置中记住位置
- 输出重名自动追加 `_1`、`_2`

第七阶段已完成：

- 素材列表和缩略图两种视图，以及名称/标签检索与结果数量反馈
- 拖拽视频、音频、图片入库；默认仅登记路径，可选复制到项目目录
- 素材详情、格式、大小、时长、尺寸、编码和缩略图展示
- 多标签添加和删除，英文标签检索不区分大小写
- 图片独立窗口预览，视频/音频通过 FFplay 独立窗口预览
- 从素材库移除记录且不删除磁盘文件，操作反馈明确

第六阶段已完成：

- 项目内 `.txt` 和 `.md` 纯文本文档列表及编辑器
- UTF-8 新建、打开、保存、另存为和默认目录导出
- 临时文件加原子替换写入，保存失败保留未保存状态
- 未保存、保存中、已保存状态反馈
- 项目切换、删除项目和关闭窗口前自动保存
- 一键全选复制，以及文档切换时保留光标和滚动位置
- 支持手工输入 `[00:23]` 时间码，不联动视频

第四阶段已完成：

- 项目内 UTF-8 `materials.json` 素材索引和原子写入
- 视频、音频、图片素材模型及多标签字段
- 默认仅记录路径，也支持按类型复制到项目目录
- 重名复制自动追加 `_1`、`_2`
- 使用 FFprobe 检测媒体类型、时长、尺寸和编码
- 使用 FFmpeg 生成视频首帧缩略图并保存到 `.cache/thumbnails`
- 按名称、标签进行不区分大小写的子串检索
- 移除素材记录时不删除源文件或已复制文件
- 损坏媒体记录错误状态，不阻断其他素材入库
- 保留前三阶段已完成的项目生命周期、Neon Dashboard、壁纸和反馈框架

项目笔记和敏感词检查均只使用本地文件，不包含 AI、语义分析或云端服务。

## 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- FFmpeg、FFplay、FFprobe 已加入系统 `PATH`
- PySide6
- Send2Trash（由 `requirements.txt` 安装）
- Requests、yt-dlp（由 `requirements.txt` 安装）

当前机器已经检测到 FFmpeg 9.0，并已在 `.venv` 中安装 PySide6 6.11.2、Send2Trash 1.8.3、Requests 2.34.2 和 yt-dlp 2026.8.19。

## 安装

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 启动

```powershell
.venv\Scripts\python.exe app.py
```

## 项目格式

本程序的一个项目就是一个普通文件夹，不是单一文件。目录内至少包含：

```text
项目文件夹
├─ project.json
├─ notes.md
├─ 原素材
├─ 脚本文档
├─ 音频文件
├─ 图片封面
└─ 输出成品
```

`project.json` 是 UTF-8 JSON，保存项目显示名称、创建时间和上述目录映射。打开已有项目时请选择“项目文件夹”，程序会自动读取其中的 `project.json`。

打开项目后，程序会在项目根目录创建并维护 UTF-8 `notes.md`。敏感词检查使用程序目录下的 UTF-8 `sensitive_words.txt`，一行一个词，空行会被忽略；修改文件后点击“检查当前文本”即可重新读取生效。

`sensitive_words.txt` 初始内容来自 ToolGood.Words 的非法关键词数据，已在保留首次出现顺序的前提下去除空行和英文大小写不敏感重复项。该词表可以继续手工增删；来源、哈希和 Apache-2.0 许可证记录在 `third_party/toolgood_words/`。

## 测试

运行全部自动化测试（当前 149 项）：

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

语法检查：

```powershell
.venv\Scripts\python.exe -m compileall -q app.py video_workbench tests
```

主窗口离屏启动检查：

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; from video_workbench.ui.main_window import MainWindow; app = QApplication([]); window = MainWindow(); print(window.windowTitle())"
Remove-Item Env:QT_QPA_PLATFORM
```

第九阶段自动化验收：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_notes_service tests.test_sensitive_words tests.test_notes_sensitive_ui -v
```

第八阶段自动化验收：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_media_tool_commands tests.test_media_tool_service tests.test_media_tool_ui tests.test_media_tool_ffmpeg_integration -v
```

第七阶段自动化验收：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_material_ui tests.test_material_library tests.test_material_repository tests.test_material_ffmpeg_integration -v
```

第六阶段自动化验收：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_script_service tests.test_script_editor_ui -v
```

第五阶段自动化验收：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_download_models tests.test_downloader_adapter tests.test_download_service tests.test_download_ffmpeg_integration tests.test_download_http_integration tests.test_download_ui -v
```

第四阶段自动化验收：

本阶段是数据与后台能力，没有新增界面。运行真实 FFmpeg 集成验收：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_material_ffmpeg_integration -v
```

该测试会临时生成 MP4、WAV、PNG，验证 FFprobe 类型识别、复制目录、重名规则和 FFmpeg 首帧缩略图。其他素材数据测试：

```powershell
.venv\Scripts\python.exe -m unittest tests.test_material_repository tests.test_material_library tests.test_media_detection -v
```

第九阶段人工验收：

参考截图：`artifacts/stage9_notes_sensitive_ui.png`。

1. 打开一个项目，进入“项目笔记”，输入包含选题、发布平台和创作备注的中文内容，确认保存状态从“未保存”变为“已保存”。
2. 关闭程序后重新打开该项目，确认笔记内容从项目根目录 `notes.md` 恢复。
3. 在未打开项目时进入“项目笔记”，确认编辑器禁用并显示“未打开项目”。
4. 确认程序目录下的 `sensitive_words.txt` 已包含预置中文词库；如需调整，可按一行一个词继续增删；进入“敏感词检查”，粘贴含时间码的脚本并点击“检查当前文本”。
5. 确认英文大小写均能命中，高亮数量与右侧列表一致，列表位置包含行号和列号。
6. 修改词库后再次点击检查，确认结果立即按新词库更新。
7. 临时重命名词库文件后点击检查，确认显示“词库不可用”且程序不崩溃；随后恢复文件名。

第八阶段人工验收：

参考截图：`artifacts/stage8_media_tools_ui.png`。

1. 无项目时进入“媒体工具箱”，选择 MP4 并转换为 MKV，确认输出目录可自行选择且转换成功。
2. 从视频提取 MP3，确认输出可播放。
3. 截取视频和音频片段，确认起止时间生效。
4. 使用 9:16、16:9、1:1 和自定义尺寸处理视频，确认画面完整、居中留黑边。
5. 对音频输入 `+6 dB` 和 `-3 dB`，确认处理成功。
6. 在底部任务抽屉取消进行中的任务，确认状态变为已取消且未完成输出被清理。
7. 打开项目后确认输出固定到“输出成品”、默认勾选加入素材库。
8. 无项目时选择输出目录，重启程序确认上次位置已记住。

第七阶段人工验收：

参考截图：`artifacts/stage7_material_library_ui.png`。

1. 打开一个项目，进入“素材库”。
2. 拖入或选择视频、音频、图片，确认默认不复制原文件。
3. 切换列表和缩略图视图，确认布局和选中反馈正常。
4. 添加多个标签，按名称或标签检索，确认结果数量同步更新。
5. 预览图片、视频和音频；视频和音频应由 FFplay 独立窗口打开。
6. 移除一条素材记录，确认界面和 `materials.json` 同步更新且磁盘文件仍存在。

第六阶段人工验收：

参考截图：`artifacts/stage6_script_editor_ui.png`。

1. 打开一个项目，进入“脚本文档”。
2. 新建 TXT 和 MD 脚本，输入中文、Markdown 和 `[00:23]` 时间码。
3. 切换文档或页面后返回，确认内容、光标和滚动位置仍在。
4. 使用“全选复制”，粘贴到剪映字幕面板，确认文字一致。
5. 使用“导出 TXT/导出 MD”，确认文件直接进入当前项目“脚本文档”目录。
6. 修改内容后关闭程序，确认重新打开时内容已自动保存。
7. 手动占用目标文件，确认保存失败有明确反馈且“未保存”状态保留。

第五阶段人工验收：

参考截图：`artifacts/stage5_download_ui.png`。

1. 新建并打开一个项目，进入“素材下载”。
2. 输入多行链接，确认有效行计数正确，无效行出现明确提示。
3. 选择“完整视频”，确认文件按顺序下载到当前项目“输出成品”目录。
4. 勾选“完成后加入项目素材库”，确认素材库索引新增对应记录。
5. 选择“仅提取音频”，确认输出为可播放的 MP3。
6. 取消一个等待中或进行中的任务，确认状态变为已取消且无 `.part` 残留。
7. 断开网络后运行任务，确认失败状态和错误摘要可见，后续任务仍会继续。


第三阶段人工验收：

1. 新建项目后关闭程序并重新打开，确认项目出现在“项目 > 最近打开”中。
2. 从最近项目列表重新打开项目，确认顶栏、侧栏和 Dashboard 显示同一个项目。
3. 重命名项目，确认显示名称更新且磁盘目录没有变化。
4. 删除项目，确认目录进入 Windows 回收站，最近项目列表同步移除。
5. 手动删除项目目录后重启，确认失效记录被清理并显示提示。
6. 未打开项目时确认“重命名项目”和“删除项目”为禁用状态。

第二阶段人工验收：

1. 启动程序，确认壁纸覆盖整个窗口。
2. 确认顶栏、侧栏、主内容区和上下文面板显示正确。
3. 确认首页欢迎面板、统计卡片、折线图、资料卡和最近处理记录层级清楚。
4. 将鼠标移到 Dashboard 卡片上，确认软霓虹辉光平滑增强。
5. 修改“项目活跃度”的时间范围下拉框，确认状态文案同步变化。
6. 切换占位导航，确认选中状态和页面淡入反馈。
7. 折叠和展开侧栏，确认布局没有跳动。
8. 使用“外观”选择本地图片，确认面板淡入且壁纸立即更新；按 `Esc` 或点击面板外可关闭。
9. 重启程序，确认壁纸自动恢复；删除原图后重启，确认回退默认壁纸。
10. 展开任务抽屉，并触发成功或失败通知，确认淡入、右下角完整显示且不被裁切。

第一阶段项目目录人工测试：

1. 启动程序并点击“新建项目”。
2. 选择一个已有目录作为项目根目录。
3. 确认目录中出现“原素材、脚本文档、音频文件、图片封面、输出成品”五个子目录。
4. 确认目录中出现 UTF-8 编码的 `project.json`。
5. 对同一个目录再次执行新建项目，程序应提示 `project.json` 已存在。

## 目录结构

```text
I:\word_tow
├─ app.py
├─ requirements.txt
├─ README.md
├─ sensitive_words.txt
├─ PRD.md
├─ UI_DESIGN.md
├─ DEVELOPMENT_PLAN.md
├─ THIRD_PARTY_NOTICES.md
├─ .gitignore
├─ third_party
│  └─ toolgood_words
│     ├─ LICENSE
│     ├─ SOURCE.md
│     └─ IllegalKeywords.txt
├─ artifacts
│  ├─ stage2_dark_dashboard.png
│  ├─ stage3_project_lifecycle.png
│  ├─ stage5_download_ui.png
│  ├─ stage6_script_editor_ui.png
│  ├─ stage7_material_library_ui.png
│  ├─ stage8_media_tools_ui.png
│  ├─ stage9_notes_sensitive_ui.png
│  └─ stage2_ui_preview.png
├─ video_workbench
│  ├─ app
│  │  └─ config.py
│  ├─ project
│  │  └─ manager.py
│  ├─ materials
│  │  ├─ importer.py
│  │  ├─ metadata.py
│  │  ├─ models.py
│  │  ├─ repository.py
│  │  └─ thumbnails.py
│  ├─ downloader
│  │  ├─ adapter.py
│  │  ├─ errors.py
│  │  ├─ ffmpeg.py
│  │  ├─ files.py
│  │  ├─ models.py
│  │  └─ service.py
│  ├─ scripts
│  │  └─ service.py
│  ├─ notes
│  │  └─ service.py
│  ├─ sensitive_words
│  │  └─ service.py
│  ├─ media_tools
│  │  ├─ commands.py
│  │  ├─ models.py
│  │  ├─ runner.py
│  │  └─ service.py
│  └─ ui
│     ├─ animations.py
│     ├─ main_window.py
│     ├─ shell.py
│     ├─ styles.py
│     ├─ pages
│     │  ├─ download.py
│     │  ├─ materials.py
│     │  ├─ notes.py
│     │  ├─ scripts.py
│     │  ├─ sensitive.py
│     │  └─ tools.py
│     └─ components
│        ├─ buttons.py
│        ├─ dashboard.py
│        ├─ dialogs.py
│        ├─ messages.py
│        ├─ page.py
│        ├─ task_drawer.py
│        ├─ wallpaper.py
│        └─ window_controls.py
└─ tests
   ├─ test_app_config.py
   ├─ test_download_ffmpeg_integration.py
   ├─ test_download_http_integration.py
   ├─ test_download_models.py
   ├─ test_download_service.py
   ├─ test_download_ui.py
   ├─ test_downloader_adapter.py
   ├─ test_material_ffmpeg_integration.py
   ├─ test_material_library.py
   ├─ test_material_repository.py
   ├─ test_material_ui.py
   ├─ test_media_detection.py
   ├─ test_media_tool_commands.py
   ├─ test_media_tool_ffmpeg_integration.py
   ├─ test_media_tool_service.py
   ├─ test_media_tool_ui.py
   ├─ test_notes_sensitive_ui.py
   ├─ test_notes_service.py
   ├─ test_project_lifecycle_ui.py
   ├─ test_dashboard_ui.py
   ├─ test_project_manager.py
   ├─ test_script_editor_ui.py
   ├─ test_script_service.py
   ├─ test_sensitive_words.py
   ├─ test_ui_components.py
   ├─ test_ui_shell.py
   └─ test_wallpaper.py
```

项目笔记保存在项目自身的 `notes.md`，敏感词库保存在程序目录的 `sensitive_words.txt`，二者均为普通 UTF-8 本地文件，不上传云端。

## 许可证

本项目原创源码和文档采用 MIT License，详见 `LICENSE`。第三方依赖、参考项目和内置数据继续适用各自原有许可证，详见 `THIRD_PARTY_NOTICES.md` 以及 `third_party/` 目录。
