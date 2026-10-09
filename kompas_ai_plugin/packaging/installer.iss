; Inno Setup script: KompasAI_Setup.exe from the PyInstaller folder build.
;   iscc /DAppVersion=0.1.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppName=КОМПАС-AI
AppVersion={#AppVersion}
AppPublisher=KompasAI
DefaultDirName={autopf}\KompasAI
DefaultGroupName=КОМПАС-AI
OutputDir=..\dist
OutputBaseFilename=KompasAI_Setup_{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=icon\kompas_ai.ico
UninstallDisplayIcon={app}\KompasAI.exe

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Ярлык на рабочем столе"; Flags: unchecked

[InstallDelete]
; Libraries of an older version must not mix with the new ones.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\KompasAI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\КОМПАС-AI"; Filename: "{app}\KompasAI.exe"
Name: "{group}\Удалить КОМПАС-AI"; Filename: "{uninstallexe}"
Name: "{autodesktop}\КОМПАС-AI"; Filename: "{app}\KompasAI.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\KompasAI.exe"; Description: "Запустить КОМПАС-AI"; Flags: nowait postinstall skipifsilent
