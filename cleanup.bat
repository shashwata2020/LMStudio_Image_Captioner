@echo off
del push.bat
git add .
git commit -m "Remove push script"
git push
