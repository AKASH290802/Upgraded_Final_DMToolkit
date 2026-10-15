"""
Dependency Planner — checks whether the user's chosen priority order for
selected objects respects Salesforce lookup/master-detail relationships.
"""
import logging

logger = logging.getLogger(__name__)


def get_reference_map(sf_conn, object_names: list[str]) -> dict[str, set[str]]:
    """
    Returns {object_name: {other_selected_object_names it references via a
    lookup/master-detail field}}.
    """
    ref_map: dict[str, set[str]] = {name: set() for name in object_names}
    selected = set(object_names)
    for obj_name in object_names:
        try:
            describe = getattr(sf_conn, obj_name).describe()
        except Exception as exc:
            logger.warning("Could not describe %s for dependency check: %s", obj_name, exc)
            continue
        for f in describe.get("fields", []):
            if f.get("type") == "reference":
                for ref_obj in f.get("referenceTo", []):
                    if ref_obj in selected and ref_obj != obj_name:
                        ref_map[obj_name].add(ref_obj)
    return ref_map


def validate_priority(sf_conn, ordered_objects: list[str]) -> list[str]:
    """
    Returns human-readable warnings for any object placed before an object
    it depends on (references via lookup/master-detail). Advisory only —
    the user's chosen order is never overridden automatically.
    """
    if not ordered_objects:
        return []
    warnings: list[str] = []
    ref_map = get_reference_map(sf_conn, ordered_objects)
    position = {name: idx for idx, name in enumerate(ordered_objects)}

    for obj_name, parents in ref_map.items():
        for parent in parents:
            if position[obj_name] < position[parent]:
                warnings.append(
                    f"⚠️ '{obj_name}' references '{parent}' but is prioritized before it. "
                    f"Recommended: validate/load '{parent}' first."
                )
    return warnings
