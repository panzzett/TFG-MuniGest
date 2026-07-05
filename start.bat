@echo off
rem =======================================================================
rem  Trabajo Fin de Grado en Ingenieria Informatica
rem  Universidad Internacional de La Rioja (UNIR)
rem  Prototipo de software de tramitacion de expedientes electronicos
rem  para administraciones locales
rem  Autor: Carlos Galvez Reguera
rem  Ano: 2026
rem
rem  Este archivo forma parte de este proyecto, desarrollado como
rem  Trabajo Fin de Grado en Ingenieria Informatica de la UNIR.
rem
rem  Licencia: MIT
rem =======================================================================
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python no esta instalado. & pause & exit /b 1)
python -m pip install --quiet -r api\requirements.txt
python run_local.py
pause
