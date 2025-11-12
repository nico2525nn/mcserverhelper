; インストーラーの基本情報
!define APP_NAME "MCServerHelper"
!define COMP_NAME "MCServerHelper"
!define VERSION "1.0.0"
!define EXE_NAME "MCServerHelper.exe"

; 生成されるインストーラーのファイル名
OutFile "${APP_NAME}-v${VERSION}-installer.exe"

; デフォルトのインストール先
InstallDir "$PROGRAMFILES\${APP_NAME}"

; インストーラーのUI
!include "MUI2.nsh"

!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Japanese"

Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    
    ; EXEファイルをコピー
    File "dist\${EXE_NAME}"
    
    ; READMEをコピー (任意)
    File "README.md"

    ; ショートカットを作成
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortCut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${EXE_NAME}"
    
    ; アンインストーラーを作成
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    ; ファイルとディレクトリを削除
    Delete "$INSTDIR\${EXE_NAME}"
    Delete "$INSTDIR\README.md"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"

    ; ショートカットを削除
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
SectionEnd
