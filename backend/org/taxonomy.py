from .models import Skill
from .taxonomy_data import skill_slug


def resolve_skill(term: str) -> Skill | None:
    """Map a name, slug or synonym ("JS", "k8s", "ReactJS") to a canonical skill."""
    term = (term or "").strip()
    if not term:
        return None
    direct = (
        Skill.objects.filter(slug=skill_slug(term)).first() or Skill.objects.filter(name__iexact=term).first()
    )
    if direct:
        return direct
    lowered = term.lower()
    for skill in Skill.objects.only("id", "name", "slug", "synonyms"):
        if any(lowered == str(s).strip().lower() for s in skill.synonyms or []):
            return skill
    return None
