# tracking-param-checker

A small Python tool that answers one question before you spend on ads: do `gclid`, `fbclid` and `utm_*` parameters survive the redirect chain to your landing page, and are Google Tag Manager, GA4 and the Meta Pixel actually on the final page?

I built the first version of this after finding a redirect that had been stripping click ids on a live campaign. The ad platform under-reported conversions for weeks and optimisation ran on partial data. The fix took ten minutes once it was found. Finding it took a lot longer, so now it is a script.

## What it does

1. Appends test values for `gclid`, `fbclid`, `utm_source`, `utm_medium` and `utm_campaign` to the URL you give it.
2. Follows every redirect and prints the chain with status codes.
3. Checks which parameters are still present at the final URL.
4. Scans the final page for GTM, GA4 (gtag) and Meta Pixel tags.
5. Prints PASS or FAIL per check and exits with code 1 on any failure, so it can run from cron or a CI job. Optionally posts failures to a Slack webhook.

## Install

```
pip install -r requirements.txt
```

## Use

```
python check_tracking.py https://example.com/landing-page
python check_tracking.py --urls urls.txt --slack-webhook https://hooks.slack.com/services/...
```

Example output:

```
URL: https://example.com/landing-page
  Redirect chain:
    301  http://example.com/landing-page?gclid=TEST_GCLID_123&...
    200  https://www.example.com/landing-page/?gclid=TEST_GCLID_123&...
  Parameters at the final URL:
    PASS  gclid
    PASS  fbclid
    PASS  utm_source
    PASS  utm_medium
    PASS  utm_campaign
  Tags on the final page:
    found  Google Tag Manager
    found  GA4 (gtag)
    missing  Meta Pixel
  Result: PASS
```

## Limits

- Tags injected by JavaScript after load (for example a consent manager) may not appear in the raw HTML. Treat a "missing" tag as a prompt to check in the browser, not as proof.
- The tool checks the URL, not the form. Confirm separately that your form's hidden fields read the parameters and send them to the CRM.

## Related

See the [attribution and tracking audit playbook](https://github.com/ammar-alkazaz/marketing-automation-playbooks/blob/main/05-attribution-and-tracking-audit.md) for the full procedure this tool belongs to.

MIT License.
