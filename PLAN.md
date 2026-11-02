# BookBot — Project Blueprint (single source of truth)

A public Telegram bot that takes a book title (Arabic / French / English), searches
**legal free libraries** only, and sends back the **PDF**.

- Framework: python-telegram-bot v21+ (async)
- Format: PDF only (DJVU results filtered out in v1; conversion = optional later)
- Interface: AR / FR / EN — auto-detect + /lang command (saved per user in SQLite)
- Results: Top-5 inline keyboard, user taps to download
- Hosting first: local PC, then VPS/Docker later
- Sources (legal / open-access): Open Library + Internet Archive, Google Books (free full text), Project Gutenberg, Noor Library (noor-book.com) for Arabic

## Legal note (baked into the design)

The bot only queries open-access / public-domain / free-download libraries.
It never touches pirate libraries and always shows the source name on each result.

## Architecture flow

```
User sends title
   └─> detect language + normalize query (strip Arabic diacritics, unify hamza, unidecode)
        └─> parallel search across sources (asyncio.gather)
             └─> merge + dedupe + fuzzy rank (rapidfuzz)
                  └─> Top-5 inline keyboard (title • author • year • 📚 source)
                       └─> user taps
                            └─> resolve direct PDF URL from that source
                                 └─> stream download (≤ 50 MB, Telegram hard limit)
                                      └─> validate (%PDF- magic bytes)
                                           └─> send as document with caption
                                                └─> delete temp file (JobQueue cleanup)
```

## Folder structure

```
bookbot/
├── .env                    # BOT_TOKEN (never committed)
├── .env.example
├── requirements.txt        # python-telegram-bot, httpx, aiosqlite, rapidfuzz, bs4, python-dotenv
├── main.py                 # entry point: build Application, register handlers, run_polling
├── config.py               # settings loaded from .env (token, limits, paths)
├── PLAN.md                 # this file — we check steps off here
├── bot/
│   ├── handlers/
│   │   ├── start.py        # /start, /help, /about
│   │   ├── search.py       # receives any text = a book title → runs the search pipeline
│   │   ├── download.py     # callback_query: user tapped a result → download & send PDF
│   │   └── lang.py         # /lang command → inline language menu
│   └── keyboards.py        # builders for Top-5 menu + language menu
├── core/
│   ├── models.py           # BookResult dataclass: title, author, year, source, pdf_url, ia_id…
│   ├── ranker.py           # merge, dedupe, fuzzy-score vs the user query
│   ├── downloader.py       # httpx streaming download, 50 MB cap, PDF validation
│   └── ratelimit.py        # per-user buckets (searches/min, downloads/hour)
├── sources/
│   ├── base.py             # BookSource abstract: search(query, lang) -> [BookResult]; get_pdf(result)
│   ├── openlibrary.py      # openlibrary.org/search.json → IA id
│   ├── internetarchive.py  # archive.org: resolve IA id → public-domain PDF
│   ├── googlebooks.py      # Google Books API, free full text only
│   ├── gutenberg.py        # gutendex.com API (good for FR/EN classics)
│   └── noor.py             # noor-book.com scraper (no official API) — polite, rate-limited
├── i18n/
│   ├── detect.py           # script + keyword heuristic (Arabic chars → ar; French markers → fr; else en)
│   ├── ar.json  fr.json  en.json
│   └── i18n.py             # t(user_id, key, **kwargs) helper
├── db/
│   ├── database.py         # aiosqlite init + schema (users, downloads)
│   └── repo.py             # get/set user lang, log downloads, stats
└── utils/
    ├── text.py             # Arabic normalization (تشكيل, hamza, ta-marbuta), unidecode fallback
    └── logging.py          # file + console logging
```

## Constraints to respect while coding

- Telegram Bot API send limit: **50 MB** per file → downloader streams and aborts past the cap.
- Noor / Waqfeya expose many books as **DJVU** → v1 keeps PDF-only results, we filter by extension/content-type.
- Be polite to scrapable sites: 1 request at a time, delays, cache results for a few minutes.
- Every result shown to users carries its source + a link (transparency).

## Step-by-step build plan (one at a time — never start N+1 before N is ✅)

