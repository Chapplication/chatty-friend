from .llm_tool_base import LLMTool, LLMToolParameter

# RSS News Feed URLs
RSS_NEWS_FEEDS = {
    "BBC": {
        "name": "BBC News",
        "general": "http://feeds.bbci.co.uk/news/rss.xml",
        "world": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "politics": "http://feeds.bbci.co.uk/news/politics/rss.xml",
        "business": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "technology": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "health": "http://feeds.bbci.co.uk/news/health/rss.xml",
        "sports": "http://feeds.bbci.co.uk/sport/rss.xml"
    },
    "Reuters": {
        "name": "Reuters",
        "general": "http://feeds.reuters.com/reuters/topNews",
        "world": "http://feeds.reuters.com/Reuters/worldNews",
        "politics": "http://feeds.reuters.com/Reuters/PoliticsNews",
        "business": "http://feeds.reuters.com/reuters/businessNews",
        "technology": "http://feeds.reuters.com/reuters/technologyNews",
        "science": "http://feeds.reuters.com/reuters/scienceNews",
        "health": "http://feeds.reuters.com/reuters/healthNews",
        "sports": "http://feeds.reuters.com/reuters/sportsNews"
    },
    "Associated Press": {
        "name": "Associated Press",
        "general": "https://apnews.com/apf-topnews",
        "world": "https://apnews.com/apf-worldnews",
        "politics": "https://apnews.com/apf-usnews",
        "business": "https://apnews.com/apf-business",
        "technology": "https://apnews.com/apf-technology",
        "science": "https://apnews.com/apf-science",
        "health": "https://apnews.com/apf-health",
        "sports": "https://apnews.com/apf-sports"
    },
    "NPR": {
        "name": "NPR",
        "general": "https://feeds.npr.org/1001/rss.xml",
        "world": "https://feeds.npr.org/1004/rss.xml",
        "politics": "https://feeds.npr.org/1014/rss.xml",
        "business": "https://feeds.npr.org/1006/rss.xml",
        "technology": "https://feeds.npr.org/1019/rss.xml",
        "science": "https://feeds.npr.org/1007/rss.xml",
        "health": "https://feeds.npr.org/1128/rss.xml",
        "sports": "https://feeds.npr.org/1055/rss.xml"
    },
    "CNN": {
        "name": "CNN",
        "general": "http://rss.cnn.com/rss/edition.rss",
        "world": "http://rss.cnn.com/rss/edition_world.rss",
        "politics": "http://rss.cnn.com/rss/edition_politics.rss",
        "business": "http://rss.cnn.com/rss/money_latest.rss",
        "technology": "http://rss.cnn.com/rss/edition_technology.rss",
        "science": "http://rss.cnn.com/rss/edition_space.rss",
        "health": "http://rss.cnn.com/rss/edition_health.rss",
        "sports": "http://rss.cnn.com/rss/edition_sport.rss"
    }
}

class NewsService(LLMTool):
    def __init__(self, master_state):
        self.use_system_voice = True

        self.categories = [k for k in RSS_NEWS_FEEDS[list(RSS_NEWS_FEEDS.keys())[0]].keys() if k != "name"]
        category = LLMToolParameter("category", "News category (e.g., "+", ".join(self.categories)+"). Leave empty for general news.", enum=self.categories, required=False)
        count = LLMToolParameter("count", "Number of news stories to retrieve (1-15, default: 5)", required=False)
        super().__init__("news_service", "Get the latest news. Can filter by category and specify how much news to retrieve. No API key required.", [category, count], master_state)
    
    def get_news_provider(self):
        """Get configured news provider from settings"""
        return self.master_state.conman.get_config("NEWS_PROVIDER")
    
    def get_rss_url(self, provider, category):
        """Get RSS URL for provider and category"""
        if provider in RSS_NEWS_FEEDS:
            if category in RSS_NEWS_FEEDS[provider]:
                return RSS_NEWS_FEEDS[provider][category]
            elif "general" in RSS_NEWS_FEEDS[provider]:
                return RSS_NEWS_FEEDS[provider]["general"]
    
    def validate_count(self, count):
        """Validate and normalize count parameter"""
        try:
            count_int = int(count) if count else 5
            return max(1, min(count_int, 15))  # Clamp between 1 and 15
        except (ValueError, TypeError):
            return 5
    
    def parse_rss_feed(self, url, count):
        """Parse RSS feed and return formatted entries"""
        try:
            import feedparser
            
            # Parse the RSS feed with timeout
            feed = feedparser.parse(url)
            
            if feed.bozo and feed.bozo_exception:
                return None, f"Error parsing RSS feed: {str(feed.bozo_exception)}"
            
            entries = feed.entries[:count]
            if not entries:
                return None, "No news stories found in the RSS feed."
            
            return entries, None
            
        except ImportError:
            return None, "RSS parser not available. Please install feedparser."
        except Exception as e:
            return None, f"Error fetching RSS feed: {str(e)}"
    
    def format_story(self, entry, index):
        """Format a single news story for output"""
        try:
            title = entry.get('title', 'No title available').strip()
            summary = entry.get('summary', entry.get('description', '')).strip()
            
            # Clean up HTML tags from summary if present
            import re
            if summary:
                summary = re.sub(r'<[^>]+>', '', summary)
                summary = re.sub(r'\s+', ' ', summary).strip()
                # Limit summary length
                if len(summary) > 200:
                    summary = summary[:200] + "..."
            
            # Format the story
            story = f"**{title}**"
            if summary:
                story += f"\n{summary}"
            
            return story
        except Exception as e:
            return f"Error formatting story {index}: {str(e)}"
    
    async def invoke(self, args):
        """Main method to fetch and return news stories"""
        try:
            
            # Validate parameters
            category = args.get("category","general").lower()
            if category not in self.categories:
                category = "general"
            count = args.get("count", 5)
            if not count or not isinstance(count, int):
                count = 5
            count = max(1, min(count, 15))
            
            # Get news provider
            provider = self.get_news_provider()
            
            # Get RSS URL
            rss_url = self.get_rss_url(provider, category)
            if not rss_url:
                return f"No RSS feed available for {provider} in category '{category}'. Try 'general' category."
            
            # Parse RSS feed
            entries, error = self.parse_rss_feed(rss_url, count)
            if error:
                return f"News service error: {error}"
            
            # Format response
            provider_name = RSS_NEWS_FEEDS.get(provider, {}).get("name", provider)
            category_display = category.replace('_', ' ').title() if category != 'general' else 'Latest News'
            
            response_parts = []
            response_parts.append(f"Here are the latest {category_display.lower()} from {provider_name}.  Please summarize for the user and discuss the news with them:")
            
            for i, entry in enumerate(entries, 1):
                story = self.format_story(entry, i)
                response_parts.append(f"\nStory {i}: {story}")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            print(f"NewsService error: {e}")
            return "News service encountered an unexpected error. Please try again or contact support."