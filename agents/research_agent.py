import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime


# ============================================================
# JARVIS RESEARCH AGENT
# ============================================================

class ResearchAgent:

    def __init__(self):
        self.name = "research"

    # ========================================================
    # GOOGLE NEWS RSS SEARCH
    # ========================================================

    def search_news(self, query, limit=8):

        try:

            encoded = urllib.parse.quote(query)

            url = (
                "https://news.google.com/rss/search?"
                f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
            )

            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            response.raise_for_status()

            root = ET.fromstring(
                response.content
            )

            results = []

            for item in root.findall(".//item")[:limit]:

                title = item.findtext(
                    "title",
                    ""
                )

                link = item.findtext(
                    "link",
                    ""
                )

                published = item.findtext(
                    "pubDate",
                    ""
                )

                source = item.findtext(
                    "source",
                    ""
                )

                results.append({
                    "title": title,
                    "source": source,
                    "published": published,
                    "url": link,
                })

            return results

        except Exception as e:

            print(
                f"JARVIS RESEARCH DEBUG > {e}"
            )

            return []


    # ========================================================
    # MARKET NEWS
    # ========================================================

    def market_news(self):

        queries = [
            "stock market",
            "India stock market",
            "Nifty Sensex",
            "US stock market",
            "global markets",
        ]

        all_news = []

        for query in queries:

            news = self.search_news(
                query,
                limit=5
            )

            all_news.extend(
                news
            )

        return self.remove_duplicates(
            all_news
        )


    # ========================================================
    # SPORTS NEWS
    # ========================================================

    def sports_news(self):

        queries = [
            "sports",
            "cricket",
            "football",
            "tennis",
            "NBA",
        ]

        all_news = []

        for query in queries:

            news = self.search_news(
                query,
                limit=4
            )

            all_news.extend(
                news
            )

        return self.remove_duplicates(
            all_news
        )


    # ========================================================
    # GENERAL NEWS
    # ========================================================

    def general_news(self):

        queries = [
            "latest news",
            "world news",
            "India news",
            "technology news",
        ]

        all_news = []

        for query in queries:

            news = self.search_news(
                query,
                limit=5
            )

            all_news.extend(
                news
            )

        return self.remove_duplicates(
            all_news
        )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    def remove_duplicates(
        self,
        articles
    ):

        seen = set()
        results = []

        for article in articles:

            title = article.get(
                "title",
                ""
            ).strip()

            key = title.lower()

            if not title:
                continue

            if key in seen:
                continue

            seen.add(key)

            results.append(
                article
            )

        return results


    # ========================================================
    # FORMAT NEWS
    # ========================================================

    def format_news(
        self,
        articles,
        limit=10
    ):

        if not articles:

            return (
                "I couldn't retrieve "
                "current news right now."
            )

        lines = []

        lines.append(
            "Here are the latest headlines:"
        )

        lines.append("")

        for index, article in enumerate(
            articles[:limit],
            start=1
        ):

            title = article.get(
                "title",
                "Unknown headline"
            )

            source = article.get(
                "source",
                ""
            )

            if source:

                lines.append(
                    f"{index}. {title} "
                    f"({source})"
                )

            else:

                lines.append(
                    f"{index}. {title}"
                )

        return "\n".join(
            lines
        )


    # ========================================================
    # MAIN RESEARCH FUNCTION
    # ========================================================

    def research(
        self,
        query
    ):

        query = str(
            query
        ).strip()

        if not query:

            return {
                "success": False,
                "message":
                    "No research topic was provided."
            }


        value = query.lower()


        # ----------------------------------------------------
        # MARKET
        # ----------------------------------------------------

        if any(
            word in value
            for word in [
                "market",
                "stock",
                "stocks",
                "nifty",
                "sensex",
                "trading",
                "finance",
                "financial",
            ]
        ):

            articles = self.market_news()

            return {
                "success": True,
                "type": "market",
                "articles": articles,
                "message": self.format_news(
                    articles
                ),
            }


        # ----------------------------------------------------
        # SPORTS
        # ----------------------------------------------------

        if any(
            word in value
            for word in [
                "sport",
                "sports",
                "cricket",
                "football",
                "soccer",
                "tennis",
                "nba",
                "f1",
            ]
        ):

            articles = self.sports_news()

            return {
                "success": True,
                "type": "sports",
                "articles": articles,
                "message": self.format_news(
                    articles
                ),
            }


        # ----------------------------------------------------
        # GENERAL
        # ----------------------------------------------------

        articles = self.search_news(
            query,
            limit=10
        )

        return {
            "success": True,
            "type": "general",
            "articles": articles,
            "message": self.format_news(
                articles
            ),
        }


# ============================================================
# GLOBAL AGENT
# ============================================================

