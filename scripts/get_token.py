"""One-time helper: obtain a Yahoo refresh token (run on your own computer).

1. Create an app at https://developer.yahoo.com/apps/ (type: Installed Application / Web,
   permission: Fantasy Sports -> Read, redirect URI: oob). Copy Client ID + Client Secret.
2. python scripts/get_token.py <client_id> <client_secret>
3. Open the printed URL, sign in as kobee2321@yahoo.com, approve, paste the code back here.
4. Save the printed YAHOO_REFRESH_TOKEN as a GitHub Actions secret (never commit it).
"""
import base64
import sys

import requests

if len(sys.argv) != 3:
    sys.exit(__doc__)
cid, sec = sys.argv[1:3]
print("Open this URL and approve access:\n")
print(f"https://api.login.yahoo.com/oauth2/request_auth?client_id={cid}&redirect_uri=oob&response_type=code&language=en-us\n")
code = input("Paste the code Yahoo shows: ").strip()
basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
r = requests.post("https://api.login.yahoo.com/oauth2/get_token",
                  headers={"Authorization": f"Basic {basic}"},
                  data={"grant_type": "authorization_code", "code": code, "redirect_uri": "oob"}, timeout=30)
r.raise_for_status()
print("\nYAHOO_REFRESH_TOKEN =", r.json()["refresh_token"])
