@echo off
rem Hourly task: load new Qwen skills from the cache into Supabase (see src/load_supabase.py).
cd /d C:\master
"C:\Users\dhanu\AppData\Local\Programs\Python\Python311\python.exe" src\load_supabase.py --if-new >> reports\task_load_qwen.log 2>&1
