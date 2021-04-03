from youtube_search import YoutubeSearch
import json

def get_details(search):
    results = YoutubeSearch(search, max_results=1).to_json()
    results = json.loads(results)
    details = results['videos'][0]
    return details




#print(get_details('new song'))
