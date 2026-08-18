# ============================================================
# JARVIS HEAD AGENT
# ============================================================

import re


# ============================================================
# HEAD AGENT
# ============================================================

class HeadAgent:

    def __init__(self):

        self.name = "head"

        self.departments = {

            "operator": [
                "operator", "end-to-end", "handle everything", "full autonomous mission",
            ],

            "web_intelligence": [
                "search the web", "search online", "find online", "read this website",
                "read this webpage", "web research", "look up online", "http://", "https://",
            ],

            "computer": [
                "open",
                "close",
                "launch",
                "start",
                "notepad",
                "calculator",
                "computer",
                "pc",
                "file",
                "folder",
                "application",
                "app",
                "system",
                "windows",
            ],

            "research": [
                "news",
                "today's news",
                "todays news",
                "latest news",
                "market news",
                "financial news",
                "world news",
                "politics news",
                "sports news",
                "research",
                "search",
                "latest",
                "today",
                "what happened",
                "what's happening",
            ],

            "trading": [
                "trade",
                "trading",
                "stock",
                "stocks",
                "share",
                "shares",
                "forex",
                "crypto",
                "bitcoin",
                "ethereum",
                "option",
                "options",
                "futures",
                "commodity",
                "commodities",
                "market",
                "markets",
                "portfolio",
                "buy",
                "sell",
                "technical analysis",
                "fundamental analysis",
                "crude oil",
                "wti",
                "brent",
                "gold futures",
                "silver futures",
                "natural gas futures",
            ],

            "coding": [
                "code",
                "coding",
                "program",
                "programming",
                "python",
                "javascript",
                "java",
                "c++",
                "html",
                "css",
                "sql",
                "debug",
                "developer",
                "development",
                "script",
                "function",
                "class",
                "api",
                "software",
            ],

            "office": [
                "excel",
                "spreadsheet",
                "word",
                "document",
                "powerpoint",
                "presentation",
                "report",
                "office",
                "csv",
                "pdf",
                "table",
                "formula",
            ],

            "chat": [
                "hello",
                "hi",
                "hey",
                "how are you",
                "who are you",
                "what are you",
                "good morning",
                "good afternoon",
                "good evening",
                "thanks",
                "thank you",
            ],

            "strategy": ["strategy", "business plan", "venture thesis", "okr", "executive decision"],
            "product": ["product roadmap", "product requirements", "user story", "mvp scope"],
            "engineering": ["architecture", "engineering plan", "technical design", "release plan"],
            "data_ai": ["ai evaluation", "machine learning", "data architecture", "model evaluation"],
            "design": ["user experience", "ux design", "prototype", "design system", "accessibility"],
            "security": ["security review", "threat model", "cybersecurity", "incident response"],
            "legal": ["legal research", "compliance", "privacy policy", "terms and conditions"],
            "finance": ["budget", "unit economics", "runway", "financial model"],
            "operations": ["operations plan", "standard operating procedure", "sop", "service level"],
            "marketing": ["marketing plan", "positioning", "campaign", "content strategy"],
            "sales": ["sales plan", "sales pipeline", "proposal", "lead qualification"],
            "customer_success": ["customer success", "customer onboarding", "retention", "support playbook"],
            "people": ["hiring plan", "job scorecard", "people operations", "employee onboarding"],
            "quality": ["quality plan", "risk register", "acceptance criteria", "release gate"],
        }


    # ========================================================
    # NORMALIZE
    # ========================================================

    def normalize(self, text):

        if not text:
            return ""

        text = str(text).lower().strip()

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text


    # ========================================================
    # DETECT DEPARTMENT
    # ========================================================

    def detect_department(self, text):

        value = self.normalize(text)

        if not value:
            return "chat"


        # ----------------------------------------------------
        # COMPUTER
        # ----------------------------------------------------

        computer_phrases = [
            "open notepad",
            "open calculator",
            "close notepad",
            "close calculator",
            "open app",
            "open application",
            "launch app",
            "launch application",
            "open folder",
            "open file",
            "close app",
            "close application",
            "computer specs",
            "system information",
        ]

        if any(
            phrase in value
            for phrase in computer_phrases
        ):

            return "computer"

        # ----------------------------------------------------
        # UNIVERSAL OPERATOR / PUBLIC WEB
        # ----------------------------------------------------

        if any(
            phrase in value
            for phrase in [
                "do this end-to-end", "do it end-to-end", "handle this end-to-end",
                "handle everything end-to-end", "full autonomous mission", "operator:",
            ]
        ):
            return "operator"

        if (
            re.search(r"https?://", value)
            or any(
                phrase in value
                for phrase in [
                    "search the web", "search online", "find online", "find on the web",
                    "read this website", "read this webpage", "read this url",
                    "web research", "research online", "look up online", "find websites",
                ]
            )
        ):
            return "web_intelligence"

        # ----------------------------------------------------
        # COMPANY SPECIALISTS
        # ----------------------------------------------------

        specialist_phrases = {
            "security": ["security review", "threat model", "cybersecurity", "incident response"],
            "legal": ["legal research", "compliance", "privacy policy", "terms and conditions"],
            "finance": ["financial model", "unit economics", "budget", "runway"],
            "marketing": ["marketing plan", "positioning", "campaign plan", "content strategy"],
            "sales": ["sales plan", "sales pipeline", "lead qualification", "discovery script"],
            "customer_success": ["customer success", "customer onboarding", "retention plan", "support playbook"],
            "people": ["hiring plan", "job scorecard", "people operations", "employee onboarding"],
            "operations": ["operations plan", "standard operating procedure", "service level", "operating cadence"],
            "quality": ["quality plan", "risk register", "release gate", "test strategy"],
            "product": ["product roadmap", "product requirements", "user story", "mvp scope"],
            "design": ["user experience", "ux design", "design system", "accessibility review"],
            "data_ai": ["ai evaluation", "machine learning plan", "data architecture", "model evaluation"],
            "engineering": ["software architecture", "engineering plan", "technical design", "release plan"],
            "strategy": ["business plan", "venture thesis", "company strategy", "executive decision", "okr"],
        }

        for department, phrases in specialist_phrases.items():
            if any(phrase in value for phrase in phrases):
                return department


        # ----------------------------------------------------
        # TRADING
        # ----------------------------------------------------

        trading_phrases = [
            "trading",
            "trade",
            "stock market",
            "stock",
            "stocks",
            "forex",
            "crypto",
            "bitcoin",
            "ethereum",
            "options",
            "option trading",
            "futures",
            "commodities",
            "portfolio",
            "buy stock",
            "sell stock",
            "buy bitcoin",
            "sell bitcoin",
            "technical analysis",
            "fundamental analysis",
            "trading strategy",
            "trading system",
            "crude oil",
            "wti",
            "brent",
            "gold futures",
            "silver futures",
            "natural gas futures",
        ]

        if any(
            phrase in value
            for phrase in trading_phrases
        ):

            return "trading"


        # ----------------------------------------------------
        # CODING
        # ----------------------------------------------------

        coding_phrases = [
            "write code",
            "write python",
            "write python code",
            "write javascript",
            "write java",
            "write c++",
            "write html",
            "write css",
            "write sql",
            "coding",
            "code",
            "programming",
            "program",
            "debug",
            "debug code",
            "fix my code",
            "create a script",
            "write a script",
            "developer",
            "software",
            "api",
        ]

        if any(
            phrase in value
            for phrase in coding_phrases
        ):

            return "coding"


        # ----------------------------------------------------
        # OFFICE
        # ----------------------------------------------------

        office_phrases = [
            "excel",
            "spreadsheet",
            "word document",
            "powerpoint",
            "presentation",
            "make a report",
            "create a report",
            "generate a report",
            "office document",
            "csv file",
            "pdf report",
        ]

        if any(
            phrase in value
            for phrase in office_phrases
        ):

            return "office"


        # ----------------------------------------------------
        # RESEARCH / NEWS
        # ----------------------------------------------------

        research_phrases = [
            "news",
            "today's news",
            "todays news",
            "latest news",
            "market news",
            "financial news",
            "world news",
            "sports news",
            "latest market",
            "what happened today",
            "what is happening today",
            "research",
            "search the web",
            "search online",
            "find information",
        ]

        if any(
            phrase in value
            for phrase in research_phrases
        ):

            return "research"


        # ----------------------------------------------------
        # SPORTS
        #
        # Sports research goes to research for now.
        # Later we can add a dedicated sports agent.
        # ----------------------------------------------------

        sports_words = [
            "sports",
            "sport",
            "football",
            "soccer",
            "cricket",
            "tennis",
            "nba",
            "nfl",
            "f1",
            "formula 1",
            "basketball",
            "baseball",
            "match",
            "matches",
            "game",
            "games",
            "score",
            "scores",
        ]

        if any(
            word in value
            for word in sports_words
        ):

            return "research"


        # ----------------------------------------------------
        # CHAT
        # ----------------------------------------------------

        return "chat"


    # ========================================================
    # ROUTE
    # ========================================================

    def route(self, text):

        department = self.detect_department(
            text
        )

        print(
            f"\nJARVIS HEAD AGENT > "
            f"{department}"
        )

        return department


    # ========================================================
    # INFORMATION
    # ========================================================

    def get_departments(self):

        return list(
            self.departments.keys()
        )


# ============================================================
# GLOBAL HEAD AGENT
# ============================================================

head_agent = HeadAgent()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def detect_department(text):

    return head_agent.detect_department(
        text
    )


def route(text):

    return head_agent.route(
        text
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("JARVIS HEAD AGENT TEST")
    print("=" * 60)

    tests = [

        "open notepad",

        "give me todays market news",

        "write Python code",

        "show me today's sports news",

        "make an Excel report",

        "trade bitcoin",

        "hi Jarvis",

    ]

    for text in tests:

        department = head_agent.detect_department(
            text
        )

        print(
            f"{text} -> {department}"
        )
