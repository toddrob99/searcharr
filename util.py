import yaml
import settings

log = None
lang = None
lang_default = None


def load_language(lang_ietf=None):
    global lang
    global lang_default
    if not lang_ietf:
        if not hasattr(settings, "searcharr_language"):
            log.warning(
                "No language defined! Defaulting to en-us. Please add searcharr_language to settings.py if you want another language, where the value is a filename (without .yml) in the lang folder."
            )
            settings.searcharr_language = "en-us"
        lang_ietf = settings.searcharr_language
    log.debug(f"Attempting to load language file: lang/{lang_ietf}.yml...")
    try:
        with open(f"lang/{lang_ietf}.yml", mode="r", encoding="utf-8") as y:
            lang = yaml.load(y, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        log.error(
            f"Error loading lang/{lang_ietf}.yml. Confirm searcharr_language in settings.py has a corresponding yml file in the lang subdirectory. Using default (English) language file."
        )
        with open("lang/en-us.yml", "r") as y:
            lang = yaml.load(y, Loader=yaml.SafeLoader)

    if lang.get("language_ietf") != "en-us":
        lang_default = load_language("en-us")

def xlate(key, **kwargs):
        if t := lang.get(key):
            return t.format(**kwargs)
        else:
            log.error(f"No translation found for key [{key}]!")
            if lang.get("language_ietf") != "en-us":
                if t := lang_default.get(key):
                    log.info(f"Using default language for key [{key}]...")
                    return t.format(**kwargs)
        return "(translation not found)"

def xlate_aliases(message, aliases, arg = None):
    t = xlate(
        message,
        commands = " OR ".join(
            [
                f"`/{c}{("" if arg == None else " <" + xlate(arg) + ">")}`"
                for c in aliases
            ]
        ),
    )
    return t

def strip_entities(message):
    text = message.text
    entities = message.parse_entities()
    log.debug(f"{entities=}")
    for v in entities.values():
        text = text.replace(v, "")
    text = text.replace("  ", "").strip()
    log.debug(f"Stripped entities from message [{message.text}]: [{text}]")
    return text