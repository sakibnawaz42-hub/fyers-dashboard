"""
Run this LOCALLY (on your own PC) once per day (Fyers tokens expire daily,
usually reset a little after midnight) to generate a fresh access_token.

Steps:
1. Fill CLIENT_ID, SECRET_KEY, REDIRECT_URI below (from your Fyers API app).
2. Run: python generate_token.py
3. A URL will print — open it in a browser, log in to Fyers, approve.
4. You'll be redirected to your REDIRECT_URI with `auth_code=...` in the URL.
   Copy that auth_code value.
5. Paste it when prompted here.
6. The script prints your access_token — put it into:
   - Streamlit Cloud: App -> Settings -> Secrets -> FYERS_ACCESS_TOKEN
   - or paste it directly into the dashboard sidebar.
"""

from fyers_apiv3 import fyersModel

CLIENT_ID = "YOUR_APP_ID-100"        # e.g. ABC123XYZ-100
SECRET_KEY = "YOUR_SECRET_KEY"        # from Fyers app dashboard
REDIRECT_URI = "https://your-redirect-url.com"  # must match your Fyers app exactly

session = fyersModel.SessionModel(
    client_id=CLIENT_ID,
    secret_key=SECRET_KEY,
    redirect_uri=REDIRECT_URI,
    response_type="code",
    grant_type="authorization_code",
)

print("\nStep 1: Open this URL, login, approve access:\n")
print(session.generate_authcode())

auth_code = input("\nStep 2: Paste the auth_code from the redirected URL here: ").strip()

session.set_token(auth_code)
response = session.generate_token()

try:
    access_token = response["access_token"]
    print("\n✅ SUCCESS — your access token:\n")
    print(access_token)
    print("\nSave this somewhere safe. It expires daily.")
except Exception as e:
    print("\n❌ Failed to generate token.")
    print("Response was:", response)
    print("Error:", e)
