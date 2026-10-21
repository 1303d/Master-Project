@echo off
rem Nightly task: Greenhouse -> clean -> dedupe -> extract (LiteLLM) -> ESCO/O*NET -> Supabase (see src/pipeline.py).
cd /d C:\master
"C:\Users\dhanu\AppData\Local\Programs\Python\Python311\python.exe" src\pipeline.py --max-new 30 >> reports\task_greenhouse.log 2>&1
