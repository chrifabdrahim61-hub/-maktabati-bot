"""Natural-language query handling (Step 6b).

User request: «he shouldnt enter the right name exactly … i want to make a
gap of natural language so it can be smart little bit».

People don't type library-catalog titles into a chat. They type:

    ابي كتاب الداء والدواء شكرا
    أريد كتاب فن الحرب من فضلك
    I want the book art of war please
    find me 1984 pdf
    je cherche le livre l'étranger merci

clean_query() peels that conversational wrapping off the EDGES of the message
(lead fillers like «ابي كتاب» / «i want the book» / «je cherche le», tail
fillers like «شكرا» / «please» / «merci» / «pdf») and returns the bare title
tokens. Everything is applied AFTER normalize_query() so the lists below are
normalized forms (أ→ا, ة→ه, punctuation dropped, lowercase).

search_variants() builds the relaxed retry ladder: if the full title finds
nothing anywhere, retry with only the longest 3 tokens, then the longest 2 —
function words are short, content words are long, so "longest" ≈ most
meaningful. This is what makes «مختصر الداء والدواء لابن القيم» still land
when no catalog contains all four words in one title.
"""
from utils.text import normalize_query

# ── tokens dropped from the START of the message ────────────────────────────
_LEAD = {
    # Arabic — greetings
    "سلام", "عليكم", "مرحبا", "مرحبتين", "اهلا", "اهلاين", "هاي", "هلا",
    # Arabic — want/need/give-me
    "ابي", "ابغى", "ابغا", "ابغي", "اريد", "ارغب", "احتاج", "بغيت", "نبي",
    "نبغي", "بدي", "ودي", "اعطني", "عطني", "اعطيني", "عطيني", "هات", "هاتلي",
    "جيب", "جيبلي", "ممكن", "لو", "سمحت", "من", "فضلك", "رجاء", "لي", "انا",
    "يا", "ابحث", "اقرا", "نقرا", "بقرا", "افضل",
    # Arabic — generic nouns that prefix a title in chat-speak
    "كتاب", "كتب", "رواية", "روايه", "قصة", "قصه", "ملف", "نسخه", "نسخة",
    "عن", "بخصوص", "عندك", "عندكم", "عند",
    # English
    "hi", "hello", "hey", "yo", "please", "pls", "plz", "can", "could",
    "would", "you", "u", "i", "im", "m", "want", "wants", "need", "like",
    "to", "read", "looking", "look", "for", "find", "give", "get", "me",
    "send", "search", "the", "a", "an", "of", "book", "books", "about",
    "download", "free", "pdf", "version", "copy", "any", "some", "and",
    # French
    "bonjour", "bonsoir", "salut", "coucou", "svp", "stp", "s", "il", "te",
    "vous", "plait", "plaît", "je", "veux", "voudrais", "aimerais", "j",
    "cherche", "cherches", "trouve", "trouves", "moi", "donne", "donnes",
    "le", "la", "les", "un", "une", "du", "de", "des", "livre", "livres",
    "oeuvre", "pour", "a", "au", "aux", "telecharger", "télécharger", "pdf",
}

# ── tokens dropped from the END of the message ──────────────────────────────
_TAIL = {
    # Arabic
    "شكرا", "جزاك", "الله", "خير", "بارك", "فيك", "جدا", "من", "فضلك", "لو",
    "سمحت", "ملف", "نسخه", "نسخة", "كتاب", "كتب", "pdf", "لي", "كامل",
    "كامله", "كاملة", "مجانا", "مجاني", "مجانيه", "بالعربي", "بالعربيه",
    "بالفرنسيه", "بالانجليزيه", "يا",
    # English
    "pdf", "please", "pls", "plz", "thanks", "thank", "you", "book", "books",
    "free", "download", "version", "copy", "full", "complete", "me", "in",
    "arabic", "english", "french", "language", "and",
    # French
    "pdf", "merci", "stp", "svp", "livre", "livres", "complet", "complete",
    "gratuit", "gratuitement", "version", "moi",
}

# lone connector letters that only make sense attached to the next word
# (Arabic و/ف/ل/ب/ك prefixes, French elisions like «l'étranger» → «l étranger»)
_DANGLING_LEAD = {"a", "i", "l", "d", "j", "n", "s", "c", "m", "u",
                  "و", "ف", "ل", "ب", "ك"}


def _is_lead(tok: str) -> bool:
    """Lead-filler test; also matches the «ال»-prefixed form of any lead
    filler («السلام» → «سلام», «الكتاب» → «كتاب»), since Arabic speakers
    naturally type the article on greetings/chat nouns but never inside
    real titles that start with those words."""
    if tok in _LEAD or tok in _DANGLING_LEAD:
        return True
    return tok.startswith("ال") and len(tok) > 3 and tok[2:] in _LEAD


def clean_query(raw: str) -> str:
    """Strip chat filler from both edges; return a bare-title query.

    Never returns '' while the raw text has content — if everything was
    filler («hello», «شكرا»), the normalized raw text comes back so the
    normal search pipeline still runs.
    """
    q = normalize_query(raw or "")
    if not q:
        return ""
    tokens = q.split()
    while tokens and _is_lead(tokens[0]):
        tokens.pop(0)
    while tokens and tokens[-1] in _TAIL:
        tokens.pop()
    return " ".join(tokens) or q


def search_variants(query: str) -> list[str]:
    """Relaxed keyword variants for the retry ladder (best candidate first).

    «الداء والدواء لابن القيم» → ['الداء والدواء القيم', 'الداء والدواء']
    (longest tokens kept, original order preserved). Short queries get no
    variants — there is nothing left to relax.
    """
    tokens = query.split()
    unique = list(dict.fromkeys(tokens))  # de-dupe, keep order
    variants: list[str] = []
    for keep in (3, 2):
        if len(unique) <= keep:
            continue
        top = sorted(unique, key=len, reverse=True)[:keep]
        top_set = set(top)
        variant = " ".join(t for t in unique if t in top_set)
        if variant and variant != query and variant not in variants:
            variants.append(variant)
    return variants
