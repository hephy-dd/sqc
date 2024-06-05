; Inno Setup template

#ifndef Version
    #error The define variable Version is not set! Use /D Version=value to set it.
#endif

#define Organization "HEPHY"
#define Name "SQC"
#define ExeName "sqc.exe"

[Setup]
AppId={#Organization}_{#Name}_{#Version}
AppName={#Name}
AppVersion={#Version}
DefaultDirName={userappdata}\{#Organization}\sqc\{#Version}
DefaultGroupName={#Name}
OutputDir=dist
OutputBaseFilename=sqc-{#Version}-win-x64-setup
SetupIconFile=src\sqc\assets\icons\sqc.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "dist\sqc\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\{#Name} {#Version}"; Filename: "{app}\{#ExeName}"
Name: "{group}\{#Name} {#Version}"; Filename: "{app}\{#ExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{app}\{#ExeName}"; Description: "{cm:LaunchProgram,{#Name} {#Version}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[UninstallRun]
Filename: "{app}\uninstall.exe"