| # | Step | What we build | Checkpoint (how we know it's done) |
|---|------|---------------|-------------------------------------|
| 1 | Skeleton & hello world | folder, venv, requirements, config.py, main.py with /start /help | bot replies to /start on Telegram |
| 2 | i18n + user language | ar/fr/en JSON, detect.py, /lang inline menu, SQLite users table | bot greets in your language and remembers it after restart |
| 3 | Search pipeline (text) | models.py, sources/base.py, openlibrary.py, utils/text.py | send a title → bot lists top-5 as text with source names |
| 4 | Top-5 inline menu | internetarchive.py, ranker.py, keyboards.py, callback handler | tapping a result logs/echoes the correct selection |
| 5 | PDF download & send | downloader.py + resolve PDF from OL/IA | bot actually sends a real PDF ≤ 50 MB, temp files cleaned |
| 6 | More sources | googlebooks.py, gutenberg.py, noor.py, parallel merge | Arabic query → Noor results; FR/EN → OL/GB/Gutenberg |
| 7 | Public hardening | rate limits, friendly errors (3 langs), logs, /stats /ban /about, download queue | safe to open to the public |
| 8 | Run 24/7 locally | .env.example, README, auto-restart script, optional Dockerfile | bot survives crashes and reboots |

## Progress log

