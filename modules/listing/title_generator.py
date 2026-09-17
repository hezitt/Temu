def generate_title(title_base: str, theme: str) -> str:
    base = " ".join(title_base.split())
    clean_theme = " ".join(theme.split())
    suffix = "Paint by Numbers Kit"
    parts = [base]
    if clean_theme.lower() not in base.lower():
        parts.append(clean_theme)
    if suffix.lower() not in base.lower():
        parts.append(suffix)
    return " - ".join(parts)
