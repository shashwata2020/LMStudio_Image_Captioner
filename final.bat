@echo off
del cleanup.bat
git add .
git commit -m "Remove cleanup script"
git push
