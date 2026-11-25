# Publishing deals

The public dashboard only displays what is committed to `deals-feed.json`. It starts empty; do not add sample listings or copy in unverified scraper results.

1. Verify the public listing, exact item and price, and any deadline or pickup requirement.
2. Add the lead to one of the existing feed arrays. Include the name, price, and public HTTPS source link. Do not include account data, private links, or secrets.
3. Commit the update. The Validate deals feed workflow checks the JSON and source-link format, not live availability or resale value. It has read-only access and requires no personal access token.

The previous scheduled scraper is not connected to the public feed. The source remains in `scraper.py` for reference; the validator neither runs it nor writes back to the repository.