research_agent = ResearchAgent()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def research(query):

    return research_agent.research(
        query
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("JARVIS RESEARCH AGENT TEST")
    print("=" * 60)

    result = research(
        "today's market news"
    )

    print()

    print(
        result.get(
            "message",
            result
        )
    )
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime


# ============================================================
# JARVIS RESEARCH AGENT
# ============================================================

class ResearchAgent:

    def __init__(self):
        self.name = "research"

    # ========================================================
    # GOOGLE NEWS RSS SEARCH
    # ========================================================

    def search_news(self, query, limit=8):

        try:

            encoded = urllib.parse.quote(query)

            url = (
                "https://news.google.com/rss/search?"
                f"q={encoded}&hl=en-US&gl=US&ceid=US:en"
            )

            response = requests.get(
                url,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            response.raise_for_status()

            root = ET.fromstring(
                response.content
            )

            results = []

            for item in root.findall(".//item")[:limit]:

                title = item.findtext(
                    "title",
                    ""
                )

                link = item.findtext(
                    "link",
                    ""
                )

                published = item.findtext(
                    "pubDate",
                    ""
                )

                source = item.findtext(
                    "source",
                    ""
                )

                results.append({
                    "title": title,
                    "source": source,
                    "published": published,
                    "url": link,
                })

            return results

        except Exception as e:

            print(
                f"JARVIS RESEARCH DEBUG > {e}"
            )

            return []


    # ========================================================
    # MARKET NEWS
    # ========================================================

    def market_news(self):

        queries = [
            "stock market",
            "India stock market",
            "Nifty Sensex",
            "US stock market",
            "global markets",
        ]

        all_news = []

        for query in queries:

            news = self.search_news(
                query,
                limit=5
            )

            all_news.extend(
                news
            )

        return self.remove_duplicates(
            all_news
        )


    # ========================================================
    # SPORTS NEWS
    # ========================================================

    def sports_news(self):

        queries = [
            "sports",
            "cricket",
            "football",
            "tennis",
            "NBA",
        ]

        all_news = []

        for query in queries:

            news = self.search_news(
                query,
                limit=4
            )

            all_news.extend(
                news
            )

        return self.remove_duplicates(
            all_news
        )


    # ========================================================
    # GENERAL NEWS
    # ========================================================

    def general_news(self):

        queries = [
            "latest news",
            "world news",
            "India news",
            "technology news",
        ]

        all_news = []

        for query in queries:

            news = self.search_news(
                query,
                limit=5
            )

            all_news.extend(
                news
            )

        return self.remove_duplicates(
            all_news
        )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    def remove_duplicates(
        self,
        articles
    ):

        seen = set()
        results = []

        for article in articles:

            title = article.get(
                "title",
                ""
            ).strip()

            key = title.lower()

            if not title:
                continue

            if key in seen:
                continue

            seen.add(key)

            results.append(
                article
            )

        return results


    # ========================================================
    # FORMAT NEWS
    # ========================================================

    def format_news(
        self,
        articles,
        limit=10
    ):

        if not articles:

            return (
                "I couldn't retrieve "
                "current news right now."
            )

        lines = []

        lines.append(
            "Here are the latest headlines:"
        )

        lines.append("")

        for index, article in enumerate(
            articles[:limit],
            start=1
        ):

            title = article.get(
                "title",
                "Unknown headline"
            )

            source = article.get(
                "source",
                ""
            )

            if source:

                lines.append(
                    f"{index}. {title} "
                    f"({source})"
                )

            else:

                lines.append(
                    f"{index}. {title}"
                )

        return "\n".join(
            lines
        )


    # ========================================================
    # MAIN RESEARCH FUNCTION
    # ========================================================

    def research(
        self,
        query
    ):

        query = str(
            query
        ).strip()

        if not query:

            return {
                "success": False,
                "message":
                    "No research topic was provided."
            }


        value = query.lower()


        # ----------------------------------------------------
        # MARKET
        # ----------------------------------------------------

        if any(
            word in value
            for word in [
                "market",
                "stock",
                "stocks",
                "nifty",
                "sensex",
                "trading",
                "finance",
                "financial",
            ]
        ):

            articles = self.market_news()

            return {
                "success": True,
                "type": "market",
                "articles": articles,
                "message": self.format_news(
                    articles
                ),
            }


        # ----------------------------------------------------
        # SPORTS
        # ----------------------------------------------------

        if any(
            word in value
            for word in [
                "sport",
                "sports",
                "cricket",
                "football",
                "soccer",
                "tennis",
                "nba",
                "f1",
            ]
        ):

            articles = self.sports_news()

            return {
                "success": True,
                "type": "sports",
                "articles": articles,
                "message": self.format_news(
                    articles
                ),
            }


        # ----------------------------------------------------
        # GENERAL
        # ----------------------------------------------------

        articles = self.search_news(
            query,
            limit=10
        )

        return {
            "success": True,
            "type": "general",
            "articles": articles,
            "message": self.format_news(
                articles
            ),
        }


# ============================================================
# GLOBAL AGENT
# ============================================================

research_agent = ResearchAgent()


# ============================================================
# SIMPLE FUNCTION
# ============================================================

def research(query):

    return research_agent.research(
        query
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("JARVIS RESEARCH AGENT TEST")
    print("=" * 60)

    result = research(
        "today's market news"
    )

    print()

    print(
        result.get(
            "message",
            result
        )
    )