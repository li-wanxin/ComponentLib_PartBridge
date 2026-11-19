; PartBridge v0.0.4 安装包（Inno Setup 6）
; 用法：ISCC.exe packaging/PartBridge.iss

#define MyAppName "PartBridge"
#define MyAppVer "0.0.5"
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

[Languages]
; 系统未内置 ChineseSimplified.isl，使用默认英文向导（界面本身是中文的）
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: checkedonce

[Dirs]
; 授予 Users 组写权限：settings.json / UserData 缓存等软件数据统一存放在安装目录下
Name: "{app}"; Permissions: users-modify

[Files]
Source: "..\release\portable\PartBridge.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时保留用户数据（settings.json 由用户自行处理），仅清理临时文件
Type: files; Name: "{app}\*.log"
