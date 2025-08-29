from .llm_tool_base import LLMTool, LLMToolParameter
import json

class GoogleSearch(LLMTool):
    def __init__(self, master_state):
        query = LLMToolParameter("query","Search query for finding information on the web. Be specific for best results.", required=True)
        num_results = LLMToolParameter("num_results","Number of search results to return (1-10, default: 5)", required=False)
        super().__init__("web_search", 
                         "Search the web using Google to find current information on any topic.",
                         [query, num_results], 
                         master_state)
        self.api_key = master_state.secrets_manager.get_secret('google_search_api_key')
        self.base_url = f"https://www.googleapis.com/customsearch/v1?key={self.api_key}&cx=c6a0b091a8502493d&q="
        self.request_timeout = 10  # seconds
        self.max_retries = 2

    def can_invoke(self):
        return self.api_key is not None

    def validate_query(self, query):
        """Validate and clean search query"""
        if not query or not query.strip():
            return None, "Please provide a search query."
        
        query = query.strip()
        if len(query) > 50:
            return None, "Search query is too long. Please provide a shorter query."
        
        # Basic sanitization while preserving search operators
        if len(query) < 2:
            return None, "Search query is too short. Please provide a more specific query."
        
        return query, None

    def make_search_request(self, query, count):
        import requests

        try:
            headers_Get = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:49.0) Gecko/20100101 Firefox/49.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }

            url = self.base_url + '+'.join(query.split())
            r = requests.Session().get(url, headers=headers_Get)  
            result_text = None
            def extract_search_text_simple(r):
                """
                Extract just the essential text content (titles and snippets) from search results.
                
                Args:
                    r: requests.Response object from Google Custom Search API
                
                Returns:
                    str: Concatenated titles and snippets
                """
                try:
                    # Handle Response object or string
                    if hasattr(r, 'text'):
                        data = json.loads(r.text)
                    elif hasattr(r, 'json'):
                        data = r.json()
                    elif isinstance(r, str):
                        data = json.loads(r)
                    else:
                        data = r
                        
                    texts = []
                    
                    # Extract only titles and snippets
                    if 'items' in data:
                        for item in data.get('items', []):
                            if 'title' in item:
                                texts.append(item['title'])
                            if 'snippet' in item:
                                texts.append(item['snippet'])
                    
                    return ' '.join(texts)
                    
                except Exception as e:
                    return None
            result_text = extract_search_text_simple(r)
            
            return result_text or "No results found", None
        except Exception as e:
            pass
        return None, "Can't search right now."

        return None, "Search service temporarily unavailable after multiple attempts."

    async def invoke(self, args):
        """Main search invocation with comprehensive error handling"""
        try:
            # Validate inputs
            query = args.get("query", "").strip()
            num_results = args.get("num_results", "5").strip()
            
            # Validate query
            clean_query, query_error = self.validate_query(query)
            if query_error:
                return query_error
            
            # Validate number of results
            try:
                count = int(num_results)
                if count < 1 or count > 10:
                    count = 5  # Default fallback
            except (ValueError, TypeError):
                count = 5  # Default fallback
            
            # Make search request
            response, request_error = self.make_search_request(clean_query, count)
            if request_error:
                return request_error
            
            return response or "No results found"
                
        except Exception as e:
            return f"Web search encountered an unexpected error: {str(e)}. Please try again or contact support."