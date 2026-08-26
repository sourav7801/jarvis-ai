"""Evidence-first venture research and long-horizon execution programs.

This module creates research questions and work orders; it never pretends that
an unanswered question is a verified result.  It is deliberately deterministic
so every Company OS project receives the same auditable research standard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass(frozen=True)
class ResearchTrack:
    id: str
    owner: str
    title: str
    questions: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    deliverable: str
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BASE_TRACKS: tuple[ResearchTrack, ...] = (
    ResearchTrack(
        "R01", "research", "Problem and customer evidence",
        (
            "Who experiences the problem, how often, and what is the measurable cost of the status quo?",
            "Which current substitutes are used and why do users switch or refuse to switch?",
            "What observable behavior would demonstrate willingness to pay rather than stated interest?",
        ),
        ("customer interviews", "workflow observation", "industry datasets", "support/review evidence"),
        "Segmented problem evidence matrix with citations, interview evidence, uncertainty and disconfirming findings.",
    ),
    ResearchTrack(
        "R02", "research", "Market, competitor and substitute map",
        (
            "Which direct, indirect, DIY and non-consumption alternatives compete for the same outcome?",
            "How large is the reachable beachhead from bottom-up units, not an unsupported headline TAM?",
            "Where are distribution, trust, cost or performance gaps demonstrably underserved?",
        ),
        ("company filings", "product documentation", "pricing pages", "industry associations", "public datasets"),
        "Citable competitor matrix, bottom-up market model and whitespace hypotheses.",
    ),
    ResearchTrack(
        "R03", "engineering", "Technical and scientific feasibility",
        (
            "What physical, software, data or scientific constraints determine whether the concept can work?",
            "Which components are proven, emerging or still speculative?",
            "What is the cheapest prototype that can falsify the highest-risk technical assumption?",
        ),
        ("peer-reviewed papers", "standards", "reference implementations", "bench tests", "expert review"),
        "Feasibility architecture, assumption tree, prototype sequence and measurable pass/fail tests.",
    ),
    ResearchTrack(
        "R04", "legal", "Patents, IP, regulation and permissions",
        (
            "Which jurisdictions, licenses, standards, codes, certifications and professional reviews apply?",
            "Which public patents or prior art constrain freedom to operate?",
            "Which claims, data, safety or consumer obligations change the product design?",
        ),
        ("regulator portals", "standards bodies", "patent databases", "statutes", "qualified professional review"),
        "Issue-spotting and prior-art register with jurisdiction, source, owner and required professional review.",
        True,
    ),
    ResearchTrack(
        "R05", "operations", "Supply chain, production and service operations",
        (
            "Which materials, vendors, skills, lead times, quality controls and bottlenecks determine delivery?",
            "What must be made, bought, partnered, insured, inspected or maintained?",
            "What unit-level failure modes could harm customers, staff, assets or the environment?",
        ),
        ("supplier specifications", "manufacturing quotes", "quality standards", "failure reports", "pilot operations"),
        "Make/buy/partner map, pilot SOP, capacity model, quality plan and failure-mode register.",
    ),
    ResearchTrack(
        "R06", "finance", "Economics, capital and downside",
        (
            "What drives price, variable cost, fixed cost, working capital, acquisition cost and retention?",
            "What capital is needed at prototype, pilot, repeatability and scale stages?",
            "Which downside scenarios break liquidity, margin, safety or delivery commitments?",
        ),
        ("supplier quotes", "comparable economics", "pilot measurements", "channel costs", "scenario models"),
        "Bottom-up unit economics, cash/runway scenarios, funding milestones and stop/continue thresholds.",
    ),
    ResearchTrack(
        "R07", "quality", "Safety, climate, ethics and misuse",
        (
            "What hazards, externalities, accessibility failures, misuse and unintended consequences are plausible?",
            "How will claims, tests, incidents and corrective actions be recorded?",
            "Which risks must be eliminated rather than accepted or transferred?",
        ),
        ("hazard analyses", "incident databases", "lifecycle evidence", "accessibility standards", "independent review"),
        "Risk register, safety case outline, lifecycle impact questions and independent verification plan.",
    ),
    ResearchTrack(
        "R08", "marketing", "Positioning, distribution and trust",
        (
            "Which audience has both urgency and an economical path to reach?",
            "What proof is required before a responsible customer believes the promise?",
            "Which channel experiments measure demand without fabricating traction or overclaiming?",
        ),
        ("channel experiments", "search demand", "communities", "partner interviews", "conversion evidence"),
        "Positioning alternatives, trust assets, channel experiment backlog and measurement plan.",
    ),
)


PHYSICAL_MARKERS = frozenset(
    {
        "building", "construction", "device", "factory", "hardware", "home", "house",
        "machine", "manufacture", "material", "mobility", "movable", "robot", "vehicle",
    }
)


def _tokens(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def build_venture_research_program(idea: str) -> dict[str, Any]:
    clean = re.sub(r"\s+", " ", str(idea or "")).strip()
    tokens = _tokens(clean)
    physical = bool(tokens.intersection(PHYSICAL_MARKERS))
    tracks = [track.to_dict() for track in BASE_TRACKS]

    hypotheses = [
        {
            "id": "H01", "owner": "research", "status": "UNTESTED",
            "statement": "A specific reachable customer experiences this problem frequently and urgently.",
            "evidence_required": "Observed workflow evidence plus repeated interviews from a defined segment.",
            "falsification": "Target users rarely experience the problem or do not change behavior when offered a credible alternative.",
        },
        {
            "id": "H02", "owner": "engineering", "status": "UNTESTED",
            "statement": "The core outcome can be delivered safely with available or developable technology.",
            "evidence_required": "Prototype measurements against explicit performance and safety thresholds.",
            "falsification": "A critical constraint cannot meet the threshold within the capital/time boundary.",
        },
        {
            "id": "H03", "owner": "finance", "status": "UNTESTED",
            "statement": "A repeatable delivery model can produce sustainable unit economics.",
            "evidence_required": "Quoted costs, measured delivery effort, observed conversion/retention and scenario-tested cash needs.",
            "falsification": "Responsible delivery cost remains above demonstrated willingness to pay at plausible scale.",
        },
        {
            "id": "H04", "owner": "legal", "status": "UNTESTED",
            "statement": "Regulatory, IP, safety and operating constraints can be satisfied without destroying the value proposition.",
            "evidence_required": "Jurisdiction map, prior-art review, required standards and qualified professional review.",
            "falsification": "A mandatory constraint prevents the intended use or makes responsible delivery nonviable.",
        },
    ]
    if physical:
        hypotheses.append(
            {
                "id": "H05", "owner": "operations", "status": "UNTESTED",
                "statement": "A physical prototype can be manufactured, transported, installed, inspected and maintained repeatably.",
                "evidence_required": "Prototype BOM, supplier evidence, logistics trial, installation timing, inspection and maintenance results.",
                "falsification": "Supply, transport, site, code, reliability or maintenance constraints prevent repeatable safe deployment.",
            }
        )

    obstacles = [
        {"category": "UNKNOWN_CUSTOMER", "owner": "research", "response": "Segment interviews and workflow observation before product commitment."},
        {"category": "TECHNICAL_FEASIBILITY", "owner": "engineering", "response": "Prototype the highest-uncertainty constraint first with pass/fail thresholds."},
        {"category": "REGULATORY_OR_IP", "owner": "legal", "response": "Build a jurisdiction/prior-art register and route conclusions to qualified review."},
        {"category": "ECONOMIC_VIABILITY", "owner": "finance", "response": "Use bottom-up quoted costs and scenario gates; do not rely on headline market size."},
        {"category": "DELIVERY_AND_QUALITY", "owner": "operations", "response": "Pilot a complete delivery unit and record exceptions, defects, cycle time and rework."},
        {"category": "TRUST_AND_DISTRIBUTION", "owner": "marketing", "response": "Test proof-led channels and measure conversion without buying scale prematurely."},
    ]

    horizons = [
        {"horizon": "0–30 DAYS", "gate": "PROBLEM / CONSTRAINT DISCOVERY", "outcome": "Rank assumptions, collect credible evidence and choose the first falsification experiments."},
        {"horizon": "31–90 DAYS", "gate": "PROTOTYPE EVIDENCE", "outcome": "Demonstrate or reject the smallest end-to-end customer outcome with safety and cost measurements."},
        {"horizon": "YEAR 1", "gate": "REPEATABLE PILOT", "outcome": "Prove a narrow segment, compliant delivery, initial retention, operating quality and viable unit-level economics."},
        {"horizon": "YEAR 4", "gate": "MULTI-MARKET REPEATABILITY", "outcome": "Expand only where product, supply, regulatory, service and distribution systems repeat with controlled risk."},
        {"horizon": "YEAR 5", "gate": "DURABLE PLATFORM", "outcome": "Operate a defensible portfolio/platform with audited impact, resilient economics and explicit stop/continue governance."},
    ]

    work_orders = [
        {
            "id": track["id"],
            "agent": track["owner"],
            "status": "QUEUED",
            "deliverable": track["deliverable"],
            "approval_required": track["approval_required"],
            "dependencies": [] if track["id"] in {"R01", "R03", "R04"} else ["R01"],
        }
        for track in tracks
    ]
    return {
        "schema_version": 1,
        "idea": clean,
        "venture_type": "PHYSICAL_OR_HYBRID" if physical else "GENERAL",
        "truth_policy": "HYPOTHESES_ARE_NOT_FACTS",
        "research_tracks": tracks,
        "hypotheses": hypotheses,
        "obstacle_register": obstacles,
        "horizons": horizons,
        "department_work_orders": work_orders,
        "opportunity_radar": {
            "status": "RESEARCH_PROTOCOL_READY",
            "notice": "JARVIS may rank only opportunities supported by current citable evidence; it must not invent future demand.",
            "signals": [
                "persistent costly customer workarounds",
                "regulatory or technology transitions",
                "falling enabling-technology cost",
                "unserved accessibility or climate needs",
                "fragmented supply with measurable quality gaps",
                "new distribution or interoperability standards",
            ],
            "score_dimensions": [
                "problem evidence", "reachability", "feasibility", "responsible economics",
                "timing", "defensibility", "regulatory path", "safety and impact",
            ],
        },
    }
