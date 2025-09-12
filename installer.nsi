!define APP_NAME "Error Analysis Tagging App"
!define COMP_NAME "ErrorAnalysisTaggingApp"
!define VERSION "1.0.0"
!define EXE_NAME "main.exe" # The name of the exe from PyInstaller
!define SETUP_NAME "${COMP_NAME}-Setup.exe"

# --- General ---
Name "${APP_NAME}"
OutFile "dist\${SETUP_NAME}"
InstallDir "$PROGRAMFILES\${APP_NAME}"
InstallDirRegKey HKLM "Software\${COMP_NAME}" "Install_Dir"
RequestExecutionLevel admin

# --- Interface ---
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "static\erroranalyzer_icon.ico"
!define MUI_UNICON "static\erroranalyzer_icon.ico"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

# --- Installer Section ---
Section "Install"
    SetOutPath $INSTDIR
    
    # Add all files from the build directory
    File /r "dist\main\*.*"
    
    # --- Create Shortcuts ---
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
    CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
    
    # --- Registry ---
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMP_NAME}" "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMP_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMP_NAME}" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMP_NAME}" "NoRepair" 1
    # Remember install directory for future upgrades
    WriteRegStr HKLM "Software\${COMP_NAME}" "Install_Dir" "$INSTDIR"
    WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

# --- Uninstaller Section ---
Section "Uninstall"
    # Remove shortcuts
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"

    # Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${COMP_NAME}"
    DeleteRegKey HKLM "Software\${COMP_NAME}"
    
    # Remove the installation directory and all its contents
    RMDir /r "$INSTDIR"
SectionEnd
