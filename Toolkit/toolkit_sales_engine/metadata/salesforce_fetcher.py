"""
Salesforce Metadata Fetcher
Accepts an already-connected simple_salesforce.Salesforce instance
so DM-Toolkit's existing SF connection is reused.
"""
import logging
from typing import Optional

from .models import FieldMeta, ObjectMeta, DataType, SF_TYPE_MAP

logger = logging.getLogger(__name__)


class SalesforceMetadataFetcher:
    def __init__(self, sf_conn=None):
        """
        Args:
            sf_conn : An already-authenticated simple_salesforce.Salesforce object.
                      If None, call connect(username, password, token, domain) first.
        """
        self._sf = sf_conn

    def connect(self, username: str, password: str, security_token: str, domain: str = "login") -> None:
        from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
        try:
            self._sf = Salesforce(
                username=username,
                password=password,
                security_token=security_token,
                domain=domain,
            )
            logger.info("Connected to Salesforce as %s", username)
        except SalesforceAuthenticationFailed as exc:
            raise ConnectionError(f"Salesforce authentication failed: {exc}") from exc

    def fetch_object(self, object_name: str) -> ObjectMeta:
        if not self._sf:
            raise RuntimeError("Not connected to Salesforce. Pass sf_conn or call connect().")
        describe = getattr(self._sf, object_name).describe()
        setup_descriptions = self._fetch_setup_descriptions(object_name)
        fields = []
        for f in describe.get("fields", []):
            sf_type = f.get("type", "string").lower()
            data_type = SF_TYPE_MAP.get(sf_type, DataType.STRING)
            picklist_values = []
            if data_type == DataType.PICKLIST:
                picklist_values = [
                    pv["value"]
                    for pv in f.get("picklistValues", [])
                    if pv.get("active", True)
                ]
            required = not f.get("nillable", True) and not f.get("defaultedOnCreate", False)
            # Combine both text sources Salesforce keeps for a field: the Setup-only
            # "Description" (admin notes, only available via the Tooling API) and the
            # end-user-facing "Help Text" (inlineHelpText, returned by describe()).
            # Both feed the embedding/LLM matching context, so richer text here means
            # better semantic field mapping in Upload & Map.
            help_text = f.get("inlineHelpText") or ""
            setup_description = setup_descriptions.get(f["name"], "")
            description = " | ".join(p for p in (setup_description, help_text) if p) or f.get("label", "")
            reference_to = f.get("referenceTo") or [] if data_type == DataType.REFERENCE else []
            fields.append(FieldMeta(
                object_name=object_name,
                field_name=f["name"],
                label=f.get("label", f["name"]),
                description=description,
                data_type=data_type,
                required=required,
                max_length=f.get("length") or None,
                picklist_values=picklist_values,
                synonyms=[],
                example_values=[],
                reference_to=reference_to,
            ))
        label = describe.get("label", object_name)
        logger.info("Fetched %d fields for %s (%d with a Setup description)",
                     len(fields), object_name, len(setup_descriptions))
        return ObjectMeta(object_name=object_name, label=label, fields=fields)

    def _fetch_setup_descriptions(self, object_name: str) -> dict[str, str]:
        """
        Best-effort fetch of each field's Setup-level "Description" (admin notes set in
        Object Manager) via the Tooling API's FieldDefinition object — describe() only
        exposes inlineHelpText, not this. Returns {} on any failure (e.g. the connected
        user lacks Tooling API access) so a schema sync never fails just because this
        optional enrichment couldn't complete.
        """
        try:
            soql = (
                "SELECT QualifiedApiName, Description FROM FieldDefinition "
                f"WHERE EntityDefinition.QualifiedApiName = '{object_name}'"
            )
            result = self._sf.toolingexecute("query/", params={"q": soql})
            records = result.get("records", []) if isinstance(result, dict) else []
            return {
                r["QualifiedApiName"]: r["Description"]
                for r in records
                if r.get("Description")
            }
        except Exception as exc:
            logger.warning("Could not fetch Setup field descriptions via Tooling API for %s: %s",
                            object_name, exc)
            return {}
