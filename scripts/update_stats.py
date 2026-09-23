#!/usr/bin/env python3
"""Build a self-hosted GitHub profile stats card with the workflow's token."""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape


LOGIN = "Shitao5"
QUERY = """
query ProfileStats($login: String!, $after: String) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { totalContributions }
      restrictedContributionsCount
    }
    followers { totalCount }
    repositories(first: 100, after: $after, privacy: PUBLIC, ownerAffiliations: OWNER) {
      totalCount
      nodes { stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""


def fetch_stats(token):
    stars = 0
    after = None
    stats = None
    while True:
        payload = json.dumps({"query": QUERY, "variables": {"login": LOGIN, "after": after}}).encode()
        request = Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "Shitao5-profile-stats",
            },
        )
        try:
            with urlopen(request, timeout=25) as response:
                result = json.load(response)
        except HTTPError as error:
            raise RuntimeError(f"GitHub GraphQL returned HTTP {error.code}") from error
        if result.get("errors"):
            raise RuntimeError(f"GitHub GraphQL errors: {result['errors']}")
        user = result.get("data", {}).get("user")
        if not user:
            raise RuntimeError("GitHub did not return the requested user")
        repos = user["repositories"]
        stars += sum(repo["stargazerCount"] for repo in repos["nodes"])
        stats = {
            "contributions": (
                user["contributionsCollection"]["contributionCalendar"]["totalContributions"]
                + user["contributionsCollection"]["restrictedContributionsCount"]
            ),
            "repositories": repos["totalCount"],
            "stars": stars,
            "followers": user["followers"]["totalCount"],
        }
        if not repos["pageInfo"]["hasNextPage"]:
            return stats
        after = repos["pageInfo"]["endCursor"]
        if not after:
            raise RuntimeError("GitHub pagination omitted the next cursor")


def render_svg(stats, updated):
    metrics = [
        ("Contributions", "past year", stats["contributions"], 26, 96),
        ("Public repos", "owned", stats["repositories"], 260, 96),
        ("Stars earned", "public repos", stats["stars"], 26, 152),
        ("Followers", "current", stats["followers"], 260, 152),
    ]
    pieces = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="495" height="198" viewBox="0 0 495 198" role="img" aria-labelledby="title desc">',
        '<title id="title">Shitao5 GitHub statistics</title>',
        '<desc id="desc">Automatically refreshed public GitHub profile statistics.</desc>',
        '<rect x="0.5" y="0.5" width="494" height="197" rx="10" fill="#ffffff" stroke="#d0d7de"/>',
        '<text x="25" y="34" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="19" font-weight="700" fill="#24292f">Shitao5 GitHub Stats</text>',
        '<text x="25" y="57" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="11" fill="#57606a">Updated ' + escape(updated) + ' · public data</text>',
        '<line x1="25" y1="70" x2="470" y2="70" stroke="#d8dee4"/>',
    ]
    for label, note, number, x, y in metrics:
        pieces.extend([
            f'<circle cx="{x + 7}" cy="{y - 7}" r="6" fill="#2da44e"/>',
            f'<text x="{x + 23}" y="{y}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="13" fill="#57606a">{escape(label)}</text>',
            f'<text x="{x + 23}" y="{y + 28}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="24" font-weight="700" fill="#24292f">{number:,}</text>',
            f'<text x="{x + 88}" y="{y + 27}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="11" fill="#6e7781">{escape(note)}</text>',
        ])
    pieces.append('</svg>')
    return "\n".join(pieces) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", help="JSON file for offline rendering checks")
    parser.add_argument("--output", default="assets/github-stats.svg")
    args = parser.parse_args()
    if args.fixture:
        stats = json.loads(Path(args.fixture).read_text())
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN is required when no fixture is supplied")
        stats = fetch_stats(token)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_svg(stats, updated), encoding="utf-8")
    print(f"Wrote {output}: {stats}")


if __name__ == "__main__":
    main()
