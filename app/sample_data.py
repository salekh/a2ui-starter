"""Realistic demo instances of every widget, populated with Google-Cloud-flavoured data."""

from __future__ import annotations

from .widgets import (
    Action,
    ActionButtons,
    Callout,
    Card,
    CitationSource,
    Column,
    DataTable,
    KeyValueList,
    MetricTile,
    RichText,
    Source,
    Step,
    TagChip,
    Timeline,
    Widget,
)


def sample_rich_text() -> RichText:
    return RichText(
        id="intro",
        accessibility_label="Introduction",
        text=(
            "**A2UI on Gemini Enterprise** lets an ADK agent describe rich UI "
            "in a declarative, catalog-safe JSON format instead of shipping "
            "walls of text.\n\n"
            "This starter renders 10 composed widgets against the Basic "
            "Catalog primitives (Text / Row / Column / Card / List / Button / "
            "Icon / Divider), pinned to v0.8 for GE compatibility."
        ),
    )


def sample_data_table() -> DataTable:
    return DataTable(
        id="engagements",
        accessibility_label="Active customer engagements",
        title="Active customer engagements",
        columns=[
            Column(key="account", header="Account"),
            Column(key="region", header="Region"),
            Column(key="stage", header="Stage"),
            Column(key="arr", header="ARR (EUR)", align="right"),
            Column(key="next_step", header="Next step"),
        ],
        rows=[
            {
                "account": "Deutsche Telekom",
                "region": "EMEA / DE",
                "stage": "Design",
                "arr": 2_400_000,
                "next_step": "GE agent deploy review",
            },
            {
                "account": "Nemetschek SE",
                "region": "EMEA / DE",
                "stage": "PoC",
                "arr": 480_000,
                "next_step": "A2UI widget demo",
            },
            {
                "account": "SoundCloud",
                "region": "EMEA / DE",
                "stage": "Production",
                "arr": 1_100_000,
                "next_step": "Cloud Run autoscale review",
            },
        ],
    )


def sample_tag_chip() -> TagChip:
    return TagChip(
        id="stack_chip",
        accessibility_label="Tech stack tag",
        label="ADK + A2UI + Cloud Run",
        variant="suggestion",
        intent="info",
        icon="check",
    )


def sample_card() -> Card:
    return Card(
        id="pitch_card",
        accessibility_label="A2UI pitch card",
        title="Speak UI, not text",
        subtitle="A2UI in one sentence",
        body=(
            "Ship declarative JSON that any A2UI-compliant renderer — "
            "including Gemini Enterprise's built-in one — will render "
            "safely as native widgets."
        ),
    )


def sample_key_value_list() -> KeyValueList:
    return KeyValueList(
        id="deploy_kv",
        accessibility_label="Deployment metadata",
        items=[
            ("Project", "sanchit-a2ui-demo"),
            ("Region", "europe-west1"),
            ("Model", "gemini-flash-latest"),
            ("A2UI version", "v0.8 (GE-compatible)"),
            ("Runtime", "Agent Engine (managed)"),
        ],
    )


def sample_citation_source() -> CitationSource:
    return CitationSource(
        id="sources",
        accessibility_label="Sources",
        title="Sources",
        sources=[
            Source(
                title="A2UI protocol specification",
                url="https://a2ui.org",
                domain="a2ui.org",
                snippet=(
                    "A2UI is an open standard that lets agents send "
                    "declarative JSON describing UI intent; clients render "
                    "using their own component catalog."
                ),
                favicon_url="https://a2ui.org/favicon.ico",
            ),
            Source(
                title="Building A2UI agents on Gemini Enterprise",
                url="https://cloud.google.com/blog/products/ai-machine-learning/a2ui-gemini-enterprise",
                domain="cloud.google.com",
                snippet=(
                    "Gemini Enterprise ships with a built-in A2UI renderer "
                    "pinned to v0.8; agents on Cloud Run or Agent Engine "
                    "can emit widgets natively."
                ),
                favicon_url="https://www.gstatic.com/devrel-devsite/prod/v0e0f589edd85502a40aa4e4d5c34d34d1a4c47a3b4d7b8a4b4a1d1a1a1a1a1a1/cloud/images/favicons/onecloud/favicon.ico",
            ),
            Source(
                title="Agent Development Kit — a2ui integration",
                url="https://adk.dev/integrations/a2ui/",
                domain="adk.dev",
                snippet=(
                    "The a2ui-agent-sdk package adds A2UI-specific tooling on "
                    "top of google-adk: prompt injection, catalog validation, "
                    "and a first-class SendA2uiToClientToolset."
                ),
            ),
        ],
    )


