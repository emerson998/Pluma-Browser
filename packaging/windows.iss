#ifndef AppVersion
#define AppVersion "0.2.0"
#endif
[Setup]
AppId=Emerson.PlumaBrowser
AppName=Pluma Browser
AppVersion={#AppVersion}
AppPublisher=Emerson Oliveira
DefaultDirName={localappdata}\Programs\Pluma
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release
OutputBaseFilename=Pluma-{#AppVersion}-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Pluma.exe
ChangesAssociations=yes
[Files]
Source: "..\dist\Pluma\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{userprograms}\Pluma Browser"; Filename: "{app}\Pluma.exe"
[Registry]
Root: HKCU; Subkey: "Software\Classes\PlumaURL"; ValueType: string; ValueData: "Pluma Browser"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\PlumaURL"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\PlumaURL\shell\open\command"; ValueType: string; ValueData: """{app}\Pluma.exe"" ""%1"""
Root: HKCU; Subkey: "Software\Pluma\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Pluma Browser"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Pluma\Capabilities\URLAssociations"; ValueType: string; ValueName: "http"; ValueData: "PlumaURL"
Root: HKCU; Subkey: "Software\Pluma\Capabilities\URLAssociations"; ValueType: string; ValueName: "https"; ValueData: "PlumaURL"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Pluma Browser"; ValueData: "Software\Pluma\Capabilities"; Flags: uninsdeletevalue
