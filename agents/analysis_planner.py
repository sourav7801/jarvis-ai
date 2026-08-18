# ============================================================
# JARVIS V2.1 - ANALYSIS PLANNER
# ============================================================

import re


# ============================================================
# NORMALIZATION
# ============================================================

def normalize(text):
    if text is None:
        return ""

    return " ".join(
        str(text).strip().lower().split()
    )


# ============================================================
# KEYWORDS
# ============================================================

EXCEL_KEYWORDS = {
    "excel",
    "xlsx",
    "spreadsheet",
    "workbook",
}

HTML_KEYWORDS = {
    "html",
    "web dashboard",
    "webpage",
    "browser dashboard",
    "website dashboard",
}

DASHBOARD_KEYWORDS = {
    "dashboard",
    "visual dashboard",
    "interactive dashboard",
    "kpi dashboard",
}

ANALYSIS_KEYWORDS = {
    "analyze",
    "analyse",
    "analysis",
    "analyzing",
    "profiling",
    "profile",
    "statistics",
    "stats",
    "insights",
    "summary",
    "report",
    "dashboard",
}


# ============================================================
# HELPERS
# ============================================================

def contains_any(text, keywords):

    for keyword in keywords:

        if keyword in text:
            return True

    return False


def wants_excel(text):

    return contains_any(
        text,
        EXCEL_KEYWORDS,
    )


def wants_html(text):

    return contains_any(
        text,
        HTML_KEYWORDS,
    )


def wants_dashboard(text):

    return contains_any(
        text,
        DASHBOARD_KEYWORDS,
    )


def wants_analysis(text):

    return contains_any(
        text,
        ANALYSIS_KEYWORDS,
    )


# ============================================================
# REQUESTED ANALYSIS EXTRACTION
# ============================================================

def extract_requested_items(request):

    text = normalize(request)

    items = []

    # --------------------------------------------------------
    # Explicit concepts
    # --------------------------------------------------------

    concepts = {

        "sales trends": [
            "sales trend",
            "sales trends",
            "monthly sales",
            "daily sales",
            "weekly sales",
            "sales over time",
        ],

        "profit analysis": [
            "profit",
            "profitability",
            "profit analysis",
            "profit margin",
            "profit margins",
        ],

        "top products": [
            "top products",
            "best products",
            "best selling products",
            "product performance",
            "product analysis",
        ],

        "regional performance": [
            "regional performance",
            "region performance",
            "regional analysis",
            "sales by region",
            "performance by region",
        ],

        "customer analysis": [
            "customer analysis",
            "customer performance",
            "top customers",
            "customer trends",
        ],

        "category analysis": [
            "category analysis",
            "category performance",
            "sales by category",
        ],

        "date trends": [
            "date trends",
            "time trends",
            "trend over time",
            "trends over time",
        ],

        "missing values": [
            "missing values",
            "missing data",
            "null values",
        ],

        "duplicates": [
            "duplicate rows",
            "duplicates",
        ],

        "data quality": [
            "data quality",
            "quality check",
            "data cleaning",
        ],

        "numeric statistics": [
            "numeric statistics",
            "statistics",
            "stats",
        ],

    }

    for canonical, aliases in concepts.items():

        for alias in aliases:

            if alias in text:

                if canonical not in items:
                    items.append(canonical)

                break

    # --------------------------------------------------------
    # Phrases after "show", "include", "calculate"
    # --------------------------------------------------------

    patterns = [

        r"show(?:ing)?\s+(.+?)(?:\.|$)",

        r"include\s+(.+?)(?:\.|$)",

        r"calculate\s+(.+?)(?:\.|$)",

        r"with\s+(.+?)(?:\.|$)",

    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            value = match.strip()

            if not value:
                continue

            # Do not treat Windows paths as analysis items.
            if ":\\" in value:
                continue

            parts = re.split(
                r",|\band\b|\&",
                value,
            )

            for part in parts:

                part = part.strip()

                if (
                    len(part) > 2
                    and "dashboard" not in part
                    and "report" not in part
                ):

                    if part not in items:
                        items.append(part)

    return items[:20]


# ============================================================
# DEFAULT ANALYSIS
# ============================================================

def default_analysis_items():

    return [

        "dataset overview",

        "data quality",

        "missing values",

        "duplicate rows",

        "numeric statistics",

        "categorical analysis",

        "date/time trends",

        "automatic insights",

    ]


# ============================================================
# BUILD ANALYSIS PLAN
# ============================================================

def build_analysis_plan(request):

    original_request = str(
        request or ""
    ).strip()

    text = normalize(
        original_request
    )

    excel = wants_excel(
        text
    )

    html = wants_html(
        text
    )

    dashboard = wants_dashboard(
        text
    )

    analysis = wants_analysis(
        text
    )

    requested_items = extract_requested_items(
        original_request
    )

    # --------------------------------------------------------
    # Dashboard without a specific format
    # --------------------------------------------------------

    if dashboard and not excel and not html:

        excel = True
        html = True

    # --------------------------------------------------------
    # Excel dashboard
    # --------------------------------------------------------

    if dashboard and "excel" in text:

        excel = True

    # --------------------------------------------------------
    # Any report/dashboard request means analysis is required.
    # --------------------------------------------------------

    if excel or html:

        analysis = True

    # --------------------------------------------------------
    # Generic analysis
    # --------------------------------------------------------

    if analysis and not requested_items:

        requested_items = default_analysis_items()

    return {

        "version": "2.1",

        "original_request": original_request,

        "analysis": analysis,

        "excel_report": excel,

        "excel_dashboard": (
            excel and dashboard
        ),

        "html_dashboard": html,

        "dashboard": dashboard,

        "requested_items": requested_items,

        "automatic_profile": analysis,

    }


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def create_analysis_plan(request):

    return build_analysis_plan(
        request
    )


# ============================================================
# HUMAN READABLE PLAN
# ============================================================

def format_plan(plan):

    lines = []

    lines.append(
        "JARVIS ANALYSIS PLAN"
    )

    lines.append(
        "--------------------------------------------------"
    )

    lines.append(
        "Analysis: "
        + (
            "YES"
            if plan.get("analysis")
            else "NO"
        )
    )

    lines.append(
        "Excel Report: "
        + (
            "YES"
            if plan.get("excel_report")
            else "NO"
        )
    )

    lines.append(
        "Excel Dashboard: "
        + (
            "YES"
            if plan.get("excel_dashboard")
            else "NO"
        )
    )

    lines.append(
        "HTML Dashboard: "
        + (
            "YES"
            if plan.get("html_dashboard")
            else "NO"
        )
    )

    requested = plan.get(
        "requested_items",
        [],
    )

    if requested:

        lines.append("")

        lines.append(
            "Requested Analysis:"
        )

        for index, item in enumerate(
            requested,
            start=1,
        ):

            lines.append(
                f"{index}. {item}"
            )

    return "\n".join(
        lines
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    examples = [

        (
            "analyze sales.xlsx and create "
            "an Excel dashboard showing monthly "
            "sales, top products, regional performance "
            "and profit"
        ),

        (
            "analyze this dataset and create "
            "a professional HTML dashboard"
        ),

        (
            "create an Excel report"
        ),

        (
            "analyze the dataset"
        ),

    ]

    for example in examples:

        print()
        print("=" * 60)
        print("REQUEST:")
        print(example)
        print()

        plan = create_analysis_plan(
            example
        )

        print(
            format_plan(plan)
        )