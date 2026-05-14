@echo off
echo ===================================================
echo Compilador MonoLithiiun Explorer (PyInstaller)
echo ===================================================
echo Instalando o PyInstaller (compilador)...
pip install pyinstaller

echo.
echo Compilando o navegador em um arquivo .EXE standalone...
echo Isso vai empacotar o Python, PyQt5 e seu codigo em um unico lugar.
echo.

pyinstaller --noconfirm --onedir --windowed --icon "Principalappico.ico" --name "MonoLithiiun Explorer" --add-data "*.png;." --add-data "*.ico;." "main.py"

echo.
echo ===================================================
echo COMPILACAO CONCLUIDA!
echo O seu navegador executavel esta na pasta "dist\MonoLithiiun Explorer"
echo Voce pode zipar essa pasta e mandar para os seus clientes!
echo ===================================================
pause
