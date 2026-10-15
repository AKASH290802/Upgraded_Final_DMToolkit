@echo off
echo ========================================
echo DM Toolkit Documentation Server
echo ========================================
echo.
echo Starting HTTP server for documentation sharing...
echo.
echo The documentation will be available at:
echo   http://localhost:8083/DM_Toolkit_Security_Workflow_Guide.html
echo.
echo Share this URL with other users on your network:
echo   http://[YOUR-IP-ADDRESS]:8083/DM_Toolkit_Security_Workflow_Guide.html
echo.
echo To find your IP address, run: ipconfig
echo.
echo Press Ctrl+C to stop the server
echo.

cd /d "c:\DM_toolkit\Documentation"
python -m http.server 8083

pause
