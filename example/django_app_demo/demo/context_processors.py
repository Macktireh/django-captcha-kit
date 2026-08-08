from .links import CAPTCHA_KIT_VERSION, PROJECT_LINKS, REPOSITORY


def project(request) -> dict:
    return {
        "project_links": PROJECT_LINKS,
        "repository_url": REPOSITORY,
        "captcha_kit_version": CAPTCHA_KIT_VERSION,
    }
