; PartBridge v0.0.4 安装包（Inno Setup 6）
; 用法：ISCC.exe packaging/PartBridge.iss

#define MyAppName "PartBridge"
#define MyAppVer "0.0.9"
#define MyAppPublisher "li-wanxin"
#define MyAppURL "https://github.com/li-wanxin/ComponentLib_PartBridge"
#define MyAppExeName "PartBridge.exe"

[Setup]
AppId={{8E4C2A61-7D33-4B8F-9A55-PARTBRIDGE004}
AppName={#MyAppName}
AppVersion={#MyAppVer}
AppVerName={#MyAppName} v{#MyAppVer}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=PartBridge-Setup-v{#MyAppVer}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\app\app.ico

[Languages]
; 系统未内置 ChineseSimplified.isl，使用默认英文向导（界面本身是中文的）
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: checkedonce

[Dirs]
; 授予 Users 组写权限：settings.json / UserData 缓存等软件数据统一存放在安装目录下
Name: "{app}"; Permissions: users-modify

[InstallDelete]
; 应用内升级下载到安装目录的升级包：新版本装好后自动清除（用户要求"安装后自动清除"）
Type: files; Name: "{app}\PartBridge-Setup-*.exe"
Type: files; Name: "{app}\PartBridge-Portable-*.exe"
Type: files; Name: "{app}\PartBridge_更新下载.exe"
Type: files; Name: "{app}\PartBridge_旧版本.exe"

[Files]
; 安装版采用 onedir 目录式（运行时直接从安装目录加载 DLL，不再解压到 %TEMP%，
; 根治杀软首扫竞态导致的 "Failed to load Python DLL" 偶发错误 —— Lab Console 同款修复）
Source: "..\release\dist\PartBridge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时保留用户数据（settings.json 由用户自行处理），仅清理临时文件
Type: files; Name: "{app}\*.log"
