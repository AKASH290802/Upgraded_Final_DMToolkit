"""
Projects: one customer's Salesforce org connections grouped together.

    Valmont = ValmontDev + ValmontQA + ValmontUAT   (+ alias folder names, e.g. Valmont_Industries,
                                                       the name Salesforce reports for the org)

The sidebar org decides the project; the File Library shows that project's files by default.
Projects live in Services/projects.json (not in linkedservices.json — no credentials here).
Grouping is never guessed: suggest_projects() only proposes groups, the user confirms them in
Configuration > Projects, and files whose org cannot be placed stay "unassigned".
"""
import json
import os
import re
from typing import Dict, List, Optional

PROJECTS_ENV = 'DM_TOOLKIT_PROJECTS'   # another file, for tests
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SCOPE_PROJECT = "📁 This project"
SCOPE_ORG = "🏢 This org"
SCOPE_ALL = "🌐 All files"
UNASSIGNED = {'', 'unknown', 'unknown_org', 'none'}

# Environment suffixes stripped when suggesting a project name (ValmontQA -> Valmont, DTNA_UAT -> DTNA).
_ENV_SUFFIX = re.compile(r'[_\- ]?(dev|qa|uat|sit|test|stage|staging|prod|preprod|full|partial|sandbox)\d*$', re.I)


def projects_path() -> str:
    return os.environ.get(PROJECTS_ENV) or os.path.join(_APP_ROOT, 'Services', 'projects.json')


def load_projects() -> List[Dict]:
    """[{'name', 'orgs': [...], 'aliases': [...]}, ...] ([] when none are defined)."""
    try:
        with open(projects_path(), encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    return [{'name': p['name'], 'orgs': list(p.get('orgs') or []), 'aliases': list(p.get('aliases') or [])}
            for p in (data.get('projects') or []) if p.get('name')]


def save_projects(items: List[Dict]) -> None:
    path = projects_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'projects': items}, f, indent=2)


def project_for_org(org: Optional[str]) -> Optional[Dict]:
    """The project an org connection, alias folder name or the project's own name belongs to, or None."""
    if not org:
        return None
    for project in load_projects():
        if org in project['orgs'] or org in project['aliases'] or org == project['name']:
            return project
    return None


def project_labels(project: Dict) -> List[str]:
    """Every org name a project's files can be filed under: its orgs, its aliases, and the
    project's own name (files uploaded for the whole project, file_store/source/<project>/)."""
    return list(project['orgs']) + list(project['aliases']) + [project['name']]


WHOLE_PROJECT = '__whole_project__'   # upload target: the project's own folder


def suggest_projects(org_names) -> Dict[str, List[str]]:
    """{suggested name: [orgs]} for orgs that share a name once the environment suffix is removed.

    Only groups of two or more orgs, and only orgs not yet in a project. These are
    suggestions shown with a 'Create' button; nothing is assigned without the user.
    """
    assigned = {o for p in load_projects() for o in project_labels(p)}
    groups: Dict[str, List[str]] = {}
    for org in org_names:
        if org in assigned:
            continue
        base = _ENV_SUFFIX.sub('', org).rstrip('_- ')
        if base and base != org:
            groups.setdefault(base, []).append(org)
    return {name: sorted(orgs) for name, orgs in sorted(groups.items()) if len(orgs) >= 2}


# Where each kind of file keeps its org in the folder path (relative to the app folder).
_VALIDATION_TYPES = {'enhanced_validation', 'genai_validation', 'schema_validation', 'formula_extraction',
                     'customrules', 'custom_validation'}
_TOP_FOLDERS = {'validation', 'datafiles', 'mapping_logs', 'dataloader_logs', 'unit testing generates',
                'file_store', 'genai_validation_results'}
_NOT_AN_ORG = {'migration_readiness'}


def org_from_path(path: str) -> Optional[str]:
    """The org a stored file belongs to, read from its folder (None when the path does not say).

    Works for paths under an old install folder too: the known top folder (Validation,
    DataFiles, file_store, ...) is found anywhere in the path.
    """
    parts = re.split(r'[\\/]+', str(path or ''))
    start = next((i for i, p in enumerate(parts) if p.lower() in _TOP_FOLDERS), None)
    if start is None:
        return None
    top, rest = parts[start].lower(), parts[start + 1:-1]   # folders after the top one (not the file)
    org = None
    if top == 'validation' and rest:
        org = rest[1] if rest[0].lower() in _VALIDATION_TYPES and len(rest) > 1 else (
            None if rest[0].lower() in _VALIDATION_TYPES else rest[0])
    elif top in ('datafiles', 'mapping_logs', 'unit testing generates') and rest:
        org = rest[0]
    elif top == 'file_store' and len(rest) > 1 and rest[0].lower() in ('source', 'output'):
        org = rest[1]
    elif top == 'dataloader_logs' and len(rest) > 1 and rest[1].lower().startswith('dataload_'):
        org = rest[1][len('dataload_'):]
    if not org or org.lower() in UNASSIGNED or org.lower() in _NOT_AN_ORG:
        return None
    return org
