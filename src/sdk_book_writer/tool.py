from agents import function_tool
from langchain_community.utilities import WikipediaAPIWrapper

@function_tool
def search_tool(topic:str, aspect:str):
    """
    Perform a search based on the given topic and aspect to generate a book outline.
    """
    wiki_tool= WikipediaAPIWrapper()
     
    search_query= f"{topic} {aspect}"
    try:
        wiki_results= wiki_tool.run(search_query)
        return wiki_results
    except:
        wiki_results= "Wiki Search Failed"
    
