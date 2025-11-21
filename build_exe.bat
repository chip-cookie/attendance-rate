@echo off
echo ========================================
echo 출석 관리 시스템 EXE 빌드
echo ========================================
echo.

echo [1/3] 필요한 패키지 설치 중...
pip install -r requirements.txt
echo.

echo [2/3] PyInstaller로 EXE 빌드 중...
pyinstaller --onefile --windowed --name="출석관리시스템" --icon=NONE attendance_app.py
echo.

echo [3/3] 빌드 완료!
echo.
echo EXE 파일 위치: dist\출석관리시스템.exe
echo.
pause
