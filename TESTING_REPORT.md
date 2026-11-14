# BOTNEX Quiz Bot - Testing Report

Environment: offline container, Python 3.12, Pillow, ffmpeg. aiogram, motor and a real MongoDB were NOT available.

## Result: 47 automated tests - all passed
Command: `python -m unittest discover -s tests -t .`

### Passed checks
- clean_text [Cert] - ok
- each_render_is_independent [Cert] - ok
- renders_png_with_expected_size [Cert] - ok
- unusual_input_never_crashes [Cert] - ok
- include_hidden_toggle_changes_pool [Admin] ... Rejected mathematics.json/mat12_9: empty option text
- owner_input_wrong_item_is_rejected [Admin] - ok
- owner_panel_stats_users [Admin] - ok
- owner_toggles_and_sets_sticker_any_time [Admin] - ok
- plain_text_gets_friendly_redirect [Admin] - ok
- premium_emoji_capture_maps_slots_in_order [Admin] - ok
- premium_mode_uses_premium_assets_and_falls_back_safely [Admin] - ok
- students_never_see_or_use_owner_panel [Admin] ... Non-owner 77 tried admin action
- answer_locks_shows_next_end_and_hides_correctness [Journey] - ok
- answers_not_available_during_exam [Journey] - ok
- chapter_click_shows_first_question_directly_no_feedback [Journey] - ok
- chapter_list_paginates_and_back [Journey] - ok
- class11_locked_class12_lists_five_subjects [Journey] - ok
- empty_chapter_alert [Journey] - ok
- end_exam_after_answering_17_style [Journey] - ok
- end_exam_midway_counts_only_shown_questions [Journey] - ok
- full_exam_auto_completion_result_certificate_review [Journey] - ok
- garbage_and_stale_callbacks_never_crash [Journey] ... Callback failed: a:
- hidden_questions_not_served_until_owner_enables [Journey] - ok
- many_students_at_once_are_isolated [Journey] ... Callback failed: a:6d2829a30c:0:c
- new_exam_closes_old_and_try_again [Journey] - ok
- next_keeps_previous_questions_and_requires_answer [Journey] - ok
- other_students_cannot_touch_my_exam [Journey] ... User 666 tried to use exam of 1001
- random_order_per_student_and_no_repeats [Journey] - ok
- restart_recovery_exam_continues [Journey] - ok
- same_user_double_click_is_serialised [Journey] - ok
- start_intro_sticker_welcome [Journey] - ok
- sticker_failure_does_not_break_start [Journey] - ok
- welcome_caches_media_file_id [Journey] - ok
- counts_and_subjects [RealBank] - ok
- every_loaded_question_valid [RealBank] - ok
- hidden_not_in_live_pool [RealBank] - ok
- duplicates_detected [Validation] ... Duplicate id x in physics.json ignored
- flag_rules [Validation] - ok
- new_class_folder_needs_no_code [Validation] - ok
- rejects_malformed_never_silently [Validation] ... Rejected physics.json/noans: answer 'e' is not a/b/c/d
- unreadable_file_does_not_crash [Validation] ... Cannot read /tmp/tmp7ypkh95j/class12/bad.json: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
- exam_roundtrip_and_isolation [TestMemory] - ok
- settings_defaults_and_persist [TestMemory] - ok
- user_lifecycle [TestMemory] - ok
- exam_roundtrip_and_isolation [TestMongoWithFakeMotor] - ok
- settings_defaults_and_persist [TestMongoWithFakeMotor] - ok
- user_lifecycle [TestMongoWithFakeMotor] - ok

### Question-bank validation (tools/validate_questionbank.py)
```
WARNING:botnex.qb:Rejected physics.json/phy14_43: empty option text
WARNING:botnex.qb:Rejected physics.json/phy14_44: empty option text
files: 5  records: 2044  loaded: 2041  rejected: 3  duplicates: 0  hidden-by-default: 33
  REJECTED mathematics.json mat12_9: empty option text
  REJECTED physics.json phy14_43: empty option text
  REJECTED physics.json phy14_44: empty option text
Class 12
  Chemistry    chapters=15 questions= 586 live= 586
  Physics      chapters=15 questions= 438 live= 416
  Mathematics  chapters=12 questions= 361 live= 354
  Zoology      chapters= 5 questions= 294 live= 291
  Botany       chapters= 6 questions= 362 live= 361
```

## Bugs found by the tests and fixed during development
- Settings returned by MemoryStorage shared nested dicts with the stored copy (mutating one changed the other) -> deep copies.
- Callback "Class 11" answered the same Telegram callback twice -> single answer.
- GFS Baskerville OTF rendered blank in Pillow -> certificate title now uses Caladea Bold.
- Certificate seal overlapped the stat boxes -> layout rebuilt and checked visually (two samples rendered and viewed).

## NOT testable here (must be checked on the real bot after deploy)
| Area | Why | What to check |
|---|---|---|
| aiogram wiring (`aio_app.py`, `aio_gateway.py`) | aiogram not installable offline; files are compile-checked only | /start, buttons, edits, stickers, photo upload |
| Coloured buttons / premium button icons | need real Telegram clients (colours need clients updated after Feb 2026) | button colours; premium mode with a Premium account |
| Custom (animated) emoji and premium sticker | need an owner with Telegram Premium | Owner Panel -> Premium flow; auto fallback message |
| Intro sticker | the supplied file id may belong to another bot | if not shown, Owner Panel -> Change Sticker |
| Real MongoDB | only an in-memory fake of motor was used | restart the bot mid-exam and continue |
| Welcome shine animation on phones | video built and a frame inspected only | looks smooth, loops |
| Load / Telegram rate limits | no real traffic | try 5-10 students at once |
| Deployment | no host access | follow README quick start |

## Known limitations
- 33 questions hidden by default (14 teacher-check keys, 19 figure-dependent); 3 rejected (no options in source). Owner can show hidden ones.
- No explanations exist in the question bank.
- Difficulty tags exist in the data but are not used (random order, as requested).
- Class 11 is a locked placeholder.
- One active exam per student (starting another closes the previous one).
- A chapter exam can be long (largest chapter has ~90 questions) - students can press End Exam any time.
- Answer keys come from the source books; wrong keys in the books would give wrong marks (see review lists shipped with the question banks).
