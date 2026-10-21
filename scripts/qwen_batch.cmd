@echo off
rem Kaggle 2,000-posting Qwen batch on the free Groq tier. Resumable: finished postings are cached.
rem Re-run any time (Task Scheduler: SkillPipeline\QwenBatch); the hourly LoadQwen task copies results to Supabase.
cd /d C:\master
"C:\Users\dhanu\AppData\Local\Programs\Python\Python311\python.exe" src\extract_skills.py --provider groq --model qwen/qwen3.8-27b --postings data\processed\extraction_sample_2000.csv --prompt prompts\skill_extraction_v3.txt --tag sample2000 --delay 4 >> reports\extract_sample2000_qwen.log 2>&1
