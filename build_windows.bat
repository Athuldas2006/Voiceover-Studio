@echo off
setlocal
cd /d "%~dp0"

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean --windowed --onedir ^
  --name "Voiceover Studio" ^
  --icon "assets\voiceover_studio.ico" ^
  --collect-all piper ^
  --collect-binaries onnxruntime ^
  --collect-binaries pygame ^
  --copy-metadata piper-tts ^
  voiceover_studio.py
if errorlevel 1 goto :error

set "APP_DIST=dist\Voiceover Studio"
if not exist "%APP_DIST%\Voiceover Studio.exe" goto :error

if exist voices xcopy voices "%APP_DIST%\voices\" /E /I /Y >nul
if exist history xcopy history "%APP_DIST%\history\" /E /I /Y >nul
if exist generated_voiceover.wav copy /Y generated_voiceover.wav "%APP_DIST%\" >nul

echo.
echo Build complete: %CD%\%APP_DIST%\Voiceover Studio.exe
echo Keep the voices and history folders beside the EXE.
pause
exit /b 0

:error
echo.
echo Build failed. Review the error above.
pause
exit /b 1