- **Step 1 — code complete** (2026-11-01). Verified: token valid (@maktabati_downloader_bot), deps installed (python-telegram-bot 22.8, python-dotenv 1.2.4, Python 3.12), bot boots and polls cleanly. ⏳ Awaiting user's `/start` test on their device → then fully done.
- **Step 2 — code complete** (2026-11-01). i18n ar/fr/en JSONs, detect.py (script+keyword heuristic), /lang inline menu, SQLite users table via aiosqlite, handlers moved into bot/handlers/. Tests green: keys complete, 7/7 detection cases, sqlite round-trip, boot smoke OK. ⏳ Awaiting user's checkpoint: greet → /lang → restart → memory.
- **Step 3 — code complete** (2026-11-01). core/models.py (BookResult), sources/base.py (BookSource ABC), sources/openlibrary.py (+ separated _parse_docs for unit tests), utils/text.py (Arabic normalization), real search handler with top-5 text results, new i18n keys (searching / results_header / no_results / error_generic / menu_coming). Tests: normalization 4/4, parser fixture 3/3 (public→pdf_url, borrowable/no_ebook→none), live IA check verified the {ia_id}/{ia_id}.pdf pattern (200 application/pdf) and showed restricted items return 401/403 → validates the ebook_access=public filter; live OL search blocked from sandbox IP → runs on user's PC. ⏳ Awaiting user checkpoint: send a title → top-5 list.
- **Step 3 — checkpoint PASSED** (2026-11-01). User received real AR results from Open Library for «فن الحرب» (normalization matched فنّ الحرب). User-side hiccup resolved (zip re-extract + venv rebuild).
- **Step 4 — code complete** (2026-11-01). sources/internetarchive.py (advancedsearch API, downloads-desc sort, license info), core/ranker.py (ia_id dedupe + merge + rapidfuzz scoring + pdf bonus), numbered tap-buttons (results_keyboard + dl:<cache>:<i> callback_data + results_cache in bot_data, bounded), download.py callback echoes selection with pdf link when known. Tests: ranker 2/2, keyboard, i18n keys, LIVE IA EN+AR searches OK. ⏳ Awaiting user checkpoint: tap a number → correct book echoed.
- **Step 4 — bugfix: "results expired" on every tap** (2026-11-01). User reported each tap answered ⌛ expired. Root cause: results_keyboard() generated cache_id A (baked into buttons) while _cache_put() generated a second id B and stored results under B → buttons pointed at an id never stored. Fix: _cache_put(context, results, cache_id) now stores under the buttons' id (single source of truth). Regression test scripts/test_step4_fix.py: per-button lookup ✅, stale-id miss → expired ✅ (correct for old messages / restart), bounded cache 40 ✅, compile OK. ⏳ Awaiting user checkpoint: tap a number → correct book echoed.
- Step 5 next: real PDF download — core/downloader.py (httpx streaming, 50 MB cap, %PDF- magic check), resolve via HEAD + /metadata fallback, send_document with caption, temp cleanup. IA intel: restricted items return 401/403 → treat as not-downloadable.
- **Step 5 — code complete** (2026-11-01) + user modifications baked in. core/downloader.py (httpx streaming, 50 MB cap via Content-Length pre-check + runtime byte-count abort, %PDF- magic validation, partial file always wiped on failure). sources/internetarchive.py += resolve_ia_pdf() via archive.org/metadata — finds the item's REAL pdf filename (the {id}.pdf guess is often wrong). download.py rewritten into real delivery: resolve → status msg → download → reply_document (caption + support line) → status→sent; per-user busy lock vs double-taps; TooLarge/NotPdf/DownloadError → friendly trilingual errors; **temp PDF deleted in finally the moment delivery finishes (user requirement: keep machine/db clean)**. Branding per user: BookBot → مكتبتي (Maktabati) everywhere, source list removed from greeting (just "send title → get PDF"), support contact @vxgix in start/help/caption/sent, post_init sets public bot name "Maktabati 📚" + description + about via Bot API (@username unchanged — not changeable). Tests: i18n parity 3 langs × 19 keys, safe_filename 4/4 (traversal-safe, Arabic kept), %PDF- validation (real+garbage), LIVE IA resolve of user's exact book → real Arabic-named PDF URL, live cap-abort test (partial wiped), compile OK. ⏳ Awaiting user checkpoint: tap a number → real PDF document arrives, tmp folder empty afterwards.
- **Step 5 revision — user chose link-only delivery** (2026-11-01). After testing real file delivery ("its really good"), the user decided a tap should return an instant DIRECT PDF LINK instead of downloading/sending the file (faster, no 50 MB ceiling). download.py: resolve (pdf_url or archive.org/metadata) → quick HEAD guard (401/403 = restricted → err_no_pdf; verified pattern from Step 3) → picked/picked_pdf message with support line. i18n: file-delivery keys (downloading/sent/busy/caption/err_too_large/err_not_pdf/err_download) removed, picked/picked_pdf restored in all 3 languages; texts updated to "I'll send the PDF link". core/downloader.py KEPT in codebase (unused) for a possible opt-in file delivery later. Tests: i18n parity 3×14 keys, downloader unit tests still green, live IA resolve OK, compile OK. ⏳ Awaiting user checkpoint: tap → instant direct link.
- **Step 5 fix — 404 dead links now verified out** (2026-11-01). User: "the links ive tried in many books it says 404 not found". Root cause: pdf_url is the GUESS {ia_id}/{ia_id}.pdf, and archive.org files often have different names (e.g. the user's ابن القيم item's real file is the Arabic-titled PDF). download.py now: _working_url() tries guess → HEAD; on death (404/401/403) falls back to archive.org/metadata real filename → HEAD again; first 200 wins; none → err_no_pdf instead of a dead link. HEAD-only-200 policy + 1-byte Range-GET fallback for HEAD-hostile servers. LIVE tests on the user's own items: ابن القيم guess 404 → metadata link 200 ✅ recovered; addaa guess 200 ✅ returned as-is; nonexistent → "" ✅. ⏳ Awaiting user checkpoint: tap → link opens a real PDF (no more 404s).
- **Step 6 — code complete** (2026-11-01). New sources: sources/googlebooks.py (volumes API, only viewability=ALL_PAGES + pdf.downloadLink → genuine direct PDFs; preview/DRM/no-link volumes skipped), sources/gutenberg.py (gutendex; catalogued application/pdf else /ebooks/{id}.pdf.noimages fallback; author dates cleaned; resolve() alternates .pdf.images ↔ .pdf.noimages at tap). sources/base.py += default resolve() hook; InternetArchiveSource.resolve() now wraps the metadata lookup (real filename). download.py: _candidate_urls() loops REGISTRY for a per-source resolver — generic, no more IA special-case. search.py: _deliverable() filter — results without pdf_url/ia_id/gutenberg_id never reach the top-5 (kills most "😕 لا يوجد PDF" taps, user complaint). مكتبة نور investigated live from sandbox: search works (noor-book.com/?q=, div.book_results cards) BUT file downloads sit behind a login/human-verification wall (POST /Verification/check_user, CSRF, /verification/user_validation redirect) and content is user-uploaded (legally shakiest) → deferred by design; Arabic coverage stays on IA/OL/Google. Tests: google fixture 1/4 accepted, gutenberg fixture 2/3 + fallback + date cleaning, resolver alternation, REGISTRY 4 unique sources, deliverable filter, LIVE IA resolve+alive, LIVE gutendex 2 results, googleapis 429 from sandbox IP (works from user's PC). ⏳ Awaiting user checkpoint: EN/FR/AR searches show up to 4 sources; links verified.
- **Step 6b — dual links + natural-language search** (2026-11-01). User: «still the same issue … ig i should put direct link of pdf and direct link where he can find the pdf» + «he shouldnt enter the right name exactly … a gap of natural language so it can be smart little bit». New core/nl.py: clean_query() peels chat filler from BOTH edges in ar/en/fr («ابي كتاب…» / «I want the book…» / «je cherche le…» leads; «شكرا / please / merci / pdf» tails), ال-prefixed filler handled (السلام→سلام), never returns empty; search_variants() = relaxed retry ladder (top-3 → top-2 longest tokens). search.py: NL clean before search, per-source 15 s timeout (one blocked source can't stall the rest), ladder only fires on misses, results widened to top-6. internetarchive.py: exact-phrase title → AND-of-tokens (title_clause) — word order / extra words no longer kill the match (LIVE: «الداء والدواء ابن القيم» → 5 hits, first «كتاب الداء والدواء للمؤلف ابن القيم الجوزية»). googlebooks.py: intitle phrase → per-token intitle AND. download.py: success message now carries BOTH the verified direct PDF link AND the book's page link (picked_page); a tap whose links all fail sends the book's page link (err_no_pdf_page) — no more dead ends (plain err_no_pdf only when no page known). i18n 3×16 keys. Tests: clean_query 11/11 ar/en/fr, variants ladder, query builders, i18n parity, deliverable guard, LIVE user's exact case «ابي كتاب الداء والدواء لابن القيم» → 5 IA hits → first resolved to real Arabic-named PDF (200) + page link; step6 + step4fix regressions green. ⏳ Awaiting user checkpoint: conversational queries work; every tap answers with direct link and/or page link.
- **Step 6c — cross-language fallback (the real "Arabic is very limited" fix)** (2026-11-01). User diagnosis: «العادات الذرية» → «لم أجد شيئاً مجانياً» while "atomic habits" → 6 IA scans. Confirmed LIVE: IA Arabic title 0 hits vs English 5 — legal catalogs index books under their ORIGINAL (mostly English) title, so an Arabic edition title can never reach them. New core/translate.py: translate_text() with two keyless providers (MyMemory ~5000 free chars/day/IP → Google gtx endpoint), pure-function parsers, bounded 300-entry cache, quota-warning guard, every failure → "" (graceful); fallback_target(): ar/fr query → en, English query from AR user → ar, else skip. search.py: ladder extracted into testable run_search() — cleaned → variants → translate once → its top variant; results ranked against the ATTEMPT that won; a «🌐 بحثنا أيضاً عن: …» note (i18n via_translation) shows the user which wording produced the results. i18n 3×17 keys. Tests: parsers + quota guard, 6 fallback-direction cases, provider cache (1 call for 2 requests), FULL offline integration (AR miss → stubbed translate → 'atomic habits' → 2 ranked, 5 attempts), translation-unavailable degradation, i18n parity; LIVE IA gap documented, 429 → graceful ''. Regressions step6b/step4fix green. Note: MyMemory free tier is per-IP — plenty from the user's home PC; persistent quota-free MT can come in Step 7 if needed. ⏳ Awaiting user checkpoint: Arabic title of an English-catalogued book now finds the scans (e.g. «العادات الذرية» → Atomic Habits results + 🌐 note).
- **Step 6d — force-subscribe gate for @gifthubai** (2026-11-01). User: «subscribe in the channel t.me/gifthubai and verify the subscription then he can access and run the bot normally». New bot/handlers/subscribe.py: is_member() via getChatMember (member/admin/creator/restricted+is_member pass), join_keyboard() (URL button → https://t.me/gifthubai + «✅ Check» callback sub:check), check_and_cache() (process-lifetime membership cache in bot_data, one API call per user per run), ensure_subscribed() sends the trilingual join prompt. search.py: on_text gated — non-members get the prompt and their query is stored in bot_data[sub_pending]; new do_search() extracted (shared pipeline); on_sub_check re-verifies, edits the prompt to join_ok and RESUMES the pending search automatically (non-member tap → alert). start.py: join prompt attached under /start greeting when not subscribed. Fail-open policy: bot-not-admin-in-channel or transient Telegram errors → gate auto-disables with ONE loud log warning (bot never bricks); definitive PARTICIPANT_ID_INVALID/user-not-found → not a member. config.py/.env.example: CHANNEL_USERNAME/@gifthubai + CHANNEL_URL. main.py registers sub_check_handler. i18n 3×21 keys (join_channel, sub_join_btn, sub_check_btn, join_ok). Tests (offline, fake Telegram objects): keyboard structure, full status matrix, fail-open/fail-closed error policy, cache (1 call/2 checks), on_text gating + pending storage, sub:check resume + non-member alert, i18n parity; step6b/6c/6/step4fix regressions green. ⏳ Awaiting user checkpoint: SETUP — add @maktabati_downloader_bot as ADMIN in @gifthubai (else gate auto-disables), then: non-member search → prompt → join → ✅ → search resumes.
- **Step 6e — credits + referral economy** (2026-11-01). User: «give every user 5 free credits and 2 credits every day … top up his credits by sending their referral link … 1 credit for every invitation … if he runs out of credits the bot doesnt work until he send the referral link or wait 24h» — owner 8974969463 exempt. config.py: OWNER_ID, WELCOME_CREDITS=5, DAILY_REFILL=2, REFERRAL_BONUS=1, REFILL_PERIOD=24 h (all env-overridable). db: users += credits/last_refill/referred_by with an idempotent ALTER migration (existing users wake up with 5 credits + a fresh 24 h clock); repo: upsert_user now returns `created` (first-contact flag), add_credits (clamped ≥ 0, enrolls ghosts on the fly), refill_if_due (one atomic UPDATE per rolling 24 h), reward_referral (existing referrers only, no self-pay). New bot/credits.py: ref_link `t.me/<bot>?start=ref<uid>`, parse_ref, share_keyboard (t.me/share/url prefilled with the link + invite text), ensure_credits (owner pass → lazy refill → balance > 0 pass → out_of_credits message with the personal link + share button + ~hours to the next refill), charge_on_success, /credits command (balance + rules + link). search.do_search: credits gate BEFORE the searching message; 1 credit charged ONLY when results are found (misses are free — the NL/translation ladder looks like misses); 💳 balance line under the results header. start: referral deep-link processed on the invitee's FIRST /start even if they then hit the channel gate; referrer gets +1 and a notification in THEIR language; self-invites / repeat starts / ghost referrers never pay. subscribe.check_and_cache: owner bypass (the operator can always test their own bot). main.py registers /credits. i18n 3×28 keys (+ out_of_credits, credits_msg, credits_owner, share_btn, share_text, ref_bonus, balance_left; start/help now mention credits). Tests: legacy+fresh migration, welcome/no-reset/charge/clamp/enroll, refill window, referral rules, link parsing + share encoding, gate paths, owner exemption, do_search charge & free-miss & block-before-search, /start referral flow (once, referrer's language), owner sub-bypass, i18n parity + placeholders, compileall; regressions 6d/6c/6b/4fix/2 green (fixed test_step2's stale search_coming key). Design calls to confirm: 1 credit per successful search (not per attempt); referral bonus lands on the invitee's first /start (tightening later = require the invitee to pass the channel gate first). ⏳ Awaiting user checkpoint: /credits → 5; search → 4; drain to 0 → invite wall; a friend starts via your link → +1 + notification.
- **Step 6f — 🤍 Telegram Stars donations** (2026-11-01). User: «after giving the book pdf or the source … a small button of support the bot with a white heart when clicking it it shows donations with stars 25/50/75/100 ect». New bot/handlers/support.py: heart_keyboard() = one small 🤍 button (callback stars:menu) attached by download.py to BOTH delivered messages — the verified direct-PDF-link message and the source-page fallback (err_no_pdf_page/err_no_pdf); donate_keyboard() = one ⭐ button per config.STAR_TIERS entry (25/50/75/100/250, env-overridable STAR_TIERS), two per row + ✖️ close (stars:close → delete menu). A tier tap sends a Telegram Stars invoice — currency "XTR", provider_token stays empty (Stars need no payment provider; Telegram renders the in-chat sheet), payload donation:<n> with a whitelist guard (out-of-list/garbage tiers answered with an alert, never invoiced). PreCheckoutQueryHandler auto-approves; MessageHandler(filters.SUCCESSFUL_PAYMENT) logs the payment into a new donations table (user_id, amount, payload, created_at — ready for /stats) and replies with a trilingual thank-you naming the amount. Invoice failure → donate_err fallback message. main.py registers stars_handler + precheckout_handler + payment_handler. i18n 3×35 keys (+ support_heart 🤍, close_btn ✖️, donate_menu, donate_title, donate_desc {n}, donate_thanks {name}{n}, donate_err). Tests: keyboard shapes, menu open/close, XTR invoice fields + tier whitelist, pre-checkout approval, payment thanks + DB row, download.py 🤍 on both delivery paths, i18n parity, compileall; regressions 6e/6d/6b/6c/4fix/2 green. Note: Stars pay out automatically into the bot's Telegram balance (visible in @BotFather → Payments / withdrawable via Fragment); the sandbox cannot test the real payment sheet — that needs a real user paying. ⏳ Awaiting user checkpoint: open a delivered book message → 🤍 → tier menu → pay a small amount → thank-you arrives.
- Step 7 next: public hardening — rate limits per user, friendly trilingual errors everywhere, logging review, /stats /ban /about, download/throttle queue.
