"""
WebSearch Agent - Fetches live web data via Tavily API.
"""
from datetime import datetime
from config.settings import get_settings
from config.logger import logger
from agents.state import AgentState

settings = get_settings()


def web_search_node(state: AgentState) -> AgentState:
    """
    WebSearch node: fetches live web data for real-time context.
    """
    logger.info(f"WebSearch: Searching for '{state['query'][:50]}...'")
    
    if not settings.tavily_api_key:
        logger.warning("WebSearch: TAVILY_API_KEY not set, skipping")
        state['web_results'] = []
        return state
    
    try:
        from tavily import TavilyClient
        
        client = TavilyClient(api_key=settings.tavily_api_key)
        
        # Perform search
        response = client.search(
            query=state['query'],
            max_results=5,
            include_answer=True,
        )
        
        # Extract results
        web_results = []
        for result in response.get('results', []):
            web_results.append({
                'title': result.get('title', 'No title'),
                'url': result.get('url', ''),
                'snippet': result.get('snippet', '')[:300],
                'score': result.get('score', 0),
            })
        
        state['web_results'] = web_results
        
        logger.info(f"WebSearch: Found {len(web_results)} results")
        
        state['agent_trace'].append({
            'agent': 'web_search',
            'timestamp': datetime.utcnow().isoformat(),
            'input_summary': f"Query: {state['query'][:50]}...",
            'output_summary': f"Found {len(web_results)} web results",
            'duration_ms': 0,
            'token_count': 0,
        })
        
        return state
        
    except Exception as e:
        logger.error(f"WebSearch error: {str(e)}")
        state['errors'].append(f"WebSearch error: {str(e)}")
        state['web_results'] = []
        return state