def sample_timeline() -> Timeline:
    return Timeline(
        id="delivery_timeline",
        accessibility_label="Delivery milestones",
        steps=[
            Step(
                title="M0 — repo skeleton",
                timestamp="2026-07-01",
                state="done",
                description="hatchling pyproject, widget base, empty tests.",
            ),
            Step(
                title="M1 — 10 widgets",
                timestamp="2026-07-03",
                state="done",
                description="Composed rich widgets on top of basic catalog.",
            ),
            Step(
                title="M2 — preview harness",
                timestamp="2026-07-08",
                state="active",
                description="FastAPI + Google-brand HTML renderer.",
            ),
            Step(
                title="M3 — GE deploy",
                timestamp="2026-07-15",
                state="pending",
                description="Register agent on Agent Engine and verify in GE.",
            ),
            Step(
                title="M4 — customer-ready",
                timestamp="2026-07-22",
                state="pending",
                description="Deutsche Telekom pilot handoff.",
            ),
        ],
    )


def sample_metric_tiles() -> list[MetricTile]:
    return [
        MetricTile(
            id="latency_p50",
            accessibility_label="p50 latency",
            label="Latency p50",
            value="284 ms",
            delta="-12 ms wow",
            delta_direction="down",
        ),
        MetricTile(
            id="latency_p99",
            accessibility_label="p99 latency",
            label="Latency p99",
            value="940 ms",
            delta="+48 ms wow",
            delta_direction="up",
        ),
        MetricTile(
            id="slo_error",
            accessibility_label="SLO error rate",
            label="SLO error rate",
            value="0.03%",
            delta="-0.01% wow",
            delta_direction="down",
        ),
        MetricTile(
            id="monthly_cost",
            accessibility_label="Monthly cost",
            label="Monthly cost",
            value="$1,240",
            delta="+$60 wow",
            delta_direction="up",
        ),
    ]


def sample_callouts() -> list[Callout]:
    return [
        Callout(
            id="callout_info",
            accessibility_label="Version info",
            title="Pinned to A2UI v0.8",
            body=(
                "Gemini Enterprise's built-in renderer targets v0.8. Bump the "
                "catalogId when GE catches up to v0.9 / v1.0."
            ),
            variant="info",
        ),
        Callout(
            id="callout_warning",
            accessibility_label="Yellow contrast warning",
            title="Yellow #FBBC04 needs dark text",
            body=(
                "Google Yellow on white fails WCAG 4.5:1. Use only as a "
                "container background with #202124 foreground."
            ),
            variant="warning",
        ),
        Callout(
            id="callout_success",
            accessibility_label="Cloud Run deploy success",
            title="Cloud Run deploy succeeded",
            body="a2ui-demo revision 00007 is now serving 100% of traffic.",
            variant="success",
        ),
    ]


def sample_action_buttons() -> ActionButtons:
    return ActionButtons(
        id="cta",
        accessibility_label="Primary actions",
        actions=[
            Action(
                label="Open in Composer",
                event_name="open_composer",
                variant="primary",
                context={"surface": "engagements"},
            ),
            Action(
                label="Download JSON",
                event_name="download_json",
                variant="secondary",
                context={"filename": "a2ui-stream.json"},
            ),
            Action(
                label="Dismiss",
                event_name="dismiss",
                variant="tertiary",
                context={},
            ),
        ],
    )


def build_all_widgets() -> list[Widget]:
    widgets: list[Widget] = [
        sample_rich_text(),
        sample_data_table(),
        sample_tag_chip(),
        sample_card(),
        sample_key_value_list(),
        sample_citation_source(),
        sample_timeline(),
    ]
    widgets.extend(sample_metric_tiles())
    widgets.extend(sample_callouts())
    widgets.append(sample_action_buttons())
    return widgets


WIDGETS_BY_NAME: dict[str, Widget] = {
    "rich_text": sample_rich_text(),
    "data_table": sample_data_table(),
    "tag_chip": sample_tag_chip(),
    "card": sample_card(),
    "key_value_list": sample_key_value_list(),
    "citation": sample_citation_source(),
    "timeline": sample_timeline(),
    "metric_latency_p50": sample_metric_tiles()[0],
    "metric_latency_p99": sample_metric_tiles()[1],
    "metric_slo_error": sample_metric_tiles()[2],
    "metric_monthly_cost": sample_metric_tiles()[3],
    "callout_info": sample_callouts()[0],
    "callout_warning": sample_callouts()[1],
    "callout_success": sample_callouts()[2],
    "action_buttons": sample_action_buttons(),
}
