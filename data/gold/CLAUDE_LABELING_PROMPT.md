# Prompt for labelling the gold set with Claude (chat)

Upload these 3 files to a new Claude chat: `gold_postings.csv`, `gold_labels.csv`, `LABELING_RULES.md`.
Then paste the prompt below. Change the name and sectors to yours.

---

I am labelling skills for a gold set. My name is <NAME>. I label only these sectors: <SECTORS>.

1. Follow `LABELING_RULES.md` exactly.
2. Show me one posting at a time from `gold_postings.csv` (only my sectors, in order of `n`). Show the full
   `description`. Do NOT suggest skills before I reply.
3. I reply with my skills. Then check them against the rules: list any skill that is not in the text,
   any rule break (degree, years, licence, trait, task-only duty), and any clear skill I missed.
   Keep it short.
4. When I say "save", write my final list into `gold_labels.csv` for that `posting_id`:
   `gold_skills` = skills separated by "; ", `labeled_by` = my name, `notes` = anything unclear.
   Leave `suggested_skills` empty, because no AI list was shown first.
5. Then show the next posting.
6. When I say "done", give me the updated `gold_labels.csv` to download.
