# BOTNEX Quiz Academy - Class 12 Telegram Quiz Bot

Premium chapter-wise MCQ practice bot. **Powered by BOTNEX** (by Chandan Nayak).

## What it does
`/start` -> animated styled-font intro -> sticker -> welcome photo/animation with student's name ->
Class 12th -> Subject -> Chapter -> questions one by one (random order per student, one answer, no feedback) ->
**Next Question / End Exam** -> result + sticker + **white & golden certificate (PNG)** -> **Know Answers** review.
When every question of the chapter has been used, the exam ends automatically.
Everything is button based (only `/start` is a command). Buttons are coloured (blue/green/red).

## Folder structure
```
botnex_quiz/        bot code (flow.py = all behaviour, ui.py = texts/buttons, storage.py, questionbank.py,
                    certificate.py, aio_gateway.py + aio_app.py = Telegram glue, __main__.py = entry)
questionbank/class12/*.json   the question bank (single source of truth)
assets/             welcome.mp4 (shine loop), welcome.jpg, fonts/
tools/              validate_questionbank.py, build_welcome_media.py
tests/              47 automated tests (python -m unittest discover -s tests -t .)
```

## Environment variables (never commit secrets)
| Name | Needed | Meaning |
|---|---|---|
| BOT_TOKEN | yes | token from @BotFather (new bot) |
| OWNER_ID | yes | your numeric Telegram id - only this id can open the Owner Panel |
| MONGO_DB_URI | yes in production | MongoDB connection string (use a NEW database name for this bot) |
| MONGO_DB_NAME | no | default `botnex_quiz` |
| OWNER_USERNAME / SUPPORT_LINK | no | defaults: lll_SOLAC_lll, https://t.me/BOT_NEX_A |
| BOT_DISPLAY_NAME | no | default `BOTNEX Quiz Academy` |
| STICKER_ID | no | default intro sticker (owner can change it from the panel any time) |

Without `MONGO_DB_URI` the bot runs with memory storage (data lost on restart) - only for quick tests.

## Quick start (Android friendly)
1. @BotFather -> `/newbot` -> name + username ending in `bot` -> copy the token.
2. Get your numeric id (any "user id" bot). Do not post it publicly.
3. Create a free MongoDB database (Atlas or any host) -> copy the URI.
4. Put the project in a GitHub repo, create a **worker** service on your host (Railway / VPS / Docker), set the env variables
   above, start command: `python -m botnex_quiz` (Procfile and Dockerfile included).
5. Open your bot -> `/start`. Owner sees an extra **Owner Panel** button.
6. Run **only one copy** of the bot (long polling: two copies fight over updates).

Run locally: `pip install -r requirements.txt` then `python -m botnex_quiz`.

## Owner Panel (button only)
Stats, Users list (name, username, id, attempts, last active), **Change Sticker**, **Premium Sticker**,
**Premium Emoji**, **Welcome Photo** (photo or GIF), Reset Welcome, **Premium mode ON/OFF**, Flagged questions show/hide.

### Premium mode (OFF by default)
Needs a Telegram Premium account for the owner. Steps when you have Premium:
1. Panel -> **Premium Sticker** -> send a premium sticker.
2. Panel -> **Premium Emoji** -> send ONE message with custom emojis in this order:
   sparkle, trophy, book, check, cross, target, fire, star, next, flag, cap, diamond (12 slots; fewer is fine).
3. Panel -> **Premium: OFF** -> turns ON. Texts then use animated custom emoji, buttons get emoji icons, and the premium
   sticker is used. If Telegram ever rejects it, the bot switches itself OFF, keeps working normally and tells you.

## Question bank
`questionbank/class12/<subject>.json` = list of records (id, subject, class, chapter_no, chapter, question,
options{a,b,c,d}, answer, optional explanation/flags/status). Add a chapter/subject = edit/add JSON, no code change.
New class = new folder `questionbank/class11/` (Class 11 button is locked for now).
Check before deploy: `python tools/validate_questionbank.py` (rejects malformed/duplicate records and tells you why).
By default these are **hidden** from exams (owner can show them in the panel): questions whose answer key needs a teacher
check (14) and questions that need a figure that is not in the bank (19). 3 questions without options in the source book are rejected.
`explanation` is empty in the bank, so Know Answers shows the correct option only (no invented explanations).

## Database (MongoDB)
`users` {_id=telegram id, first_name, username, registered_at, last_active, attempts, completed}
`exams` {_id, user_id, chat_id, subject_slug, subject, chapter_no, chapter, order[question ids], index, answers{qid:letter},
status active|completed|ended|abandoned, started_at, finished_at, result{total,attempted,correct,incorrect,unattempted,marks,accuracy},
last_msg_id, cert_file_id}
`settings` {_id='main', premium_mode, include_hidden, sticker_normal, sticker_premium, premium_emoji{slot:id}, welcome_file_id, welcome_kind}

## Rules implemented
One answer per question and it is locked; no correct/incorrect shown during the exam; Next only after answering; old questions
stay in chat (only their buttons are locked); random order per student, no repeats; result counts only the questions shown;
marks = correct answers (1 each, no negative marking); accuracy = correct / attempted; Know Answers only after the exam ends.
Certificate says "Powered by BOTNEX" and is drawn by code (no template image).
