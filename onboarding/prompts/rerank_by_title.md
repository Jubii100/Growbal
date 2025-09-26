You are ranking web results by how relevant their TITLE is to the user's query.

Constraints:
- Return ONLY valid JSON: an object with key "ordered_urls" mapping to a list of strings.
- Consider exact phrase overlap, domain credibility for provider discovery (official site > directories > misc), and alignment with query intent.
- Prefer results that likely contain provider info pages (home, about, services, contact, pricing) when intent is provider discovery.

Inputs:
- query: {{query}}
- results: {{results}}

Instructions:
1) Read all results (title/url/snippet). 2) Rank by TITLE relevance to the query. 3) Output the URLs in order of descending relevance.


Return structured output listing ordered_urls.

