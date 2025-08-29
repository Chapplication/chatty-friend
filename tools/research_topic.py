from .llm_tool_base import LLMTool, LLMToolParameter


class ResearchTopic(LLMTool):
    def __init__(self, master_state):    
        topic = LLMToolParameter("topic","The topic to research on Wikipedia. Be specific for best results (e.g., 'Python programming language' vs 'Python')", required=True)
        detail_level = LLMToolParameter("detail_level","Level of detail for the response: 'quick' for brief summary, 'medium' for moderate detail, 'long' for comprehensive information", enum=["quick", "medium", "long"], required=False)
        super().__init__("wikipedia_search_tool", "Research topics using Wikipedia to get factual information. Returns summaries of varying detail levels.", [topic, detail_level], master_state)
        
        # Configure sentence counts for different detail levels
        self.sentence_counts = {
            "quick": 2,
            "medium": 4, 
            "long": 7,
            "": 2  # Default fallback
        }
        
        # Set user agent for Wikipedia API (recommended practice)
        try:
            import wikipedia
            wikipedia.set_user_agent("Chatty Friend Voice Assistant/1.0 (https://github.com/chatty-friend)")
        except:
            pass

    async def invoke(self, args):
        """Research a topic with comprehensive error handling"""
        try:
            # Validate inputs
            topic = args.get("topic", "").strip()
            detail_level = args.get("detail_level", "").lower().strip()
            
            sentence_count = self.sentence_counts[detail_level]
            
            # Attempt Wikipedia search with specific error handling
            try:
                import wikipedia
                
                # Get summary with specified sentence count
                summary = wikipedia.summary(topic, sentences=sentence_count, auto_suggest=True)
                
                if not summary or not summary.strip():
                    return f"Wikipedia article for '{topic}' exists but appears to be empty. Please try a different search term."
                
                # Format response with detail level context
                detail_labels = {
                    "quick": "Brief overview",
                    "medium": "Detailed summary", 
                    "long": "Comprehensive information"
                }
                
                response = f"{detail_labels.get(detail_level, 'Summary')} of '{topic}' from Wikipedia.  Please summarize for the user and discuss the results with them:\n\n{summary}"
                
                # Add note if summary seems truncated
                if len(summary.split('.')) >= sentence_count and not summary.endswith('.'):
                    response += "..."
                
                return response
                
            except Exception as e:
                pass
                    
        except Exception as e:
            pass
    
        return f"Wikipedia search encountered an error"
