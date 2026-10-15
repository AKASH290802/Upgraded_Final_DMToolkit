@echo off
rem Start the DM Toolkit from its own folder so the Tavant theme (.streamlit\config.toml) is used.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py %*
