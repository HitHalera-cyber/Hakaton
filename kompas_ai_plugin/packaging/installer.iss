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
UninstallDisplayIcon={app}\KompasAI_icon_v2.ico

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Ярлык на рабочем столе"; Flags: unchecked

[InstallDelete]
; Libraries of an older version must not mix with the new ones.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\KompasAI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
; Microsoft Visual C++ runtime: python312.dll and numpy need it; a fresh Windows
; may not have it ("Failed to load Python DLL ... module not found").
Source: "vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
; the icon as its own file with a new name: Windows caches shortcut icons by
; path, and the exe path stays the same between versions
Source: "icon\kompas_ai.ico"; DestDir: "{app}"; DestName: "KompasAI_icon_v2.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\КОМПАС-AI"; Filename: "{app}\KompasAI.exe"; IconFilename: "{app}\KompasAI_icon_v2.ico"
Name: "{group}\Удалить КОМПАС-AI"; Filename: "{uninstallexe}"
Name: "{autodesktop}\КОМПАС-AI"; Filename: "{app}\KompasAI.exe"; IconFilename: "{app}\KompasAI_icon_v2.ico"; Tasks: desktopicon

[Run]
; refresh the Windows icon cache so the new icon shows at once
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden skipifdoesntexist
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /passive /norestart"; StatusMsg: "Установка Microsoft Visual C++ Runtime..."; Flags: shellexec waituntilterminated; Verb: runas; Check: VCRedistNeeded
Filename: "{app}\KompasAI.exe"; Description: "Запустить КОМПАС-AI"; Flags: nowait postinstall skipifsilent

[Code]
function VCRedistNeeded: Boolean;
var
  Installed: Cardinal;
begin
  Result := not (RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
                                    'Installed', Installed) and (Installed = 1));
end;
