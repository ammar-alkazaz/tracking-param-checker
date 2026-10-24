#!/usr/bin/env python3
"""
tracking-param-checker

Follows a landing page's redirect chain and reports whether ad click ids and
UTM parameters survive to the final URL, and whether the final page carries
Google Tag Manager, GA4 and Meta Pixel tags.

Why: a single redirect rule (http to https, www to non-www, trailing slash,
a plugin redirect) can silently strip gclid, fbclid and utm_* parameters.
Conversions then stop matching ad clicks and optimisation runs on partial data.

Usage:
    python check_tracking.py https://example.com/landing-page
    python check_tracking.py https://example.com/landing-page --slack-webhook https://hooks.slack.com/...
    python check_tracking.py --urls urls.txt

Exit code is 0 when every check passes, 1 when any check fails, so it can run
from cron or a CI job.
"""

import argparse
import json
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

TEST_PARAMS = {
    "gclid": "TEST_GCLID_123",
    "fbclid": "TEST_FBCLID_123",
    "utm_source": "tracking_check",
    "utm_medium": "test",
    "utm_campaign": "param_survival",
}

TAG_PATTERNS = {
    "Google Tag Manager": re.compile(r"googletagmanager\.com/gtm\.js|GTM-[A-Z0-9]{4,}"),
    "GA4 (gtag)": re.compile(r"googletagmanager\.com/gtag/js\?id=G-[A-Z0-9]+|G-[A-Z0-9]{6,}"),
    "Meta Pixel": re.compile(r"connect\.facebook\.net/[a-z_]+/fbevents\.js|fbq\(\s*['\"]init['\"]"),
}

USER_AGENT = "tracking-param-checker/1.0 (+https://github.com)"


def add_params(url: str) -> str:
    parts = urlparse(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    for key, value in TEST_PARAMS.items():
        query[key] = [value]
    return urlunparse(parts._replace(query=urlencode(query, doseq=True)))


def follow(url: str, timeout: int = 15):
    """Return the list of hops (status, url) and the final response."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    response = session.get(url, allow_redirects=True, timeout=timeout)
    hops = [(r.status_code, r.url) for r in response.history] + [(response.status_code, response.url)]
    return hops, response


def check(url: str, timeout: int = 15) -> dict:
    start = add_params(url)
    result = {"url": url, "start": start, "hops": [], "params": {}, "tags": {}, "ok": True, "error": None}
    try:
        hops, response = follow(start, timeout)
    except requests.RequestException as exc:
        result["ok"] = False
        result["error"] = str(exc)
        return result

    result["hops"] = hops
    final_query = parse_qs(urlparse(response.url).query)
    for key, value in TEST_PARAMS.items():
        survived = final_query.get(key, [None])[0] == value
        result["params"][key] = survived
        if not survived:
            result["ok"] = False

    body = response.text if response.ok else ""
    for name, pattern in TAG_PATTERNS.items():
        result["tags"][name] = bool(pattern.search(body))
    if response.status_code != 200:
        result["ok"] = False
    return result


def format_report(result: dict) -> str:
    lines = [f"URL: {result['url']}"]
    if result["error"]:
        lines.append(f"  ERROR: {result['error']}")
        return "\n".join(lines)
    lines.append("  Redirect chain:")
    for status, hop in result["hops"]:
        lines.append(f"    {status}  {hop}")
    lines.append("  Parameters at the final URL:")
    for key, survived in result["params"].items():
        lines.append(f"    {'PASS' if survived else 'FAIL'}  {key}")
    lines.append("  Tags on the final page:")
    for name, present in result["tags"].items():
        lines.append(f"    {'found' if present else 'missing'}  {name}")
    lines.append(f"  Result: {'PASS' if result['ok'] else 'FAIL'}")
    return "\n".join(lines)


def post_to_slack(webhook: str, text: str) -> None:
    requests.post(webhook, data=json.dumps({"text": text}), headers={"Content-Type": "application/json"}, timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that ad tracking parameters survive redirects.")
    parser.add_argument("urls", nargs="*", help="Landing page URLs to check")
    parser.add_argument("--urls", dest="urls_file", help="Text file with one URL per line")
    parser.add_argument("--slack-webhook", help="Post failures to this Slack incoming webhook")
    parser.add_argument("--timeout", type=int, default=15)
    args = parser.parse_args()

    urls = list(args.urls)
    if args.urls_file:
        with open(args.urls_file, encoding="utf-8") as handle:
            urls += [line.strip() for line in handle if line.strip() and not line.startswith("#")]
    if not urls:
        parser.error("give at least one URL or --urls file")

    all_ok = True
    failures = []
    for url in urls:
        result = check(url, args.timeout)
        report = format_report(result)
        print(report)
        print()
        if not result["ok"]:
            all_ok = False
            failures.append(report)

    if failures and args.slack_webhook:
        post_to_slack(args.slack_webhook, "Tracking parameter check failed:\n```" + "\n\n".join(failures) + "```")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
