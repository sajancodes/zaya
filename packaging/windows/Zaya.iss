; Inno Setup script for Zaya Windows installer
; Created and developed by Sajan Rai for Zaya.

#ifndef MyAppVersion
#define MyAppVersion "0.5.0"
#endif

#ifndef MyAppBuild
#define MyAppBuild "10007"
#endif

#define MyAppName "Zaya"
#define MyAppPublisher "Sajan Rai"
#define MyAppURL "https://zayaxyz.vercel.app"
#define MyAppExeName "Zaya.exe"
#ifndef SourceAppDir
#define SourceAppDir "..\..\dist\windows\Zaya"
#endif

[Setup]
AppId={{9F5781E2-A23C-4C7D-8946-7DF45F60B8E1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL=https://github.com/sajancodes/zaya-companion-releases
DefaultDirName={localappdata}\Programs\Zaya
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=ZayaSetup
OutputDir=..\..\dist\windows
SetupIconFile=..\..\config\jarvis.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "codingskill"; Description: "Install Zaya Coding Skill (internet required)"; GroupDescription: "Adds autonomous coding and software setup capabilities powered by OpenCode."; Flags: unchecked

[Files]
Source: "{#SourceAppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\config\jarvis.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\config\jarvis.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--install-coding-skill"; Tasks: codingskill; StatusMsg: "Installing optional Coding Skill…"; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExeName}"; Flags: nowait; Check: ShouldRestartZaya

[Code]
function ShouldRestartZaya: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:ZAYARESTART|0}') = '1');
end;

// User data removal prompt on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    UserDataDir := ExpandConstant('{localappdata}\Zaya');
    if DirExists(UserDataDir) and not UninstallSilent then
    begin
      if MsgBox('Would you like to remove your local Zaya data (memory, logs, cached models) as well?' + #13#10 +
                'Select No to keep your personal configurations and databases for future installations.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(UserDataDir, True, True, True);
      end;
    end;
  end;
end;
