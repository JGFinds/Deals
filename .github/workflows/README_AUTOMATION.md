# Auto-updater for deals-feed.json (GitHub Actions)

This automation scrapes retail + secondary marketplaces and updates `deals-feed.json` in this repo.

## Setup steps

1. Add files to repo:
   - scraper.py
   - requirements.txt
   - .github/workflows/update_feed.yml

2. Add GitHub secret `GH_PUSH_TOKEN`:
   - Create a **Personal Access Token** on GitHub:
     - Settings -> Developer settings -> Personal access tokens -> Generate new token
     - Scopes: repo (full control of private repositories if repo is private; for public repo, repo:status + repo_deployment + repo:public_repo)
     - Copy the token
   - In your repo: Settings -> Secrets and variables -> Actions -> New repository secret
     - Name: `GH_PUSH_TOKEN`
     - Value: the token you created

3. (Optional) Enable Selenium:
   - Edit `.github/workflows/update_feed.yml` and set `SELENIUM_MODE: 'true'`.
   - Note: enabling Selenium makes the Action install Chrome and chromedriver — it increases runtime and complexity.

4. Commit & push to GitHub.
   - After you push, go to Actions -> Update deals-feed -> Run workflow (or wait for scheduled runs).

5. Check results:
   - After the action completes, check the repo root for `deals-feed.json` commit.
   - Your GitHub Pages dashboard (`index.html`) will fetch the updated JSON.

## Troubleshooting

- Action fails at Chrome install:
  - Try running with `SELENIUM_MODE: 'false'`.
  - Or move Selenium scraping to a self-hosted runner or separate server.

- Marketplace scraping returns few results:
  - Many marketplaces block scraping; consider using official APIs (e.g., eBay API) or increase robustness (Selenium, rotating proxies).
  - For higher reliability, I can customize per-site selectors.

- Commit/push fails:
  - Ensure `GH_PUSH_TOKEN` has write permission to the repo and is configured correctly.

## Maintenance / improvements
- Replace generic selectors in `scraper.py` with site-specific selectors for guaranteed accuracy.
- Add caching / rate-limiting to avoid IP bans.
- Add logging and Sentry for production debugging.
