def cprint(text, *args, **kwargs):
    """Simple fallback for termcolor.cprint when termcolor isn't installed."""
    print(text)


def colored(text, *args, **kwargs):
    """Simple fallback for termcolor.colored when termcolor isn't installed."""
    return text
